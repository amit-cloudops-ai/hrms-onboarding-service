import json
import unittest
from unittest.mock import Mock

from botocore.exceptions import ClientError

from callbacks import CallbackConflict, resume_stage


class ResumeStageTests(unittest.TestCase):
    def setUp(self):
        self.table = Mock()
        self.table.get_item.return_value = {
            "Item": {
                "employee_id": "emp-123",
                "stage": "policy_signoff",
                "status": "in_progress",
                "task_token": "secret-token",
            }
        }
        self.stepfunctions = Mock()

    def test_resumes_callback_without_returning_token(self):
        result = resume_stage(
            "emp-123",
            "policy_signoff",
            authorized=True,
            table=self.table,
            stepfunctions=self.stepfunctions,
        )

        self.stepfunctions.send_task_success.assert_called_once()
        args = self.stepfunctions.send_task_success.call_args.kwargs
        self.assertEqual(args["taskToken"], "secret-token")
        self.assertEqual(json.loads(args["output"])["status"], "complete")
        self.assertNotIn("task_token", result)
        self.assertNotIn("secret-token", repr(result))
        self.assertEqual(result["status"], "completion_submitted")

    def test_rejects_unauthorized_caller_before_database_access(self):
        with self.assertRaises(PermissionError):
            resume_stage(
                "emp-123", "policy_signoff", authorized=False,
                table=self.table, stepfunctions=self.stepfunctions,
            )
        self.table.get_item.assert_not_called()

    def test_rejects_stage_not_in_progress(self):
        self.table.get_item.return_value = {
            "Item": {"status": "complete", "task_token": "secret-token"}
        }
        with self.assertRaisesRegex(ValueError, "not awaiting completion"):
            resume_stage(
                "emp-123", "policy_signoff", authorized=True,
                table=self.table, stepfunctions=self.stepfunctions,
            )

    def test_rejects_missing_token(self):
        self.table.get_item.return_value = {
            "Item": {"status": "in_progress"}
        }
        with self.assertRaisesRegex(ValueError, "No active callback"):
            resume_stage(
                "emp-123", "policy_signoff", authorized=True,
                table=self.table, stepfunctions=self.stepfunctions,
            )

    def test_rejects_unknown_stage(self):
        with self.assertRaisesRegex(ValueError, "Unknown onboarding stage"):
            resume_stage(
                "emp-123", "unknown", authorized=True,
                table=self.table, stepfunctions=self.stepfunctions,
            )

    def test_rejects_empty_employee_id(self):
        with self.assertRaisesRegex(ValueError, "employee_id is required"):
            resume_stage(
                " ", "policy_signoff", authorized=True,
                table=self.table, stepfunctions=self.stepfunctions,
            )

    def test_stale_or_consumed_tokens_become_callback_conflicts(self):
        for code in ("InvalidToken", "TaskDoesNotExist", "TaskTimedOut"):
            with self.subTest(code=code):
                self.stepfunctions.send_task_success.side_effect = ClientError(
                    {"Error": {"Code": code, "Message": "test"}},
                    "SendTaskSuccess",
                )
                with self.assertRaises(CallbackConflict):
                    resume_stage(
                        "emp-123", "policy_signoff", authorized=True,
                        table=self.table, stepfunctions=self.stepfunctions,
                    )
                self.stepfunctions.send_task_success.reset_mock()
                self.stepfunctions.send_task_success.side_effect = None

    def test_unexpected_aws_errors_propagate(self):
        self.stepfunctions.send_task_success.side_effect = ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "test"}},
            "SendTaskSuccess",
        )
        with self.assertRaises(ClientError):
            resume_stage(
                "emp-123", "policy_signoff", authorized=True,
                table=self.table, stepfunctions=self.stepfunctions,
            )


if __name__ == "__main__":
    unittest.main()
