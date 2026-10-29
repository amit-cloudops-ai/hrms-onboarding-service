# Implementation status and handoff log

## Working agreements

- Preserve working code; do not reset or delete existing work to restart.
- Keep contributor work on isolated feature branches.
- `docs/api-contract.md` and `docs/data-model.md` are the shared contract sources.
- Run local tests before committing. Do not deploy AWS resources without explicit approval.
- Never expose Step Functions task tokens to browsers or employees.

## WP1 — Identity

Status: **Implemented; integration pending**

- Location: `services/identity/`
- Last recorded local baseline: 13 unit tests passed.
- Covers payload validation, email normalization, DynamoDB employee creation,
  Cognito user creation, and cleanup after Cognito creation failure.
- Not yet proven end-to-end: workflow initiation, persisted `execution_arn`,
  duplicate-request behavior, AWS integration, and recovery from ambiguous
  cross-service failures.
- Decision: preserve the current implementation and close integration gaps after
  WP2 and WP5 are connected.

## WP2 — Workflow

Status: **Initial implementation; local validation pending**

- Location: `services/workflow/`
- Implements the four contract stages in sequence.
- Callback task timeout: 24 hours, followed by reminder dispatch and a new wait.
- Persists stage state and task tokens in the existing DynamoDB stage table.
- Includes a SAM template, unit tests, and a package README.
- Not yet deployed or validated against live AWS resources.
- WP5 must implement authorized callback resumption; WP4 stage-specific handlers
  must be integrated before end-to-end completion.

## Verification log

### Initial WP1 baseline

- Command: `cd services/identity && python -m unittest -v`
- Result: 13 tests passed.
- Note: this is the previously observed baseline, not a claim of current end-to-end readiness.

### WP2 initial implementation

- Local tests and SAM/ASL validation: pending.
- AWS deployment and integration tests: not run.

## WP2 callback hardening — 2026-10-29

- Added explicit handling for expired, invalid, or already-consumed Step Functions callback tokens.
- Callback tokens remain server-side and are not returned in the helper response.
- Callback submission and persisted stage completion are separate events: the Step Functions state machine performs the DynamoDB completion update after callback acceptance.
- Authorization must be enforced by the API layer before calling `resume_stage`; the helper's `authorized` argument is not a substitute for authentication.
- Validation target: WP1 and WP2 unit tests, ASL JSON parsing, SAM template lint validation, and `git diff --check`.
- AWS deployment and end-to-end integration remain unverified.
