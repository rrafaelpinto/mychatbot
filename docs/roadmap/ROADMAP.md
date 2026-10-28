# ResumeBot Product and Engineering Roadmap

## Product Direction

ResumeBot is evolving into an AI-powered professional-profile platform. Each candidate owns a professional profile and may eventually expose a focused Candidate Agent that answers recruiter questions in the candidate's voice using only candidate-verified professional information.

The product is not a general-purpose chatbot. Public profile visibility does not grant unlimited paid AI access, and generated language never becomes candidate truth automatically.

## Portfolio-first product direction (October 2026)

**Primary purpose:** ResumeBot is a public engineering portfolio and a small deployed demonstration for technical reviewers and recruiters, not a SaaS product targeting sustained traffic or recurring revenue. Expected usage is occasional. Optimize for a clear, credible end-to-end demonstration of Python, Django, API integration, LLM integration, testing, deployment, and engineering decisions, rather than speculative scale.

**Planning decision:** The original phase sequence is a proposal, not an implementation commitment. In particular, Phase 3 (knowledge extraction and verification) must be re-scoped through discovery before work starts. Evaluate which features make the strongest, easiest-to-try portfolio experience. LangChain is a candidate technology to demonstrate, not a mandatory dependency: adopt it only when it contributes an inspectable integration or a clear technical advantage over the current direct OpenAI boundary.

**Outstanding follow-ups (prioritize by portfolio value and risk):**
- Close out Phase 2 only after confirming PR #7 integration and full CI status; document what is validated rather than assuming production readiness.
- Confirm deployment cost and low-traffic hosting constraints, including database persistence, the public demo domain, email delivery and how a recruiter can try the app with minimal friction.
- Evaluate the AI budget policy for occasional usage (especially maximum-token reservation sizing and whether the default budget blocks demonstration).
- Determine whether public interactive AI access needs demo credentials, a short-lived access grant, or another low-friction but abuse-resistant approach.
- Add an operational mechanism for inspecting/recovering successful but unsettled usage events only if deployment or testing shows it is necessary; current reconciliation has no automatic retry.
- Assess privacy, safe synthetic demo data, verified-claim boundaries, and whether the recruiter journey currently showcases the system effectively.
- Consider concise architecture documentation, a small demo video/GIF, an API example, and meaningful CI evidence as portfolio deliverables.
- Reassess extraction, RAG, embeddings, LangChain, orchestration, React and other proposed capabilities against demonstrable engineering value; avoid implementation for technology-name coverage alone.

**Next step:** Run a discovery interview to define target reviewer, ideal 3–5 minute demo, essential capabilities, technical showcase goals, operating budget, constraints, and success criteria. Produce a prioritized MVP/portfolio backlog and revised Phase 3 scope before opening implementation issues or PRs.

## Engineering Principles

- **The LLM is never the source of truth. Verified candidate data is the source of truth.**
- `PUBLIC PROFILE != UNLIMITED AI ACCESS`.
- `ACCOUNT STATUS != PUBLICATION STATUS != AI ENTITLEMENT`.
- `RAW SOURCE DOCUMENT != VERIFIED STRUCTURED FACT != GENERATED AI CONTENT`.
- `FRONTEND VISIBILITY != AUTHORIZATION`.
- AI provider calls occur only after identity, authorization, scope, and applicable cost-policy checks.
- Privacy and tenant isolation default to deny/private.
- External documents, recruiter input, retrieved content, and model output are untrusted data.
- Prefer deterministic code for security, business policy, factual validation, and cost controls.
- Introduce infrastructure and frameworks only for measured, approved requirements.
- Tests protect product and security invariants, including the absence of provider calls on denied paths.

## Completed Phases

### Phase 0 — Repository Assessment and Safety Baseline

**Status:** Completed

The legacy Django application was mapped end to end. Request flows, data handling, AI call patterns, authorization, uploads, secrets, costs, tooling, and deployment assumptions were assessed. Critical risks were documented, private working artifacts were isolated, and characterization tests established a safe modernization baseline.

### Phase 1 — Engineering, Domain, Security, and Tooling Foundation

**Status:** Completed

The project was rebuilt as a clean ResumeBot 2.0 foundation inside Django without preserving a nonexistent production schema. Python 3.12, uv, a committed lockfile, Ruff, pytest, PostgreSQL CI, production-aware settings, and a clean initial migration were established.

The domain now separates candidate ownership, lifecycle, publication, private source documents, verified facts, conversations, messages, and AI usage. Server-side policies enforce visibility and isolation. The AI provider is behind one authorization-first service boundary, uses only verified facts, records usage metadata, and is fully mocked in tests. Unsafe HTML rendering, ambiguous booleans, direct LangChain calls, and source-overwriting AI flows were removed.

