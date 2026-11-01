import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { OwnerDashboard } from "./OwnerDashboard";
import { GuestChatPanel } from "./GuestChatPanel";
import { MessageBubble } from "./MessageBubble";
import { ApiError, api } from "./api/client";
import type { CandidateDetail, CandidateSummary, ChatMessage } from "./api/types";

type Session = "checking" | "guest" | "authenticated";
type Route = { page: "home" | "owner" } | { page: "profile" | "agent"; slug: string };

function routeFromHash(hash: string): Route {
  const parts = hash.replace(/^#\/?/, "").split("/");
  const slug = parts[1];
  if ((parts[0] === "profile" || parts[0] === "agent") && slug && /^[a-z0-9-]+$/.test(slug)) {
    return { page: parts[0], slug };
  }
  if (parts[0] === "owner") return { page: "owner" };
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
  const featured = candidates[0];
  return <section className="view portfolio-home" aria-labelledby="home-title">
    <div className="portfolio-hero">
      <div className="portfolio-intro">
        <div className="eyebrow"><span className="eyebrow-line" aria-hidden="true" /> An interactive engineering portfolio</div>
        <h1 id="home-title">Get to know the <em>engineer behind the code.</em></h1>
        <p className="hero-description">Explore practical software engineering experience, or ask a Candidate Agent directly about the work, technical decisions, and projects.</p>
        <div className="hero-actions">
          {featured && <a className="button button-primary" href={agentLink(featured.slug)}>Ask about my experience <span aria-hidden="true">↗</span></a>}
          <a className="button button-secondary" href={featured ? profileLink(featured.slug) : "#profiles"}>View professional profile</a>
        </div>
        <p className="hero-caption">Answers are grounded in published professional information.</p>
      </div>
      {featured && <aside className="featured-profile" aria-label="Featured professional profile">
        <div className="featured-topline"><span className="section-kicker">FEATURED PROFILE</span><span className="featured-availability">Published experience</span></div>
        <div className="featured-person"><Initials name={featured.name} /><div><span>Senior Software Engineer</span><h2>{featured.name}</h2></div></div>
        <p className="featured-summary">{featured.professional_summary}</p>
        <div className="featured-bottom"><span>Explore verified skills and experience</span><a href={profileLink(featured.slug)} aria-label={`View ${featured.name}'s professional profile`}>View profile <span aria-hidden="true">↗</span></a></div>
      </aside>}
    </div>
    <div className="portfolio-paths" aria-label="Ways to explore">
      <div className="path-heading"><span className="section-kicker">EXPLORE THE WORK</span><h2>Start with what matters to you.</h2></div>
      <div className="path-grid">
        <a href={featured ? agentLink(featured.slug) : "#profiles"} className="path-card"><span className="path-icon" aria-hidden="true">01</span><strong>Ask the Candidate Agent</strong><span>Ask about backend architecture, APIs, data modeling, and applied AI.</span><span className="path-link">Start a conversation ↗</span></a>
        <a href={featured ? profileLink(featured.slug) : "#profiles"} className="path-card"><span className="path-icon" aria-hidden="true">02</span><strong>Review professional experience</strong><span>Explore the experience and skills approved for publication.</span><span className="path-link">Explore the profile ↗</span></a>
      </div>
    </div>
    <section id="profiles" aria-labelledby="profiles-title" className="section-block portfolio-directory">
      <div className="section-heading"><div><div className="eyebrow">PUBLIC PROFILE DIRECTORY</div><h2 id="profiles-title">Published profiles</h2></div></div>
      {candidates.length ? <div className="feature-grid">{candidates.map(candidate =>
        <article className="feature-card" key={candidate.slug}>
          <div className="art-person"><Initials name={candidate.name} /><div><h3>{candidate.name}</h3><span>Professional profile</span></div></div>
          <p>{candidate.professional_summary}</p>
          <a className="button button-secondary" href={profileLink(candidate.slug)}>Read profile</a>
        </article>)}</div> : <Notice kind="warning">No professional profiles are currently published.</Notice>}
    </section>
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
    <div className="page-topline"><div className="breadcrumbs"><a href="#/">Overview</a><span>/</span><a href={profileLink(slug)}>{profile.name}</a><span>/</span> Agent</div><span className="sample-label">PUBLIC CONVERSATION</span></div>
    <div className="agent-page-title"><div><div className="eyebrow">CANDIDATE AGENT</div><h1 id="agent-title">Ask about <em>{profile.name}.</em></h1><p>Ask about engineering decisions, backend development, and applied AI. Responses are written from the candidate’s perspective using published experience.</p></div><div className="agent-intro-person"><Initials name={profile.name} /><div><strong>{profile.name}</strong><span>Published profile</span></div></div></div>
    <div className="agent-layout"><section className="conversation" aria-label="Candidate conversation">
      <div className="conversation-top"><div className="conversation-icon">✓</div><div><strong>Candidate Agent</strong><span>{profile.name}'s approved facts</span></div><span className="demo-badge">FACT-BASED ANSWERS</span></div>
      {session === "guest" ? <GuestChatPanel slug={slug} onLogin={onLogin} /> : <>
      <div className="conversation-scroll" aria-live="polite" aria-relevant="additions text">
        {session === "checking" && <p>Checking your session…</p>}

        {session === "authenticated" && <><div className="conversation-day">Your conversation</div>{history.length ? history.map((message, i) => <MessageBubble message={message} key={i} />) : <div className="welcome-message"><div><strong>What would you like to know?</strong><p>Ask about this candidate's published professional experience.</p></div></div>}</>}
        {error && <Notice kind="error">{error}</Notice>}
      </div>
      {session === "authenticated" ? <div className="composer-area">
        <div className="suggested-questions">{["What is this candidate's experience?", "Which technical skills are verified?", "What projects are documented?"].map(question => <button key={question} disabled={busy} onClick={() => setInput(question)} type="button">{question}</button>)}</div>
        <form className="composer" onSubmit={submit}><label className="sr-only" htmlFor="chat-input">Ask a professional question</label><input id="chat-input" maxLength={1000} required disabled={busy} value={input} onChange={e => setInput(e.target.value)} placeholder="Ask about professional experience…" /><button type="submit" disabled={busy || !input.trim()} aria-label="Send question">↑</button></form>
        <div className="composer-foot"><span>No guarantee of availability; backend quotas and budget apply.</span><button className="text-action" type="button" onClick={onLogout}>Sign out</button></div>
      </div> : null}
      </>}
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
    
    <div className="site-shell"><header className="site-header"><a className="brand" href="#/" aria-label="ResumeBot homepage"><span className="brand-mark">✓</span>resumebot<span className="brand-period">.</span></a>
      <nav className="main-nav" aria-label="Main navigation"><a href="#/" aria-current={active === "home" ? "page" : undefined}>Home</a><a href={candidates[0] ? profileLink(candidates[0].slug) : "#profiles"} aria-current={active === "profile" ? "page" : undefined}>Public profile</a><a href={candidates[0] ? agentLink(candidates[0].slug) : "#profiles"} aria-current={active === "agent" ? "page" : undefined}>Candidate Agent</a></nav>
      {session === "authenticated" && <a className="header-cta" href="#/owner">My workspace</a>}<div className="header-actions"><button type="button" id="theme-toggle" className="icon-button" aria-label={dark ? "Switch to light theme" : "Switch to dark theme"} aria-pressed={dark} onClick={() => setDark(!dark)}>{dark ? "☀" : "☾"}</button></div>
    </header><main id="main">
      {listError && active === "home" && <Notice kind="error">{listError}</Notice>}
      {route.page === "home" && <Home candidates={candidates} />}
      {route.page === "profile" && <PublicProfile slug={route.slug} />}
      {route.page === "owner" && <OwnerDashboard session={session} onLogin={() => setSession("authenticated")} onLogout={() => { setSession("guest"); void api.logout().catch(() => undefined); }} />}
      {route.page === "agent" && <Agent slug={route.slug} session={session} onLogin={() => setSession("authenticated")} onLogout={() => { setSession("guest"); void api.logout().catch(() => undefined); }} />}
    </main><footer className="site-footer"><div className="footer-logo">resumebot<span>.</span></div><p>Professional stories, grounded in approved information.</p><span>Built with Django and React</span></footer></div>
  </>;
}
