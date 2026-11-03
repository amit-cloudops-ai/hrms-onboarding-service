"""WP3 - Employee document collection service."""

import json
import logging
import os
import uuid
from datetime import datetime, timezone

import boto3
from validator import validate_document
from botocore.exceptions import ClientError, BotoCoreError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Configuration from Lambda environment variables
EMPLOYEES_TABLE_NAME = os.environ.get("EMPLOYEES_TABLE")
DOCUMENTS_TABLE_NAME = os.environ.get("DOCUMENTS_TABLE")
DOCUMENTS_BUCKET_NAME = os.environ.get("DOCUMENTS_BUCKET")
SNS_TOPIC_ARN = os.environ.get("SNS_TOPIC_ARN")
WORKFLOW_FUNCTION_NAME = os.environ.get("WORKFLOW_FUNCTION_NAME")
UPLOAD_URL_TTL = int(os.environ.get("UPLOAD_URL_TTL_SECONDS", "300"))

# AWS clients and resources
dynamodb = boto3.resource(
    "dynamodb",
    region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
)

s3_client = boto3.client(
    "s3",
    region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
)
sns_client = boto3.client(
    "sns",
    region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
)
employees_table = (
    dynamodb.Table(EMPLOYEES_TABLE_NAME)
    if EMPLOYEES_TABLE_NAME else None
)

documents_table = (
    dynamodb.Table(DOCUMENTS_TABLE_NAME)
    if DOCUMENTS_TABLE_NAME else None
)

# Allowed document types
ALLOWED_DOCUMENT_TYPES = {
    "id_proof",
    "degree_certificate",
    "signed_offer_letter",
}

# Allowed content types
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
}

MAX_FILE_SIZE = 5 * 1024 * 1024


def api_response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def validate_upload_input(document):
    """Validate the document details received from WP5."""

    if not isinstance(document, dict):
        raise ValueError("Invalid document details")

    document_type = document.get("document_type")
    content_type = document.get("content_type")
    file_size = document.get("file_size")

    if document_type not in ALLOWED_DOCUMENT_TYPES:
        raise ValueError("Unsupported document type")

    if content_type not in ALLOWED_CONTENT_TYPES:
        raise ValueError("Unsupported content type")

    if type(file_size) is not int or not 1 <= file_size <= MAX_FILE_SIZE:
        raise ValueError("File size must be between 1 byte and 5 MB")

    return True
def validate_employee_access(employee_id, caller, allow_admin=False):
    """Verify the trusted Cognito caller against the employee record."""

    if not isinstance(caller, dict):
        raise PermissionError("Unauthorized caller")

    caller_sub = caller.get("sub")

    if not isinstance(caller_sub, str) or not caller_sub.strip():
        raise PermissionError("Missing Cognito subject")

    if employees_table is None:
        raise RuntimeError("Employees table is not configured")

    response = employees_table.get_item(
        Key={"employee_id": employee_id}
    )

    employee = response.get("Item")

    if not employee:
        raise ValueError("Employee record not found")

    if allow_admin and caller.get("is_admin") is True:
        return True

    if employee.get("cognito_sub") != caller_sub:
        raise PermissionError("Employee access denied")

    return True

