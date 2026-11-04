import unittest
from unittest.mock import Mock, patch

from botocore.exceptions import ClientError

from completion import send_completion_notification


class CompletionNotificationTests(unittest.TestCase):
    def setUp(self):
        self.employee_id = "employee-test-123"
        self.employees = Mock()
        self.employees.get_item.return_value = {
            "Item": {
                "employee_id": self.employee_id,
                "full_name": "Asha Rao",
                "email": "asha@example.com",
            }
        }
        self.stages = Mock()
        self.stages.query.return_value = {
            "Items": [
                {"stage": "document_collection", "status": "complete"},
                {"stage": "it_provisioning", "status": "complete"},
                {"stage": "policy_signoff", "status": "complete"},
                {"stage": "manager_intro", "status": "complete"},
            ]
        }
        self.ses = Mock()
        self.ses.send_email.return_value = {"MessageId": "ses-message-123"}

    @patch.dict("os.environ", {"COMPLETION_EMAIL_SOURCE": "hr@example.com"}, clear=True)
    def test_sends_day_one_email_only_after_all_stages_complete(self):
        result = send_completion_notification(
            {"employee_id": self.employee_id},
            employees_table=self.employees,
            stages_table=self.stages,
            ses=self.ses,
            now="2026-11-04T10:00:00+00:00",
        )
        self.assertEqual(result["status"], "sent")
        self.ses.send_email.assert_called_once()
        args = self.ses.send_email.call_args.kwargs
        self.assertEqual(args["Destination"]["ToAddresses"], ["asha@example.com"])
        self.assertIn("Day 1", args["Message"]["Subject"]["Data"])
        self.assertIn("Asha Rao", args["Message"]["Body"]["Text"]["Data"])
        self.assertEqual(self.employees.update_item.call_count, 2)

    @patch.dict("os.environ", {"COMPLETION_EMAIL_SOURCE": "hr@example.com"}, clear=True)
    def test_refuses_to_send_when_any_required_stage_is_incomplete(self):
        self.stages.query.return_value = {
            "Items": [
                {"stage": "document_collection", "status": "complete"},
                {"stage": "it_provisioning", "status": "complete"},
                {"stage": "policy_signoff", "status": "in_progress"},
            ]
        }
        with self.assertRaisesRegex(ValueError, "manager_intro"):
            send_completion_notification(
                {"employee_id": self.employee_id},
                employees_table=self.employees,
                stages_table=self.stages,
                ses=self.ses,
            )
        self.ses.send_email.assert_not_called()
        self.employees.update_item.assert_not_called()

    @patch.dict("os.environ", {"COMPLETION_EMAIL_SOURCE": "hr@example.com"}, clear=True)
    def test_does_not_send_again_when_already_sent(self):
        conditional = ClientError(
            {"Error": {"Code": "ConditionalCheckFailedException", "Message": "claimed"}},
            "UpdateItem",
        )
        self.employees.update_item.side_effect = conditional
        self.employees.get_item.side_effect = [
            {"Item": {"employee_id": self.employee_id, "full_name": "Asha Rao", "email": "asha@example.com"}},
            {"Item": {"completion_email_status": "sent"}},
        ]
        result = send_completion_notification(
            {"employee_id": self.employee_id},
            employees_table=self.employees,
            stages_table=self.stages,
            ses=self.ses,
        )
        self.assertEqual(result["status"], "already_sent")
        self.ses.send_email.assert_not_called()

    @patch.dict("os.environ", {"COMPLETION_EMAIL_SOURCE": "hr@example.com"}, clear=True)
    def test_does_not_duplicate_concurrent_send(self):
        conditional = ClientError(
            {"Error": {"Code": "ConditionalCheckFailedException", "Message": "claimed"}},
            "UpdateItem",
        )
        self.employees.update_item.side_effect = conditional
        self.employees.get_item.side_effect = [
            {"Item": {"employee_id": self.employee_id, "full_name": "Asha Rao", "email": "asha@example.com"}},
            {"Item": {"completion_email_status": "sending"}},
        ]
        result = send_completion_notification(
            {"employee_id": self.employee_id},
            employees_table=self.employees,
            stages_table=self.stages,
            ses=self.ses,
        )
        self.assertEqual(result["status"], "send_in_progress")
        self.ses.send_email.assert_not_called()

    @patch.dict("os.environ", {"COMPLETION_EMAIL_SOURCE": "hr@example.com"}, clear=True)
    def test_requires_verified_sender_configuration(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "COMPLETION_EMAIL_SOURCE"):
                send_completion_notification(
                    {"employee_id": self.employee_id},
                    employees_table=self.employees,
                    stages_table=self.stages,
                    ses=self.ses,
                )
        self.ses.send_email.assert_not_called()


if __name__ == "__main__":
    unittest.main()
