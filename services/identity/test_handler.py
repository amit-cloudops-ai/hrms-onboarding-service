"""Unit tests for WP1 identity validation and AWS interaction boundaries."""
import json
import unittest
from unittest.mock import Mock

from botocore.exceptions import ClientError

from handler import (
    IdentityError,
    InvalidEmployeeInput,
    create_employee,
    lambda_handler,
    validate_employee_payload,
)


def client_error(code="AccessDeniedException"):
    return ClientError({"Error": {"Code": code, "Message": "mocked failure"}}, "MockOperation")


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

    def test_omits_blank_optional_manager_id(self):
        result = validate_employee_payload(dict(self.valid, manager_id="  "))
        self.assertNotIn("manager_id", result)

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

    def test_rejects_malformed_email_addresses(self):
        for email in (
            "person@@example.com",
            "person@",
            "@example.com",
            "person@example",
            "person@-example.com",
            "person@example-.com",
        ):
            with self.subTest(email=email):
                with self.assertRaises(InvalidEmployeeInput):
                    validate_employee_payload(dict(self.valid, email=email))

    def test_rejects_non_string_optional_field(self):
        with self.assertRaises(InvalidEmployeeInput):
            validate_employee_payload(dict(self.valid, manager_id=123))


class CreateEmployeeTests(unittest.TestCase):
    def setUp(self):
        self.payload = {
            "full_name": "Asha Rao",
            "email": "asha.rao@example.com",
            "department": "Engineering",
            "role": "Software Engineer",
            "joining_date": "2026-11-16",
            "employment_type": "full_time",
        }
        self.table = Mock()
        self.cognito = Mock()
        self.cognito.admin_create_user.return_value = {
            "User": {
                "Attributes": [{"Name": "sub", "Value": "cognito-sub-123"}],
            }
        }

    def test_writes_employee_and_creates_cognito_user(self):
        result = create_employee(
            self.payload,
            table=self.table,
            cognito=self.cognito,
            user_pool_id="us-east-1_testpool",
            now="2026-10-28T10:00:00+00:00",
            employee_id="employee-test-123",
        )

        self.table.put_item.assert_called_once()
        item = self.table.put_item.call_args.kwargs["Item"]
        self.assertEqual(item["employee_id"], "employee-test-123")
        self.assertEqual(item["email"], "asha.rao@example.com")
        self.assertEqual(item["status"], "in_progress")
        self.cognito.admin_create_user.assert_called_once()
        self.table.update_item.assert_called_once()
        self.assertEqual(
            self.table.update_item.call_args.kwargs["ExpressionAttributeValues"][":sub"],
            "cognito-sub-123",
        )
        cognito_args = self.cognito.admin_create_user.call_args.kwargs
        self.assertEqual(cognito_args["Username"], "asha.rao@example.com")
        self.assertEqual(cognito_args["UserPoolId"], "us-east-1_testpool")
        self.assertEqual(result["employee_id"], "employee-test-123")
        self.assertNotIn("temporary_password", result)

    def test_does_not_create_cognito_user_if_dynamodb_write_fails(self):
        self.table.put_item.side_effect = client_error()
        with self.assertRaises(IdentityError):
            create_employee(
                self.payload, table=self.table, cognito=self.cognito,
                user_pool_id="us-east-1_testpool", employee_id="employee-test-123",
            )
        self.cognito.admin_create_user.assert_not_called()

    def test_removes_employee_record_if_cognito_creation_fails(self):
        self.cognito.admin_create_user.side_effect = client_error()
        with self.assertRaises(IdentityError):
            create_employee(
                self.payload, table=self.table, cognito=self.cognito,
                user_pool_id="us-east-1_testpool", employee_id="employee-test-123",
            )
        self.table.delete_item.assert_called_once_with(
            Key={"employee_id": "employee-test-123"},
            ConditionExpression="attribute_exists(employee_id)",
        )

    def test_logs_cleanup_failure_without_hiding_identity_error(self):
        self.cognito.admin_create_user.side_effect = client_error()
        self.table.delete_item.side_effect = client_error()

        with self.assertLogs("handler", level="ERROR") as captured:
            with self.assertRaisesRegex(
                IdentityError,
                "Could not create the employee's Cognito identity",
            ):
                create_employee(
                    self.payload,
                    table=self.table,
                    cognito=self.cognito,
                    user_pool_id="us-east-1_testpool",
                    employee_id="employee-test-123",
                )

        self.assertIn("cleanup failed", captured.output[0].lower())

    def test_returns_identity_error_when_pool_id_missing(self):
        with self.assertRaises(IdentityError):
            create_employee(self.payload, table=self.table, cognito=self.cognito, user_pool_id="")
        self.table.put_item.assert_not_called()
        self.cognito.admin_create_user.assert_not_called()


class LambdaHandlerTests(unittest.TestCase):
    def test_parses_api_gateway_json_body(self):
        # The AWS services are not invoked because this payload is invalid.
        response = lambda_handler({"body": json.dumps({"email": "bad"})}, None)
        self.assertFalse(response["ok"])
        self.assertEqual(response["error"]["code"], "INVALID_REQUEST")


if __name__ == "__main__":
    unittest.main()
