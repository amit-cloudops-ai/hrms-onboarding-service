"""WP1 identity service helpers for AWS Lambda.

Transport/API routing belongs to WP5. This module accepts a validated employee
payload, writes the canonical employee record, and creates the Cognito user.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any

import boto3
from botocore.exceptions import ClientError


REQUIRED_FIELDS = ("full_name", "email", "department", "role", "joining_date", "employment_type")
OPTIONAL_FIELDS = ("manager_id",)


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

    missing = [field for field in REQUIRED_FIELDS if not isinstance(payload.get(field), str) or not payload[field].strip()]
    if missing:
        raise InvalidEmployeeInput(f"Missing or empty required fields: {', '.join(missing)}")

    email = payload["email"].strip().lower()
    if "@" not in email or email.startswith("@") or email.endswith("@"):
        raise InvalidEmployeeInput("email must be a valid email address.")

    normalized = {field: payload[field].strip() for field in REQUIRED_FIELDS}
    normalized["email"] = email
    for field in OPTIONAL_FIELDS:
        value = payload.get(field)
        if value is not None and not isinstance(value, str):
            raise InvalidEmployeeInput(f"{field} must be a string when provided.")
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
        cognito.admin_create_user(
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
            # Preserve the original Cognito failure; operational logs can identify
            # any cleanup issue without leaking credentials or personal data.
            pass
        raise IdentityError("Could not create the employee's Cognito identity.") from exc

    return {
        "employee_id": new_id,
        "email": employee["email"],
        "status": record["status"],
        "created_at": created_at,
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
        return {"ok": False, "error": {"code": "INVALID_REQUEST", "message": str(exc)}}
    except IdentityError as exc:
        return {"ok": False, "error": {"code": "IDENTITY_CREATION_FAILED", "message": str(exc)}}
