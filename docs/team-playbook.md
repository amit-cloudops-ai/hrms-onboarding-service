# Team Playbook — Smart Employee Onboarding & Identity Service

This is the simple starting guide for all three contributors. Read it once, then keep it open while building. It explains what we are building, who owns each part, how the parts connect, and how to avoid breaking one another's work.

- **Shared team branch:** `team-dev`
- **Stable branch:** `main` (do not push directly)
- **Solo branch:** `v1-solo` (not for team deliverables)
- **AWS region:** `us-east-1`
- **API contract:** [`docs/api-contract.md`](api-contract.md)
- **Data model:** [`docs/data-model.md`](data-model.md)
- **Detailed package guide:** [`docs/team-work-packages.md`](team-work-packages.md)

## 1. The project in one minute

We are building an AWS-based employee onboarding system. HR registers a new hire. The system creates the employee's identity/profile, starts an onboarding workflow, tracks four stages, collects required documents, and shows progress in a new-hire portal and an HR dashboard.

Think of it like a relay race: **Amit builds the shared engine and API; Sushmitha builds document and stage services; Gopi builds the screens that use the API.** We agree on the same contract so all three parts fit together.

## 2. Who owns what

| Person | Packages | Work folders | Main outcome |
|---|---|---|---|
| **Gopi** | WP6 portal + WP7 HR dashboard | `frontend/portal/`, `frontend/hr-dashboard/` | Two usable screens; fake data first, real API later |
| **Sushmitha** (`sush-kush`) | WP3 documents + WP4 stage handlers | `services/documents/`, `services/stages/` | Secure document collection and handlers for onboarding stages |
| **Amit** | WP1 identity + WP2 workflow + WP5 API | `services/identity/`, `services/workflow/`, `services/api/` and shared infrastructure | Employee identity, workflow orchestration, API routes and authorization |
| **Everyone** | WP8 docs + screenshots + demo | Each person's package README/tests; shared docs by agreement | Record how their part works and prove it with tests/screenshots; Amit assembles the demo |

**Golden rule:** make changes inside your own package folders. If you need to change a shared contract, table shape, route, workflow payload, or infrastructure name, ask in the team chat first. Do not silently change a shared interface.

## 3. How everything connects

```text
HR admin creates a new hire
          |
          v
WP5 API + Cognito authorization (Amit)
          |
          +--> WP1 Identity (Amit)
          |       Creates employee ID/profile and invitation
          |
          +--> WP2 Workflow (Amit)
          |       Step Functions tracks the four onboarding stages
          |                  |
          |                  +--> WP4 stage handlers (Sushmitha)
          |                       IT provisioning, policy sign-off,
          |                       manager introduction
          |
          +--> WP3 Documents (Sushmitha)
          |       Upload URL, validation, document status,
          |       private S3 storage and HR notification
          |
          +--> DynamoDB records stage/document status
                         |
                         v
             WP6 Portal + WP7 HR dashboard (Gopi)
             Both call the documented API
```

The diagram is the **intended design**, not proof that every service is already deployed. Until Amit publishes and tests the real API, Gopi should use mock functions and fake data shaped like the contract. This lets frontend work continue without waiting.

## 4. Shared rules — do not invent your own

The two contract documents are the shared agreement. Before coding, read [API contract](api-contract.md) and [data model](data-model.md).

### API routes currently documented

| Method + route | Purpose |
|---|---|
| `POST /employees` | HR admin registers a hire and starts onboarding |
| `GET /employees` | HR admin lists hires and stage status |
| `GET /employees/{employee_id}` | View one employee profile |
| `GET /employees/{employee_id}/progress` | View the four-stage progress |
| `POST /employees/{employee_id}/documents/upload-url` | Get a one-time document upload URL |
| `GET /employees/{employee_id}/documents` | View document status |
| `POST /employees/{employee_id}/policies/sign` | Record policy acceptance |
| `POST /employees/{employee_id}/stages/{stage}/complete` | HR admin manually marks a stage complete |

Every route is intended to sit behind API Gateway with a Cognito authorizer. Authorization must be enforced by the backend, not only by hiding UI buttons.

### Exact names and validation

- Stage names: `document_collection`, `it_provisioning`, `policy_signoff`, `manager_intro`.
- Stage statuses: `pending`, `in_progress`, `complete`.
- Document types: `id_proof`, `degree_certificate`, `signed_offer_letter`.
- Document formats: PDF, JPG, PNG only.
- Maximum document size: 5 MB.
- Document statuses: `missing`, `uploaded`, `verified`, `rejected`.
- Region: `us-east-1`.
- Resource naming convention: `hrms-dev-<component>`.

DynamoDB table names in the current data model:
- `hrms-dev-employees` — canonical employee profile.
- `hrms-dev-onboarding-stages` — per-employee stage state.
- `hrms-dev-documents` — per-employee document metadata/status.
- `hrms-dev-equipment` — equipment assignment data.

Do not rename a route, status, document type, table key, or workflow event field in just one package. If a change is genuinely needed, agree it first, update the contract/data model, then update all affected packages together.

## 5. What each person should do first

### Gopi — WP6 and WP7
1. Read this playbook, `docs/api-contract.md`, and `docs/data-model.md`.
2. Work only in `frontend/portal/` and `frontend/hr-dashboard/`.
3. Create a small mock API/service layer with fake employees, stages, and document statuses matching the contract.
4. Build loading, empty, success, and error states. Keep the visual design clean and consistent.
5. Do not wait for live AWS endpoints. Swap the mock service for real HTTP calls only after Amit confirms the API is deployed and provides the base URL and example responses.
6. Add a README, tests, and screenshots for WP8.

