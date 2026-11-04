# WP2 workflow

WP2 owns Step Functions orchestration, task-token lifecycle, reminders and canonical onboarding-stage state. Document collection and policy sign-off are callback stages. IT provisioning and manager introduction are synchronous WP4 business stages. WP4 receives no task tokens and never writes canonical lifecycle fields.

WP3 signals document verification through the trusted WP2 resume action. WP5 records employee policy acceptance through WP4 and submits the policy-signoff callback. MODE is required; simulated is the only supported demonstration mode until real provider adapters are configured.

## Day 1 completion email

After the four persisted stages (`document_collection`, `it_provisioning`, `policy_signoff`, and `manager_intro`) are complete, the final Step Functions task sends the employee a Day 1-ready email. WP2 claims the send in the employee record before calling SES and records the SES message ID after acceptance. Retries skip records already marked `sent`; records left `sending` require SES reconciliation before an operator clears the claim.

For employees who completed onboarding before this notification was deployed, invoke the WP2 Lambda with `{"action":"reconcile_completion_notifications"}` to preview one bounded page (25 records by default). The response masks email addresses and returns `next_cursor` when another page exists. Continue previewing with `exclusive_start_key` set to that cursor. Only after reviewing eligible employee IDs and confirming SES recipient eligibility should the caller set `confirm_send: true`; the action then sends only for records whose four required stages are complete. Page size is limited to 1–100. SES sandbox accounts can send only to verified recipients.
