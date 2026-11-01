# Solo implementation and AWS deployment record

**Repository:** amit-cloudops-ai/hrms-onboarding-service  
**Branch:** v1-solo  
**Region:** us-east-1  
**Environment:** development (hrms-dev-*)  
**Recorded:** 1 November 2026

> **Current state:** all five backend CloudFormation stacks have returned CREATE_COMPLETE. This confirms resource provisioning, not full application-level end-to-end success. Frontend live configuration and acceptance testing remain.

## 1. Executive summary

The solo implementation integrates identity (WP1), workflow (WP2), documents (WP3), stage handlers (WP4), API (WP5), and the portal/dashboard (WP6/WP7).

Backend deployment order used:

1. Shared foundation — Cognito and DynamoDB.
2. WP4 — stage handlers and notification topic.
3. WP3 — private document bucket, validation Lambda and HR notification topic.
4. WP2 — Standard Step Functions state machine, workflow Lambda and reminder topic.
5. WP5 — Cognito-protected HTTP API and API Lambda.

IT provisioning is in simulation mode for the first AWS test. This is a development environment, not a production release.

## 2. Problems encountered and fixes

### Work packages were not yet proven together
Separate local tests did not prove deployed service-to-service integration. We established a dependency-aware deployment order and passed the real stack outputs between services: WP4 before WP3/WP2, and WP5 after all dependencies.

### Employee identity needed an immutable key
Email can change and is not a reliable authorization key. The implementation links an employee record to Cognito's immutable subject (sub), stored as cognito_sub. The /employees/me route resolves the signed-in employee through that subject. HR operations require the hr-admins Cognito group. Live role and ownership checks still need testing with real accounts.

### Step Functions callback tokens are sensitive
Task tokens must not be returned to browsers or written to logs. Workflow and stage services retain/use them server-side. The live callback and timeout/reminder paths still need acceptance testing.

### Document uploads are asynchronous
A successful browser PUT does not mean the document passed validation. WP3 uses short-lived object-scoped presigned URLs, S3 object-created validation, content-type/size/signature checks, metadata status, rejection handling and workflow resumption only after all required documents are verified. Live S3 event and retry paths remain to be tested.

### Cognito foundation initially failed
The first foundation deployment failed because optional MFA was configured without the required SMS configuration. The development template was changed to MfaConfiguration OFF, committed, and redeployed successfully. This is a development-only setting. Configure and test TOTP MFA and recovery before production.

### Frontend type-checking/build issues
The frontend CI build identified missing Vite ImportMeta.env declarations. src/vite-env.d.ts was added to both frontend applications and a frontend build workflow was added. The recorded GitHub Actions build run passed both apps.

### Frontend/backend contract alignment
The dashboard create-employee payload was aligned to the backend schema. GET /employees/me was added for employee self-service. API CORS was parameterized for portal :5173 and dashboard :5174. Both apps now use the Northstar in-app Cognito SRP sign-in through Amplify Auth v6, with session-scoped token storage and bearer-token API requests. The existing app client already permits SRP and refresh-token auth, so this UI change does not require a CloudFormation update. Real browser authentication/API behavior still requires acceptance testing. See [Northstar custom authentication](northstar-custom-auth.md).

### SAM dependency notice
SAM printed: "requirements.txt file not found. Continuing the build without dependencies." The builds still succeeded and copied source. This means SAM did not install a requirements file for those functions. Verify deployed imports in CloudWatch; add/package any third-party dependencies required. Do not treat the successful build as proof of runtime import success.

### Deployment approval boundary
SAM build and change-set creation are not deployment. Each stack was deployed with --no-execute-changeset, its proposed resource list was reviewed, and the change set was executed separately. All five stacks then reached CREATE_COMPLETE.

## 3. Confirmed AWS deployment inventory

All resources are in us-east-1.

| Stack | Confirmed status | Main contents |
|---|---|---|
| hrms-dev-foundation | CREATE_COMPLETE | Cognito pool/client/groups and four DynamoDB tables |
| hrms-dev-stages | CREATE_COMPLETE | WP4 Lambda and stage notification topic |
| hrms-dev-documents | CREATE_COMPLETE | WP3 Lambda, private S3 bucket and SNS topic |
| hrms-dev-workflow | CREATE_COMPLETE | Workflow Lambda, Standard Step Functions state machine and reminder topic |
| hrms-dev-api | CREATE_COMPLETE | HTTP API, Cognito JWT authorizer, API Lambda and route permissions |

