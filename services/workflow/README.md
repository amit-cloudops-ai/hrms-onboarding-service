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

## Stage-handler integration boundary

This milestone records stage lifecycle state and waits for authorized callbacks.
The stage-specific business actions owned by WP4 must be connected and tested
with Sushmitha's handlers before claiming full end-to-end completion.

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

## Known follow-up work

- Connect WP5's authorized callback endpoint to `SendTaskSuccess`.
- Integrate and contract-test WP4 stage-specific handlers.
- Add execution-start persistence (`execution_arn`) and recoverable behavior for
  failures between identity creation and workflow initiation.
- Validate the ASL with AWS tooling and run an end-to-end test in a non-production
  environment before production use.
- Reminder delivery is at-least-once; monitor SNS delivery and handle duplicate
  notifications operationally.
