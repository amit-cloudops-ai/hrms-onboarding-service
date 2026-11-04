# Gate A evaluation pack

This folder is the presentation companion for the current `team-dev` evaluation release. It is not a production-readiness certificate. The workflow is deployed in `MODE=simulated`; IT provisioning and manager-introduction actions are simulated.

## Current verified state

- GitHub Actions run [41770787762](https://github.com/amit-cloudops-ai/hrms-onboarding-service/actions/runs/41770787762) passed on team-dev commit `4671aafeee44a8d371358990f7985110db8b4b45`.
- The run validates workflow JSON, all four SAM templates, runs the WP1/WP2/WP3/WP4/WP5 backend test suites, lints and builds both frontends, audits production dependencies, lints the team CloudFormation templates, syntax-checks the deployment script, and builds all backend SAM applications without deploying.
- Manual UI evidence already captured by the project team demonstrates HR admin access, employee self-service, new-hire creation, document status, policy sign-off interaction and HR dashboard progress. Put redacted approved screenshots under `docs/evidence/`; do not commit real employee information.
- The CI run is offline/mocked/template validation. It does not prove a new AWS deployment or live notification delivery.

## Evaluation sequence (8–10 minutes)

1. **Problem and objective (45 sec):** explain the fragmented new-hire handoff and the goal of one identity-backed onboarding journey.
2. **Architecture (60 sec):** use `docs/architecture.mmd`; explain Cognito → API Gateway/JWT → WP5 API → WP1 identity / WP2 Step Functions; DynamoDB is the system of record; S3 stores private documents; SNS handles alerts.
3. **HR creates a synthetic employee (90 sec):** show HR login and creation. Highlight the employee UUID, Cognito invitation and HR-admin-only route.
4. **Employee self-service (60 sec):** sign into the portal as the synthetic employee. Explain that the backend binds the signed-in Cognito subject to the employee, rather than trusting a browser-supplied employee identity.
5. **Documents (90 sec):** upload dummy ID proof, degree certificate and signed offer letter. Show status and describe presigned S3 upload plus server-side content validation. Never reveal a presigned URL.
6. **Policy and workflow (90 sec):** show the policy sign-off action. Open the Step Functions execution if one exists and show the execution path and persisted stage states. Explain that document collection and policy sign-off use callback waits, and that the callback token remains server-side.
7. **HR progress / persistence (60 sec):** return to the dashboard, refresh, and show persisted progress.
8. **Security, limitations and next gate (60 sec):** mention Cognito subject checks, HR-admin group authorization, private encrypted S3, and least-privilege IAM. Clearly state the WP4 business steps are simulated; real IT/manager integrations and Gate B controls are not claimed.

## Evidence checklist

Capture only redacted / synthetic evidence:

- `01-hr-dashboard.png` — HR pipeline with synthetic employee.
- `02-employee-portal.png` — employee checklist and profile.
- `03-document-status.png` — required document statuses.
- `04-step-functions-execution.png` — execution graph and successful state history.
- `05-stage-records.png` — four persisted stage records with IDs redacted.
- `06-notification.png` — confirmed SNS subscription or test delivery; redact email address.
- `07-refresh-persistence.png` — portal/dashboard after refresh.
- `08-github-ci.png` — successful CI run.

A screenshot of an SNS topic or subscription pending confirmation is not proof of delivered email. Do not label it as delivery evidence.

## Live demo fallback

If a live screen fails, use the pre-captured screenshot and explain what it proves. Do not improvise with AWS console mutations, deploy stacks, reset accounts or use actual employee documents during the evaluation.

## What not to claim

- Do not say the full platform is production-ready.
- Do not say IT asset provisioning or manager-calendar introduction is live; WP4 is simulated.
- Do not claim notification delivery without a confirmed subscription and delivery record.
- Do not claim the CI run is a live AWS integration test.
- Do not show passwords, Cognito tokens, JWTs, task tokens, presigned URLs, account IDs, private employee information or secrets.