### Foundation outputs
- User Pool ID: us-east-1_UHdj6I89K
- Public App Client ID: 1p5860pgdk2jc0nqgo1217sh8
- Hosted login domain: https://amit-hrms-dev-20261101.auth.us-east-1.amazoncognito.com
- DynamoDB tables: hrms-dev-employees, hrms-dev-documents, hrms-dev-onboarding-stages, hrms-dev-equipment

### Service outputs
- WP4 Lambda: hrms-dev-stages
- WP4 SNS topic: arn:aws:sns:us-east-1:924422830139:hrms-dev-stage-notifications
- WP3 Lambda: hrms-dev-documents
- WP3 bucket: hrms-924422830139-us-east-1-hrms-dev-documents-documents
- WP3 SNS topic: arn:aws:sns:us-east-1:924422830139:hrms-dev-document-notifications
- WP2 Lambda: hrms-dev-workflow
- WP2 state machine: arn:aws:states:us-east-1:924422830139:stateMachine:hrms-dev-onboarding
- WP2 reminder topic: arn:aws:sns:us-east-1:924422830139:hrms-dev-onboarding-reminders
- WP5 API endpoint: https://mv5cyfzsya.execute-api.us-east-1.amazonaws.com

The API endpoint is an authenticated API, not a public website. Requests need a valid Cognito JWT.

## 4. AWS CLI deployment steps

### 4.1 Prerequisites and account check

The session used WSL/Linux, AWS CLI, AWS SAM CLI and an authenticated AWS profile. The SAM artifact bucket used was aws-sam-cli-managed-default-samclisourcebucket-lravsdtrjseo.

~~~
cd ~/hrms-frontend-preview
aws sts get-caller-identity
aws configure get region
aws configure set region us-east-1
aws --version
sam --version
~~~

Check the AWS account identity before any deployment or deletion. Use the intended account and region.

### 4.2 Foundation stack

Template: infra/template.yaml. Cognito domain prefix: amit-hrms-dev-20261101. Local callback/logout origins: ports 5173 and 5174.

~~~
sam build --template-file infra/template.yaml

sam deploy --guided   --template-file .aws-sam/build/template.yaml   --stack-name hrms-dev-foundation   --region us-east-1   --capabilities CAPABILITY_IAM   --resolve-s3   --parameter-overrides     Environment=dev     CognitoDomainPrefix=amit-hrms-dev-20261101     CognitoCallbackUrls=http://localhost:5173/,http://localhost:5174/     CognitoLogoutUrls=http://localhost:5173/,http://localhost:5174/
~~~

The first attempt failed on Cognito MFA/SMS configuration. The dev template was corrected to MFA OFF, then rebuilt and deployed. The foundation stack reached CREATE_COMPLETE.

### 4.3 WP4 stage handlers

~~~
sam build --template-file services/stages/template.yaml

sam deploy   --template-file .aws-sam/build/template.yaml   --stack-name hrms-dev-stages   --region us-east-1   --capabilities CAPABILITY_IAM   --resolve-s3   --parameter-overrides SimulationMode=true   --no-execute-changeset
~~~

Review the SAM/CloudFormation change set before execution. Use the ARN printed by SAM:

~~~
aws cloudformation execute-change-set   --stack-name hrms-dev-stages   --change-set-name REPLACE_WITH_CHANGE_SET_ARN   --region us-east-1

aws cloudformation wait stack-create-complete   --stack-name hrms-dev-stages --region us-east-1

aws cloudformation describe-stacks   --stack-name hrms-dev-stages --region us-east-1   --query "Stacks[0].[StackName,StackStatus,Outputs]" --output json
~~~

Confirmed function name: hrms-dev-stages. SimulationMode was true.

### 4.4 WP3 document service

~~~
sam build --template-file services/documents/template.yaml

sam deploy   --template-file .aws-sam/build/template.yaml   --stack-name hrms-dev-documents   --region us-east-1   --capabilities CAPABILITY_IAM   --resolve-s3   --parameter-overrides     EmployeesTableName=hrms-dev-employees     DocumentsTableName=hrms-dev-documents     StagesFunctionName=hrms-dev-stages     UploadAllowedOrigin=http://localhost:5173     UploadUrlTtlSeconds=300   --no-execute-changeset
~~~

Reviewed change set execution:

