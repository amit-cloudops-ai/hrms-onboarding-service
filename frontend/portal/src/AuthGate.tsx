import { ArrowRight, Fingerprint, LockKeyhole, ShieldCheck } from "lucide-react";

type Props = { workspace: string; title: string; description: string; configured: boolean; error?: string; onSignIn: () => void };
export function AuthGate({ workspace, title, description, configured, error, onSignIn }: Props) {
  return <main className="auth-page">
    <section className="auth-card">
      <div className="auth-brand"><span className="auth-mark"><Fingerprint size={23}/></span><span><b>northstar</b><small>PEOPLE EXPERIENCE</small></span></div>
      <div className="auth-eyebrow"><ShieldCheck size={15}/> SECURE WORKSPACE · {workspace.toUpperCase()}</div>
      <h1>{title}</h1><p className="auth-description">{description}</p>
      {error && <div className="auth-error" role="alert">{error}</div>}
      {!configured && <div className="auth-config" role="status">Cognito settings are missing. Configure the public app-client ID, hosted UI domain, and allowed sign-in/sign-out URLs in this app's environment before signing in.</div>}
      <button className="auth-primary" onClick={onSignIn} disabled={!configured}>Continue with secure sign-in <ArrowRight size={17}/></button>
      <div className="auth-security"><LockKeyhole size={15}/><span>Your session uses Cognito OAuth authorization code with PKCE. API permissions are enforced by the backend.</span></div>
    </section>
  </main>;
}
