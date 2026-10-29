"""Offline onboarding journey contract/integration checks.

These tests exercise the real handlers with mocked AWS dependencies. They never
call AWS or claim to prove live AWS integration.
"""
import json
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock, patch

from services.documents import handler as documents
from services.stages import handler as stages


ROOT = Path(__file__).resolve().parents[1]
with (ROOT / "services/workflow/state_machine.asl.json").open(encoding="utf-8") as handle:
    STATE_MACHINE = json.load(handle)


class WorkflowDefinitionJourneyTests(unittest.TestCase):
    def test_four_stage_order_and_timeout_reminder_retry_are_explicit(self):
        states = STATE_MACHINE["States"]
        self.assertEqual(STATE_MACHINE["StartAt"], "RunStage")
        self.assertEqual(states["RunStage"]["TimeoutSeconds"], 86400)
        self.assertEqual(states["RunStage"]["Next"], "MarkStageComplete")
        timeout_catches = states["RunStage"]["Catch"]
        self.assertTrue(any("States.Timeout" in item["ErrorEquals"] and item["Next"] == "SendReminder" for item in timeout_catches))
        self.assertEqual(states["SendReminder"]["Next"], "RunStage")

        choices = {
            choice["StringEquals"]: choice["Next"]
            for choice in states["SelectNextStage"]["Choices"]
        }
        self.assertEqual(
            [choice["StringEquals"] for choice in states["SelectNextStage"]["Choices"]],
            ["document_collection", "it_provisioning", "policy_signoff", "manager_intro"],
        )
        self.assertEqual(
            [choice["Next"] for choice in states["SelectNextStage"]["Choices"]],
            ["SetITProvisioning", "SetPolicySignoff", "SetManagerIntro", "WorkflowComplete"],
        )
        self.assertEqual(states["WorkflowComplete"]["Type"], "Succeed")


class DocumentStageJourneyTests(unittest.TestCase):
    def test_document_stage_cannot_complete_until_all_three_files_are_verified(self):
        table = Mock()
        table.query.return_value = {"Items": [
            {"doc_type": "id_proof", "status": "verified"},
            {"doc_type": "degree_certificate", "status": "verified"},
            {"doc_type": "signed_offer_letter", "status": "missing"},
        ]}
        stage_table = Mock()
        stage_table.get_item.return_value = {"Item": {
            "employee_id": "emp-1", "stage": "document_collection",
            "status": "in_progress", "task_token": "private-document-token",
        }}
        sfn = Mock()
        response = stages.complete_stage(
            {"employee_id": "emp-1", "stage": "document_collection", "source": "document_validation"},
            documents_table=table, stages_table=stage_table, sfn=sfn,
        )
        self.assertEqual(response["statusCode"], 409)
        self.assertEqual(json.loads(response["body"])["error"]["code"], "DOCUMENTS_INCOMPLETE")
        sfn.send_task_success.assert_not_called()

        table.query.return_value = {"Items": [
            {"doc_type": "id_proof", "status": "verified"},
            {"doc_type": "degree_certificate", "status": "verified"},
            {"doc_type": "signed_offer_letter", "status": "verified"},
        ]}
        response = stages.complete_stage(
            {"employee_id": "emp-1", "stage": "document_collection", "source": "document_validation"},
            documents_table=table, stages_table=stage_table, sfn=sfn,
        )
        self.assertEqual(response["statusCode"], 202)
        self.assertEqual(json.loads(response["body"])["status"], "completion_submitted")
        sfn.send_task_success.assert_called_once()
        self.assertNotIn("private-document-token", response["body"])

    def test_invalid_magic_bytes_reject_upload_and_notify_hr(self):
        key = "emp-1/id_proof/" + "a" * 32 + ".pdf"
        table = Mock()
        table.get_item.return_value = {"Item": {
            "employee_id": "emp-1", "doc_type": "id_proof", "s3_key": key,
            "status": "missing", "file_size": 12, "content_type": "application/pdf",
        }}
        table.query.return_value = {"Items": [
            {"doc_type": "id_proof", "status": "rejected"},
            {"doc_type": "degree_certificate", "status": "missing"},
            {"doc_type": "signed_offer_letter", "status": "missing"},
        ]}
        s3 = Mock()
        s3.head_object.return_value = {"ContentLength": 12, "ContentType": "application/pdf"}
        body = Mock()
        body.read.return_value = b"<html>bad</html>"
        s3.get_object.return_value = {"Body": body}
        notifications = Mock()
        with patch.dict(documents.os.environ, {"HR_NOTIFICATION_TOPIC_ARN": "arn:aws:sns:us-east-1:123456789012:hrms-notify"}):
            result = documents.verify_uploaded_object(
                "private-bucket", key, documents_table=table, s3=s3, sns=notifications, now="now"
            )
        self.assertEqual(result["status"], "rejected")
        self.assertFalse(result["ok"])
        s3.delete_object.assert_called_once()
        notifications.publish.assert_called_once()
        message = json.loads(notifications.publish.call_args.kwargs["Message"])
        self.assertEqual(message["reason"], "file_validation_failed")
        self.assertNotIn("private-bucket", notifications.publish.call_args.kwargs["Message"])


