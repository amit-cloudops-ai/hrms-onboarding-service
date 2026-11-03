"""WP2 orchestration support for callback and synchronous business stages."""
from __future__ import annotations
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any
import boto3
from botocore.exceptions import ClientError

VALID_STAGES = ("document_collection", "it_provisioning", "policy_signoff", "manager_intro")
WP4_STAGES = ("it_provisioning", "policy_signoff", "manager_intro")
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
    return boto3.resource("dynamodb").Table(os.environ.get("STAGES_TABLE", "hrms-dev-onboarding-stages"))

def _conditional_failure(exc: ClientError) -> bool:
    return exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException"

def start_stage(event: dict[str, Any], *, table: Any | None = None, now: str | None = None) -> dict[str, Any]:
    """Start document collection and persist its callback token privately."""
    employee_id = _required_string(event, "employee_id")
    stage = _validate_stage(event)
    if stage != "document_collection":
        raise ValueError("Callback tokens are reserved for document_collection")
    task_token = _required_string(event, "taskToken")
    target = _stages_table(table)
    try:
        target.update_item(
            Key={"employee_id": employee_id, "stage": stage},
            UpdateExpression="SET #status = :in_progress, started_at = if_not_exists(started_at, :now), task_token = :token, reminder_count = if_not_exists(reminder_count, :zero)",
            ConditionExpression="attribute_not_exists(#status) OR #status = :pending OR (#status = :in_progress AND task_token = :token)",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={":in_progress": "in_progress", ":pending": "pending", ":now": now or _now(), ":token": task_token, ":zero": 0},
        )
    except ClientError as exc:
        if not _conditional_failure(exc):
            raise
        current = target.get_item(Key={"employee_id": employee_id, "stage": stage}, ConsistentRead=True).get("Item", {})
        if current.get("status") == "in_progress" and current.get("task_token") == task_token:
            return {"ok": True, "employee_id": employee_id, "stage": stage, "status": "in_progress"}
        raise
    return {"ok": True, "employee_id": employee_id, "stage": stage, "status": "in_progress"}

def start_business_stage(event: dict[str, Any], *, table: Any | None = None, now: str | None = None) -> dict[str, Any]:
    """Mark a WP4 stage in progress without creating a callback token."""
    employee_id = _required_string(event, "employee_id")
    stage = _validate_stage(event)
    if stage not in WP4_STAGES:
        raise ValueError("This stage is not a WP4 business stage")
    correlation_id = _required_string(event, "correlation_id")
    target = _stages_table(table)
    try:
        target.update_item(
            Key={"employee_id": employee_id, "stage": stage},
            UpdateExpression="SET #status = :in_progress, started_at = if_not_exists(started_at, :now), correlation_id = :correlation_id",
            ConditionExpression="attribute_not_exists(#status) OR #status = :pending OR (#status = :in_progress AND correlation_id = :correlation_id)",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={":in_progress": "in_progress", ":pending": "pending", ":now": now or _now(), ":correlation_id": correlation_id},
        )
    except ClientError as exc:
        if not _conditional_failure(exc):
            raise
        current = target.get_item(Key={"employee_id": employee_id, "stage": stage}, ConsistentRead=True).get("Item", {})
        if current.get("status") == "in_progress" and current.get("correlation_id") == correlation_id:
            return {"ok": True, "employee_id": employee_id, "stage": stage, "status": "in_progress", "correlation_id": correlation_id}
        raise
    return {"ok": True, "employee_id": employee_id, "stage": stage, "status": "in_progress", "correlation_id": correlation_id}

def execute_business_stage(event: dict[str, Any], *, lambda_client: Any | None = None) -> dict[str, Any]:
    """Invoke WP4 synchronously; task tokens and lifecycle writes stay in WP2."""
    employee_id = _required_string(event, "employee_id")
    stage = _validate_stage(event)
    if stage not in WP4_STAGES:
        raise ValueError("This stage is not a WP4 business stage")
    correlation_id = _required_string(event, "correlation_id")
    mode = os.environ.get("MODE", "").strip()
    if mode not in {"simulated", "real"}:
        raise RuntimeError("MODE must be explicitly configured as simulated or real")
    function_name = os.environ.get("STAGES_FUNCTION_NAME", "").strip()
    if not function_name:
        raise RuntimeError("STAGES_FUNCTION_NAME is not configured")
    if lambda_client is None:
        lambda_client = boto3.client("lambda")
    payload = {"action": "execute_stage", "employee_id": employee_id, "stage": stage, "mode": mode, "correlation_id": correlation_id}
    invocation = lambda_client.invoke(FunctionName=function_name, InvocationType="RequestResponse", Payload=json.dumps(payload).encode("utf-8"))
    if invocation.get("FunctionError"):
        logger.error("WP4 invocation returned a Lambda function error.")
        raise RuntimeError("WP4 business-stage execution failed")
    stream = invocation.get("Payload")
    raw = stream.read() if hasattr(stream, "read") else stream
    try:
        result = json.loads(raw or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError, TypeError) as exc:
        raise RuntimeError("WP4 returned an invalid JSON response") from exc
    if not isinstance(result, dict) or result.get("ok") is not True or result.get("employee_id") != employee_id or result.get("stage") != stage or result.get("status") != "complete" or result.get("mode") != mode:
        logger.error("WP4 returned an unsuccessful or mismatched business result.")
        raise RuntimeError("WP4 did not confirm successful business-stage execution")
    return result

