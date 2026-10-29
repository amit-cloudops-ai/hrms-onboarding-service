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
Copy `.env.example` to `.env.local`. Set `VITE_API_BASE_URL` to the deployed API Gateway base URL and `VITE_DEMO_MODE=false` to use the API. Without an API base URL the dashboard stays in preview mode. Never expose AWS credentials or privileged tokens in frontend variables.

## API integration notes
Uses `GET /employees` and `POST /employees` from `../../docs/api-contract.md`. The dashboard expects the list response to include employee identifiers and stage status; confirm deployed response shapes and auth headers in live integration. API Gateway/Cognito and backend role checks remain the security boundary. Demo mode is not connected to a backend.
