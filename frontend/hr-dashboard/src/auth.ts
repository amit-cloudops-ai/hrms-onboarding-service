const DOMAIN = (import.meta.env.VITE_COGNITO_DOMAIN || "").replace(/\/$/, "");
const CLIENT_ID = import.meta.env.VITE_COGNITO_CLIENT_ID || "";
const REDIRECT_URI = import.meta.env.VITE_AUTH_REDIRECT_URI || window.location.origin;
const LOGOUT_URI = import.meta.env.VITE_LOGOUT_REDIRECT_URI || window.location.origin;
const SCOPES = (import.meta.env.VITE_COGNITO_SCOPES || "openid email profile").trim();
const KEYS = { id: "hrms_id_token", access: "hrms_access_token", refresh: "hrms_refresh_token", expiry: "hrms_token_expiry", state: "hrms_oauth_state", verifier: "hrms_oauth_verifier" };
let callbackPromise: Promise<void> | null = null;

export function isAuthConfigured(): boolean {
  return Boolean(DOMAIN && CLIENT_ID && REDIRECT_URI && LOGOUT_URI);
}

function base64Url(bytes: Uint8Array): string {
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}
function randomUrlSafe(length: number): string {
  return base64Url(crypto.getRandomValues(new Uint8Array(length)));
}
async function codeChallenge(verifier: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(verifier));
  return base64Url(new Uint8Array(digest));
}
function saveTokens(tokens: { id_token?: string; access_token?: string; refresh_token?: string; expires_in?: number }): void {
  if (!tokens.id_token || !tokens.access_token) throw new Error("Cognito did not return the expected sign-in tokens.");
  sessionStorage.setItem(KEYS.id, tokens.id_token);
  sessionStorage.setItem(KEYS.access, tokens.access_token);
  if (tokens.refresh_token) sessionStorage.setItem(KEYS.refresh, tokens.refresh_token);
  sessionStorage.setItem(KEYS.expiry, String(Date.now() + Math.max(60, Number(tokens.expires_in) || 3600) * 1000));
}
function clearTokens(): void {
  [KEYS.id, KEYS.access, KEYS.refresh, KEYS.expiry, KEYS.state, KEYS.verifier].forEach(key => sessionStorage.removeItem(key));
}
async function tokenRequest(body: URLSearchParams): Promise<Record<string, unknown>> {
  const response = await fetch(`${DOMAIN}/oauth2/token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
    credentials: "omit",
  });
  const payload = await response.json().catch(() => ({})) as Record<string, unknown>;
  if (!response.ok) throw new Error("Cognito sign-in could not be completed. Check the app client and callback URL configuration.");
  return payload;
}

export async function signIn(): Promise<void> {
  if (!isAuthConfigured()) throw new Error("Cognito sign-in is not configured. Set VITE_COGNITO_DOMAIN, VITE_COGNITO_CLIENT_ID, and the redirect URLs.");
  const state = randomUrlSafe(32);
  const verifier = randomUrlSafe(64);
  sessionStorage.setItem(KEYS.state, state);
  sessionStorage.setItem(KEYS.verifier, verifier);
  const query = new URLSearchParams({
    response_type: "code", client_id: CLIENT_ID, redirect_uri: REDIRECT_URI, scope: SCOPES,
    state, code_challenge: await codeChallenge(verifier), code_challenge_method: "S256",
  });
  window.location.assign(`${DOMAIN}/oauth2/authorize?${query.toString()}`);
}

export function handleAuthRedirect(): Promise<void> {
  if (callbackPromise) return callbackPromise;
  const params = new URLSearchParams(window.location.search);
  const code = params.get("code");
  const providerError = params.get("error");
  if (!code && !providerError) return Promise.resolve();
  callbackPromise = (async () => {
    const returnedState = params.get("state");
    const expectedState = sessionStorage.getItem(KEYS.state);
    const verifier = sessionStorage.getItem(KEYS.verifier);
    window.history.replaceState({}, document.title, window.location.pathname + window.location.hash);
    sessionStorage.removeItem(KEYS.state);
    sessionStorage.removeItem(KEYS.verifier);
    if (providerError) { clearTokens(); throw new Error("Cognito rejected sign-in. Verify the user pool app client and hosted UI configuration."); }
    if (!code || !returnedState || !expectedState || returnedState !== expectedState || !verifier) {
      clearTokens();
      throw new Error("The sign-in response could not be validated. Please start sign-in again.");
    }
    try {
      const tokens = await tokenRequest(new URLSearchParams({
        grant_type: "authorization_code", client_id: CLIENT_ID, code, redirect_uri: REDIRECT_URI, code_verifier: verifier,
      }));
      saveTokens(tokens as { id_token?: string; access_token?: string; refresh_token?: string; expires_in?: number });
    } catch (error) {
      clearTokens();
      throw error;
    }
  })().finally(() => { callbackPromise = null; });
  return callbackPromise;
}

export async function getIdToken(): Promise<string | null> {
  if (!isAuthConfigured()) return null;
  const idToken = sessionStorage.getItem(KEYS.id);
  const refreshToken = sessionStorage.getItem(KEYS.refresh);
  const expiry = Number(sessionStorage.getItem(KEYS.expiry) || "0");
  if (idToken && expiry > Date.now() + 60_000) return idToken;
  if (!refreshToken) {
    clearTokens();
    return null;
  }
  try {
    const payload = await tokenRequest(new URLSearchParams({
      grant_type: "refresh_token", client_id: CLIENT_ID, refresh_token: refreshToken,
    }));
    const nextId = payload.id_token;
    const nextAccess = payload.access_token;
    if (typeof nextId !== "string" || typeof nextAccess !== "string") throw new Error("Token refresh response was incomplete.");
    sessionStorage.setItem(KEYS.id, nextId);
    sessionStorage.setItem(KEYS.access, nextAccess);
    if (typeof payload.refresh_token === "string") sessionStorage.setItem(KEYS.refresh, payload.refresh_token);
    sessionStorage.setItem(KEYS.expiry, String(Date.now() + Math.max(60, Number(payload.expires_in) || 3600) * 1000));
    return nextId;
  } catch {
    clearTokens();
    return null;
  }
}

export function signOut(): void {
  clearTokens();
  if (!isAuthConfigured()) return;
  const query = new URLSearchParams({ client_id: CLIENT_ID, logout_uri: LOGOUT_URI });
  window.location.assign(`${DOMAIN}/logout?${query.toString()}`);
}
