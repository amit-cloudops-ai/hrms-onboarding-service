# Solo integration runbook — WP1/WP2/WP3/WP4/WP5

This runbook is for a separately approved development deployment in Amit's AWS account. **The code and templates have not been deployed by these changes.** Unit tests and SAM validation are offline. The deployment creates billable AWS resources. Review the AWS Pricing Calculator and set an AWS Budget before proceeding.

## Integration shape

- The foundation stack creates the DynamoDB tables and Cognito user pool/client/groups.
- WP1 creates the employee record and Cognito identity, persisting immutable Cognito `sub`.
- WP5 authenticates requests through API Gateway's Cognito JWT authorizer and enforces HR-admin/self-service authorization.
- WP2 owns the four-stage Step Functions state machine and persists each active task token.
- WP4 handles simulated/real IT provisioning, versioned policy acceptance, and manager-intro completion.
- WP3 issues scoped presigned PUT URLs, validates actual uploaded bytes, stores document status, notifies HR on rejection, and resumes document collection after all three required documents pass.

## Pre-deployment checks

1. Confirm AWS CLI is authenticated to the intended account: `aws sts get-caller-identity`.
2. Confirm the target region is `us-east-1`: `aws configure get region`.
3. Confirm the six-region inventory and any remaining billable resources have been reviewed. Cost Explorer data can lag.
4. Confirm the Cognito domain prefix is globally unique for the selected region.
5. Decide the exact browser origins. For local Vite development, the portal is `http://localhost:5173` and the dashboard is `http://localhost:5174`. For hosted apps, use their exact HTTPS origins instead.
6. Confirm a real provisioning adapter is not required for the first test. Use simulated IT provisioning.
7. Review the CloudFormation change set and resource list before approving each stack. Do not deploy duplicate stacks if equivalent resources already exist.

## Deploy order

**Deploy the foundation first.** All service stacks depend on its DynamoDB tables and Cognito user pool. Deploying the service stacks before the foundation causes missing-resource or permission failures.

### 1. Shared foundation

Choose a unique lowercase Cognito domain prefix. The callback/logout defaults are suitable only for local development.

```bash
sam build --template-file infra/template.yaml
sam deploy --guided --template-file .aws-sam/build/template.yaml --stack-name hrms-dev-foundation --capabilities CAPABILITY_IAM --parameter-overrides Environment=dev CognitoDomainPrefix=REPLACE-WITH-UNIQUE-PREFIX CognitoCallbackUrls=http://localhost:5173/,http://localhost:5174/ CognitoLogoutUrls=http://localhost:5173/,http://localhost:5174/
```

Record these outputs: `EmployeesTableName`, `OnboardingStagesTableName`, `DocumentsTableName`, `EquipmentTableName`, `UserPoolId`, `UserPoolClientId`, and `CognitoHostedUiDomain`.

Create the initial HR administrator in the new user pool and add that user to the `hr-admins` group before testing admin routes. Do not put passwords or tokens in source control.

### 2. WP4 stage handler

```bash
sam build --template-file services/stages/template.yaml
sam deploy --guided --template-file .aws-sam/build/template.yaml --stack-name hrms-dev-stages --capabilities CAPABILITY_IAM --parameter-overrides SimulationMode=true
```

Record `StagesFunctionName` and `StageNotificationTopicArn`. The function name is passed to WP2, WP3, and WP5. Subscribe only an authorized HR notification endpoint if notifications are required.

### 3. WP3 document service

For local browser testing, use the portal origin `http://localhost:5173`. Replace it with the exact deployed portal origin when hosting the frontend.

```bash
sam build --template-file services/documents/template.yaml
sam deploy --guided --template-file .aws-sam/build/template.yaml --stack-name hrms-dev-documents --capabilities CAPABILITY_IAM --parameter-overrides StagesFunctionName=hrms-dev-stages UploadAllowedOrigin=http://localhost:5173
```

Record `DocumentsFunctionName`, `DocumentsBucketName`, and `HrDocumentNotificationsTopicArn`. Confirm the bucket's public-access block, encryption, versioning, and CORS origin. Subscribe only an authorized HR endpoint to the notification topic.

