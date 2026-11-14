# WP2 — Workflow orchestration

WP2 owns the canonical onboarding lifecycle: Step Functions orchestration, stage state transitions, callback/task-token handling, reminders, failure correlation and completion notification.

## Four-stage workflow

1. `document_collection` — waits for WP3 to validate all required documents and submit the trusted callback.
2. `it_provisioning` — invokes the WP4 business adapter synchronously.
3. `policy_signoff` — waits for the employee's versioned policy acknowledgement callback.
4. `manager_intro` — invokes the WP4 business adapter synchronously.

WP2 owns canonical stage lifecycle transitions. WP4 receives no Step Functions task tokens and does not write canonical onboarding lifecycle fields. Callback tokens remain server-side and must never be returned to the browser or written to ordinary logs.

## Completion and notification state

Employee lifecycle completion and email delivery are independent:

- The employee becomes `complete` after all four required stage records are persisted as complete.
- Completion-email delivery is tracked separately as `sending`, `sent` or `failed`.
- A definitive SES failure is recorded as a notification failure and must not keep an otherwise complete employee in `in_progress`.
- An ambiguous transport outcome remains `sending` until reconciled; do not blindly retry and risk duplicate messages.
- The Step Functions `WorkflowComplete` state is the single completion-email trigger.

## Reconciliation

The reconciliation action is preview-first and paginated. It masks email addresses in preview output, skips incomplete/already-sent/in-progress records and requires explicit `confirm_send: true` before sending.

For a controlled recovery, the action can target one `employee_id`. Review the returned preview and verify recipient eligibility before requesting a send. Reconciliation does not restart a completed onboarding execution.

## Tests

From the repository root:

```bash
(cd services/workflow && python -m unittest test_handler test_completion test_reconciliation test_callbacks -v)
```

The tests use mocks; they do not prove live Step Functions or SES delivery.

## Deployment configuration

The workflow template receives the environment-specific employee/stage table names, WP4 function name, state-machine configuration and notification settings. Standalone defaults may use `hrms-dev-*`; the team environment uses `hrms-team-*`.

WP4 currently runs in `simulated` mode for the evaluation environment. Real provisioning and manager-calendar providers must be configured and separately validated before those operations are enabled.

## Safety

- Never log or expose callback task tokens.
- Keep retries bounded and side effects idempotent.
- Inspect an active execution before recovery or replay.
- Do not run reconciliation with `confirm_send: true` until the target employee and SES recipient eligibility have been reviewed.
- CI validates source and templates; it does not deploy AWS resources.
