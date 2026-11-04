# Mentor evaluation slide outline — Gate A

## Slide 1 — From fragmented handoffs to one onboarding journey
**Say:** The project creates a consistent employee identity and coordinates the main onboarding stages with visible, persisted progress.
**Show:** HR dashboard and the new-hire view.

## Slide 2 — Architecture and trust boundaries
**Say:** Cognito authenticates users; API Gateway validates JWTs; WP5 applies role and ownership checks; WP1 creates the canonical employee identity; WP2 coordinates long-running stages; DynamoDB stores status; S3 stores private documents.
**Show:** `docs/architecture.mmd` and `docs/er-diagram.mmd`.

## Slide 3 — HR creates a new hire
**Say:** HR creates a synthetic employee. The system links an employee record with a Cognito identity and initiates onboarding.
**Show:** HR pipeline and a newly created synthetic employee.

## Slide 4 — Employee self-service
**Say:** The employee signs in and sees their own checklist. The backend uses the immutable Cognito subject to resolve ownership; the browser does not pick another employee's identity.
**Show:** Employee portal for the synthetic account.

## Slide 5 — Document collection and verification
**Say:** The portal requests a short-lived upload URL; the file goes directly to private S3; the server validates actual object metadata and file content before changing its status.
**Show:** Document status. Do not display the upload URL.

## Slide 6 — Durable workflow and callback stages
**Say:** Step Functions coordinates stages that can wait for human action. Callback task tokens remain server-side. IT provisioning and manager introduction are deterministic simulated WP4 adapters in this evaluation.
**Show:** Step Functions execution history, only if captured and verified.

## Slide 7 — HR visibility and persistence
**Say:** HR sees stage progress from the same underlying records. Refreshing the views does not reset progress.
**Show:** Dashboard after refresh.

## Slide 8 — Validation, limits and next gate
**Say:** The latest CI run passed backend tests, frontend lint/build, production dependency audit, infrastructure lint, SAM validation/build and deployment-script syntax. This is offline/template verification plus manual demo evidence, not a production certification. Gate B requires live external integrations, security/privacy review and operational readiness.
**Show:** Successful Actions run and the limitations register.

## Demo close
**Say:** Gate A demonstrates the identity-backed onboarding flow and integration contracts. We are not claiming live provisioning/calendar integrations or approval for real employee data. The next step is an approved Gate B plan.
