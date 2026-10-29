"""WP1 identity service helpers for AWS Lambda.

Transport/API routing belongs to WP5. This module accepts a validated employee
payload, writes the canonical employee record, and creates the Cognito user.
"""
from __future__ import annotations

import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any

import boto3
from botocore.exceptions import ClientError


REQUIRED_FIELDS = (
    "full_name",
    "email",
    "department",
    "role",
    "joining_date",
    "employment_type",
)
OPTIONAL_FIELDS = ("manager_id",)

def _is_valid_email(email: str) -> bool:
    """Validate a conventional email address without fragile regex escaping."""
    if not email or len(email) > 254 or email.count("@") != 1:
        return False

    local, domain = email.rsplit("@", 1)

    if (
        not local
        or len(local) > 64
        or local.startswith(".")
        or local.endswith(".")
        or ".." in local
    ):
        return False

    allowed_local = set(
        "abcdefghijklmnopqrstuvwxyz"
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        "0123456789.!#$%&'*+/=?^_`{|}~-"
    )
    if any(char not in allowed_local for char in local):
        return False

    labels = domain.split(".")
    if len(labels) < 2:
        return False

    for label in labels:
        if (
            not label
            or len(label) > 63
            or label.startswith("-")
            or label.endswith("-")
        ):
            return False
        if any(
            not (char.isascii() and (char.isalnum() or char == "-"))
            for char in label
        ):
            return False

    return True


class IdentityError(Exception):
    """Base exception for expected identity-service errors."""


