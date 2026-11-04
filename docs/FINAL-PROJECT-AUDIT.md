# Final project audit — AWS team environment

**Snapshot date:** 4 November 2026  
**Account / region:** `924422830139` / `us-east-1`  
**Repository baseline:** `team-dev` at `114dfe7e512c7502efef14e7db8cfb179dce6446`  
**Audit method:** read-only AWS CLI inventory supplied by the project owner, repository source review, and GitHub Actions status. No AWS resources or employee records were changed during this audit.

## Executive verdict

The team environment has the core AWS services deployed and the onboarding workflow has completed for the audited employee. The employee's four required stages are all `complete`, and all three required documents are `verified`.

The employee record nevertheless remains `in_progress`. The completion notification record is `failed` with `AccessDenied`. The code currently couples employee lifecycle completion to successful SES delivery; this is a correctness defect. The remediation branch separates those two states and makes notification failure non-fatal to the onboarding workflow.

**The project is not yet verified end to end.** In particular, the actual SES denial is not explained by the IAM policy simulator result, the currently running Step Functions execution has not been identified, the deployed frontend configuration has not been inspected, and several deployed Lambda environment variables were omitted from the audit query. Do not describe the system as production-ready.

## 1. AWS infrastructure inventory

| Stack | Observed status | Notes |
|---|---|---|
| `hrms-team-foundation` | `CREATE_COMPLETE` | Cognito and four DynamoDB tables |
| `hrms-team-wp2` | `UPDATE_COMPLETE` | Workflow Lambda, Step Functions and reminder SNS topic |
| `hrms-team-wp3` | `CREATE_COMPLETE` | Private document bucket, document Lambda, EventBridge rule and rejection SNS topic |
| `hrms-team-wp4` | `CREATE_COMPLETE` | Simulated stage adapter Lambda |
| `hrms-team-api` | `CREATE_COMPLETE` | HTTP API, JWT authorizer, routes and API Lambda |
| `hrms-team-cloudfront-hosting-v2` | `CREATE_COMPLETE` | Portal and dashboard CloudFront distributions |
| `hrms-team-static-hosting` | `CREATE_COMPLETE` | Additional Lambda Function URL hosting path |
| `hrms-team-hosting` | `ROLLBACK_COMPLETE` | Earlier hosting stack; its resources were deleted |

The two CloudFront URLs in the snapshot are:

- Employee portal: `https://d1aozjt2t5kjtv.cloudfront.net`
- HR dashboard: `https://d2i8jrjhff3cr3.cloudfront.net`

The separate static-hosting stack also exposes two Lambda Function URLs. The API CORS and Cognito callback/logout allowlists include both hosting paths and local development origins. The project should designate one canonical public hosting path and remove stale origins only after confirming which frontend deployment is in use.

**Deployment-script defect — corrected in the remediation branch:** the original script expected the old `hrms-team-hosting` stack and its outputs. The audit shows that stack is `ROLLBACK_COMPLETE`, while the deployed CloudFront stack is named `hrms-team-cloudfront-hosting-v2` and the S3 buckets are owned by `hrms-team-static-hosting`. The remediation branch now reuses those two existing stacks, verifies their health and refuses to create/replace hosting resources automatically. This script change passed the CI shell-syntax check; it has not been run against AWS.

## 2. Identity, API and authorization

**Verified from AWS inventory:**

- Cognito user pool: `us-east-1_GUx6uZsFJ`
- Public app client: `5659oiu8c5v4q83cq8j4uepb4n`
- HR group: `hr-admins` exists. However, the audit's `admin-list-groups-for-user` query for `amitmadakatti@gmail.com` returned an empty list. Membership for the account actually used to sign in is therefore **not verified** and may be missing.
- API Gateway HTTP API: `m040hqrfd4`
- API authorizer: Cognito JWT, issuer bound to the user pool and audience bound to the public app client.
- All nine listed application routes use the JWT authorizer.
- The API code authorizes employee self-service by immutable Cognito `sub` and checks the HR group for administrative operations.

The deployed routes cover employee creation/listing, profile and progress reads, document status/upload URL, policy sign-off and the HR stage callback override.

