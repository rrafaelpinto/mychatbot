# Architecture and trust boundaries

ResumeBot is a low-traffic portfolio application built as a modular Django
monolith, with PostgreSQL as its single durable datastore.

```text
Visitor / recruiter
    |
    v
Gunicorn + WhiteNoise (static files only)
    |
    +--> Django candidate profile and access policies
    |      +--> Published profile: public, approved fields
    |      +--> Private owner review: pending facts and provenance
    |
    +--> Candidate Agent (optional public guest session)
           +--> Turnstile challenge and server-side guest session
           +--> Per-session, per-origin and global quotas
           +--> Global AI budget reservation
           +--> Verified + public CandidateFact selection (full context)
           +--> OpenAI completion / structured fact IDs
           +--> Backend fact-ID authorization and usage reconciliation
           +--> Answer and approved evidence
    |
    v
PostgreSQL (profiles, facts, sessions, conversations, AI ledger,
            FTS index, optional pgvector experiment)
```

**Trust rules**

- Candidate facts are private until explicitly verified **and** published.
- Raw resume files and extracted text are private; evidence quotations stay
  on owner-only review pages.
- An authenticated user cannot access another candidate's private data.
  Anonymous users only access published profiles and bounded sessions.
- The model receives only explicitly approved facts; its citations are
  revalidated in deterministic application code.
- Guest identity and quotas are persisted, not enforced by browser state.
  Trusted proxy IP headers must be configured explicitly.
- Every live paid operation has quota and project-budget admission; synthetic
  CI evaluations do not call paid services.
- Production public chat uses `full_context`. Native PostgreSQL FTS and
  LangChain + pgvector are measured examples, not enabled alternatives.
- File uploads remain disabled in production until durable public/private
  storage is configured. WhiteNoise never serves uploaded source documents.
- Public registration is off by default for a controlled portfolio.

**Important limitations**

A cited fact is an authorized reference, not proof that an entire model
response is semantically entailed. The small synthetic evaluation corpus
is useful for repeatable engineering checks but not statistical claims of
retrieval superiority. The separate paid benchmark runner remains optional
and has not been used to select a new production strategy.

The operational checklist and manual deployment sequence are documented in
[Production deployment](DEPLOYMENT.md). Architecture decision records are in
`docs/adr/`.
