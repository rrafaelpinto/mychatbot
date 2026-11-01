import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { ApiError, api } from "./api/client";
import type { CandidateDetail, CandidateSummary, ChatMessage, PublicFact } from "./api/types";

type Session = "checking" | "guest" | "authenticated";
type Route = { page: "home" } | { page: "profile" | "agent"; slug: string };

function routeFromHash(hash: string): Route {
  const parts = hash.replace(/^#\/?/, "").split("/");
  const slug = parts[1];
  if ((parts[0] === "profile" || parts[0] === "agent") && slug && /^[a-z0-9-]+$/.test(slug)) {
    return { page: parts[0], slug };
  }
  return { page: "home" };
}

function profileLink(slug: string): string { return "#/profile/" + encodeURIComponent(slug); }
function agentLink(slug: string): string { return "#/agent/" + encodeURIComponent(slug); }

function Initials({ name, large = false }: { name: string; large?: boolean }) {
  const text = name.trim().split(/\s+/).slice(0, 2).map(word => word[0]?.toUpperCase()).join("");
  return <span className={"portrait " + (large ? "portrait-large" : "portrait-mini")} aria-hidden="true">{text}</span>;
}

function Notice({ kind, children }: { kind: "error" | "warning"; children: ReactNode }) {
  return <div role="status" className={"state-feedback state-" + kind}>{children}</div>;
}

function Home({ candidates }: { candidates: CandidateSummary[] }) {
  const first = candidates[0];
  return <section className="view" aria-labelledby="home-title">
    <div className="hero-grid">
      <div className="hero-copy">
        <div className="eyebrow"><span className="eyebrow-line" aria-hidden="true" /> Evidence-led professional profiles</div>
        <h1 id="home-title">Your experience.<br /><em>Nothing invented.</em></h1>
        <p className="hero-description">Explore published professional experience and ask a Candidate Agent questions grounded in facts the candidate chose to share.</p>
        <div className="hero-actions">
          <a className="button button-primary" href={first ? profileLink(first.slug) : "#profiles"}>Explore profiles</a>
          {first && <a className="button button-secondary" href={agentLink(first.slug)}>Meet the Candidate Agent</a>}
        </div>
        <div className="hero-caption">Candidate-approved facts only · Visible supporting evidence</div>
      </div>
      <div className="hero-art" aria-label="Illustration showing a verified professional profile">
        <div className="art-pattern" aria-hidden="true" />
        <div className="art-profile">
          <div className="art-profile-top"><span className="tiny-label">PROFILE / OVERVIEW</span><span className="mini-status">Published</span></div>
          <div className="art-person"><span className="portrait portrait-mini" aria-hidden="true">RB</span><div><strong>Professional profile</strong><span>Approved candidate information</span></div></div>
          <div className="art-divider" />
          <div className="art-tags"><span>Experience</span><span>Skills</span><span>Projects</span></div>
          <div className="art-profile-bottom"><span>Professional evidence</span><strong>Verified before sharing</strong></div>
        </div>
        <div className="art-answer"><div className="art-answer-title"><span className="answer-glyph" aria-hidden="true">✓</span><strong>Candidate Agent</strong></div><p>Answers are supported by facts the candidate has explicitly approved for publication.</p><div className="art-evidence">Inspect the evidence behind each answer</div></div>
      </div>
    </div>
    <div className="trust-strip" aria-label="Product principles">
      <div><span className="trust-number">01</span><strong>Candidate owned</strong><span>Control what is published</span></div>
      <div><span className="trust-number">02</span><strong>Evidence grounded</strong><span>Answers refer to approved facts</span></div>
      <div><span className="trust-number">03</span><strong>Privacy by default</strong><span>Private documents stay private</span></div>
    </div>
    <section id="profiles" aria-labelledby="profiles-title" className="section-block">
      <div className="section-heading"><div><div className="eyebrow">PUBLIC PROFILES</div><h2 id="profiles-title">Meet the candidates.</h2></div><p>Only published, approved profiles appear here.</p></div>
      {candidates.length ? <div className="feature-grid">{candidates.map(candidate =>
        <article className="feature-card" key={candidate.slug}>
          <div className="art-person"><Initials name={candidate.name} /><div><h3>{candidate.name}</h3><span>Public candidate</span></div></div>
          <p>{candidate.professional_summary}</p>
          <a className="button button-secondary" href={profileLink(candidate.slug)}>View profile</a>
        </article>)}</div> : <Notice kind="warning">No profiles are published yet. Private or pending profiles are never shown here.</Notice>}
    </section>
    <section className="bottom-banner"><div><span className="banner-label">A DIFFERENT KIND OF AI PROFILE</span><h2>Less hype. More signal.</h2><p>Understand the work and the evidence behind it.</p></div></section>
  </section>;
}

function PublicProfile({ slug }: { slug: string }) {
  const [profile, setProfile] = useState<CandidateDetail | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    setProfile(null);
    setError("");
    void api.candidate(slug).then(data => { if (active) setProfile(data); })
      .catch(() => { if (active) setError("This profile is unavailable or is not published."); });
    return () => { active = false; };
  }, [slug]);
  if (error) return <Notice kind="warning">{error} <a href="#/">Return to overview</a></Notice>;
  if (!profile) return <p role="status">Loading public profile…</p>;
  return <section className="view" aria-labelledby="profile-title">
    <div className="page-topline"><div className="breadcrumbs"><a href="#/">Overview</a><span>/</span> Public profile</div><span className="sample-label">PUBLISHED INFORMATION</span></div>
    <div className="profile-hero"><div className="profile-hero-main"><Initials name={profile.name} large /><div className="profile-heading"><div className="eyebrow">Published professional profile</div><h1 id="profile-title">{profile.name}<span className="name-period">.</span></h1><p>Professional experience and approved facts</p></div></div>
      <div className="profile-hero-cta"><span className="small-note">Curious about this experience?</span><a className="button button-primary" href={agentLink(slug)}>Ask Candidate Agent</a><span>Answers are subject to access and usage limits.</span></div></div>
    <div className="profile-layout"><div className="profile-content">
      <section className="profile-section"><div className="section-kicker">01 / ABOUT</div><h2>Professional overview</h2><p>{profile.professional_summary}</p></section>
      <section className="profile-section evidence-section"><div className="section-kicker">02 / VERIFIED EXPERIENCE</div><h2>Published facts</h2>
        {profile.facts.length ? profile.facts.map((fact, i) => <article key={fact.id} className="experience-item"><div className="experience-index">{String(i + 1).padStart(2, "0")}</div><div><h3>{fact.fact_type.replace(/_/g, " ")}</h3><p>{fact.content}</p><div className="fact-meta">Approved for publication</div></div></article>) : <p>No verified facts are currently published.</p>}
      </section>
    </div><aside className="profile-aside" aria-label="Contact and privacy">
      <div className="aside-card"><div className="aside-title">At a glance</div><div className="aside-stat"><span>Published facts</span><strong>{profile.facts.length}</strong></div>
        {profile.linkedin && <div className="aside-stat"><span>LinkedIn</span><a href={profile.linkedin} target="_blank" rel="noopener noreferrer">Professional profile</a></div>}
        {profile.contact_email && <div className="aside-stat"><span>Contact</span><a href={"mailto:" + profile.contact_email}>{profile.contact_email}</a></div>}
      </div>
      <div className="aside-trust"><h3>Candidate-controlled information.</h3><p>Only facts approved for public use appear on this page. Private documents and pending information are not disclosed.</p></div>
    </aside></div>
  </section>;
}

