#!/usr/bin/env bash
set -euo pipefail
REGION="${AWS_REGION:-us-east-1}"
EXPECTED_ACCOUNT_ID="${EXPECTED_AWS_ACCOUNT_ID:-924422830139}"
ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
if [[ "$ACCOUNT_ID" != "$EXPECTED_ACCOUNT_ID" ]]; then
  echo "Refusing deployment: expected AWS account $EXPECTED_ACCOUNT_ID, authenticated to $ACCOUNT_ID." >&2
  exit 1
fi
COGNITO_DOMAIN_PREFIX="${COGNITO_DOMAIN_PREFIX:-hrms-team-$ACCOUNT_ID}"
HR_ADMIN_EMAIL="${HR_ADMIN_EMAIL:?Set HR_ADMIN_EMAIL to the team HR administrator email.}"
COMPLETION_EMAIL_SOURCE="${COMPLETION_EMAIL_SOURCE:?Set COMPLETION_EMAIL_SOURCE to a verified SES sender in $REGION.}"
SENDER_VERIFICATION="$(aws ses get-identity-verification-attributes --identities "$COMPLETION_EMAIL_SOURCE" --region "$REGION" --query 'VerificationAttributes.*.VerificationStatus' --output text)"
if [[ "$SENDER_VERIFICATION" != "Success" ]]; then
  echo "COMPLETION_EMAIL_SOURCE is not a verified SES identity in $REGION." >&2
  exit 1
fi
SES_PRODUCTION_ACCESS="$(aws sesv2 get-account --region "$REGION" --query 'ProductionAccessEnabled' --output text)"
if [[ "$SES_PRODUCTION_ACCESS" != "True" ]]; then
  echo "WARNING: SES is in the sandbox. Completion emails can only reach verified recipient identities." >&2
fi
ALLOW_STACK_UPDATES="${ALLOW_STACK_UPDATES:-false}"
ENABLE_POINT_IN_TIME_RECOVERY="${ENABLE_POINT_IN_TIME_RECOVERY:-false}"
stack_exists(){ aws cloudformation describe-stacks --stack-name "$1" --region "$REGION" >/dev/null 2>&1; }
guard_stack(){ if stack_exists "$1" && [[ "$ALLOW_STACK_UPDATES" != "true" ]]; then echo "Stack $1 exists. Inspect it first; set ALLOW_STACK_UPDATES=true only for an intentional update." >&2; exit 1; fi; }
require_existing_stack(){
  local name="$1" status
  if ! stack_exists "$name"; then
    echo "Required stack $name is missing. Refusing to bootstrap new AWS resources from this update script." >&2
    exit 1
  fi
  status="$(aws cloudformation describe-stacks --stack-name "$name" --region "$REGION" --query 'Stacks[0].StackStatus' --output text)"
  case "$status" in
    CREATE_COMPLETE|UPDATE_COMPLETE) ;;
    *) echo "Stack $name is in $status; refusing deployment." >&2; exit 1 ;;
  esac
}
stack_output(){ local value; value="$(aws cloudformation describe-stacks --stack-name "$1" --region "$REGION" --query "Stacks[0].Outputs[?OutputKey=='$2'].OutputValue | [0]" --output text)"; if [[ -z "$value" || "$value" == "None" ]]; then echo "Missing CloudFormation output $2 from stack $1." >&2; return 1; fi; printf "%s\n" "$value"; }

# Reuse an existing private SAM artifact bucket. Never let SAM create one implicitly.
SAM_ARTIFACT_BUCKET="${SAM_ARTIFACT_BUCKET:-$(aws s3api list-buckets --query "Buckets[?starts_with(Name, 'aws-sam-cli-managed-default-samclisourcebucket')].Name | [0]" --output text)}"
if [[ -z "$SAM_ARTIFACT_BUCKET" || "$SAM_ARTIFACT_BUCKET" == "None" ]]; then
  echo "No existing SAM artifact bucket found. Set SAM_ARTIFACT_BUCKET to an existing private bucket; this script will not create one." >&2
  exit 1
fi
SAM_BUCKET_REGION="$(aws s3api get-bucket-location --bucket "$SAM_ARTIFACT_BUCKET" --region "$REGION" --query LocationConstraint --output text)"
[[ "$SAM_BUCKET_REGION" == "None" ]] && SAM_BUCKET_REGION="us-east-1"
if [[ "$SAM_BUCKET_REGION" != "$REGION" ]]; then
  echo "SAM artifact bucket $SAM_ARTIFACT_BUCKET is in $SAM_BUCKET_REGION, not $REGION." >&2
  exit 1
fi
SAM_PUBLIC_ACCESS_BLOCK="$(aws s3api get-public-access-block --bucket "$SAM_ARTIFACT_BUCKET" --region "$REGION" --query 'PublicAccessBlockConfiguration.[BlockPublicAcls,IgnorePublicAcls,BlockPublicPolicy,RestrictPublicBuckets]' --output text)"
if [[ "$SAM_PUBLIC_ACCESS_BLOCK" != "True True True True" ]]; then
  echo "SAM artifact bucket $SAM_ARTIFACT_BUCKET must have all four S3 Block Public Access settings enabled." >&2
  exit 1
