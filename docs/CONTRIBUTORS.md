# Project contributors

This document records the contributors and work-package ownership for the Smart Employee Onboarding Platform. It is intended to make the collaborative work visible to reviewers, recruiters and future maintainers.

## Work-package ownership

| Contributor | GitHub | Work packages | Primary scope |
|---|---|---|---|
| Amit Madakatti | [@amit-cloudops-ai](https://github.com/amit-cloudops-ai) | WP1, WP2, WP5, shared integration | Identity, workflow orchestration, API authorization, infrastructure, cross-service integration and release coordination |
| Gopi | [@gk78-lab](https://github.com/gk78-lab) | WP6, WP7 | Employee portal, HR dashboard, frontend data adapters, UI documentation and screenshots |
| Sushmitha | [@sush-kush](https://github.com/sush-kush) | WP3, WP4 | Document service, upload validation, document events, stage handlers, tests and integration documentation |

## Contribution evidence

### Gopi — employee and HR interfaces

- [PR #5 — New-hire portal and HR dashboard](https://github.com/amit-cloudops-ai/hrms-onboarding-service/pull/5) — merged into the shared integration branch.
- Delivered the first employee-facing portal and HR operations dashboard, including mock API layers, UI states, documentation and screenshots.
- The integrated application subsequently connected both interfaces to Cognito authentication and the WP5 API.

### Sushmitha — document and onboarding-stage services

- [PR #6 — WP3 Document Service and WP4 Onboarding Stages](https://github.com/amit-cloudops-ai/hrms-onboarding-service/pull/6) — original contribution PR; later marked superseded after the implementation was integrated and refined in the shared branch.
- The contribution branch contains implementation and test commits authored by Sushmitha.
- Follow-up integration and hardening evidence:
  - [PR #7 — WP2 to WP4 orchestration integration](https://github.com/amit-cloudops-ai/hrms-onboarding-service/pull/7)
  - [PR #11 — S3 EventBridge upload-event integration](https://github.com/amit-cloudops-ai/hrms-onboarding-service/pull/11)
  - [PR #12 — Document upload and policy-sign-off prerequisites](https://github.com/amit-cloudops-ai/hrms-onboarding-service/pull/12)
  - [PR #13 — DynamoDB Decimal serialization fix](https://github.com/amit-cloudops-ai/hrms-onboarding-service/pull/13)

### Amit — identity, workflow, API and integration

- WP1 employee identity and Cognito account lifecycle.
- WP2 Step Functions orchestration, callback lifecycle, reminders, completion notifications and reconciliation.
- WP5 API Gateway integration, JWT claim validation, HR-group authorization and employee self-access checks.
- Shared infrastructure, service contracts, team integration, CI validation, deployment guardrails and final documentation.

## Shared engineering practices

The project used work-package ownership to keep implementation boundaries clear. Contributors worked in feature branches and submitted pull requests to the shared integration branch. The team aligned around shared API and data-model contracts, with cross-package changes reviewed and tested as integration work.

## Attribution policy

This page records work-package ownership and links to the source pull requests. It does not imply that every later integration or hardening commit was authored by the original package owner. The GitHub commit and pull-request history remains the authoritative record of individual code authorship.
