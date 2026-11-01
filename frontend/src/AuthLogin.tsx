import { useState, type FormEvent } from "react";
import { ApiError, api } from "./api/client";

export function AuthLogin({ onLogin, heading = "Sign in to the Candidate Agent" }: {
  onLogin: () => void;
  heading?: string;
}) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api.login(username, password);
      onLogin();
    } catch (err) {
      setError(err instanceof ApiError && err.status === 401
        ? "Invalid credentials." : "Sign-in unavailable.");
    } finally {
      setBusy(false);
      setPassword("");
    }
  }

  return <form onSubmit={submit} className="login-form">
    <h2>{heading}</h2>
    <p>Authentication is managed by the Django API. Access is subject to account permissions.</p>
    <label htmlFor="login-username">Username</label>
    <input required id="login-username" autoComplete="username" value={username}
      onChange={event => setUsername(event.target.value)} />
    <label htmlFor="login-password">Password</label>
    <input required id="login-password" type="password" autoComplete="current-password"
      value={password} onChange={event => setPassword(event.target.value)} />
    {error && <p role="alert" className="owner-error">{error}</p>}
    <button className="button button-primary" disabled={busy} type="submit">
      {busy ? "Signing in…" : "Sign in"}
    </button>
  </form>;
}