### Sushmitha — WP3 and WP4
1. Read this playbook, `docs/api-contract.md`, and `docs/data-model.md`.
2. Work only in `services/documents/` and `services/stages/`.
3. For WP3, implement upload URL generation, server-side file/type/size checks, document metadata/status persistence, and the agreed notification behavior.
4. Keep the document bucket private; use scoped, short-lived upload URLs. Never log file contents, credentials, or tokens.
5. For WP4, implement handlers for IT provisioning, policy sign-off, and manager intro using the exact stage names and statuses above.
6. Make workflow handlers safe to retry where possible. Document required event input/output fields and tell Amit what the workflow/API must pass to your handlers.
7. Add a README, tests (including invalid file type/oversize cases), and screenshots or sample test output for WP8.

### Amit — WP1, WP2, and WP5
1. Own identity creation, workflow orchestration, API routes, Cognito authorization, shared infrastructure, and integration decisions.
2. Keep the API and DynamoDB contract stable for Gopi and Sushmitha.
3. Agree on the event payloads and outputs with Sushmitha before wiring her stage handlers into Step Functions.
4. Give Gopi the API base URL and sample request/response payloads only after the API is deployed and tested.
5. Review all pull requests and merge package work into `team-dev`.
6. Reconcile IAM policy resource patterns with actual resource names before deployment; do not create cloud resources just to match an assumed policy ARN.

## 6. The safe Git workflow — everyone follows this

Do not work directly on `main` or commit another person's feature branch. Start each work session from the current `team-dev`.

### First-time setup

```bash
git clone https://github.com/amit-cloudops-ai/hrms-onboarding-service.git
cd hrms-onboarding-service
git switch team-dev
git pull origin team-dev
git switch -c feature/wp3-documents
```

Replace `feature/wp3-documents` with your own branch name:
- Gopi: `feature/wp6-portal` (can contain both WP6 and WP7 because both are his frontend packages).
- Sushmitha: `feature/wp3-documents` (can contain both WP3 and WP4 because both are her backend packages).
- Amit: use focused branches such as `feature/wp1-identity`, `feature/wp2-workflow`, or `feature/wp5-api`.

### Before starting work each day

```bash
git status
git switch team-dev
git pull origin team-dev
git switch <your-feature-branch>
git merge team-dev
```

If the merge reports conflicts, stop and resolve them carefully; do not blindly choose “ours” or “theirs.” Ask the owner of the conflicting file if needed. Run tests after resolving conflicts.

### Commit and open a PR

```bash
git status
git diff
git add <your-package-folder>
git commit -m "feat(wp3): implement document collection"
git push -u origin <your-feature-branch>
```

Open a pull request with **base branch `team-dev`**. Include what changed, how to test it, test results, screenshots for UI work, and any interface changes. Amit reviews it; after approval, merge into `team-dev`. Changes reach `main` only through the agreed release process.

**Avoid conflicts:** small PRs, one owner per folder, no unannounced contract edits, and frequent updates from `team-dev`.

## 7. AWS access — important and simple

AWS access and GitHub access are different:
- GitHub lets you read and contribute code.
- AWS IAM lets you access specific cloud resources.
- The future HRMS/Cognito employee login is an application login; it is not the same as your AWS Console login.

Each teammate must use their own AWS IAM login and only their assigned permissions. The AWS Console sign-in URL and temporary passwords were shared separately by Amit. **Do not put the CSV, passwords, access keys, MFA secrets, or screenshots containing credentials in GitHub or the team channel.** Share temporary credentials privately and delete the CSV securely after the handoff.

MFA is part of the planned AWS security setup. If the first login or MFA enrollment is blocked, send Amit the exact error message without including passwords or security codes. Do not work around it by sharing Amit's account.

Use the AWS region `us-east-1` when following this project's setup instructions. Do not create or delete AWS resources unless they are part of an agreed task. Stop and ask Amit before provisioning anything that could incur cost.

## 8. Tests and definition of done

A package is not done merely because it compiles. Before opening a PR, check:

- [ ] It stays within your package folder unless the change was agreed.
- [ ] It follows the API contract and data model.
- [ ] Happy path and meaningful failure cases are tested.
- [ ] Server-side authorization and input validation are in place where applicable.
- [ ] No credentials, tokens, real employee data, or document files are committed.
- [ ] README explains purpose, setup, inputs/outputs, and how to test.
- [ ] UI work includes screenshots; backend work includes test output.
- [ ] PR targets `team-dev` and explains dependencies on another package.

For WP8, each person captures their own work and explains what is mocked versus connected to live AWS. Amit assembles the end-to-end demo and confirms integration.

## 9. What is ready versus what still needs verification

Present in `team-dev`: README, contributing rules, API contract, data model, team package guide, team IAM policy drafts, and this playbook.

Before claiming the complete system is ready, the team still needs to verify:
- Each contributor has the right GitHub Write access and has accepted the invitation.
- AWS console login, password change, and MFA enrollment work for both teammates.
- IAM policies are tested against the actual resources and tightened where necessary.
- Infrastructure definitions and package implementations exist, match the documented names, and pass tests.
- Gopi's mock API matches the contract; real API integration is tested after deployment.
- End-to-end onboarding works through all four stages.

**Repository note:** the current `docs/team-brief.md` is a placeholder and `infra/template.yaml` was not found at the expected path during this review. Do not assume the infrastructure template is ready; Amit should confirm its intended location or add the agreed template before deployment.

## 10. The rule that prevents most confusion

**If your change affects another person's input, output, route, table, event, or naming convention: talk first, update the shared contract, then code.** Otherwise, stay in your folder, use the agreed names, test your part, and submit a PR to `team-dev`.
