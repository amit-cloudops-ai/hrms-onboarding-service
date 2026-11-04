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


    @patch("reconciliation._all_stages_complete", return_value=[])
    @patch("reconciliation.send_completion_notification", return_value={
        "ok": False, "status": "failed", "error_code": "AccessDenied",
    })
    def test_reports_failed_email_delivery_instead_of_false_success(self, send, _stages):
        result = reconcile_completion_notifications(
            {"confirm_send": True, "page_size": 10},
            employees_table=self.employees,
            stages_table=self.stages,
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result["errors"], [
            {"employee_id": "emp-1", "error": "AccessDenied"},
            {"employee_id": "emp-3", "error": "AccessDenied"},
        ])
        self.assertEqual(send.call_count, 2)


    @patch("reconciliation._all_stages_complete", return_value=[])
    @patch("reconciliation.send_completion_notification", return_value={
        "ok": False, "status": "failed", "error_code": "AccessDenied",
    })
    def test_targeted_reconciliation_reads_only_requested_employee(self, send, _stages):
        self.employees.get_item.return_value = {
            "Item": {"employee_id": "emp-1", "email": "asha@example.com"}
        }
        result = reconcile_completion_notifications(
            {"employee_id": "emp-1"},
            employees_table=self.employees,
            stages_table=self.stages,
        )
        self.employees.get_item.assert_called_once_with(
            Key={"employee_id": "emp-1"},
            ConsistentRead=True,
        )
        self.employees.scan.assert_not_called()
        send.assert_not_called()
        self.assertEqual(result["scanned"], 1)
        self.assertEqual(result["eligible"], [
            {"employee_id": "emp-1", "email": "a***@example.com"}
        ])
        self.assertTrue(result["ok"])
        self.assertEqual(result["mode"], "preview")

    def test_targeted_reconciliation_rejects_scan_cursor(self):
        with self.assertRaisesRegex(ValueError, "cannot be combined"):
            reconcile_completion_notifications(
                {"employee_id": "emp-1", "exclusive_start_key": {"employee_id": "emp-0"}},
                employees_table=self.employees,
                stages_table=self.stages,
            )


    @patch("reconciliation._all_stages_complete", return_value=[])
    @patch("reconciliation.send_completion_notification", return_value={
        "ok": False, "status": "failed", "error_code": "AccessDenied",
    })
    def test_targeted_send_attempts_only_the_requested_employee(self, send, _stages):
        self.employees.get_item.return_value = {
            "Item": {"employee_id": "emp-1", "email": "asha@example.com"}
        }
        result = reconcile_completion_notifications(
            {"employee_id": "emp-1", "confirm_send": True},
            employees_table=self.employees,
            stages_table=self.stages,
        )
        self.employees.scan.assert_not_called()
        send.assert_called_once()
        self.assertEqual(send.call_args.args[0], {"employee_id": "emp-1"})
        self.assertFalse(result["ok"])
        self.assertEqual(result["errors"], [
            {"employee_id": "emp-1", "error": "AccessDenied"}
        ])


if __name__ == "__main__":
    unittest.main()
