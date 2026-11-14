# Final project audit — public engineering summary

**Audit snapshot:** 4 November 2026  
**Region:** `us-east-1`  
**Method:** read-only AWS inventory supplied by the project owner, source review and GitHub Actions evidence.

Account identifiers, user emails, API URLs, Cognito IDs, CloudFront URLs, resource ARNs, execution IDs and other environment-specific identifiers are intentionally omitted from this public summary.

## Executive summary

The evaluation environment contained the core identity, API, workflow, document and stage services. The audit recorded the four required onboarding stage records as complete and all three required document records as verified for the inspected synthetic/evaluation journey.

The audit also found an employee lifecycle consistency defect: the employee record remained `in_progress` when the completion-email delivery record was `failed`. The workflow implementation was updated to separate lifecycle completion from notification delivery. The remediation records delivery state independently (`sending`, `sent`, `failed`) and provides preview-first, targeted reconciliation.

The source changes passed the final-readiness GitHub Actions validation. The merge did not deploy AWS resources, change IAM policies, mutate employee records, restart executions or send email.

## 1. Infrastructure inventory

The read-only snapshot showed the following service groups in successful stack states:

| Service group | Observed state | Responsibility |
|---|---|---|
| Identity foundation | Successful | Cognito user pool/groups and DynamoDB tables |
| Workflow | Successful update | Lambda workflow handler, Step Functions and reminder notifications |
| Documents | Successful | Private S3 bucket, document Lambda, event-driven validation and HR notifications |
| Stage adapters | Successful | Business-stage Lambda adapter |
| API | Successful | API Gateway HTTP API, JWT authorizer, routes and API Lambda |
| Static hosting | Successful | Frontend hosting resources |
| Current CDN hosting | Successful | Employee portal and HR dashboard delivery |
| Legacy hosting attempt | Rolled back | Earlier hosting stack; not the current deployment target |

The deployment tooling was updated to reuse the observed hosting resources, require existing stacks in stable states, require an existing private same-region SAM artifact bucket and use interactive change-set confirmation. The script does not automatically recreate missing hosting resources or artifact buckets. These changes were source-validated; the updated deployment script was not run against AWS as part of the code merge.

## 2. Identity and API authorization

The environment audit confirmed a Cognito-backed API boundary. The listed application routes used a JWT authorizer, and the API implementation adds server-side checks for:

- HR-only operations through the configured HR administrator group.
- Employee self-service by matching the authenticated Cognito `sub` claim to the employee record's immutable `cognito_sub`.
- Service-adapter invocation through backend-controlled configuration.

The audit confirmed HR-group membership for the account queried at that time. The actual identity used by a future operator must be checked independently.

The API Lambda's deployed environment configuration was not fully captured in the audit. Confirm required environment variables before exercising employee creation or downstream service calls.

## 3. Workflow and stage lifecycle

The intended workflow contains four stages:

1. `document_collection` — waits for required documents to be validated.
2. `it_provisioning` — invokes the WP4 business adapter.
3. `policy_signoff` — waits for the employee's policy acknowledgement callback.
4. `manager_intro` — invokes the WP4 business adapter.

Callback/task tokens remain server-side and are not returned to browser clients.

The audited environment used `MODE=simulated` for WP4. IT provisioning and manager introduction therefore return deterministic demonstration outcomes; they do not create real third-party accounts, allocate physical equipment or schedule calendar events.

The audit observed one completed execution and one additional running execution. The latter's employee association and current stage were not included in the report. Inspect an execution's input and history before taking any operational action.

## 4. Employee completion and SES delivery

For the inspected journey, all four stage records were complete and all three required document records were verified. The employee lifecycle record nevertheless remained `in_progress` because completion email delivery had failed.

The audit observed:

- SES was operating in sandbox mode.
- The configured sender identities were verified.
- The IAM policy simulation allowed the examined send action/resource pair.
- The stored delivery error was `AccessDenied`.
- The recipient's SES verification status and the exact denial event were not established.

The precise SES denial cause remains unresolved. Do not add broad IAM permissions based only on the stored error. Retrieve the specific Lambda invocation log or CloudTrail event and verify recipient eligibility before changing IAM or SES account settings.

### Source-level correction

The final workflow changes:

- Persist employee lifecycle completion once all four required stages are complete, independently of email delivery.
- Track notification delivery separately as `sending`, `sent` or `failed`.
- Treat definitive delivery errors as notification failures rather than onboarding failures.
- Keep ambiguous transport outcomes in `sending` to avoid duplicate email delivery.
- Use one completion-notification trigger in the Step Functions workflow.
- Make reconciliation preview-first and support a targeted employee identifier for controlled recovery.

These source changes passed automated validation. They do not automatically repair an existing AWS record or send an email; that requires an approved, targeted runtime operation after recipient eligibility and deployed code are verified.

## 5. Documents and data protection

The document flow uses short-lived, scoped presigned upload URLs and private S3 storage. The service validates the uploaded object's actual size, content type and file signature before marking a document verified. Rejected uploads can be retried under the documented object-key and status rules.

The public API must never expose S3 object keys, bucket names, callback task tokens, credentials or document contents. Use synthetic employees and dummy files for evaluation.

## 6. Remaining runtime and operational checks

Before using the environment for real employee operations, complete and record:

1. Verify deployed Lambda environment variables for API and document integrations.
2. Inspect any currently running Step Functions execution before recovery or replay.
3. Resolve the SES denial from the exact runtime event and confirm recipient eligibility.
4. Confirm the deployed portal and dashboard use the intended live API and Cognito configuration.
5. Run a controlled end-to-end journey with synthetic identities and dummy documents.
6. Verify callback, retry, timeout, duplicate-event and failure-path behavior in the deployed environment.
7. Review IAM least privilege and Cognito MFA configuration.
8. Define backups, restore testing, data retention/deletion, CloudWatch alarms, log retention, tracing, incident response and cost budgets.
9. Review policy text and employee-data handling with the appropriate HR/legal stakeholders.
10. Integrate approved real IT provisioning and manager-calendar providers before enabling those operations.

## 7. Validation and deployment boundary

The final-readiness GitHub Actions run passed backend tests, targeted reconciliation tests, Step Functions/SAM validation, frontend lint/build, dependency audit, CloudFormation validation, deployment-script syntax and backend SAM builds.

[View the validation run](https://github.com/amit-cloudops-ai/hrms-onboarding-service/actions/runs/41800581911).

CI is validation-only. No AWS deployment or resource mutation is implied by a passing workflow or a source merge. Any deployment must be separately approved, use the guarded scripts and reviewed CloudFormation change sets, and follow the cost and cleanup documentation.

## Related documentation

- [Implementation status](implementation-status.md)
- [Architecture](architecture.md)
- [API contract](api-contract.md)
- [Data model](data-model.md)
- [Cost estimate](COST-ESTIMATE.md)
- [Mentor demo guide](MENTOR-DEMO-GUIDE.md)
