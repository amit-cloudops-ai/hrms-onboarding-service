# HRMS Onboarding Service — Project Goal and Definition of Done

## Product outcome

Deliver a secure, auditable, reliable employee-onboarding system that lets an HR administrator create and manage a new hire, lets the employee complete required onboarding tasks, and orchestrates document verification and business stages through one consistent workflow. HR must be able to see the authoritative status, outstanding actions, failures, and completion history without relying on manual coordination or mock data.

The project is complete only when the acceptance criteria below are evidenced by automated tests, deployed-environment tests, and operational documentation. A successful build or CloudFormation deployment alone is not completion.

## Scope and system boundaries

- WP1 — Identity and access: Cognito authentication, role/group authorization, employee-to-identity binding, and least-privilege access.
- WP2 — Workflow orchestration: authoritative stage lifecycle, ordering, retries/timeouts, reminders, idempotency, callback/task-token handling, and audit events.
- WP3 — Documents: secure upload, file validation, metadata/status persistence, rejection handling, and trusted workflow completion callback.
- WP4 — Business stage adapters: IT provisioning, policy acknowledgement/sign-off, and manager introduction. Simulated adapters are acceptable only in the evaluation environment; production completion requires configured real providers or explicitly approved operational adapters.
- WP5 — API: authenticated and authorized API boundary, input validation, safe errors, and consistent contracts.
- WP6 — Employee portal: employee can see and complete only their own onboarding tasks and documents.
- WP7 — HR dashboard: authorized HR users can create/manage employees and monitor onboarding status and exceptions.

## Gate A — Mentor evaluation environment

The isolated `team-dev` environment is ready for mentor evaluation only when all of the following are true:

1. All team work is integrated on `team-dev`; CI passes for backend tests, frontend lint/build, SAM validation/build, infrastructure lint, and deployment-script syntax.
2. The environment is deployed into the intended AWS account and region using dedicated `hrms-team-*` stacks, tables, buckets, Cognito resources, API, workflow, and CloudFront distributions. Existing `hrms-dev` resources remain unchanged.
3. HR administrator invitation and login work; HR can create a test employee; the employee can activate their account and sign in.
4. Employee authorization is enforced server-side: an employee cannot read or mutate another employee's profile, documents, stages, or workflow. HR-only operations reject employee tokens.
5. A document can be uploaded through the portal, validated by WP3, persisted with the correct status, and cause WP2 to resume through the trusted callback path. Invalid/rejected documents are visible to HR and generate the configured HR notification.
6. Policy acknowledgement advances the correct stage. WP2 invokes WP4 for the simulated IT and manager-introduction stages and records their outcomes.
7. The HR dashboard reflects the same persisted stage state as the workflow and employee portal. Refreshing either frontend does not lose progress.
8. SNS email subscriptions are confirmed. Logs for a test employee can be correlated across API, WP2, WP3, and WP4 without exposing credentials, document contents, or task tokens.
9. A smoke-test record is retained with timestamps, test employee identifier, expected/actual results, and any known limitations.
10. Teardown instructions and a cost/resource inventory are documented. No team stack is removed until evaluation sign-off.

**Evaluation-mode constraints:** WP4 may run with `Mode=simulated`. Demo policy text must be labelled as non-legal placeholder content. HR email notifications do not count as employee-specific reminder delivery. The evaluation gate must not be represented as production approval.

## Gate B — Production release

Production release requires all Gate A criteria plus:

### Security and privacy
- Threat model and data classification completed; collect only required employee data.
- Enforce tenant/organization boundaries if multiple organizations are supported; otherwise document the single-organization boundary.
- Verify authorization for every API operation and object access, including IDOR/BOLA tests and negative tests.
- Enforce secure session/token handling, short-lived credentials, MFA policy for privileged HR users, account recovery controls, and secrets management/rotation.
- S3 uploads enforce size/type constraints, malware scanning or an approved equivalent, encryption, private access, retention/deletion rules, and auditable access.
- Define privacy notice, consent/legal basis where applicable, retention schedule, employee data export/correction/deletion process, and incident/breach response aligned with applicable Indian law and contractual obligations.
- Complete dependency, container, infrastructure, and application security scans; resolve critical/high findings or document an approved risk exception.

### Workflow correctness and resilience
- Idempotency for employee creation, document processing, callbacks, and stage transitions.
- Explicit retry, timeout, compensation, dead-letter/recovery, and manual-replay procedures.
- No task token or secret in logs, browser state, API responses, or WP4 payloads.
- Concurrent update and duplicate event tests; workflow state remains consistent after Lambda/API failures.
- Real WP4 integrations configured and tested for IT provisioning and manager introduction, or a formally approved human-operated adapter with ownership and SLA.
- Approved policy content, versioning, acceptance evidence, timestamps, and audit retention; legal review completed where required.
- Employee-specific reminder channels and delivery/failure tracking implemented if required by the business.

### Operations and release controls
- Production environment isolated from development with infrastructure-as-code, least-privilege deployment roles, protected branches, reviewed changes, and repeatable release/rollback.
- Centralized structured logs, correlation IDs, dashboards, actionable alarms, error budgets/SLIs, and on-call ownership.
- Backup/restore and disaster-recovery exercises with agreed RPO/RTO; point-in-time recovery enabled where justified.
- WAF/rate limiting and abuse controls for public endpoints; security headers and CORS restricted to approved origins.
- Load, performance, accessibility, browser/device, and end-to-end regression tests completed against agreed targets.
- Runbooks for deployment, rollback, incident response, user support, data recovery, and routine operations.
- Product owner and operational owner sign off on the release.

## Evidence required to close the project

Maintain these artifacts in the repository:
- Architecture and trust-boundary diagram.
- API and WP2/WP3/WP4 integration contracts.
- Automated test results and security scan reports.
- Environment/resource inventory and deployment/rollback instructions.
- End-to-end smoke-test report for Gate A and production acceptance report for Gate B.
- Known-issues/risk register with owner and target date.
- Operational runbooks and final sign-off.

## Current status at the time this document was added

This repository has CI-validated integration work and a deployment path for the isolated evaluation environment. Gate A is **not complete** until the environment is deployed and the end-to-end smoke test is evidenced. Gate B is **not complete**: real IT/calendar integrations, production policy content and legal review, employee-specific reminders, production operational controls, and live-environment verification remain outstanding.

Do not mark either gate complete based solely on a green CI run.
