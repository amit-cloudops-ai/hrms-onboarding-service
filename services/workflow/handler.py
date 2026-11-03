"""WP2 owns workflow sequencing, callback tokens and canonical stage lifecycle."""
from __future__ import annotations
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any
import boto3
from botocore.exceptions import ClientError

VALID_STAGES=("document_collection","it_provisioning","policy_signoff","manager_intro")
CALLBACK_STAGES=("document_collection","policy_signoff")
WP4_STAGES=("it_provisioning","manager_intro")
logger=logging.getLogger(__name__)

def _now():
    return datetime.now(timezone.utc).isoformat()

def _required(event, field):
    value=event.get(field)
    if not isinstance(value,str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()

def _stage(event):
    value=_required(event,"stage")
    if value not in VALID_STAGES:
        raise ValueError(f"Unsupported stage: {value}")
    return value

def _table(table=None):
    return table if table is not None else boto3.resource("dynamodb").Table(os.environ.get("STAGES_TABLE","hrms-dev-onboarding-stages"))

def _conditional(exc):
    return isinstance(exc,ClientError) and exc.response.get("Error",{}).get("Code")=="ConditionalCheckFailedException"

def _callback_ready(item,stage):
    if stage=="document_collection":
        return item.get("documents_verified") is True
    return item.get("policy_accepted") is True

def _send_callback(token,employee_id,stage,stepfunctions=None):
    client=stepfunctions or boto3.client("stepfunctions")
    try:
        client.send_task_success(taskToken=token,output=json.dumps({
            "employee_id":employee_id,"stage":stage,"status":"complete"
        }))
        return True
    except ClientError as exc:
        code=exc.response.get("Error",{}).get("Code")
        if code in {"InvalidToken","TaskDoesNotExist","TaskTimedOut"}:
            # The callback task may have timed out and be rotating its token.
            # Readiness remains persisted; the next start_stage invocation
            # detects it and resumes using the fresh token.
            return False
        raise

def start_stage(event,*,table=None,stepfunctions=None,now=None):
    """Start a human/document callback stage; task token never leaves WP2."""
    employee_id=_required(event,"employee_id")
    stage=_stage(event)
    if stage not in CALLBACK_STAGES:
        raise ValueError("Callback tokens are reserved for document_collection and policy_signoff")
    token=_required(event,"taskToken")
    target=_table(table)
    try:
        target.update_item(
            Key={"employee_id":employee_id,"stage":stage},
            UpdateExpression="SET #status=:active, started_at=if_not_exists(started_at,:now), task_token=:token, reminder_count=if_not_exists(reminder_count,:zero)",
            ConditionExpression="attribute_not_exists(#status) OR #status=:pending OR (#status=:active AND task_token=:token)",
            ExpressionAttributeNames={"#status":"status"},
            ExpressionAttributeValues={":active":"in_progress",":pending":"pending",":now":now or _now(),":token":token,":zero":0},
        )
    except ClientError as exc:
        if not _conditional(exc):
            raise
        current=target.get_item(Key={"employee_id":employee_id,"stage":stage},ConsistentRead=True).get("Item",{})
        if current.get("status")!="in_progress" or current.get("task_token")!=token:
            raise
    current=target.get_item(Key={"employee_id":employee_id,"stage":stage},ConsistentRead=True).get("Item",{})
    if _callback_ready(current,stage):
        _send_callback(token,employee_id,stage,stepfunctions)
    return {"ok":True,"employee_id":employee_id,"stage":stage,"status":"in_progress"}

def resume_document_collection(event,*,table=None,stepfunctions=None):
    """Trusted WP3 callback: persist verification readiness and resume if token exists."""
    employee_id=_required(event,"employee_id")
    target=_table(table)
    target.update_item(
        Key={"employee_id":employee_id,"stage":"document_collection"},
        UpdateExpression="SET documents_verified=:yes",
        ExpressionAttributeValues={":yes":True},
    )
    item=target.get_item(
        Key={"employee_id":employee_id,"stage":"document_collection"},
        ConsistentRead=True,
    ).get("Item",{})
    if item.get("status")=="complete":
        return {"ok":True,"employee_id":employee_id,"stage":"document_collection","status":"already_complete"}
    token=item.get("task_token")
    if item.get("status")=="in_progress" and isinstance(token,str) and token:
        submitted=_send_callback(token,employee_id,"document_collection",stepfunctions)
        status="completion_submitted" if submitted else "callback_deferred_until_token_refresh"
        return {"ok":True,"employee_id":employee_id,"stage":"document_collection","status":status}
    return {"ok":True,"employee_id":employee_id,"stage":"document_collection","status":"verified_waiting_for_workflow"}

def start_business_stage(event,*,table=None,now=None):
    employee_id=_required(event,"employee_id")
    stage=_stage(event)
    if stage not in WP4_STAGES:
        raise ValueError("This stage is not a WP4 synchronous business stage")
    correlation=_required(event,"correlation_id")
    target=_table(table)
    try:
        target.update_item(
            Key={"employee_id":employee_id,"stage":stage},
            UpdateExpression="SET #status=:active, started_at=if_not_exists(started_at,:now), correlation_id=:correlation",
            ConditionExpression="attribute_not_exists(#status) OR #status=:pending OR #status=:failed OR (#status=:active AND correlation_id=:correlation)",
            ExpressionAttributeNames={"#status":"status"},
            ExpressionAttributeValues={":active":"in_progress",":pending":"pending",":failed":"failed",":now":now or _now(),":correlation":correlation},
        )
    except ClientError as exc:
        if not _conditional(exc):
            raise
        current=target.get_item(Key={"employee_id":employee_id,"stage":stage},ConsistentRead=True).get("Item",{})
        if current.get("status")!="in_progress" or current.get("correlation_id")!=correlation:
            raise
    return {"ok":True,"employee_id":employee_id,"stage":stage,"status":"in_progress","correlation_id":correlation}

def execute_business_stage(event,*,lambda_client=None):
    """Invoke WP4 synchronously with no task token and validate its direct JSON result."""
    employee_id=_required(event,"employee_id")
    stage=_stage(event)
    if stage not in WP4_STAGES:
        raise ValueError("This stage is not a WP4 synchronous business stage")
    correlation=_required(event,"correlation_id")
    mode=os.environ.get("MODE","").strip()
    if mode not in {"simulated","real"}:
        raise RuntimeError("MODE must be explicitly configured as simulated or real")
    function_name=os.environ.get("STAGES_FUNCTION_NAME","").strip()
    if not function_name:
        raise RuntimeError("STAGES_FUNCTION_NAME is not configured")
    client=lambda_client or boto3.client("lambda")
    payload={"action":"execute_stage","employee_id":employee_id,"stage":stage,"mode":mode,"correlation_id":correlation}
    response=client.invoke(FunctionName=function_name,InvocationType="RequestResponse",Payload=json.dumps(payload).encode("utf-8"))
    if response.get("FunctionError"):
        raise RuntimeError("WP4 business-stage execution failed")
    stream=response.get("Payload")
    raw=stream.read() if hasattr(stream,"read") else stream
    try:
        result=json.loads(raw or b"{}")
    except (json.JSONDecodeError,UnicodeDecodeError,TypeError) as exc:
        raise RuntimeError("WP4 returned invalid JSON") from exc
    if not isinstance(result,dict) or result.get("ok") is not True or result.get("employee_id")!=employee_id or result.get("stage")!=stage or result.get("status")!="complete" or result.get("mode")!=mode:
        raise RuntimeError("WP4 did not confirm successful business-stage execution")
    return result

def mark_stage_complete(event,*,table=None,now=None):
    employee_id=_required(event,"employee_id")
    stage=_stage(event)
    correlation=event.get("correlation_id")
    if correlation is not None:
        if stage not in WP4_STAGES or not isinstance(correlation,str) or not correlation.strip():
            raise ValueError("Business-stage completion requires a valid correlation_id")
        condition="#status=:active AND correlation_id=:correlation"
        values={":complete":"complete",":active":"in_progress",":now":now or _now(),":correlation":correlation.strip()}
    else:
        if stage not in CALLBACK_STAGES:
            raise ValueError("Only callback stages can complete without correlation_id")
        condition="#status=:active AND attribute_exists(task_token)"
        values={":complete":"complete",":active":"in_progress",":now":now or _now()}
    target=_table(table)
    try:
        target.update_item(
            Key={"employee_id":employee_id,"stage":stage},
            UpdateExpression="SET #status=:complete, completed_at=:now REMOVE task_token",
            ConditionExpression=condition,
            ExpressionAttributeNames={"#status":"status"},
            ExpressionAttributeValues=values,
        )
    except ClientError as exc:
        if not _conditional(exc):
            raise
        current=target.get_item(Key={"employee_id":employee_id,"stage":stage},ConsistentRead=True).get("Item",{})
        same=(correlation is None or current.get("correlation_id")==correlation)
        if current.get("status")=="complete" and same and not current.get("task_token"):
            return {"ok":True,"employee_id":employee_id,"stage":stage,"status":"complete"}
        raise
    return {"ok":True,"employee_id":employee_id,"stage":stage,"status":"complete"}

def mark_stage_failed(event,*,table=None,now=None):
    employee_id=_required(event,"employee_id")
    stage=_stage(event)
    if stage not in WP4_STAGES:
        raise ValueError("Only WP4 business stages can be marked failed")
    correlation=_required(event,"correlation_id")
    code=event.get("error_code","BUSINESS_STAGE_FAILED")
    if not isinstance(code,str) or not code.strip():
        code="BUSINESS_STAGE_FAILED"
    _table(table).update_item(
        Key={"employee_id":employee_id,"stage":stage},
        UpdateExpression="SET #status=:failed, failed_at=:now, failure_code=:code REMOVE task_token",
        ConditionExpression="#status=:active AND correlation_id=:correlation",
        ExpressionAttributeNames={"#status":"status"},
        ExpressionAttributeValues={":failed":"failed",":active":"in_progress",":now":now or _now(),":code":code[:80],":correlation":correlation},
    )
    return {"ok":True,"employee_id":employee_id,"stage":stage,"status":"failed"}

def send_reminder(event,*,table=None,sns=None,now=None):
    employee_id=_required(event,"employee_id")
    stage=_stage(event)
    if stage not in CALLBACK_STAGES:
        raise ValueError("Reminders are supported only for callback stages")
    topic=os.environ.get("REMINDER_TOPIC_ARN","").strip()
    if not topic:
        raise RuntimeError("REMINDER_TOPIC_ARN is not configured")
    updated=_table(table).update_item(
        Key={"employee_id":employee_id,"stage":stage},
        UpdateExpression="ADD reminder_count :one",
        ExpressionAttributeValues={":one":1},
        ReturnValues="UPDATED_NEW",
    )
    count=int(updated.get("Attributes",{}).get("reminder_count",1))
    client=sns or boto3.client("sns")
    client.publish(TopicArn=topic,Subject="HRMS onboarding reminder",Message=json.dumps({"employee_id":employee_id,"stage":stage,"reminder_count":count,"reminder_time":now or _now()}))
    return {"ok":True,"employee_id":employee_id,"stage":stage,"reminder_count":count}

def lambda_handler(event,context):
    if not isinstance(event,dict):
        raise ValueError("Event must be a JSON object")
    action=event.get("action")
    if action=="start_stage": return start_stage(event)
    if action=="resume_document_collection": return resume_document_collection(event)
    if action=="start_business_stage": return start_business_stage(event)
    if action=="execute_business_stage": return execute_business_stage(event)
    if action=="mark_stage_complete": return mark_stage_complete(event)
    if action=="mark_stage_failed": return mark_stage_failed(event)
    if action=="send_reminder": return send_reminder(event)
    raise ValueError("Unsupported workflow action")
