"""WP3 document collection: presigned uploads, private storage, validation and status.

The handler supports API adapter invocations and S3 ObjectCreated events. It makes
no AWS calls at import time and is testable with injected clients/tables.
"""
from __future__ import annotations

import json
import logging
import mimetypes
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.parse import unquote_plus

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
DOCUMENT_TYPES = ("id_proof", "degree_certificate", "signed_offer_letter")
ALLOWED = {
    "application/pdf": (".pdf",),
    "image/jpeg": (".jpg", ".jpeg"),
    "image/png": (".png",),
}
MAX_BYTES = 5 * 1024 * 1024


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _response(status: int, body: dict[str, Any]) -> dict[str, Any]:
    return {"statusCode": status, "headers": {"content-type": "application/json", "cache-control": "no-store"},
            "body": json.dumps(body, separators=(",", ":"), default=str), "isBase64Encoded": False}


def _table(name: str, table: Any | None = None) -> Any:
    if table is not None:
        return table
    configured = os.environ.get(name, "").strip()
    if not configured:
        raise RuntimeError(f"{name} is not configured")
    return boto3.resource("dynamodb").Table(configured)


def _s3(client: Any | None = None) -> Any:
    return client if client is not None else boto3.client("s3")


def _employees(employee_id: str, table: Any | None = None) -> dict[str, Any] | None:
    item = _table("EMPLOYEES_TABLE", table).get_item(Key={"employee_id": employee_id}, ConsistentRead=True).get("Item")
    return item if isinstance(item, dict) else None


def _authorized(employee_id: str, caller: Any, employees_table: Any | None = None) -> tuple[bool, dict[str, Any] | None]:
    if not isinstance(caller, dict):
        return False, None
    employee = _employees(employee_id, employees_table)
    if employee is None:
        return False, None
    if caller.get("is_admin") is True:
        return True, employee
    sub = caller.get("sub")
    return bool(isinstance(sub, str) and sub and sub == employee.get("cognito_sub")), employee


def _valid_request(document: Any) -> tuple[str, str, int]:
    if not isinstance(document, dict):
        raise ValueError("document must be a JSON object")
    doc_type = document.get("document_type", document.get("doc_type"))
    content_type = document.get("content_type")
    file_size = document.get("file_size")
    if doc_type not in DOCUMENT_TYPES:
        raise ValueError("document_type must be one of the required document types")
    if content_type not in ALLOWED:
        raise ValueError("Only PDF, JPEG, and PNG files are accepted")
    if isinstance(file_size, bool) or not isinstance(file_size, int) or file_size < 1 or file_size > MAX_BYTES:
        raise ValueError("file_size must be between 1 byte and 5 MB")
    return doc_type, content_type, file_size


def _key(employee_id: str, doc_type: str, content_type: str) -> str:
    extension = mimetypes.guess_extension(content_type) or ".bin"
    if extension == ".jpe":
        extension = ".jpg"
    return f"{employee_id}/{doc_type}/{uuid.uuid4().hex}{extension}"


def create_upload_url(event: dict[str, Any], *, documents_table: Any | None = None,
                      employees_table: Any | None = None, s3: Any | None = None,
                      now: str | None = None) -> dict[str, Any]:
    employee_id = event.get("employee_id")
    if not isinstance(employee_id, str) or not employee_id.strip():
        return _response(400, {"error": {"code": "INVALID_EMPLOYEE", "message": "employee_id is required"}})
    allowed, _ = _authorized(employee_id, event.get("caller"), employees_table)
    if not allowed:
        return _response(403, {"error": {"code": "FORBIDDEN", "message": "Employee access is required"}})
    try:
        doc_type, content_type, file_size = _valid_request(event.get("document"))
    except ValueError as exc:
        return _response(400, {"error": {"code": "INVALID_DOCUMENT", "message": str(exc)}})
    bucket = os.environ.get("DOCUMENTS_BUCKET", "").strip()
    if not bucket:
        return _response(503, {"error": {"code": "SERVICE_NOT_CONFIGURED", "message": "Document storage is not configured"}})
    key = _key(employee_id, doc_type, content_type)
    table = _table("DOCUMENTS_TABLE", documents_table)
    timestamp = now or _now()
    item = {"employee_id": employee_id, "doc_type": doc_type, "s3_key": key, "status": "missing",
            "file_size": file_size, "content_type": content_type, "requested_at": timestamp}
    try:
        table.put_item(
            Item=item,
            ConditionExpression="attribute_not_exists(employee_id) AND attribute_not_exists(doc_type)",
        )
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
            raise
        existing = table.get_item(Key={"employee_id": employee_id, "doc_type": doc_type}, ConsistentRead=True).get("Item")
        if not isinstance(existing, dict) or existing.get("status") not in ("missing", "rejected"):
            return _response(409, {"error": {"code": "DOCUMENT_ALREADY_VERIFIED", "message": "This document type is already uploaded or verified"}})
        # Permit retry after an expired upload URL or rejected file. A fresh
        # random key prevents a stale URL from overwriting the replacement.
        table.update_item(
            Key={"employee_id": employee_id, "doc_type": doc_type},
            UpdateExpression="SET s3_key = :key, #status = :status, file_size = :size, content_type = :type, requested_at = :now REMOVE validated_at",
            ConditionExpression="#status IN (:missing, :rejected)",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={":key": key, ":status": "missing", ":size": file_size, ":type": content_type,
                                       ":now": timestamp, ":missing": "missing", ":rejected": "rejected"},
        )
    try:
        url = _s3(s3).generate_presigned_url(
            "put_object",
            Params={"Bucket": bucket, "Key": key, "ContentType": content_type},
            ExpiresIn=int(os.environ.get("UPLOAD_URL_TTL_SECONDS", "300")),
            HttpMethod="PUT",
        )
    except Exception:
        # No dangling metadata row when the signed URL cannot be issued.
        table.delete_item(Key={"employee_id": employee_id, "doc_type": doc_type})
        logger.exception("Could not create document upload URL.")
        raise
    return _response(201, {"document_type": doc_type, "status": "missing", "upload_url": url,
                           "expires_in_seconds": int(os.environ.get("UPLOAD_URL_TTL_SECONDS", "300")),
                           "required_headers": {"Content-Type": content_type}})


