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

section "API Gateway HTTP APIs and route authorization"
API_IDS="$(aws apigatewayv2 get-apis --region "$REGION" --query "Items[?ProtocolType=='HTTP'].ApiId" --output text 2>/dev/null || true)"
[ "$API_IDS" = "None" ] && API_IDS=""
for api_id in $API_IDS; do
  [ -z "$api_id" ] && continue
  echo "--- HTTP API $api_id ---"
  run_readonly aws apigatewayv2 get-api --region "$REGION" --api-id "$api_id" \
    --query '{Name:Name,Protocol:ProtocolType,Endpoint:ApiEndpoint,Cors:CorsConfiguration}' --output json
  run_readonly aws apigatewayv2 get-routes --region "$REGION" --api-id "$api_id" \
    --query 'Items[].{Route:RouteKey,Authorization:AuthorizationType,AuthorizerId:AuthorizerId,Target:Target}' --output table
done

section "Step Functions state machines"
run_readonly aws stepfunctions list-state-machines --region "$REGION" \
  --query "stateMachines[?starts_with(name, 'hrms-dev-')].{Name:name,Type:type,Arn:stateMachineArn,Created:creationDate}" --output table

STATE_MACHINE_ARNS="$(aws stepfunctions list-state-machines --region "$REGION" --query "stateMachines[?contains(name, 'hrms-dev-')].stateMachineArn" --output text 2>/dev/null || true)"
[ "$STATE_MACHINE_ARNS" = "None" ] && STATE_MACHINE_ARNS=""
for state_machine_arn in $STATE_MACHINE_ARNS; do
  [ -z "$state_machine_arn" ] && continue
  echo "--- deployed state machine ---"
  run_readonly aws stepfunctions describe-state-machine --region "$REGION" --state-machine-arn "$state_machine_arn" \
    --query '{Name:name,Type:type,Status:status,RoleArn:roleArn,Definition:definition}' --output json
done

section "HRMS S3 bucket security metadata (no objects/versions listed)"
run_readonly aws s3api list-buckets --query "Buckets[?contains(Name, 'hrms') || contains(Name, 'documents')].{Name:Name,Created:CreationDate}" --output table
BUCKETS="$(aws s3api list-buckets --query "Buckets[?contains(Name, 'hrms') || contains(Name, 'documents')].Name" --output text 2>/dev/null || true)"
[ "$BUCKETS" = "None" ] && BUCKETS=""
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

section "HRMS SNS subscription status (endpoint values omitted)"
TOPIC_ARNS="$(aws sns list-topics --region "$REGION" --query "Topics[?contains(TopicArn, ':hrms-dev-')].TopicArn" --output text 2>/dev/null || true)"
[ "$TOPIC_ARNS" = "None" ] && TOPIC_ARNS=""
for topic_arn in $TOPIC_ARNS; do
  [ -z "$topic_arn" ] && continue
  echo "--- $topic_arn ---"
  run_readonly aws sns list-subscriptions-by-topic --region "$REGION" --topic-arn "$topic_arn" \
    --query 'Subscriptions[].{Protocol:Protocol,SubscriptionArn:SubscriptionArn}' --output table
done

section "Recent AWS cost — last 30 days (requires Cost Explorer permission)"
run_readonly aws ce get-cost-and-usage --time-period "Start=$START_DATE,End=$END_DATE" \
  --granularity DAILY --metrics UnblendedCost \
  --group-by Type=DIMENSION,Key=SERVICE \
  --query 'ResultsByTime[].{Date:TimePeriod.Start,Costs:Groups[].{Service:Keys[0],Amount:Metrics.UnblendedCost.Amount,Unit:Metrics.UnblendedCost.Unit}}' --output json

section "CloudFormation resource inventory for expected solo stacks"
for stack in hrms-dev-stages hrms-dev-documents hrms-dev-workflow hrms-dev-api; do
  echo "--- $stack ---"
  run_readonly aws cloudformation describe-stacks --region "$REGION" --stack-name "$stack" \
    --query 'Stacks[0].Outputs[].{Key:OutputKey,Value:OutputValue,Description:Description}' --output table
  run_readonly aws cloudformation list-stack-resources --region "$REGION" --stack-name "$stack" \
    --query 'StackResourceSummaries[].{LogicalId:LogicalResourceId,Type:ResourceType,PhysicalId:PhysicalResourceId,Status:ResourceStatus}' --output table
done

section "Cognito OAuth app-client configuration (only when COGNITO_USER_POOL_ID is set)"
if [ -n "${COGNITO_USER_POOL_ID:-}" ]; then
  CLIENT_IDS="$(aws cognito-idp list-user-pool-clients --region "$REGION" --user-pool-id "$COGNITO_USER_POOL_ID" --max-results 60 --query 'UserPoolClients[].ClientId' --output text 2>/dev/null || true)"
  for client_id in $CLIENT_IDS; do
    [ -z "$client_id" ] && continue
    echo "--- $client_id (ClientSecret is intentionally not requested) ---"
    run_readonly aws cognito-idp describe-user-pool-client --region "$REGION" --user-pool-id "$COGNITO_USER_POOL_ID" --client-id "$client_id" \
      --query 'UserPoolClient.{Name:ClientName,Id:ClientId,HasSecret:GenerateSecret,AuthFlows:ExplicitAuthFlows,OAuthEnabled:AllowedOAuthFlowsUserPoolClient,OAuthFlows:AllowedOAuthFlows,Scopes:AllowedOAuthScopes,CallbackURLs:CallbackURLs,LogoutURLs:LogoutURLs,Providers:SupportedIdentityProviders,RefreshTokenValidity:RefreshTokenValidity,AccessTokenValidity:AccessTokenValidity,IdTokenValidity:IdTokenValidity}' --output json
  done
fi

section "IAM policies for HRMS Lambda execution roles"
ROLE_ARNS="$(aws lambda list-functions --region "$REGION" --query "Functions[?contains(FunctionName, 'hrms-dev-')].Role" --output text 2>/dev/null || true)"
[ "$ROLE_ARNS" = "None" ] && ROLE_ARNS=""
for role_arn in $ROLE_ARNS; do
  [ -z "$role_arn" ] && continue
  role_name="$(basename "$role_arn")"
  echo "--- $role_name ---"
  run_readonly aws iam list-attached-role-policies --role-name "$role_name" \
    --query 'AttachedPolicies[].{Name:PolicyName,Arn:PolicyArn}' --output table
  run_readonly aws iam list-role-policies --role-name "$role_name" --query 'PolicyNames' --output json
  INLINE_NAMES="$(aws iam list-role-policies --role-name "$role_name" --query 'PolicyNames[]' --output text 2>/dev/null || true)"
  for policy_name in $INLINE_NAMES; do
    [ -z "$policy_name" ] && continue
    echo "Inline policy: $role_name / $policy_name"
    run_readonly aws iam get-role-policy --role-name "$role_name" --policy-name "$policy_name" --query 'PolicyDocument' --output json
  done
done

section "CloudWatch log retention for expected Lambda functions"
run_readonly aws logs describe-log-groups --region "$REGION" --log-group-name-prefix "/aws/lambda/hrms-dev-" \
  --query 'logGroups[].{Name:logGroupName,RetentionDays:retentionInDays,StoredBytes:storedBytes}' --output table

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
