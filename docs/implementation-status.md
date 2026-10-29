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

Status: **UI implemented on `v1-solo`; frontend build and live Cognito/API integration pending verification**

- Adds a premium, responsive employee workspace with a four-stage journey, progress summary, document checklist, policy acknowledgements, equipment/manager status cards, and support dialog.
- Implements PDF/JPG/PNG document selection with a 5 MB client-side limit and the presigned-upload-URL → S3 PUT flow when configured for live mode.
- Includes a clearly labelled demo mode that works without AWS resources or credentials.
- Uses the route contract in `docs/api-contract.md`; browser uploads require matching S3 bucket CORS.
- **Release limitation:** API Gateway requires Cognito JWTs. Cognito sign-in/session wiring and live response-shape verification still need to be completed before this portal can operate against a protected deployed API.

## WP7 — HR operations dashboard

Status: **UI implemented on `v1-solo`; frontend build and live Cognito/API integration pending verification**

- Adds a premium, responsive operations overview with stage completion analytics, cohort metrics, upcoming start dates, search/filter, employee details, CSV export, and a create-new-hire form.
- The create form maps to `POST /employees`; the list reads `GET /employees` when configured for live mode.
- Includes a clearly labelled demo workspace; demo-created employees are local UI state and do not create AWS resources.
- **Release limitation:** Cognito sign-in/session wiring and live API response-shape verification are still required for the protected API. Validate the live flow before treating WP6/WP7 as end-to-end integrated.

## Frontend build verification

- Added `.github/workflows/frontend-build.yml` to install dependencies and run production builds for both Vite apps on changes to `v1-solo`.
- The first build run exposed a missing Vite type declaration (`ImportMeta.env`) in both apps. Added `src/vite-env.d.ts` to each frontend on `v1-solo`.
- GitHub Actions run [40920740247](https://github.com/amit-cloudops-ai/hrms-onboarding-service/actions/runs/40920740247) passed for both `portal` and `hr-dashboard` after the fix. This confirms TypeScript compilation and Vite production builds only; it does **not** validate live Cognito/API integration.

## Release boundary

- No AWS deployment or live integration test has been performed.
- Before a live release, validate the deployed IAM role behavior, existing DynamoDB table schemas and indexes, Cognito JWT claims, Step Functions callback and timeout behavior, and SNS reminder delivery in an explicitly approved non-production environment.
- Deploy WP4 first, then WP3 and WP2, then WP5 with the emitted function/state-machine outputs; follow `docs/solo-integration-runbook.md`.
- Do not describe the entire HRMS product as end-to-end production-ready until external adapters and live integration tests are complete.
