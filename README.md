# Smart Employee Onboarding & Identity Service

Automated new-hire onboarding on AWS: from offer acceptance to a fully ready Day 1.
This is the identity spine of the HRMS. It creates the canonical employee record every other service refers to.

**Evaluation:** 4 November 2026 | **Region:** us-east-1 | **Naming:** hrms-dev-<component>

## What it does
1. Creates an employee profile (UUID) in DynamoDB and a Cognito login, and emails an invite via SES.
2. Runs four stages with Step Functions: Document Collection, IT Provisioning, Policy Sign-off, Manager Intro.
3. Sends a reminder email when a stage is incomplete after 24 hours.
4. Stores documents encrypted in S3, validates them, and notifies HR via SNS.
5. Shows progress in two web views: new-hire portal and HR admin dashboard.

## Start here — team members

**New to the project? Read [docs/team-playbook.md](docs/team-playbook.md) first.** It explains the system, work ownership, how packages connect, AWS/GitHub access rules, and the safe Git workflow.

Then read:
1. [docs/api-contract.md](docs/api-contract.md) — routes, access roles, stage names, document types and limits.
2. [docs/data-model.md](docs/data-model.md) — DynamoDB tables, keys and attributes.
3. [docs/team-work-packages.md](docs/team-work-packages.md) — package responsibilities and integration details.
4. [CONTRIBUTING.md](CONTRIBUTING.md) — branch and pull-request rules.
5. [docs/team-iam-setup.md](docs/team-iam-setup.md) — AWS IAM policy drafts and setup notes.

## Repository layout

| Folder | Purpose |
|---|---|
| services/identity | Employee profile, Cognito, invite email (WP1 — Amit) |
| services/workflow | Step Functions state machine and stage tracking (WP2 — Amit) |
| services/documents | Upload URLs, validation, HR notification (WP3 — Sushmitha) |
| services/stages | IT provisioning, policy sign-off, manager intro handlers (WP4 — Sushmitha) |
| services/api | API Gateway routes and authorizers (WP5 — Amit) |
| frontend/portal | New-hire portal (WP6 — Gopi) |
| frontend/hr-dashboard | HR admin dashboard (WP7 — Gopi) |
| infra | Shared infrastructure definitions |
| docs | Contracts, data model, architecture, decisions and team guides (WP8 — everyone) |

## Rules in one line

No secrets in Git. No direct pushes to main. Team changes go through feature branches and pull requests into team-dev. Stay in your owned folder. Ask before changing the shared API contract, data model, or workflow payloads.

**Implementation status:** these documents describe the agreed design and team workflow; verify infrastructure, deployed AWS resources, and end-to-end tests before claiming the full system is deployed.
