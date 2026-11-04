# HRMS Onboarding — Project Control & Gate A Release State

> This is the persistent engineering control record for the integrated `team-dev` release. Read it before proposing code, test, merge, or AWS changes. Update it after each verified milestone. Do not treat chat history as the source of truth.
>
> **Last consolidated:** 2026-11-04  
> **Release target:** Gate A mentor/evaluation release (simulated WP4; not production)  
> **Repository:** `amit-cloudops-ai/hrms-onboarding-service`

## 1. Product and finish line

Build an integrated HRMS employee-onboarding system with:
- WP1 identity provisioning and Cognito subject linking.
- WP2 Step Functions onboarding orchestration, callbacks, reminders and stage lifecycle.
- WP3 secure document upload, validation, metadata persistence and rejection notification.
- WP4 business-stage adapter for IT provisioning and manager introduction. Gate A runs this in explicit **simulated** mode.
- WP5 authenticated API and authorization boundary.
- WP6 employee portal and WP7 HR dashboard.
- Shared persisted employee/stage state, correlated logs, CI evidence and cost-safe evaluation operations.

**Gate A is complete only when** a real evaluation journey works through the deployed applications and AWS services: HR admin signs in → creates employee → employee activates/signs in → uploads documents → WP3 validates and WP2 resumes through the trusted callback → employee acknowledges policy → WP2 invokes simulated WP4 stages → portal and dashboard show the same persisted progress after refresh. Authorization negatives, notifications, logs, smoke-test evidence and cost/resource notes must also be recorded.

**Gate B is separate.** Real IT provisioning, calendar/manager-provider integration, production security controls, operational resilience and production readiness are not implied by a successful Gate A demo.

## 2. Branch and implementation context

- `v1-solo` is the independently built implementation and an architectural/reference baseline. It was synced at `198f687` on 2026-11-03 according to the project history.
- `team-dev` is the integrated multi-work-package evaluation target. It must be completed and validated as its own integration; do not blindly replace it with, or merge all of, `v1-solo`.
- `main` is not the active integration branch.
- PRs #12 and #13 were merged into `team-dev`; PR #13 addressed WP3 Decimal serialization. CI runs #310 and #311 were reported successful (26 steps) on the then-current integration state.
- PR #6 (`feature/wp3-sushmitha-documents`) was reported stale and non-mergeable. Do not merge it without a fresh base/head comparison and contract review.
- Last reported local working branch: `team-dev`. The local checkout has uncommitted work listed in §8. Do not overwrite it.

## 3. Architecture and integration contracts

| Work package | Responsibility | Integration contract / boundary |
|---|---|---|
| WP1 | Cognito identity creation and immutable subject link | Self-service authorization uses Cognito `sub`, not mutable email |
| WP2 | Step Functions workflow, wait/callback, reminders, lifecycle state | Owns canonical stage lifecycle and correlation; trusted WP5 path resumes callbacks |
| WP3 | Presigned upload, S3 object validation, document metadata, rejection | Must not receive/store Step Functions task token; S3 EventBridge invokes WP3 |
| WP4 | IT provisioning and manager introduction adapter | Synchronous WP2 invocation; explicit `MODE=simulated` for Gate A; no canonical lifecycle writes |
| WP5 | Cognito JWT-protected API, authorization and adapters | Enforces HR-admin and employee-self boundaries; trusted callback boundary |
| WP6 | Employee portal | Uses real WP5 API, not mock data in evaluation |
| WP7 | HR dashboard | Reads the same persisted employee/stage state as portal/workflow |

WP2 → WP4 contract previously tested with a synchronous Lambda invocation: `action=execute_business_stage`, employee ID, stage and correlation ID; returned simulated completion for IT provisioning. This proves the adapter invocation contract only, not the entire Step Functions journey.

The deployed state machine was reported ACTIVE and contained document wait/callback, IT provisioning, policy wait/sign-off and business-stage states. The complete deployed ASL transition graph has not been fully re-reviewed in this snapshot; do not claim full E2E verification from state names alone.

## 4. AWS environment inventory — last observed, not a live query

