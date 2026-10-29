# Implementation status and handoff log

## Working agreements

- Preserve working code; do not reset or delete existing work to restart.
- Keep contributor work on isolated feature branches.
- `docs/api-contract.md` and `docs/data-model.md` are the shared contract sources.
- Run local tests before committing. Do not deploy AWS resources without explicit approval.
- Never expose Step Functions task tokens to browsers or employees.

## WP1 — Identity

Status: **Offline implementation and test gates passing; live integration unverified**

- Validates and normalizes employee input.
- Writes the employee record, creates the Cognito identity, and stores Cognito's immutable `sub` on the employee record.
- Performs compensating cleanup when identity creation or subject linkage fails.
- WP5 self-service authorization compares the JWT `sub` with the stored `cognito_sub`; email alone does not grant access.

## WP2 — Workflow

Status: **Offline implementation and template gates passing; live integration unverified**

- Orchestrates the four contract stages in order.
- Stores callback tokens server-side and never returns them in responses or reminder messages.
- Waits up to 24 hours for each callback, sends a reminder on timeout, and starts a new callback wait.
- Persists stage completion after Step Functions accepts the callback.
- Dispatches each active stage to WP4 and clears the token if dispatch fails; WP4 owns stage-specific behavior.

## WP3 — Documents

Status: **Offline implementation and CI gates passing; live integration unverified**

- Issues short-lived, object-scoped presigned PUT URLs for the three contract document types.
- Uses immutable Cognito-sub authorization and records metadata in the existing documents table.
- Validates actual object size, content type, and PDF/JPEG/PNG magic bytes on S3 object-created events.
- Rejects invalid files, deletes the rejected object, notifies the HR SNS topic, and supports safe re-upload after expiry/rejection.
- Resumes document collection only after all three required documents are verified.
- The SAM template creates a private encrypted/versioned bucket, CORS configuration, S3 trigger, notification topic, and service IAM policy.

## WP4 — Stage handlers

Status: **Implementation added on `v1-solo`; CI/live verification pending**

- Simulated IT provisioning writes deterministic laptop/monitor assignments to the equipment table and completes automatically; real mode requires an explicitly configured provisioning Lambda.
- Stores versioned policy acceptance and resumes `policy_signoff` only after every configured required policy is accepted.
- Publishes a manager-introduction action-required notification and waits for HR completion.
- Uses the WP2 task token only for Step Functions callback submission; token values are not returned or logged.
- Includes a SAM template with stage-handler IAM permissions and notification topic.

## WP5 — API

Status: **Offline implementation and template gates passing; live integration unverified**

- Implements the eight routes in `docs/api-contract.md` behind an API Gateway Cognito JWT authorizer.
- Enforces HR-admin checks and immutable-sub employee self-access checks.
- Creates employee identity and starts the onboarding execution, persisting its execution ARN privately.
- Exposes server-side callback completion without exposing task tokens.
- Routes document and policy operations to the configured WP3/WP4 adapters and fail closed if an adapter is missing or fails.

## Verification log

GitHub Actions run **#90** passed on validation commit `04353204dc8a001f680bacb57304499e48d9e122`. The WP1/WP2/WP3/WP4/WP5 code, tests, templates, and CI workflow on that validation branch were checked against `v1-solo` and have matching file contents. The run passed all 73 tests and all four SAM template validations.

GitHub Actions workflow run **#90** for validation commit `04353204dc8a001f680bacb57304499e48d9e122` completed successfully. It passed all 73 tests and validations:

- ASL JSON syntax validation.
- SAM lint validation for `services/api/template.yaml`, `services/workflow/template.yaml`, `services/documents/template.yaml`, and `services/stages/template.yaml`.
- WP1 identity tests: 16 passed.
- WP5 API tests: 20 passed.
- WP2 workflow handler tests: 9 passed.
- WP2 callback helper tests: 8 passed.
- WP3 document service tests: 8 passed.
- WP4 stage service tests: 12 passed.

These are offline/mocked tests. They do not prove live AWS behavior.


## WP6 — New-hire portal

Status: **Cognito/API client wiring implemented; production build verified; live AWS authentication remains unverified**

- Premium responsive portal with four-stage progress, document checklist, policy acceptance, equipment/manager status, and support dialog.
- Uses Cognito OAuth authorization-code grant with PKCE, state validation, session-scoped token storage, refresh on expiry, and sign-out. No app-client secret or AWS credential is placed in frontend code.
- Adds the ID token as a bearer token on API requests and parses the backend's structured error envelopes.
- Live mode resolves the signed-in employee through `GET /employees/me`, which matches the verified JWT subject to the stored `cognito_sub`. Live mode does not require a hard-coded employee ID.
- Document uploads check the presigned S3 PUT response, poll the document status for asynchronous verification, and surface verified/rejected/pending status. Required policy acceptances are restored from backend progress metadata.
- Local demo mode remains available without AWS credentials or side effects.
- **Live configuration still needs confirmation:** actual Cognito hosted-login domain/client, allowed callback and sign-out URLs/scopes, deployed API endpoint, and the exact deployed portal origin for API/S3 CORS. Those values have not been supplied or verified against a live deployment.

