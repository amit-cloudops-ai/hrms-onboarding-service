"""Idempotent employee Day 1 completion email for WP2."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

REQUIRED_STAGES = (
    "document_collection",
    "it_provisioning",
    "policy_signoff",
    "manager_intro",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _required_employee_id(event: dict[str, Any]) -> str:
    value = event.get("employee_id")
    if not isinstance(value, str) or not value.strip():
        raise ValueError("employee_id must be a non-empty string")
    return value.strip()


def _table(table: Any | None, env_name: str, default_name: str) -> Any:
    if table is not None:
        return table
    return boto3.resource("dynamodb").Table(os.environ.get(env_name, default_name))


def _all_stages_complete(stages_table: Any, employee_id: str) -> list[str]:
    response = stages_table.query(
        KeyConditionExpression=Key("employee_id").eq(employee_id),
        ConsistentRead=True,
    )
    items = list(response.get("Items", []))
    while response.get("LastEvaluatedKey"):
        response = stages_table.query(
            KeyConditionExpression=Key("employee_id").eq(employee_id),
            ConsistentRead=True,
            ExclusiveStartKey=response["LastEvaluatedKey"],
        )
        items.extend(response.get("Items", []))

    statuses = {item.get("stage"): item.get("status") for item in items}
    return [stage for stage in REQUIRED_STAGES if statuses.get(stage) != "complete"]


def send_completion_notification(
    event: dict[str, Any],
    *,
    employees_table: Any | None = None,
    stages_table: Any | None = None,
    ses: Any | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    """Send one Day 1 email, only after every required stage is persisted complete.

    A DynamoDB claim prevents concurrent/retried executions from sending twice.
    A claim left in 'sending' after an ambiguous network failure is deliberately
    not auto-retried: an operator must reconcile SES before clearing it.
    """
    employee_id = _required_employee_id(event)
    employees = _table(employees_table, "EMPLOYEES_TABLE", "hrms-dev-employees")
    stages = _table(stages_table, "STAGES_TABLE", "hrms-dev-onboarding-stages")

    employee_response = employees.get_item(
        Key={"employee_id": employee_id},
        ConsistentRead=True,
    )
    employee = employee_response.get("Item")
    if not isinstance(employee, dict):
        raise ValueError("Employee record was not found")

    missing_stages = _all_stages_complete(stages, employee_id)
    if missing_stages:
        raise ValueError(
            "Cannot send completion email; onboarding stages are not complete: "
            + ", ".join(missing_stages)
        )

    recipient = employee.get("email")
    if not isinstance(recipient, str) or recipient.count("@") != 1:
        raise ValueError("Employee record does not contain a valid email address")

    source = os.environ.get("COMPLETION_EMAIL_SOURCE", "").strip()
    if not source or source.count("@") != 1:
        raise RuntimeError("COMPLETION_EMAIL_SOURCE must be a verified SES sender address")

    timestamp = now or _now()
    try:
        employees.update_item(
            Key={"employee_id": employee_id},
            UpdateExpression=(
                "SET completion_email_status=:sending, completion_email_started_at=:now"
            ),
            ConditionExpression=(
                "attribute_not_exists(completion_email_status) "
                "OR completion_email_status=:failed"
            ),
            ExpressionAttributeValues={
                ":sending": "sending",
                ":failed": "failed",
                ":now": timestamp,
            },
        )
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
            raise
        current = employees.get_item(
            Key={"employee_id": employee_id},
            ConsistentRead=True,
        ).get("Item", {})
        status = current.get("completion_email_status")
        if status == "sent":
            return {"ok": True, "employee_id": employee_id, "status": "already_sent"}
        if status == "sending":
            raise RuntimeError(
                "Completion email is already claimed; reconcile SES delivery before retrying"
            )
        raise

    client = ses or boto3.client("ses")
    name = employee.get("full_name") or "there"
    subject = "Your onboarding is complete — get ready for Day 1!"
    body = (
        f"Hi {name},\n\n"
        "Congratulations! You have completed all the required onboarding steps. "
        "Your documents have been verified, your policy acknowledgement is recorded, "
        "and your onboarding process is complete.\n\n"
        "You're all set for your first day! We look forward to welcoming you.\n\n"
        "Regards,\nHuman Resources Team"
    )

    try:
        response = client.send_email(
            Source=source,
            Destination={"ToAddresses": [recipient]},
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {"Text": {"Data": body, "Charset": "UTF-8"}},
            },
        )
    except ClientError as exc:
        # SES returned a definitive service error, so a controlled retry is safe.
        code = exc.response.get("Error", {}).get("Code", "SES_SEND_FAILED")
        employees.update_item(
            Key={"employee_id": employee_id},
            UpdateExpression="SET completion_email_status=:failed, completion_email_error=:error",
            ConditionExpression="completion_email_status=:sending",
            ExpressionAttributeValues={
                ":failed": "failed",
                ":sending": "sending",
                ":error": str(code)[:80],
            },
        )
        raise

    employees.update_item(
        Key={"employee_id": employee_id},
        UpdateExpression=(
            "SET completion_email_status=:sent, completion_email_sent_at=:now, "
            "completion_email_message_id=:message_id, #employee_status=:complete"
        ),
        ConditionExpression="completion_email_status=:sending",
        ExpressionAttributeNames={"#employee_status": "status"},
        ExpressionAttributeValues={
            ":sent": "sent",
            ":complete": "complete",
            ":sending": "sending",
            ":now": timestamp,
            ":message_id": response.get("MessageId", "accepted"),
        },
    )
    return {"ok": True, "employee_id": employee_id, "status": "sent"}
