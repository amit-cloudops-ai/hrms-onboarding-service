# Northstar custom Cognito authentication

## Decision

Both the Employee Portal and HR Dashboard now use the same in-app Northstar sign-in experience. The browser no longer redirects to the Cognito hosted login page. Cognito remains the identity provider and the API remains the authorization boundary.

The frontend uses AWS Amplify Auth v6 with Cognito's `USER_SRP_AUTH` flow. The password is processed through Secure Remote Password authentication rather than being sent as a plain password authentication request. The user pool, public app client, groups, JWT issuer and API Gateway authorizer remain the same.

## Shared experience

- Northstar brand mark, typography, pale background, white surface, navy brand mark and restrained lavender accent match the existing portal/dashboard design language.
- Separate employee and HR workspace labels and copy.
- Email and password sign-in.
- Temporary-password / first-login password change.
- MFA challenge selection and TOTP, SMS or email challenge entry where enabled by Cognito.
- TOTP setup hand-off through the authenticator URI.
- Forgot-password, email code and password reset.
- Session restoration and refresh through Amplify `fetchAuthSession`.
- Session-only token persistence using browser `sessionStorage`, preserving the previous tab-scoped session behavior.
- Sign-out clears the Amplify session and returns to the sign-in screen.

## Configuration

Set these in each frontend's uncommitted `.env.local` file:

```dotenv
VITE_COGNITO_USER_POOL_ID=us-east-1_UHdj6I89K
VITE_COGNITO_CLIENT_ID=1p5860pgdk2jc0nqgo1217sh8
VITE_API_BASE_URL=https://mv5cyfzsya.execute-api.us-east-1.amazonaws.com
VITE_DEMO_MODE=false
```

The user pool ID currently has a development fallback in the frontend auth module; set it explicitly in deployment environments. The app client ID is public by design. Never add a Cognito app-client secret to a browser app.

The old hosted-domain, OAuth callback URL and logout URL values are no longer used by the frontend sign-in flow. The Cognito domain and OAuth configuration can remain provisioned for administrative or future federation needs; no CloudFormation update is required for this UI change.

The existing app client template already enables `ALLOW_USER_SRP_AUTH` and `ALLOW_REFRESH_TOKEN_AUTH`. The implementation therefore does not require an AWS resource change.

## API token contract

The existing API client continues to send the Cognito ID token as a bearer token. The token is retrieved through Amplify `fetchAuthSession()`, which refreshes the session when a valid refresh token is available. API Gateway's JWT authorizer and backend group/employee ownership checks remain authoritative. The UI does not decide whether a user is an HR administrator.

## Local run

Install dependencies in each frontend after pulling the branch:

```bash
cd frontend/portal && npm install && npm run dev
cd frontend/hr-dashboard && npm install && npm run dev
```

Use the existing local URLs:
- Employee Portal: http://localhost:5173
- HR Dashboard: http://localhost:5174

## Acceptance gates

- [ ] Install Amplify dependencies and pass both TypeScript/Vite production builds.
- [ ] Employee test account signs in through the in-app form; no Cognito hosted login page appears.
- [ ] HR admin account signs in through the same branded form.
- [ ] A regular employee is denied HR API operations by backend authorization.
- [ ] HR admin can load the HR dashboard.
- [ ] Employee can load only their own onboarding profile.
- [ ] First-login temporary password change succeeds.
- [ ] Forgot-password code and reset succeed.
- [ ] TOTP/SMS/email challenges are completed correctly when enabled in the pool.
- [ ] Refresh token renewal works after the 15-minute access/ID token lifetime.
- [ ] Sign-out clears the session; reloading returns to sign-in.
- [ ] Both frontends build successfully in GitHub Actions.
- [ ] Real browser sign-in and API access are verified against the deployed development pool.

## Security and release notes

- No passwords, reset codes, MFA codes, refresh tokens or ID tokens are written to source control.
- No Cognito client secret is used.
- Tokens are kept in session storage and are cleared when the tab session ends.
- The development pool currently has MFA disabled. The UI can handle Cognito challenge steps, but production MFA policy must be enabled and tested separately.
- A successful frontend build is not proof of a successful real Cognito sign-in. Complete the live browser acceptance gates before calling authentication production-ready.
