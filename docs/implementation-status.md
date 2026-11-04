# Implementation status — team integration

This document tracks the shared team build. Passing unit tests are not a substitute for end-to-end AWS verification.

## Implemented in the integration branch
- WP1 identity service: employee validation, Cognito user creation, immutable Cognito subject linking.
- WP2 workflow support: private document-collection callback token, reminders, synchronous WP4 invocation, correlation-bound completion and failure recording.
- WP3 document service: presigned uploads, metadata, S3 object validation and rejection notification.
- WP4 business adapter: IT provisioning, policy sign-off and manager introduction in explicit simulated mode.
- WP5 authenticated HTTP API: Cognito JWT authorizer, employee/HR authorization and service adapters.
- WP6/WP7: portal and HR dashboard from the merged team frontend PR.

## Integration design
- Document collection waits on the WP2 Step Functions callback token.
- WP3 never receives or stores the task token. The trusted WP5 callback path resumes WP2 after document verification.
- WP2 invokes WP4 synchronously for the three business stages. WP4 receives no task token and does not write canonical lifecycle fields.
- WP2 persists stage lifecycle state and correlates completion with the Step Functions execution.

## Release gates
- Confirm the WP3 document-complete callback is wired to the authenticated WP5/WP2 callback boundary.
- Complete policy-signing persistence and verify its authorization/audit fields.
- Replace frontend mock adapters with the real WP5 API and verify both apps.
- Validate SAM templates and Step Functions ASL in CI.
- Deploy a dedicated team demo stack using MODE=simulated.
- Run a real AWS end-to-end test for employee creation, upload, document verification, stage progression and dashboard visibility.
- Configure approved IT/calendar providers, Cognito MFA, monitoring, backups and operational runbooks before claiming production readiness.

## Mode limitation
IT provisioning and manager introduction are simulated. No approved external provider is configured. The project can be deployed as a controlled demonstration in simulated mode; it is not production-ready for real HR operations.
