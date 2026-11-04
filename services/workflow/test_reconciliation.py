import unittest
from unittest.mock import Mock, patch

from reconciliation import reconcile_completion_notifications


class CompletionReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.employees = Mock()
        self.stages = Mock()
        self.employees.scan.return_value = {
            "Items": [
                {"employee_id": "emp-1", "email": "asha@example.com"},
                {"employee_id": "emp-2", "email": "b***@example.com", "completion_email_status": "sent"},
                {"employee_id": "emp-3", "email": "ravi@example.com"},
                {"employee_id": "emp-4", "email": "no-at-symbol"},
            ],
            "LastEvaluatedKey": {"employee_id": "emp-4"},
        }

    @patch("reconciliation._all_stages_complete", side_effect=[[], ["policy_signoff"]])
    def test_defaults_to_preview_and_masks_addresses(self, _stages):
        result = reconcile_completion_notifications({}, employees_table=self.employees, stages_table=self.stages)
        self.assertEqual(result["mode"], "preview")
        self.assertEqual(result["eligible"], [{"employee_id": "emp-1", "email": "a***@example.com"}])
        self.assertTrue(result["has_more"])
        self.assertEqual(result["skipped"]["already_sent"], 1)
        self.assertEqual(result["skipped"]["incomplete"], 1)
        self.assertEqual(result["skipped"]["invalid_email"], 1)

    @patch("reconciliation._all_stages_complete", return_value=[])
    @patch("reconciliation.send_completion_notification", return_value={"status": "sent"})
    def test_sends_only_after_explicit_confirmation(self, send, _stages):
        result = reconcile_completion_notifications({"confirm_send": True, "page_size": 10}, employees_table=self.employees, stages_table=self.stages)
        self.assertEqual(result["mode"], "send")
        self.assertEqual(result["sent_employee_ids"], ["emp-1", "emp-3"])
        self.assertEqual(send.call_count, 2)

    def test_rejects_invalid_page_size(self):
        with self.assertRaisesRegex(ValueError, "page_size"):
            reconcile_completion_notifications({"page_size": 1000}, employees_table=self.employees, stages_table=self.stages)

    def test_rejects_non_boolean_confirmation(self):
        with self.assertRaisesRegex(ValueError, "confirm_send"):
            reconcile_completion_notifications({"confirm_send": "yes"}, employees_table=self.employees, stages_table=self.stages)


if __name__ == "__main__":
    unittest.main()
