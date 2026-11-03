"""WP4 synchronous business adapter. WP2 exclusively owns stage lifecycle."""
from __future__ import annotations
import os
from typing import Any
from services.stages.stages import WP4_STAGES, validate_employee_id, validate_stage

SUPPORTED_WP4_STAGES = set(WP4_STAGES)

def execute_simulated_action(stage: str, correlation_id: str) -> dict[str, Any]:
    if stage == "it_provisioning":
        result = {"equipment_status": "assigned", "account_status": "created"}
    elif stage == "policy_signoff":
        result = {"policy_status": "accepted"}
    elif stage == "manager_intro":
        result = {"invitation_status": "created"}
    else:
        raise ValueError("Unsupported WP4 stage")
    return {**result, "correlation_id": correlation_id}

def process_stage(event: dict[str, Any], mode: str) -> dict[str, Any]:
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
    if mode not in {"simulated", "real"}:
        raise RuntimeError("MODE must be explicitly configured as simulated or real")
    if event.get("mode") != mode:
        raise ValueError("Invocation mode does not match deployed MODE")
    if mode == "real":
        raise NotImplementedError("Real stage integrations are unavailable: no approved provider is configured")
    return {"ok": True, "employee_id": employee_id, "stage": stage, "status": "complete", "mode": "simulated", "result": execute_simulated_action(stage, correlation_id)}

def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    mode = os.environ.get("MODE", "").strip()
    if mode not in {"simulated", "real"}:
        return {"ok": False, "error": "MODE must be explicitly configured as simulated or real"}
    try:
        return process_stage(event, mode)
    except NotImplementedError as exc:
        return {"ok": False, "error": str(exc)}
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    except Exception:
        return {"ok": False, "error": "Stage execution failed"}
