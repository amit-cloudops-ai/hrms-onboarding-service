import unittest
from botocore.exceptions import ClientError
from unittest.mock import Mock

from services.stages.repository import save_stage_record


class TestStageRepository(unittest.TestCase):

    def test_save_stage_record(self):
        mock_table = Mock()

        record = {
            "employee_id": "EMP001",
            "stage": "it_provisioning",
            "status": "complete",
            "reminder_count": 0,
            "started_at": "2026-11-02T12:00:00+00:00",
            "completed_at": "2026-11-02T12:01:00+00:00",
        }

        result = save_stage_record(record, table=mock_table)

        mock_table.put_item.assert_called_once()
        put_args = mock_table.put_item.call_args.kwargs
        self.assertEqual(put_args["Item"], record)
        self.assertIn("#status <> :complete", put_args["ConditionExpression"])
        self.assertEqual(result, record)

    def test_incomplete_record_rejected(self):
        mock_table = Mock()

        with self.assertRaises(ValueError):
            save_stage_record(
                {"employee_id": "EMP001"},
                table=mock_table,
            )

        mock_table.put_item.assert_not_called()

    def test_invalid_record_values_are_rejected_before_table_lookup(self):
        invalid_records = (
            None,
            {"employee_id": " ", "stage": "it_provisioning", "status": "pending"},
            {"employee_id": "EMP001", "stage": "document_collection", "status": "pending"},
            {"employee_id": "EMP001", "stage": "it_provisioning", "status": "unknown"},
        )

        with unittest.mock.patch(
            "services.stages.repository.get_stages_table"
        ) as mock_get_table:
            for record in invalid_records:
                with self.subTest(record=record):
                    with self.assertRaises(ValueError):
                        save_stage_record(record)

        mock_get_table.assert_not_called()

    def test_completed_stage_write_is_rejected_by_condition(self):
        mock_table = Mock()
        mock_table.put_item.side_effect = ClientError(
            {"Error": {"Code": "ConditionalCheckFailedException"}},
            "PutItem",
        )
        record = {
            "employee_id": "EMP001",
            "stage": "it_provisioning",
            "status": "complete",
        }

        with self.assertRaises(ClientError):
            save_stage_record(record, table=mock_table)

        self.assertIn(
            "#status <> :complete",
            mock_table.put_item.call_args.kwargs["ConditionExpression"],
        )


if __name__ == "__main__":
    unittest.main()