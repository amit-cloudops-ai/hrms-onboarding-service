import { useMemo, useState } from "react";
import type { FormEvent } from "react";
import { ArrowLeft, ArrowRight, Fingerprint, KeyRound, LockKeyhole, Mail, ShieldCheck, Sparkles } from "lucide-react";
import { completeSignIn, finishPasswordReset, isAuthConfigured, signIn, signOut, startPasswordReset } from "./auth";

type Props = { workspace: string; title: string; description: string; error?: string; onAuthenticated: () => void };
type Mode = "signin" | "challenge" | "forgot" | "reset";
const challengeCopy: Record<string, { title: string; description: string; placeholder: string; type?: string }> = {
  CONFIRM_SIGN_IN_WITH_NEW_PASSWORD_REQUIRED: { title: "Create your password", description: "Your account was created with a temporary password. Choose a new password to continue.", placeholder: "New password", type: "password" },
  CONFIRM_SIGN_IN_WITH_TOTP_CODE: { title: "Verify it’s you", description: "Enter the six-digit code from your authenticator app.", placeholder: "6-digit authenticator code" },
  CONFIRM_SIGN_IN_WITH_SMS_CODE: { title: "Check your phone", description: "Enter the verification code sent to your registered phone.", placeholder: "SMS verification code" },
  CONFIRM_SIGN_IN_WITH_EMAIL_CODE: { title: "Check your email", description: "Enter the verification code sent to your registered email.", placeholder: "Email verification code" },
  CONTINUE_SIGN_IN_WITH_TOTP_SETUP: { title: "Set up your authenticator", description: "Add your account to an authenticator app, then enter the code it generates.", placeholder: "6-digit authenticator code" },
  CONTINUE_SIGN_IN_WITH_EMAIL_SETUP: { title: "Verify your email", description: "Enter the email address you want to use for verification.", placeholder: "Work email", type: "email" },
  CONFIRM_SIGN_IN_WITH_PASSWORD: { title: "Confirm your password", description: "Enter your password to complete this sign-in step.", placeholder: "Password", type: "password" },
  CONFIRM_SIGN_IN_WITH_CUSTOM_CHALLENGE: { title: "Additional verification", description: "Complete the additional verification step to continue.", placeholder: "Verification response" },
};
export function AuthGate({ workspace, title, description, error: externalError, onAuthenticated }: Props) {
  const [mode,setMode]=useState<Mode>("signin");
  const [email,setEmail]=useState("");
  const [password,setPassword]=useState("");
  const [answer,setAnswer]=useState("");
  const [code,setCode]=useState("");
  const [newPassword,setNewPassword]=useState("");
  const [challenge,setChallenge]=useState("");
  const [mfaChoice,setMfaChoice]=useState("TOTP");
  const [setupUri,setSetupUri]=useState("");
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");
  const [notice,setNotice]=useState("");
  const [configured]=useState(isAuthConfigured());
  const challengeDetails=useMemo(()=>challengeCopy[challenge]||{title:"Verify your account",description:"Complete the verification step requested by your organisation.",placeholder:"Verification code"},[challenge]);
  async function applyStep(step:string, details?:any) {
    setChallenge(step);
    if(step==="DONE"){onAuthenticated();return;}
    if(step==="RESET_PASSWORD"){
      await startPasswordReset(email);
      setMode("reset");
      setNotice("A password reset code has been sent to your registered email address.");
      return;
    }
    if(step==="CONTINUE_SIGN_IN_WITH_TOTP_SETUP" && details?.totpSetupDetails?.getSetupUri){
      setSetupUri(details.totpSetupDetails.getSetupUri("Northstar"));
    }
    if(step==="CONTINUE_SIGN_IN_WITH_MFA_SELECTION" || step==="CONTINUE_SIGN_IN_WITH_MFA_SETUP_SELECTION"){
      setMfaChoice("TOTP");
    }
    setMode("challenge");
  }
  async function submitSignIn(event:FormEvent<HTMLFormElement>){
    event.preventDefault();setError("");setNotice("");setBusy(true);
    try{const result=await signIn(email,password);await applyStep(result.nextStep.signInStep,result.nextStep);}
    catch(e){setError(e instanceof Error?e.message:"Sign-in failed. Check your details and try again.");}
    finally{setBusy(false);}
  }
  async function submitChallenge(event:FormEvent<HTMLFormElement>){
    event.preventDefault();setError("");setNotice("");setBusy(true);
    try{
      const formData = new FormData(event.currentTarget);
      const enteredValue = String(formData.get("challengeResponse") ?? "");
      const response = challenge==="CONTINUE_SIGN_IN_WITH_MFA_SELECTION"||challenge==="CONTINUE_SIGN_IN_WITH_MFA_SETUP_SELECTION"
        ? mfaChoice
        : challenge==="CONFIRM_SIGN_IN_WITH_NEW_PASSWORD_REQUIRED"
          ? (enteredValue || newPassword)
          : (enteredValue || answer);
      if (!response) {
        setError(challenge==="CONFIRM_SIGN_IN_WITH_NEW_PASSWORD_REQUIRED" ? "Enter a new password to continue." : "Enter the requested verification response.");
        return;
      }
      const result=await completeSignIn(response);await applyStep(result.nextStep.signInStep,result.nextStep);
    }catch(e){setError(e instanceof Error?e.message:"Verification failed. Check the code and try again.");}
    finally{setBusy(false);}
  }
  async function submitReset(event:FormEvent<HTMLFormElement>){
    event.preventDefault();setError("");setNotice("");setBusy(true);
    try{await finishPasswordReset(email,code,newPassword);setMode("signin");setPassword("");setCode("");setNewPassword("");setNotice("Password updated. Sign in with your new password.");}
    catch(e){setError(e instanceof Error?e.message:"Password reset failed. Check the code and try again.");}
    finally{setBusy(false);}
  }
  async function resendReset(){setError("");setNotice("");setBusy(true);try{await startPasswordReset(email);setNotice("A new reset code has been sent.");}catch(e){setError(e instanceof Error?e.message:"Could not send a reset code.");}finally{setBusy(false);}}
  const isMfaChoice=challenge==="CONTINUE_SIGN_IN_WITH_MFA_SELECTION"||challenge==="CONTINUE_SIGN_IN_WITH_MFA_SETUP_SELECTION";
  return <main className="auth-page"><section className="auth-card">
    <div className="auth-brand"><span className="auth-mark"><Fingerprint size={23}/></span><span><b>northstar</b><small>PEOPLE EXPERIENCE</small></span></div>
    <div className="auth-eyebrow"><ShieldCheck size={15}/> SECURE WORKSPACE · {workspace.toUpperCase()}</div>
    <div className="auth-intro"><span className="auth-orbit"><Sparkles size={16}/></span><h1>{mode==="signin"?title:mode==="forgot"?"Reset your password":mode==="reset"?"Check your inbox":challengeDetails.title}</h1>
    <p className="auth-description">{mode==="signin"?description:mode==="forgot"?"We’ll send a secure reset code to the email associated with your account.":mode==="reset"?"Enter the code from your email and choose a new password.":challengeDetails.description}</p></div>
    {(error||externalError)&&<div className="auth-error" role="alert">{error||externalError}</div>}
    {notice&&<div className="auth-notice" role="status">{notice}</div>}
    {!configured&&<div className="auth-config" role="status">Cognito settings are missing. Add the user pool ID and public app-client ID to this app’s environment.</div>}
    {mode==="signin"&&<form className="auth-form" onSubmit={submitSignIn}>
      <label htmlFor="northstar-email">Work email</label><div className="auth-input-wrap"><Mail size={17}/><input id="northstar-email" type="email" autoComplete="username" value={email} onChange={e=>setEmail(e.target.value)} placeholder="you@company.com" required/></div>
      <div className="auth-label-row"><label htmlFor="northstar-password">Password</label><button type="button" className="auth-text-button" onClick={()=>{setMode("forgot");setError("");setNotice("");}}>Forgot password?</button></div>
      <div className="auth-input-wrap"><KeyRound size={17}/><input id="northstar-password" type="password" autoComplete="current-password" value={password} onChange={e=>setPassword(e.target.value)} placeholder="Enter your password" required/></div>
      <button className="auth-primary" disabled={!configured||busy}>{busy?"Signing in…":<>Sign in securely <ArrowRight size={17}/></>}</button>
    </form>}
    {mode==="forgot"&&<form className="auth-form" onSubmit={async e=>{e.preventDefault();setBusy(true);setError("");try{await startPasswordReset(email);setMode("reset");setNotice("A password reset code has been sent to your registered email address.");}catch(err){setError(err instanceof Error?err.message:"Could not start password reset.");}finally{setBusy(false);}}}>
      <label htmlFor="reset-email">Work email</label><div className="auth-input-wrap"><Mail size={17}/><input id="reset-email" type="email" autoComplete="username" value={email} onChange={e=>setEmail(e.target.value)} placeholder="you@company.com" required/></div>
      <button className="auth-primary" disabled={!configured||busy}>{busy?"Sending code…":<>Send reset code <ArrowRight size={17}/></>}</button>
      <button type="button" className="auth-back" onClick={()=>{setMode("signin");setError("");setNotice("");}}><ArrowLeft size={14}/> Back to sign in</button>
    </form>}
    {mode==="reset"&&<form className="auth-form" onSubmit={submitReset}>
      <label htmlFor="reset-code">Email verification code</label><div className="auth-input-wrap"><Mail size={17}/><input id="reset-code" inputMode="numeric" autoComplete="one-time-code" value={code} onChange={e=>setCode(e.target.value)} placeholder="Enter your code" required/></div>
      <label htmlFor="new-password">New password</label><div className="auth-input-wrap"><KeyRound size={17}/><input id="new-password" type="password" autoComplete="new-password" value={newPassword} onChange={e=>setNewPassword(e.target.value)} placeholder="At least 12 characters" minLength={12} required/></div>
      <button className="auth-primary" disabled={busy}>{busy?"Updating…":<>Update password <ArrowRight size={17}/></>}</button>
      <button type="button" className="auth-back" onClick={resendReset} disabled={busy}>Resend code</button>
    </form>}
    {mode==="challenge"&&<form className="auth-form" onSubmit={submitChallenge}>
      {isMfaChoice?<><label>Choose a verification method</label><div className="auth-choice-list">{["TOTP","SMS","EMAIL"].map(value=><label className="auth-choice" key={value}><input type="radio" name="mfa-choice" value={value} checked={mfaChoice===value} onChange={()=>setMfaChoice(value)}/><span>{value==="TOTP"?"Authenticator app":value==="SMS"?"Text message":"Email code"}</span></label>)}</div></>:<>
        {challenge==="CONTINUE_SIGN_IN_WITH_TOTP_SETUP"&&setupUri&&<div className="auth-setup-note"><b>Authenticator setup link</b><a href={setupUri}>Open in authenticator app</a><small>If your app cannot open the link, contact your administrator for the manual setup key.</small></div>}
        <label htmlFor="challenge-answer">{challengeDetails.placeholder}</label><div className="auth-input-wrap"><KeyRound size={17}/><input id="challenge-answer" type={challengeDetails.type||"text"} autoComplete={challengeDetails.type==="password"?"new-password":"one-time-code"} name="challengeResponse" value={challenge==="CONFIRM_SIGN_IN_WITH_NEW_PASSWORD_REQUIRED"?newPassword:answer} onChange={e=>challenge==="CONFIRM_SIGN_IN_WITH_NEW_PASSWORD_REQUIRED"?setNewPassword(e.target.value):setAnswer(e.target.value)} placeholder={challengeDetails.placeholder} required/></div>
      </>}
      <button className="auth-primary" disabled={busy}>{busy?"Verifying…":<>Continue securely <ArrowRight size={17}/></>}</button>
      <button type="button" className="auth-back" onClick={()=>{setMode("signin");setChallenge("");setError("");setNotice("");}}>Cancel and return to sign in</button>
    </form>}
    <button type="button" className="auth-back" onClick={()=>void signOut()}>Clear saved sign-in on this browser</button>
    <div className="auth-security"><LockKeyhole size={15}/><span>Protected by Amazon Cognito Secure Remote Password authentication. API permissions are independently enforced by the backend.</span></div>
    <div className="auth-footnote">NORTHSTAR <span>·</span> {workspace.toUpperCase()}</div>
  </section></main>;
}
