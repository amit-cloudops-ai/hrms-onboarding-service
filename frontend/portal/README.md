# WP6 — New-hire onboarding portal

Premium, responsive employee-facing onboarding workspace built with React, TypeScript and Vite. The visual direction is a calm, light enterprise interface: generous whitespace, restrained lavender accents, clear progress, and task cards with accessible controls.

## Features
- Personal onboarding overview with four-stage progress and checklist.
- Required document uploads (PDF/JPG/PNG, max 5 MB) with upload URL → direct S3 PUT flow in live mode.
- Policy acceptance for acceptable use, privacy, and security.
- Equipment and manager-introduction status cards.
- Responsive mobile navigation, support dialog, loading/error feedback, keyboard focus states, and reduced-motion support.
- Demo mode works without AWS or credentials; sample data is explicitly labelled.

## Run locally
```bash
npm install
npm run dev
npm run build
```

## Configuration
Copy `.env.example` to `.env.local` and set:
- `VITE_API_BASE_URL` to the deployed API Gateway HTTP API endpoint (the templates use the `$default` stage, so do not append `/dev`).
- `VITE_DEMO_MODE=false`.
- `VITE_COGNITO_DOMAIN` to the Cognito managed-login domain and `VITE_COGNITO_CLIENT_ID` to the public app-client ID.
- `VITE_AUTH_REDIRECT_URI` and `VITE_LOGOUT_REDIRECT_URI` to the exact callback and sign-out URLs configured in the Cognito app client.

Configure Cognito OAuth **authorization code grant with PKCE**, allow the `openid`, `email`, and `profile` scopes, and add each exact frontend callback/sign-out URL to the app-client allowlists. Use a public SPA app client with **no client secret**. Never place AWS credentials, client secrets, or backend administrative tokens in frontend variables.

For live mode, the portal calls `GET /employees/me` and resolves the employee using the authenticated Cognito `sub`; do not configure an employee ID in the browser. HR must create/link that Cognito identity to the employee record first. API role and ownership checks remain server-side. Without an API URL, the portal stays in preview mode.

## API assumptions
Uses the routes in `../../docs/api-contract.md`. The current progress route returns stage statuses and policy acceptance metadata, while the documents route returns the three document states. Browser uploads require the API's presigned S3 URL and matching bucket CORS configuration.

## Scope and security
The UI is a client, not an authorization boundary. Enforce employee ownership and roles in API Gateway/Lambda. Policy acceptance is submitted with policy ID, version and `accepted: true`; demo-mode acceptance is local UI state only.