def create_upload_url(employee_id, document):
    """Create a fresh presigned S3 upload URL for an employee."""

    validate_upload_input(document)

    if not EMPLOYEES_TABLE_NAME or not DOCUMENTS_TABLE_NAME:
        raise RuntimeError("DynamoDB tables are not configured")

    if not DOCUMENTS_BUCKET_NAME:
        raise RuntimeError("Documents S3 bucket is not configured")

    if not 1 <= UPLOAD_URL_TTL <= 604800:
        raise RuntimeError("Invalid upload URL expiry configuration")

    document_type = document["document_type"]
    content_type = document["content_type"]
    file_size = document["file_size"]

    # Generate a unique key for this upload attempt.
    extension = {
        "application/pdf": ".pdf",
        "image/jpeg": ".jpg",
        "image/png": ".png",
    }[content_type]

    s3_key = (
        f"{employee_id}/{document_type}/{uuid.uuid4().hex}{extension}"
    )

    requested_at = datetime.now(timezone.utc).isoformat()

    # Save the new attempt, but never overwrite a verified document.
    try:
        documents_table.put_item(
            Item={
                "employee_id": employee_id,
                "doc_type": document_type,
                "s3_key": s3_key,
                "status": "missing",
                "file_size": file_size,
                "content_type": content_type,
                "requested_at": requested_at,
            },
            ConditionExpression=(
                "attribute_not_exists(#status) "
                "OR #status IN (:missing, :rejected)"
            ),
            ExpressionAttributeNames={
                "#status": "status"
            },
            ExpressionAttributeValues={
                ":missing": "missing",
                ":rejected": "rejected",
            },
        )

    except ClientError as error:
        error_code = error.response["Error"]["Code"]

        if error_code == "ConditionalCheckFailedException":
            return api_response(409, {
                "error": {
                    "code": "DOCUMENT_ALREADY_VERIFIED",
                    "message": "This document cannot be uploaded again."
                }
            })

        logger.exception("Failed to save document metadata")
        raise

    # Generate a URL that permits only the specified S3 PUT operation.
    try:
        upload_url = s3_client.generate_presigned_url(
            ClientMethod="put_object",
            Params={
                "Bucket": DOCUMENTS_BUCKET_NAME,
                "Key": s3_key,
                "ContentType": content_type,
            },
            ExpiresIn=UPLOAD_URL_TTL,
        )

    except (ClientError, BotoCoreError):
        logger.exception("Failed to generate upload URL")

        # Remove only this attempt's metadata.
        # Do not accidentally delete a newer concurrent attempt.
        try:
            documents_table.delete_item(
                Key={
                    "employee_id": employee_id,
                    "doc_type": document_type,
                },
                ConditionExpression="#s3_key = :s3_key",
                ExpressionAttributeNames={
                    "#s3_key": "s3_key"
                },
                ExpressionAttributeValues={
                    ":s3_key": s3_key
                },
            )
        except ClientError:
            logger.exception("Could not clean up failed upload attempt")

        raise

    return api_response(201, {
            "document_type": document_type,
            "status": "missing",
            "upload_url": upload_url,
            "expires_in_seconds": UPLOAD_URL_TTL,
            "required_headers": {
                "Content-Type": content_type
            }
        })
def list_documents(employee_id):
    """Return the status of all required employee documents."""

    if documents_table is None:
        raise RuntimeError("Documents table is not configured")

    required_documents = [
        "id_proof",
        "degree_certificate",
        "signed_offer_letter",
    ]

    document_list = []

    for document_type in required_documents:
        response = documents_table.get_item(
            Key={
                "employee_id": employee_id,
                "doc_type": document_type,
            }
        )

        item = response.get("Item")

        if not item:
            document_list.append({
                "document_type": document_type,
                "status": "missing",
            })
            continue

        document_info = {
            "document_type": document_type,
            "status": item.get("status", "missing"),
        }

        # Include file details only when available.
        for field in ("file_size", "content_type", "validated_at"):
            if field in item:
                document_info[field] = item[field]

        document_list.append(document_info)

    return {
        "employee_id": employee_id,
        "documents": document_list,
    }
def lambda_handler(event, context):
    """Main entry point for the WP3 document service."""

    # S3 invokes this Lambda asynchronously; failures must reach Lambda so it
    # can retry. Keep API-style error mapping for synchronous WP5 requests.
    if isinstance(event, dict):
        records = event.get("Records", [])

        if (
            isinstance(records, list)
            and records
            and isinstance(records[0], dict)
            and records[0].get("eventSource") == "aws:s3"
        ):
            return process_s3_upload(event)

    try:
        if not isinstance(event, dict):
            raise ValueError("Invalid request")

        action = event.get("action")
        employee_id = event.get("employee_id")
        caller = event.get("caller")

        if not isinstance(employee_id, str) or not employee_id.strip():
            raise ValueError("Invalid employee ID")

        if action == "create_upload_url":
            document = event.get("document")

            validate_employee_access(employee_id, caller)

            return create_upload_url(employee_id, document)

        elif action == "list_documents":
            validate_employee_access(
                employee_id,
                caller,
                allow_admin=True,
            )

            return api_response(200, list_documents(employee_id))

        else:
            raise ValueError("Unsupported action")
    except ValueError as error:
        message = str(error)

        if "employee ID" in message:
            error_code = "INVALID_EMPLOYEE"
        elif "Unsupported action" in message:
            error_code = "INVALID_REQUEST"
        else:
            error_code = "INVALID_DOCUMENT"

        return api_response(400, {
            "error": {
                "code": error_code,
                "message": message,
            },
        })

    except PermissionError as error:
        return api_response(403, {
            "error": {
                "code": "FORBIDDEN",
                "message": str(error),
            },
        })

    except RuntimeError:
        logger.exception("WP3 service configuration error")
        return api_response(503, {
            "error": {
                "code": "SERVICE_NOT_CONFIGURED",
                "message": "Document service is not configured.",
            },
        })

    except Exception:
        logger.exception("Unexpected WP3 service error")
        return api_response(502, {
            "error": {
                "code": "DOWNSTREAM_ERROR",
                "message": "Unable to process the document request.",
            },
        })
