# WP1 — Identity service

Owner: Amit  
Runtime target: AWS Lambda, Python 3.12  
Region: `us-east-1`

## Responsibility

Create the canonical employee record in `hrms-dev-employees` and create the corresponding Cognito user. The service returns the employee ID and safe status fields only; it never returns temporary credentials.

## Contract

Input fields are aligned with `docs/data-model.md`:

- Required: `full_name`, `email`, `department`, `role`, `joining_date`, `employment_type`
- Optional: `manager_id`

The API contract defines `POST /employees` as an HR-admin-only route. WP5 must enforce Cognito authentication and HR-admin authorization before invoking this service. Do not treat this module's input validation as an authorization boundary.

Successful result: `employee_id`, `email`, `status`, `created_at`.

## Configuration

- `EMPLOYEES_TABLE` — defaults to `hrms-dev-employees`
- `COGNITO_USER_POOL_ID` — required
- Lambda execution role requires narrowly scoped DynamoDB write/delete permissions for the employee table and `cognito-idp:AdminCreateUser` for the intended user pool.
- Configure Cognito's invitation email delivery before enabling real invitations. Do not hardcode credentials or AWS keys.

The function writes the employee record first and then creates the Cognito user. If Cognito creation fails, it attempts to remove the record. Review CloudWatch logs and cleanup outcomes during integration testing.

## Local tests

From this directory:

```bash
python -m unittest -v
```

AWS SDK dependencies are provided by the Lambda Python runtime; for local execution install `boto3` in your development environment if it is not already available.

## Integration notes

- WP5 owns API Gateway route mapping, request parsing at the API boundary, and HR-admin authorization.
- WP2 starts the Step Functions workflow after employee identity creation succeeds.
- The current API contract does not specify a detailed request schema or response envelope. The field mapping above follows the existing data model; coordinate any required response-shape adjustment with Amit before changing the shared contract.
