# Implementation status and handoff log

**Branch:** `v1-solo`  
**AWS region:** `us-east-1`  
**Last deployment confirmation:** 1 November 2026

## Current release status

The five backend development stacks have been deployed and each returned `CREATE_COMPLETE`:

| Stack | Status |
|---|---|
| `hrms-dev-foundation` | `CREATE_COMPLETE` |
| `hrms-dev-stages` | `CREATE_COMPLETE` |
| `hrms-dev-documents` | `CREATE_COMPLETE` |
| `hrms-dev-workflow` | `CREATE_COMPLETE` |
| `hrms-dev-api` | `CREATE_COMPLETE` |

The API endpoint is `https://mv5cyfzsya.execute-api.us-east-1.amazonaws.com`.

**Boundary:** stack creation is confirmed; live end-to-end application behavior is not yet confirmed. Frontend environment setup, Cognito login, admin/employee authorization, employee creation, S3 upload validation, policy sign-off, manager completion, notification delivery and failure-path testing remain.

For the complete implementation history, problems/fixes, AWS resource inventory, deployment commands, Console walkthrough, local frontend configuration, acceptance checklist and cleanup procedure, see [Solo implementation and AWS deployment record](solo-implementation-and-aws-deployment-record.md).

## WP1 — Identity

Status: **Implementation and offline tests passing; deployed foundation exists; live employee-creation path pending acceptance testing**

- Validates and normalizes employee input.
- Writes the employee record, creates the Cognito identity, and stores Cognito's immutable `sub` on the employee record.
- Performs compensating cleanup when identity creation or subject linkage fails.
- WP5 self-service authorization compares the JWT `sub` with the stored `cognito_sub`; email alone does not grant access.

## WP2 — Workflow

Status: **Implementation deployed; live callback and reminder journey pending**

- Orchestrates the four contract stages in order.
- Stores callback tokens server-side and never returns them in responses or reminder messages.
- Waits up to 24 hours for each callback, sends a reminder on timeout, and starts a new callback wait.
- Persists stage completion after Step Functions accepts the callback.
- Dispatches each active stage to WP4; WP4 owns stage-specific behavior.
- Deployed state machine: `arn:aws:states:us-east-1:924422830139:stateMachine:hrms-dev-onboarding`.

## WP3 — Documents

Status: **Implementation deployed; live S3 upload/validation path pending**

- Issues short-lived, object-scoped presigned PUT URLs for the three contract document types.
- Uses immutable Cognito-sub authorization and records metadata in the existing documents table.
- Validates actual object size, content type, and PDF/JPEG/PNG magic bytes on S3 object-created events.
- Rejects invalid files, deletes the rejected object, notifies the HR SNS topic, and supports safe re-upload after expiry/rejection.
- Resumes document collection only after all three required documents are verified.
- Deployed private bucket: `hrms-924422830139-us-east-1-hrms-dev-documents-documents`.

## WP4 — Stage handlers

Status: **Implementation deployed; simulation mode enabled; live stage progression pending acceptance testing**

- Simulated IT provisioning writes deterministic laptop/monitor assignments to the equipment table and completes automatically; real mode requires an explicitly configured provisioning Lambda.
- Stores versioned policy acceptance and resumes `policy_signoff` only after every configured required policy is accepted.
- Publishes a manager-introduction action-required notification and waits for HR completion.
- Uses the WP2 task token only for Step Functions callback submission; token values are not returned or logged.
- Deployed Lambda: `hrms-dev-stages`. `SimulationMode=true` for the first development test.

## WP5 — API

Status: **HTTP API deployed; live authenticated route/authorization checks pending**

- Implements the routes in `docs/api-contract.md` behind an API Gateway Cognito JWT authorizer.
- Enforces HR-admin checks and immutable-sub employee self-access checks.
- Creates employee identity and starts the onboarding execution, persisting its execution ARN privately.
- Exposes server-side callback completion without exposing task tokens.
- Routes document and policy operations to WP3/WP4 adapters and fails closed if an adapter is missing or fails.
- API endpoint: `https://mv5cyfzsya.execute-api.us-east-1.amazonaws.com`.