## WP7 — HR operations dashboard

Status: **Cognito/API client wiring implemented; production build verified; live admin authorization remains unverified**

- Premium responsive dashboard with pipeline metrics, four-stage analytics, start dates, search/filter, employee details, CSV export, refresh, notifications, and add-new-hire workflow.
- Uses the same Cognito OAuth PKCE/session module and sends the ID token as a bearer token for protected API requests.
- Live employee data is fetched from `GET /employees`; live mode starts empty rather than displaying demo employees.
- The create form sends the backend's required `full_name`, `email`, `role`, `department`, `joining_date`, and `employment_type` fields.
- The backend's `hr-admins` Cognito group check remains the authorization boundary for list/create/stage completion. Client-side login state does not grant admin permissions.
- **Live configuration still needs confirmation:** same Cognito pool/client, dashboard callback and sign-out URLs (local Vite port `:5174`), actual `hr-admins` group membership, deployed API endpoint, and deployed dashboard origin in API CORS.

## Step 1 — Frontend build verification

- Added `.github/workflows/frontend-build.yml` to install dependencies and run `tsc -b && vite build` for both Vite apps.
- The first run identified missing Vite `ImportMeta.env` declarations; added `src/vite-env.d.ts` to both frontends.
- GitHub Actions run [40924366978](https://github.com/amit-cloudops-ai/hrms-onboarding-service/actions/runs/40924366978) passed the `portal` and `hr-dashboard` production builds after Cognito wiring, API integration, CORS defaults, and document-verification polling were implemented. Later repository changes did not alter frontend source.

## Step 2 — Cognito authentication and API integration

- Implemented Cognito authorization-code + PKCE in both frontends with state checking, refresh on expiry, sign-out, bearer-token API requests, structured error handling, and configuration examples.
- Added `GET /employees/me` across the API handler, SAM route, API contract, and tests. It resolves an employee using the authenticated JWT `sub`, never the mutable email claim, and rejects missing or ambiguous links.
- Exposed the versioned policy-acceptance metadata needed to restore employee policy checkboxes after refresh.
- Corrected the dashboard create-employee payload to match WP1's input contract. API CORS is now parameterized for separate portal/dashboard origins.
- API self-access/admin authorization and current-employee lookup have offline regression tests. **Real Cognito hosted login, live tokens, and live API claims have not been tested because the target AWS deployment is not yet available.**

## Step 3 — Mocked end-to-end integration tests

- Added `tests/test_onboarding_integration.py` and wired it into `.github/workflows/unit-tests.yml`.
- The composed success-path test invokes the real identity, document-validation, IT-provisioning, policy-signoff, and manager-completion handlers while using in-memory tables and a mocked Step Functions callback engine.
- Additional regression cases cover ordered four-stage ASL progression, the 24-hour timeout/reminder loop, document-stage gating until all three files are verified, invalid file signatures and HR notification, retrying rejected documents with a fresh S3 object key, policy advancement only after all three required acceptances, HR-only manager completion, and expired callback handling.
- GitHub Actions run [40925133142](https://github.com/amit-cloudops-ai/hrms-onboarding-service/actions/runs/40925133142) passed the offline unit-test workflow including the composed journey and rejected-document retry test. The simulated journey does **not** prove live AWS event delivery or service permissions.

## Step 4 — AWS configuration and cost audit

- Added [`docs/predeployment-audit.md`](predeployment-audit.md) with the expected table/key/index contract, fixed resource-name collision risks, CORS and Cognito prerequisites, deployment/rollback gates, and cost considerations.
- Added [`scripts/aws_predeploy_audit.sh`](../scripts/aws_predeploy_audit.sh), a read-only audit script for account identity/region, CloudFormation stacks/resources/outputs, DynamoDB schemas and indexes, Cognito pool/client configuration, API Gateway routes and CORS, Lambda IAM policies, Step Functions definitions, S3 security/CORS/versioning, SNS subscription status, CloudWatch retention, and recent Cost Explorer data.
- The script does not deploy, update, delete, or list document objects. CI runs `bash -n` against the script.
- **The live account audit is not complete.** This execution environment does not have the AWS CLI or the user's AWS credentials, so I cannot report the real account ID, existing resource inventory, actual IAM configuration, or actual spend. Run `bash scripts/aws_predeploy_audit.sh` from a terminal authenticated to the intended AWS account and review the output before authorizing deployment.

## Release boundary

- No AWS deployment or live integration test has been performed.
- Before a live release, validate the deployed IAM role behavior, existing DynamoDB table schemas and indexes, Cognito JWT claims, Step Functions callback and timeout behavior, and SNS reminder delivery in an explicitly approved non-production environment.
- Deploy WP4 first, then WP3 and WP2, then WP5 with the emitted function/state-machine outputs; follow `docs/solo-integration-runbook.md`.
- Do not describe the entire HRMS product as end-to-end production-ready until external adapters and live integration tests are complete.
