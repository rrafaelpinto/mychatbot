# ResumeBot Product and Engineering Roadmap

## Product Direction

ResumeBot is evolving into an AI-powered professional-profile platform. Each candidate owns a professional profile and may eventually expose a focused Candidate Agent that answers recruiter questions in the candidate's voice using only candidate-verified professional information.

The product is not a general-purpose chatbot. Public profile visibility does not grant unlimited paid AI access, and generated language never becomes candidate truth automatically.

## Portfolio Scope and Priorities

ResumeBot is a publicly inspectable engineering portfolio with a low-traffic, deployed demonstration for recruiters and technical reviewers. It is not currently intended as a commercial SaaS product. The application should make it straightforward to explore a representative candidate profile, understand the architecture, and evaluate a working LLM-backed interaction.

Prioritize a credible end-to-end experience and maintainable engineering: Python, Django, PostgreSQL, API and LLM integrations, automated tests, security, and economical deployment. Public documentation should explain observable behavior, architecture, technical trade-offs, and product direction.

Candidate knowledge extraction, evaluation, recruiter access, APIs, and retrieval remain potential capabilities. Their scope and sequence should be based on demonstrated value to the portfolio, rather than the previously numbered phases. Additional frameworks, including LangChain, should be adopted when they solve a specific problem and offer a defensible trade-off against simpler alternatives.

### Open product and operational decisions

- Select a minimal, safe experience for occasional public recruiter demonstrations, including appropriate authorization and cost safeguards.
- Define low-traffic hosting requirements and a sustainable operating budget, including persistent storage and essential communications.
- Evaluate whether existing AI budget reservation limits impede the intended demonstration.
- Define the handling of successful AI calls whose usage reconciliation remains pending; automated retry is not currently provided.
- Determine the appropriate treatment of representative candidate data, including privacy and verification requirements.
- Identify the minimum useful technical documentation and automated checks for a publicly reviewed application.

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

**Status:** Implemented; release and operational verification remain separate concerns.

**Objective:** Make paid AI consumption bounded, observable, concurrency-safe, and gracefully disableable before public access expands.

**Major capabilities:** Named operation policies; rate limits; per-identity, per-candidate, and operation-specific quotas; project daily/monthly budgets; reservation and reconciliation around provider calls; cost estimation from model/token usage; idempotency where duplicate requests can spend money; administrative visibility; a global circuit breaker.

**Important prerequisites:** Phase 1 authorization-first AI boundary and `AIUsageEvent`; configurable development policy; tests that can count provider calls exactly.

**Explicit non-goals:** Payments, subscriptions, commercial plan design, recruiter magic links, multiple providers, Redis by default, RAG, or final production quota values.

**Completion criteria:** Every paid operation follows `Identity -> Authorization -> Scope -> Rate Limit -> Quota -> Budget Reservation -> Provider Call -> Usage Reconciliation`; denied/exhausted requests invoke no provider; concurrent requests cannot overspend configured budgets; AI shutdown leaves non-AI profile functionality available; policy and usage are administratively inspectable.

### Phase 3 — Trusted Candidate Agent, RAG, and Public Demonstration

**Status:** Approved; implementation in progress.

**Objective:** Demonstrate a publicly accessible, trustworthy Candidate Agent
grounded in reviewed professional information, with traceable evidence and
reproducible AI evaluations.

**Incremental delivery:**
1. Prepare a curated professional-fact corpus, with private-by-default imports,
   explicit verification and public visibility, and synthetic test data.
2. Allow limited anonymous chat with contextual follow-up questions and
   backend-enforced budget and abuse controls.
3. Support structured LLM-assisted knowledge extraction and human review of
   proposed facts. Documents remain private; generated facts never self-approve.
4. Compare full-context prompting, PostgreSQL full-text retrieval, and semantic
   retrieval using LangChain, embeddings, and pgvector against a shared
   evaluation dataset. Select the production approach based on measured quality,
   latency, and cost.
5. Publish a reproducible low-traffic demonstration, architecture documentation,
   and minimal operational procedures.

**Trust boundaries:** Verified knowledge is necessary but not sufficient for
public use; facts require explicit public approval. Candidate access policies,
recruiter input controls, and provider-cost governance stay outside LLM control.

**Non-goals:** Commercial recruiter SaaS, job matching, tailored resume
generation, multi-agent orchestration, blanket React adoption, or distributed
infrastructure without measured need.

## Future Considerations

Potential later work includes job description analysis, evidence-based resume
generation, dedicated public APIs, frontend modernization, and stateful agent
orchestration. These are not approved implementation commitments.
