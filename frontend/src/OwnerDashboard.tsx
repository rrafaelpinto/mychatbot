import { useEffect, useState, type FormEvent } from "react";
import { DocumentsPanel } from "./DocumentsPanel";
import { AuthLogin } from "./AuthLogin";
import { ApiError, api } from "./api/client";
import type { Account, OwnerFact, OwnerProfile, OwnerProfileUpdate, ReviewAction } from "./api/types";

type Session = "checking" | "guest" | "authenticated";
type EditableField = "name" | "professional_summary" | "linkedin" | "contact_email" | "phone";
const editableFields: EditableField[] = ["name", "professional_summary", "linkedin", "contact_email", "phone"];

function FactActions({ fact, busy, onReview }: {
  fact: OwnerFact;
  busy: boolean;
  onReview: (fact: OwnerFact, action: ReviewAction) => void;
}) {
  const options: { action: ReviewAction; label: string }[] = [];
  if (fact.verification_status === "pending") options.push({ action: "approve", label: "Approve" }, { action: "reject", label: "Reject" });
  if (fact.verification_status === "verified") {
    if (fact.is_public) options.push({ action: "unpublish", label: "Withdraw" });
    else options.push({ action: "publish", label: "Publish" }, { action: "reject", label: "Reject" });
  }
  if (fact.verification_status === "rejected") options.push({ action: "reopen", label: "Reopen" });
  return <div className="owner-actions">{options.map(({ action, label }) =>
    <button key={action} type="button" disabled={busy} onClick={() => onReview(fact, action)}>{label}</button>)}</div>;
}

