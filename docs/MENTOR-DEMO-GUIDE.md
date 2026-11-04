# Gate A — Mentor demonstration guide

## What this release is

This is an evaluation deployment of the employee onboarding identity spine. It demonstrates HR administration, employee identity, document collection, policy acknowledgement, persisted onboarding progress, and simulated IT/manager stages.

**Important boundary:** WP4 IT provisioning and manager introduction run in `MODE=simulated`. Do not describe these as real integrations or use real employee documents. Gate A is not Gate B production approval.

## Demo preparation

1. Open the HR dashboard and employee portal in separate browser windows or profiles.
2. Sign in to the HR dashboard with the HR administrator account.
3. Have a test employee account ready. Use synthetic data and dummy documents only.
4. Confirm the HR dashboard and employee portal are using the same deployed environment.
5. Keep the Step Functions console open in a separate tab, filtered to the onboarding state machine.
6. Keep the relevant CloudWatch log groups available for the API, workflow, documents and stage Lambdas.
7. Do not show passwords, access tokens, presigned URLs, task tokens, private employee data or AWS account credentials.

## Suggested 8–10 minute presentation

### 1. Architecture (1 minute)

Explain that Cognito authenticates users, API Gateway protects the API, Lambda functions implement bounded work packages, DynamoDB stores canonical employee and stage records, Step Functions coordinates the long-running process, and S3 stores private documents. SNS/SES handle notifications.

### 2. HR creates a new hire (1–2 minutes)

- Sign in as HR.
- Register a synthetic employee with name, email, department, role, manager, joining date and employment type.
- Show the new employee in the HR pipeline.
- Explain the UUID employee record and Cognito identity association.

### 3. Employee signs in (1 minute)

- Open the employee portal as the new hire.
- Show that the employee sees their own profile and onboarding checklist.
- Explain that the backend binds the Cognito subject to the canonical employee record; the browser does not choose its own employee identity.

### 4. Documents (1–2 minutes)

- Upload synthetic ID proof, degree certificate and signed offer letter.
- Show document status in the employee portal and HR dashboard.
- Explain presigned S3 upload, server-side encryption, file validation and the WP2 completion callback.
- Show a successful validation record/notification if available in the deployed environment.

### 5. Workflow and stages (2 minutes)

- Show the Step Functions execution and stage order: Document Collection → IT Provisioning → Policy Sign-off → Manager Intro.
- Show policy acceptance and the simulated IT/manager stage outcomes.
- Explain that Step Functions owns the orchestration and DynamoDB stores the visible stage state.

### 6. HR visibility and persistence (1 minute)

- Return to the HR dashboard.
- Show the same employee and persisted stage progress.
- Refresh both applications and show that progress remains.

### 7. Security and limitations (1 minute)

- Explain HR-admin group checks and employee Cognito-sub ownership checks.
- State clearly that WP4 uses simulated adapters in Gate A.
- State that production integrations, production controls and Gate B work are out of scope.

## Evidence to capture for the submission

Save redacted screenshots under `docs/evidence/` (never commit credentials or personal data):

- `01-hr-dashboard.png` — HR pipeline with synthetic employee.
- `02-employee-portal.png` — employee profile and progress.
- `03-document-status.png` — all three required document states.
- `04-step-functions-execution.png` — execution graph and successful state history.
- `05-stage-records.png` — persisted four-stage DynamoDB state, with identifiers redacted.
- `06-notification.png` — SNS/SES evidence with addresses redacted.
- `07-refresh-persistence.png` — portal/dashboard after refresh.

Also record the execution start/end timestamps, synthetic employee ID, region, expected/actual outcomes and any failed/retried steps in `docs/GATE-A-SMOKE-TEST.md`.

## Mentor Q&A

**Why Step Functions?** Onboarding spans days and waits for human actions. Step Functions provides durable orchestration, retries, timeouts and execution history without keeping a Lambda running.

**Why Cognito subject instead of email?** Email is mutable; Cognito `sub` is the stable identity claim used to bind the authenticated principal to the employee record.

**Why DynamoDB?** The workflow is key-oriented and serverless; employee, stage and document records can be accessed by known partition/sort keys without managing database servers.

**What is simulated?** IT asset provisioning and manager introduction. These are deterministic evaluation adapters, not live integrations.

**What remains for production?** Real provider integrations, security/privacy review, operational monitoring and recovery, retention policy, load/accessibility testing, and formal release approval.
