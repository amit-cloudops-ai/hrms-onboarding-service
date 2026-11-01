import { Amplify } from "aws-amplify";
import {
  confirmResetPassword,
  confirmSignIn,
  fetchAuthSession,
  resetPassword,
  signIn as cognitoSignIn,
  signOut as cognitoSignOut,
} from "aws-amplify/auth";
import { cognitoUserPoolsTokenProvider } from "aws-amplify/auth/cognito";
import { sessionStorage } from "aws-amplify/utils";

const USER_POOL_ID = import.meta.env.VITE_COGNITO_USER_POOL_ID || "us-east-1_UHdj6I89K";
const CLIENT_ID = import.meta.env.VITE_COGNITO_CLIENT_ID || "";
const KEYS = ["hrms_id_token","hrms_access_token","hrms_refresh_token","hrms_token_expiry","hrms_oauth_state","hrms_oauth_verifier"];

if (USER_POOL_ID && CLIENT_ID) {
  Amplify.configure({
    Auth: {
      Cognito: {
        userPoolId: USER_POOL_ID,
        userPoolClientId: CLIENT_ID,
        loginWith: { email: true },
      },
    },
  });
  // Keep the previous session-only behavior; tokens are not persisted across browser restarts.
  cognitoUserPoolsTokenProvider.setKeyValueStorage(sessionStorage);
}

export function isAuthConfigured(): boolean {
  return Boolean(USER_POOL_ID && CLIENT_ID);
}

export async function signIn(username: string, password: string) {
  if (!isAuthConfigured()) throw new Error("Cognito is not configured. Set VITE_COGNITO_USER_POOL_ID and VITE_COGNITO_CLIENT_ID.");
  return cognitoSignIn({
    username: username.trim().toLowerCase(),
    password,
    options: { authFlowType: "USER_SRP_AUTH" },
  });
}

export async function completeSignIn(challengeResponse: string) {
  return confirmSignIn({ challengeResponse });
}

export async function startPasswordReset(username: string) {
  return resetPassword({ username: username.trim().toLowerCase() });
}

export async function finishPasswordReset(username: string, confirmationCode: string, newPassword: string) {
  return confirmResetPassword({
    username: username.trim().toLowerCase(),
    confirmationCode: confirmationCode.trim(),
    newPassword,
  });
}

export async function getIdToken(): Promise<string | null> {
  if (!isAuthConfigured()) return null;
  try {
    // Amplify refreshes expired tokens automatically when a valid refresh token exists.
    const session = await fetchAuthSession();
    return session.tokens?.idToken?.toString() || null;
  } catch {
    return null;
  }
}

export async function signOut(): Promise<void> {
  KEYS.forEach(key => sessionStorage.removeItem(key));
  await cognitoSignOut();
  window.location.reload();
}
