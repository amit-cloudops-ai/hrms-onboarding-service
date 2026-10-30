# WP3 — Document collection service

## Responsibility

WP3 owns employee document upload URLs, private S3 object storage, file validation, per-document status, retry behavior and HR notification for rejected files. It is a Python 3.12 AWS Lambda service using `boto3`, packaged with AWS SAM. Do not add FastAPI/Flask or expose this Lambda as a public HTTP endpoint. WP5 invokes it after authenticating and authorizing the employee.

## Public API contract

`POST /employees/{employee_id}/documents/upload-url`

The public route is protected by the Cognito JWT authorizer and is employee-self-only. WP5 verifies that the JWT `sub` matches the employee record before it invokes WP3.

Request body:

```json
{
  "document_type": "id_proof",
  "content_type": "application/pdf",
  "file_size": 12345
}
```

Required fields and validation:

| Field | Type | Allowed values |
|---|---|---|
| `document_type` | string | `id_proof`, `degree_certificate`, `signed_offer_letter` |
| `content_type` | string | `application/pdf`, `image/jpeg`, `image/png` |
| `file_size` | integer | 1–5,242,880 bytes (5 MiB) |

Do not require `filename`, `employee_id`, `caller`, `sub`, `is_admin`, `action`, bucket name or S3 key in the public body. The employee ID is in the URL path. WP5 passes trusted identity information and the internal action to the documents Lambda.

Success response: HTTP `201 Created`

```json
{
  "document_type": "id_proof",
  "status": "missing",
  "upload_url": "https://<presigned-s3-put-url>",
  "expires_in_seconds": 300,
  "required_headers": {
    "Content-Type": "application/pdf"
  }
}
```

The URL is for HTTP PUT directly to S3. Upload raw file bytes and send the exact `Content-Type` header returned. The default lifetime is 300 seconds; return the configured TTL actually used. Never include the S3 key or bucket name in the response.

Errors use `{"error":{"code":"...","message":"..."}}`. Relevant conditions include 400 `INVALID_DOCUMENT`, 403 `FORBIDDEN`, 409 `DOCUMENT_ALREADY_VERIFIED`, 502 downstream integration failures and 503 `SERVICE_NOT_CONFIGURED`. See the authoritative examples/table in `docs/api-contract.md`.

## Internal WP5 → WP3 event

WP5 invokes the Lambda synchronously with an event similar to:

```json
{
  "action": "create_upload_url",
  "employee_id": "<employee-uuid>",
  "caller": {
    "sub": "<verified-cognito-sub>",
    "is_admin": false
  },
  "document": {
    "document_type": "id_proof",
    "content_type": "application/pdf",
    "file_size": 12345
  }
}
```

Those `action` and `caller` fields are internal adapter fields, not part of the browser request. Validate caller ownership against the canonical employee record using Cognito `sub`; do not authorize based on email.

For document listing, WP5 invokes the same function with `action: "list_documents"`, `employee_id` and trusted `caller`.

## Document types and statuses

Required types:

- `id_proof`
- `degree_certificate`
- `signed_offer_letter`

Status lifecycle:

- `missing`: no accepted document object yet / upload awaiting validation
- `verified`: actual S3 object passed validation
- `rejected`: size, content type or file signature did not pass validation

`GET /employees/{employee_id}/documents` returns all three document types, including types with no record yet:

```json
{
  "employee_id": "<employee-uuid>",
  "documents": [
    {"document_type": "id_proof", "status": "missing"},
    {"document_type": "degree_certificate", "status": "verified", "file_size": 12345, "content_type": "application/pdf", "validated_at": "2026-10-30T12:00:00+00:00"},
    {"document_type": "signed_offer_letter", "status": "rejected"}
  ]
}
```

The `s3_key`, bucket name, presigned URL and task token are never returned by the status endpoint.

## Upload and verification flow

1. Validate the internal event, employee ID, caller, document type, content type and file size.
2. Check the employee record and confirm `caller.sub == employee.cognito_sub` (or trusted HR admin for status listing only).
3. Generate a random object key under `{employee_id}/{document_type}/`.
4. Write upload metadata to `hrms-dev-documents` (PK `employee_id`, SK `doc_type`) with `status: missing`.
5. Generate a short-lived presigned S3 PUT URL that binds the bucket, object key and exact `Content-Type`.
6. Return the 201 response above. If URL signing fails, remove the metadata row created for that attempt and fail safely.
7. S3 `ObjectCreated` invokes the validator. Compare actual object size/content type to metadata and inspect PDF/JPEG/PNG magic bytes. Do not trust only the browser's declared MIME type or filename.
8. If valid, update status to `verified`. If invalid, set `rejected`, delete the invalid object where possible, and publish an HR SNS notification.
9. Permit a safe retry after an expired unused URL or rejected upload by generating a new random key. Do not allow a second upload URL for an already uploaded/verified document.
10. Ask WP4 to resume `document_collection` only when all three required documents are verified.

The browser must send the exact content type in the `required_headers` object when performing the PUT. S3 CORS must allow the exact frontend origin, method PUT and Content-Type header.

## DynamoDB metadata

Existing table: `hrms-dev-documents`

- Partition key: `employee_id`
- Sort key: `doc_type`
- Attributes: `s3_key`, `status`, `file_size`, `content_type`, `requested_at`, `validated_at`

The public contract uses `document_type`; the table's sort-key attribute is `doc_type`. Do not accidentally use one name for both layers.

## Local dependencies and tests

From the repository root, in a Python 3.12 virtual environment:

```bash
python -m pip install --upgrade boto3
python -m unittest services.documents.test_handler -v
sam validate --lint --template-file services/documents/template.yaml
```

Tests must mock DynamoDB, S3, SNS and Lambda invocations. Do not deploy or access the AWS account for unit tests. Include success and failure cases: valid presigned URL, invalid file metadata, wrong employee subject, duplicate upload, retry after rejection/expiry, invalid magic bytes, S3 event verification and HR notification.

## Infrastructure

`template.yaml` defines the private encrypted/versioned S3 bucket, S3 object-created trigger, Lambda function, SNS notification topic and IAM permissions. It expects existing employees/documents tables and WP4's stage-handler Lambda. Deploy WP4 first in the later approved AWS integration phase. Set `UploadAllowedOrigin` to the exact employee portal origin; the local default is not the production origin.

No AWS deployment is part of WP3 local implementation. Never commit AWS credentials, employee documents, JWTs, presigned URLs or Step Functions task tokens.
