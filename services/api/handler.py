"""WP5 HTTP API handlers for HRMS onboarding.

The Lambda is designed for API Gateway HTTP API payload format 2.0. All AWS
clients are created lazily, and helpers accept injected clients/tables for
offline tests. No AWS resources are created by importing or testing this module.
"""
from __future__ import annotations

import base64
import json
import logging
import os
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from services.identity.handler import (
    IdentityError,
    InvalidEmployeeInput,
    create_employee,
)

logger = logging.getLogger(__name__)
STAGES = ("document_collection", "it_provisioning", "policy_signoff", "manager_intro")


def _response(status: int, payload: Any) -> dict[str, Any]:
    return {
        "statusCode": status,
        "headers": {"content-type": "application/json", "cache-control": "no-store"},
        "body": json.dumps(payload, separators=(",", ":"), default=str),
        "isBase64Encoded": False,
    }


def _error(status: int, code: str, message: str) -> dict[str, Any]:
    return _response(status, {"error": {"code": code, "message": message}})


def _json_body(event: dict[str, Any]) -> dict[str, Any]:
    body = event.get("body")
    if event.get("isBase64Encoded") and isinstance(body, str):
        try:
            body = base64.b64decode(body).decode("utf-8")
        except (ValueError, UnicodeDecodeError) as exc:
            raise ValueError("Request body must be valid UTF-8 JSON.") from exc
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except json.JSONDecodeError as exc:
            raise ValueError("Request body must be valid JSON.") from exc
    if not isinstance(body, dict):
        raise ValueError("Request body must be a JSON object.")
    return body


def _claims(event: dict[str, Any]) -> dict[str, Any]:
    # HTTP API JWT authorizer claims. Never trust identity or role from the body.
    authorizer = event.get("requestContext", {}).get("authorizer", {})
    jwt = authorizer.get("jwt", {}) if isinstance(authorizer, dict) else {}
    claims = jwt.get("claims", {}) if isinstance(jwt, dict) else {}
    return claims if isinstance(claims, dict) else {}


def _is_admin(claims: dict[str, Any]) -> bool:
    configured = os.environ.get("HR_ADMIN_GROUP", "hr-admins")
    groups = claims.get("cognito:groups", [])
    if isinstance(groups, str):
        try:
            decoded = json.loads(groups)
            groups = decoded if isinstance(decoded, list) else [groups]
        except json.JSONDecodeError:
            groups = [part.strip() for part in groups.split(",") if part.strip()]
    return isinstance(groups, list) and configured in groups


def _is_self(claims: dict[str, Any], employee: dict[str, Any]) -> bool:
    """Authorize self-service by Cognito's immutable subject, never mutable email."""
    caller_sub = claims.get("sub")
    employee_sub = employee.get("cognito_sub")
    return (
        isinstance(caller_sub, str)
        and bool(caller_sub.strip())
        and isinstance(employee_sub, str)
        and bool(employee_sub.strip())
        and caller_sub == employee_sub
    )


def _employees_table(table: Any | None = None) -> Any:
    if table is not None:
        return table
    return boto3.resource("dynamodb").Table(
        os.environ.get("EMPLOYEES_TABLE", "hrms-dev-employees")
    )


def _stages_table(table: Any | None = None) -> Any:
    if table is not None:
        return table
    return boto3.resource("dynamodb").Table(
        os.environ.get("STAGES_TABLE", "hrms-dev-onboarding-stages")
    )


def _documents_table(table: Any | None = None) -> Any:
    if table is not None:
        return table
    return boto3.resource("dynamodb").Table(
        os.environ.get("DOCUMENTS_TABLE", "hrms-dev-documents")
    )


def _get_employee(employee_id: str, *, table: Any | None = None) -> dict[str, Any] | None:
    result = _employees_table(table).get_item(Key={"employee_id": employee_id}, ConsistentRead=True)
    item = result.get("Item")
    return item if isinstance(item, dict) else None


def get_progress(employee_id: str, *, table: Any | None = None) -> dict[str, Any]:
    """Return a stable four-stage progress view, including pending stages."""
    result = _stages_table(table).query(
        KeyConditionExpression=Key("employee_id").eq(employee_id),
        ConsistentRead=True,
    )
    records = {
        item.get("stage"): item
        for item in result.get("Items", [])
        if isinstance(item, dict) and item.get("stage") in STAGES
    }
    while result.get("LastEvaluatedKey"):
        result = _stages_table(table).query(
            KeyConditionExpression=Key("employee_id").eq(employee_id),
            ConsistentRead=True,
            ExclusiveStartKey=result["LastEvaluatedKey"],
        )
        records.update({item.get("stage"): item for item in result.get("Items", []) if isinstance(item, dict) and item.get("stage") in STAGES})
    stages = []
    for stage in STAGES:
        record = records.get(stage, {})
        stages.append({
            "stage": stage,
            "status": record.get("status", "pending"),
            **({"started_at": record["started_at"]} if record.get("started_at") else {}),
            **({"completed_at": record["completed_at"]} if record.get("completed_at") else {}),
        })
    completed = sum(1 for stage in stages if stage["status"] == "complete")
    return {"employee_id": employee_id, "completed_stages": completed, "total_stages": len(STAGES), "stages": stages}


