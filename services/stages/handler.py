"""WP4 onboarding stage handlers: IT provisioning, policy sign-off and manager intro.

The API invokes this Lambda only through its IAM-authorized adapter role. Human
stages use the Step Functions task token stored by WP2; tokens are never logged
or returned to API clients.
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any

import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key

logger = logging.getLogger(__name__)
VALID_STAGES = ("document_collection", "it_provisioning", "policy_signoff", "manager_intro")
POLICY_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{1,63}$")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _table(env: str, default: str, table: Any | None = None) -> Any:
    if table is not None:
        return table
    name = os.environ.get(env, default).strip()
    if not name:
        raise RuntimeError(f"{env} is not configured")
    return boto3.resource("dynamodb").Table(name)


def _required(event: dict[str, Any], name: str) -> str:
    value = event.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()


def _employee(employee_id: str, table: Any | None = None) -> dict[str, Any] | None:
    result = _table("EMPLOYEES_TABLE", "hrms-dev-employees", table).get_item(
        Key={"employee_id": employee_id}, ConsistentRead=True
    )
    item = result.get("Item")
    return item if isinstance(item, dict) else None


def _caller_authorized(employee: dict[str, Any] | None, caller: Any) -> bool:
    if employee is None or not isinstance(caller, dict):
        return False
    if caller.get("is_admin") is True:
        return True
    sub = caller.get("sub")
    return isinstance(sub, str) and bool(sub) and sub == employee.get("cognito_sub")


def _stage_record(employee_id: str, stage: str, table: Any | None = None) -> dict[str, Any] | None:
    item = _table("STAGES_TABLE", "hrms-dev-onboarding-stages", table).get_item(
        Key={"employee_id": employee_id, "stage": stage}, ConsistentRead=True
    ).get("Item")
    return item if isinstance(item, dict) else None


def _send_task_success(task_token: str, output: dict[str, Any], *, sfn: Any | None = None) -> None:
    if not task_token:
        raise ValueError("No active task token exists for this stage")
    client = sfn if sfn is not None else boto3.client("stepfunctions")
    client.send_task_success(taskToken=task_token, output=json.dumps(output, separators=(",", ":")))


def _complete(employee_id: str, stage: str, *, table: Any | None = None, sfn: Any | None = None,
              source: str) -> dict[str, Any]:
    if stage not in VALID_STAGES:
        raise ValueError("Unsupported onboarding stage")
    record = _stage_record(employee_id, stage, table)
    if record is None or record.get("status") != "in_progress":
        return {"ok": False, "status": 409, "code": "STAGE_NOT_READY"}
    token = record.get("task_token")
    if not isinstance(token, str) or not token:
        return {"ok": False, "status": 409, "code": "STAGE_CALLBACK_EXPIRED"}
    try:
        _send_task_success(token, {"employee_id": employee_id, "stage": stage, "status": "complete", "source": source}, sfn=sfn)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code in ("TaskTimedOut", "InvalidToken", "TaskDoesNotExist"):
            return {"ok": False, "status": 409, "code": "STAGE_CALLBACK_EXPIRED"}
        raise
    # WP2's MarkStageComplete state performs the authoritative status update and
    # removes task_token after Step Functions accepts this callback.
    return {"ok": True, "employee_id": employee_id, "stage": stage, "status": "completion_submitted"}


def _record_simulated_assets(employee_id: str, *, equipment_table: Any | None = None,
                            now: str | None = None) -> list[dict[str, Any]]:
    """Create deterministic demo equipment assignments; safe to retry."""
    table = _table("EQUIPMENT_TABLE", "hrms-dev-equipment", equipment_table)
    timestamp = now or _now()
    assets = [
        {"asset_id": f"sim-{employee_id}-laptop", "type": "laptop", "model": "SIMULATED-LAPTOP"},
        {"asset_id": f"sim-{employee_id}-monitor", "type": "monitor", "model": "SIMULATED-MONITOR"},
    ]
    for asset in assets:
        item = {**asset, "status": "assigned", "assigned_to": employee_id,
                "provisioning_mode": "simulated", "assigned_at": timestamp}
        try:
            table.put_item(Item=item, ConditionExpression="attribute_not_exists(asset_id)")
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
                raise
            existing = table.get_item(Key={"asset_id": asset["asset_id"]}, ConsistentRead=True).get("Item", {})
            if existing.get("assigned_to") != employee_id or existing.get("provisioning_mode") != "simulated":
                raise RuntimeError("A simulated asset ID is already assigned to a different employee") from exc
    return assets


def _it_provisioning(employee_id: str, task_token: str, *, sfn: Any | None = None,
                     lambda_client: Any | None = None, equipment_table: Any | None = None) -> dict[str, Any]:
    simulation = os.environ.get("SIMULATION_MODE", "true").strip().lower() in ("1", "true", "yes")
    result: dict[str, Any]
    if simulation:
        result = {
            "mode": "simulated",
            "provisioned": True,
            "assets": _record_simulated_assets(employee_id, equipment_table=equipment_table),
        }
    else:
        function_name = os.environ.get("PROVISIONING_FUNCTION_NAME", "").strip()
        if not function_name:
            raise RuntimeError("PROVISIONING_FUNCTION_NAME is required when SIMULATION_MODE is false")
        client = lambda_client if lambda_client is not None else boto3.client("lambda")
        response = client.invoke(FunctionName=function_name, InvocationType="RequestResponse",
                                 Payload=json.dumps({"employee_id": employee_id, "action": "provision"}).encode("utf-8"))
        if response.get("FunctionError"):
            raise RuntimeError("IT provisioning provider failed")
        payload = response.get("Payload")
        raw = payload.read() if hasattr(payload, "read") else payload
        result = json.loads(raw or b"{}")
        if not isinstance(result, dict) or result.get("ok") is not True:
            raise RuntimeError("IT provisioning provider did not confirm success")
        result = {"mode": "real", "provisioned": True, "provider_result": result}
    _send_task_success(task_token, {"employee_id": employee_id, "stage": "it_provisioning",
                                    "status": "complete", "provisioning": result}, sfn=sfn)
    return {"ok": True, "employee_id": employee_id, "stage": "it_provisioning",
            "status": "completion_submitted", "mode": result["mode"]}


def start_stage(event: dict[str, Any], *, stages_table: Any | None = None,
                sfn: Any | None = None, lambda_client: Any | None = None,
                sns: Any | None = None) -> dict[str, Any]:
    employee_id = _required(event, "employee_id")
    stage = _required(event, "stage")
    task_token = _required(event, "taskToken")
    if stage not in VALID_STAGES:
        raise ValueError("Unsupported onboarding stage")
    # WP2 has already persisted the token and in_progress state before invoking us.
    record = _stage_record(employee_id, stage, stages_table)
    if not record or record.get("status") != "in_progress" or record.get("task_token") != task_token:
        raise ValueError("Stage callback state is not active")
    if stage == "it_provisioning":
        return _it_provisioning(employee_id, task_token, sfn=sfn, lambda_client=lambda_client)
    if stage == "manager_intro":
        topic = os.environ.get("STAGE_NOTIFICATION_TOPIC_ARN", "").strip()
        if topic:
            client = sns if sns is not None else boto3.client("sns")
            client.publish(TopicArn=topic, Subject="HRMS manager introduction required",
                           Message=json.dumps({"employee_id": employee_id, "stage": stage, "action_required": "schedule_manager_intro"}))
    # Documents and human policy/manager stages intentionally wait for their
    # corresponding verified document, signature, or HR completion event.
    return {"ok": True, "employee_id": employee_id, "stage": stage, "status": "waiting_for_completion"}


def sign_policy(event: dict[str, Any], *, employees_table: Any | None = None,
                stages_table: Any | None = None, sfn: Any | None = None,
                now: str | None = None) -> dict[str, Any]:
    employee_id = _required(event, "employee_id")
    policy = event.get("policy")
    caller = event.get("caller")
    employee = _employee(employee_id, employees_table)
    if not _caller_authorized(employee, caller) or not isinstance(caller, dict) or caller.get("is_admin") is True:
        return {"statusCode": 403, "headers": {"content-type": "application/json"},
                "body": json.dumps({"error": {"code": "FORBIDDEN", "message": "Only the employee can accept their policies"}})}
    if not isinstance(policy, dict):
        raise ValueError("policy must be a JSON object")
    policy_id = policy.get("policy_id")
    version = policy.get("policy_version", policy.get("version"))
    accepted = policy.get("accepted")
    if not isinstance(policy_id, str) or not POLICY_ID_RE.fullmatch(policy_id):
        raise ValueError("policy_id has an invalid format")
    if not isinstance(version, str) or not version.strip() or len(version) > 64:
        raise ValueError("policy_version must be a non-empty string of at most 64 characters")
    if accepted is not True:
        raise ValueError("accepted must be true to record policy acceptance")
    table = _table("STAGES_TABLE", "hrms-dev-onboarding-stages", stages_table)
    record = _stage_record(employee_id, "policy_signoff", table)
    if not record or record.get("status") != "in_progress" or not record.get("task_token"):
        return {"statusCode": 409, "headers": {"content-type": "application/json"},
                "body": json.dumps({"error": {"code": "STAGE_NOT_READY", "message": "Policy sign-off is not currently open"}})}
    timestamp = now or _now()
    # DynamoDB cannot assign a nested map key until the parent map exists.
    table.update_item(
        Key={"employee_id": employee_id, "stage": "policy_signoff"},
        UpdateExpression="SET policy_acceptances = if_not_exists(policy_acceptances, :empty)",
        ConditionExpression="#status = :in_progress AND attribute_exists(task_token)",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={":empty": {}, ":in_progress": "in_progress"},
    )
    updated = table.update_item(
        Key={"employee_id": employee_id, "stage": "policy_signoff"},
        UpdateExpression="SET policy_acceptances.#policy = :acceptance",
        ConditionExpression="#status = :in_progress AND attribute_exists(task_token)",
        ExpressionAttributeNames={"#policy": policy_id, "#status": "status"},
        ExpressionAttributeValues={":acceptance": {"policy_version": version.strip(), "accepted_at": timestamp, "accepted": True},
                                   ":in_progress": "in_progress"},
        ReturnValues="ALL_NEW",
    ).get("Attributes", {})
    required = [item.strip() for item in os.environ.get("REQUIRED_POLICIES", "acceptable-use,privacy,security").split(",") if item.strip()]
    acceptances = updated.get("policy_acceptances", {})
    complete = bool(required) and all(isinstance(acceptances.get(item), dict) and acceptances[item].get("accepted") is True for item in required)
    if complete:
        result = _complete(employee_id, "policy_signoff", table=table, sfn=sfn, source="policy_acceptance")
        if not result.get("ok"):
            return {"statusCode": result.get("status", 409), "headers": {"content-type": "application/json"},
                    "body": json.dumps({"error": {"code": result.get("code", "STAGE_NOT_READY"), "message": "Policy acceptance was recorded but the workflow callback could not be completed"}})}
    return {"statusCode": 200, "headers": {"content-type": "application/json"},
            "body": json.dumps({"employee_id": employee_id, "policy_id": policy_id, "accepted": True,
                                "required_policies_complete": complete,
                                "stage_status": "completion_submitted" if complete else "in_progress"})}


def complete_stage(event: dict[str, Any], *, employees_table: Any | None = None,
                   documents_table: Any | None = None, stages_table: Any | None = None,
                   sfn: Any | None = None) -> dict[str, Any]:
    employee_id = _required(event, "employee_id")
    stage = _required(event, "stage")
    source = event.get("source")
    if stage == "document_collection" and source == "document_validation":
        table = _table("DOCUMENTS_TABLE", "hrms-dev-documents", documents_table)
        page = table.query(
            KeyConditionExpression=Key("employee_id").eq(employee_id),
            ConsistentRead=True,
        )
        records = list(page.get("Items", []))
        while page.get("LastEvaluatedKey"):
            page = table.query(
                KeyConditionExpression=Key("employee_id").eq(employee_id),
                ConsistentRead=True,
                ExclusiveStartKey=page["LastEvaluatedKey"],
            )
            records.extend(page.get("Items", []))
        statuses = {item.get("doc_type"): item.get("status") for item in records}
        required = ("id_proof", "degree_certificate", "signed_offer_letter")
        if not all(statuses.get(item) == "verified" for item in required):
            return {"statusCode": 409, "headers": {"content-type": "application/json"},
                    "body": json.dumps({"error": {"code": "DOCUMENTS_INCOMPLETE", "message": "All required documents must be verified"}})}
    elif stage == "manager_intro" and source == "hr_admin":
        employee = _employee(employee_id, employees_table)
        caller = event.get("caller")
        if not isinstance(caller, dict) or caller.get("is_admin") is not True or employee is None:
            return {"statusCode": 403, "headers": {"content-type": "application/json"},
                    "body": json.dumps({"error": {"code": "FORBIDDEN", "message": "HR administrator access is required"}})}
    else:
        return {"statusCode": 400, "headers": {"content-type": "application/json"},
                "body": json.dumps({"error": {"code": "INVALID_COMPLETION_SOURCE", "message": "This stage cannot be completed by this action"}})}
    result = _complete(employee_id, stage, table=stages_table, sfn=sfn, source=source)
    if not result.get("ok"):
        return {"statusCode": result.get("status", 409), "headers": {"content-type": "application/json"},
                "body": json.dumps({"error": {"code": result.get("code", "STAGE_NOT_READY"), "message": "Stage callback could not be completed"}})}
    return {"statusCode": 202, "headers": {"content-type": "application/json"},
            "body": json.dumps({"employee_id": employee_id, "stage": stage, "status": "completion_submitted"})}


def lambda_handler(event: dict[str, Any], context: Any) -> Any:
    if not isinstance(event, dict):
        raise ValueError("Event must be a JSON object")
    action = event.get("action")
    try:
        if action == "start_stage":
            return start_stage(event)
        if action == "sign_policy":
            return sign_policy(event)
        if action == "complete_stage":
            return complete_stage(event)
        return {"statusCode": 400, "headers": {"content-type": "application/json"},
                "body": json.dumps({"error": {"code": "INVALID_ACTION", "message": "Unsupported stage action"}})}
    except ValueError as exc:
        return {"statusCode": 400, "headers": {"content-type": "application/json"},
                "body": json.dumps({"error": {"code": "INVALID_REQUEST", "message": str(exc)}})}
    except ClientError:
        logger.exception("Stage handler dependency failed.")
        return {"statusCode": 502, "headers": {"content-type": "application/json"},
                "body": json.dumps({"error": {"code": "DEPENDENCY_FAILURE", "message": "Stage service could not complete the request"}})}
    except RuntimeError:
        logger.exception("Stage handler is misconfigured.")
        return {"statusCode": 503, "headers": {"content-type": "application/json"},
                "body": json.dumps({"error": {"code": "SERVICE_NOT_CONFIGURED", "message": "Stage service is not configured"}})}
