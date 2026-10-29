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
            choice["Variable"]: choice["Next"]
            for choice in states["SelectNextStage"]["Choices"]
        }
        self.assertEqual(choices["$.current_stage"], "SetITProvisioning")
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


if __name__ == "__main__":
    unittest.main()