fi

deploy_sam(){
  local template="$1" build_dir="$2" stack="$3"; shift 3
  guard_stack "$stack"
  sam build --template-file "$template" --build-dir "$build_dir"
  sam deploy --template-file "$build_dir/template.yaml" --stack-name "$stack" --region "$REGION" --s3-bucket "$SAM_ARTIFACT_BUCKET" --capabilities CAPABILITY_IAM --no-fail-on-empty-changeset --parameter-overrides "$@"
}
for STACK in hrms-team-foundation hrms-team-wp4 hrms-team-wp2 hrms-team-wp3 hrms-team-api hrms-team-static-hosting hrms-team-cloudfront-hosting-v2; do
  require_existing_stack "$STACK"
done
echo "AWS account: $ACCOUNT_ID | Region: $REGION"
echo "Updates existing HRMS team stacks and static assets only. No new stacks, hosting resources or SAM artifact bucket will be created."
read -r -p "Type DEPLOY to apply the reviewed team-environment updates: " answer
[[ "$answer" == "DEPLOY" ]] || { echo "Cancelled."; exit 1; }

# Reuse the hosting topology that is already deployed. The old
# hrms-team-hosting stack is ROLLBACK_COMPLETE and must not be updated.
# The S3 buckets are owned by hrms-team-static-hosting; CloudFront v2 adds
# private OAC-backed distributions and is the canonical public origin.
HOSTING_STACK="${HOSTING_STACK:-hrms-team-cloudfront-hosting-v2}"
BUCKET_STACK="${BUCKET_STACK:-hrms-team-static-hosting}"
for STACK in "$HOSTING_STACK" "$BUCKET_STACK"; do
  if ! stack_exists "$STACK"; then
    echo "Required existing hosting stack $STACK was not found. Refusing to create or replace hosting resources automatically." >&2
    exit 1
  fi
  STATUS="$(aws cloudformation describe-stacks --stack-name "$STACK" --region "$REGION" --query 'Stacks[0].StackStatus' --output text)"
  case "$STATUS" in
    CREATE_COMPLETE|UPDATE_COMPLETE) ;;
    *) echo "Hosting stack $STACK is in $STATUS; refusing deployment." >&2; exit 1 ;;
  esac
done
PORTAL_BUCKET="$(stack_output "$BUCKET_STACK" PortalBucketName)"
PORTAL_DISTRIBUTION="$(stack_output "$HOSTING_STACK" PortalDistributionId)"
PORTAL_ORIGIN="$(stack_output "$HOSTING_STACK" PortalUrl)"
DASHBOARD_BUCKET="$(stack_output "$BUCKET_STACK" DashboardBucketName)"
DASHBOARD_DISTRIBUTION="$(stack_output "$HOSTING_STACK" DashboardDistributionId)"
DASHBOARD_ORIGIN="$(stack_output "$HOSTING_STACK" DashboardUrl)"
CALLBACK_URLS="$PORTAL_ORIGIN/,$DASHBOARD_ORIGIN/"

guard_stack hrms-team-foundation
aws cloudformation deploy --template-file infra/team-dev-foundation.yaml --stack-name hrms-team-foundation --region "$REGION" --no-fail-on-empty-changeset --parameter-overrides Environment=team EnablePointInTimeRecovery="$ENABLE_POINT_IN_TIME_RECOVERY" CognitoDomainPrefix="$COGNITO_DOMAIN_PREFIX" CognitoCallbackUrls="$CALLBACK_URLS" CognitoLogoutUrls="$CALLBACK_URLS"
EMPLOYEES_TABLE="$(stack_output hrms-team-foundation EmployeesTableName)"
STAGES_TABLE="$(stack_output hrms-team-foundation OnboardingStagesTableName)"
DOCUMENTS_TABLE="$(stack_output hrms-team-foundation DocumentsTableName)"
USER_POOL_ID="$(stack_output hrms-team-foundation UserPoolId)"
USER_POOL_CLIENT_ID="$(stack_output hrms-team-foundation UserPoolClientId)"
COGNITO_DOMAIN="$(stack_output hrms-team-foundation CognitoHostedUiDomain)"

