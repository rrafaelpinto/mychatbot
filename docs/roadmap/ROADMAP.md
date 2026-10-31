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

**Status:** Implementation delivered through the evaluation runner.
Production deployment, data approval and paid-model evaluation remain
operational follow-ups, not completed deployment claims.

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
   retrieval using LangChain and pgvector against a shared synthetic dataset.
   A paid real-model runner is available but execution is deferred.
   Full-context remains the production default until evidence supports a change.
5. Prepare a reproducible low-traffic demonstration, architecture documentation,
   secure deploy configuration and minimal operational procedures.
   Actual provisioning and public release require separate verification.

**Trust boundaries:** Verified knowledge is necessary but not sufficient for
public use; facts require explicit public approval. Candidate access policies,
recruiter input controls, and provider-cost governance stay outside LLM control.

**Non-goals:** Commercial recruiter SaaS, job matching, tailored resume
generation, multi-agent orchestration, blanket React adoption, or distributed
infrastructure without measured need.

## Future Considerations

Potential later work includes job description analysis, evidence-based resume
generation, and stateful agent orchestration. These are not approved
implementation commitments. API and independent frontend modernization have
been approved separately in Phase 4 below.

## Release readiness and deferred work

The repository includes production-focused configuration, static serving,
readiness health checks, controlled account creation and a deployment runbook.
These do not constitute a live deployed release.

**Before enabling a public demo:** provision durable managed PostgreSQL with
pgvector, verify DNS/TLS, create an owner account, review representative
professional facts for public visibility, configure positive AI budgets and
the OpenAI key, and enable Turnstile only with scheduled guest retention cleanup.
Do not enable uploads without durable private and public media storage.

**Deferred and optional:** paid real-embedding/response evaluation, strategy
selection beyond full-context, production performance measurements, object
storage, self-service registration, a verified outbound email provider, and
expanded observability. These are not release blockers for an owner-controlled
portfolio demo with uploads and registration disabled.

## Phase 4 — API and Frontend Modernization

**Status:** Approved. Incremental implementation starting with the DRF API.

**Objective:** Demonstrate professional backend/API contracts, JWT security and
a distinctive, responsive React frontend with independent deployment.

### Architecture decision

- Keep one Git repository but **two independently deployable applications**:
  existing root Django backend and future `frontend/` React/TypeScript/Vite
  application. Do not relocate the mature Django project in the first PR.
- Serve React separately as a static build from an independent host or reverse
  proxy. Django/WhiteNoise continues serving only its own admin/static assets.
- PostgreSQL/pgvector remains backend-only. Continue running the existing
  Django pages until their React replacements are verified; no big-bang rewrite.
- Use API-first DRF serializers/viewsets, stable `/api/v1/` routes,
  drf-spectacular/OpenAPI and schema-based TypeScript client generation.
- JWT applies only to authenticated API use; keep short-lived bearer access
  tokens in JavaScript memory and rotate/revoke HttpOnly refresh cookies with
  CSRF protection. Keep Django Admin session authentication. Anonymous chat
  remains an isolated, rate-limited Turnstile + session flow, not JWT.
- Preserve `full_context` and all privacy, candidate ownership, AI budgets,
  quota, idempotency and evidence authorization policy as backend invariants.
- Frontend and backend CI, build outputs, secrets and release cycles are
  independently managed. No CORS wildcard with credentialed requests.

### Delivery sequence

1. **API foundation** ([#29](https://github.com/rrafaelpinto/mychatbot/issues/29)):
   DRF, OpenAPI Swagger, public candidate read API, authenticated owner
   read API, isolation tests, no breaking HTML changes.
2. **Authentication and API mutations**
   ([#30](https://github.com/rrafaelpinto/mychatbot/issues/30)):
   SimpleJWT secure refresh design, logout/revocation, CORS, CSRF and authenticated
   mutations/chat contracts reusing existing Django services.
3. **Visual system and prototypes**
   ([#31](https://github.com/rrafaelpinto/mychatbot/issues/31)):
   deliberate recruiter-facing branding and responsive, accessible designs
   with review before implementation.
4. **Independent frontend**
   ([#32](https://github.com/rrafaelpinto/mychatbot/issues/32)):
   React/TypeScript/Vite, approved design system, typed API client, tests
   and standalone build/deployment (not embedded in Django's static assets).

**Scope controls:** no third backend service, no new paid vendor, no database
duplication, no framework replatforming, no production JWT rollout before
security tests, and no user document exposure. Live-model benchmark remains
deferred. Production deployment/guest access retain their existing safeguards.

**Definition of done:** API schema and negative authorization tests pass,
existing Python CI remains green; frontend builds/tests independently and
uses the versioned contract; visual prototypes approved; backend and frontend
can deploy independently. No cloud services are provisioned automatically.
