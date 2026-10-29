# WP7 — HR onboarding operations dashboard

Premium, responsive HR operations dashboard built with React, TypeScript and Vite, sharing the new-hire portal's Northstar design system.

## Features
- Operational overview: total hires, ready-for-day-one, in-progress, and outstanding onboarding.
- Completion analytics for document collection, IT provisioning, policy sign-off, and manager introduction.
- Upcoming start-date list and searchable/filterable employee pipeline.
- Employee detail dialog with milestone statuses.
- Add-new-hire form mapped to `POST /employees`, with client-side validation.
- CSV export, refresh action, notifications popover, empty states, keyboard-accessible table rows, responsive layout.
- Demo mode has clearly labelled sample data and no AWS side effects.

## Run locally
```bash
npm install
npm run dev
npm run build
```

## Configuration
Copy `.env.example` to `.env.local`. Set `VITE_API_BASE_URL` to the deployed API Gateway HTTP API endpoint (the templates use the `$default` stage; do not append `/dev`) and set `VITE_DEMO_MODE=false`. Configure the Cognito managed-login domain, public app-client ID, and the exact redirect/sign-out URLs. Use the same Cognito user pool as the employee portal, with **authorization code grant + PKCE**, no app-client secret, and `openid email profile` scopes. Add the local and deployed URLs to Cognito's callback and sign-out allowlists.

The dashboard sends a Cognito ID token as a bearer token. API Gateway verifies it; the backend's `hr-admins` group check gates list/create/stage-completion operations. Do not expose AWS credentials, client secrets, or privileged tokens in frontend variables. Without API configuration, the dashboard remains a clearly labelled demo.

## API integration notes
Uses `GET /employees` and `POST /employees` from `../../docs/api-contract.md`. The list response uses the backend's `employee_id`, `full_name`, `joining_date`, and `progress.stages` fields. The create request sends the required `full_name`, `email`, `role`, `department`, `joining_date`, and `employment_type` fields. API Gateway/Cognito and backend role checks remain the security boundary. Demo mode is not connected to a backend.
