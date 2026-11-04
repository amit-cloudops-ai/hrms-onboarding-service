# Gate A limitations and Gate B entry criteria

## Gate A — current evaluation boundary

- WP1 identity and Cognito employee mapping are integrated.
- WP2 owns Step Functions sequencing, callback tokens, timeout/retry lifecycle and canonical onboarding stage progress.
- WP3 document collection uses private S3, metadata records, content validation and callback handoff to WP2.
- WP4 IT provisioning and manager introduction are deterministic simulated adapters. Policy acknowledgement is a recorded employee action; it is not a substitute for legal policy approval or HR compliance review.
- WP5 exposes the authenticated HTTP API and HR/employee authorization.
- WP6 employee portal and WP7 HR dashboard are integrated with Cognito and the API.
- GitHub Actions validates the offline test suites, infrastructure templates and frontend builds. This is not proof of live AWS runtime behavior.

## Explicit exclusions

- No live IT asset/identity provisioning provider is configured.
- No live manager calendar/invitation provider is configured.
- Do not use real employee documents or personally identifiable employee records in the evaluation.
- Notification delivery must not be claimed until the SNS/SES subscription is confirmed and a message delivery is observed.
- Cost estimates are planning assumptions; actual AWS account billing must be checked independently.
- The logical ER diagram is a documentation view. Actual primary keys/indexes must be compared to deployed table descriptions before treating it as an authoritative physical schema.

## Gate B entry criteria

1. Formal security and privacy review, retention/deletion policy, access-control audit and incident response ownership.
2. Approved real WP4 provider integrations with secret management, least-privilege IAM, idempotency and failure/reconciliation behavior.
3. Deployed integration tests in a separately approved non-production environment, including Cognito claims/groups, Step Functions callbacks/timeouts/retries, S3 object validation, duplicate/stale events, API authorization and notification delivery.
4. Operational monitoring, alarms, log retention, budget alerts, support/runbook and recovery/replay procedure.
5. Accessibility, mobile/network performance, load and resilience validation.
6. Legal/HR review of policy text, acknowledgement evidence and employee-data handling.
7. Release approval and rollback plan.
