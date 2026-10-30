# Contributing

## Workflow
1. Claim a work package Issue (comment "I'll take this").
2. Create a branch: `feature/<package>-<short-name>`, e.g. `feature/wp3-upload-validation`.
3. Make small commits using a type prefix: `feat:`, `fix:`, `docs:`, `chore:`.
4. Open a pull request into `team-dev` using the template. At least one review from the lead is required.
5. After approval, squash and merge. Delete the branch.

## Rules
- Work only inside your own package folder.
- Never commit secrets, keys, tokens or `.env` files. Use SSM Parameter Store.
- Resource names: `hrms-dev-<component>`, for example `hrms-dev-documents-bucket`.
- Do not change `docs/api-contract.md` or `docs/data-model.md` without asking the lead.
- Every package folder has a README: what it does, how to test it, its input and output.

## Definition of done
- Meets the package's "done when" checklist in the Issue
- Works against the API contract
- README written
- Reviewed and merged via pull request

## Branches
- `main`: stable, evaluation-ready. Changes arrive only by pull request from `team-dev`.
- `team-dev`: shared integration branch. Feature branches start here and merge back here.
- `v1-solo`: the lead's independent implementation. Not open for team contributions.