def extract_s3_upload_details(event):
    """Extract bucket and object key from an S3 event."""

    if not isinstance(event, dict):
        raise ValueError("Invalid S3 event")

    records = event.get("Records", [])

    if not records:
        raise ValueError("No S3 records found")

    record = records[0]

    if record.get("eventSource") != "aws:s3":
        raise ValueError("Unsupported event source")

    s3_details = record.get("s3", {})
    bucket = s3_details.get("bucket", {}).get("name")
    object_key = s3_details.get("object", {}).get("key")

    if not bucket or not object_key:
        raise ValueError("Missing S3 bucket or object key")

    from urllib.parse import unquote_plus

    return bucket, unquote_plus(object_key)
def extract_document_identity(object_key):
    """Extract employee ID and document type from an S3 object key."""

    parts = object_key.split("/")

    if len(parts) != 3:
        raise ValueError("Invalid document object key")

    employee_id, document_type, filename = parts

    if not employee_id or not filename:
        raise ValueError("Invalid document object key")

    if document_type not in ALLOWED_DOCUMENT_TYPES:
        raise ValueError("Unsupported document type")

    return employee_id, document_type
def validate_s3_object(bucket, object_key, expected_file_size, expected_content_type):
    """Download and validate the uploaded S3 document."""

    response = s3_client.get_object(
        Bucket=bucket,
        Key=object_key,
    )

    content_length = response.get("ContentLength")

    if type(content_length) is not int or not 1 <= content_length <= MAX_FILE_SIZE:
        raise ValueError("Uploaded file size is outside allowed limits")

    if content_length != expected_file_size:
        raise ValueError("Uploaded file size does not match")

    file_content = response["Body"].read()

    actual_file_size = len(file_content)
    actual_content_type = response.get("ContentType")

    if actual_file_size != content_length:
        raise ValueError("Uploaded file size does not match")

    if actual_content_type != expected_content_type:
        raise ValueError("Uploaded content type does not match")

    extension = {
        "application/pdf": ".pdf",
        "image/jpeg": ".jpg",
        "image/png": ".png",
    }.get(expected_content_type)

    if not extension:
        raise ValueError("Unsupported content type")

    filename = object_key.rsplit("/", 1)[-1]

    # Reuse our existing document validator.
    validate_document(
        doc_type=object_key.split("/")[1],
        filename=filename,
        content_type=actual_content_type,
        file_size=actual_file_size,
        file_content=file_content,
    )

    return True

def mark_document_verified(employee_id, document_type, object_key):
    """Mark a document verified only if this is the latest upload."""

    try:
        documents_table.update_item(
            Key={
                "employee_id": employee_id,
                "doc_type": document_type,
            },
            UpdateExpression="SET #status = :verified, validated_at = :time",
            ConditionExpression="#s3_key = :key AND #status = :missing",
            ExpressionAttributeNames={
                "#status": "status",
                "#s3_key": "s3_key",
            },
            ExpressionAttributeValues={
                ":verified": "verified",
                ":missing": "missing",
                ":key": object_key,
                ":time": datetime.now(timezone.utc).isoformat(),
            },
        )

        return True

    except ClientError as error:
        error_code = error.response["Error"]["Code"]

        if error_code == "ConditionalCheckFailedException":
            logger.info("Ignoring stale or duplicate S3 upload event")
            return False

        raise
def mark_document_rejected(employee_id, document_type, object_key):
    """Mark a document rejected only if this is the latest upload."""

    try:
        documents_table.update_item(
            Key={
                "employee_id": employee_id,
                "doc_type": document_type,
            },
            UpdateExpression="SET #status = :rejected, validated_at = :time",
            ConditionExpression="#s3_key = :key AND #status = :missing",
            ExpressionAttributeNames={
                "#status": "status",
                "#s3_key": "s3_key",
            },
            ExpressionAttributeValues={
                ":rejected": "rejected",
                ":missing": "missing",
                ":key": object_key,
                ":time": datetime.now(timezone.utc).isoformat(),
            },
        )

        return True

    except ClientError as error:
        error_code = error.response["Error"]["Code"]

        if error_code == "ConditionalCheckFailedException":
            logger.info("Ignoring stale or duplicate rejected upload event")
            return False

        raise