class HumanStageJourneyTests(unittest.TestCase):
    def test_policy_signoff_advances_only_after_all_three_required_policies(self):
        employees = Mock()
        employees.get_item.return_value = {"Item": {"employee_id": "emp-1", "cognito_sub": "sub-1"}}
        stage_table = Mock()
        stage_table.get_item.return_value = {"Item": {
            "employee_id": "emp-1", "stage": "policy_signoff",
            "status": "in_progress", "task_token": "private-policy-token",
        }}
        stored = {}

        def update_item(**kwargs):
            values = kwargs.get("ExpressionAttributeValues", {})
            if ":empty" in values:
                stored.setdefault("policy_acceptances", {})
            if ":acceptance" in values:
                policy_id = kwargs["ExpressionAttributeNames"]["#policy"]
                stored["policy_acceptances"][policy_id] = values[":acceptance"]
            return {"Attributes": {"policy_acceptances": dict(stored.get("policy_acceptances", {}))}}

        stage_table.update_item.side_effect = update_item
        sfn = Mock()
        outcomes = []
        for policy_id in ("acceptable-use", "privacy", "security"):
            response = stages.sign_policy(
                {
                    "employee_id": "emp-1",
                    "caller": {"sub": "sub-1", "is_admin": False},
                    "policy": {"policy_id": policy_id, "policy_version": "v1", "accepted": True},
                },
                employees_table=employees, stages_table=stage_table, sfn=sfn, now="now",
            )
            self.assertEqual(response["statusCode"], 200)
            outcomes.append(json.loads(response["body"])["required_policies_complete"])
        self.assertEqual(outcomes, [False, False, True])
        sfn.send_task_success.assert_called_once()
        self.assertNotIn("private-policy-token", sfn.send_task_success.call_args.kwargs["output"])

    def test_manager_intro_requires_admin_and_then_submits_callback(self):
        employees = Mock()
        employees.get_item.return_value = {"Item": {"employee_id": "emp-1", "cognito_sub": "sub-1"}}
        stage_table = Mock()
        stage_table.get_item.return_value = {"Item": {
            "employee_id": "emp-1", "stage": "manager_intro",
            "status": "in_progress", "task_token": "private-manager-token",
        }}
        sfn = Mock()
        denied = stages.complete_stage(
            {
                "employee_id": "emp-1", "stage": "manager_intro", "source": "hr_admin",
                "caller": {"sub": "sub-1", "is_admin": False},
            },
            employees_table=employees, stages_table=stage_table, sfn=sfn,
        )
        self.assertEqual(denied["statusCode"], 403)
        sfn.send_task_success.assert_not_called()

        accepted = stages.complete_stage(
            {
                "employee_id": "emp-1", "stage": "manager_intro", "source": "hr_admin",
                "caller": {"sub": "hr-sub", "is_admin": True},
            },
            employees_table=employees, stages_table=stage_table, sfn=sfn,
        )
        self.assertEqual(accepted["statusCode"], 202)
        self.assertEqual(json.loads(accepted["body"])["status"], "completion_submitted")
        sfn.send_task_success.assert_called_once()
        self.assertNotIn("private-manager-token", accepted["body"])

    def test_expired_stage_callback_is_not_reported_as_success(self):
        from botocore.exceptions import ClientError

        stage_table = Mock()
        stage_table.get_item.return_value = {"Item": {
            "employee_id": "emp-1", "stage": "manager_intro",
            "status": "in_progress", "task_token": "expired-token",
        }}
        sfn = Mock()
        sfn.send_task_success.side_effect = ClientError(
            {"Error": {"Code": "TaskTimedOut", "Message": "expired"}}, "SendTaskSuccess"
        )
        response = stages.complete_stage(
            {
                "employee_id": "emp-1", "stage": "manager_intro", "source": "hr_admin",
                "caller": {"sub": "hr-sub", "is_admin": True},
            },
            employees_table=Mock(get_item=Mock(return_value={"Item": {"employee_id": "emp-1"}})),
            stages_table=stage_table, sfn=sfn,
        )
        self.assertEqual(response["statusCode"], 409)
        self.assertNotIn("expired-token", response["body"])




