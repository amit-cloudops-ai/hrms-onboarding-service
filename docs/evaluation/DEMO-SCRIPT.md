# Demo script — spoken narration

**Opening (30 sec)**

“This project addresses the handoffs involved when a new employee joins. We built an identity-backed onboarding flow where HR can create a new hire, the employee can complete their checklist, and HR can see progress in one place.”

**Architecture (60 sec)**

“Cognito authenticates HR and employees. API Gateway validates the JWT. The API enforces HR-admin and employee-ownership checks. WP1 creates the employee identity, WP2 coordinates the long-running process in Step Functions, WP3 handles private document uploads and validation, and WP4 owns the business-stage adapter boundary. DynamoDB stores employee, document and stage state.”

**HR creation (90 sec)**

“I’ll create a synthetic employee. HR uses a protected API operation. The platform creates a canonical employee record and Cognito identity, then starts onboarding. I’m using fake evaluation data.”

**Employee view (60 sec)**

“Now I’ll sign in as that employee. The portal resolves the employee from the authenticated Cognito subject. It does not trust an employee ID supplied by the browser to grant access to another record.”

**Documents (90 sec)**

“The employee requests a short-lived upload URL and uploads dummy documents directly to private S3. The backend checks the stored upload attempt, object metadata and file signature before updating the document state. It does not mark a file verified just because the browser uploaded it.”

**Workflow (90 sec)**

“Step Functions coordinates the stages. Document collection and policy sign-off are modeled as callback waits. Callback tokens remain on the server side. IT provisioning and manager introduction are represented by deterministic simulated WP4 actions in this evaluation; they are not connected to real business systems.”

**HR visibility (60 sec)**

“Back in the HR dashboard, we can see the same employee and the persisted progress. Refreshing the page does not reset the state.”

**Quality and limits (60 sec)**

“Our latest CI run passed the backend tests, both frontend lint and production builds, production dependency audits, SAM validation/build, CloudFormation lint and deployment script syntax checks. These are offline/template checks plus manual demo evidence; they do not amount to production certification. Gate B needs real provider integrations, live integration testing, security/privacy review and operational readiness.”

**Close (15 sec)**

“Gate A demonstrates the end-to-end evaluation journey and integration architecture. We are not claiming real IT provisioning, manager-calendar integration or production approval.”
