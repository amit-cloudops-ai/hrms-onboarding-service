# Solo implementation plan

**Branch:** `v1-solo`  
**Evaluation target:** 4 November 2026  
**AWS region:** `us-east-1`  
**Deployment approach:** AWS SAM + Python Lambda, with infrastructure managed as code.

## Delivery principle

Build one testable vertical slice at a time. A feature is not complete until its infrastructure, least-privilege permissions, validation, failure handling, automated tests, operational notes, and end-to-end verification are in place. Do not claim production readiness until security, reliability, observability, cost controls, and recovery have been checked.

## Phases and acceptance criteria

### 0. Repository and environment baseline
- Confirm work is on `v1-solo`, working tree is clean, and the remote is up to date.
- Check AWS CLI, SAM CLI, Python, Node.js, and Docker availability.
- Confirm AWS identity and selected region without printing credentials.
- Establish formatting, linting, unit tests, dependency pinning, and CI checks.
- Never commit credentials, personal data, or internal documents.

**Exit:** a reproducible local setup and a safe deployment identity.

### 1. Infrastructure foundation
- Create an AWS SAM template and environment configuration.
- Define DynamoDB tables for employees, onboarding stages, documents, and equipment.
- Define a private S3 documents bucket with block-public-access, encryption, TLS-only access, lifecycle policy, and appropriate CORS only if required.
- Define Cognito user pool/groups, SNS topic, Step Functions state machine, API Gateway, and Lambda roles.
- Use least-privilege IAM, parameterized names, explicit retention, and stack outputs.
- Add a budget/cost guardrail and document cleanup of development resources.

**Exit:** template validates and deploys into a development stack without manual console-only resources.

### 2. Identity and employee registration
- Validate and normalize input; reject invalid email and required fields.
- Generate an employee UUID and write the canonical employee record.
- Create the Cognito identity and send an invitation only after the employee record is safely created.
- Handle retries/idempotency, partial failure and compensation; never log passwords, tokens, or sensitive document data.
- Add unit and integration tests plus structured logs.

**Exit:** authenticated HR can register a test hire once, safely retry, and retrieve the employee record.

### 3. Onboarding workflow
- Implement the four agreed stages: document collection, IT provisioning, policy sign-off, manager intro.
- Use Step Functions for orchestration and durable stage status.
- Use callback/task-token waits only where an external human action must resume the workflow; keep tokens out of client responses and persist them securely if required.
- Add 24-hour reminders, retry/backoff, timeout paths, failure states and safe redrive behavior.

**Exit:** an end-to-end execution demonstrates stage transitions, reminder behavior, and recoverable failures.

### 4. Documents
- Issue short-lived, scoped presigned upload URLs for the employee's own record.
- Enforce the allowed document types and a 5 MB maximum; validate actual content rather than trusting the filename or declared MIME type.
- Store documents privately with encryption and server-side metadata.
- Track missing/uploaded/verified/rejected status and notify HR through SNS.
- Test expired URLs, wrong employee IDs, invalid content, oversize files and duplicate events.

**Exit:** document upload and review work end-to-end without public object access.

### 5. API, authorization and frontend
- Implement the documented API contract with Cognito authorization and per-record ownership checks.
- Separate HR-admin operations from employee self-service.
- Build the employee portal and HR dashboard against the same API contract.
- Add pagination, input validation, consistent error responses, accessibility and loading/empty/error states.

**Exit:** role-based end-to-end tests prove employees cannot read or modify another employee's data.

### 6. Production-readiness hardening
- CI for lint, unit tests, template validation, dependency/security scanning and deployment packaging.
- CloudWatch structured logs, metrics, alarms, dashboards and retention settings.
- Encryption, least privilege, throttling, CORS allow-list, secret management, audit trail and data retention/deletion policy.
- Idempotency, concurrency/race-condition tests, DLQ or equivalent failure handling where applicable, backup/restore and incident/runbook notes.
- Cost estimate for 50 onboarding events/month and documented teardown/redeploy procedure.

**Exit:** security checklist, test report, architecture diagram, DynamoDB ER diagram, demo script, execution-history evidence, cost estimate and known-limitations list are ready for evaluation.

## First working session

1. Verify local branch and clean state.
2. Verify installed tools and AWS caller identity.
3. Inspect the existing scaffold before choosing runtime or changing contracts.
4. Implement Phase 0, then add the SAM foundation in small reviewable commits.
5. Deploy only after template validation and an explicit cost/security review.

## Production-readiness definition

This is an engineering target, not a claim that the project is already production-ready. Before real employee data is used, the project needs security review, privacy/data-retention approval, restore testing, monitored deployment, incident ownership, and a documented rollback plan.