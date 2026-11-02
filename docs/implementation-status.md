# Implementation status and handoff log

**Branch:** `v1-solo`  
**AWS region:** `us-east-1`  
**Live acceptance update:** 2 November 2026

## Current release status

The five development backend stacks have been deployed. The live HR dashboard and employee portal have now been opened and exercised against the deployed application.

| Stack | Deployment |
|---|---|
| `hrms-dev-foundation` | Previously confirmed deployed |
| `hrms-dev-stages` | Previously confirmed deployed |
| `hrms-dev-documents` | Previously confirmed deployed |
| `hrms-dev-workflow` | Previously confirmed deployed |
| `hrms-dev-api` | Previously confirmed deployed |

**API endpoint:** `https://mv5cyfzsya.execute-api.us-east-1.amazonaws.com`

### Live checks confirmed on 2 November 2026

- [x] HR administrator can sign in to the HR dashboard using Cognito.
- [x] Dashboard is configured for live API mode (`VITE_DEMO_MODE=false`); it is not using the demo employee seed data.
- [x] HR dashboard loads employee records from the live API.
- [x] HR can open employee documents; document content is displayed successfully.
- [x] Employee can sign in to the onboarding portal using an existing employee account.
- [x] Employee portal loads successfully after authentication.

These are manual live-application checks, not merely local unit-test results.

### Not yet recorded as individually verified

The following workflows must not be described as production-verified until their actual live outcomes are checked and recorded:

- Employee document upload, S3 object validation and status polling.
- HR approval and rejection, including mandatory rejection reason.
- Employee visibility of HR decisions and replacement upload after rejection.
- Policy acceptance and manager-introduction completion.
- Full Step Functions progression, reminder delivery, SNS delivery and failure-path behavior.
- Anonymous 401 and employee self-only authorization checks.
- Production hardening, MFA, IAM review, retention, monitoring and cost controls.

## WP1 — Identity

Implementation and offline tests are recorded as passing. Live HR Cognito authentication and employee sign-in through the portal have now been manually confirmed. Employee creation and the full invitation/identity lifecycle still require a separately recorded acceptance test.

## WP2 — Workflow

Workflow implementation and deployment are recorded. Live end-to-end stage progression, callbacks, timeout/reminder behavior and notification delivery still require explicit verification.

## WP3 — Documents

Upload validation and HR review implementation are present in source. Live HR document viewing is confirmed. Upload validation, approval/rejection, re-upload and all associated state transitions still require explicit end-to-end verification.

## WP4 — Stage handlers

Stage-handler implementation is deployed. IT provisioning remains in simulation mode. Policy acceptance, manager introduction and callback-driven progression still require explicit live acceptance tests.

## WP5 — API

HTTP API is deployed behind a Cognito JWT authorizer. Live dashboard access to employee records and employee document viewing are confirmed. The full authorization matrix and every API operation still require regression testing.

## WP6 — New-hire portal

Cognito sign-in and successful portal loading for an existing employee account are confirmed live. The portal includes onboarding progress, document checklist, policy acceptance, equipment/manager status and document-review/replacement UI. Each business action must be exercised against live data before being marked verified.

## WP7 — HR operations dashboard

Cognito HR sign-in, live employee listing and employee document viewing are confirmed live. The dashboard includes employee management, search/filter, employee details, document review controls and related HR operations. Employee creation, approval/rejection and all remaining actions require explicit live acceptance tests.

## Verification record

- Previously recorded offline backend regression suite: **84 tests passed**. These tests use local/mocked services and are not proof of live AWS integration.
- Both frontend production builds passed in the recorded workflow.
- Five backend CloudFormation stacks were previously confirmed deployed.
- On 2 November 2026, manual live checks confirmed HR Cognito sign-in, live employee listing, HR document viewing and employee portal sign-in/loading.

## Production hardening still required

- Development Cognito MFA is OFF. Configure and test TOTP MFA before production.
- IT provisioning is simulated; connect a real provisioning adapter before operational use.
- Configure approved SNS subscriptions and verify delivery.
- Review IAM least privilege, especially employee-table and Step Functions callback permissions.
- Set exact production HTTPS origins for Cognito callback/logout, API CORS and S3 upload CORS.
- Establish data retention, backups, CloudWatch retention/alerts, incident response and cost budgets.
- Review actual AWS charges; deployed services can incur costs.

## Remaining acceptance gates

- [ ] Exercise employee document upload and verify S3 validation plus status polling.
- [ ] Exercise HR approval and rejection with a rejection reason.
- [ ] Verify employee sees the decision and can replace a rejected document.
- [ ] Verify policy acceptance and manager-introduction completion.
- [ ] Verify Step Functions progression and callback behavior.
- [ ] Verify authorization matrix, failure paths, CloudWatch logs and SNS delivery.
- [ ] Run final backend and frontend regression builds.
- [ ] Review AWS spend and complete production security/privacy hardening before any production launch.

## Working agreements

- Preserve working code; do not reset or delete existing work to restart.
- Keep contributor work on isolated feature branches.
- `docs/api-contract.md` and `docs/data-model.md` are the shared contract sources.
- Never expose Step Functions task tokens to browsers or employees.
- Review CloudFormation change sets before executing them.
- Never commit credentials, temporary passwords, JWTs, presigned URLs or employee document contents.
