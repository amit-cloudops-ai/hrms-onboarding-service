# API contract

Region: us-east-1. All routes sit behind API Gateway with a Cognito authorizer.

| Method and route | Purpose | Who can call |
|---|---|---|
| POST /employees | Register a new hire and start onboarding | HR admin |
| GET /employees | List all hires with stage status | HR admin |
| GET /employees/{employee_id} | One employee profile | HR admin, that employee |
| GET /employees/{employee_id}/progress | Progress of all four stages | HR admin, that employee |
| POST /employees/{employee_id}/documents/upload-url | One-time upload link for a document type | That employee |
| GET /employees/{employee_id}/documents | Status of each required document | HR admin, that employee |
| POST /employees/{employee_id}/policies/sign | Record policy acceptance | That employee |
| POST /employees/{employee_id}/stages/{stage}/complete | Manually mark a stage done | HR admin |

Stage names: `document_collection`, `it_provisioning`, `policy_signoff`, `manager_intro`
Stage status: `pending`, `in_progress`, `complete`
Document types: `id_proof`, `degree_certificate`, `signed_offer_letter`
Uploads: PDF, JPG, PNG; max 5 MB.
