# Team Onboarding Guide — Smart Employee Onboarding & Identity Service

**Audience:** interns and contributors joining the project  
**Reference branch:** `v1-solo` (lead's independent reference implementation)  
**Shared team workflow:** feature branches created from `team-dev` and merged into `team-dev` by pull request  
**AWS region used by the project contracts:** `us-east-1`

This guide is intended to get a new contributor from zero context to a first tested change. Read it before coding. If anything here conflicts with the current issue assigned to you or the API/data-model contracts, stop and ask the project lead before changing the shared design.

---

## 1. What are we building?

We are building an employee onboarding system that takes a new hire from employee creation to Day 1 readiness. HR creates the employee record. The system creates the employee's login, collects required documents, prepares IT equipment, records policy acceptance, and coordinates a manager introduction. The employee and HR see progress in separate web applications.

The four onboarding stages are fixed across the project:

1. `document_collection`
2. `it_provisioning`
3. `policy_signoff`
4. `manager_intro`

Stage status values are `pending`, `in_progress`, and `complete`.

The system uses AWS managed services. We are not building one large backend server. The backend is split into small Python AWS Lambda services, exposed through API Gateway and coordinated by Step Functions.

## 2. Technology stack — use these choices

### Backend

- **Language:** Python 3.12.
- **Execution model:** AWS Lambda functions.
- **AWS SDK:** `boto3` (which provides the `botocore` exceptions and clients used by this code).
- **Infrastructure:** AWS SAM templates, written in YAML, to define Lambda functions, permissions, triggers, and related AWS resources.
- **HTTP entry point:** Amazon API Gateway HTTP API with a Cognito JWT authorizer.
- **Data store:** Amazon DynamoDB.
- **Authentication:** Amazon Cognito.
- **Workflow orchestration:** AWS Step Functions.
- **Document storage:** private Amazon S3 bucket with short-lived presigned upload URLs.
- **Notifications:** Amazon SNS; email integrations use Amazon SES where configured.
- **Tests:** Python's built-in `unittest`, with AWS clients/tables mocked for offline tests.

**Important:** there is no FastAPI, Flask, Django, or Express backend in this architecture. Do not create a new web server/framework for your package. Implement the Lambda handler pattern used by the other services and expose HTTP behavior through API Gateway where your package owns an API route.

### Frontend

The two existing web applications use React 18, TypeScript, Vite 6, and `lucide-react`. The employee portal is in `frontend/portal`; the HR dashboard is in `frontend/hr-dashboard`.

### Why this architecture?

Lambda keeps each backend responsibility isolated. API Gateway handles incoming HTTPS requests and Cognito JWT verification. DynamoDB stores the state shared across services. Step Functions manages the long-running onboarding journey so a Lambda does not need to stay running while an employee uploads a document or signs a policy.

## 3. Repository map

| Folder | Package | What it owns |
|---|---|---|
| `services/identity` | WP1 — Identity | Employee input validation, canonical employee record, Cognito user creation and identity linking |
| `services/workflow` | WP2 — Workflow | Four-stage Step Functions orchestration, stage state, callbacks and reminders |
| `services/documents` | WP3 — Documents | Presigned upload URLs, file validation, document statuses and HR notifications |
| `services/stages` | WP4 — Stage handlers | IT provisioning, policy sign-off and manager-introduction completion |
| `services/api` | WP5 — API | API Gateway Lambda handler, request routing, JWT-claim checks and service adapters |
| `frontend/portal` | WP6 — Employee portal | Employee-facing onboarding checklist and document/policy tasks |
| `frontend/hr-dashboard` | WP7 — HR dashboard | HR pipeline, employee creation, progress and operations view |
| `infra` | Shared infrastructure | Shared infrastructure definitions, subject to the current team issue |
| `docs` | Shared contracts and documentation | Architecture, API contract, data model and operating notes |

Your issue tells you which WP you own. Work only in that package's folder unless the lead explicitly approves a cross-package change.

## 4. What each work package must deliver

### WP1 — Identity

Build the employee-registration identity service. Validate the agreed employee fields, create one canonical employee record with a UUID, create/link the Cognito user, and persist Cognito's immutable `sub` on that employee record. Handle partial failures so the system does not leave an employee record that appears ready when identity creation failed.

Required employee fields in the current contract:

- `full_name`
- `email`
- `department`
- `role`
- `joining_date` (ISO date: `YYYY-MM-DD`)
- `employment_type`

Optional field: `manager_id`.

Do not use email as the permanent identity key. Employee self-access is based on Cognito `sub`.

### WP2 — Workflow

Own the four-stage workflow definition and stage-state transitions. The workflow starts when WP1/WP5 creates an employee. It dispatches the current stage, waits for a callback when a human action is required, marks a stage complete, and moves to the next stage.

The current design uses Step Functions callback/task-token waits with a 24-hour timeout and reminder cycle. Task tokens are secrets: store them only server-side, never return them to the browser, and never print them in normal logs. The workflow must handle retries and stale/expired callbacks safely.

### WP3 — Documents

Own the employee document upload and verification flow.

Required document types:

- `id_proof`
- `degree_certificate`
- `signed_offer_letter`

Accepted formats: PDF, JPG/JPEG, PNG. Maximum file size: 5 MB.

The expected flow is:

1. The authenticated employee requests a short-lived presigned S3 PUT URL for one document.
2. The service stores upload metadata in the documents table.
3. The browser uploads directly to the private S3 bucket using the URL and the exact `Content-Type` header.
4. An S3 object-created event invokes the validator.
5. The validator checks the real object size, content type and file signature. Do not trust only the filename or browser MIME type.
6. Valid documents become `verified`; invalid files become `rejected`, are removed from the bucket where possible, and trigger an HR notification.
7. A rejected/expired upload must be safely retryable with a new object key.
8. Resume `document_collection` only when all three required documents are verified.

Do not make the bucket public. Do not return S3 credentials. The presigned URL is the only browser upload authorization.

### WP4 — Stage handlers

Own stage-specific work after WP2 dispatches a stage.

- **IT provisioning:** for the first test, use deterministic simulated laptop/monitor assignments. Do not connect to real employee/device provisioning unless the issue explicitly asks for it and the lead approves the provider/integration.
- **Policy sign-off:** record policy ID, version, acceptance and timestamp. The default required IDs are `acceptable-use`, `privacy`, and `security`. Do not complete this stage until all required policies are accepted.
- **Manager introduction:** publish the action-required notification and allow an authorized HR admin to complete the stage.

The stage handler uses the WP2 callback token only to submit a Step Functions callback. Never expose it in an API response or frontend.

### WP5 — API

Own the HTTP API Lambda handler and route integration. The API is protected by API Gateway's Cognito JWT authorizer. The backend must enforce authorization on every route:

- HR admin routes require membership in the configured `hr-admins` Cognito group.
- Employee self-service routes require the caller's JWT `sub` to match the employee record's stored `cognito_sub`.
- Never trust an employee ID, role, email, or admin flag supplied by the browser request body.
- Invoke WP3/WP4 through the configured service adapters; fail safely if an adapter is missing or fails.
- Do not expose internal task tokens, execution ARNs, credentials or internal Cognito subject values in public responses.

The current route and request/response contract is in `docs/api-contract.md`.

### WP6 — Employee portal

Build the employee-facing React/TypeScript application. It should show the signed-in employee's own progress, document upload tasks, policy acknowledgements, equipment status, and manager-introduction status. Use the shared API contract. Do not hard-code another employee's ID or treat frontend checks as authorization; the backend owns access control.

### WP7 — HR dashboard

Build the HR-facing React/TypeScript application. It should show employee pipeline status, stage progress, search/filter, employee detail, and employee creation. Employee creation must send the API's exact required fields. The dashboard is not the security boundary: the API verifies the HR-admin group.

### WP8 / shared infrastructure and documentation

Follow the exact scope in the assigned issue. Shared infrastructure and contracts affect every package, so do not independently rename tables, stages, fields, resource names, or routes.

## 5. Local development setup

You can run the offline unit tests without deploying AWS resources or putting AWS credentials on your laptop.

### Backend prerequisites

Install:

- Python 3.12
- Git
- AWS SAM CLI (needed to validate/build SAM templates)
- AWS CLI is useful for later account inspection, but is not needed for the offline unit tests.

There is currently no root `requirements.txt` or package-specific requirements file in the repository. The backend uses Python standard-library modules plus `boto3`; `botocore` is installed as a dependency of `boto3`. The CI workflow installs `boto3` and AWS SAM CLI separately.

Create a virtual environment from the repository root:

**Windows PowerShell**
```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip boto3
python --version
sam --version
```

**macOS / Linux**
```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip boto3
python --version
sam --version
```

If your team has already provided a pinned dependency file or setup script in a newer team branch, use that instead of inventing a second dependency list.

### Frontend prerequisites

Install Node.js (use the version configured by the repository/CI environment) and npm.

Employee portal:
```bash
cd frontend/portal
npm install
npm run build
npm run dev
```

HR dashboard (in a separate terminal):
```bash
cd frontend/hr-dashboard
npm install
npm run build
npm run dev
```

Do not put AWS access keys, Cognito client secrets, real employee data or tokens in Vite environment variables. The frontend only receives public Cognito SPA configuration and the API base URL.

## 6. How to run tests

Run backend commands from the repository root unless the command says otherwise.

| Package | Offline test command |
|---|---|
| WP1 Identity | `cd services/identity && python -m unittest -v` |
| WP2 Workflow handlers | `cd services/workflow && python -m unittest test_handler -v` |
| WP2 Workflow callbacks | `cd services/workflow && python -m unittest test_callbacks -v` |
| WP3 Documents | `python -m unittest services.documents.test_handler -v` |
| WP4 Stages | `python -m unittest services.stages.test_handler -v` |
| WP5 API | `python -m unittest services.api.test_handler -v` |
| Journey regression tests | `python -m unittest tests.test_onboarding_integration -v` |

Validate a backend SAM template (replace the path with your package's template):

```bash
sam validate --lint --template-file services/documents/template.yaml
```

Other template paths are `services/stages/template.yaml`, `services/workflow/template.yaml`, and `services/api/template.yaml`.

These tests use mocks. A passing local test does not mean that AWS has been deployed or that the live Cognito/S3/Step Functions integration has been verified.

## 7. Shared data and API contract — do not improvise

Read these before implementing a request or data record:

- `docs/api-contract.md` — routes, access roles, request payloads, response behavior, document types and policy IDs.
- `docs/data-model.md` — DynamoDB table names, primary keys, attributes and expected indexes.
- `docs/architecture.md` — service boundaries and request/workflow flow.

The current data model names these tables:

| DynamoDB table | Keys |
|---|---|
| `hrms-dev-employees` | PK `employee_id` |
| `hrms-dev-onboarding-stages` | PK `employee_id`, SK `stage` |
| `hrms-dev-documents` | PK `employee_id`, SK `doc_type` |
| `hrms-dev-equipment` | PK `asset_id` |

The employee table's documented HR dashboard GSI is `status-index` (PK `status`).

If you need a new field, route, table, index, stage name or document type, propose it to the lead first. Update the shared contract only after agreement, then update every affected package and tests together.

## 8. Git workflow and collaboration rules

The shared team process is:

1. Check your assigned GitHub Issue and confirm the exact WP and acceptance criteria.
2. Clone the repository and update your local `team-dev` branch.
3. Create a feature branch from `team-dev`, for example `feature/wp3-sushmitha-documents`.
4. Work only in your assigned package folder. Make small commits with prefixes such as `feat:`, `fix:`, `test:`, or `docs:`.
5. Run the relevant test and SAM validation before pushing.
6. Push your feature branch and open a pull request into `team-dev`.
7. Request review from the project lead. Merge only after approval.

Example:

```bash
git clone https://github.com/amit-cloudops-ai/hrms-onboarding-service.git
cd hrms-onboarding-service
git checkout team-dev
git pull origin team-dev
git checkout -b feature/wp3-yourname
```

**Branch boundary:** `main` is stable; `team-dev` is the shared integration branch; `v1-solo` is the lead's independent implementation/reference branch and is not the branch for team contributions. Do not push directly to `main`, `team-dev`, or `v1-solo`.

**Security and collaboration rules:**

- Never commit `.env` files, AWS credentials, private keys, client secrets, Cognito tokens, Step Functions task tokens, presigned URLs or real employee documents.
- Do not deploy, delete, or modify AWS resources as part of local development. Ask the lead before any AWS operation that can create cost or affect shared resources.
- Do not change the API contract or data model without approval.
- Do not edit another contributor's package without coordinating first.
- Keep tests and a short README/update with your PR.

## 9. What to do before writing code

For your first work session:

1. Confirm your assigned WP and acceptance criteria with the lead.
2. Read the package folder, its SAM template, its existing tests, and the three shared docs listed above.
3. Run the current tests before making changes. This gives you a baseline.
4. Write down the input your package receives, the output it must return, which other WP it calls, and what failure/retry behavior is required.
5. Implement one small path first, add tests for success and failure, then expand.
6. Open a PR with: what changed, how to run it, tests executed, and any contract or dependency changes requested.

If you are unsure whether something belongs in your WP or another service, do not duplicate that service. Ask the lead and agree the interface first.

---

## 10. Useful project links

- Repository: https://github.com/amit-cloudops-ai/hrms-onboarding-service
- Architecture: `docs/architecture.md`
- API contract: `docs/api-contract.md`
- Data model: `docs/data-model.md`
- Contribution rules: `CONTRIBUTING.md`
- Solo implementation status/reference: `docs/implementation-status.md`

**Remember:** implement your assigned package, keep to the shared contracts, test locally with mocked AWS clients, and merge through a reviewed PR into `team-dev`. Do not deploy AWS resources unless the lead explicitly approves it.