deploy_sam services/stages/template.yaml .aws-sam/team-wp4 hrms-team-wp4 Mode=simulated StagesTableName="$STAGES_TABLE"
STAGES_FUNCTION_NAME="$(stack_output hrms-team-wp4 StagesFunctionName)"
deploy_sam services/workflow/template.yaml .aws-sam/team-wp2 hrms-team-wp2 Mode=simulated StagesTableName="$STAGES_TABLE" EmployeesTableName="$EMPLOYEES_TABLE" StagesFunctionName="$STAGES_FUNCTION_NAME" NotificationEmail="$HR_ADMIN_EMAIL" CompletionEmailSource="$COMPLETION_EMAIL_SOURCE"
STATE_MACHINE_ARN="$(stack_output hrms-team-wp2 StateMachineArn)"
WORKFLOW_FUNCTION_NAME="$(stack_output hrms-team-wp2 WorkflowFunctionName)"
deploy_sam services/documents/template.yaml .aws-sam/team-wp3 hrms-team-wp3 EmployeesTableName="$EMPLOYEES_TABLE" DocumentsTableName="$DOCUMENTS_TABLE" WorkflowFunctionName="$WORKFLOW_FUNCTION_NAME" UploadAllowedOrigin="$PORTAL_ORIGIN" NotificationEmail="$HR_ADMIN_EMAIL"
DOCUMENTS_FUNCTION_NAME="$(stack_output hrms-team-wp3 DocumentsFunctionName)"
DOCUMENTS_BUCKET="$(stack_output hrms-team-wp3 DocumentsBucketName)"
deploy_sam services/api/template.yaml .aws-sam/team-api hrms-team-api CognitoUserPoolId="$USER_POOL_ID" CognitoAppClientId="$USER_POOL_CLIENT_ID" EmployeesTableName="$EMPLOYEES_TABLE" StagesTableName="$STAGES_TABLE" DocumentsTableName="$DOCUMENTS_TABLE" StateMachineArn="$STATE_MACHINE_ARN" DocumentsFunctionName="$DOCUMENTS_FUNCTION_NAME" StagesFunctionName="$STAGES_FUNCTION_NAME" PortalOrigin="$PORTAL_ORIGIN" DashboardOrigin="$DASHBOARD_ORIGIN"
API_URL="$(stack_output hrms-team-api ApiEndpoint)"

if ! aws cognito-idp admin-get-user --user-pool-id "$USER_POOL_ID" --username "$HR_ADMIN_EMAIL" --region "$REGION" >/dev/null 2>&1; then
  aws cognito-idp admin-create-user --user-pool-id "$USER_POOL_ID" --username "$HR_ADMIN_EMAIL" --user-attributes Name=email,Value="$HR_ADMIN_EMAIL" Name=email_verified,Value=true --desired-delivery-mediums EMAIL --region "$REGION"
fi
aws cognito-idp admin-add-user-to-group --user-pool-id "$USER_POOL_ID" --username "$HR_ADMIN_EMAIL" --group-name hr-admins --region "$REGION"
HR_ADMIN_IN_GROUP="$(aws cognito-idp admin-list-groups-for-user --user-pool-id "$USER_POOL_ID" --username "$HR_ADMIN_EMAIL" --region "$REGION" --query "contains(Groups[].GroupName, 'hr-admins')" --output text)"
if [[ "$HR_ADMIN_IN_GROUP" != "True" ]]; then
  echo "HR administrator $HR_ADMIN_EMAIL is not a member of hr-admins after assignment." >&2
  exit 1
fi

cat > frontend/portal/.env.production <<EOF
VITE_USE_MOCK=false
VITE_API_BASE_URL=$API_URL
VITE_COGNITO_DOMAIN=$COGNITO_DOMAIN
VITE_COGNITO_CLIENT_ID=$USER_POOL_CLIENT_ID
VITE_COGNITO_REDIRECT_URI=$PORTAL_ORIGIN/
VITE_COGNITO_LOGOUT_URI=$PORTAL_ORIGIN/
EOF
cat > frontend/hr-dashboard/.env.production <<EOF
VITE_USE_MOCK=false
VITE_API_BASE_URL=$API_URL
VITE_COGNITO_DOMAIN=$COGNITO_DOMAIN
VITE_COGNITO_CLIENT_ID=$USER_POOL_CLIENT_ID
VITE_COGNITO_REDIRECT_URI=$DASHBOARD_ORIGIN/
VITE_COGNITO_LOGOUT_URI=$DASHBOARD_ORIGIN/
EOF
(cd frontend/portal && npm ci && npm run build)
(cd frontend/hr-dashboard && npm ci && npm run build)
aws s3 sync frontend/portal/dist "s3://$PORTAL_BUCKET" --delete --region "$REGION"
aws s3 sync frontend/hr-dashboard/dist "s3://$DASHBOARD_BUCKET" --delete --region "$REGION"
aws cloudfront create-invalidation --distribution-id "$PORTAL_DISTRIBUTION" --paths "/*" --region "$REGION" >/dev/null
aws cloudfront create-invalidation --distribution-id "$DASHBOARD_DISTRIBUTION" --paths "/*" --region "$REGION" >/dev/null
printf "\nTEAM DEMO DEPLOYED\nPortal: %s\nDashboard: %s\nAPI: %s\nCognito: %s\nDocuments bucket: %s\nHR admin invitation: %s\nMode: simulated\n" "$PORTAL_ORIGIN" "$DASHBOARD_ORIGIN" "$API_URL" "$COGNITO_DOMAIN" "$DOCUMENTS_BUCKET" "$HR_ADMIN_EMAIL"
