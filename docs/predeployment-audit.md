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

## Automated read-only inventory

Run the repository script from a terminal that has the AWS CLI configured for the intended account:

```bash
bash scripts/aws_predeploy_audit.sh
```

It reports the current identity, region, CloudFormation stack metadata, expected table key/index metadata, Cognito pool names/IDs, matching Lambda/state machine/SNS names, HRMS-like bucket security metadata (not objects), and a recent Cost Explorer view when permission is available. To inspect one selected Cognito pool's settings, groups, and app-client metadata without printing secrets, set `COGNITO_USER_POOL_ID` before running it. Permission-denied or missing-resource output needs human interpretation; it is not evidence that a resource is absent.

**The script has not been run against the target AWS account from this session.** The repository-side static review cannot establish the real account ID, resource existence, index schemas, live settings, or actual costs.

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

1. **Cognito PKCE and JWT wiring is now implemented in both frontends but not live-verified.** Each app uses a public Cognito app-client ID, authorization-code grant with PKCE, session-scoped token storage/refresh, and bearer ID tokens. Confirm the real hosted-login domain, token endpoint CORS, callback/sign-out allowlists, supported scopes, and that the app client has no secret.
2. **Current employee lookup is implemented as `GET /employees/me`.** It maps the verified JWT `sub` to one employee record and refuses missing or ambiguous links. The route currently performs a paginated DynamoDB scan on `cognito_sub`; verify `dynamodb:Scan` permission. Before meaningful scale, review adding a dedicated `cognito_sub` GSI and migrating the endpoint to `Query`.
3. **HR create-employee request matches the identity service schema:** `full_name`, `email`, `role`, `department`, `joining_date`, and `employment_type`. Confirm the deployed API's `201 { employee: ... }` response and subsequent list refresh.
4. **Upload completion is asynchronous.** The browser checks the presigned PUT status and refreshes document status, but S3-trigger validation may finish after that first refresh. A live acceptance test must verify that the UI visibly converges to `verified` or `rejected`, including retry after a rejected file or an expired link.
5. **CORS origins are parameterized in the API template.** Defaults are localhost portal `:5173` and HR dashboard `:5174`; override both for deployed origins. The document bucket's `UploadAllowedOrigin` must exactly match the deployed portal origin. No production URLs have been selected or verified.
6. **Journey regression coverage has been added.** The new offline integration tests exercise the four-stage ASL order, 24-hour timeout/reminder loop, document-stage gate, invalid upload rejection/notification, all three policy acceptances, manager-admin completion, and expired callback failure. They use mocks; they do not establish live Step Functions, S3 events, Cognito, or SNS behavior.
7. **Actual DynamoDB table existence/schema and the documented `status-index` remain unverified.** Templates reference existing tables. Verify exact keys, indexes, billing mode, encryption, deletion protection/PITR as applicable, and IAM access before deploying.
8. **Fixed resource names and IAM permissions need a change-set review.** Confirm `hrms-dev-*` Lambda/state-machine/SNS names will not conflict. Review callback wildcard permissions, S3 object scope, adapter Lambda invocation targets, and any resource replacement.
9. **Real AWS costs are unknown until the target account is inspected.** Inspect recent Cost Explorer figures and budget configuration; include Lambda, API Gateway, Step Functions Standard, DynamoDB, S3 requests/storage/versions, CloudWatch Logs, and SNS. Cost Explorer can lag and does not predict future usage.

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
