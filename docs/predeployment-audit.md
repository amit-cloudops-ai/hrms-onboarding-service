# Pre-deployment audit — solo onboarding stack

**Scope:** static review of `v1-solo` templates and contracts. This is not a live AWS account audit. No AWS resources were queried, created, modified, or deleted during this review.

## Decision

**Do not deploy yet.** The two frontends now pass production builds, but live authentication and API integration are not complete, the end-to-end onboarding journey has not been exercised, and the target AWS account has not been inspected. The checks below are deployment gates, not assumed facts.

## Known target configuration from repository contracts

- Intended region: `us-east-1` (see `docs/api-contract.md` and `docs/solo-integration-runbook.md`).
- Existing DynamoDB tables expected by defaults:
  - `hrms-dev-employees` — partition key `employee_id`; the data model documents a `status-index` GSI.
  - `hrms-dev-onboarding-stages` — partition key `employee_id`, sort key `stage`.
  - `hrms-dev-documents` — partition key `employee_id`, sort key `doc_type`.
  - `hrms-dev-equipment` — partition key `asset_id`.
- Cognito: an existing user pool, app client, and `hr-admins` group are assumed by the integration runbook. Their IDs, configuration, token claims, MFA/password policies, and invitation delivery have not been verified.
- Lambda names in the templates are fixed `hrms-dev-*` names. Confirm they do not conflict with existing functions before deploying.
- The document template creates a private, encrypted, versioned S3 bucket and uses an exact upload-origin parameter for CORS.
- The workflow uses Step Functions Standard callbacks and SNS topics. IT provisioning is intended to run in simulation mode for the first test.

## Required live-account inspection

Run only after explicitly selecting the intended AWS profile. These are read-only checks:

```bash
aws sts get-caller-identity
aws configure get region
aws cloudformation list-stacks --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE UPDATE_ROLLBACK_COMPLETE
aws dynamodb list-tables --region us-east-1
aws cognito-idp list-user-pools --max-results 60 --region us-east-1
aws lambda list-functions --region us-east-1 --query 'Functions[?starts_with(FunctionName, `hrms-dev-`)].{Name:FunctionName,Runtime:Runtime}'
aws stepfunctions list-state-machines --region us-east-1
aws s3api list-buckets --query 'Buckets[].Name'
aws sns list-topics --region us-east-1
```

For each existing DynamoDB table, use `describe-table` and verify exact key schema, billing mode, GSIs, encryption, and point-in-time recovery. For Cognito, inspect the selected pool, app client, and group. For existing CloudFormation stacks, inspect resources and outputs before proposing updates. Do not print credentials, JWTs, presigned URLs, or document contents into logs or chat.

## Static integration findings that must be closed before deployment

1. **Cognito sign-in is not wired into either frontend.** The API requires a JWT in the `Authorization: Bearer` header. Both frontend request helpers currently call the protected API without adding a Cognito token.
2. **Employee portal identity resolution is not production-ready.** It uses a configured employee ID instead of resolving the authenticated user's own employee record. Do not expose a shared portal configuration as a multi-employee self-service app until this is corrected.
3. **The HR create-employee request was corrected to the backend schema** (`full_name`, `joining_date`, `employment_type`). Verify the latest frontend build and live response mapping after this change.
4. **Frontend behavior must handle API error envelopes and refresh stage/document state.** A successful upload URL response is followed by a direct S3 PUT; check the PUT response and then poll/refresh document status until it is verified or rejected.
5. **S3 CORS origin must exactly match the eventual portal origin.** No production URL has been selected or verified.
6. **Workflow callback chain needs real integration testing.** Verify stage token storage/clearing, timeout/reminder behavior, document validation retries, all three policy acceptances, manager-intro admin completion, and the final workflow execution status.
7. **DynamoDB table existence/schema and the documented `status-index` are unverified.** The current SAM templates reference existing tables rather than creating them. Do not assume the data model document matches the actual account.
8. **Template names and permissions require a change-set review.** In particular, review IAM wildcards used for Step Functions callback submission, Lambda invocation targets, S3 object access, and any replacement/deletion of existing resources.
9. **Cost cannot be responsibly estimated from templates alone.** Inspect actual usage and current AWS pricing for Lambda, Step Functions, S3 versions/requests, DynamoDB capacity, CloudWatch logs, and SNS. Set a budget alert before a test deployment.

## Deployment gate

Proceed to an AWS test deployment only when all boxes can be checked with evidence:

- [ ] Both frontend production builds pass on the latest commit.
- [ ] Cognito sign-in, token refresh/expiry, sign-out, and role-specific UI/API calls are implemented and tested.
- [ ] Employee identity maps to the authenticated Cognito `sub`; employees cannot access another employee's records.
- [ ] A reproducible local/mocked end-to-end test covers success, invalid upload, retry, expired callback, and forbidden access.
- [ ] Live account/region, existing resources, schemas, stack names, and cost guardrails have been checked.
- [ ] SAM validation and reviewed CloudFormation change sets show no unintended replacements or destructive changes.
- [ ] Test portal origin, notification recipients, simulation mode, rollback plan, and cleanup plan are explicitly set.

## Rollback and cleanup guardrails

- Never delete or replace an existing table, Cognito pool, or bucket simply to make a deployment pass.
- Review every CloudFormation change set before executing it.
- Preserve existing data; use dedicated test employee records and test documents.
- The document bucket is versioned. Cleanup must account for object versions and delete markers before bucket deletion.
- Delete only stacks created for this approved test, in reverse dependency order, after reviewing each stack's resources.
- No deployment, stack deletion, or other AWS mutation is authorized by this document.
