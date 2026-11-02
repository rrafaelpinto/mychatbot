import { useEffect, useState, type FormEvent } from "react";
import { api, ApiError } from "./api/client";
import type { OwnerDocument } from "./api/types";

export function DocumentsPanel({ uploadsEnabled, onExtracted }: { uploadsEnabled: boolean; onExtracted: () => void }) {
  const [documents, setDocuments] = useState<OwnerDocument[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [page, setPage] = useState(1);
  const [hasNext, setHasNext] = useState(false);
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    let active = true;
    void api.documents(page).then(data => { if (active) { setDocuments(data.results); setHasNext(Boolean(data.next)); } }).catch(() => { if (active) setError("Unable to load documents."); });
    return () => { active = false; };
  }, [page, refresh]);
  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!file || busy) return;
    if (file.size > 5 * 1024 * 1024) { setError("Choose a PDF or DOCX up to 5 MB."); return; }
    setBusy(true); setError(""); setMessage("");
    try {
      const document = await api.uploadDocument(file);
      setPage(1); setRefresh(v => v + 1);
      setMessage(document.processing_status === "failed" ? "The document was saved but could not be read. Try a different PDF or DOCX." : "Document uploaded and read. Generate suggested facts when you are ready.");
    } catch (err) { setError(err instanceof ApiError && err.status === 400 ? "Upload a valid PDF or DOCX, up to 5 MB." : "Upload could not be completed. Refresh the document list before retrying."); }
    finally { setBusy(false); }
  }
  async function extract(id: number) {
    setBusy(true); setError(""); setMessage("");
    try { const result = await api.extractDocument(id); setMessage(`${result.proposed_count} suggested facts are ready for review. Nothing has been published.`); setRefresh(v => v + 1); onExtracted(); }
    catch (err) { setError(err instanceof ApiError ? err.message : "Extraction could not be completed."); setRefresh(v => v + 1); }
    finally { setBusy(false); }
  }
  return <section className="owner-card" aria-labelledby="documents-title">
    <div className="section-kicker">02 / SOURCE DOCUMENTS</div><h2 id="documents-title">Your resume</h2>
    <p>Documents stay private. Generating suggested facts uses your existing AI allowance and does not approve or publish information.</p>
    {!uploadsEnabled && <p role="status">Uploads are currently unavailable.</p>}
    <form className="owner-form" onSubmit={upload}><label htmlFor="resume-file">PDF or DOCX, up to 5 MB<input id="resume-file" type="file" accept=".pdf,.docx" required disabled={busy || !uploadsEnabled} onChange={e => setFile(e.target.files?.[0] ?? null)} /></label><button className="button button-primary" disabled={busy || !uploadsEnabled || !file}>{busy ? "Working…" : "Upload resume"}</button></form>
    {error && <p role="alert" className="owner-error">{error}</p>}{message && <p role="status">{message}</p>}
    <ul className="document-list">{documents.map(document => <li key={document.id}><strong>{document.original_filename}</strong><p>Document: {document.processing_status}. Fact extraction: {document.extraction_status.replace(/_/g, " ")}.</p>{document.processing_status === "processed" && <button disabled={busy || document.extraction_status === "succeeded" || document.extraction_status === "running"} onClick={() => void extract(document.id)}>Generate suggested facts</button>}</li>)}</ul>
    {!documents.length && <p>No documents uploaded yet.</p>}
    <nav className="owner-pagination" aria-label="Document pages"><button disabled={busy || page === 1} onClick={() => setPage(p => p - 1)}>Previous</button><span>Page {page}</span><button disabled={busy || !hasNext} onClick={() => setPage(p => p + 1)}>Next</button><button disabled={busy} onClick={() => setRefresh(v => v + 1)}>Refresh</button></nav>
  </section>;
}
