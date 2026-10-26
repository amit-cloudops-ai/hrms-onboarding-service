# Infrastructure

This folder contains the AWS SAM/CloudFormation infrastructure for the solo implementation.

## Foundation template

`template.yaml` creates the four DynamoDB tables in `docs/data-model.md`, a private encrypted S3 document bucket, an SNS topic for HR notifications, a Cognito user pool, and the `HRAdmin` / `Employee` groups.

Security and cost defaults:

- DynamoDB uses on-demand billing; point-in-time recovery is disabled by default and can be enabled after reviewing its cost.
- The S3 bucket blocks public access, enforces TLS, enables S3-managed encryption and versioning, and expires noncurrent object versions after 30 days.
- The Cognito web client has no client secret. Access and ID tokens are short-lived.
- No API, Lambda functions, SES sender identities, or Step Functions state machine are created yet. Those belong in later tested increments.

## Prerequisites

- AWS CLI v2, AWS SAM CLI, Python 3.12, and Docker.
- An authenticated IAM identity with only the permissions required for the deployment.
- AWS region `us-east-1`.

From the repository root, confirm the branch and working tree before pulling:

```bash
git status --short --branch
git switch v1-solo
git pull --ff-only origin v1-solo
aws sts get-caller-identity
aws configure get region
```

## Validate before deployment

```bash
sam validate --lint --template-file infra/template.yaml
```

Do not deploy if validation reports errors. Review the template and the resulting CloudFormation change set before approving it.

## Deploy

First run the validation above. Then start the guided deployment:

```bash
sam deploy --guided --template-file infra/template.yaml
```

Use these values when prompted:

- Stack name: `hrms-dev-foundation`
- Region: `us-east-1`
- Environment: `dev`
- EnablePointInTimeRecovery: `false`
- Confirm changes before deploy: `Y`
- Allow SAM CLI IAM role creation: `N` (the foundation currently declares no Lambda functions or IAM roles)
- Save arguments to configuration file: optional

Inspect the proposed resources and charges before confirming deployment. Do not deploy if the stack already exists with resources you have not inspected. Do not use `--no-confirm-changeset` for the first deployment.

## Verify

```bash
aws cloudformation describe-stacks \
  --stack-name hrms-dev-foundation \
  --region us-east-1 \
  --query 'Stacks[0].[StackStatus,CreationTime]' \
  --output table

aws cloudformation describe-stack-resources \
  --stack-name hrms-dev-foundation \
  --region us-east-1 \
  --query 'StackResources[].[LogicalResourceId,ResourceType,ResourceStatus]' \
  --output table
```

## Cleanup

Only run this if you intend to remove the development foundation and have verified the stack contains no data you need:

```bash
aws cloudformation delete-stack \
  --stack-name hrms-dev-foundation \
  --region us-east-1
aws cloudformation wait stack-delete-complete \
  --stack-name hrms-dev-foundation \
  --region us-east-1
```

The S3 bucket must be empty before CloudFormation can delete it. Because versioning is enabled, delete every object version and delete marker before deleting the stack. Never run cleanup against a production stack or one containing real employee documents.

## Cost and safety notes

- The $5 AWS Budget sends an alert; it does not stop resources or cap spending.
- The template does not provision compute or a database instance. DynamoDB is pay-per-request.
- S3 storage/requests, Cognito, SNS, and related usage may still incur charges.
- Use synthetic test data only. Never commit credentials, tokens, generated deployment files, or employee data.