**Account:** `924422830139`  
**Region:** `us-east-1`  
**Constraint:** use existing team evaluation resources only. Do not create new billable infrastructure without explicit approval. Preserve existing `hrms-dev` resources/stacks.

### Cognito
- User pool: `us-east-1_GUx6uZsFJ`
- App client: `5659oiu8c5v4q83cq8j4uepb4n`
- Domain: `https://hrms-team-924422830139.auth.us-east-1.amazoncognito.com`
- HR group: `hr-admins`
- Admin user membership in `hr-admins` was previously verified.

### API
- API Gateway HTTP API: `m040hqrfd4`
- Base URL: `https://m040hqrfd4.execute-api.us-east-1.amazonaws.com`
- Lambda: `hrms-team-api`
- Handler: `services.api.handler.lambda_handler`
- Runtime: Python 3.12
- Tables: `hrms-team-employees`, `hrms-team-documents`, `hrms-team-onboarding-stages`
- Downstream functions: `hrms-team-documents-hrms-team-wp3`; `hrms-team-wp4-StageFunction-0bIozhND66Qc`
- State machine: `arn:aws:states:us-east-1:924422830139:stateMachine:hrms-team-onboarding`

### WP2 / WP3 / WP4
- WP2 Lambda: `hrms-team-wp2-WorkflowFunction-GAuBPspQIQrF`; `MODE=simulated`; WP4 stage function configured.
- WP3 Lambda: `hrms-team-documents-hrms-team-wp3`; documents bucket: `hrms-924422830139-us-east-1-hrms-team-documents-documents`.
- WP3 EventBridge rule: `hrms-team-wp3-DocumentsObjectCreatedRule-9kezeIgFUkXR`, previously observed enabled and targeting WP3. S3 bucket EventBridge notification was configured. Actual post-fix upload processing still needs E2E proof.
- WP4 Lambda: `hrms-team-wp4-StageFunction-0bIozhND66Qc`; `MODE=simulated`.

### Notifications
- WP3 rejection topic: `arn:aws:sns:us-east-1:924422830139:hrms-team-wp3-DocumentRejectedTopic-BTPTdSOQrO07`
- WP2 reminders topic: `arn:aws:sns:us-east-1:924422830139:hrms-team-onboarding-reminders`
- Email subscriptions for `amitmadakatti@gmail.com` were last observed as `PendingConfirmation`. Do not repeatedly resubscribe; user must confirm the existing emails.

### Frontends / CDN
- Portal bucket: `hrms-team-portal-924422830139-us-east-1`
- Portal CloudFront: `E3CSGQ6L758GID`
- Portal URL: `https://d1aozjt2t5kjtv.cloudfront.net`
- Dashboard bucket: `hrms-team-dashboard-924422830139-us-east-1`
- Dashboard CloudFront: `E3NQ04V3BNKO68`
- Dashboard URL: `https://d2i8jrjhff3cr3.cloudfront.net`
- A previous dashboard request returned 403 for employee listing and the bundle was observed calling a Lambda Function URL rather than the expected API Gateway URL. This may be a stale bundle/API-base mismatch; verify only after backend authorization is corrected, and don't assume this old observation is still current.

All AWS facts above are a historical inventory from prior CLI output, not a guarantee of current state. Re-query only the specific resource whose state is material to the next action. Do not repeatedly rediscover the entire account.

## 5. Current known blocker: deployed API differs from tested local API

On 2026-11-04:
- Local `services/api/handler.py` SHA-256: `843d65e3b0ca5164222481dcae2ffc74a1764f394f17d136ed8108303d9bfe5`
- SAM-built handler SHA-256: identical to local.
- Deployed Lambda package handler SHA-256: `8bc4c39feb7851a0b4f84d39c66f5988fff4b07c6482e2c11e15015c621e934d`
- Deployed Lambda last modified: `2026-11-03T17:48:17Z`; state Active; last update Successful.
- Therefore deployed handler is older/different from current tested source. This is consistent with, but does not alone prove the sole cause of, the live HR-admin 403.
- Local `_is_admin` normalizer passed manual cases: normal list, JSON string, nested Python-list string, nested JSON string; rejects `Employee`.
- API suite `services.api.test_handler`: 23 tests passed.
- Do not rewrite the normalizer again without new evidence. Add the exact logged claim shape as a regression test before shipping.

