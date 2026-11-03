# WP3 / WP4 integration contract

**Status:** Integration handoff for local implementation; no AWS deployment.
**Region:** us-east-1
**Shared branch:** team-dev
**Source contracts:** docs/api-contract.md, docs/data-model.md, docs/adr/0001-step-functions-callback-pattern.md, docs/adr/0002-simulated-and-real-adapters.md

This document makes the existing decisions explicit for WP3 (documents) and WP4 (stage business handlers). It does not claim that the end-to-end workflow is already wired.

## Ownership

- WP2 owns Step Functions sequencing, callback task-token lifecycle, timeout/reminder handling, and all writes to canonical lifecycle fields in `hrms-dev-onboarding-stages`.
- WP3 owns document upload URL generation, S3 object validation, document metadata/status in `hrms-dev-documents`, and rejection notification.
- WP4 owns synchronous IT provisioning and manager-introduction adapters, plus the authenticated policy-acceptance record. WP4 does not own the canonical WP2 stage lifecycle.
- WP5 owns authenticated API routes, employee/HR authorization, document/stage adapter invocation, and the server-side callback submission boundary.

## WP4 synchronous business-handler contract

WP4 is invoked as a synchronous Lambda business adapter. It must not receive or store a Step Functions task token.

Request:

```json
{
  "action": "execute_stage",
  "employee_id": "<employee-uuid>",
  "stage": "it_provisioning",
  "mode": "simulated",
  "correlation_id": "<stable-execution-or-stage-correlation-id>"
}
```

Allowed stages for WP4:

- `it_provisioning`
- `manager_intro`

Allowed modes: `simulated`, `real`. The deployment configuration is `MODE=simulated|real`; an explicit per-invocation mode may be used by offline tests only if the handler validates it against the deployment mode or the project owner approves that override. Do not let an untrusted public client choose real/simulated mode.

Success response:

```json
{
  "ok": true,
  "employee_id": "<employee-uuid>",
  "stage": "it_provisioning",
  "status": "complete",
  "mode": "simulated",
  "result": {
    "equipment_status": "assigned",
    "account_status": "created"
  }
}
```

Return a JSON object. Do not return task tokens, credentials, provider secrets, S3 object keys, or presigned URLs. Fail with a clear, non-sensitive error when configuration or a provider is unavailable. Real mode must never silently fall back to simulated mode.

The exact `result` fields may be stage-specific, but must be documented and tested. Business completion must be idempotent for the same `correlation_id`.

## Callback pattern and completion ownership

ADR 0001 selects Step Functions callback tasks because stages can wait for human action. The existing WP2 state machine uses `arn:aws:states:::lambda:invoke.waitForTaskToken` and invokes the WP2 workflow support Lambda with `action=start_stage`, `employee_id`, `stage`, and `taskToken`.

WP2 stores the token privately in `hrms-dev-onboarding-stages`; tokens must never be exposed to WP4 responses, browser clients, logs, notifications, or test fixtures committed to the repository.

The state machine waits for an authorized backend caller to submit `SendTaskSuccess`. WP5/WP2 owns that trusted callback path. After the callback is accepted, the state machine's `mark_stage_complete` action updates the canonical status to `complete`, records `completed_at`, and removes `task_token`.

WP4 returns business-operation results only. It must not write `status`, `started_at`, `completed_at`, `reminder_count`, or `task_token` in `hrms-dev-onboarding-stages`. If WP4 needs additional operational data, propose a separate attribute/table and obtain agreement before changing the shared schema.

**Known integration gap:** the current WP2 ASL contains callback waiting, timeout/reminder, completion persistence, and sequential stage selection, but it does not yet invoke a WP4 business-handler Lambda. Amit owns that WP2-to-WP4 orchestration change. Do not claim end-to-end integration until the invocation/callback sequence is implemented and tested.

## Stage-specific behaviour

### IT provisioning

