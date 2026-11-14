# Team-dev AWS deployment

This creates an isolated evaluation environment, separate from the v1-solo development resources: two private S3 buckets behind CloudFront, a dedicated Cognito user pool, four DynamoDB tables, WP2/WP3/WP4/WP5 Lambda services, Step Functions, SNS and an HTTP API.

## Prerequisites

- AWS CLI authenticated to account 924422830139 with permissions to create CloudFormation/SAM, IAM, Cognito, DynamoDB, Lambda, Step Functions, SNS, S3 and CloudFront resources.
- AWS SAM CLI and Node.js 22/npm.
- An email address for the HR administrator.
- Region us-east-1 (the templates and CSP allowlist target this region).

## Deploy

From the repository root:

```bash
HR_ADMIN_EMAIL="your-hr-admin-email@example.com" \
COGNITO_DOMAIN_PREFIX="hrms-team-924422830139" \
bash infra/deploy-team-dev.sh
```

The script checks the AWS account, verifies the SES sender, warns if SES remains sandboxed, requires all existing team stacks and an existing private same-region SAM artifact bucket, then asks for an explicit DEPLOY confirmation. It reuses the existing `hrms-team-static-hosting` S3 bucket stack and `hrms-team-cloudfront-hosting-v2` distribution stack, then updates the foundation and WP4 → WP2 → WP3 → WP5 with SAM. It builds both frontends with Cognito/API configuration, uploads static assets and invalidates the existing CloudFront distributions. It refuses to create or replace hosting resources automatically if either expected hosting stack is missing or unhealthy. Before deployment it verifies the SES sender identity, warns if SES is still sandboxed, and verifies that the selected `HR_ADMIN_EMAIL` actually belongs to `hr-admins` after assignment.

The earlier `hrms-team-hosting` stack is in `ROLLBACK_COMPLETE` and is not used by the current script. The legacy `infra/team-dev-hosting.yaml` is not the owner template for the currently deployed split hosting topology. Do not deploy that legacy template over the existing resources. Cognito domain prefixes are globally unique. If the suggested prefix is taken, choose another lowercase prefix. If application stacks already exist, inspect them first; set ALLOW_STACK_UPDATES=true only when intentionally updating those stacks.

Optional: set ENABLE_POINT_IN_TIME_RECOVERY=true for DynamoDB tables. It adds ongoing backup cost. The default is false for the evaluation environment.

## Access

The script creates or reuses the supplied HR admin Cognito user and adds it to hr-admins. Cognito sends an invitation email. Complete password setup and sign in to the HR dashboard. HR creates employees; WP1 creates their Cognito accounts and assigns the Employee group.

## Demonstration flow

- Cognito Hosted UI sign-in using authorization code + PKCE.
- HR-only employee creation and dashboard listing.
- Employee self-service resolved by immutable Cognito sub.
- Private, versioned, encrypted S3 document storage with public access blocked and TLS enforced.
- S3 validation → trusted WP2 callback after all required documents are verified.
- WP2 owns callback tokens and canonical lifecycle state.
- WP2 invokes WP4 synchronously for IT provisioning and manager introduction.
- Versioned policy acknowledgement is recorded with timestamp and Cognito subject, then resumes WP2 policy sign-off.
- Both static frontends are served over HTTPS by CloudFront.

## Production limitations

This is a deployable evaluation build, not yet suitable for real employee operations:

- MODE=simulated; real IT account/equipment and calendar/manager-introduction providers do not exist. MODE=real fails closed.
- company_policy v1 is a demo acknowledgement. Production needs the actual policy text/version, evidence retention and legal review.
- TOTP MFA is optional in the demo pool. Require MFA before production and test recovery flows.
- DynamoDB point-in-time recovery is off by default; enable it and define backup/restore tests for production.
- Employee lookup uses the cognito-sub-index GSI. Review table capacity, retention, encryption and access patterns before real data.
- Configure CloudWatch alarms, log retention, tracing, alert routing, S3 access logging, incident response and data-retention/deletion policies before production.
- Browser tokens are held in sessionStorage for this SPA demo. Evaluate a BFF with HttpOnly Secure cookies and perform a strict CSP/XSS review before production.
- Run a live end-to-end test with non-sensitive test identities before presenting it as verified.

Never use real employee documents in the evaluation environment.