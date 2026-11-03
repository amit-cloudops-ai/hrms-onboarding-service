#!/usr/bin/env bash
# Deploy the isolated HRMS team demo without AWS CloudFront.
# Static React frontends are hosted on Cloudflare Pages; application services remain on AWS.
set -euo pipefail

REGION="${AWS_REGION:-us-east-1}"
EXPECTED_ACCOUNT_ID="${EXPECTED_AWS_ACCOUNT_ID:-924422830139}"
ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
if [[ "$ACCOUNT_ID" != "$EXPECTED_ACCOUNT_ID" ]]; then
  echo "Refusing deployment: expected AWS account $EXPECTED_ACCOUNT_ID, authenticated to $ACCOUNT_ID." >&2
  exit 1
fi

HR_ADMIN_EMAIL="${HR_ADMIN_EMAIL:?Set HR_ADMIN_EMAIL to the team HR administrator email.}"
COGNITO_DOMAIN_PREFIX="${COGNITO_DOMAIN_PREFIX:-hrms-team-$ACCOUNT_ID}"
ALLOW_STACK_UPDATES="${ALLOW_STACK_UPDATES:-false}"
ENABLE_POINT_IN_TIME_RECOVERY="${ENABLE_POINT_IN_TIME_RECOVERY:-false}"
CF_PAGES_BRANCH="${CF_PAGES_BRANCH:-team-dev}"
PORTAL_PROJECT="${CF_PORTAL_PROJECT:-hrms-team-portal}"
DASHBOARD_PROJECT="${CF_DASHBOARD_PROJECT:-hrms-team-dashboard}"

for command in aws sam npm npx; do
  command -v "$command" >/dev/null 2>&1 || { echo "Missing required command: $command" >&2; exit 1; }
done

stack_exists() {
  aws cloudformation describe-stacks --stack-name "$1" --region "$REGION" >/dev/null 2>&1
}
guard_stack() {
  if stack_exists "$1" && [[ "$ALLOW_STACK_UPDATES" != "true" ]]; then
    echo "Stack $1 exists. Inspect it first; set ALLOW_STACK_UPDATES=true only for an intentional update." >&2
    exit 1
  fi
}
stack_output() {
  local value
  value="$(aws cloudformation describe-stacks --stack-name "$1" --region "$REGION" --query "Stacks[0].Outputs[?OutputKey=='$2'].OutputValue | [0]" --output text)"
  if [[ -z "$value" || "$value" == "None" ]]; then
    echo "Missing CloudFormation output $2 from stack $1." >&2
    return 1
  fi
  printf "%s\n" "$value"
}
deploy_sam() {
  local template="$1" build_dir="$2" stack="$3"
  shift 3
  guard_stack "$stack"
  sam build --template-file "$template" --build-dir "$build_dir"
  sam deploy --template-file "$build_dir/template.yaml" --stack-name "$stack" --region "$REGION" --resolve-s3 --capabilities CAPABILITY_IAM --no-confirm-changeset --no-fail-on-empty-changeset --parameter-overrides "$@"
}
ensure_pages_project() {
  local project="$1"
  if ! npx wrangler pages project list 2>/dev/null | grep -Fq "$project"; then
    echo "Creating Cloudflare Pages project: $project"
    npx wrangler pages project create "$project" --production-branch "$CF_PAGES_BRANCH"
  else
    echo "Cloudflare Pages project already exists: $project"
  fi
}

echo "AWS account: $ACCOUNT_ID | Region: $REGION"
echo "Frontend hosting: Cloudflare Pages ($PORTAL_PROJECT, $DASHBOARD_PROJECT)"
echo "AWS resources: Cognito, DynamoDB, Lambda, Step Functions, SNS, S3 documents and API Gateway."
echo "This deployment path does not create CloudFront distributions or the hrms-team-hosting stack."
echo
npx wrangler whoami >/dev/null
ensure_pages_project "$PORTAL_PROJECT"
ensure_pages_project "$DASHBOARD_PROJECT"

PORTAL_ORIGIN="https://$PORTAL_PROJECT.pages.dev"
DASHBOARD_ORIGIN="https://$DASHBOARD_PROJECT.pages.dev"
CALLBACK_URLS="$PORTAL_ORIGIN/,$DASHBOARD_ORIGIN/"

read -r -p "Type DEPLOY to create/update the isolated AWS team environment and publish both Pages sites: " answer
[[ "$answer" == "DEPLOY" ]] || { echo "Cancelled."; exit 1; }

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
deploy_sam services/workflow/template.yaml .aws-sam/team-wp2 hrms-team-wp2 Mode=simulated StagesTableName="$STAGES_TABLE" StagesFunctionName="$STAGES_FUNCTION_NAME" NotificationEmail="$HR_ADMIN_EMAIL"
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
npx wrangler pages deploy frontend/portal/dist --project-name "$PORTAL_PROJECT" --branch "$CF_PAGES_BRANCH"
npx wrangler pages deploy frontend/hr-dashboard/dist --project-name "$DASHBOARD_PROJECT" --branch "$CF_PAGES_BRANCH"

printf "\nTEAM DEMO DEPLOYED (CLOUDFLARE PAGES FRONTENDS)\nPortal: %s\nDashboard: %s\nAPI: %s\nCognito: %s\nDocuments bucket: %s\nHR admin invitation: %s\nMode: simulated\n" "$PORTAL_ORIGIN" "$DASHBOARD_ORIGIN" "$API_URL" "$COGNITO_DOMAIN" "$DOCUMENTS_BUCKET" "$HR_ADMIN_EMAIL"