- Simulated: return deterministic/mock account and equipment assignment outcomes; label mode as `simulated`.
- Real: call only an explicitly configured, approved IT provider. No provider is currently specified in the repository. Missing provider configuration must fail clearly.
- Do not create actual accounts or assign physical assets in local tests.

### Policy sign-off

- Policy sign-off is a human callback stage owned by WP2, not an automatic simulated WP4 stage.
- WP5 authenticates the employee by immutable Cognito sub and invokes WP4 action sign_policy with a versioned acceptance.
- WP4 records only the policy_acceptances attribute on the policy-signoff row; it never changes WP2 lifecycle status or task tokens.
- WP5 submits the policy-signoff callback when its token exists. If the workflow has not reached that stage yet, WP2 detects the saved acceptance when it creates the callback token and resumes safely.
- The demo uses company_policy v1 as a placeholder acknowledgement. Production must render the actual policy text/version and retain complete audit evidence.

### Manager introduction

- Simulated: create a deterministic demo invitation/result only.
- Real: use an explicitly configured, approved calendar/HR provider. No provider is currently specified in the repository. Missing configuration must fail clearly.
- Do not send real invitations in local tests.

## WP3 document upload contract

Public request to `POST /employees/{employee_id}/documents/upload-url`:

```json
{
  "document_type": "id_proof",
  "content_type": "application/pdf",
  "file_size": 12345
}
```

Allowed document types: `id_proof`, `degree_certificate`, `signed_offer_letter`.
Allowed content types: `application/pdf`, `image/jpeg`, `image/png`.
Size: 1–5,242,880 bytes (5 MiB), validated server-side.

WP5 invokes WP3 synchronously with trusted context:

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

WP3 uses the existing `hrms-dev-documents` table with keys `employee_id` + `doc_type`; do not confuse the public field `document_type` with the table sort key `doc_type`. The bucket must remain private. Issue a short-lived presigned PUT URL (default 300 seconds), bind the content type, and do not expose bucket/object keys. Validate the actual S3 object's size, content type, and file signature on the S3 ObjectCreated event.

S3 event handling must be idempotent and conditional: an update is valid only when the stored `s3_key` equals the event object key and status is still `missing`. A stale event for a superseded upload must not modify the current document row. A verified document cannot be overwritten through a new upload request; rejected/missing attempts may be retried with a fresh random key.

When all three required documents have passed validation, WP3 invokes the trusted WP2 resume_document_collection action. WP2 records a documents_verified readiness flag and submits the stored task token if the callback is active; if uploads finish before the workflow reaches the wait state, WP2 resumes automatically when it creates the token. WP3 must not directly mutate canonical lifecycle fields.

## Mode configuration

ADR 0002 requires `MODE=simulated|real` and secrets in SSM Parameter Store. Use `simulated` for local/offline testing. For `real`, require explicit provider configuration, retrieve secrets at runtime from SSM (with least-privilege execution-role access), and fail closed when required parameters are absent. Never commit secrets or use the developer IAM user's credentials from Lambda code.

## Retry, security, and testing requirements

- Validate every event shape and enum at the Lambda boundary.
- Make operations idempotent using a stable correlation/idempotency key.
- Do not log JWTs, task tokens, presigned URLs, document bytes, or provider secrets.
- Use conditional DynamoDB writes for state transitions and S3 event validation.
- Unit tests must mock AWS SDK clients; no AWS deployment or live external API calls are part of local tests.
- Cover valid/invalid inputs, authorization failures, duplicate/replayed events, stale upload events, expired/renewed upload URLs, missing provider configuration, simulated success, and provider failure.
- Keep feature work on the contributor's feature branch; open a PR targeting `team-dev`. Do not commit directly to `main`.

## AWS access boundary

Developer IAM permissions and Lambda execution-role permissions are separate. The developer user should have only the scoped inspection/development permissions approved for the package. The WP3 execution role separately needs only the S3 object, DynamoDB, SNS, and SSM actions required at runtime. Never grant public-access-block write permission merely to fix a read denial. No deployment is authorized by this document.
