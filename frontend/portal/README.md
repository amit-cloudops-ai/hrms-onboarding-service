# New-hire portal (WP6)

Employee-facing interface for the onboarding journey of the Smart Employee Onboarding & Identity Service.

## What it does
- Shows the employee's progress across the 4 stages: `document_collection`, `it_provisioning`, `policy_signoff`, `manager_intro`
- Document submission for `id_proof`, `degree_certificate`, `signed_offer_letter` (PDF / JPG / PNG, max 5 MB, checked in the browser before upload)
- Policy sign-off
- Loading, empty, error and success states

## Run locally
Requires Node.js 20 or newer.

```bash
cd frontend/portal
npm install
npm run dev
```

Open the address printed in the terminal (usually http://localhost:5173/).

Production build check: `npm run build`

## Mock data (no backend needed)
All data comes from `src/api/`. Components never import mock data directly, they only call `api` from `src/api/index.js`.

| File | Purpose |
|---|---|
| `constants.js` | Stage names, document types, statuses, upload limits (from `docs/api-contract.md`) |
| `validation.js` | Client-side upload checks (the backend still validates) |
| `mockData.js` | Fake employees, stages and documents shaped like `docs/data-model.md` |
| `mockApi.js` | One function per contract route, with simulated delay and errors |
| `index.js` | Single import point; swap this to real HTTP calls later |

The "Demo controls" row at the bottom of the page (Simulate error, Toggle slow network) is for screenshots and demos only. Remove it before connecting the real API.

## Connecting the real API later
1. Add an HTTP implementation with the same function names as `mockApi.js`.
2. Point `api` in `src/api/index.js` at it.
3. Get the employee id and auth token from the login session instead of `MOCK_CURRENT_EMPLOYEE_ID`.
4. Keep any API base URL in an environment variable. Never commit credentials or secrets.

## Assumptions to confirm with the API owner
- JSON response shapes (the contract lists routes only)
- Response of `POST .../documents/upload-url` (mock returns `upload_url`, `doc_type`, `expires_in_seconds`)
- `POST .../policies/sign` body and whether individual policies must be listed
- How the employee logs in

## Screenshots
| Screen | File |
|---|---|
| Progress, documents, policy sign-off | `screenshots/portal-home.png` |
| Loading | `screenshots/portal-loading.png` |
| Error | `screenshots/portal-error.png` |
| Mobile | `screenshots/portal-mobile.png` |
