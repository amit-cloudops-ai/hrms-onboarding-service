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

## Request details for WP3/WP4 integration

### Request an upload URL

`POST /employees/{employee_id}/documents/upload-url`

```json
{
  "document_type": "id_proof",
  "content_type": "application/pdf",
  "file_size": 12345
}
```

The response contains `upload_url`, `expires_in_seconds`, and the required `Content-Type` header. Upload the file directly to that URL using HTTP PUT. The URL is short-lived and scoped to one private object. The service validates the actual object size, content type, and file signature after upload.

### Read document status

`GET /employees/{employee_id}/documents` returns all three required document types. Missing records are represented as `missing`; accepted file signatures become `verified`; invalid uploads become `rejected`.

### Accept a policy

`POST /employees/{employee_id}/policies/sign`

```json
{
  "policy_id": "acceptable-use",
  "policy_version": "v1",
  "accepted": true
}
```

The default required policy IDs are `acceptable-use`, `privacy`, and `security`. Policy acceptance is tied to the authenticated Cognito subject and stored with a timestamp and version. The `policy_signoff` stage resumes only after all configured required policies have been accepted.

### Stage completion

`POST /employees/{employee_id}/stages/{stage}/complete` remains HR-admin-only. `manager_intro` completion is routed through WP4; other stages use WP2's callback helper. The document-collection stage is automatically submitted by WP3 only when all three required documents are verified.
