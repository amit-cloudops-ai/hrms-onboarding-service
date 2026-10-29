"""Offline WP4 tests; no AWS resources or real provisioning are used."""
import json
import unittest
from io import BytesIO
from unittest.mock import Mock, patch

from botocore.exceptions import ClientError

from services.stages import handler


class StageStartTests(unittest.TestCase):
    def setUp(self):
        self.table = Mock()
        self.table.get_item.return_value = {"Item": {
            "employee_id": "emp-1", "stage": "it_provisioning",
            "status": "in_progress", "task_token": "private-task-token",
        }}

    def test_simulated_it_provisioning_resumes_waiting_state_machine(self):
        sfn = Mock()
        with patch.dict(handler.os.environ, {"SIMULATION_MODE": "true"}):
            result = handler._it_provisioning("emp-1", "private-task-token", sfn=sfn)
        self.assertEqual(result["mode"], "simulated")
        self.assertEqual(result["status"], "completion_submitted")
        sfn.send_task_success.assert_called_once()
        kwargs = sfn.send_task_success.call_args.kwargs
        self.assertEqual(kwargs["taskToken"], "private-task-token")
        self.assertNotIn("private-task-token", kwargs["output"])

    def test_real_provisioning_requires_configured_provider(self):
        with patch.dict(handler.os.environ, {"SIMULATION_MODE": "false", "PROVISIONING_FUNCTION_NAME": ""}):
            with self.assertRaisesRegex(RuntimeError, "PROVISIONING_FUNCTION_NAME"):
                handler._it_provisioning("emp-1", "token", sfn=Mock())

    def test_real_provisioning_provider_must_confirm_success(self):
        lambda_client = Mock()
        lambda_client.invoke.return_value = {"Payload": BytesIO(b'{"ok":true,"ticket":"IT-123"}')}
        sfn = Mock()
        with patch.dict(handler.os.environ, {"SIMULATION_MODE": "false", "PROVISIONING_FUNCTION_NAME": "it-provider"}):
            result = handler._it_provisioning("emp-1", "token", sfn=sfn, lambda_client=lambda_client)
        self.assertEqual(result["mode"], "real")
        lambda_client.invoke.assert_called_once()
        sfn.send_task_success.assert_called_once()

    def test_start_stage_waits_for_human_document_and_policy_events(self):
        self.table.get_item.return_value = {"Item": {
            "employee_id": "emp-1", "status": "in_progress", "task_token": "token"
        }}
        for stage in ("document_collection", "policy_signoff", "manager_intro"):
            self.table.get_item.return_value["Item"]["stage"] = stage
            with patch.dict(handler.os.environ, {"STAGE_NOTIFICATION_TOPIC_ARN": ""}):
                result = handler.start_stage(
                    {"employee_id": "emp-1", "stage": stage, "taskToken": "token"},
                    stages_table=self.table, sfn=Mock(), sns=Mock()
                )
            self.assertEqual(result["status"], "waiting_for_completion")

    def test_stage_token_must_match_current_record(self):
        with self.assertRaisesRegex(ValueError, "not active"):
            handler.start_stage(
                {"employee_id": "emp-1", "stage": "it_provisioning", "taskToken": "different"},
                stages_table=self.table
            )


class PolicySignoffTests(unittest.TestCase):
    def setUp(self):
        self.employees = Mock()
        self.employees.get_item.return_value = {"Item": {"employee_id": "emp-1", "cognito_sub": "sub-1"}}
        self.stages = Mock()
        self.stages.get_item.return_value = {"Item": {
            "employee_id": "emp-1", "stage": "policy_signoff",
            "status": "in_progress", "task_token": "secret-token",
        }}
        self.stages.update_item.return_value = {"Attributes": {"policy_acceptances": {
            "acceptable-use": {"accepted": True}, "privacy": {"accepted": True}, "security": {"accepted": True}
        }}}

    def test_acceptance_is_bound_to_cognito_subject(self):
        response = handler.sign_policy(
            {"employee_id": "emp-1", "caller": {"sub": "other"}, "policy": {
                "policy_id": "acceptable-use", "policy_version": "v1", "accepted": True
            }}, employees_table=self.employees, stages_table=self.stages
        )
        self.assertEqual(response["statusCode"], 403)
        self.stages.update_item.assert_not_called()

    def test_policy_acceptance_persists_and_completes_when_all_required_are_signed(self):
        sfn = Mock()
        response = handler.sign_policy(
            {"employee_id": "emp-1", "caller": {"sub": "sub-1"}, "policy": {
                "policy_id": "acceptable-use", "policy_version": "v1", "accepted": True
            }}, employees_table=self.employees, stages_table=self.stages, sfn=sfn, now="now"
        )
        self.assertEqual(response["statusCode"], 200)
        self.assertTrue(json.loads(response["body"])["required_policies_complete"])
        self.assertEqual(self.stages.update_item.call_count, 2)
        sfn.send_task_success.assert_called_once()

    def test_rejects_unaccepted_policy(self):
        response = handler.sign_policy(
            {"employee_id": "emp-1", "caller": {"sub": "sub-1"}, "policy": {
                "policy_id": "acceptable-use", "policy_version": "v1", "accepted": False
            }}, employees_table=self.employees, stages_table=self.stages
        )
        self.assertEqual(response["statusCode"], 400)

    def test_expired_callback_returns_conflict_not_success(self):
        sfn = Mock()
        sfn.send_task_success.side_effect = ClientError(
            {"Error": {"Code": "TaskTimedOut", "Message": "expired"}}, "SendTaskSuccess"
        )
        result = handler._complete("emp-1", "policy_signoff", table=self.stages, sfn=sfn, source="policy_acceptance")
        self.assertEqual(result["status"], 409)
        self.assertEqual(result["code"], "STAGE_CALLBACK_EXPIRED")


class DocumentCompletionTests(unittest.TestCase):
    def test_document_stage_requires_all_three_verified_documents(self):
        docs = Mock()
        docs.query.return_value = {"Items": [
            {"doc_type": "id_proof", "status": "verified"},
            {"doc_type": "degree_certificate", "status": "uploaded"},
            {"doc_type": "signed_offer_letter", "status": "verified"},
        ]}
        result = handler.complete_stage(
            {"employee_id": "emp-1", "stage": "document_collection", "source": "document_validation"},
            documents_table=docs
        )
        self.assertEqual(result["statusCode"], 409)

    def test_manager_intro_requires_admin_claim(self):
        employees = Mock()
        employees.get_item.return_value = {"Item": {"employee_id": "emp-1"}}
        result = handler.complete_stage(
            {"employee_id": "emp-1", "stage": "manager_intro", "source": "hr_admin", "caller": {"is_admin": False}},
            employees_table=employees
        )
        self.assertEqual(result["statusCode"], 403)


if __name__ == "__main__":
    unittest.main()
