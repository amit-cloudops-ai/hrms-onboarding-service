import {useEffect,useState} from "react";
import {useMock} from "../api";
import {bootstrapAuth,beginLogin,logout} from "../auth";
export default function AuthGate({children}){
 const [state,setState]=useState(useMock?"authenticated":"checking");
 const [error,setError]=useState("");
 useEffect(()=>{if(useMock)return undefined;let active=true;bootstrapAuth().then(token=>{if(active)setState(token?"authenticated":"anonymous");}).catch(err=>{if(active){setError(err.message||"Sign-in could not be completed.");setState("anonymous");}});return()=>{active=false;};},[]);
 if(useMock)return children;
 if(state==="checking")return <main className="auth-screen"><p>Checking secure session…</p></main>;
 if(state!=="authenticated")return <main className="auth-screen"><section className="auth-card"><p className="auth-kicker">HRMS · HR DASHBOARD</p><h1>Sign in.</h1><p>Use an authorised HR account to manage onboarding.</p>{error&&<p role="alert" className="auth-error">{error}</p>}<button className="btn btn-primary" onClick={()=>beginLogin().catch(err=>setError(err.message))}>Sign in securely</button></section></main>;
 return <><button className="auth-signout" onClick={()=>logout()}>Sign out</button>{children}</>;
}
