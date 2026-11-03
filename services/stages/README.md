# WP4 — Stage-specific business handlers

WP4 performs the business action for the three non-document onboarding stages.
WP2 remains the owner of stage sequencing, callback tokens, reminders, and the
canonical `hrms-dev-onboarding-stages` lifecycle records. WP4 does not write
those records.

## Supported stages

- `it_provisioning`
- `policy_signoff`
- `manager_intro`

WP4 does not handle `document_collection`; that belongs to WP3.

## Internal Lambda event

The current handler accepts a JSON object with this shape:

```json
{
  "action": "execute_stage",
  "employee_id": "employee-uuid",
  "stage": "it_provisioning",
  "correlation_id": "execution-id-stage-it_provisioning"
}
```

The correlation ID should be stable for retries of the same workflow stage
attempt. The handler rejects unknown actions, invalid employee IDs, unsupported
stages, and missing correlation IDs.

## Response

The handler currently returns an API-style Lambda response envelope. Its
`body` is JSON with `ok`, `employee_id`, `stage`, `status`, `mode`, and
`result`. The simulated result is deterministic for a given input:

- IT provisioning: `equipment_status=assigned`, `account_status=created`
- Policy sign-off: `policy_status=accepted`
- Manager intro: `invitation_status=created`

## Execution modes

- `MODE=simulated` (default): returns deterministic simulated outcomes.
- `MODE=real`: fails closed with HTTP-style status 501 until approved provider
  integrations and credentials are configured.

Callers cannot select the mode in the event. Keep credentials in approved
secret storage; never commit them.

## WP2 integration status

The WP2 readiness branch currently documents that its Step Functions state
machine does **not** invoke the WP4 handler. The team guide describes the
intended WP2-to-WP4 connection, but the executable event/response contract
still needs Amit's confirmation. Until that agreement and a workflow-level
test exist, do not describe the full onboarding flow as end-to-end integrated.

Proposed handoff for discussion: WP2 invokes this Lambda synchronously with the
event above, interprets the returned envelope, and only then submits the
business result through its own callback/lifecycle path. WP4 must never receive
or persist a Step Functions task token.

## Tests

From the repository root:

```bash
python -m unittest services.stages.test_stages -v
```

These are offline unit tests; they do not call AWS or prove WP2 integration.