## 6. Test and packaging status — 2026-11-04

### Confirmed
- API unit suite: 23/23 passed.
- Python compileall under `services`: passed.
- `sam validate --lint --template-file services/api/template.yaml`: passed.
- SAM build: succeeded.
- Local handler and SAM-built handler bytes match.

### Not passed / not complete
- Explicit seven-module unittest command ran 40 tests but ended with **5 import errors**:
  - `services/documents/test_handler.py`: `ModuleNotFoundError: handler`
  - `services/documents/test_validate.py`: `ModuleNotFoundError: validator`
  - `services/identity/test_handler.py`: `ModuleNotFoundError: handler`
  - `services/workflow/test_callbacks.py`: `ModuleNotFoundError: callbacks`
  - `services/workflow/test_handler.py`: `ModuleNotFoundError: handler`
- API tests and WP4/stages tests passed in that run. Documents, identity and workflow tests were not successfully imported; do not count them as passed.
- `unittest discover -s services` found zero tests; this is a discovery/layout issue, not evidence that no tests exist.

### Critical packaging defect / deployment prohibition
- API SAM template currently has `CodeUri: ../..`, so the API build copies the repository root.
- Build output `/tmp/hrms-api-sam-build/ApiFunction` was 186 MB; `frontend` alone was 185 MB and `.wrangler` was included.
- **Do not zip or deploy this artifact.** It is polluted with unrelated frontend and Wrangler content.
- No API `requirements.txt` was found at the declared CodeUri root or under `services/api`; SAM reported it continued without dependencies. Confirm actual runtime imports and packaging expectations before changing CodeUri.
- Correct packaging architecture must isolate the API deployment package and retain only runtime-required modules/dependencies. Validate API imports and any shared service modules before deployment.

## 7. Failure history and regression risks to guard against

1. **HR admin 403:** Cognito membership was correct; logs showed group claim value represented as a list containing a stringified list. Local normalization now accepts nested forms, but deployed code differs.
2. **Stale frontend/API base URL:** prior dashboard used a Lambda Function URL rather than expected API Gateway URL; frontend bundles/CloudFront invalidation can make a correct backend appear broken.
3. **WP3 Decimal serialization:** caused a runtime serialization failure; fix was merged/deployed, but real upload processing after that deployment has not been proven.
4. **WP3 event trigger:** EventBridge rule/bucket notification/Lambda permission were configured; configuration alone does not prove event processing or callback completion.
5. **Workflow contracts:** WP2/WP4 synchronous adapter invocation succeeded in isolation; full Step Functions path and callback sequencing remain unproven.
6. **Test import layout:** test modules use service-local imports such as `import handler`; root-level unittest invocation fails unless test runner sets the service directory on `sys.path` or tests are made package-safe. Do not "fix" imports blindly; align with existing CI conventions and Lambda packaging.
7. **SAM root CodeUri:** causes huge contaminated package; must be corrected before any API deployment.
8. **Frontend changes:** portal and dashboard have uncommitted edits; build and lint each app independently before publishing either.
9. **SNS:** pending email confirmation can look like a broken notification even if publish succeeds.
10. **Infrastructure drift/cost:** team and hrms-dev names/defaults differ in templates. Never run broad deploy scripts or change defaults without inspecting exact stack/resource targets.

## 8. Local working-tree state last reported

Local checkout: `~/hrms-onboarding-service`, branch `team-dev`.

Uncommitted changes reported by `git status --short`:
- Modified: `frontend/hr-dashboard/src/App.css`
- Modified: `frontend/hr-dashboard/src/App.jsx`
- Modified: `frontend/hr-dashboard/src/components/AuthGate.jsx`
- Modified: `frontend/portal/src/api/httpApi.js`
- Modified: `services/api/handler.py`
- Untracked: `.wrangler/`
- Untracked: `infra/team-dev-cloudfront-only.yaml`
- Untracked: `infra/team-dev-static-hosting.yaml`

This status is from the user's local machine and may have changed since reported. Do not assume GitHub has these edits. Never run `git clean`, `git reset`, `git add .`, force push, stash, branch switch or broad overwrite. Preserve all listed work.