### 4. WP2 workflow

```bash
sam build --template-file services/workflow/template.yaml
sam deploy --guided --template-file .aws-sam/build/template.yaml --stack-name hrms-dev-workflow --capabilities CAPABILITY_IAM --parameter-overrides StagesFunctionName=hrms-dev-stages
```

Record `StateMachineArn`. Confirm the workflow role can invoke `hrms-dev-stages` and the stage role can call `states:SendTaskSuccess`.

### 5. WP5 API

Use the `UserPoolId` and `UserPoolClientId` outputs from the foundation and `StateMachineArn` from WP2.

```bash
sam build --template-file services/api/template.yaml
sam deploy --guided --template-file .aws-sam/build/template.yaml --stack-name hrms-dev-api --capabilities CAPABILITY_IAM --parameter-overrides CognitoUserPoolId=REPLACE-WITH-UserPoolId CognitoAppClientId=REPLACE-WITH-UserPoolClientId StateMachineArn=REPLACE-WITH-StateMachineArn DocumentsFunctionName=hrms-dev-documents StagesFunctionName=hrms-dev-stages PortalOrigin=http://localhost:5173 DashboardOrigin=http://localhost:5174
```

Record `ApiEndpoint`. Do not put real tokens, temporary passwords, document contents, or credentials into GitHub issues or logs.

## Frontend configuration

Configure both Vite apps to use the deployed `ApiEndpoint` and the foundation Cognito values. Use the exact callback/logout URLs registered in Cognito. Do not commit secrets; the Cognito web client is public and must not contain a client secret.

## End-to-end acceptance checklist

Use a real HR-admin JWT and a separate employee account. The employee token's Cognito `sub` must match the employee record's stored `cognito_sub`.

1. **Authorization:** anonymous requests return 401; a non-admin cannot list/create employees; one employee cannot read another employee's profile, progress, or documents.
2. **Identity + workflow:** HR admin creates a valid employee. API returns 201 without exposing `cognito_sub` or `execution_arn`. Employee row has `cognito_sub` and `execution_arn`; execution appears in Step Functions.
3. **Stage progression:** `it_provisioning` completes automatically in simulation mode. The next active stage is visible as `in_progress`.
4. **Documents:** employee requests upload URLs for each required type, uploads a small valid PDF/JPEG/PNG, and sees status become `verified`. An unsupported type, oversized file, or incorrect file signature is rejected. The document stage must not complete until all three required files are verified.
5. **Policy sign-off:** submit the required policies (`acceptable-use`, `privacy`, `security` by default) with versions and `accepted: true`. The stage must remain open until all required policies are accepted, then the workflow advances.
6. **Manager introduction:** HR admin completes `manager_intro`; a non-admin request is denied and the workflow reaches `WorkflowComplete`.
7. **Failure paths:** expired/consumed task tokens return a conflict, adapter failures return sanitized errors, and no response/log contains task tokens or presigned URLs beyond the intended upload response.
8. **Observability:** inspect CloudWatch logs for each Lambda and Step Functions execution history. Check only fixed error messages and correlation data; do not print secrets or document bytes.

## Cleanup and cost control

After testing, remove test employee records and test documents only after confirming the data is disposable. The WP3 documents bucket is versioned; remove current objects, object versions, and delete markers before deleting its stack. Delete stacks in reverse dependency order only after reviewing their resources and retaining any data you need: `hrms-dev-api`, `hrms-dev-workflow`, `hrms-dev-documents`, `hrms-dev-stages`, then `hrms-dev-foundation`.

Do not run stack deletion automatically. Confirm there are no remaining test Step Functions executions, S3 objects/versions, or SNS subscriptions you intend to retain.

## CI verification

The repository workflow `.github/workflows/unit-tests.yml` validates the SAM templates and runs the WP1/WP2/WP3/WP4/WP5 offline regression suites on `v1-solo` and pull requests targeting `v1-solo`. These checks use mocks and do not deploy or call live AWS resources.
