# Implementation status — team integration

**Current baseline:** GitHub `team-dev` at `114dfe7`.  
**AWS snapshot:** 4 November 2026, `us-east-1`.  
**Evidence and release gates:** [Final project audit](FINAL-PROJECT-AUDIT.md).

## Implemented components

- **WP1 Identity:** employee input validation, Cognito user creation, Employee group assignment and immutable Cognito-subject linking.
- **WP2 Workflow:** Step Functions orchestration, private callback tokens for document collection and policy sign-off, reminders, synchronous WP4 invocation, correlation-bound stage completion/failure and completion notification.
- **WP3 Documents:** presigned S3 uploads, document metadata, S3 object validation, rejected-document notification and trusted WP2 document callback.
- **WP4 Stages:** versioned policy acknowledgement plus simulated IT provisioning and manager introduction.
- **WP5 API:** Cognito JWT authorizer, HR-group checks, immutable-subject employee authorization and WP3/WP4 service adapters.
- **WP6/WP7:** employee portal and HR dashboard with separate mock and HTTP API adapters.

## AWS evidence

The team foundation, WP2, WP3, WP4 and WP5 CloudFormation stacks were present and in successful stack states in the 4 November audit. The API Gateway routes were configured with a Cognito JWT authorizer. The audited employee had all four stage records complete and all three required documents verified.

The employee record still showed `in_progress` because the completion email had failed. The IAM policy simulator allowed `ses:SendEmail`, while the SES account remained in the sandbox. The exact SES denial cause is not established. See the audit before changing IAM or SES settings.

## Current remediation branch

The branch `feature/final-demo-readiness` separates employee lifecycle completion from email delivery, removes the duplicate completion-email trigger from stage persistence, makes reconciliation report failed notification attempts, and adds a targeted single-employee recovery path. The workflow test suite and the full checks available so far passed on commit `52b3462`; the targeted-reconciliation tests are running in the latest CI workflow. These changes require final CI success and a separately approved deployment before they can be considered active in AWS.

## Remaining verification gates

1. Confirm the exact Cognito username used for HR sign-in is in `hr-admins`; the audit query for `amitmadakatti@gmail.com` returned no groups. If membership is added, sign out/in to refresh the JWT claim.
2. Inspect the running Step Functions execution before taking any action on it.
3. Confirm the WP3 Lambda's `DOCUMENTS_BUCKET`, `SNS_TOPIC_ARN` and `WORKFLOW_FUNCTION_NAME` values.
4. Confirm the API Lambda's `COGNITO_USER_POOL_ID` value.
5. Resolve the SES `AccessDenied` using the exact Lambda log/CloudTrail event and verify the employee recipient is eligible in the SES sandbox.
6. Verify the deployed portal and dashboard use `VITE_USE_MOCK=false` and the deployed API/Cognito endpoints.
7. Reconcile the hosting stack names and the deployment script before another deployment.
8. Run a controlled end-to-end test with non-sensitive test identities after approval.

## Production limitations

- WP4 is deliberately simulated. No approved IT account/equipment or calendar/manager-introduction provider exists.
- The `company_policy` v1 acknowledgement is a demo placeholder, not a legally sufficient production policy record.
- Cognito MFA is optional in the evaluation pool.
- DynamoDB point-in-time recovery was disabled in the audit snapshot.
- CloudWatch alarms, retention, tracing, alert routing, access logging, incident response and deletion/retention policy need production design.
- Browser tokens are held in `sessionStorage`; evaluate a BFF using HttpOnly/Secure cookies and complete an XSS/CSP review before production.
- The checked-in hosting deployment script is not aligned with the currently observed CloudFront v2 and Lambda Function URL stacks.

**Release classification:** deployable simulated mentor demo after the remaining verification gates; not production-ready for real employee operations.