function MessageBubble({ message }: { message: ChatMessage }) {
  return <div className={"message message-" + (message.role === "user" ? "user" : "assistant")}><div className="message-body">
    <strong className="message-label">{message.role === "user" ? "You" : "Candidate Agent"}</strong><p>{message.content}</p>
    {message.evidence.length > 0 && <details className="evidence-details"><summary>{message.evidence.length} supporting fact(s)</summary><ul>{message.evidence.map((fact: PublicFact) => <li key={fact.id}>{fact.content}</li>)}</ul></details>}
  </div></div>;
}

function LoginForm({ onLogin }: { onLogin: () => void }) {
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
      setError(err instanceof ApiError && err.status === 401 ? "Invalid credentials." : "Sign-in unavailable.");
    } finally {
      setBusy(false);
      setPassword("");
    }
  }
  return <form onSubmit={submit} className="login-form">
    <h3>Sign in to the Candidate Agent</h3>
    <p>Authenticated chat uses the existing backend access rules and usage limits.</p>
    <label htmlFor="login-username">Username</label><input required id="login-username" autoComplete="username" value={username} onChange={e => setUsername(e.target.value)} />
    <label htmlFor="login-password">Password</label><input required type="password" id="login-password" autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)} />
    {error && <Notice kind="error">{error}</Notice>}
    <button className="button button-primary" disabled={busy} type="submit">{busy ? "Signing in…" : "Sign in"}</button>
  </form>;
}