## WP6 — New-hire portal

Status: **Cognito/API client wiring implemented; production build passed; local live configuration and browser acceptance pending**

- Responsive portal with four-stage progress, document checklist, policy acceptance, equipment/manager status and support dialog.
- Uses Cognito OAuth authorization-code grant with PKCE, state validation, session-scoped token storage, refresh on expiry and sign-out.
- Adds the ID token as a bearer token on API requests and parses structured backend error envelopes.
- Live mode resolves the signed-in employee through `GET /employees/me`, matching the verified JWT subject to stored `cognito_sub`.
- Document uploads check the presigned S3 PUT response, poll document status and surface verified/rejected/pending state.
- Local demo mode remains available without AWS credentials or side effects.
- Create `frontend/portal/.env.local` using the values in the solo deployment record; do not commit it.

## WP7 — HR operations dashboard

Status: **Cognito/API client wiring implemented; production build passed; local live configuration and admin acceptance pending**

- Dashboard with pipeline metrics, stage analytics, search/filter, employee details, CSV export, refresh, notifications and add-new-hire workflow.
- Uses Cognito OAuth PKCE/session module and bearer-token API requests.
- Live employee data is fetched from `GET /employees`; live mode starts empty rather than displaying demo employees.
- Create form sends `full_name`, `email`, `role`, `department`, `joining_date` and `employment_type`.
- Backend `hr-admins` group membership is the authorization boundary.
- Create `frontend/hr-dashboard/.env.local` using the values in the solo deployment record; do not commit it.

## Verification record

- Offline backend regression suite: **84 tests passed**, as reported during the solo deployment session. These tests use local/mocked services and are not proof of live AWS integration.
- Both Vite frontend production builds passed in the recorded GitHub Actions workflow after Vite environment typings and Cognito/API wiring were added.
- SAM builds for WP2, WP3 and WP5 succeeded during the deployment session. SAM printed `requirements.txt file not found. Continuing the build without dependencies.`; deployed Lambda runtime imports must be verified in CloudWatch and missing third-party dependencies packaged if needed.
- Each of the five CloudFormation stacks returned `CREATE_COMPLETE`. Change sets were reviewed before execution. This confirms resource provisioning, not the full business journey.

## Known production hardening

- Development Cognito MFA is OFF because the initial optional-MFA configuration failed without SMS configuration. Configure and test TOTP MFA before production.
- IT provisioning is simulated; connect a real provisioning adapter before real operations.
- Configure approved SNS subscriptions and verify delivery.
- Review IAM least privilege, especially employee-table access and Step Functions callback permissions.
- Set exact production HTTPS origins for Cognito callback/logout, API CORS and S3 upload CORS.
- Establish data retention, backups, CloudWatch retention/alerts, incident response and cost budgets.
- Review actual AWS charges; deployed services can incur costs.

## Next acceptance gates

- [ ] Configure both local frontend environment files and verify Cognito hosted login.
- [ ] Create/verify HR admin membership in `hr-admins`.
- [ ] Verify anonymous 401, HR-admin access and employee self-only access.
- [ ] Create a disposable employee and verify Cognito identity, DynamoDB record and Step Functions execution.
- [ ] Verify simulated IT provisioning and equipment assignment.
- [ ] Verify valid/invalid document uploads, asynchronous S3 validation, status polling and retry.
- [ ] Verify all required policy acceptances and manager-intro completion.
- [ ] Verify failure paths, CloudWatch logs, SNS delivery and AWS spend.
- [ ] Complete production MFA, IAM, privacy and real-adapter hardening before production use.

## Working agreements

- Preserve working code; do not reset or delete existing work to restart.
- Keep contributor work on isolated feature branches.
- `docs/api-contract.md` and `docs/data-model.md` are the shared contract sources.
- Never expose Step Functions task tokens to browsers or employees.
- Review CloudFormation change sets before executing them.
- Never commit credentials, temporary passwords, JWTs, presigned URLs or employee document contents.
