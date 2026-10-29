# WP5 — API Gateway and authorization

## Local implementation

`handler.py` is the HTTP API Lambda for API Gateway HTTP API payload format 2.0. It implements the contract routes, validates request bodies, checks the `hr-admins` Cognito group for HR-only operations, and limits employee self-service access by matching the authenticated token's immutable Cognito `sub` claim to the canonical employee record's `cognito_sub`.

The Lambda expects API Gateway JWT authorization to be configured for every route. The Lambda's own claim checks are additional authorization controls, not a replacement for API Gateway authentication.

## Routes

- `POST /employees` — HR admin; create identity, start Step Functions, persist `execution_arn`.
- `GET /employees` — HR admin; list employees with progress.
- `GET /employees/{employee_id}` — HR admin or matching Cognito subject.
- `GET /employees/{employee_id}/progress` — HR admin or matching Cognito subject.
- `POST /employees/{employee_id}/documents/upload-url` — matching employee by Cognito subject; delegates to `DOCUMENTS_FUNCTION_NAME` with action `create_upload_url`.
- `GET /employees/{employee_id}/documents` — HR admin or matching employee; delegates with action `list_documents`.
- `POST /employees/{employee_id}/policies/sign` — matching employee by Cognito subject; delegates to `STAGES_FUNCTION_NAME` with action `sign_policy`.
- `POST /employees/{employee_id}/stages/{stage}/complete` — HR admin; submits the stored callback token server-side and never returns it.

WP3 and WP4 are implemented as separately deployed Lambda packages. The API passes the authenticated Cognito `sub` to the adapter and only invokes them through its IAM role. Each adapter validates the requested employee against the canonical employee record and returns a standard API Gateway response envelope. Missing function names return `503 SERVICE_NOT_CONFIGURED`; downstream failures return sanitized errors.

- Documents adapter actions: `list_documents`, `create_upload_url`.
- Stage adapter actions: `sign_policy`, `complete_stage` for the manager-intro route.
- HR admins can complete the manager-intro stage. Other manual stage callbacks are submitted through WP2's server-side callback helper.
- Deploy WP4 first, then WP3 and WP2, and finally WP5. See `docs/solo-integration-runbook.md` for parameters and acceptance tests.

## Required environment variables

- `EMPLOYEES_TABLE` (default `hrms-dev-employees`)
- `STAGES_TABLE` (default `hrms-dev-onboarding-stages`)
- `DOCUMENTS_TABLE` (default `hrms-dev-documents`; reserved for the WP3 adapter)
- `COGNITO_USER_POOL_ID`
- `STATE_MACHINE_ARN`
- `HR_ADMIN_GROUP` (default `hr-admins`)
- `DOCUMENTS_FUNCTION_NAME` (WP3 adapter)
- `STAGES_FUNCTION_NAME` (WP4 adapter)

## Offline tests — no AWS access

From repository root, with the project's Python environment active:

```bash
python -m unittest discover -s services/api -p 'test_*.py' -v
```

Tests use mocks. They do not create resources, call AWS, or deploy anything.

## AWS billing and deployment status

This package has **not** been deployed. Do not run `sam deploy`, CloudFormation changesets, or live integration tests as part of local validation. SAM template validation is local-only, but deployment and runtime checks require separate approval and a cost review.
