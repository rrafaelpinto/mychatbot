# AI-assisted development responsibilities

ResumeBot uses responsibility boundaries, not a large collection of generic agents.

- **Planner / Architect:** cross-domain scope, invariants, acceptance criteria, migration/design trade-offs. Does not implement speculative infrastructure.
- **Backend Engineer:** Django, PostgreSQL, policies, services, migrations, and provider integrations. Does not move authorization to the frontend or call providers before policy.
- **Frontend Engineer:** accessible, safe server-rendered UX now and approved React slices later. Does not treat UI visibility as authorization or render model HTML.
- **Quality Engineer:** characterization, invariant, integration, migration, and future AI evaluation design. Does not optimize for superficial coverage.
- **Security & Reliability Engineer:** isolation, privacy, uploads, secrets, prompt injection, paid-call ordering, failure modes, and cost governance. Does not outsource deterministic controls to prompts.

Use only the roles materially needed by a task. Stable procedures live in repository-local skills; task prompts, transcripts, scratch plans, and personal reflection remain under `.local/`.
