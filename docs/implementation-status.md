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
- Stage-specific business handlers are an external integration boundary and are not implemented by this WP2 package.

## WP5 — API

Status: **Offline implementation and template gates passing; live integration unverified**

- Implements the eight routes in `docs/api-contract.md` behind an API Gateway Cognito JWT authorizer.
- Enforces HR-admin checks and immutable-sub employee self-access checks.
- Creates employee identity and starts the onboarding execution, persisting its execution ARN privately.
- Exposes server-side callback completion without exposing task tokens.
- Document and policy operations fail closed with a 503 response until their adapter functions are configured; they do not report false success.

## Verification log

GitHub Actions workflow run **#35** for commit `33367925965e6580a7e42b68cee4d2d1286144e8` completed successfully. It passed all 52 tests and validations:

- ASL JSON syntax validation.
- SAM lint validation for `services/api/template.yaml`.
- SAM lint validation for `services/workflow/template.yaml`.
- WP1 identity tests: 16 passed.
- WP5 API tests: 19 passed.
- WP2 workflow handler tests: 9 passed.
- WP2 callback helper tests: 8 passed.

These are offline/mocked tests. They do not prove live AWS behavior.

## Release boundary

- No AWS deployment or live integration test has been performed.
- Before a live release, validate the deployed IAM role behavior, existing DynamoDB table schemas and indexes, Cognito JWT claims, Step Functions callback and timeout behavior, and SNS reminder delivery in an explicitly approved non-production environment.
- Document/policy routes require their separately owned adapter integrations before those routes can serve production traffic.
- Do not describe the entire HRMS product as end-to-end production-ready until external adapters and live integration tests are complete.
