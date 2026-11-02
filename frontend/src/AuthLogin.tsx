import { useEffect, useState, type FormEvent } from "react";
import { ApiError, api } from "./api/client";

export function AuthLogin({ onLogin, heading = "Sign in to ResumeBot", registration = false }: {
  onLogin: () => void;
  heading?: string;
  registration?: boolean;
}) {
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [role, setRole] = useState<"candidate" | "recruiter">("candidate");
  const [code, setCode] = useState("");
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [cooldown, setCooldown] = useState(0);
  const [error, setError] = useState("");
  useEffect(() => {
    if (!cooldown) return;
    const timer = window.setTimeout(() => setCooldown(cooldown - 1), 1000);
    return () => window.clearTimeout(timer);
  }, [cooldown]);

  async function sendCode() {
    setBusy(true); setError("");
    try {
      await api.requestCode(email, registration ? { name, role } : undefined);
      setSent(true); setCooldown(60);
    } catch (err) {
      setError(err instanceof ApiError && err.status === 429 ? "Too many requests. Try again later." : "Unable to send a code. Please try again.");
    } finally { setBusy(false); }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    if (!sent) { await sendCode(); return; }
    setBusy(true); setError("");
    try { await api.verifyCode(email, code); onLogin(); }
    catch (err) { setError(err instanceof ApiError && err.status === 401 ? "Invalid or expired code. Check the code or request a new one." : "Unable to sign in. Please try again later."); }
    finally { setBusy(false); setCode(""); }
  }

  return <form onSubmit={submit} className="login-form auth-card">
    <div className="eyebrow">{registration ? "CREATE AN ACCOUNT" : "EMAIL SIGN-IN"}</div>
    <h1>{registration ? "Start with your professional story." : heading}</h1>
    <p>{sent ? `If your email is eligible, a six-digit code has been sent to ${email}. It expires in 10 minutes.` : "Use your email to receive a one-time sign-in code. No password needed."}</p>
    {!sent ? <>
      {registration && <><label htmlFor="signup-name">Full name</label><input id="signup-name" required maxLength={255} autoComplete="name" value={name} onChange={e => setName(e.target.value)} />
      <label htmlFor="signup-role">I am joining as a</label><select id="signup-role" value={role} onChange={e => setRole(e.target.value as typeof role)}><option value="candidate">Candidate</option><option value="recruiter">Recruiter</option></select>
      <p className="owner-note">{role === "candidate" ? "After email verification, an administrator must approve your account before you can use the workspace." : "Verify your email to explore profiles and ask the Candidate Agents questions."}</p></>}
      <label htmlFor="login-email">Email</label><input required id="login-email" type="email" autoComplete="email" maxLength={254} value={email} onChange={e => setEmail(e.target.value)} />
    </> : <><label htmlFor="login-code">Verification code</label><input autoFocus required id="login-code" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" minLength={6} maxLength={6} value={code} onChange={e => setCode(e.target.value.replace(/[^0-9]/g, ""))} /></>}
    {error && <p role="alert" className="owner-error">{error}</p>}
    <button className="button button-primary" disabled={busy} type="submit">{busy ? "Please wait…" : sent ? "Verify and continue" : "Send sign-in code"}</button>
    {sent && <><button type="button" disabled={busy || cooldown > 0} onClick={() => void sendCode()}>{cooldown ? `Resend code in ${cooldown}s` : "Resend code"}</button><button type="button" disabled={busy} onClick={() => { setSent(false); setError(""); setCode(""); }}>Use another email</button></>}
    <p>{registration ? "Already registered? " : "New to ResumeBot? "}<a href={registration ? "#/login" : "#/register"}>{registration ? "Sign in" : "Create an account"}</a></p>
  </form>;
}
