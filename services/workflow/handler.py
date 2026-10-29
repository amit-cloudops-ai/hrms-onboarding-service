"""WP2 workflow support: stage tracking and reminder dispatch."""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

import boto3

VALID_STAGES = (
    "document_collection",
    "it_provisioning",
    "policy_signoff",
    "manager_intro",
)

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _required_string(event: dict[str, Any], field: str) -> str:
    value = event.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _validate_stage(event: dict[str, Any]) -> str:
    stage = _required_string(event, "stage")
    if stage not in VALID_STAGES:
        raise ValueError(f"Unsupported stage: {stage}")
    return stage


def _stages_table(table: Any | None = None) -> Any:
    if table is not None:
        return table
    name = os.environ.get("STAGES_TABLE", "hrms-dev-onboarding-stages")
    return boto3.resource("dynamodb").Table(name)


def start_stage(
    event: dict[str, Any],
    *,
    table: Any | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    """Record a callback task. Never return or log its task token."""
    employee_id = _required_string(event, "employee_id")
    stage = _validate_stage(event)
    task_token = _required_string(event, "taskToken")

    _stages_table(table).update_item(
        Key={"employee_id": employee_id, "stage": stage},
        UpdateExpression=(
            "SET #status = :status, "
            "started_at = if_not_exists(started_at, :now), "
            "task_token = :token, "
            "reminder_count = if_not_exists(reminder_count, :zero)"
        ),
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={
            ":status": "in_progress",
            ":now": now or _now(),
            ":token": task_token,
            ":zero": 0,
        },
    )

    return {
        "ok": True,
        "employee_id": employee_id,
        "stage": stage,
        "status": "in_progress",
    }


def mark_stage_complete(
    event: dict[str, Any],
    *,
    table: Any | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    """Mark a stage complete after Step Functions accepts its callback."""
    employee_id = _required_string(event, "employee_id")
    stage = _validate_stage(event)

    _stages_table(table).update_item(
        Key={"employee_id": employee_id, "stage": stage},
        UpdateExpression=(
            "SET #status = :complete, completed_at = :now "
            "REMOVE task_token"
        ),
        ConditionExpression="#status = :in_progress",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={
            ":complete": "complete",
            ":in_progress": "in_progress",
            ":now": now or _now(),
        },
    )

    return {
        "ok": True,
        "employee_id": employee_id,
        "stage": stage,
        "status": "complete",
    }


def send_reminder(
    event: dict[str, Any],
    *,
    table: Any | None = None,
    sns: Any | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    """Publish a stage reminder after a callback task times out."""
    employee_id = _required_string(event, "employee_id")
    stage = _validate_stage(event)
    topic_arn = os.environ.get("REMINDER_TOPIC_ARN")
    if not topic_arn:
        raise RuntimeError("REMINDER_TOPIC_ARN is not configured")

    response = _stages_table(table).update_item(
        Key={"employee_id": employee_id, "stage": stage},
        UpdateExpression="ADD reminder_count :one",
        ExpressionAttributeValues={":one": 1},
        ReturnValues="UPDATED_NEW",
    )
    attributes = response.get("Attributes", {})
    reminder_count = int(attributes.get("reminder_count", 1))

    if sns is None:
        sns = boto3.client("sns")

    # Do not include task tokens or sensitive employee data in notifications.
    sns.publish(
        TopicArn=topic_arn,
        Subject="HRMS onboarding reminder",
        Message=json.dumps({
            "employee_id": employee_id,
            "stage": stage,
            "reminder_count": reminder_count,
            "reminder_time": now or _now(),
        }),
    )

    logger.info(
        "Published onboarding reminder for stage %s (reminder count %s)",
        stage,
        reminder_count,
    )
    return {
        "ok": True,
        "employee_id": employee_id,
        "stage": stage,
        "reminder_count": reminder_count,
    }


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Dispatcher invoked by the Step Functions state machine."""
    if not isinstance(event, dict):
        raise ValueError("Event must be a JSON object")

    action = event.get("action")
    if action == "start_stage":
        return start_stage(event)
    if action == "mark_stage_complete":
        return mark_stage_complete(event)
    if action == "send_reminder":
        return send_reminder(event)

    raise ValueError("Unsupported workflow action")
