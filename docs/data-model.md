# Data model (DynamoDB)

| Table | Keys | Attributes |
|---|---|---|
| hrms-dev-employees | PK employee_id (UUID) | full_name, email, cognito_sub (internal immutable Cognito subject), department, role, manager_id, joining_date, employment_type, status, execution_arn, created_at |
| hrms-dev-onboarding-stages | PK employee_id, SK stage | status, started_at, completed_at, reminder_count, task_token |
| hrms-dev-documents | PK employee_id, SK doc_type | s3_key, status (missing, uploaded, verified, rejected), file_size, content_type, validated_at |
| hrms-dev-equipment | PK asset_id | type, model, status (available, assigned), assigned_to |

GSI on `hrms-dev-employees`: `status-index` (PK status) for the HR dashboard.
