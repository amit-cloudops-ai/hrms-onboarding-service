# Team Work Packages and Integration Guide

**Shared integration branch:** `team-dev`  
**Stable branch:** `main`  
**Region:** `us-east-1`  
**Primary contract documents:** [API contract](api-contract.md) · [Data model](data-model.md)

This is the working handoff guide for the three contributors. Keep shared integration work on `team-dev`; do not develop shared packages directly on `main` or `v1-solo`.

## Ownership

| Contributor | Work packages | Main folders | Responsibility |
|---|---|---|---|
| Gopi | WP6 — New-hire portal; WP7 — HR dashboard | `frontend/portal/`, `frontend/hr-dashboard/` | Build both UI experiences. Use contract-shaped fake data until the API is available. |
| Sushmitha (`sush-kush`) | WP3 — Document collection; WP4 — Stage handlers | `services/documents/`, `services/stages/` | Document upload URL and status flow, validation, notifications, and stage handlers for IT provisioning, policy sign-off, and manager intro. |
| Amit | WP1 — Identity; WP2 — Workflow; WP5 — API | `services/identity/`, `services/workflow/`, `services/api/`, shared infrastructure | Build employee identity and onboarding initiation, Step Functions workflow, API routes/authorization, and shared integration. |
| Everyone | WP8 — Docs, screenshots, demo | Their own package docs plus shared `docs/` reviewed by Amit | Document setup, decisions, tests, and screenshots for their own work; Amit assembles the final demo. |

Folder ownership is intended to reduce merge conflicts. If a shared contract or infrastructure change is needed, raise it in the team chat before editing another contributor's package.

## How the packages connect

1. **WP1 — Identity (Amit):** creates the canonical employee record with an `employee_id` and starts the onboarding experience.
2. **WP2 — Workflow (Amit):** starts and tracks the four stages: `document_collection`, `it_provisioning`, `policy_signoff`, and `manager_intro`.
3. **WP5 — API (Amit):** exposes the routes in `docs/api-contract.md`, applies the Cognito authorizer and role checks, and connects UI requests to the backend handlers.
4. **WP3 — Documents (Sushmitha):** generates a one-time upload URL, validates the uploaded document metadata/file rules, records status, and notifies HR where appropriate. The portal calls the upload-url and document-status routes; the API routes requests to this package.
5. **WP4 — Stage handlers (Sushmitha):** implements the stage-specific work for IT provisioning, policy sign-off, and manager introduction. The workflow invokes these handlers and records each stage's status.
6. **WP6 — New-hire portal (Gopi):** shows the new hire's onboarding progress, document requirements, and policy sign-off. Until WP5 is available, use fake data and mock functions matching the API contract.
7. **WP7 — HR dashboard (Gopi):** lists hires and their stage progress using the HR-admin routes from the same contract. Continue with mock data until the real API is ready.
8. **WP8 — Docs/demo (everyone):** each contributor records setup steps, tests, and screenshots; Amit assembles the end-to-end demo.

Conceptual flow:

```text
Gopi: Portal + HR dashboard
            |
            | docs/api-contract.md (mock first, real API later)
            v
Amit: API Gateway routes + Cognito authorization
            |
            +--> WP1 Identity --> employee record + invite
            |
            +--> WP2 Workflow --> Step Functions --> WP4 stage handlers (Sushmitha)
            |
            +--> WP3 Documents (Sushmitha) --> private S3 + document status + HR notification
            |
            +--> DynamoDB canonical records and stage/document status
```

The contract and data model are the source of truth. Do not invent different route names, stage names, document types, or response fields independently. If the current implementation requires a contract change, discuss it and update the contract first so all three packages remain compatible.

## Shared API contract

Read [`docs/api-contract.md`](api-contract.md) and [`docs/data-model.md`](data-model.md) before coding.

The currently documented routes are:

- `POST /employees` — HR admin creates/registers a hire and starts onboarding.
- `GET /employees` — HR admin lists hires and stage status.
- `GET /employees/{employee_id}` — employee profile.
- `GET /employees/{employee_id}/progress` — progress across four stages.
- `POST /employees/{employee_id}/documents/upload-url` — one-time upload URL.
- `GET /employees/{employee_id}/documents` — document status.
- `POST /employees/{employee_id}/policies/sign` — record policy acceptance.
- `POST /employees/{employee_id}/stages/{stage}/complete` — HR admin manually marks a stage complete.

