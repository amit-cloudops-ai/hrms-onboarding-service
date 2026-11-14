# WP5 — API Gateway and authorization

WP5 is the authenticated HTTP boundary for the onboarding platform. API Gateway validates Cognito JWTs; the API Lambda performs route-level authorization and invokes the identity, workflow, document and stage services through configured adapters.

## Responsibilities

- Parse and validate HTTP API payload format 2.0 requests.
- Enforce HR administrator access through the configured Cognito group.
- Enforce employee self-service by matching the authenticated token's immutable `sub` claim to the employee record's `cognito_sub`.
- Delegate employee registration to WP1 and onboarding initiation to WP2.
- Invoke WP3/WP4 adapters with server-derived caller context.
- Return sanitized errors and never expose internal task tokens, S3 object keys or credentials.

API Gateway authentication and Lambda authorization checks are both required. Frontend route visibility is not an authorization boundary.

## Routes

The canonical route and request/response definitions are in [docs/api-contract.md](../../docs/api-contract.md). The implemented surface includes:

| Method | Route | Access |
|---|---|---|
| POST | `/employees` | HR administrator |
| GET | `/me` | Authenticated employee |
| GET | `/employees` | HR administrator |
| GET | `/employees/{employee_id}` | HR administrator or matching employee |
| GET | `/employees/{employee_id}/progress` | HR administrator or matching employee |
| POST | `/employees/{employee_id}/documents/upload-url` | Matching employee |
| GET | `/employees/{employee_id}/documents` | HR administrator or matching employee |
| POST | `/employees/{employee_id}/policies/sign` | Matching employee |
| POST | `/employees/{employee_id}/stages/{stage}/complete` | HR administrator |

The API delegates document and stage operations to separately deployed Lambda adapters. Adapter function names are supplied through environment configuration. Missing or failed dependencies return explicit service/dependency errors rather than simulated success.

## Configuration

The SAM template supports environment-specific table and service names. Common variables include:

- `EMPLOYEES_TABLE`
- `STAGES_TABLE`
- `DOCUMENTS_TABLE`
- `COGNITO_USER_POOL_ID`
- `STATE_MACHINE_ARN`
- `HR_ADMIN_GROUP` (default `hr-admins`)
- `DOCUMENTS_FUNCTION_NAME`
- `STAGES_FUNCTION_NAME`

Standalone templates may use `hrms-dev-*` defaults. The team evaluation environment uses its own `hrms-team-*` resource names; pass the correct names through the deployment parameters rather than relying on defaults.

## Offline tests

From the repository root:

```bash
python -m unittest services.api.test_handler -v
```

These tests use mocks and do not call AWS or create resources.

## Validation and deployment boundary

Validate the template without deploying:

```bash
sam validate --lint --template-file services/api/template.yaml
sam build --template-file services/api/template.yaml
```

CI runs validation/build checks only. Any AWS deployment requires a separate approval, account/region verification and CloudFormation change-set review. See the [final project audit](../../docs/FINAL-PROJECT-AUDIT.md).