**Still to verify:** (1) identify the exact Cognito username used for HR dashboard sign-in and confirm it belongs to `hr-admins`; the queried `amitmadakatti@gmail.com` account had no groups in the audit output. If it is the login account, add it to `hr-admins` and sign out/in to obtain a JWT with the updated group claim. (2) The audit's Lambda environment query did not include `COGNITO_USER_POOL_ID` for the API Lambda. The API template requires it for WP1 user creation. Confirm the actual deployed value before testing employee creation.

## 3. Workflow and stage state

The active state machine is `arn:aws:states:us-east-1:924422830139:stateMachine:hrms-team-onboarding`.

Its definition contains the four intended stages:

1. `document_collection` — WP2 task-token callback, resumed after WP3 verifies all required uploads.
2. `it_provisioning` — synchronous WP4 invocation.
3. `policy_signoff` — WP2 task-token callback after versioned policy acceptance.
4. `manager_intro` — synchronous WP4 invocation.

The audited employee has all four stage records in DynamoDB with status `complete`. The three required document metadata records are `verified`. The corresponding Step Functions execution is `SUCCEEDED`.

A second execution, `9dbad4cb-09bd-40a4-83c5-c13d1c66f35a`, was `RUNNING` at audit time. Its input and employee association were not included in the report. Do not stop or restart it until its execution input and current stage are inspected.

WP4 is explicitly configured as `MODE=simulated`. IT account/equipment provisioning and manager introduction return demonstration results; they do not create real third-party accounts, allocate actual equipment, or schedule a real calendar event. This is acceptable for a clearly labelled mentor demo, not for live HR operations.

## 4. Employee completion and SES incident

For the audited employee record:

- All four onboarding stage records: `complete`
- Required document records: 3 of 3 `verified`
- Employee lifecycle status: `in_progress`
- Completion email status: `failed`
- Stored completion email error code: `AccessDenied`

The workflow Lambda's inline IAM policy contains `ses:SendEmail` scoped to the verified sender identity. The IAM policy simulator returned `allowed` for that exact action/resource pair. The Lambda role has no permissions boundary in the audit output.

SES account state:

- Sending enabled: true
- Production access: false (SES sandbox)
- Sender identities `amitmadakatti@gmail.com` and `amitpm.work@gmail.com`: verified
- Daily quota: 200; maximum send rate: 1 per second

The SES sandbox can restrict recipients to verified identities. The employee recipient address was not included in the audit query, so recipient verification is not established. However, the stored error is `AccessDenied`, and the IAM simulation is allowed; neither fact alone proves the underlying SES denial reason.

The audit's CloudWatch filter returned no matching `AccessDenied` log events. The exact SES request failure therefore remains **unresolved**. Do not add another broad IAM policy. Retrieve the specific Lambda invocation log/CloudTrail event and verify the recipient identity before changing permissions or requesting SES production access.

### Code correction on the remediation branch

- Persist employee `status=complete` and `onboarding_completed_at` once all required stages are complete, independently of email delivery.
- Keep notification delivery state separate: `sending`, `sent`, or `failed`.
- Treat definitive SES errors as notification failures that can be retried without restarting onboarding.
- Keep ambiguous network outcomes in `sending` so automatic retries cannot duplicate a message.
- Keep one notification invocation point: the Step Functions `WorkflowComplete` state. Stage completion only persists stage lifecycle state.
- Make the reconciliation operation report failed sends rather than returning a misleading success.

These changes do not resend email, alter the audited employee record, or deploy anything to AWS. The workflow unit tests passed in GitHub Actions on commit `a858f635b09c7e85db775cc729e26df3a3122df1`; the deployment-script syntax check passed on commit `dbf61c630cbd5e01d8b91fb1159df752608361cd`. The latest documentation-only CI run was still in progress when this audit note was updated.

## 5. Document storage and DynamoDB

The four DynamoDB tables are active and use `PAY_PER_REQUEST` billing:

- `hrms-team-employees`
- `hrms-team-onboarding-stages`
- `hrms-team-documents`
- `hrms-team-equipment`

The employee table has `status-index` and `cognito-sub-index`; the latter supports immutable-subject lookup.

