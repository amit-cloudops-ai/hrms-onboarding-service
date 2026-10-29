"""Unit tests for WP2 workflow stage helpers."""
import os
import unittest
from unittest.mock import Mock, patch

from handler import (
    VALID_STAGES,
    lambda_handler,
    mark_stage_complete,
    send_reminder,
    start_stage,
)


class StartStageTests(unittest.TestCase):
    def setUp(self):
        self.table = Mock()
        self.event = {
            "employee_id": "employee-123",
            "stage": "document_collection",
            "taskToken": "secret-task-token",
        }

    def test_stores_callback_token_but_never_returns_it(self):
        result = start_stage(
            self.event,
            table=self.table,
            now="2026-10-29T12:00:00+00:00",
        )
        kwargs = self.table.update_item.call_args.kwargs
        self.assertEqual(
            kwargs["Key"],
            {"employee_id": "employee-123", "stage": "document_collection"},
        )
        self.assertEqual(
            kwargs["ExpressionAttributeValues"][":token"],
            "secret-task-token",
        )
        self.assertNotIn("taskToken", result)
        self.assertNotIn("secret-task-token", str(result))
        self.assertEqual(result["status"], "in_progress")

    def test_rejects_missing_task_token(self):
        with self.assertRaisesRegex(ValueError, "taskToken"):
            start_stage({**self.event, "taskToken": ""}, table=self.table)
        self.table.update_item.assert_not_called()

    def test_rejects_unknown_stage(self):
        with self.assertRaisesRegex(ValueError, "Unsupported stage"):
            start_stage({**self.event, "stage": "unknown"}, table=self.table)
        self.table.update_item.assert_not_called()

    def test_accepts_only_the_four_contract_stages(self):
        self.assertEqual(len(VALID_STAGES), 4)


class MarkStageCompleteTests(unittest.TestCase):
    def test_marks_complete_and_removes_task_token(self):
        table = Mock()
        result = mark_stage_complete(
            {
                "employee_id": "employee-123",
                "stage": "it_provisioning",
            },
            table=table,
            now="2026-10-29T12:00:00+00:00",
        )
        kwargs = table.update_item.call_args.kwargs
        self.assertIn("REMOVE task_token", kwargs["UpdateExpression"])
        self.assertEqual(kwargs["ExpressionAttributeValues"][":complete"], "complete")
        self.assertEqual(result["status"], "complete")

    def test_rejects_unknown_stage(self):
        with self.assertRaises(ValueError):
            mark_stage_complete(
                {"employee_id": "employee-123", "stage": "other"},
                table=Mock(),
            )


class ReminderTests(unittest.TestCase):
    @patch.dict(os.environ, {"REMINDER_TOPIC_ARN": "arn:aws:sns:us-east-1:123:topic"})
    def test_increments_count_and_publishes_reminder(self):
        table = Mock()
        table.update_item.return_value = {"Attributes": {"reminder_count": 2}}
        sns = Mock()
        result = send_reminder(
            {
                "employee_id": "employee-123",
                "stage": "policy_signoff",
            },
            table=table,
            sns=sns,
            now="2026-10-29T12:00:00+00:00",
        )
        table.update_item.assert_called_once()
        sns.publish.assert_called_once()
        self.assertEqual(result["reminder_count"], 2)
        self.assertNotIn("taskToken", sns.publish.call_args.kwargs["Message"])

    @patch.dict(os.environ, {}, clear=True)
    def test_requires_reminder_topic(self):
        with self.assertRaisesRegex(RuntimeError, "REMINDER_TOPIC_ARN"):
            send_reminder(
                {
                    "employee_id": "employee-123",
                    "stage": "policy_signoff",
                },
                table=Mock(),
                sns=Mock(),
            )

    def test_lambda_dispatch_rejects_unknown_action(self):
        with self.assertRaisesRegex(ValueError, "Unsupported workflow action"):
            lambda_handler({"action": "unknown"}, None)


if __name__ == "__main__":
    unittest.main()
