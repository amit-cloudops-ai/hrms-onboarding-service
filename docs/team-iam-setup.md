# Team IAM setup and decisions

**Shared branch:** `team-dev`  
**Repository:** `amit-cloudops-ai/hrms-onboarding-service`  
**AWS region:** `us-east-1`  
**Evaluation target:** 4 November 2026

## Team responsibilities

- **Amit (project owner / `Amit-admin`):** account-level IAM, shared infrastructure, approvals, deployments and cost checks.
- **Gopi — frontend:** frontend S3 bucket, CloudFront deployment/cache invalidation, and read access to API Gateway and Cognito configuration.
- **Sushmitha — backend:** designated backend Lambda functions, document storage, DynamoDB stage/document/equipment tables, workflow operations, related logs and notification operations.
- Each teammate gets an individual IAM user. Never share the owner's credentials.
- Send temporary passwords privately, never in group chat. Never commit passwords, access keys, tokens, or MFA secrets.

## Policy JSON files

- [MFA policy](../infra/iam/policies/hrms-force-mfa.json)
- [Frontend policy](../infra/iam/policies/hrms-frontend-dev.json)
- [Backend policy](../infra/iam/policies/hrms-backend-dev.json)

These are version-controlled working copies of the policy drafts supplied for the IAM console. Do not silently remove planned permissions. Validate and document any targeted change before updating these files.

## Intended setup order

1. Sign in using the existing `Amit-admin` IAM user.
2. Create customer-managed policies named exactly `hrms-force-mfa`, `hrms-frontend-dev`, and `hrms-backend-dev`.
3. Create `frontend-devs` and attach `hrms-force-mfa` plus `hrms-frontend-dev`.
4. Create `backend-devs` and attach `hrms-force-mfa` plus `hrms-backend-dev`.
5. Create individual IAM users `gopi` and `sushmita`, enable console access, and add each to the appropriate group. Do not attach developer policies directly to users.
6. Send each temporary password privately. Each teammate must change it and configure MFA.
7. Test each account in a private browser window, checking both expected access and denied access.
8. Reconcile policy resource names against `infra/template.yaml` and `docs/data-model.md` before deployment.

## Resource-name assumptions in the policy drafts

- Frontend S3 bucket: `hrms-dev-frontend-bucket`
- Backend Lambda functions: `hrms-dev-documents-*`, `hrms-dev-stages-*`
- Lambda execution roles: `hrms-dev-documents-role`, `hrms-dev-stages-role`
- DynamoDB tables: `hrms-dev-documents`, `hrms-dev-equipment`, `hrms-dev-onboarding-stages`
- SNS topic pattern: `hrms-dev-documents-*`
- Region: `us-east-1`

These are names embedded in the draft policies, not proof that the resources exist. Compare them with the SAM template and data model; do not create extra resources merely to satisfy a policy ARN.

## Security review notes

- The MFA policy uses an explicit deny when the request context indicates MFA is absent. Test initial console sign-in and MFA enrollment with a controlled test user before relying on this control.
- The frontend policy retains API Gateway read permissions for REST API and HTTP API resource paths. Validate the actual console operations with Gopi's test account.
- The backend draft contains broad actions (`s3:*`, `lambda:*`, `sns:*`) within resource-name patterns and wildcard scopes for some listing, SES and Step Functions actions. Review and narrow them where feasible after the actual workflow is confirmed.
- Policy summaries are diagnostics, not proof every statement works. Use IAM policy validation and test sessions.
- Do not attach developer policies to `Amit-admin`.
- Never store credentials or secrets in GitHub.

## Branch conventions

- `main`: protected stable branch.
- `team-dev`: shared team integration and team setup documentation.
- `v1-solo`: independent solo work; do not put shared team deliverables here.

## Setup progress

- [x] Supplied JSON policy drafts saved in the shared branch.
- [x] Team responsibilities and setup sequence documented.
- [ ] Create and validate the three IAM policies in AWS.
- [ ] Create groups and attach policies.
- [ ] Create `gopi` and `sushmita` users.
- [ ] Test initial login and MFA enrollment.
- [ ] Test positive and negative permissions.
- [ ] Reconcile policy ARNs with the SAM template/data model.
