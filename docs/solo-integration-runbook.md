# Solo integration runbook — WP1/WP2/WP3/WP4/WP5

This runbook is for a separately approved test in Amit's AWS account. **Nothing in this document has been deployed by these code changes.** The unit tests and SAM validation are offline. Do not run deployment commands until the AWS account, region, existing table names, Cognito pool/client, and expected costs have been checked.

## Integration shape

- WP1 creates the employee record and Cognito identity, persisting immutable Cognito `sub`.
- WP5 authenticates requests through API Gateway's Cognito JWT authorizer and enforces HR-admin/self-service authorization.
- WP2 owns the four-stage Step Functions state machine and persists each active task token.
- WP4 handles simulated/real IT provisioning, versioned policy acceptance, and manager-intro completion.
- WP3 issues scoped presigned PUT URLs, validates actual uploaded bytes, stores document status, notifies HR on rejection, and resumes document collection after all three required documents pass.

## Pre-deployment checks

1. Confirm AWS CLI is authenticated to the intended account: `aws sts get-caller-identity`.
2. Confirm the region is `us-east-1` and the existing DynamoDB tables (employees, stages, documents, and equipment) match `docs/data-model.md`.
3. Confirm the existing Cognito user pool, app client, and `hr-admins` group.
4. Confirm the chosen S3 upload origin (exact portal origin) and SNS notification subscriptions.
5. Confirm a real provisioning adapter is not required for the first test. Use simulated IT provisioning for the first pass.
6. Check current AWS pricing and set a budget alert. These templates create Lambda functions, a Standard Step Functions state machine, SNS topics, and a versioned S3 bucket. Do not deploy duplicate stacks if equivalent resources already exist.

## Deploy order

The order matters because the API and workflow refer to the stage handler, and the document service calls the stage handler.

### 1. WP4 stage handler

```bash
sam build --template-file services/stages/template.yaml
sam deploy --guided --template-file .aws-sam/build/template.yaml --stack-name hrms-dev-stages --capabilities CAPABILITY_IAM --parameter-overrides SimulationMode=true
```

Record the `StagesFunctionName` and `StageNotificationTopicArn` outputs. The first output is passed to WP2, WP3, and WP5. Subscribe the authorized manager/HR notification endpoint to the topic if required.

### 2. WP3 document service

Replace the origin with the exact browser origin that will upload files.

```bash
sam build --template-file services/documents/template.yaml
sam deploy --guided --template-file .aws-sam/build/template.yaml --stack-name hrms-dev-documents --capabilities CAPABILITY_IAM --parameter-overrides StagesFunctionName=hrms-dev-stages UploadAllowedOrigin=https://YOUR-PORTAL-ORIGIN
```

Record `DocumentsFunctionName`, `DocumentsBucketName`, and `HrDocumentNotificationsTopicArn`. Subscribe only an authorized HR endpoint to the notification topic. Confirm the bucket's public-access block, encryption, versioning, and CORS origin in the console.

### 3. WP2 workflow

```bash
sam build --template-file services/workflow/template.yaml
sam deploy --guided --template-file .aws-sam/build/template.yaml --stack-name hrms-dev-workflow --capabilities CAPABILITY_IAM --parameter-overrides StagesFunctionName=hrms-dev-stages
```

Record the `StateMachineArn` output. Confirm the workflow role can invoke `hrms-dev-stages` and the stage role can call `states:SendTaskSuccess`.

### 4. WP5 API

Use the real existing Cognito pool/client IDs and the State Machine ARN output from WP2.

```bash
sam build --template-file services/api/template.yaml
sam deploy --guided --template-file .aws-sam/build/template.yaml --stack-name hrms-dev-api --capabilities CAPABILITY_IAM --parameter-overrides CognitoUserPoolId=YOUR_POOL_ID CognitoAppClientId=YOUR_APP_CLIENT_ID StateMachineArn=YOUR_STATE_MACHINE_ARN DocumentsFunctionName=hrms-dev-documents StagesFunctionName=hrms-dev-stages
```

Record `ApiEndpoint`. Do not put real tokens, temporary passwords, document contents, or credentials into GitHub issues or logs.

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

After testing, remove test employee records and test documents only after confirming the data is disposable. The documents bucket is versioned; remove current objects **and object versions/delete markers** before deleting the stack. Then delete stacks in reverse dependency order: `hrms-dev-api`, `hrms-dev-workflow`, `hrms-dev-documents`, `hrms-dev-stages`. Before stack deletion, inspect each stack's resources and retain any resource that contains data you need. Confirm there are no remaining test Step Functions executions, S3 objects/versions, or SNS subscriptions you intended to remove.

Do not run `sam deploy` or stack deletion automatically. Review the change set and account identity first.

## CI verification

The repository workflow `.github/workflows/unit-tests.yml` validates all four SAM templates and runs the WP1/WP2/WP3/WP4/WP5 offline regression suites on the solo branch and on pull requests targeting `v1-solo`. These checks use mocks and do not deploy or call live AWS resources.