class MemoryEmployeesTable:
    def __init__(self):
        self.items = {}

    def put_item(self, **kwargs):
        item = dict(kwargs["Item"])
        self.items[item["employee_id"]] = item
        return {}

    def get_item(self, **kwargs):
        item = self.items.get(kwargs["Key"]["employee_id"])
        return {"Item": dict(item) if item else {}}

    def update_item(self, **kwargs):
        item = self.items[kwargs["Key"]["employee_id"]]
        values = kwargs.get("ExpressionAttributeValues", {})
        if ":sub" in values:
            item["cognito_sub"] = values[":sub"]
        return {"Attributes": dict(item)}

    def delete_item(self, **kwargs):
        self.items.pop(kwargs["Key"]["employee_id"], None)
        return {}


class MemoryDocumentsTable:
    def __init__(self):
        self.items = {}

    def put_item(self, **kwargs):
        item = dict(kwargs["Item"])
        key = (item["employee_id"], item["doc_type"])
        if key in self.items:
            raise AssertionError("Unexpected duplicate document setup in success path")
        self.items[key] = item
        return {}

    def get_item(self, **kwargs):
        key = (kwargs["Key"]["employee_id"], kwargs["Key"]["doc_type"])
        item = self.items.get(key)
        return {"Item": dict(item) if item else {}}

    def query(self, **kwargs):
        return {"Items": [dict(item) for item in self.items.values()]}

    def update_item(self, **kwargs):
        key = (kwargs["Key"]["employee_id"], kwargs["Key"]["doc_type"])
        item = self.items[key]
        values = kwargs.get("ExpressionAttributeValues", {})
        if ":status" in values:
            item["status"] = values[":status"]
        if ":key" in values:
            item["s3_key"] = values[":key"]
        if ":size" in values:
            item["file_size"] = values[":size"]
        if ":type" in values:
            item["content_type"] = values[":type"]
        if ":now" in values:
            item["validated_at"] = values[":now"]
        return {"Attributes": dict(item)}