## Current and Planned Phases

### Phase 2 — AI Cost Governance and Policy Enforcement

**Status:** Implemented via PRs #2–#7; formal close-out and CI verification pending.

**Objective:** Make paid AI consumption bounded, observable, concurrency-safe, and gracefully disableable before public access expands.

**Major capabilities:** Named operation policies; rate limits; per-identity, per-candidate, and operation-specific quotas; project daily/monthly budgets; reservation and reconciliation around provider calls; cost estimation from model/token usage; idempotency where duplicate requests can spend money; administrative visibility; a global circuit breaker.

**Important prerequisites:** Phase 1 authorization-first AI boundary and `AIUsageEvent`; configurable development policy; tests that can count provider calls exactly.

**Explicit non-goals:** Payments, subscriptions, commercial plan design, recruiter magic links, multiple providers, Redis by default, RAG, or final production quota values.

**Completion criteria:** Every paid operation follows `Identity -> Authorization -> Scope -> Rate Limit -> Quota -> Budget Reservation -> Provider Call -> Usage Reconciliation`; denied/exhausted requests invoke no provider; concurrent requests cannot overspend configured budgets; AI shutdown leaves non-AI profile functionality available; policy and usage are administratively inspectable.

### Phase 3 — Candidate Knowledge Extraction and Verification

**Status:** Discovery required; scope and priority subject to portfolio-first reassessment

**Objective:** Turn private candidate documents into reviewable, provenance-linked professional facts without treating extraction as truth.

**Major capabilities:** Deterministic document-processing states; extraction proposals; candidate review, correction, verification, and rejection; provenance to source documents/locations; initial domain-specific fact structures where requirements are understood.

**Important prerequisites:** Private `CandidateDocument`, `CandidateFact`, candidate ownership policies, and safe parser boundaries.

**Explicit non-goals:** Embeddings, vector search, autonomous fact approval, tailored resumes, or broad normalization of every possible resume concept.

**Completion criteria:** A candidate can upload a source, inspect extracted proposals, approve/correct facts, and distinguish raw, extracted, verified, rejected, and generated information. Only verified facts are eligible for Candidate Agent context.

### Phase 4 — AI Evaluation and Trustworthiness

**Status:** Planned

**Objective:** Measure whether Candidate Agent behavior remains factual, private, scoped, and resistant to adversarial inputs.

**Major capabilities:** Versioned evaluation datasets; deterministic assertions for evidence use, unsupported claims, refusal, privacy, scope, and prompt injection; regression gates; model/provider configuration tracking; model-as-judge only for calibrated cases that need semantic judgment.

**Important prerequisites:** Verified knowledge workflow, stable AI operation boundary, provenance, and representative synthetic scenarios.

**Explicit non-goals:** Production monitoring, broad benchmark chasing, replacing deterministic checks with an LLM judge, or retrieval technology selection.

**Completion criteria:** Repeatable evals detect factual invention, privacy leakage, injection failures, off-topic behavior, and evidence regressions; acceptance thresholds and failure triage are documented and runnable without real candidate PII.

### Phase 5 — Recruiter Identity and Controlled Public AI Access

**Status:** Planned

**Objective:** Allow lightweight verified recruiter access to published Candidate Agents without equating anonymous profile viewing with paid AI access.

**Major capabilities:** Email-code or magic-link recruiter verification; expiring/scoped access grants; candidate/operation limits; consent and privacy-aware conversation handling; abuse controls integrated with Phase 2 policy.

**Important prerequisites:** Cost governance, trustworthy agent behavior, publication policies, email delivery, and conversation authorization.

**Explicit non-goals:** Full recruiter organizations, billing, complex CRM features, or mandatory permanent recruiter accounts without evidence.

**Completion criteria:** Anonymous users can view published profiles; only verified, authorized recruiter identities can invoke AI; grants expire and are scoped; private data remains unavailable; abuse and cost policies deny before provider calls.

### Phase 6 — Public/Candidate APIs and Frontend Modernization

**Status:** Planned

**Objective:** Introduce stable APIs and modernize the highest-value candidate/public experiences without weakening backend authority.

**Major capabilities:** Purpose-built Django REST Framework endpoints as concrete UI needs arise; React/TypeScript feature slices; accessible profile, document-review, public-profile, and conversation UX; explicit loading/error/AI-disabled states.

**Important prerequisites:** Stable domain workflows, authorization policies, recruiter access rules, and API acceptance tests.