## 9. Operational safety rules

- No new billable AWS infrastructure without explicit approval.
- Preserve all existing `hrms-dev` stacks/resources.
- Never run `infra/deploy-team-dev.sh`; it may create stacks and sync frontend buckets with `--delete`.
- No broad SAM/CloudFormation deployment for a code-only API fix.
- No frontend deployment while backend/API base URL and auth behavior are unresolved.
- No deployment from a package that has not been inspected for size, contents, handler path and dependencies.
- No code change until the target behavior, callers, callees, persisted schema, authorization boundary, tests and rollback are identified.
- Do not use a successful unit test as evidence of AWS E2E success.
- Do not call simulated WP4 a production integration.

## 10. Required change-control workflow (every fix)

Before editing:
1. State the Gate A acceptance criterion this change advances.
2. Record current behavior and exact evidence (test/log/request/commit).
3. Trace impact across caller → API/contract → downstream Lambda/workflow → DynamoDB/S3/SNS → portal/dashboard.
4. Identify schema, IAM, environment, packaging, frontend compatibility and cost implications.
5. List regression tests and a rollback path.
6. Choose the smallest isolated change; do not bundle unrelated cleanup.

After editing:
1. Inspect the diff; verify no unrelated files changed.
2. Run the narrow test, then all relevant service tests using the repository's actual CI import convention.
3. Run syntax, lint, SAM/ASL validation and frontend build checks for affected components.
4. Inspect built artifact contents/size and compare handler/source hashes.
5. Deploy only the smallest approved target.
6. Wait for update completion; verify deployed version/hash.
7. Run one positive and relevant negative smoke test through the real boundary.
8. Update this document with evidence, timestamps, commit/deployment IDs, remaining risks and next gate.

If any test or validation fails, stop at that gate. Do not compensate with another speculative change.

## 11. Immediate next sequence — no parallel fixes

**Gate 0 — establish reliable baseline**
- Record current `team-dev` GitHub head, local diff and CI status without altering local work.
- Compare `v1-solo` with `team-dev` by capability and contract; identify proven behavior in v1-solo that is missing or regressed in team-dev. Do not merge wholesale.
- Read the actual CI workflow to learn the intended per-service test working directories/import setup.

**Gate 1 — fix validation and API packaging design**
- Make test invocation deterministic using the same convention as CI; prove all seven test modules execute, not merely import.
- Design an isolated API CodeUri/package. Ensure it includes required handler/shared code and dependencies, and excludes frontend, `.wrangler`, Git metadata, local venvs and unrelated services.
- Add the exact HR-admin claim regression case.
- Run all impacted tests and build inspection before AWS update.

**Gate 2 — targeted API release**
- Only after Gate 1 passes, update code for existing `hrms-team-api` (no stack deployment).
- Verify Lambda code hash and last-modified timestamp.
- Test HR admin list endpoint and employee-token denial; then test dashboard against the correct API base URL.

**Gate 3 — end-to-end evaluation**
- Run one controlled HR-created evaluation employee through activation, document upload, WP3 validation/callback, policy acknowledgement, WP2 simulated WP4 stages and portal/dashboard refresh.
- Capture execution IDs, employee ID, timestamps, expected/actual outcomes and correlated logs.
- Confirm SNS subscriptions, notification delivery and security redaction.

**Gate 4 — Gate A sign-off**
- Produce evidence-based acceptance matrix, known limitations, cost/resource inventory and teardown instructions.
- Keep resources until mentor/evaluation sign-off. Do not delete the environment early.

## 12. How this record is maintained

- This file is the project-level memory and release-control index.
- Add detailed dated entries to `docs/engineering/CHANGELOG.md` for each completed change: problem, root cause, files/resources changed, tests, deploy IDs, outcome, side effects and rollback.
- Keep `docs/implementation-status.md` as the high-level feature summary, but align it with this control record.
- Keep AWS inventory in a separate dated `docs/engineering/AWS_INVENTORY.md`; each resource entry must include last-observed timestamp and source evidence.
- Update records only from actual evidence. If an item is unknown or stale, label it unknown/stale; do not fill gaps by assumption.