class MemoryStagesTable:
    def __init__(self, employee_id):
        self.records = {}
        order = ("document_collection", "it_provisioning", "policy_signoff", "manager_intro")
        for index, stage in enumerate(order):
            token = f"journey-token-{stage}"
            self.records[(employee_id, stage)] = {
                "employee_id": employee_id,
                "stage": stage,
                "status": "in_progress" if index == 0 else "pending",
                **({"task_token": token} if index == 0 else {}),
            }

    def get_item(self, **kwargs):
        item = self.records.get((kwargs["Key"]["employee_id"], kwargs["Key"]["stage"]))
        return {"Item": dict(item) if item else {}}

    def update_item(self, **kwargs):
        key = (kwargs["Key"]["employee_id"], kwargs["Key"]["stage"])
        record = self.records[key]
        values = kwargs.get("ExpressionAttributeValues", {})
        names = kwargs.get("ExpressionAttributeNames", {})
        if ":empty" in values:
            record.setdefault("policy_acceptances", {})
        if ":acceptance" in values:
            policy_id = names["#policy"]
            record.setdefault("policy_acceptances", {})[policy_id] = values[":acceptance"]
        return {"Attributes": dict(record)}


class MemoryEquipmentTable:
    def __init__(self):
        self.items = {}

    def put_item(self, **kwargs):
        item = dict(kwargs["Item"])
        self.items[item["asset_id"]] = item
        return {}


class MockCognito:
    def admin_create_user(self, **kwargs):
        return {"User": {"Attributes": [{"Name": "sub", "Value": "cognito-sub-journey"}]}}


class MockStepFunctions:
    def __init__(self, stage_table, employee_id):
        self.stage_table = stage_table
        self.employee_id = employee_id
        self.completed = []

    def send_task_success(self, *, taskToken, output):
        payload = json.loads(output)
        stage = payload["stage"]
        record = self.stage_table.records[(self.employee_id, stage)]
        if record.get("task_token") != taskToken or record.get("status") != "in_progress":
            raise AssertionError("Callback token does not match the active stage")
        record["status"] = "complete"
        record.pop("task_token", None)
        self.completed.append(stage)
        order = ("document_collection", "it_provisioning", "policy_signoff", "manager_intro")
        next_index = order.index(stage) + 1
        if next_index < len(order):
            next_stage = order[next_index]
            next_record = self.stage_table.records[(self.employee_id, next_stage)]
            next_record["status"] = "in_progress"
            next_record["task_token"] = f"journey-token-{next_stage}"