def list_documents(event: dict[str, Any], *, documents_table: Any | None = None,
                   employees_table: Any | None = None) -> dict[str, Any]:
    employee_id = event.get("employee_id")
    if not isinstance(employee_id, str) or not employee_id.strip():
        return _response(400, {"error": {"code": "INVALID_EMPLOYEE", "message": "employee_id is required"}})
    allowed, _ = _authorized(employee_id, event.get("caller"), employees_table)
    if not allowed:
        return _response(403, {"error": {"code": "FORBIDDEN", "message": "Employee access is required"}})
    result = _table("DOCUMENTS_TABLE", documents_table).query(
        KeyConditionExpression=Key("employee_id").eq(employee_id), ConsistentRead=True
    )
    items = list(result.get("Items", []))
    while result.get("LastEvaluatedKey"):
        result = _table("DOCUMENTS_TABLE", documents_table).query(
            KeyConditionExpression=Key("employee_id").eq(employee_id), ConsistentRead=True,
            ExclusiveStartKey=result["LastEvaluatedKey"],
        )
        items.extend(result.get("Items", []))
    by_type = {item.get("doc_type"): item for item in items if item.get("doc_type") in DOCUMENT_TYPES}
    documents = []
    for doc_type in DOCUMENT_TYPES:
        item = by_type.get(doc_type, {})
        documents.append({"document_type": doc_type, "status": item.get("status", "missing"),
                          **({"file_size": item["file_size"]} if "file_size" in item else {}),
                          **({"content_type": item["content_type"]} if "content_type" in item else {}),
                          **({"validated_at": item["validated_at"]} if "validated_at" in item else {})})
    return _response(200, {"employee_id": employee_id, "documents": documents})


def _sniff(content_type: str, prefix: bytes) -> bool:
    if content_type == "application/pdf":
        return prefix.startswith(b"%PDF-")
    if content_type == "image/jpeg":
        return prefix.startswith(b"\xff\xd8\xff")
    if content_type == "image/png":
        return prefix.startswith(b"\x89PNG\r\n\x1a\n")
    return False