~~~
aws cloudformation execute-change-set   --stack-name hrms-dev-documents   --change-set-name arn:aws:cloudformation:us-east-1:924422830139:changeSet/samcli-deploy1793544714/76bd9f6e-7d72-4981-87b5-bd229cc05823   --region us-east-1

aws cloudformation wait stack-create-complete   --stack-name hrms-dev-documents --region us-east-1

aws cloudformation describe-stacks   --stack-name hrms-dev-documents --region us-east-1   --query "Stacks[0].[StackName,StackStatus,Outputs]" --output json
~~~

Confirmed CREATE_COMPLETE and outputs for bucket, Lambda and SNS topic.

### 4.5 WP2 workflow

~~~
sam build --template-file services/workflow/template.yaml

sam deploy   --template-file .aws-sam/build/template.yaml   --stack-name hrms-dev-workflow   --region us-east-1   --capabilities CAPABILITY_IAM   --resolve-s3   --parameter-overrides     StagesTableName=hrms-dev-onboarding-stages     StagesFunctionName=hrms-dev-stages   --no-execute-changeset
~~~

Reviewed change set execution:

~~~
aws cloudformation execute-change-set   --stack-name hrms-dev-workflow   --change-set-name arn:aws:cloudformation:us-east-1:924422830139:changeSet/samcli-deploy1793544932/00718092-658b-437d-91d8-5a7f022b7aab   --region us-east-1

aws cloudformation wait stack-create-complete   --stack-name hrms-dev-workflow --region us-east-1

aws cloudformation describe-stacks   --stack-name hrms-dev-workflow --region us-east-1   --query "Stacks[0].[StackName,StackStatus,Outputs]" --output json
~~~

Confirmed state machine ARN: arn:aws:states:us-east-1:924422830139:stateMachine:hrms-dev-onboarding.

### 4.6 WP5 authenticated API

~~~
sam build --template-file services/api/template.yaml

sam deploy   --template-file .aws-sam/build/template.yaml   --stack-name hrms-dev-api   --region us-east-1   --capabilities CAPABILITY_IAM   --resolve-s3   --parameter-overrides     CognitoUserPoolId=us-east-1_UHdj6I89K     CognitoAppClientId=1p5860pgdk2jc0nqgo1217sh8     EmployeesTableName=hrms-dev-employees     StagesTableName=hrms-dev-onboarding-stages     DocumentsTableName=hrms-dev-documents     StateMachineArn=arn:aws:states:us-east-1:924422830139:stateMachine:hrms-dev-onboarding     DocumentsFunctionName=hrms-dev-documents     StagesFunctionName=hrms-dev-stages     PortalOrigin=http://localhost:5173     DashboardOrigin=http://localhost:5174   --no-execute-changeset
~~~

The change set contained 13 additions (nine route permissions, API Lambda role/function, HTTP API and default stage) and no replacements/deletions.

~~~
aws cloudformation execute-change-set   --stack-name hrms-dev-api   --change-set-name arn:aws:cloudformation:us-east-1:924422830139:changeSet/samcli-deploy1793545274/d8d6eb88-1bae-4dab-8586-499009d1888a   --region us-east-1

aws cloudformation wait stack-create-complete   --stack-name hrms-dev-api --region us-east-1

aws cloudformation describe-stacks   --stack-name hrms-dev-api --region us-east-1   --query "Stacks[0].[StackName,StackStatus,Outputs]" --output json
~~~

Confirmed API endpoint: https://mv5cyfzsya.execute-api.us-east-1.amazonaws.com

### 4.7 Verify all stacks

~~~
for stack in   hrms-dev-foundation   hrms-dev-stages   hrms-dev-documents   hrms-dev-workflow   hrms-dev-api
do
  aws cloudformation describe-stacks     --stack-name "$stack"     --region us-east-1     --query "Stacks[0].[StackName,StackStatus]"     --output table
done
~~~

Expected recorded state for each stack: CREATE_COMPLETE.

## 5. AWS Console walkthrough

The stacks were deployed with SAM/CLI. Use the Console for visual inspection and administration as follows.

### Select account and region
1. Sign in to AWS Console.
2. Confirm the intended AWS account in the account menu.
3. Set region to US East (N. Virginia), us-east-1.
4. Open CloudFormation → Stacks. Search hrms-dev-. Open each stack and inspect Stack info, Events, Resources and Outputs. Confirm CREATE_COMPLETE.