The document bucket has S3 Block Public Access enabled and default SSE-S3 AES-256 encryption. Its CORS configuration allows PUT from the portal CloudFront origin and `http://localhost:5173`. The EventBridge object-created integration is present in the bucket notification configuration and the WP3 stack has an enabled object-created rule.

The audit reports DynamoDB continuous-backup status as enabled but point-in-time recovery as disabled for the tables. Recovery settings should be deliberately selected before production; do not enable PITR without reviewing its ongoing cost.

**Environment values still to verify:** the audit's Lambda query omitted WP3's `DOCUMENTS_BUCKET`, `SNS_TOPIC_ARN` and `WORKFLOW_FUNCTION_NAME`, and omitted the API Lambda's `COGNITO_USER_POOL_ID`. The WP3 template requires these values. Confirm them before claiming the document callback and employee-creation paths are fully wired in the deployed environment.

## 6. Frontend and hosting

Both frontend codebases support a real HTTP API adapter and a mock adapter. Their selection logic defaults to mock mode unless `VITE_USE_MOCK=false`. The checked-in deployment script writes `VITE_USE_MOCK=false` and API/Cognito settings before building, but the audit did not inspect the actual deployed frontend bundles or their embedded configuration.

The deployment script also targets the rolled-back hosting stack rather than the currently observed v2 CloudFront stack. This is a release-blocking infrastructure/documentation mismatch. No hosting stack should be recreated, deleted, or updated until the canonical hosting path and template ownership are settled.

## 7. Repository and CI

The local audit checkout was clean on `team-dev` at `a752f72`. The GitHub `team-dev` branch is one commit ahead at `114dfe7` (`Fix automatic onboarding completion email`). The latest GitHub Actions run for that commit completed successfully.

Use the GitHub `team-dev` head as the integration baseline. The local checkout in the audit report is stale by one commit; do not push from it until it has been fast-forwarded and its working tree rechecked.

Documentation gaps found in the repository include a placeholder architecture page and data-model/API-contract examples still naming `hrms-dev-*` tables while the deployed team environment uses `hrms-team-*`.

## 8. Release gates

| Gate | Status | Required evidence |
|---|---|---|
| Core AWS stacks exist | Verified | CloudFormation inventory |
| Cognito JWT authorization on API routes | Verified | API Gateway route/authorizer inventory |
| HR dashboard login user belongs to `hr-admins` | Unverified; queried `amitmadakatti@gmail.com` had no groups | Check the actual login username; add to group only if missing, then obtain a fresh token |
| All four audited employee stages complete | Verified | Consistent DynamoDB query |
| Required documents verified | Verified | Document metadata query |
| Employee lifecycle status independent of SES | Implemented in remediation branch; workflow unit tests passed; not deployed | Later approved deployment + read-only record check |
| SES completion email actually delivered | Unverified / failed in snapshot | CloudWatch/CloudTrail cause, recipient verification, successful test to verified recipient |
| WP3 callback environment fully configured | Unverified | Read actual WP3 Lambda environment variables |
| API Cognito pool environment configured | Unverified | Read actual API Lambda environment variables |
| Second running execution understood | Incomplete | Describe execution input/current state; do not stop it blindly |
| Frontends use live API rather than mock data | Unverified | Inspect deployed build configuration and exercise both apps |
| Hosting deployment script matches deployed stack | Script corrected in remediation branch; not run against AWS | Review script diff, then approve deployment separately |
| Real IT/calendar integrations | Intentionally simulated | Keep clearly labelled for mentor demo |
| Production operational readiness | Incomplete | MFA policy, recovery/retention, monitoring, backups, incident runbooks and approved real providers |

## 9. Safety and deployment policy

Until the release gates are closed:

- Do not recreate, delete, or update CloudFormation stacks.
- Do not modify IAM policies broadly to chase the SES error.
- Do not restart, stop, or reseed onboarding executions.
- Do not rewrite existing employee or document records to make the dashboard appear complete.
- Do not enable paid backup/hosting features without reviewing cost.
- Validate code and templates locally/through CI first; deploy only after a separate explicit approval.

The target for this branch is a reliable, reproducible **simulated mentor demonstration** with clear production limitations—not a claim that real IT provisioning or production HR operations are already implemented.
