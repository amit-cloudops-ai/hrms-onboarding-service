#!/usr/bin/env bash
# Read-only pre-deployment inspection for the solo HRMS stack.
# This script does not deploy, update, delete, or read application data.
set -u

REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-us-east-1}}"
START_DATE="$(date -u -d '30 days ago' +%F 2>/dev/null || date -u -v-30d +%F)"
END_DATE="$(date -u +%F)"

section() { printf '\n\n========== %s ==========\n' "$1"; }
warn() { printf 'WARNING: %s\n' "$*" >&2; }
run_readonly() {
  printf '\n$'
  printf ' %q' "$@"
  printf '\n'
  "$@"
  local rc=$?
  if [ "$rc" -ne 0 ]; then
    warn "Command failed (exit $rc). This may mean the resource is absent or the current AWS identity lacks read permission."
  fi
  return 0
}

if ! command -v aws >/dev/null 2>&1; then
  echo "AWS CLI v2 is required. Install/configure it locally, then run this script again."
  exit 2
fi

section "Safety and target"
echo "Read-only checks only. No deployment, resource mutation, object listing, or application-data reads."
echo "Region being inspected: $REGION"
echo "AWS profile: ${AWS_PROFILE:-default credential chain}"
run_readonly aws --version
run_readonly aws sts get-caller-identity --output json
run_readonly aws configure get region

section "CloudFormation stacks (metadata only)"
run_readonly aws cloudformation list-stacks --region "$REGION" \
  --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE UPDATE_ROLLBACK_COMPLETE ROLLBACK_COMPLETE \
  --query 'StackSummaries[].{Name:StackName,Status:StackStatus,Updated:LastUpdatedTime,Created:CreationTime}' --output table

section "Expected DynamoDB tables and key/index configuration"
for table in hrms-dev-employees hrms-dev-onboarding-stages hrms-dev-documents hrms-dev-equipment; do
  echo "--- $table ---"
  run_readonly aws dynamodb describe-table --region "$REGION" --table-name "$table" \
    --query 'Table.{Name:TableName,Status:TableStatus,Keys:KeySchema,Attributes:AttributeDefinitions,GSIs:GlobalSecondaryIndexes[].{Name:IndexName,Keys:KeySchema,Status:IndexStatus,Projection:Projection},Billing:BillingModeSummary.BillingMode,DeletionProtection:DeletionProtectionEnabled,SSE:SSEDescription.Status}' --output json
done

section "Cognito user pools (names/IDs only)"
run_readonly aws cognito-idp list-user-pools --region "$REGION" --max-results 60 \
  --query 'UserPools[].{Name:Name,Id:Id,Status:Status,Created:CreationDate}' --output table
if [ -n "${COGNITO_USER_POOL_ID:-}" ]; then
  section "Selected Cognito pool configuration (no secrets)"
  run_readonly aws cognito-idp describe-user-pool --region "$REGION" --user-pool-id "$COGNITO_USER_POOL_ID" \
    --query 'UserPool.{Id:Id,Name:Name,Status:Status,MFA:MfaConfiguration,AutoVerifiedAttributes:AutoVerifiedAttributes,Policies:Policies,DeletionProtection:DeletionProtection,Domain:Domain}' --output json
  run_readonly aws cognito-idp list-user-pool-clients --region "$REGION" --user-pool-id "$COGNITO_USER_POOL_ID" --max-results 60 \
    --query 'UserPoolClients[].{Name:ClientName,Id:ClientId,HasSecret:GenerateSecret}' --output table
  run_readonly aws cognito-idp list-groups --region "$REGION" --user-pool-id "$COGNITO_USER_POOL_ID" \
    --query 'Groups[].{Name:GroupName,Precedence:Precedence,RoleArn:RoleArn}' --output table
fi

section "Lambda functions with expected prefix"
run_readonly aws lambda list-functions --region "$REGION" \
  --query "Functions[?starts_with(FunctionName, 'hrms-dev-')].{Name:FunctionName,Runtime:Runtime,Memory:MemorySize,Timeout:Timeout,LastModified:LastModified}" --output table

section "Step Functions state machines"
run_readonly aws stepfunctions list-state-machines --region "$REGION" \
  --query "stateMachines[?starts_with(name, 'hrms-dev-')].{Name:name,Type:type,Arn:stateMachineArn,Created:creationDate}" --output table

section "HRMS S3 bucket security metadata (no objects/versions listed)"
run_readonly aws s3api list-buckets --query "Buckets[?contains(Name, 'hrms') || contains(Name, 'documents')].{Name:Name,Created:CreationDate}" --output table
BUCKETS="$(aws s3api list-buckets --query "Buckets[?contains(Name, 'hrms') || contains(Name, 'documents')].Name" --output text 2>/dev/null || true)"
for bucket in $BUCKETS; do
  [ -z "$bucket" ] && continue
  echo "--- $bucket ---"
  run_readonly aws s3api get-public-access-block --bucket "$bucket" --query 'PublicAccessBlockConfiguration' --output json
  run_readonly aws s3api get-bucket-encryption --bucket "$bucket" --query 'ServerSideEncryptionConfiguration.Rules[].ApplyServerSideEncryptionByDefault' --output json
  run_readonly aws s3api get-bucket-versioning --bucket "$bucket" --query '{Status:Status,MFADelete:MFADelete}' --output json
  run_readonly aws s3api get-bucket-cors --bucket "$bucket" --query 'CORSRules[].{Origins:AllowedOrigins,Methods:AllowedMethods,Headers:AllowedHeaders}' --output json
done

section "SNS topics in target region (names/ARNs only)"
run_readonly aws sns list-topics --region "$REGION" --query "Topics[?contains(TopicArn, ':hrms-dev-')]" --output table

section "Recent AWS cost — last 30 days (requires Cost Explorer permission)"
run_readonly aws ce get-cost-and-usage --time-period "Start=$START_DATE,End=$END_DATE" \
  --granularity DAILY --metrics UnblendedCost \
  --group-by Type=DIMENSION,Key=SERVICE \
  --query 'ResultsByTime[].{Date:TimePeriod.Start,Costs:Groups[].{Service:Keys[0],Amount:Metrics.UnblendedCost.Amount,Unit:Metrics.UnblendedCost.Unit}}' --output json

section "Manual verification still required"
cat <<'NOTE'
1. Confirm the displayed account ID and region are the intended test target.
2. Compare each table's keys and GSIs with docs/data-model.md; in particular verify status-index on employees.
3. For the chosen Cognito pool/client, separately inspect OAuth flows, callback/sign-out URLs,
   allowed scopes, hosted-login domain, HR admin group, invitation delivery, and MFA/password policy.
   Do not copy or display client secrets, JWTs, or employee PII.
4. Review existing CloudFormation stack resources and change sets before any deploy. Fixed hrms-dev-*
   Lambda/topic/state-machine names may conflict with existing resources.
5. Set the exact portal origin for both API CORS and S3 upload CORS. Configure real deployed frontend URLs,
   notification subscriptions, and a budget alert before test deployment.
6. Record costs for Lambda, API Gateway, Step Functions Standard, DynamoDB, S3 requests/storage/versioning,
   CloudWatch Logs, and SNS. Cost Explorer data can lag and is not a future cost estimate.
7. The current GET /employees/me implementation scans the employees table by cognito_sub. Fine for a small
   test cohort, but add/verify a cognito_sub GSI before use at meaningful scale; this needs schema/change review.
8. No commands in this script mutate resources. Do not deploy or delete stacks until the report is reviewed.
NOTE