### Inspect DynamoDB and Cognito
1. Open DynamoDB → Tables. Inspect hrms-dev-employees, hrms-dev-documents, hrms-dev-onboarding-stages and hrms-dev-equipment. Review key schema, indexes, billing mode and encryption against infra/template.yaml and docs/data-model.md.
2. Open Amazon Cognito → User pools. Select pool ID us-east-1_UHdj6I89K.
3. Inspect Users, Groups, App integration → App clients, and App integration → Domain.
4. Confirm groups hr-admins and Employee exist. Confirm app client is public (no client secret), callback/logout URLs are correct, and OAuth authorization-code flow/scopes match the frontend.
5. Add the intended HR operator to hr-admins. Do not share temporary passwords or tokens.

### Inspect Lambda, S3 and SNS
1. Open Lambda → Functions. Inspect hrms-dev-stages, hrms-dev-documents, hrms-dev-workflow and hrms-dev-api.
2. For each, review Configuration → Environment variables and Permissions; Monitor → View CloudWatch logs for runtime errors. Never share secrets or personal document contents.
3. Open S3 → Buckets → the deployed HRMS documents bucket. Verify Block Public Access, default encryption, versioning and CORS. Keep the bucket private.
4. Open SNS → Topics. Inspect stage, document and reminder topics. Add subscriptions only for approved HR/manager notification destinations.

### Inspect Step Functions and API Gateway
1. Open Step Functions → State machines → hrms-dev-onboarding. Inspect definition and, during tests, execution graph/history.
2. Open API Gateway → APIs. Select the API with endpoint https://mv5cyfzsya.execute-api.us-east-1.amazonaws.com.
3. Review Routes, Authorization and CORS. Routes should use the Cognito JWT authorizer.
4. Open Lambda → hrms-dev-api and inspect its execution role and CloudWatch log group.
5. Test protected routes only with a valid Cognito JWT. Anonymous 401/Unauthorized is expected.

### Create/verify HR administrator
1. Cognito → User pools → selected pool → Users: create or locate the intended HR admin.
2. Use Cognito's invitation/reset flow. Never store a temporary password in Git or this document.
3. Groups → hr-admins → Add user to group.
4. Sign in to dashboard and verify the admin can perform HR actions. A regular employee must not be in hr-admins.

## 6. Local website preview setup

The portal and HR dashboard have passed production builds in CI, and their Cognito/API client wiring exists. However, the apps are not confirmed live-configured until local environment files are created and login/API calls are tested.

Create frontend/portal/.env.local:

~~~
VITE_API_BASE_URL=https://mv5cyfzsya.execute-api.us-east-1.amazonaws.com
VITE_DEMO_MODE=false
VITE_COGNITO_USER_POOL_ID=us-east-1_UHdj6I89K
VITE_COGNITO_CLIENT_ID=1p5860pgdk2jc0nqgo1217sh8
~~~

Create frontend/hr-dashboard/.env.local:

~~~
VITE_API_BASE_URL=https://mv5cyfzsya.execute-api.us-east-1.amazonaws.com
VITE_DEMO_MODE=false
VITE_COGNITO_USER_POOL_ID=us-east-1_UHdj6I89K
VITE_COGNITO_CLIENT_ID=1p5860pgdk2jc0nqgo1217sh8
~~~

Do not commit .env.local files.

Start the portal in one terminal:

~~~
cd ~/hrms-frontend-preview/frontend/portal
npm install
npm run dev -- --host 0.0.0.0
~~~

Start the dashboard in another terminal:

~~~
cd ~/hrms-frontend-preview/frontend/hr-dashboard
npm install
npm run dev -- --host 0.0.0.0
~~~

Open:
- Employee portal: http://localhost:5173
- HR dashboard: http://localhost:5174

Use the HR admin Cognito account for dashboard testing and a separate employee account for portal testing. Keep demo mode false for live integration tests.

**CORS:** API CORS currently allows localhost:5173 and localhost:5174. S3 upload CORS currently allows localhost:5173. If deploying the frontends to hosted domains, update API CORS, S3 CORS, and Cognito callback/logout URLs to the exact HTTPS origins and redeploy the relevant stacks.

## 7. Live end-to-end acceptance test

Do not call the project complete until these pass against real AWS services:

