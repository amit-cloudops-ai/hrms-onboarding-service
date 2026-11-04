# Gate A cost estimate — 50 onboarding events per month

## Scope and assumptions

Indicative estimate for the evaluation architecture in `us-east-1` (N. Virginia), 50 new hires/month, one workflow per hire, three documents per hire, and low-volume HR/employee portal use.

Workload assumptions:
- 50 workflow executions/month.
- 150 documents/month, average 2 MB each (about 300 MB new object data/month).
- Approximately 30–60 Step Functions state transitions per employee, depending on reminder/time-out path (1,500–3,000 transitions/month).
- Approximately 25,000 API requests/month across HR and employee usage.
- Lambda average 256 MB and short executions; no provisioned concurrency.
- DynamoDB on-demand; low single-digit GB total stored data.
- SES/SNS low-volume transactional notifications.
- No NAT Gateway, RDS, always-on EC2, WAF, paid support plan, or external provider fees.
- Excludes taxes, one-time setup/development, and any unusual internet egress.

## Indicative monthly usage cost

| Service | Usage driver | Indicative monthly cost (USD) |
|---|---|---:|
| API Gateway HTTP API | ~25,000 requests | $0.03–$0.10 |
| Lambda | API, identity, document and workflow handlers | $0.00–$0.50 |
| Step Functions Standard | 1,500–3,000 transitions | $0.00–$0.00 under the 4,000-transition monthly free tier, if eligible |
| DynamoDB on-demand | Low thousands of reads/writes; small storage | $0.05–$0.50 |
| S3 Standard | ~0.3 GB new document data/month plus requests | $0.01–$0.10 initially; storage grows over time |
| SES | Invitations and low-volume reminders | $0.02–$0.20 |
| SNS | HR notifications | $0.00–$0.10 at this volume |
| CloudWatch Logs | Low-volume application logs | $0.00–$1.00, depending on retention/ingestion |
| CloudFront/static hosting | Low traffic and transfer | $0.00–$2.00, depending on free-tier eligibility and transfer |

**Planning range: approximately $1–$5/month at this small workload when eligible free tiers apply. Budget $5–$15/month until actual billing and traffic are measured.** This is an order-of-magnitude estimate, not a quote or a guarantee. The cost can be higher if free-tier eligibility has expired, logs are verbose, data transfer grows, CloudFront usage is higher, or idle resources incur hourly charges.

## Cost controls

- Keep Lambda concurrency unprovisioned and use short timeouts appropriate to each handler.
- Use DynamoDB on-demand for the low/variable evaluation workload.
- Keep S3 private and lifecycle/retention rules explicit; avoid storing unnecessary test uploads.
- Set CloudWatch log retention rather than retaining logs indefinitely.
- Avoid NAT Gateway, RDS and always-on compute for this serverless evaluation.
- Use AWS Budgets and billing alerts; review Cost Explorer by service and resource tags.
- Do not run deployment scripts or create additional stacks solely to reproduce the demo.

## Pricing references

Rates and free-tier rules change. Recheck the live AWS pricing pages and the account's Free Tier eligibility before submission:
- API Gateway: https://aws.amazon.com/api-gateway/pricing/
- Lambda: https://aws.amazon.com/lambda/pricing/
- Step Functions: https://aws.amazon.com/step-functions/pricing/
- DynamoDB: https://aws.amazon.com/dynamodb/pricing/
- S3: https://aws.amazon.com/s3/pricing/
- SES: https://aws.amazon.com/ses/pricing/
- SNS: https://aws.amazon.com/sns/pricing/
- CloudFront: https://aws.amazon.com/cloudfront/pricing/

## Actual billing validation

Before final submission, capture the AWS Billing/Cost Explorer monthly view for the project account and compare it with this estimate. Do not publish account IDs, billing identifiers or other sensitive details in the mentor evidence pack.
