import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { AuthLogin } from "./AuthLogin";
import { GuestTurnstile } from "./GuestTurnstile";
import { MessageBubble } from "./MessageBubble";
import { ApiError, api } from "./api/client";
import type { ChatMessage, GuestStatus } from "./api/types";

export function GuestChatPanel({ slug, onLogin }: { slug: string; onLogin: () => void }) {
  const [status, setStatus] = useState<GuestStatus | null>(null);
  const [history, setHistory] = useState<ChatMessage[]>([]);
  const [question, setQuestion] = useState("");
  const [token, setToken] = useState("");
  const [resetKey, setResetKey] = useState(0);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const pending = useRef<{ question: string; key: string } | null>(null);
  const clearToken = useCallback((value: string) => setToken(value), []);
  const captchaError = useCallback((value: string) => setError(value), []);

  useEffect(() => {
    let active = true;
    setStatus(null);
    setHistory([]);
    setError("");
    setLoading(true);
    setToken("");
    pending.current = null;
    void api.guestStatus(slug).then(result => {
      if (!active) return;
      setStatus(result);
      setHistory(result.history);
    }).catch(() => { if (active) setError("Guest conversation unavailable."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [slug]);

  async function reload() {
    setError("");
    try {
      const updated = await api.guestStatus(slug);
      setStatus(updated);
      setHistory(updated.history);
    } catch { setError("Could not refresh the conversation."); }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = question.trim();
    if (!text || busy || !status?.enabled || status.remaining === 0 ||
        (!status.guest_verified && !token)) return;
    const key = pending.current?.question === text ? pending.current.key : crypto.randomUUID();
    pending.current = { question: text, key };
    setBusy(true);
    setError("");
    try {
      const result = await api.guestAsk(slug, text, status.guest_verified ? "" : token, key);
      setHistory(previous => [...previous,
        { role: "user", content: text, evidence: [] },
        { role: "assistant", content: result.response, evidence: result.evidence },
      ]);
      setStatus(previous => previous && ({
        ...previous,
        guest_verified: true,
        turnstile_site_key: "",
        remaining: result.remaining,
      }));
      setQuestion("");
      setToken("");
      pending.current = null;
    } catch (err) {
      if (err instanceof ApiError && err.status === 429) setError("Guest question limit reached. No further requests are available.");
      else if (err instanceof ApiError && err.status === 403) setError("Bot verification or session was rejected. Refresh the challenge to try again.");
      else if (err instanceof ApiError && err.status === 503) setError("Guest chat or bot verification is temporarily unavailable.");
      else setError("Request not confirmed. Reload the conversation before retrying to avoid duplicate usage.");
      if (!status.guest_verified) {
        setToken("");
        setResetKey(current => current + 1);
      }
      if (err instanceof ApiError && (err.status === 409 || err.status === 429)) await reload();
    } finally { setBusy(false); }
  }

  return <>
    <div className="conversation-scroll" aria-live="polite" aria-relevant="additions text">
      {loading && <p role="status">Checking guest access…</p>}
      {!loading && !status?.enabled && <div className="welcome-message"><div>
        <strong>Guest conversation is unavailable</strong>
        <p>Guest access may be disabled. Sign in for authenticated chat or try again later.</p>
      </div></div>}
      {status?.enabled && <>
        {history.length ? history.map((message, index) =>
          <MessageBubble key={index} message={message} />)
          : <div className="welcome-message"><div><strong>Ask about verified experience</strong>
            <p>Guest questions are limited, and answers only use approved public facts.</p>
          </div></div>}
      </>}
      {error && <p role="alert" className="guest-error">{error}</p>}
    </div>
    <div className="composer-area">
      {status?.enabled && <>
        <p className="guest-counter" role="status">
          {status.guest_verified ? String(status.remaining ?? 0) + " guest questions remaining" : "Verify once to begin a limited guest session."}
        </p>
        <div className="guest-prompts" aria-label="Suggested questions">
          {["How do you use Django and DRF?", "What is your PostgreSQL experience?", "How do you use AI in development?"].map(suggestion =>
            <button type="button" key={suggestion} disabled={busy || status.remaining === 0}
              onClick={() => { setQuestion(suggestion); document.getElementById("guest-question")?.focus(); }}>{suggestion}</button>)}
        </div>
        <form className="guest-composer" onSubmit={submit}>
          <label htmlFor="guest-question">Professional question</label>
          <input id="guest-question" required maxLength={1000} value={question} disabled={busy || status.remaining === 0}
            onChange={event => setQuestion(event.target.value)} placeholder="Ask about professional experience…" />
          {!status.guest_verified && status.turnstile_site_key &&
            <GuestTurnstile key={slug + "-" + resetKey} siteKey={status.turnstile_site_key}
              onToken={clearToken} onError={captchaError} />}
          <button className="button button-primary" type="submit"
            disabled={busy || !question.trim() || status.remaining === 0 || (!status.guest_verified && !token)}>
            {busy ? "Sending…" : "Send guest question"}
          </button>
        </form>
      </>}
      <div className="guest-footer">
        <p>Do not share sensitive personal information. Guest conversations and usage are limited by the backend.</p>
        <button type="button" onClick={() => void reload()} disabled={busy}>Reload conversation</button>

      </div>
      <details className="guest-signin"><summary>Sign in to use your account</summary>
        <AuthLogin onLogin={onLogin} />
      </details>
    </div>
  </>;
}