function Agent({ slug, session, onLogin, onLogout }: { slug: string; session: Session; onLogin: () => void; onLogout: () => void }) {
  const [profile, setProfile] = useState<CandidateDetail | null>(null);
  const [history, setHistory] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    setProfile(null);
    void api.candidate(slug).then(data => { if (active) setProfile(data); }).catch(() => { if (active) setError("The candidate is not available."); });
    return () => { active = false; };
  }, [slug]);
  useEffect(() => {
    let active = true;
    setHistory([]);
    if (session !== "authenticated") return;
    void api.chatHistory(slug).then(data => { if (active) setHistory(data); })
      .catch(() => { if (active) setError("Conversation history is unavailable."); });
    return () => { active = false; };
  }, [slug, session]);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const question = input.trim();
    if (!question || busy || session !== "authenticated") return;
    setBusy(true);
    setError("");
    try {
      const answer = await api.ask(slug, question, crypto.randomUUID());
      setHistory(previous => [...previous, { role: "user", content: question, evidence: [] }, { role: "assistant", content: answer.response, evidence: answer.evidence }]);
      setInput("");
    } catch (err) {
      if (err instanceof ApiError && err.status === 429) setError("Question limit or budget reached. Further requests are not available.");
      else if (err instanceof ApiError && (err.status === 401 || err.status === 403)) setError("Your session is no longer authorized.");
      else if (err instanceof ApiError && err.status === 503) setError("Candidate Agent temporarily unavailable.");
      else setError("The request could not be completed. Check conversation history before retrying to avoid duplicate charges.");
    } finally {
      setBusy(false);
    }
  }
  if (error === "The candidate is not available.") return <Notice kind="warning">{error}</Notice>;
  if (!profile) return <p role="status">Loading candidate…</p>;
  return <section className="view" aria-labelledby="agent-title">
    <div className="page-topline"><div className="breadcrumbs"><a href="#/">Overview</a><span>/</span><a href={profileLink(slug)}>{profile.name}</a><span>/</span> Agent</div><span className="sample-label">LIVE API</span></div>
    <div className="agent-page-title"><div><div className="eyebrow">EVIDENCE-LED CONVERSATIONS</div><h1 id="agent-title">Ask better questions.<br /><em>Get grounded answers.</em></h1><p>Answers use only currently published, verified facts, subject to backend policies.</p></div><div className="agent-intro-person"><Initials name={profile.name} /><div><strong>{profile.name}</strong><span>Published profile</span></div></div></div>
    <div className="agent-layout"><section className="conversation" aria-label="Candidate conversation">
      <div className="conversation-top"><div className="conversation-icon">✓</div><div><strong>Candidate Agent</strong><span>{profile.name}'s approved facts</span></div><span className="demo-badge">LIMITED ACCESS</span></div>
      <div className="conversation-scroll" aria-live="polite" aria-relevant="additions text">
        {session === "checking" && <p>Checking your session…</p>}
        {session === "guest" && <div className="welcome-message"><div><strong>Sign in to ask a question</strong><p>This API currently supports authenticated conversations. Anonymous recruiter chat remains available on the existing Django demonstration.</p><a href={api.getBackendUrl("/chat/" + encodeURIComponent(slug) + "/")} rel="noopener noreferrer">Open limited guest demo</a></div></div>}
        {session === "authenticated" && <><div className="conversation-day">Your conversation</div>{history.length ? history.map((message, i) => <MessageBubble message={message} key={i} />) : <div className="welcome-message"><div><strong>What would you like to know?</strong><p>Ask about this candidate's published professional experience.</p></div></div>}</>}
        {error && <Notice kind="error">{error}</Notice>}
      </div>
      {session === "authenticated" ? <div className="composer-area">
        <div className="suggested-questions">{["What is this candidate's experience?", "Which technical skills are verified?", "What projects are documented?"].map(question => <button key={question} disabled={busy} onClick={() => setInput(question)} type="button">{question}</button>)}</div>
        <form className="composer" onSubmit={submit}><label className="sr-only" htmlFor="chat-input">Ask a professional question</label><input id="chat-input" maxLength={1000} required disabled={busy} value={input} onChange={e => setInput(e.target.value)} placeholder="Ask about professional experience…" /><button type="submit" disabled={busy || !input.trim()} aria-label="Send question">↑</button></form>
        <div className="composer-foot"><span>No guarantee of availability; backend quotas and budget apply.</span><button className="text-action" type="button" onClick={onLogout}>Sign out</button></div>
      </div> : session === "guest" ? <div className="composer-area"><LoginForm onLogin={onLogin} /></div> : null}
    </section>
      <aside className="agent-sidebar" aria-label="Conversation evidence"><div className="sidebar-card"><div className="sidebar-card-title"><strong>Evidence you can inspect</strong></div><p>Supported answers may disclose the approved professional facts behind them.</p><div className="sidebar-divider" /><div className="sidebar-fact">Candidate-approved facts only</div><div className="sidebar-fact">No private source documents</div><div className="sidebar-fact">Server-enforced cost and access limits</div></div><a className="sidebar-profile-link" href={profileLink(slug)}>View published profile</a></aside>
    </div>
  </section>;
}

export function App() {
  const [route, setRoute] = useState<Route>(() => routeFromHash(window.location.hash));
  const [candidates, setCandidates] = useState<CandidateSummary[]>([]);
  const [listError, setListError] = useState("");
  const [session, setSession] = useState<Session>("checking");
  const [dark, setDark] = useState(false);
  useEffect(() => {
    const updateRoute = () => setRoute(routeFromHash(window.location.hash));
    window.addEventListener("hashchange", updateRoute);
    void api.candidates().then(page => setCandidates(page.results)).catch(() => setListError("Public profiles are unavailable."));
    void api.restore().then(ok => setSession(ok ? "authenticated" : "guest")).catch(() => setSession("guest"));
    return () => window.removeEventListener("hashchange", updateRoute);
  }, []);
  useEffect(() => { document.documentElement.dataset.theme = dark ? "dark" : "light"; }, [dark]);
  const active = route.page;
  return <>
    <a className="skip-link" href="#main">Skip to content</a>
    <div className="preview-ribbon">ResumeBot · Verified professional information</div>
    <div className="site-shell"><header className="site-header"><a className="brand" href="#/" aria-label="ResumeBot homepage"><span className="brand-mark">✓</span>resumebot<span className="brand-period">.</span></a>
      <nav className="main-nav" aria-label="Main navigation"><a href="#/" aria-current={active === "home" ? "page" : undefined}>Overview</a><a href={candidates[0] ? profileLink(candidates[0].slug) : "#profiles"} aria-current={active === "profile" ? "page" : undefined}>Public profile</a><a href={candidates[0] ? agentLink(candidates[0].slug) : "#profiles"} aria-current={active === "agent" ? "page" : undefined}>Candidate Agent</a></nav>
      <div className="header-actions"><button type="button" id="theme-toggle" className="icon-button" aria-label={dark ? "Switch to light theme" : "Switch to dark theme"} aria-pressed={dark} onClick={() => setDark(!dark)}>{dark ? "☀" : "☾"}</button></div>
    </header><main id="main">
      {listError && active === "home" && <Notice kind="error">{listError}</Notice>}
      {route.page === "home" && <Home candidates={candidates} />}
      {route.page === "profile" && <PublicProfile slug={route.slug} />}
      {route.page === "agent" && <Agent slug={route.slug} session={session} onLogin={() => setSession("authenticated")} onLogout={() => { setSession("guest"); void api.logout().catch(() => undefined); }} />}
    </main><footer className="site-footer"><div className="footer-logo">resumebot<span>.</span></div><p>Professional stories, grounded in approved information.</p><span>Independent React frontend</span></footer></div>
  </>;
}
