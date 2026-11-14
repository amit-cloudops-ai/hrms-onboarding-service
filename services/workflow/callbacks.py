"""Server-side Step Functions callback support for WP2.

Call only after the API layer has authenticated the caller and authorized
completion of the requested employee stage.
"""
from __future__ import annotations

import json
from typing import Any

import boto3
from botocore.exceptions import ClientError

try:  # Works both as a package import from WP5 and as a local Lambda module.
    from .handler import VALID_STAGES
except ImportError:  # pragma: no cover - compatibility with direct module execution.
    from handler import VALID_STAGES


class CallbackConflict(RuntimeError):
    """The workflow callback token is expired or has already been consumed."""


_STALE_TOKEN_CODES = {
    "InvalidToken",
    "TaskDoesNotExist",
    "TaskTimedOut",
}


def resume_stage(
    employee_id: str,
    stage: str,
    *,
    authorized: bool,
    table: Any,
    stepfunctions: Any | None = None,
) -> dict[str, Any]:
    """Submit stage completion to Step Functions without exposing its token.

    `authorized` must be set by the trusted API authorization layer, never
    directly from a request-body field.
    """
    if authorized is not True:
        raise PermissionError("Caller is not authorized to complete this stage")

    if not isinstance(employee_id, str) or not employee_id.strip():
        raise ValueError("employee_id is required")

    employee_id = employee_id.strip()

    if not isinstance(stage, str) or stage not in VALID_STAGES:
        raise ValueError("Unknown onboarding stage")

    response = table.get_item(
        Key={"employee_id": employee_id, "stage": stage},
        ConsistentRead=True,
    )
    item = response.get("Item")

    if not item or item.get("status") != "in_progress":
        raise ValueError("Stage is not awaiting completion")

    token = item.get("task_token")
    if not isinstance(token, str) or not token:
        raise ValueError("No active callback is available for this stage")

    if stepfunctions is None:
        stepfunctions = boto3.client("stepfunctions")

    try:
        stepfunctions.send_task_success(
            taskToken=token,
            output=json.dumps({
                "employee_id": employee_id,
                "stage": stage,
                "status": "complete",
            }),
        )
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "Unknown")
        if code in _STALE_TOKEN_CODES:
            raise CallbackConflict(
                "The workflow callback has expired or was already consumed"
            ) from exc
        raise

    # The state machine's next state persists completion in DynamoDB.
    # A successful callback submission alone does not mean that update finished.
    return {
        "ok": True,
        "employee_id": employee_id,
        "stage": stage,
        "status": "completion_submitted",
    }