def _invoke_service(function_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Invoke a configured package Lambda; missing integrations fail closed."""
    if not function_name:
        return _error(503, "SERVICE_NOT_CONFIGURED", "This service integration is not configured yet.")
    response = boto3.client("lambda").invoke(
        FunctionName=function_name,
        InvocationType="RequestResponse",
        Payload=json.dumps(payload).encode("utf-8"),
    )
    if response.get("FunctionError"):
        logger.error("Downstream service invocation failed (function error).")
        return _error(502, "DEPENDENCY_FAILURE", "A required onboarding service failed.")
    raw = response.get("Payload")
    decoded = raw.read() if hasattr(raw, "read") else raw
    try:
        result = json.loads(decoded or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError, TypeError):
        return _error(502, "INVALID_DEPENDENCY_RESPONSE", "A required onboarding service returned an invalid response.")
    # Allow a downstream Lambda to return an API Gateway response envelope.
    if isinstance(result, dict) and isinstance(result.get("statusCode"), int) and "body" in result:
        return result
    if isinstance(result, dict) and result.get("ok") is False:
        logger.error("Downstream service returned a failure envelope.")
        return _error(502, "DEPENDENCY_FAILURE", "A required onboarding service could not complete the request.")
    return _response(200, result)


def _start_onboarding(employee: dict[str, Any], *, employees_table: Any) -> dict[str, Any]:
    state_machine_arn = os.environ.get("STATE_MACHINE_ARN", "").strip()
    if not state_machine_arn:
        raise RuntimeError("STATE_MACHINE_ARN is not configured")
    sfn = boto3.client("stepfunctions")
    try:
        execution = sfn.start_execution(
            stateMachineArn=state_machine_arn,
            name=employee["employee_id"],
            input=json.dumps({"employee_id": employee["employee_id"], "current_stage": STAGES[0]}),
        )
    except ClientError as exc:
        # The employee and Cognito user already exist. Attempt both compensating
        # actions independently so a missing pool ID or Cognito failure cannot
        # prevent DynamoDB cleanup. Never log PII/credentials.
        try:
            pool_id = os.environ.get("COGNITO_USER_POOL_ID", "").strip()
            if pool_id:
                boto3.client("cognito-idp").admin_delete_user(
                    UserPoolId=pool_id,
                    Username=employee["email"],
                )
        except ClientError:
            logger.error("Cognito cleanup failed after workflow startup failure.")
        try:
            employees_table.delete_item(Key={"employee_id": employee["employee_id"]})
        except ClientError:
            logger.error("Employee record cleanup failed after workflow startup failure.")
        raise RuntimeError("Could not start onboarding workflow") from exc
    arn = execution.get("executionArn")
    if not isinstance(arn, str) or not arn:
        # Do not attempt rollback: Step Functions may already be running.
        logger.error("Workflow started but execution ARN was absent from the response.")
        raise RuntimeError("Workflow started but its execution ARN could not be recorded")
    try:
        employees_table.update_item(
            Key={"employee_id": employee["employee_id"]},
            UpdateExpression="SET execution_arn = :arn",
            ExpressionAttributeValues={":arn": arn},
            ConditionExpression="attribute_exists(employee_id)",
        )
    except ClientError as exc:
        # The execution is live; don't delete its employee or Cognito records.
        logger.error("Workflow started but execution ARN persistence failed.")
        raise RuntimeError("Workflow started but its execution ARN could not be recorded") from exc
    return {**employee, "execution_arn": arn}


def _dispatch(event: dict[str, Any], *, employees_table: Any | None = None,
              stages_table: Any | None = None, documents_table: Any | None = None) -> dict[str, Any]:
    method = event.get("requestContext", {}).get("http", {}).get("method")
    path = event.get("rawPath", "")
    path_params = event.get("pathParameters") or {}
    employee_id = path_params.get("employee_id")
    claims = _claims(event)
    admin = _is_admin(claims)

    if not method or not isinstance(path, str):
        return _error(400, "INVALID_EVENT", "Invalid API Gateway request.")

    if method == "POST" and path == "/employees":
        if not admin:
            return _error(403, "FORBIDDEN", "HR administrator access is required.")
        try:
            payload = _json_body(event)
        except ValueError as exc:
            return _error(400, "INVALID_REQUEST", str(exc))
        # Validate configuration before creating the employee/Cognito user so a
        # missing workflow ARN cannot leave an orphaned identity record.
        if not os.environ.get("STATE_MACHINE_ARN", "").strip():
            return _error(503, "SERVICE_NOT_CONFIGURED", "Onboarding workflow is not configured yet.")
        if not os.environ.get("COGNITO_USER_POOL_ID", "").strip():
            return _error(503, "SERVICE_NOT_CONFIGURED", "Employee identity is not configured yet.")
        table = _employees_table(employees_table)
        try:
            created = create_employee(payload, table=table)
            employee = _start_onboarding(created, employees_table=table)
            # Avoid exposing execution ARNs to clients.
            public = {key: employee[key] for key in ("employee_id", "full_name", "email", "status", "created_at") if key in employee}
            return _response(201, {"employee": public})
        except InvalidEmployeeInput as exc:
            return _error(400, "INVALID_REQUEST", str(exc))
        except IdentityError as exc:
            return _error(502, "IDENTITY_CREATION_FAILED", str(exc))
        except RuntimeError as exc:
            return _error(503, "ONBOARDING_START_FAILED", str(exc))

    # Resolve the signed-in employee from Cognito immutable subject.
    if method == "GET" and path == "/employees/me":
        caller_sub = claims.get("sub")
        if not isinstance(caller_sub, str) or not caller_sub.strip():
            return _error(401, "AUTHENTICATION_REQUIRED", "A valid Cognito subject is required.")
        try:
            table = _employees_table(employees_table)
            from boto3.dynamodb.conditions import Attr
            result = table.scan(FilterExpression=Attr("cognito_sub").eq(caller_sub))
            matches = list(result.get("Items", []))
            while result.get("LastEvaluatedKey"):
                result = table.scan(FilterExpression=Attr("cognito_sub").eq(caller_sub), ExclusiveStartKey=result["LastEvaluatedKey"])
                matches.extend(result.get("Items", []))
            if not matches:
                return _error(404, "EMPLOYEE_PROFILE_NOT_LINKED", "No employee profile is linked to this Cognito account.")
            if len(matches) != 1:
                logger.error("Multiple employee records are linked to one Cognito subject.")
                return _error(409, "EMPLOYEE_PROFILE_AMBIGUOUS", "The employee profile requires administrative review.")
            employee = matches[0]
            employee_id = employee["employee_id"]
            public_employee = {k: v for k, v in employee.items() if k not in {"execution_arn", "cognito_sub"}}
            return _response(200, {"employee": public_employee, "progress": get_progress(employee_id, table=stages_table)})
        except ClientError:
            logger.exception("Current employee profile lookup failed.")
            return _error(502, "DATA_ACCESS_FAILED", "Your employee profile could not be retrieved.")
    if method == "GET" and path == "/employees":
        if not admin:
            return _error(403, "FORBIDDEN", "HR administrator access is required.")
        table = _employees_table(employees_table)
        try:
            result = table.scan()
            items = list(result.get("Items", []))
            while result.get("LastEvaluatedKey"):
                result = table.scan(ExclusiveStartKey=result["LastEvaluatedKey"])
                items.extend(result.get("Items", []))
            output = []
            for item in items:
                if not isinstance(item, dict) or not item.get("employee_id"):
                    continue
                progress = get_progress(item["employee_id"], table=stages_table)
                public_item = dict(item)
                public_item.pop("execution_arn", None)
                public_item.pop("cognito_sub", None)
                output.append({**public_item, "progress": progress})
            return _response(200, {"employees": output})
        except ClientError:
            logger.exception("Employee list query failed.")
            return _error(502, "DATA_ACCESS_FAILED", "Employee records could not be retrieved.")

    if method == "GET" and isinstance(employee_id, str) and path.endswith("/progress"):
        employee = _get_employee(employee_id, table=employees_table)
        if employee is None:
            return _error(404, "NOT_FOUND", "Employee was not found.")
        if not admin and not _is_self(claims, employee):
            return _error(403, "FORBIDDEN", "You cannot access this employee's progress.")
        try:
            return _response(200, get_progress(employee_id, table=stages_table))
        except ClientError:
            logger.exception("Employee progress query failed.")
            return _error(502, "DATA_ACCESS_FAILED", "Employee progress could not be retrieved.")

    if method == "GET" and isinstance(employee_id, str) and path == f"/employees/{employee_id}":
        employee = _get_employee(employee_id, table=employees_table)
        if employee is None:
            return _error(404, "NOT_FOUND", "Employee was not found.")
        if not admin and not _is_self(claims, employee):
            return _error(403, "FORBIDDEN", "You cannot access this employee profile.")
        employee.pop("execution_arn", None)
        employee.pop("cognito_sub", None)
        return _response(200, {"employee": employee})

    if method == "GET" and isinstance(employee_id, str) and path == f"/employees/{employee_id}/documents":
        employee = _get_employee(employee_id, table=employees_table)
        if employee is None:
            return _error(404, "NOT_FOUND", "Employee was not found.")
        if not admin and not _is_self(claims, employee):
            return _error(403, "FORBIDDEN", "You cannot access these documents.")
        return _invoke_service(os.environ.get("DOCUMENTS_FUNCTION_NAME", ""), {
            "action": "list_documents", "employee_id": employee_id,
            "caller": {"email": claims.get("email"), "sub": claims.get("sub"), "is_admin": admin},
        })

    if method == "POST" and isinstance(employee_id, str) and path == f"/employees/{employee_id}/documents/upload-url":
        employee = _get_employee(employee_id, table=employees_table)
        if employee is None:
            return _error(404, "NOT_FOUND", "Employee was not found.")
        if not _is_self(claims, employee):
            return _error(403, "FORBIDDEN", "Only this employee can request an upload URL.")
        try:
            payload = _json_body(event)
        except ValueError as exc:
            return _error(400, "INVALID_REQUEST", str(exc))
        return _invoke_service(os.environ.get("DOCUMENTS_FUNCTION_NAME", ""), {
            "action": "create_upload_url", "employee_id": employee_id,
            "caller": {"email": claims.get("email"), "sub": claims.get("sub"), "is_admin": False},
            "document": payload,
        })

    if method == "POST" and isinstance(employee_id, str) and path == f"/employees/{employee_id}/policies/sign":
        employee = _get_employee(employee_id, table=employees_table)
        if employee is None:
            return _error(404, "NOT_FOUND", "Employee was not found.")
        if not _is_self(claims, employee):
            return _error(403, "FORBIDDEN", "Only this employee can sign their policies.")
        try:
            payload = _json_body(event)
        except ValueError as exc:
            return _error(400, "INVALID_REQUEST", str(exc))
        return _invoke_service(os.environ.get("STAGES_FUNCTION_NAME", ""), {
            "action": "sign_policy", "employee_id": employee_id,
            "caller": {"email": claims.get("email"), "sub": claims.get("sub"), "is_admin": False}, "policy": payload,
        })

    if method == "POST" and isinstance(employee_id, str) and path.startswith(f"/employees/{employee_id}/stages/") and path.endswith("/complete"):
        if not admin:
            return _error(403, "FORBIDDEN", "HR administrator access is required.")
        stage = path[len(f"/employees/{employee_id}/stages/"):-len("/complete")].strip("/")
        if stage not in STAGES:
            return _error(400, "INVALID_STAGE", "Unsupported onboarding stage.")
        if _get_employee(employee_id, table=employees_table) is None:
            return _error(404, "NOT_FOUND", "Employee was not found.")
        try:
            if stage == "manager_intro":
                return _invoke_service(os.environ.get("STAGES_FUNCTION_NAME", ""), {
                    "action": "complete_stage",
                    "employee_id": employee_id,
                    "stage": stage,
                    "source": "hr_admin",
                    "caller": {"sub": claims.get("sub"), "email": claims.get("email"), "is_admin": True},
                })
            from services.workflow.callbacks import CallbackConflict, resume_stage
            result = resume_stage(
                employee_id, stage, authorized=True,
                table=_stages_table(stages_table),
            )
            return _response(202, result)
        except CallbackConflict:
            return _error(409, "STAGE_CALLBACK_EXPIRED", "This stage callback expired or was already used.")
        except ValueError as exc:
            return _error(409, "STAGE_NOT_READY", str(exc))
        except PermissionError:
            return _error(403, "FORBIDDEN", "HR administrator access is required.")
        except ClientError:
            logger.exception("Stage completion submission failed.")
            return _error(502, "WORKFLOW_FAILURE", "Stage completion could not be submitted.")

    return _error(404, "NOT_FOUND", "Route not found.")


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """API Gateway entry point. API Gateway's JWT authorizer is mandatory."""
    if not isinstance(event, dict):
        return _error(400, "INVALID_EVENT", "Invalid API Gateway request.")
    claims = _claims(event)
    if not claims:
        return _error(401, "UNAUTHORIZED", "Authentication is required.")
    try:
        return _dispatch(event)
    except ClientError:
        logger.exception("Unhandled AWS service error in API handler.")
        return _error(502, "DEPENDENCY_FAILURE", "A required backend service failed.")
    except Exception:
        # Keep internal exception text, request bodies, and credentials out of
        # the HTTP response. The traceback stays in CloudWatch for operators.
        logger.exception("Unhandled API handler failure.")
        return _error(500, "INTERNAL_ERROR", "The request could not be completed.")
