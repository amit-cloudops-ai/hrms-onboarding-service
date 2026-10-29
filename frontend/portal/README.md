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
Copy `.env.example` to `.env.local` and set `VITE_API_BASE_URL` to the deployed API Gateway base URL and `VITE_DEMO_MODE=false`. Set `VITE_DEMO_EMPLOYEE_ID` to a valid employee UUID. Without an API base URL, the portal automatically stays in preview mode. Never put AWS credentials in frontend environment variables.

## API assumptions
Uses the routes in `../../docs/api-contract.md`. Live progress/document response shapes are normalized defensively; confirm the deployed API payload shape during integration testing. Browser uploads require the API's presigned S3 URL and matching bucket CORS configuration.

## Scope and security
The UI is a client, not an authorization boundary. Enforce employee ownership and roles in API Gateway/Lambda. Policy acceptance is submitted with policy ID, version and `accepted: true`; demo-mode acceptance is local UI state only.