Document rules for WP3 and WP6: accept **PDF, JPG, or PNG only**, maximum **5 MB**, with exactly these document types: `id_proof`, `degree_certificate`, `signed_offer_letter`.

The data model currently names these tables: `hrms-dev-employees`, `hrms-dev-onboarding-stages`, `hrms-dev-documents`, and `hrms-dev-equipment`. Stage statuses are `pending`, `in_progress`, and `complete`; document statuses are `missing`, `uploaded`, `verified`, and `rejected`.

## Gopi: frontend integration instructions

- Work in `frontend/portal/` and `frontend/hr-dashboard/`.
- Build using mock data that mirrors `docs/api-contract.md`; don't wait for live endpoints.
- Keep API calls behind a small service/client layer so mocked functions can be replaced with real HTTP requests without rewriting UI components.
- Include loading, empty, error, and success states.
- Portal user views should not expose HR-only routes or another employee's data.
- Dashboard views are for HR administrators; do not rely on hiding a button as authorization.
- Capture screenshots and note which data is mocked for WP8.

## Sushmitha: backend integration instructions

- Work in `services/documents/` and `services/stages/`.
- WP3 should validate extension/content type and size server-side; don't trust only the browser. Use short-lived, scoped upload URLs and keep the document bucket private.
- Persist document metadata/status using the agreed `hrms-dev-documents` key model (`employee_id` + `doc_type`).
- Use the exact document types and status values in the contract/data model.
- WP4 stage handlers must use the exact stage names and status model; be safe to retry where workflow retries can occur.
- Raise required IAM permissions, event payloads, or schema changes before assuming new infrastructure names. Capture tests and failure cases for WP8.

## Amit: integration responsibilities

- Own WP1 identity, WP2 workflow, WP5 API, and shared infrastructure integration.
- Keep route paths, request/response fields, authorization rules, table keys, and stage/document enums aligned with the two contract files.
- Provide Gopi a mock-to-real API transition note and example payloads before wiring up the live API.
- Confirm Sushmitha's event input/output shape for workflow stage handlers.
- Review PRs and merge package work into `team-dev`; protect `main`.
- Ensure actual IAM resource names and permissions match the deployed infrastructure before giving contributors broader AWS access.

## Branch and pull-request workflow

Each contributor starts from the latest `team-dev` and creates their own feature branch:

- Gopi: `feature/wp6-portal` (and include WP7 work in that branch unless the team agrees otherwise).
- Sushmitha: `feature/wp3-documents` (and include WP4 work in that branch unless the team agrees otherwise).
- Amit: use separate branches such as `feature/wp1-identity`, `feature/wp2-workflow`, and `feature/wp5-api` when practical.

Commands:

```bash
git clone https://github.com/amit-cloudops-ai/hrms-onboarding-service.git
cd hrms-onboarding-service
git switch team-dev
git pull origin team-dev
git switch -c feature/wp3-documents  # change branch name for your package
```

Before pushing:

```bash
git status
git diff
git add <your-package-path>
git commit -m "feat(wp3): implement document collection"
git push -u origin feature/wp3-documents
```

Open a Pull Request with **base `team-dev`**, not `main`. Include a summary, tests run, screenshots if UI-related, and any contract/infrastructure changes. Do not commit secrets, AWS CSVs, temporary passwords, access keys, MFA seeds, or real employee documents.

## Before merging a package

- [ ] The implementation follows `docs/api-contract.md` and `docs/data-model.md`.
- [ ] Unit or component tests cover the happy path and important failures.
- [ ] Input validation and authorization are enforced server-side.
- [ ] Logs omit passwords, tokens, and document contents.
- [ ] No credentials or real personal data are committed.
- [ ] README/setup notes and WP8 screenshots are included.
- [ ] PR targets `team-dev` and names any dependencies on another package.

## Team setup and access

GitHub access and AWS access are separate:

- GitHub collaborator access allows source-code collaboration; it does not grant AWS permissions.
- AWS IAM console access is controlled by the IAM user and its group. Use each teammate's own account, never Amit's credentials.
- Teammates should use MFA if required by the AWS account policy. If first-time enrollment fails, report the error so it can be fixed deliberately.
- Temporary passwords must be shared privately and never committed to this repository.

## Current integration caveat

The API contract and data model are present in `team-dev`. This guide describes the agreed package interfaces, not a claim that every Lambda, route, table, or UI is already implemented or deployed. Verify live AWS resources and run end-to-end tests before switching the frontend from mock data to the real API.
