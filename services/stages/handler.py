"""WP4 synchronous business-handler adapter.

WP2 owns canonical onboarding-stage lifecycle state. This module performs
stage-specific business actions only and never writes task tokens or lifecycle
fields to the onboarding-stages table.
"""

import json
import os

from services.stages.stages import WP4_STAGES, validate_employee_id, validate_stage


SUPPORTED_WP4_STAGES = set(WP4_STAGES)


def response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def execute_simulated_action(stage, event, correlation_id):
    """Return deterministic simulated results for the same stage correlation."""
    if stage == "it_provisioning":
        result = {
            "equipment_status": "assigned",
            "account_status": "created",
        }
    elif stage == "policy_signoff":
        result = {"policy_status": "accepted"}
    elif stage == "manager_intro":
        result = {"invitation_status": "created"}
    else:
        raise ValueError("Unsupported WP4 stage")

    return {
        **result,
        "correlation_id": correlation_id,
    }


def process_stage(event, mode="simulated"):
    """Execute one WP4 business action without changing WP2 lifecycle state."""
    if not isinstance(event, dict):
        raise ValueError("Event must be a JSON object")

    if event.get("action") != "execute_stage":
        raise ValueError("action must be execute_stage")

    employee_id = validate_employee_id(event.get("employee_id"))
    stage = validate_stage(event.get("stage"))
    if stage not in SUPPORTED_WP4_STAGES:
        raise ValueError("WP4 does not process this stage")

    correlation_id = event.get("correlation_id")
    if not isinstance(correlation_id, str) or not correlation_id.strip():
        raise ValueError("correlation_id is required")
    correlation_id = correlation_id.strip()

    if mode == "real":
        raise NotImplementedError(
            "Real stage integrations are unavailable: no approved provider is configured"
        )
    if mode != "simulated":
        raise ValueError("MODE must be simulated or real")

    result = execute_simulated_action(stage, event, correlation_id)
    return {
        "ok": True,
        "employee_id": employee_id,
        "stage": stage,
        "status": "complete",
        "mode": "simulated",
        "result": result,
    }


def lambda_handler(event, context):
    try:
        # Mode is deployment configuration, never selected by an untrusted caller.
        mode = os.environ.get("MODE", "simulated")
        result = process_stage(event, mode)
        return response(200, result)
    except ValueError as exc:
        return response(400, {"ok": False, "error": str(exc)})
    except NotImplementedError as exc:
        return response(501, {"ok": False, "error": str(exc)})
    except Exception:
        # Avoid returning internal provider or infrastructure details.
        return response(500, {"ok": False, "error": "Stage execution failed"})
