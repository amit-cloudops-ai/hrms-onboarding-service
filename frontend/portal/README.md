# Employee onboarding portal (WP6)

The employee-facing React application for the Smart Employee Onboarding Platform. It provides an authenticated view of onboarding progress, required documents and policy actions.

## Capabilities

- Cognito Hosted UI sign-in using OAuth 2.0 authorization-code flow with PKCE.
- Employee self-service through the authenticated WP5 HTTP API.
- Four-stage onboarding progress: `document_collection`, `it_provisioning`, `policy_signoff`, `manager_intro`.
- Document upload flow for identity proof, degree certificate and signed offer letter.
- Policy acknowledgement and clear loading, empty, error and success states.
- A mock API adapter for local UI development without AWS access.

## Local development

Requires Node.js 20 or newer.

```bash
cd frontend/portal
npm ci
cp .env.example .env.local
npm run dev
```

Open the local URL printed by Vite (normally `http://localhost:5173/`).

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

Copy the example and replace placeholders only in your local `.env.local`. The Cognito app client is public; never put a client secret, AWS credential or other private key in Vite variables.

The API adapter is selected in `src/api/index.js`. Components call the shared API interface rather than importing mock data directly.

## Validation

```bash
npm run lint
npm run build
```

## Authentication and security notes

- The portal uses the signed-in user's Cognito session and sends a bearer token to the API.
- The backend remains the authorization boundary; employee ownership is enforced using the immutable Cognito subject.
- Browser tokens are currently held in `sessionStorage`. Review the authentication architecture, CSP and XSS controls before using the application for real employee data.
- Never commit `.env.local`, credentials, JWTs, presigned URLs, employee documents or real employee data.

## Screenshots

- [Portal overview](screenshots/portal-home.png)

The demo should use synthetic identities and dummy documents.
