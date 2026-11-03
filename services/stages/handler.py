"""WP4 synchronous business adapter and policy-acceptance recorder."""
from __future__ import annotations
import os, re
from datetime import datetime, timezone
from typing import Any
import boto3
from services.stages.stages import WP4_STAGES, validate_employee_id, validate_stage
SUPPORTED_WP4_STAGES=set(WP4_STAGES)
POLICY_ID_PATTERN=re.compile(r"^[A-Za-z0-9_-]{1,64}$")
def _stages_table(table=None):
    if table is not None: return table
    name=os.environ.get("STAGES_TABLE","").strip()
    if not name: raise RuntimeError("STAGES_TABLE is not configured")
    return boto3.resource("dynamodb").Table(name)
def execute_simulated_action(stage: str, correlation_id: str) -> dict[str, Any]:
    if stage=="it_provisioning": result={"equipment_status":"assigned","account_status":"created"}
    elif stage=="manager_intro": result={"invitation_status":"created"}
    else: raise ValueError("Unsupported WP4 business stage")
    return {**result,"correlation_id":correlation_id}
def process_stage(event: dict[str, Any], mode: str) -> dict[str, Any]:
    if not isinstance(event,dict): raise ValueError("Event must be a JSON object")
    if event.get("action")!="execute_stage": raise ValueError("action must be execute_stage")
    employee_id=validate_employee_id(event.get("employee_id")); stage=validate_stage(event.get("stage"))
    if stage not in SUPPORTED_WP4_STAGES: raise ValueError("WP4 does not execute this stage")
    correlation=event.get("correlation_id")
    if not isinstance(correlation,str) or not correlation.strip(): raise ValueError("correlation_id is required")
    correlation=correlation.strip()
    if mode not in {"simulated","real"}: raise RuntimeError("MODE must be explicitly configured as simulated or real")
    if event.get("mode")!=mode: raise ValueError("Invocation mode does not match deployed MODE")
    if mode=="real": raise NotImplementedError("Real stage integrations are unavailable: no approved provider is configured")
    return {"ok":True,"employee_id":employee_id,"stage":stage,"status":"complete","mode":"simulated","result":execute_simulated_action(stage,correlation)}
def record_policy_acceptance(event: dict[str, Any], *, table=None, now=None) -> dict[str, Any]:
    if not isinstance(event,dict) or event.get("action")!="sign_policy": raise ValueError("action must be sign_policy")
    employee_id=validate_employee_id(event.get("employee_id"))
    caller=event.get("caller"); sub=caller.get("sub") if isinstance(caller,dict) else None
    if not isinstance(sub,str) or not sub.strip(): raise ValueError("Verified Cognito subject is required")
    policy=event.get("policy")
    if not isinstance(policy,dict): raise ValueError("policy is required")
    policy_id=policy.get("policy_id"); version=policy.get("version")
    if not isinstance(policy_id,str) or not POLICY_ID_PATTERN.fullmatch(policy_id): raise ValueError("Invalid policy_id")
    if not isinstance(version,str) or not version.strip() or len(version)>64: raise ValueError("Invalid policy version")
    if policy.get("accepted") is not True: raise ValueError("Explicit policy acceptance is required")
    target=_stages_table(table); key={"employee_id":employee_id,"stage":"policy_signoff"}
    existing=target.get_item(Key=key,ConsistentRead=True).get("Item",{})
    previous=existing.get("policy_acceptances",{}).get(policy_id,{})
    if previous.get("version")==version and previous.get("cognito_sub")==sub and previous.get("accepted") is True:
        return {"ok":True,"employee_id":employee_id,"stage":"policy_signoff","status":"accepted","already_accepted":True,"policy":{"policy_id":policy_id,"version":version}}
    accepted_at=now or datetime.now(timezone.utc).isoformat()
    acceptance={"policy_id":policy_id,"version":version,"accepted":True,"accepted_at":accepted_at,"cognito_sub":sub}
    target.update_item(Key=key,UpdateExpression="SET #acceptances.#policy_id = :acceptance",ExpressionAttributeNames={"#acceptances":"policy_acceptances","#policy_id":policy_id},ExpressionAttributeValues={":acceptance":acceptance})
    return {"ok":True,"employee_id":employee_id,"stage":"policy_signoff","status":"accepted","already_accepted":False,"policy":{"policy_id":policy_id,"version":version},"accepted_at":accepted_at}
def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    mode=os.environ.get("MODE","").strip()
    if mode not in {"simulated","real"}: return {"ok":False,"error":"MODE must be explicitly configured as simulated or real"}
    try:
        if isinstance(event,dict) and event.get("action")=="sign_policy": return record_policy_acceptance(event)
        return process_stage(event,mode)
    except NotImplementedError as exc: return {"ok":False,"error":str(exc)}
    except ValueError as exc: return {"ok":False,"error":str(exc)}
    except Exception: return {"ok":False,"error":"Stage execution failed"}
