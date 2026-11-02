
"""WP4 onboarding stage handler."""

import json
import os
from datetime import datetime, timezone

from services.stages.stages import (
    WP4_STAGES,
    build_stage_record,
    validate_employee_id,
    validate_stage,
)
from services.stages.repository import save_stage_record


SUPPORTED_WP4_STAGES = set(WP4_STAGES)


def response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def execute_simulated_action(stage, event):
    """Simulate a successful stage action for local testing."""

    if stage == "it_provisioning":
        return {
            "action": "simulated_it_provisioning",
            "mode": "simulated",
            "success": True,
        }

    if stage == "policy_signoff":
        return {
            "action": "simulated_policy_signoff",
            "mode": "simulated",
            "success": True,
        }

    if stage == "manager_intro":
        return {
            "action": "simulated_manager_intro",
            "mode": "simulated",
            "success": True,
        }

    raise ValueError("Unsupported WP4 stage")


def process_stage(event, mode="simulated"):
    if not isinstance(event, dict):
        raise ValueError("Event must be a JSON object")

    employee_id = validate_employee_id(event.get("employee_id"))
    stage = validate_stage(event.get("stage"))

    if stage not in SUPPORTED_WP4_STAGES:
        raise ValueError("WP4 does not process this stage")

    if mode == "real":
        raise NotImplementedError(
            "Real stage integrations are awaiting team confirmation"
        )

    if mode != "simulated":
        raise ValueError("Mode must be simulated or real")

    record = build_stage_record(
        employee_id,
        stage,
        "in_progress",
    )
    record["started_at"] = datetime.now(timezone.utc).isoformat()
    save_stage_record(record)

    action_result = execute_simulated_action(stage, event)

    if not action_result.get("success"):
        raise RuntimeError("Stage action failed")

    completed_record = build_stage_record(
        employee_id,
        stage,
        "complete",
    )
    completed_record["started_at"] = record["started_at"]
    completed_record["completed_at"] = datetime.now(
        timezone.utc
    ).isoformat()
    save_stage_record(dict(completed_record))
    completed_record["action_result"] = action_result

    return completed_record


def lambda_handler(event, context):
    try:
        mode = os.environ.get("STAGE_MODE", "simulated")
        result = process_stage(event, mode)

        return response(200, {
            "success": True,
            "data": result,
        })

    except ValueError as exc:
        return response(400, {
            "success": False,
            "error": str(exc),
        })

    except NotImplementedError as exc:
        return response(501, {
            "success": False,
            "error": str(exc),
        })

    except RuntimeError as exc:
        return response(500, {
            "success": False,
            "error": str(exc),
        })
