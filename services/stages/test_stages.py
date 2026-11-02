from datetime import datetime
import unittest
from unittest.mock import patch

from services.stages.stages import (
    STAGES,
    STATUSES,
    WP4_STAGES,
    build_stage_record,
    validate_employee_id,
    validate_stage,
    validate_status,
)
from services.stages.handler import process_stage


class TestStageDefinitions(unittest.TestCase):

    def test_all_stages_exist(self):
        self.assertEqual(len(STAGES), 4)

    def test_all_statuses_exist(self):
        self.assertEqual(
            STATUSES,
            ("pending", "in_progress", "complete")
        )

    def test_wp4_stage_subset_excludes_document_collection(self):
        self.assertEqual(
            WP4_STAGES,
            ("it_provisioning", "policy_signoff", "manager_intro"),
        )
        self.assertIn("document_collection", STAGES)
        self.assertNotIn("document_collection", WP4_STAGES)

    def test_build_stage_record(self):
        record = build_stage_record(
            "EMP001", "it_provisioning"
        )
        self.assertEqual(record["status"], "pending")

    def test_empty_employee_id(self):
        with self.assertRaises(ValueError):
            validate_employee_id("")

    def test_invalid_stage(self):
        with self.assertRaises(ValueError):
            validate_stage("unknown")

    def test_invalid_status(self):
        with self.assertRaises(ValueError):
            validate_status("unknown")


class TestStageHandler(unittest.TestCase):

    @patch("services.stages.handler.save_stage_record")
    def test_it_provisioning_persists_both_statuses(self, mock_save):
        result = process_stage({
            "employee_id": "EMP001",
            "stage": "it_provisioning",
        })

        self.assertEqual(mock_save.call_count, 2)
        in_progress = mock_save.call_args_list[0].args[0]
        completed = mock_save.call_args_list[1].args[0]
        self.assertEqual(in_progress["status"], "in_progress")
        self.assertIn("started_at", in_progress)
        self.assertNotIn("completed_at", in_progress)
        self.assertEqual(completed["status"], "complete")
        self.assertEqual(completed["started_at"], in_progress["started_at"])
        self.assertIn("completed_at", completed)
        self.assertNotIn("action_result", completed)
        self.assertEqual(result["status"], completed["status"])
        self.assertEqual(result["started_at"], completed["started_at"])
        self.assertEqual(result["completed_at"], completed["completed_at"])
        self.assertEqual(result["action_result"]["mode"], "simulated")

        for timestamp_field in ("started_at", "completed_at"):
            parsed = datetime.fromisoformat(result[timestamp_field])
            self.assertIsNotNone(parsed.tzinfo)
            self.assertEqual(parsed.utcoffset().total_seconds(), 0)

    @patch("services.stages.handler.execute_simulated_action")
    @patch("services.stages.handler.save_stage_record")
    def test_in_progress_is_saved_before_action_and_complete_after(
        self,
        mock_save,
        mock_action,
    ):
        calls = []
        mock_save.side_effect = lambda record: calls.append(
            ("save", record["status"])
        )
        mock_action.side_effect = lambda stage, event: (
            calls.append(("action", stage))
            or {"action": "simulated", "mode": "simulated", "success": True}
        )

        process_stage({
            "employee_id": "EMP001",
            "stage": "it_provisioning",
        })

        self.assertEqual(
            calls,
            [
                ("save", "in_progress"),
                ("action", "it_provisioning"),
                ("save", "complete"),
            ],
        )

    @patch("services.stages.handler.save_stage_record")
    def test_policy_signoff(self, mock_save):
        result = process_stage({
            "employee_id": "EMP001",
            "stage": "policy_signoff",
        })
        self.assertEqual(result["status"], "complete")
        self.assertEqual(mock_save.call_count, 2)

    @patch("services.stages.handler.save_stage_record")
    def test_manager_intro(self, mock_save):
        result = process_stage({
            "employee_id": "EMP001",
            "stage": "manager_intro",
        })
        self.assertEqual(result["status"], "complete")
        self.assertEqual(mock_save.call_count, 2)

    @patch("services.stages.handler.save_stage_record")
    def test_document_collection_rejected(self, mock_save):
        with self.assertRaises(ValueError):
            process_stage({
                "employee_id": "EMP001",
                "stage": "document_collection"
            })
        mock_save.assert_not_called()

    @patch("services.stages.handler.save_stage_record")
    @patch("services.stages.handler.execute_simulated_action")
    def test_simulated_action_failure_keeps_in_progress_record(
        self,
        mock_action,
        mock_save,
    ):
        mock_action.return_value = {
            "action": "simulated_it_provisioning",
            "mode": "simulated",
            "success": False,
        }

        with self.assertRaisesRegex(RuntimeError, "Stage action failed"):
            process_stage({
                "employee_id": "EMP001",
                "stage": "it_provisioning",
            })

        self.assertEqual(mock_save.call_count, 1)
        self.assertEqual(mock_save.call_args.args[0]["status"], "in_progress")

    @patch("services.stages.handler.save_stage_record")
    def test_non_dictionary_event_is_rejected(self, mock_save):
        with self.assertRaises(ValueError):
            process_stage(None)

        mock_save.assert_not_called()

    @patch("services.stages.handler.save_stage_record")
    def test_real_mode_remains_unimplemented_without_persistence(self, mock_save):
        with self.assertRaises(NotImplementedError):
            process_stage({
                "employee_id": "EMP001",
                "stage": "it_provisioning",
            }, mode="real")

        mock_save.assert_not_called()

    @patch("services.stages.handler.save_stage_record")
    def test_invalid_employee_id_is_rejected(self, mock_save):
        with self.assertRaises(ValueError):
            process_stage({
                "employee_id": "   ",
                "stage": "it_provisioning",
            })

        mock_save.assert_not_called()

    @patch("services.stages.handler.save_stage_record")
    def test_invalid_stage_is_rejected(self, mock_save):
        with self.assertRaises(ValueError):
            process_stage({
                "employee_id": "EMP001",
                "stage": "unknown",
            })

        mock_save.assert_not_called()


if __name__ == "__main__":
    unittest.main()