function OwnerWorkspace({ onLogout, account }: { onLogout: () => void; account: Account }) {
  const [refresh, setRefresh] = useState(0);
  const [profile, setProfile] = useState<OwnerProfile | null>(null);
  const [draft, setDraft] = useState<OwnerProfileUpdate | null>(null);
  const [facts, setFacts] = useState<OwnerFact[]>([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [hasNext, setHasNext] = useState(false);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [reviewing, setReviewing] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    let active = true;
    setProfile(null);
    setDraft(null);
    setFacts([]);
    setError("");
    setMessage("");
    setPage(1);
    setLoading(true);
    void Promise.all([api.ownerProfile(), api.ownerFacts(1)]).then(([owned, results]) => {
      if (!active) return;
      setProfile(owned);
      setDraft({
        name: owned.name, professional_summary: owned.professional_summary,
        linkedin: owned.linkedin, contact_email: owned.contact_email,
        show_linkedin: owned.show_linkedin, show_contact_email: owned.show_contact_email, phone: owned.phone,
      });
      setFacts(results.results);
      setTotal(results.count);
      setHasNext(Boolean(results.next));
    }).catch(err => {
      if (active && err instanceof ApiError && err.status === 404 && account.is_superuser) {
        setDraft({ name: "", professional_summary: "", linkedin: "", contact_email: "", show_linkedin: false, show_contact_email: false, phone: "" });
        return;
      }
      if (active) setError(err instanceof ApiError && err.status === 404
        ? "No candidate profile belongs to this account." : "Unable to load your private profile.");
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [refresh, account.is_superuser]);

  useEffect(() => {
    if (page === 1) return;
    let active = true;
    setLoading(true);
    void api.ownerFacts(page).then(results => {
      if (active) {
        setFacts(results.results);
        setTotal(results.count);
        setHasNext(Boolean(results.next));
      }
    }).catch(() => { if (active) setError("Unable to load this page of facts."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [page]);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!draft || saving) return;
    setSaving(true);
    setError("");
    setMessage("");
    try {
      const updated = await (profile ? api.updateOwnerProfile(draft) : api.createOwnerProfile(draft));
      setProfile(updated);
      setMessage("Profile changes saved. Publication status is unchanged.");
    } catch (err) {
      setError(err instanceof ApiError && err.status === 400
        ? "Check the profile fields and try again." : "Could not save the profile.");
    } finally { setSaving(false); }
  }

  async function review(fact: OwnerFact, action: ReviewAction) {
    if (reviewing !== null) return;
    setReviewing(fact.id);
    setError("");
    setMessage("");
    try {
      const changed = await api.reviewFact(fact.id, action, fact.updated_at);
      setFacts(current => current.map(item => item.id === changed.id ? changed : item));
      setMessage("Review decision saved.");
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setError("This fact has changed or the action is no longer allowed. Latest facts were reloaded.");
        try {
          const current = await api.ownerFacts(page);
          setFacts(current.results);
          setTotal(current.count);
          setHasNext(Boolean(current.next));
        } catch { setError("This fact has changed. Reload this page before reviewing."); }
      } else {
        setError("Review could not be saved. No local decision was applied.");
      }
    } finally { setReviewing(null); }
  }

  return <section className="owner-page" aria-labelledby="owner-title">
    <div className="page-topline"><div className="breadcrumbs"><a href="#/">Overview</a><span>/</span> My workspace</div><span className="sample-label">OWNER ONLY</span></div>
    <div className="owner-heading">
      <div><div className="eyebrow">PRIVATE WORKSPACE</div><h1 id="owner-title">Your profile.<br /><em>Your decisions.</em></h1>
        <p>Review professional information before it is available to recruiters.</p></div>

    </div>
    {loading && <p role="status">Loading your information…</p>}
    {error && <p role="alert" className="owner-error">{error}</p>}
    {message && <p role="status" className="owner-success">{message}</p>}
    {draft && <div className="owner-grid">
      <section className="owner-card" aria-labelledby="edit-title">
        <div className="section-kicker">01 / PROFILE</div>
        <h2 id="edit-title">Public profile details</h2>
        <p className="owner-note">Changes do not change account approval or publication status.</p>
        {profile && <button className="button button-secondary" type="button" disabled={saving} onClick={async () => {
          setSaving(true); setError("");
          try { setProfile(await api.publishProfile(profile.publication_status !== "published")); setMessage("Profile publication updated."); }
          catch { setError("Unable to change publication."); }
          finally { setSaving(false); }
        }}>{profile.publication_status === "published" ? "Withdraw profile" : "Publish profile"}</button>}
        <div className="owner-states"><span>Account: {profile?.status.replace(/_/g, " ") || "active"}</span>
          <span>Publication: {profile?.publication_status || "draft"}</span></div>
        <form className="owner-form" onSubmit={save}>
          {editableFields.map(field => <label key={field} htmlFor={"owner-" + field}>
            {field.replace(/_/g, " ")}
            {field === "professional_summary"
              ? <textarea id={"owner-" + field} rows={5} maxLength={10000}
                  value={draft[field]} onChange={event => setDraft(current => current ? { ...current, [field]: event.target.value } : current)} />
              : <input id={"owner-" + field} value={draft[field]}
                  type={field === "phone" ? "tel" : field === "contact_email" ? "email" : field === "linkedin" ? "url" : "text"}
                  maxLength={field === "name" ? 255 : 255}
                  onChange={event => setDraft(current => current ? { ...current, [field]: event.target.value } : current)} />}
          </label>)}
          <label className="owner-checkbox"><input type="checkbox" checked={draft.show_linkedin}
            onChange={event => setDraft(current => current ? { ...current, show_linkedin: event.target.checked } : current)} />
            Make LinkedIn URL public</label>
          <label className="owner-checkbox"><input type="checkbox" checked={draft.show_contact_email}
            onChange={event => setDraft(current => current ? { ...current, show_contact_email: event.target.checked } : current)} />
            Make contact email public</label>
          <button className="button button-primary" type="submit" disabled={saving}>{saving ? "Saving…" : "Save profile"}</button>
        </form>
      </section>
      {profile && <DocumentsPanel uploadsEnabled={account.uploads_enabled} onExtracted={() => setRefresh(v => v + 1)} />}
      <section className="owner-card" aria-labelledby="facts-title">
        <div className="section-kicker">03 / KNOWLEDGE REVIEW</div>
        <h2 id="facts-title">Professional facts</h2>
        <p className="owner-note">Approval and publication are separate. Review decisions are audited by the backend.</p>
        <p className="owner-count">{total} facts</p>
        {facts.length === 0 && <p>No facts are available for this page.</p>}
        <div className="owner-facts">{facts.map(fact => <article className="owner-fact" key={fact.id}>
          <div className="owner-fact-head"><strong>{fact.fact_type.replace(/_/g, " ")}</strong>
            <span>{fact.verification_status} · {fact.is_public ? "public" : "private"}</span></div>
          <p>{fact.content}</p>
          <details><summary>Edit fact</summary><form className="owner-form" onSubmit={async e => {
            e.preventDefault(); if (reviewing !== null) return;
            const content = new FormData(e.currentTarget).get("content") as string;
            setReviewing(fact.id); setError("");
            try { const changed = await api.editFact(fact.id, content, fact.updated_at); setFacts(items => items.map(item => item.id === changed.id ? changed : item)); setMessage("Fact updated. Review and approve it again before publishing."); }
            catch { setError("Unable to edit this fact. Reload before retrying."); }
            finally { setReviewing(null); }
          }}><label htmlFor={"fact-edit-" + fact.id}>Fact content<textarea id={"fact-edit-" + fact.id} name="content" required maxLength={4000} defaultValue={fact.content} /></label><button disabled={reviewing !== null}>Save fact</button></form></details>
          <FactActions fact={fact} busy={reviewing !== null || loading} onReview={review} />
        </article>)}</div>
        <nav className="owner-pagination" aria-label="Fact pages">
          <button disabled={page === 1 || loading || reviewing !== null} onClick={() => setPage(p => p - 1)}>Previous</button>
          <span>Page {page}</span>
          <button disabled={!hasNext || loading || reviewing !== null} onClick={() => setPage(p => p + 1)}>Next</button>
        </nav>
      </section>
    </div>}
  </section>;
}

export function OwnerDashboard({ session, onLogin, onLogout, account }: {
  account: Account | null;
  session: Session;
  onLogin: () => void;
  onLogout: () => void;
}) {
  if (session === "checking") return <p role="status">Checking your session…</p>;
  if (session === "guest") return <section className="owner-page">
    <div className="eyebrow">PRIVATE WORKSPACE</div>
    <AuthLogin heading="Manage your professional profile" onLogin={onLogin} />
    <p>Only the profile owner can view or change unpublished facts.</p>
  </section>;

  if (!account) return <p role="status">Loading account…</p>;
  if (!account.can_manage_candidate) return <section className="owner-page"><h1>Recruiter workspace</h1><p>Your account can explore published profiles and ask the Candidate Agents questions.</p><a className="button button-primary" href="#/">Explore profiles</a></section>;
  return <OwnerWorkspace onLogout={onLogout} account={account} />;
}