class InvalidEmployeeInput(IdentityError):
    """The employee payload is missing required fields or has invalid values."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_employee_payload(payload: Any) -> dict[str, str]:
    """Validate the fields defined by docs/data-model.md; return a normalized copy."""
    if not isinstance(payload, dict):
        raise InvalidEmployeeInput("Request body must be a JSON object.")

    missing = [
        field
        for field in REQUIRED_FIELDS
        if not isinstance(payload.get(field), str) or not payload[field].strip()
    ]
    if missing:
        raise InvalidEmployeeInput(
            f"Missing or empty required fields: {', '.join(missing)}"
        )

    email = payload["email"].strip().lower()
    if len(email) > 254 or not _is_valid_email(email):
        raise InvalidEmployeeInput("email must be a valid email address.")

    normalized = {
        field: payload[field].strip()
        for field in REQUIRED_FIELDS
    }
    normalized["email"] = email

    for field in OPTIONAL_FIELDS:
        value = payload.get(field)
        if value is not None and not isinstance(value, str):
            raise InvalidEmployeeInput(
                f"{field} must be a string when provided."
            )
        if isinstance(value, str) and value.strip():
            normalized[field] = value.strip()

    return normalized


def create_employee(
    payload: Any,
    *,
    table: Any | None = None,
    cognito: Any | None = None,
    user_pool_id: str | None = None,
    now: str | None = None,
    employee_id: str | None = None,
) -> dict[str, Any]:
    """Create a DynamoDB employee record and a Cognito user.

    AWS resources are injected for tests. In Lambda, configure EMPLOYEES_TABLE
    and COGNITO_USER_POOL_ID. Cognito must be configured to deliver its invite
    email; this function never returns temporary credentials.
    """
    employee = validate_employee_payload(payload)
    table_name = os.environ.get("EMPLOYEES_TABLE", "hrms-dev-employees")
    pool_id = user_pool_id or os.environ.get("COGNITO_USER_POOL_ID")

    if table is None:
        table = boto3.resource("dynamodb").Table(table_name)
    if cognito is None:
        cognito = boto3.client("cognito-idp")
    if not pool_id:
        raise IdentityError("COGNITO_USER_POOL_ID is not configured.")

    created_at = now or _utc_now()
    new_id = employee_id or str(uuid.uuid4())
    record = {
        "employee_id": new_id,
        **employee,
        "status": "in_progress",
        "created_at": created_at,
    }

    try:
        table.put_item(
            Item=record,
            ConditionExpression="attribute_not_exists(employee_id)",
        )
    except ClientError as exc:
        raise IdentityError("Could not create the employee record.") from exc

    try:
        cognito_result = cognito.admin_create_user(
            UserPoolId=pool_id,
            Username=employee["email"],
            DesiredDeliveryMediums=["EMAIL"],
            UserAttributes=[
                {"Name": "email", "Value": employee["email"]},
                {"Name": "name", "Value": employee["full_name"]},
                {"Name": "email_verified", "Value": "false"},
            ],
        )
    except ClientError as exc:
        # Avoid leaving a record that looks onboardable when identity creation failed.
        try:
            table.delete_item(
                Key={"employee_id": new_id},
                ConditionExpression="attribute_exists(employee_id)",
            )
        except ClientError:
            # Log a fixed message without exposing employee data or AWS error details.
            logging.getLogger(__name__).error(
                "Employee record cleanup failed after Cognito user creation failure."
            )
        raise IdentityError(
            "Could not create the employee's Cognito identity."
        ) from exc

    # Cognito's immutable sub claim is the authorization key for self-service.
    # Do not fall back to email: email can change and is not a stable subject ID.
    cognito_user = cognito_result.get("User", {}) if isinstance(cognito_result, dict) else {}
    attributes = cognito_user.get("Attributes", []) if isinstance(cognito_user, dict) else []
    cognito_sub = next(
        (
            attribute.get("Value")
            for attribute in attributes
            if isinstance(attribute, dict) and attribute.get("Name") == "sub"
        ),
        None,
    )
    if not isinstance(cognito_sub, str) or not cognito_sub.strip():
        try:
            cognito.admin_delete_user(UserPoolId=pool_id, Username=employee["email"])
        except ClientError:
            logging.getLogger(__name__).error(
                "Cognito cleanup failed after missing immutable subject."
            )
        try:
            table.delete_item(Key={"employee_id": new_id})
        except ClientError:
            logging.getLogger(__name__).error(
                "Employee cleanup failed after missing immutable subject."
            )
        raise IdentityError("Cognito did not return the immutable user subject.")

    try:
        table.update_item(
            Key={"employee_id": new_id},
            UpdateExpression="SET cognito_sub = :sub",
            ExpressionAttributeValues={":sub": cognito_sub},
            ConditionExpression="attribute_exists(employee_id)",
        )
    except ClientError as exc:
        try:
            cognito.admin_delete_user(UserPoolId=pool_id, Username=employee["email"])
        except ClientError:
            logging.getLogger(__name__).error(
                "Cognito cleanup failed after subject-link persistence failure."
            )
        try:
            table.delete_item(Key={"employee_id": new_id})
        except ClientError:
            logging.getLogger(__name__).error(
                "Employee cleanup failed after subject-link persistence failure."
            )
        raise IdentityError("Could not link the employee to the Cognito identity.") from exc

    # Return the canonical employee fields needed by the API response.
    # Never return the internal Cognito subject or temporary credentials.
    return {
        key: value
        for key, value in record.items()
        if key not in {"cognito_sub", "execution_arn"}
    }


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Optional Lambda entry point for direct invocation by WP5.

    WP5 remains responsible for API Gateway routing and authorizer/HR-role checks.
    """
    try:
        payload = event.get("employee") if isinstance(event, dict) else None

        if payload is None and isinstance(event, dict):
            payload = event.get("body")
            if isinstance(payload, str):
                payload = json.loads(payload)

        result = create_employee(payload)
        return {"ok": True, "employee": result}

    except (InvalidEmployeeInput, json.JSONDecodeError) as exc:
        return {
            "ok": False,
            "error": {
                "code": "INVALID_REQUEST",
                "message": str(exc),
            },
        }
    except IdentityError as exc:
        return {
            "ok": False,
            "error": {
                "code": "IDENTITY_CREATION_FAILED",
                "message": str(exc),
            },
        }
