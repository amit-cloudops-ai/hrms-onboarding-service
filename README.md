# Smart Employee Onboarding & Identity Service

Automated new-hire onboarding on AWS: from offer acceptance to a fully ready Day 1. This project provides the identity and workflow foundation for employee onboarding, with an employee self-service portal and an HR operations dashboard.

**Development evaluation:** 4 November 2026 | **AWS region:** `us-east-1`

## What it does

1. Creates an employee profile and Cognito identity.
2. Orchestrates onboarding stages with AWS Step Functions.
3. Collects and validates employee documents in private S3 storage.
4. Supports HR document review and employee resubmission flows.
5. Coordinates IT provisioning, policy sign-off and manager introduction.
6. Provides separate web applications for employees and HR administrators.

## Repository layout

| Folder | Purpose |
|---|---|
| `services/identity` | Employee profile and Cognito identity (WP1) |
| `services/workflow` | Step Functions orchestration (WP2) |
| `services/documents` | Document upload, validation and review (WP3) |
| `services/stages` | IT provisioning, policy and manager stages (WP4) |
| `services/api` | API Gateway routes and authorization (WP5) |
| `frontend/portal` | New-hire portal (WP6) |
| `frontend/hr-dashboard` | HR administrator dashboard (WP7) |
| `infra` | AWS infrastructure definitions |
| `docs` | Architecture, contracts and implementation records |

## Live verification

On 2 November 2026, the deployed application was manually exercised:

- HR administrator Cognito sign-in succeeded.
- The HR dashboard loaded employee records through the live API (demo mode disabled).
- HR employee document viewing worked.
- An existing employee account successfully signed in to and loaded the employee portal.

These checks confirm core live access paths. They do not, by themselves, certify every onboarding workflow or production readiness. See [implementation status](docs/implementation-status.md) for the verified checks and remaining acceptance gates.

## Deployment and local setup

Read [the solo implementation and AWS deployment record](docs/solo-implementation-and-aws-deployment-record.md), [the API contract](docs/api-contract.md), and [Northstar custom authentication](docs/northstar-custom-auth.md) before changing deployment or authentication behavior.

Create local frontend environment files from the supplied examples. Do not commit `.env.local`, credentials, temporary passwords, JWTs, presigned URLs or employee document contents.

## Deployment status

The five development backend stacks (foundation, stages, documents, workflow and API) have been deployed in `us-east-1`. Core live HR and employee portal access paths were manually verified on 2 November 2026. Full workflow acceptance and production hardening remain outstanding; this is not yet a production release.

## Contribution rules

- Preserve working code and use isolated feature branches.
- Do not push directly to `main`.
- Follow `CONTRIBUTING.md`.
- Treat `docs/api-contract.md` and `docs/data-model.md` as shared contracts.
- Review CloudFormation change sets before execution.
