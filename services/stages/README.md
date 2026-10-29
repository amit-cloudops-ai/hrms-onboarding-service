# WP4 — Stage handlers

## Implemented contract

Handler: `services.stages.handler.lambda_handler`. The function is invoked synchronously by WP2 for stage start and by WP5/WP3 for policy and completion events. It expects IAM-authenticated Lambda invocation from the API, workflow, and document service roles; it is not a public HTTP endpoint.

### Actions

- `start_stage`: `employee_id`, `stage`, and Step Functions `taskToken`. WP2 must persist the token and `in_progress` state before invoking WP4.
- `sign_policy`: `employee_id`, caller `sub`, and `policy` containing `policy_id`, `policy_version` (or `version`), and `accepted: true`.
- `complete_stage`: used by WP3 only after all required documents have been verified, or by WP5 HR-admin completion of `manager_intro`.

### Stage behavior

- `document_collection`: remains waiting until WP3 verifies all three required documents.
- `it_provisioning`: defaults to deterministic simulation and immediately submits the callback. Real mode invokes the configured `PROVISIONING_FUNCTION_NAME` and requires an explicit `{"ok":true}` provider response.
- `policy_signoff`: records versioned acceptance in the stage record and resumes the callback only after every ID in `REQUIRED_POLICIES` is accepted. The default IDs are `acceptable-use,privacy,security`.
- `manager_intro`: publishes an action-required notification if a topic is configured, then waits for HR to complete the stage through WP5.

Callback tokens are only passed to Step Functions. They are not returned to callers or written to logs. WP2 owns the authoritative stage status transition after Step Functions accepts the callback.

## Deployment template

`template.yaml` creates the stage Lambda and notification topic, with permissions limited to the employee/stage/document tables, callback submission, notification publishing, and optional provisioning Lambda invocation. It expects the DynamoDB tables created by the shared infrastructure setup.

For the demo, use `SimulationMode=true`. Use `SimulationMode=false` only after a real provisioning adapter is deployed and its function name supplied. Subscribe an authorized HR/manager notification endpoint to the output topic.

## Offline tests

From the repository root:

```bash
python -m unittest services.stages.test_handler -v
sam validate --lint --template-file services/stages/template.yaml
```

No live AWS resources are created by these tests. Live testing should verify IAM, task-token expiry behavior, policy acceptance persistence, manager-intro completion, and the real provisioning adapter separately.