def verify_uploaded_object(bucket: str, key: str, *, documents_table: Any | None = None,
                           s3: Any | None = None, sns: Any | None = None,
                           now: str | None = None) -> dict[str, Any]:
    match = re.fullmatch(r"([A-Za-z0-9-]+)/(" + "|".join(DOCUMENT_TYPES) + r")/([0-9a-f]{32}\.(?:pdf|jpg|jpeg|png))", key)
    if not match:
        logger.warning("Ignoring document object with an unexpected key layout.")
        return {"ok": False, "reason": "invalid_key"}
    employee_id, doc_type, _ = match.groups()
    table = _table("DOCUMENTS_TABLE", documents_table)
    result = table.get_item(Key={"employee_id": employee_id, "doc_type": doc_type}, ConsistentRead=True)
    record = result.get("Item")
    if not isinstance(record, dict) or record.get("s3_key") != key:
        logger.warning("Ignoring an unregistered document object.")
        return {"ok": False, "reason": "unregistered_object"}
    # S3 notifications are at-least-once; terminal records make retries idempotent.
    if record.get("status") in ("verified", "rejected"):
        if record.get("status") == "verified" and all_required_verified(employee_id, table=table):
            # Retry a previously failed stage callback on duplicate S3 delivery.
            _complete_document_stage(employee_id)
        return {"ok": record["status"] == "verified", "employee_id": employee_id,
                "document_type": doc_type, "status": record["status"]}
    client = _s3(s3)
    head = client.head_object(Bucket=bucket, Key=key)
    actual_size = int(head.get("ContentLength", 0))
    actual_type = head.get("ContentType", "")
    expected_size = int(record.get("file_size", -1))
    expected_type = record.get("content_type", "")
    obj = client.get_object(Bucket=bucket, Key=key, Range="bytes=0-15")
    prefix = obj["Body"].read(16)
    valid = (0 < actual_size <= MAX_BYTES and actual_size == expected_size and
             actual_type == expected_type and _sniff(actual_type, prefix))
    timestamp = now or _now()
    if valid:
        table.update_item(
            Key={"employee_id": employee_id, "doc_type": doc_type},
            UpdateExpression="SET #status = :status, validated_at = :now",
            ConditionExpression="s3_key = :key AND #status = :missing",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={":status": "verified", ":missing": "missing", ":now": timestamp, ":key": key},
        )
        outcome = "verified"
    else:
        table.update_item(
            Key={"employee_id": employee_id, "doc_type": doc_type},
            UpdateExpression="SET #status = :status, validated_at = :now",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={":status": "rejected", ":now": timestamp},
        )
        try:
            client.delete_object(Bucket=bucket, Key=key, **({"VersionId": head["VersionId"]} if head.get("VersionId") else {}))
        except ClientError:
            logger.error("Could not remove rejected document object.")
        topic = os.environ.get("HR_NOTIFICATION_TOPIC_ARN", "")
        if topic:
            (sns if sns is not None else boto3.client("sns")).publish(
                TopicArn=topic, Subject="HRMS document rejected",
                Message=json.dumps({"employee_id": employee_id, "document_type": doc_type, "reason": "file_validation_failed"}),
            )
        outcome = "rejected"
    if outcome == "verified" and all_required_verified(employee_id, table=table):
        _complete_document_stage(employee_id)
    return {"ok": outcome == "verified", "employee_id": employee_id, "document_type": doc_type, "status": outcome}


def all_required_verified(employee_id: str, *, table: Any) -> bool:
    result = table.query(KeyConditionExpression=Key("employee_id").eq(employee_id), ConsistentRead=True)
    items = list(result.get("Items", []))
    while result.get("LastEvaluatedKey"):
        result = table.query(KeyConditionExpression=Key("employee_id").eq(employee_id), ConsistentRead=True,
                             ExclusiveStartKey=result["LastEvaluatedKey"])
        items.extend(result.get("Items", []))
    states = {item.get("doc_type"): item.get("status") for item in items}
    return all(states.get(doc_type) == "verified" for doc_type in DOCUMENT_TYPES)


def _complete_document_stage(employee_id: str) -> None:
    function_name = os.environ.get("STAGES_FUNCTION_NAME", "").strip()
    if not function_name:
        logger.warning("All documents verified but stage handler is not configured.")
        return
    try:
        result = boto3.client("lambda").invoke(
            FunctionName=function_name, InvocationType="RequestResponse",
            Payload=json.dumps({"action": "complete_stage", "employee_id": employee_id,
                                "stage": "document_collection", "source": "document_validation"}).encode("utf-8"),
        )
        if result.get("FunctionError"):
            logger.error("Document stage completion invocation failed.")
            return
        payload = result.get("Payload")
        raw = payload.read() if hasattr(payload, "read") else payload
        decoded = json.loads(raw or b"{}")
        if isinstance(decoded, dict) and isinstance(decoded.get("statusCode"), int) and decoded["statusCode"] >= 400:
            logger.error("Document collection callback was rejected with HTTP status %s.", decoded["statusCode"])
    except ClientError:
        logger.exception("Document stage completion could not be submitted.")


def lambda_handler(event: dict[str, Any], context: Any) -> Any:
    if not isinstance(event, dict):
        return _response(400, {"error": {"code": "INVALID_EVENT", "message": "Event must be an object"}})
    # S3 notifications are handled separately from API adapter requests.
    if isinstance(event.get("Records"), list):
        results = []
        for record in event["Records"]:
            if record.get("eventSource") != "aws:s3":
                continue
            bucket = record.get("s3", {}).get("bucket", {}).get("name", "")
            key = unquote_plus(record.get("s3", {}).get("object", {}).get("key", ""))
            if bucket and key:
                results.append(verify_uploaded_object(bucket, key))
        return {"ok": True, "processed": len(results), "results": results}
    action = event.get("action")
    try:
        if action == "create_upload_url":
            return create_upload_url(event)
        if action == "list_documents":
            return list_documents(event)
        return _response(400, {"error": {"code": "INVALID_ACTION", "message": "Unsupported document action"}})
    except ClientError:
        logger.exception("Document service dependency failed.")
        return _response(502, {"error": {"code": "DEPENDENCY_FAILURE", "message": "Document service could not complete the request"}})
    except RuntimeError:
        logger.exception("Document service is misconfigured.")
        return _response(503, {"error": {"code": "SERVICE_NOT_CONFIGURED", "message": "Document service is not configured"}})
