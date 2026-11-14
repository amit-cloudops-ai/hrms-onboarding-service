# Gate A smoke-test record

Use only synthetic employees and dummy documents. Do not put passwords, access tokens, JWTs, task tokens, presigned URLs, account IDs or real employee data in this file.

## Environment

- Date/time (IST): TODO
- AWS region: us-east-1
- Environment / stack names: TODO
- Synthetic employee ID: TODO (redact or use a non-sensitive alias in public evidence)
- Portal URL: TODO
- HR dashboard URL: TODO
- API endpoint label: TODO (do not publish credentials or account identifiers)
- Execution ARN: store privately; never publish the full ARN in public evidence

## Results

| Check | Expected result | Actual result | Evidence |
|---|---|---|---|
| HR administrator sign-in | HR admin can access dashboard | TODO | 01-hr-dashboard.png |
| Employee creation | Synthetic employee is created and identity provisioned | TODO | 01-hr-dashboard.png |
| Employee sign-in | Employee sees own record only | TODO | 02-employee-portal.png |
| Document upload | Three dummy docs accepted to private S3 | TODO | 03-document-status.png |
| Document validation | Server validates object and persists verified/rejected status | TODO | 03-document-status.png / CloudWatch reference |
| Document workflow callback | WP2 document wait resumes only after documents are verified | TODO | 04-step-functions-execution.png |
| Policy sign-off | Explicit policy acceptance is persisted; WP2 callback resumes | TODO | 04-step-functions-execution.png / 05-stage-records.png |
| WP4 IT provisioning | Deterministic simulated completion | TODO (state clearly simulated) | 04-step-functions-execution.png |
| WP4 manager introduction | Deterministic simulated completion | TODO (state clearly simulated) | 04-step-functions-execution.png |
| HR progress refresh | Progress survives page refresh | TODO | 07-refresh-persistence.png |
| Notification | HR email subscription confirmed and message delivered | TODO (do not claim delivery without proof) | 06-notification.png |
| CI | Latest release commit passes checks | PASS on commit 4671aafeee44a8d371358990f7985110db8b4b45 | 08-github-ci.png |

## Execution observation

- Step Functions execution start: TODO
- Step Functions execution end: TODO
- Expected stage order: document_collection → it_provisioning → policy_signoff → manager_intro
- Failed/retried states and reason: TODO (write None only after checking execution history)
- CloudWatch log group/time range reviewed: TODO
- Notification subscription status and message ID: TODO (redact recipient and message details)

## Sign-off

- Presenter: TODO
- Reviewer/mentor: TODO
- Open issues / limitations: WP4 external integrations remain simulated; Gate B production controls and external integrations remain outside this Gate A evaluation.
