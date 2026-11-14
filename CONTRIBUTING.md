# Contributing

Thank you for helping improve the Smart Employee Onboarding Platform. The repository's canonical branch is `main`; all ongoing work should be proposed through a focused pull request.

## Development workflow

1. Check the open issues and current project documentation before starting.
2. Create a feature branch from the latest `main`:
   ```bash
   git switch main
   git pull --ff-only origin main
   git switch -c feature/<work-package>-<short-description>
   ```
3. Keep changes within the owned work package unless a cross-package change is agreed with the maintainers.
4. Use small, descriptive commits such as `feat:`, `fix:`, `test:`, `docs:` and `chore:`.
5. Run the relevant tests, frontend lint/build and template validation.
6. Open a pull request targeting `main`. Include the motivation, affected packages, test commands/results, screenshots for UI changes and any API/data-model changes.
7. Merge only after review and required GitHub Actions checks pass.

## Work-package ownership

| Contributor / area | Primary paths |
|---|---|
| WP1 — Identity | `services/identity/` |
| WP2 — Workflow | `services/workflow/` |
| WP3 — Documents | `services/documents/` |
| WP4 — Stage adapters | `services/stages/` |
| WP5 — API and authorization | `services/api/` |
| WP6 — Employee portal | `frontend/portal/` |
| WP7 — HR dashboard | `frontend/hr-dashboard/` |
| Shared infrastructure and contracts | `infra/`, `docs/` |

See [the contributor record](docs/CONTRIBUTORS.md) and [work-package guide](docs/team-work-packages.md) for the project history and original ownership.

## Engineering rules

- Never commit AWS credentials, access keys, passwords, private keys, Cognito tokens, JWTs, Step Functions task tokens, presigned URLs or `.env.local` files.
- Use synthetic employees and dummy documents in tests and demos.
- Do not trust client-provided employee IDs, roles, email addresses or admin flags as authorization. The backend must validate the Cognito identity and enforce ownership/role checks.
- Keep Step Functions task tokens server-side. Never expose them in browser responses or ordinary logs.
- Keep S3 document storage private and use short-lived, scoped presigned URLs.
- Preserve idempotency and safe retry behavior for event-driven handlers and workflow callbacks.
- Discuss changes to `docs/api-contract.md`, `docs/data-model.md`, stage names, workflow payloads or infrastructure contracts before implementation.
- Review CloudFormation change sets and cost implications before any AWS deployment or resource mutation. CI is validation-only and does not authorize deployment.

## Local validation

Run the relevant backend unit tests from the repository root. For frontend packages, run:

```bash
cd frontend/portal
npm ci
npm run lint
npm run build
```

Repeat for `frontend/hr-dashboard`.

Validate SAM templates without deploying:

```bash
sam validate --lint --template-file services/api/template.yaml
sam validate --lint --template-file services/workflow/template.yaml
sam validate --lint --template-file services/documents/template.yaml
sam validate --lint --template-file services/stages/template.yaml
```

The GitHub Actions workflow runs the broader validation suite on pull requests targeting `main`.

## Definition of done

- The change matches the relevant API and data-model contracts.
- Relevant unit/regression tests pass.
- Frontend lint/build or infrastructure validation passes when applicable.
- Documentation and examples reflect the actual implementation.
- No secrets or real employee data are introduced.
- The pull request is reviewed and required checks pass.

## Branch policy

- `main` is the canonical branch and the only branch intended for the current project release.
- Use short-lived feature branches created from `main`.
- The historical `team-dev` and `v1-solo` branches are retained as project-development history; do not use them as the base for new work.
