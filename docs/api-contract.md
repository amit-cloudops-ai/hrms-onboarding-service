# API contract

Region: us-east-1. All routes sit behind API Gateway with a Cognito authorizer.

| Method and route | Purpose | Who can call |
|---|---|---|
| POST /employees | Register a new hire and start onboarding | HR admin |
| GET /employees | List all hires with stage status | HR admin |
| GET /employees/{employee_id} | One employee profile | HR admin, that employee |
| GET /employees/{employee_id}/progress | Progress of all four stages | HR admin, that employee |
| POST /employees/{employee_id}/documents/upload-url | One-time upload link for a document type | That employee |
| GET /employees/{employee_id}/documents | Status of each required document | HR admin, that employee |
| POST /employees/{employee_id}/policies/sign | Record policy acceptance | That employee |
| POST /employees/{employee_id}/stages/{stage}/complete | Manually mark a stage done | HR admin |

Stage names: `document_collection`, `it_provisioning`, `policy_signoff`, `manager_intro`
Stage status: `pending`, `in_progress`, `complete`
Document types: `id_proof`, `degree_certificate`, `signed_offer_letter`
Uploads: PDF, JPG, PNG; max 5 MB.

## Document upload URL contract (WP3)

### Public HTTP request

`POST /employees/{employee_id}/documents/upload-url`

This route requires a valid Cognito-authenticated employee session. The employee may request an upload URL only for their own employee record. API Gateway validates the JWT, and WP5 must compare the token's immutable `sub` claim with the employee record's stored Cognito subject before invoking WP3.

Headers:

```http
Authorization: Bearer <Cognito ID token>
Content-Type: application/json
```

Request body — exactly these three fields:

```json
{
  "document_type": "id_proof",
  "content_type": "application/pdf",
  "file_size": 12345
}
```

Field rules:

| Field | Type | Required | Allowed values / validation |
|---|---|---:|---|
| `document_type` | string | Yes | `id_proof`, `degree_certificate`, `signed_offer_letter` |
| `content_type` | string | Yes | `application/pdf`, `image/jpeg`, `image/png` |
| `file_size` | integer | Yes | 1 through 5,242,880 bytes (5 MiB); reject booleans, strings, zero, negative values and larger files |

Do not require or accept an S3 bucket name, S3 object key, Cognito subject, caller/admin flag, filename, or `action` from the public request body. The authenticated API layer supplies trusted identity/context and the internal action when it invokes the WP3 Lambda.

### Successful response

HTTP status: `201 Created`

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

The URL is a short-lived S3 **PUT** URL. The client must upload the raw file bytes directly to it and send the exact `Content-Type` value returned in `required_headers`. Do not wrap the file in JSON or send it to the API endpoint a second time.

Example browser request after receiving the response:

```http
PUT <upload_url>
Content-Type: application/pdf

<raw file bytes>
```

The default URL lifetime is 300 seconds (5 minutes). The service may be configured with `UPLOAD_URL_TTL_SECONDS`; the response must report the actual lifetime used to sign the URL. The API response must not expose the internal S3 object key or bucket name.

The initial document status is `missing` while the presigned URL has been issued and the S3 upload/validation event is still pending. After S3 receives the object, WP3 validates the actual object size, actual content type and file signature. The eventual status is `verified` or `rejected`; clients read it through the document-status endpoint.

### Error response envelope

All errors use this JSON structure:

```json
{
  "error": {
    "code": "INVALID_DOCUMENT",
    "message": "Only PDF, JPEG, and PNG files are accepted"
  }
}
```

Expected status/code pairs:

| HTTP status | Error code | Meaning |
|---:|---|---|
| 400 | `INVALID_EMPLOYEE` | Missing/invalid employee ID in the internal handler request |
| 400 | `INVALID_DOCUMENT` | Missing/invalid document type, content type or file size |
| 400 | `INVALID_REQUEST` | Malformed public JSON request body |
| 403 | `FORBIDDEN` | Caller is not the employee that owns the record |
| 404 | `NOT_FOUND` | Employee record does not exist (API layer) |
| 409 | `DOCUMENT_ALREADY_VERIFIED` | An existing document record is in a non-retryable state. In the current WP3 handler, a verified document cannot be uploaded again through this endpoint |
| 502 | `DEPENDENCY_FAILURE` | WP3 Lambda invocation failed |
| 502 | `INVALID_DEPENDENCY_RESPONSE` | WP3 returned a malformed response |
| 503 | `SERVICE_NOT_CONFIGURED` | Documents adapter or private S3 bucket configuration is missing |

If a prior upload URL expired before an object was uploaded, or the prior file was rejected, WP3 may issue a new URL with a fresh random object key. The current handler treats existing missing and rejected records as retryable, and an existing verified record as non-retryable (409). A renewed URL replaces the registered object key, so an object uploaded later through an older URL is treated as unregistered. Do not reuse an old presigned URL or object key.

### Internal WP5 → WP3 Lambda event (not the public API body)

WP5 invokes the documents Lambda synchronously (`RequestResponse`) and enriches the event with trusted values from the verified JWT:

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

WP3's Lambda handler should not trust client-supplied identity fields. The public client never sends `action`, `caller`, `sub`, or `is_admin`; WP5 supplies these. The WP3 handler returns an API Gateway-style envelope with `statusCode`, `headers`, and JSON `body`; WP5 forwards that envelope to the HTTP caller.

### DynamoDB metadata (internal only)

Use the existing `hrms-dev-documents` table, with partition key `employee_id` and sort key `doc_type`. Store at least:

- `employee_id`
- `doc_type`
- `s3_key` (internal; never return it to the browser)
- `status`
- `file_size`
- `content_type`
- `requested_at`
- `validated_at` after verification/rejection

The upload URL request must not mark the document as verified. Metadata is updated only after the S3 event validator checks the uploaded object.