def notify_hr_document_rejected(employee_id, document_type):
    """Notify HR when an employee document is rejected."""

    topic_arn = os.environ.get("HR_NOTIFICATION_TOPIC_ARN") or SNS_TOPIC_ARN

    if not topic_arn:
        raise RuntimeError("SNS topic ARN is not configured")

    try:
        sns_client.publish(
            TopicArn=topic_arn,
            Subject="Employee document rejected",
            Message=(
                f"Document rejected for employee: {employee_id}\n"
                f"Document type: {document_type}\n"
                "Please review the uploaded document."
            ),
        )
        return True

    except (ClientError, BotoCoreError):
        logger.exception("Failed to notify HR")
        raise


def all_required_documents_verified(employee_id):
    """Return true only when all mandatory document records are verified."""
    if documents_table is None:
        raise RuntimeError("Documents table is not configured")
    for document_type in ("id_proof", "degree_certificate", "signed_offer_letter"):
        response = documents_table.get_item(Key={"employee_id": employee_id, "doc_type": document_type})
        item = response.get("Item")
        if not item or item.get("status") != "verified":
            return False
    return True


def resume_document_collection(employee_id):
    """Ask WP2 to resume the callback; WP3 never reads or handles task tokens."""
    function_name = (WORKFLOW_FUNCTION_NAME or os.environ.get("WORKFLOW_FUNCTION_NAME", "")).strip()
    if not function_name:
        raise RuntimeError("WORKFLOW_FUNCTION_NAME is not configured")
    client = boto3.client("lambda")
    response = client.invoke(
        FunctionName=function_name,
        InvocationType="RequestResponse",
        Payload=json.dumps({"action": "resume_document_collection", "employee_id": employee_id}).encode("utf-8"),
    )
    if response.get("FunctionError"):
        raise RuntimeError("WP2 document callback invocation failed")
    stream = response.get("Payload")
    raw = stream.read() if hasattr(stream, "read") else stream
    try:
        result = json.loads(raw or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError, TypeError) as exc:
        raise RuntimeError("WP2 returned an invalid callback response") from exc
    if not isinstance(result, dict) or result.get("ok") is not True:
        raise RuntimeError("WP2 did not accept the document completion signal")
    return result


def process_s3_upload(event):
    """Validate an upload idempotently and signal WP2 after all required docs pass."""
    bucket, object_key = extract_s3_upload_details(event)
    if bucket != DOCUMENTS_BUCKET_NAME:
        raise ValueError("Unexpected S3 bucket")
    employee_id, document_type = extract_document_identity(object_key)
    response = documents_table.get_item(Key={"employee_id": employee_id, "doc_type": document_type})
    item = response.get("Item")
    if not item or item.get("s3_key") != object_key:
        logger.info("Ignoring stale or unknown upload event")
        return False

    status = item.get("status")
    if status == "verified":
        # A prior attempt may have persisted verification but failed before
        # notifying WP2. Replayed S3 events safely retry the callback signal.
        if all_required_documents_verified(employee_id):
            resume_document_collection(employee_id)
        return True
    if status != "missing":
        logger.info("Ignoring stale or duplicate upload event")
        return False

    try:
        validate_s3_object(
            bucket=bucket,
            object_key=object_key,
            expected_file_size=item["file_size"],
            expected_content_type=item["content_type"],
        )
    except ValueError:
        logger.warning("Document validation failed: %s", object_key)
        updated = mark_document_rejected(employee_id, document_type, object_key)
        if not updated:
            return False
        try:
            s3_client.delete_object(Bucket=bucket, Key=object_key)
        except (ClientError, BotoCoreError):
            logger.exception("Could not delete rejected document")
            raise
        notify_hr_document_rejected(employee_id, document_type)
        return True

    updated = mark_document_verified(employee_id, document_type, object_key)
    if not updated:
        latest = documents_table.get_item(
            Key={"employee_id": employee_id, "doc_type": document_type},
            ConsistentRead=True,
        ).get("Item", {})
        if latest.get("s3_key") != object_key or latest.get("status") != "verified":
            return False
    if all_required_documents_verified(employee_id):
        resume_document_collection(employee_id)
    return True