class FullOnboardingJourneyTests(unittest.TestCase):
    def test_create_employee_to_day_one_ready_using_real_handlers_and_mocked_aws(self):
        from services.identity import handler as identity

        employee_id = "emp-journey-001"
        employees = MemoryEmployeesTable()
        docs = MemoryDocumentsTable()
        stage_records = MemoryStagesTable(employee_id)
        equipment = MemoryEquipmentTable()
        sfn = MockStepFunctions(stage_records, employee_id)
        s3 = Mock()
        s3.generate_presigned_url.return_value = "https://signed.example/presigned"
        s3.head_object.return_value = {"ContentLength": 1024, "ContentType": "application/pdf"}
        pdf_body = Mock()
        pdf_body.read.return_value = b"%PDF-1.7 sample document bytes"
        s3.get_object.return_value = {"Body": pdf_body}
        notify_hr = Mock()

        employee = identity.create_employee(
            {
                "full_name": "Taylor Morgan",
                "email": "taylor.morgan@example.com",
                "department": "Engineering",
                "role": "Software Engineer",
                "joining_date": "2026-11-16",
                "employment_type": "full-time",
            },
            table=employees,
            cognito=MockCognito(),
            user_pool_id="test-pool",
            employee_id=employee_id,
            now="2026-10-29T00:00:00+00:00",
        )
        self.assertEqual(employee["employee_id"], employee_id)
        self.assertEqual(employees.items[employee_id]["cognito_sub"], "cognito-sub-journey")

        def submit_document_stage(employee_key):
            return stages.complete_stage(
                {"employee_id": employee_key, "stage": "document_collection", "source": "document_validation"},
                employees_table=employees, documents_table=docs, stages_table=stage_records, sfn=sfn,
            )

        with patch.dict(documents.os.environ, {
            "DOCUMENTS_BUCKET": "private-test-bucket",
            "UPLOAD_URL_TTL_SECONDS": "300",
            "STAGES_FUNCTION_NAME": "mock-stage-adapter",
            "HR_NOTIFICATION_TOPIC_ARN": "arn:aws:sns:us-east-1:123456789012:hrms-test",
        }), patch.object(documents, "_complete_document_stage", side_effect=submit_document_stage):
            # Request all three presigned URLs first, just as the employee portal does.
            for doc_type in documents.DOCUMENT_TYPES:
                request = {
                    "employee_id": employee_id,
                    "caller": {"sub": "cognito-sub-journey", "is_admin": False},
                    "document": {"document_type": doc_type, "content_type": "application/pdf", "file_size": 1024},
                }
                signed = documents.create_upload_url(request, documents_table=docs, employees_table=employees, s3=s3, now="now")
                self.assertEqual(signed["statusCode"], 201)
            # Simulate S3 ObjectCreated notifications for each valid PDF. The real validator
            # checks size, content type, and magic bytes, then invokes document-stage completion.
            for doc_type in documents.DOCUMENT_TYPES:
                key = docs.items[(employee_id, doc_type)]["s3_key"]
                verified = documents.verify_uploaded_object("private-test-bucket", key, documents_table=docs, s3=s3, sns=notify_hr, now="now")
                self.assertEqual(verified["status"], "verified")
        self.assertEqual(stage_records.records[(employee_id, "document_collection")]["status"], "complete")
        self.assertEqual(stage_records.records[(employee_id, "it_provisioning")]["status"], "in_progress")

        token = stage_records.records[(employee_id, "it_provisioning")]["task_token"]
        with patch.dict(stages.os.environ, {"SIMULATION_MODE": "true"}):
            it_result = stages._it_provisioning(employee_id, token, sfn=sfn, equipment_table=equipment)
        self.assertEqual(it_result["status"], "completion_submitted")
        self.assertEqual(len(equipment.items), 2)
        self.assertEqual(stage_records.records[(employee_id, "policy_signoff")]["status"], "in_progress")

        # Each policy is saved separately; the workflow advances only on the third required acceptance.
        policy_results = []
        for policy_id in ("acceptable-use", "privacy", "security"):
            response = stages.sign_policy(
                {
                    "employee_id": employee_id,
                    "caller": {"sub": "cognito-sub-journey", "is_admin": False},
                    "policy": {"policy_id": policy_id, "policy_version": "v1", "accepted": True},
                },
                employees_table=employees, stages_table=stage_records, sfn=sfn, now="now",
            )
            policy_results.append(json.loads(response["body"])["required_policies_complete"])
        self.assertEqual(policy_results, [False, False, True])
        self.assertEqual(stage_records.records[(employee_id, "manager_intro")]["status"], "in_progress")

        manager_result = stages.complete_stage(
            {
                "employee_id": employee_id,
                "stage": "manager_intro",
                "source": "hr_admin",
                "caller": {"sub": "hr-admin-sub", "is_admin": True},
            },
            employees_table=employees, stages_table=stage_records, sfn=sfn,
        )
        self.assertEqual(manager_result["statusCode"], 202)
        self.assertEqual(
            sfn.completed,
            ["document_collection", "it_provisioning", "policy_signoff", "manager_intro"],
        )
        self.assertTrue(all(record["status"] == "complete" for record in stage_records.records.values()))
        self.assertEqual(
            {item["status"] for item in docs.items.values()},
            {"verified"},
        )
        self.assertTrue(all(item["status"] == "assigned" for item in equipment.items.values()))
        self.assertNotIn("task_token", json.dumps(stage_records.records))


if __name__ == "__main__":
    unittest.main()
