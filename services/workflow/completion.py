"""Idempotent employee Day 1 completion email for WP2.

Employee lifecycle completion is independent of notification delivery. A failed
email must never leave an employee's onboarding status stuck in in_progress.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger(__name__)

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


def _mark_employee_complete(employees_table: Any, employee_id: str, timestamp: str) -> None:
    """Persist lifecycle completion before attempting any external notification."""
    try:
        employees_table.update_item(
            Key={"employee_id": employee_id},
            UpdateExpression=(
                "SET #employee_status=:complete, "
                "onboarding_completed_at=if_not_exists(onboarding_completed_at,:now)"
            ),
            ConditionExpression=(
                "#employee_status=:in_progress OR #employee_status=:complete"
            ),
            ExpressionAttributeNames={"#employee_status": "status"},
            ExpressionAttributeValues={
                ":complete": "complete",
                ":in_progress": "in_progress",
                ":now": timestamp,
            },
        )
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
            raise
        current = employees_table.get_item(
            Key={"employee_id": employee_id},
            ConsistentRead=True,
        ).get("Item", {})
        if current.get("status") != "complete":
            raise ValueError(
                "Employee lifecycle status is not eligible for onboarding completion"
            ) from exc


def send_completion_notification(
    event: dict[str, Any],
    *,
    employees_table: Any | None = None,
    stages_table: Any | None = None,
    ses: Any | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    """Complete the employee lifecycle and attempt one idempotent Day 1 email.

    The lifecycle status is committed independently of SES. A conditional
    DynamoDB claim prevents concurrent sends. Definitive SES errors are stored
    as failed and can be retried; ambiguous transport outcomes remain sending
    so an operator can reconcile delivery without risking a duplicate email.
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
            "Cannot complete onboarding; required stages are not complete: "
            + ", ".join(missing_stages)
        )

    timestamp = now or _now()
    _mark_employee_complete(employees, employee_id, timestamp)

    notification_status = employee.get("completion_email_status")
    if notification_status == "sent":
        return {"ok": True, "employee_id": employee_id, "status": "already_sent"}
    if notification_status == "sending":
        return {
            "ok": False,
            "employee_id": employee_id,
            "status": "sending",
            "reason": "delivery_outcome_unknown",
        }

    recipient = employee.get("email")
    if not isinstance(recipient, str) or recipient.count("@") != 1:
        raise ValueError("Employee record does not contain a valid email address")

    source = os.environ.get("COMPLETION_EMAIL_SOURCE", "").strip()
    if not source or source.count("@") != 1:
        raise RuntimeError("COMPLETION_EMAIL_SOURCE must be a verified SES sender address")

    try:
        employees.update_item(
            Key={"employee_id": employee_id},
            UpdateExpression=(
                "SET completion_email_status=:sending, "
                "completion_email_started_at=:now"
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
            return {
                "ok": False,
                "employee_id": employee_id,
                "status": "sending",
                "reason": "delivery_outcome_unknown",
            }
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
        code = exc.response.get("Error", {}).get("Code", "SES_SEND_FAILED")
        try:
            employees.update_item(
                Key={"employee_id": employee_id},
                UpdateExpression=(
                    "SET completion_email_status=:failed, completion_email_error=:error"
                ),
                ConditionExpression="completion_email_status=:sending",
                ExpressionAttributeValues={
                    ":failed": "failed",
                    ":sending": "sending",
                    ":error": str(code)[:80],
                },
            )
        except ClientError as persist_error:
            persist_code = persist_error.response.get("Error", {}).get("Code", "UNKNOWN")
            logger.error(
                "Could not persist SES failure state for employee %s (%s)",
                employee_id,
                persist_code,
            )
            return {
                "ok": False,
                "employee_id": employee_id,
                "status": "sending",
                "reason": "notification_state_update_failed",
            }
        logger.warning("SES rejected completion notification (%s)", code)
        return {
            "ok": False,
            "employee_id": employee_id,
            "status": "failed",
            "error_code": str(code)[:80],
        }
    except BotoCoreError as exc:
        # A transport timeout can happen after SES accepted the message. Do not
        # retry automatically because delivery may already have occurred.
        logger.error(
            "SES completion delivery outcome is unknown for employee %s (%s)",
            employee_id,
            type(exc).__name__,
        )
        return {
            "ok": False,
            "employee_id": employee_id,
            "status": "sending",
            "reason": "delivery_outcome_unknown",
        }

    try:
        employees.update_item(
            Key={"employee_id": employee_id},
            UpdateExpression=(
                "SET completion_email_status=:sent, "
                "completion_email_sent_at=:now, "
                "completion_email_message_id=:message_id"
            ),
            ConditionExpression="completion_email_status=:sending",
            ExpressionAttributeValues={
                ":sent": "sent",
                ":sending": "sending",
                ":now": timestamp,
                ":message_id": response.get("MessageId", "accepted"),
            },
        )
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "UNKNOWN")
        logger.error(
            "SES accepted completion notification but state persistence failed for employee %s (%s)",
            employee_id,
            code,
        )
        return {
            "ok": False,
            "employee_id": employee_id,
            "status": "sending",
            "reason": "notification_state_update_failed",
        }

    return {"ok": True, "employee_id": employee_id, "status": "sent"}
