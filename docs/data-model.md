# Data model (DynamoDB)

The deployed team evaluation environment uses the `hrms-team-*` table names below. Some standalone SAM templates retain `hrms-dev-*` defaults for local development; the team deployment must pass the team table names explicitly.

| Table | Keys | Attributes |
|---|---|---|
| `hrms-team-employees` | PK `employee_id` (UUID) | `full_name`, `email`, `cognito_sub` (internal immutable Cognito subject), `department`, `role`, `manager_id`, `joining_date`, `employment_type`, `status`, `execution_arn`, `created_at`, `onboarding_completed_at`, `completion_email_status`, `completion_email_started_at`, `completion_email_sent_at`, `completion_email_message_id`, `completion_email_error` |
| `hrms-team-onboarding-stages` | PK `employee_id`, SK `stage` | `status` (pending, in_progress, complete, failed), `started_at`, `completed_at`, `failed_at`, `failure_code`, `correlation_id`, `reminder_count`, `task_token` (backend-only), `documents_verified`, `policy_id`, `policy_version`, `policy_accepted`, `policy_accepted_at`, `policy_accepted_by`, `admin_override`, `admin_override_by`, `admin_override_at` |
| `hrms-team-documents` | PK `employee_id`, SK `doc_type` | `s3_key` (internal), `status` (missing, uploaded, verified, rejected), `file_size`, `content_type`, `requested_at`, `validated_at` |
| `hrms-team-equipment` | PK `asset_id` | `type`, `model`, `status` (available, assigned), `assigned_to` |

## Indexes

- `hrms-team-employees/status-index`: partition key `status`, used for employee lifecycle filtering.
- `hrms-team-employees/cognito-sub-index`: partition key `cognito_sub`, used to resolve the authenticated employee from Cognito's immutable `sub` claim.

## Lifecycle semantics

Employee lifecycle status and notification delivery are independent:

- `employees.status=complete` means all four required onboarding stages have been persisted complete.
- `completion_email_status` is independently `sending`, `sent`, or `failed`.
- An email failure must not revert or hold the employee lifecycle status at `in_progress`.
- A `sending` notification status represents an ambiguous delivery outcome and requires reconciliation before retrying.

## Cost and recovery notes

The audited team tables use `PAY_PER_REQUEST`. Point-in-time recovery was disabled in the 4 November 2026 audit snapshot; review its cost and recovery requirements before enabling it for a production environment.