1. Northstar in-app Cognito SRP sign-in, token refresh and sign-out work in both applications.
2. Anonymous requests are rejected. Employee cannot list/create or read another employee's data. Only hr-admins can list/create employees and complete manager intro.
3. HR admin creates a disposable test employee. Confirm employee record, Cognito identity and Step Functions execution are created.
4. Simulated IT provisioning completes and records expected equipment assignment.
5. Employee uploads each required valid PDF/JPEG/PNG. Confirm S3 PUT, object-created event, document validation and verified status. Test invalid signature, unsupported type, oversize and retry.
6. Confirm document stage does not complete until all required documents are verified.
7. Employee accepts all required versioned policies. Confirm workflow advances only after all required acceptances.
8. HR admin completes manager_intro. Confirm non-admin is denied and workflow reaches terminal success.
9. Test expired/duplicate callbacks and adapter failures. No task token appears in responses or logs.
10. Inspect Lambda CloudWatch logs, SNS notification delivery and Step Functions execution history.

## 8. Remaining risks and production hardening

- Live end-to-end acceptance has not yet been completed.
- Frontend environment configuration and real browser login/API calls are not yet confirmed.
- Cognito MFA is OFF in this development stack. Configure and test TOTP MFA before production.
- IT provisioning is simulated; a real adapter is needed for real device/account provisioning.
- SNS topics exist; authorized subscriptions and delivery must be configured and verified.
- SAM's no-requirements.txt notice requires runtime import verification and dependency packaging where needed.
- Review IAM least privilege, especially API table access and Step Functions callback permissions. SendTaskSuccess uses wildcard resource scope in this implementation; task tokens must remain secret.
- Production HTTPS origins are not configured.
- Establish employee-data retention/deletion, backups, log retention, alerting, incident response and access procedures.
- Costs are not zero. Lambda, API Gateway, Step Functions Standard, DynamoDB, S3, SNS and CloudWatch can incur charges. Check Billing/Cost Explorer and set a budget/alerts; Cost Explorer can lag.

## 9. Cost-safe console checks and cleanup

Inspect Billing and Cost Management → Bills/Cost Explorer, CloudWatch → Log groups, Step Functions → Executions, S3 → bucket objects/versions, and SNS → subscriptions.

Do not delete stacks merely to stop a test. If cleanup is explicitly approved, export required data and empty all S3 object versions/delete markers first. Delete stacks in reverse dependency order, reviewing each stack before deletion:

~~~
aws cloudformation delete-stack --stack-name hrms-dev-api --region us-east-1
aws cloudformation wait stack-delete-complete --stack-name hrms-dev-api --region us-east-1

aws cloudformation delete-stack --stack-name hrms-dev-workflow --region us-east-1
aws cloudformation wait stack-delete-complete --stack-name hrms-dev-workflow --region us-east-1

# Empty all object versions and delete markers in the versioned WP3 bucket first.
aws cloudformation delete-stack --stack-name hrms-dev-documents --region us-east-1
aws cloudformation wait stack-delete-complete --stack-name hrms-dev-documents --region us-east-1

aws cloudformation delete-stack --stack-name hrms-dev-stages --region us-east-1
aws cloudformation wait stack-delete-complete --stack-name hrms-dev-stages --region us-east-1

aws cloudformation delete-stack --stack-name hrms-dev-foundation --region us-east-1
aws cloudformation wait stack-delete-complete --stack-name hrms-dev-foundation --region us-east-1
~~~

**Never run cleanup commands without explicit approval.** This removes the development environment and its identity/data resources. The SAM artifact bucket may remain separately.

## 10. Handoff checklist

- [x] WP1–WP5 solo backend implementation and templates are in v1-solo.
- [x] Offline backend regression suite: 84 tests passed, as reported during this deployment session.
- [x] Portal and dashboard production builds passed in CI.
- [x] Foundation deployed.
- [x] WP4 stages deployed.
- [x] WP3 documents deployed.
- [x] WP2 workflow deployed.
- [x] WP5 API deployed.
- [ ] Create local frontend environment files and verify Northstar in-app Cognito SRP login.
- [ ] Verify HR admin membership in hr-admins.
- [ ] Complete live authorization checks.
- [ ] Complete live employee creation and workflow execution.
- [ ] Complete document upload/validation/retry tests.
- [ ] Complete policy sign-off and manager introduction.
- [ ] Verify CloudWatch logs, SNS delivery and actual AWS spend.
- [ ] Complete production MFA, security, privacy and real-adapter hardening.

**Release decision:** backend infrastructure is deployed to the development account. The websites can be opened locally for a visual review after the environment files are configured. The live user journey has not yet been verified. This is a deployed development integration candidate, not a production release.
