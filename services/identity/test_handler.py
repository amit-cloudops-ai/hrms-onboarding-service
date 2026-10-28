"""Unit tests for WP1 identity payload validation."""
import unittest

from handler import InvalidEmployeeInput, validate_employee_payload


class ValidateEmployeePayloadTests(unittest.TestCase):
    def setUp(self):
        self.valid = {
            "full_name": "Asha Rao",
            "email": " ASHA.RAO@example.com ",
            "department": "Engineering",
            "role": "Software Engineer",
            "joining_date": "2026-11-16",
            "employment_type": "full_time",
            "manager_id": "manager-123",
        }

    def test_normalizes_email_and_trims_fields(self):
        result = validate_employee_payload(self.valid)
        self.assertEqual(result["email"], "asha.rao@example.com")
        self.assertEqual(result["full_name"], "Asha Rao")
        self.assertEqual(result["manager_id"], "manager-123")

    def test_rejects_non_object(self):
        with self.assertRaises(InvalidEmployeeInput):
            validate_employee_payload("not an object")

    def test_rejects_missing_required_field(self):
        payload = dict(self.valid)
        del payload["department"]
        with self.assertRaises(InvalidEmployeeInput):
            validate_employee_payload(payload)

    def test_rejects_invalid_email(self):
        payload = dict(self.valid, email="not-an-email")
        with self.assertRaises(InvalidEmployeeInput):
            validate_employee_payload(payload)


if __name__ == "__main__":
    unittest.main()
