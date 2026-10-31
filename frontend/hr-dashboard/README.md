# HR dashboard (WP7)

HR-facing interface for the Smart Employee Onboarding & Identity Service.

## What it does
- Employee list with search and a status filter
- Per-employee stage progress (4 stages) at a glance
- Employee detail panel with stages and documents
- Register a new hire (form with validation)
- Mark a stage complete (with a confirm step)
- Loading, empty, error and success states

## Run locally
Requires Node.js 20 or newer.

```bash
cd frontend/hr-dashboard
npm install
npm run dev
```

Open the address printed in the terminal. If the portal is already running on port 5173, this app uses the next free port (for example 5174).

Production build check: `npm run build`

## Mock data (no backend needed)
All data comes from `src/api/`, which has the same files as the portal (`constants.js`, `validation.js`, `mockData.js`, `mockApi.js`, `index.js`). Components only call `api` from `src/api/index.js`, so the mock layer can be replaced with real HTTP calls later.

The "Demo controls" row at the bottom (Simulate error, Toggle slow network) is for screenshots and demos only. Remove it before connecting the real API.

## Connecting the real API later
1. Add an HTTP implementation with the same function names as `mockApi.js`.
2. Point `api` in `src/api/index.js` at it.
3. Add the HR login and token handling.
4. Keep the API base URL in an environment variable. Never commit credentials or secrets.

## Assumptions to confirm with the API owner
- JSON response shapes, including whether `GET /employees` returns each employee's stages (the mock does)
- Allowed values of employee `status` (mock uses `onboarding` and `ready`)
- Allowed values of `employment_type` (mock uses `full_time`, `part_time`, `contract`)
- No route exists for HR to verify or reject a document, so documents are read-only here
- How HR logs in

## Screenshots
| Screen | File |
|---|---|
| Employee list | `screenshots/hr-list.png` |
| Employee detail | `screenshots/hr-detail.png` |
| Register new hire | `screenshots/hr-register.png` |
| Error | `screenshots/hr-error.png` |
| Mobile | `screenshots/hr-mobile.png` |
