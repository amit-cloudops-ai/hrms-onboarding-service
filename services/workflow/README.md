# WP2 — Onboarding workflow

## Scope

Implements the four contract stages in order:

1. `document_collection`
2. `it_provisioning`
3. `policy_signoff`
4. `manager_intro`

The Standard Step Functions workflow uses callback tasks and DynamoDB stage records.
A callback task waits up to 24 hours. On timeout, the workflow publishes a reminder
and creates a new callback task for the same stage.

## Files

- `state_machine.asl.json` — Step Functions Amazon States Language definition.
- `handler.py` — stage-start tracking, completion recording, and reminder dispatch.
- `test_handler.py` — offline unit tests.
- `template.yaml` — AWS SAM deployment template.

## Input contract

Start an execution with JSON such as:

    {
      "employee_id": "employee-uuid",
      "current_stage": "document_collection"
    }

The API layer must validate the employee and start the execution. Only the four
contract stage names are accepted by the workflow support handler.

## Callback-token security

The Step Functions task token is stored in the private stage record and is never
returned in the handler's response or included in reminder messages/logs. Do not
send it to a browser or employee. WP5 must authorize the completion request,
retrieve the stored token server-side, and call `SendTaskSuccess`. A token from
an expired callback task cannot resume that task.

## Integration boundary

WP2 owns stage sequencing, callback-token lifecycle, stage-state persistence,
and timeout reminders. WP5 owns the authenticated HR completion endpoint and
server-side callback submission. The state machine intentionally does not
invoke a WP4 stage-specific business handler in this branch; that remains a
separate integration contract and must be agreed and tested before claiming
the entire HRMS onboarding product is end-to-end complete.

## Callback integration contract

WP5 invokes `services.workflow.callbacks.resume_stage` only after verifying the
JWT claim and HR-admin group. The callback helper reads the active token using
the composite key `{employee_id, stage}`, requires the record to be
`in_progress`, and submits this result to Step Functions:

```json
{
  "employee_id": "employee-uuid",
  "stage": "document_collection",
  "status": "complete"
}
```

The token itself is passed only to `SendTaskSuccess`; it is never included in
the callback output, API response, or logs. The API returns HTTP 202 with
`completion_submitted` after Step Functions accepts the callback. The state
machine's next state writes the completed status. A 202 response therefore
means submission was accepted, not that the full state machine has finished.

The workflow role needs `dynamodb:UpdateItem` for stage lifecycle updates and
the state-machine role needs permission to invoke the workflow Lambda. The API
role needs `dynamodb:GetItem` and `states:SendTaskSuccess` for callback
submission. These permissions are described in the SAM templates and must be
checked against the actual deployed role before release.

## Local tests

From the repository root:

    source ~/.venvs/hrms-onboarding/bin/activate
    cd services/workflow
    python -m unittest -v

## Deployment

The template references the existing `hrms-dev-onboarding-stages` DynamoDB table
and creates a reminder SNS topic, Lambda function, and Standard state machine.
Review the generated change set, table existence, IAM permissions, topic
subscriptions, and account/region before deploying. No deployment is performed
by the local test command.

## Verification and release boundary

- Offline tests cover the workflow helper actions and server-side callback helper.
- The CI workflow validates the ASL JSON and runs SAM lint validation for both
  the API and workflow templates.
- No AWS resources have been deployed by this implementation. Runtime IAM,
  actual DynamoDB key schemas, Cognito authorizer claims, Step Functions callback
  behavior, SNS delivery, and timeout behavior still require a separately approved
  non-production integration test before a live release.
- Reminder delivery is at-least-once; operational monitoring must account for
  duplicate notifications.
