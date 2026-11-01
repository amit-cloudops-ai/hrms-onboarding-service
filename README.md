# Smart Employee Onboarding & Identity Service

Automated new-hire onboarding on AWS: from offer acceptance to a fully ready Day 1.
This is the identity spine of the HRMS. It creates the canonical employee record every other service refers to.

**Evaluation:** 4 November 2026 | **Region:** us-east-1 | **Naming:** `hrms-dev-<component>`

## What it does
1. Creates an employee profile (UUID) in DynamoDB and a Cognito login, and emails an invite via SES.
2. Runs four stages with Step Functions: Document Collection, IT Provisioning, Policy Sign-off, Manager Intro.
3. Sends a reminder email when a stage is incomplete after 24 hours.
4. Stores documents encrypted in S3, validates them, and notifies HR via SNS.
5. Shows progress in two web views: new-hire portal and HR admin dashboard.

## Repository layout
| Folder | Purpose |
|---|---|
| `services/identity` | Employee profile, Cognito, invite email (WP1) |
| `services/workflow` | Step Functions state machine and stage tracking (WP2) |
| `services/documents` | Upload URLs, validation, HR notification (WP3) |
| `services/stages` | IT provisioning, policy sign-off, manager intro handlers (WP4) |
| `services/api` | API Gateway routes and authorizers (WP5) |
| `frontend/portal` | New-hire portal (WP6) |
| `frontend/hr-dashboard` | HR admin dashboard (WP7) |
| `infra` | Shared infrastructure definitions |
| `docs` | Contract, data model, architecture, decisions (WP8) |

## Start here
1. Read `docs/team-brief.md` and `docs/api-contract.md`.
2. For the full solo implementation history, deployed AWS inventory, exact deployment commands, Console walkthrough, local website setup and remaining acceptance tests, read [Solo implementation and AWS deployment record](docs/solo-implementation-and-aws-deployment-record.md).
3. For the current component handoff, read `docs/implementation-status.md`.
4. Follow `CONTRIBUTING.md` for repository workflow.

## Deployment status

The five development backend stacks (foundation, stages, documents, workflow and API) are deployed in `us-east-1` and were confirmed `CREATE_COMPLETE` on 1 November 2026. The frontends have passed production builds, but live Cognito sign-in and the full end-to-end onboarding journey still require verification. This is not a production release.

## Rules in one line
No secrets in Git. No direct pushes to `main`. Stay in your folder. Ask before changing the contract.
