# HR operations dashboard (WP7)

The HR-facing React application for the Smart Employee Onboarding Platform. It gives authorized HR administrators an operational view of employee onboarding and document status.

## Capabilities

- Cognito Hosted UI sign-in using OAuth 2.0 authorization-code flow with PKCE.
- Authenticated requests to the WP5 HTTP API.
- Employee pipeline with search, status filtering and employee details.
- Onboarding stage progress and document review information.
- Employee registration and HR-only actions exposed by the API.
- A mock API adapter for local UI development without AWS access.

## Local development

Requires Node.js 20 or newer.

```bash
cd frontend/hr-dashboard
npm ci
cp .env.example .env.local
npm run dev
```

Open the local URL printed by Vite (normally `http://localhost:5174/` when the portal uses port 5173).

## Configuration

The supplied `.env.example` contains placeholders for:

| Variable | Purpose |
|---|---|
| `VITE_USE_MOCK` | Set to `true` for mock data or `false` for the HTTP API adapter |
| `VITE_API_BASE_URL` | API Gateway HTTP API base URL |
| `VITE_COGNITO_DOMAIN` | Cognito Hosted UI domain |
| `VITE_COGNITO_CLIENT_ID` | Public Cognito app-client ID |
| `VITE_COGNITO_REDIRECT_URI` | OAuth callback URL registered in Cognito |
| `VITE_COGNITO_LOGOUT_URI` | Post-logout redirect URL registered in Cognito |

Copy the example and replace placeholders only in your local `.env.local`. Never put AWS credentials, a Cognito client secret or other private keys in Vite variables.

The API adapter is selected in `src/api/index.js`. UI components use the shared API interface, allowing mock and HTTP implementations to remain separate.

## Validation

```bash
npm run lint
npm run build
```

## Authorization and security notes

- The dashboard requires an authenticated HR administrator.
- The API validates HR-group membership for administrative routes; hiding UI controls is not an authorization mechanism.
- Browser tokens are currently held in `sessionStorage`. Review the authentication architecture, CSP and XSS controls before using the application for real employee data.
- Never commit `.env.local`, credentials, JWTs, presigned URLs or real employee data.

## Screenshots

- [HR employee list](screenshots/hr-list.png)

Use synthetic employee records for evaluation and screenshots.