**Explicit non-goals:** Rewriting every working server-rendered page at once, moving authorization into the frontend, FastAPI, or design-system expansion without product need.

**Completion criteria:** Selected product journeys use tested APIs and accessible frontend slices; server-side authorization remains canonical; old surfaces are removed only when replacements preserve behavior and security.

### Phase 7 — Retrieval Evaluation and Candidate Knowledge Search

**Status:** Planned

**Objective:** Select relevant verified candidate evidence efficiently and measurably as knowledge volume grows.

**Major capabilities:** Defined corpus/query patterns; structured SQL and PostgreSQL full-text baselines; retrieval evaluation dataset and metrics; comparison of semantic and hybrid retrieval; evidence-linked answer context.

**Important prerequisites:** Sufficient verified structured knowledge, provenance, eval infrastructure, and representative queries.

**Explicit non-goals:** Assuming pgvector, embeddings, or a dedicated vector database before measurement; indexing unverified/private data without policy; generic web search.

**Completion criteria:** Retrieval quality, latency, isolation, and cost are measured against a baseline; the simplest approach meeting thresholds is selected and documented; every retrieved item remains authorized and evidence-linked.

### Phase 8 — Job Description Analysis and Candidate Matching

**Status:** Planned

**Objective:** Analyze job requirements against verified candidate evidence while distinguishing strengths, partial matches, and gaps.

**Major capabilities:** Untrusted JD ingestion; structured requirement extraction; authorized candidate-evidence retrieval; requirement matching; explainable strengths/gaps; evidence references; evaluation of unsupported-match risk.

**Important prerequisites:** Verified facts, retrieval baseline, AI evals, cost governance, and privacy policies.

**Explicit non-goals:** Fabricating requested skills, auto-applying to jobs, ranking candidates across tenants, or generating a tailored resume in the same phase.

**Completion criteria:** Each match claim is supported by verified evidence or explicitly marked as a gap/uncertainty; injected JD instructions cannot override system/privacy policy; cost and accuracy are measured.

### Phase 9 — Tailored Resume Generation and Validation

**Status:** Planned

**Objective:** Generate truthful, ATS-friendly resume versions planned from verified evidence and a specific JD.

**Major capabilities:** Requirement-to-evidence mapping; resume planning; constrained generation; claim-level evidence tracking; factual validation; ATS-oriented structural checks; candidate review and version management.

**Important prerequisites:** JD matching, verified knowledge, provenance, evaluations, document generation requirements, and cost controls.

**Explicit non-goals:** Adding unsupported experience, replacing the original source resume, autonomous submission, or visual complexity that harms ATS readability.

**Completion criteria:** Generated claims trace to verified evidence; unsupported JD terms are not represented as candidate experience; deterministic factual/ATS checks pass; candidates review and manage generated versions separately from source truth.

### Phase 10 — Agent Tools and Stateful Orchestration

**Status:** Planned

**Objective:** Add durable multi-step orchestration only for workflows that require tools, checkpoints, retries, and human approval.

**Major capabilities:** Explicit tool permissions; resumable workflow state; candidate approval checkpoints; bounded retries; idempotent steps; auditability; evaluation of an orchestration framework such as LangGraph against actual needs.

**Important prerequisites:** At least one proven complex workflow, stable tools/services, cost governance, evaluations, and persistence requirements.

**Explicit non-goals:** A multi-agent product hierarchy, framework adoption for basic chat, unrestricted tools, or replacing deterministic services with agent reasoning.

**Completion criteria:** The chosen workflow demonstrates a concrete need for orchestration; interruption/resume and approval are reliable; tools remain authorized and cost-bounded; the framework decision is evidence-backed and recorded.

### Phase 11 — Production Observability, Reliability, and Deployment

**Status:** Planned

**Objective:** Operate ResumeBot safely with measurable reliability, cost, security, and recovery characteristics.

**Major capabilities:** Deployment pipeline; production PostgreSQL and private object storage; secrets and backup/restore procedures; structured PII-safe logs; metrics/tracing; AI cost/eval monitoring; latency/error dashboards; health checks; CSP/security headers; operational runbooks; background processing only where measured workloads require it.

**Important prerequisites:** Stable product surfaces, cost policies, privacy/retention decisions, representative load, and completed security review.

**Explicit non-goals:** Kubernetes, Kafka, Redis, Celery, or other infrastructure without measured operational requirements; declaring production readiness without restore/security exercises.

**Completion criteria:** Deployments and rollbacks are repeatable; backups restore successfully; secrets and private files are managed outside Git; service/AI health and budgets are observable; incident and AI-disable procedures are tested; production security checks pass.