def mark_stage_complete(event: dict[str, Any], *, table: Any | None = None, now: str | None = None) -> dict[str, Any]:
    """Persist canonical completion after callback acceptance or WP4 success."""
    employee_id = _required_string(event, "employee_id")
    stage = _validate_stage(event)
    correlation_id = event.get("correlation_id")
    target = _stages_table(table)
    if correlation_id is not None:
        if not isinstance(correlation_id, str) or not correlation_id.strip():
            raise ValueError("correlation_id must be a non-empty string")
        condition = "#status = :in_progress AND correlation_id = :correlation_id"
        values = {":complete": "complete", ":in_progress": "in_progress", ":now": now or _now(), ":correlation_id": correlation_id.strip()}
    else:
        if stage != "document_collection":
            raise ValueError("Business-stage completion requires correlation_id")
        condition = "#status = :in_progress AND attribute_exists(task_token)"
        values = {":complete": "complete", ":in_progress": "in_progress", ":now": now or _now()}
    try:
        target.update_item(
            Key={"employee_id": employee_id, "stage": stage},
            UpdateExpression="SET #status = :complete, completed_at = :now REMOVE task_token",
            ConditionExpression=condition,
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues=values,
        )
    except ClientError as exc:
        if not _conditional_failure(exc):
            raise
        current = target.get_item(Key={"employee_id": employee_id, "stage": stage}, ConsistentRead=True).get("Item", {})
        same_execution = correlation_id is None or current.get("correlation_id") == correlation_id
        if current.get("status") == "complete" and same_execution and not current.get("task_token"):
            return {"ok": True, "employee_id": employee_id, "stage": stage, "status": "complete"}
        raise
    return {"ok": True, "employee_id": employee_id, "stage": stage, "status": "complete"}

def mark_stage_failed(event: dict[str, Any], *, table: Any | None = None, now: str | None = None) -> dict[str, Any]:
    """Record a failed WP4 attempt without exposing provider details."""
    employee_id = _required_string(event, "employee_id")
    stage = _validate_stage(event)
    if stage not in WP4_STAGES:
        raise ValueError("Only WP4 business stages can be marked failed")
    correlation_id = _required_string(event, "correlation_id")
    error_code = event.get("error_code", "BUSINESS_STAGE_FAILED")
    if not isinstance(error_code, str) or not error_code.strip():
        error_code = "BUSINESS_STAGE_FAILED"
    _stages_table(table).update_item(
        Key={"employee_id": employee_id, "stage": stage},
        UpdateExpression="SET #status = :failed, failed_at = :now, failure_code = :failure_code REMOVE task_token",
        ConditionExpression="#status = :in_progress AND correlation_id = :correlation_id",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={":failed": "failed", ":in_progress": "in_progress", ":now": now or _now(), ":failure_code": error_code[:80], ":correlation_id": correlation_id},
    )
    return {"ok": True, "employee_id": employee_id, "stage": stage, "status": "failed"}

def send_reminder(event: dict[str, Any], *, table: Any | None = None, sns: Any | None = None, now: str | None = None) -> dict[str, Any]:
    """Publish a reminder for the document-collection callback."""
    employee_id = _required_string(event, "employee_id")
    stage = _validate_stage(event)
    if stage != "document_collection":
        raise ValueError("Reminders are currently supported for document_collection only")
    topic_arn = os.environ.get("REMINDER_TOPIC_ARN", "").strip()
    if not topic_arn:
        raise RuntimeError("REMINDER_TOPIC_ARN is not configured")
    response = _stages_table(table).update_item(
        Key={"employee_id": employee_id, "stage": stage},
        UpdateExpression="ADD reminder_count :one",
        ExpressionAttributeValues={":one": 1},
        ReturnValues="UPDATED_NEW",
    )
    reminder_count = int(response.get("Attributes", {}).get("reminder_count", 1))
    if sns is None:
        sns = boto3.client("sns")
    sns.publish(TopicArn=topic_arn, Subject="HRMS onboarding reminder", Message=json.dumps({
        "employee_id": employee_id, "stage": stage, "reminder_count": reminder_count, "reminder_time": now or _now(),
    }))
    return {"ok": True, "employee_id": employee_id, "stage": stage, "reminder_count": reminder_count}

def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    if not isinstance(event, dict):
        raise ValueError("Event must be a JSON object")
    action = event.get("action")
    if action == "start_stage":
        return start_stage(event)
    if action == "start_business_stage":
        return start_business_stage(event)
    if action == "execute_business_stage":
        return execute_business_stage(event)
    if action == "mark_stage_complete":
        return mark_stage_complete(event)
    if action == "mark_stage_failed":
        return mark_stage_failed(event)
    if action == "send_reminder":
        return send_reminder(event)
    raise ValueError("Unsupported workflow action")
