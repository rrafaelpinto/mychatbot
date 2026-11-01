# Architecture and trust boundaries

ResumeBot is a low-traffic portfolio application built as a modular **Python/Django** monolith with a separately compiled **React/TypeScript** frontend and PostgreSQL as the durable datastore.

```text
Visitor / recruiter                   Candidate owner
       |                                    |
       +----------- React / Vite -----------+
                       |
                  Versioned REST API
                  Django REST Framework
                       |
          +------------+------------+
          |            |            |
     Public views   Owner review   Candidate Agent
          |            |            |
     Published data   Private     Authenticated JWT
       only           facts      or guest sessions
          |            |            |
          |      Verification    Turnstile (guest)
          |      + publication   Rate/quota/budget gates
          |            |            |
          |            |      Approved fact retrieval
          |            |      OpenAI structured answer
          |            |      Evidence reauthorization
          +------------+------------+
                       |
                    PostgreSQL
           Profiles, facts, sessions,
           conversations, AI usage ledger,
           FTS and optional pgvector
```

Django retains its own administrative and fallback HTML pages, and WhiteNoise serves only Django's static assets. React consumes a versioned Django REST Framework API. `drf-spectacular` generates the OpenAPI schema, and CI checks the generated TypeScript contract for drift.

## Domain and AI boundary

- `CandidateProfile` separates account status, publication status, and public profile fields.
- `CandidateFact` has independent verification and publication decisions; owner-only evidence/provenance never appears in public payloads.
- `CandidateDocument` contains private raw documents and extracted material; publication is always an explicit review action.
- `Conversation` and `Message` preserve authorized conversation history; guest sessions have distinct ownership and retention.
- `chatbot.services.ai` is the only paid provider boundary. It admits requests after authorization, quota and budget checks, then reconciles usage.
- The Candidate Agent **speaks as the candidate in first person**. It receives approved facts as data and must return a structured answer plus supporting fact IDs. The backend checks those IDs against current approvals.
- Retrieval defaults to `full_context`; native PostgreSQL FTS and LangChain/pgvector semantic retrieval are independently evaluated alternatives, not the public production strategy.

## Security and operational controls

- All privacy and authorization decisions are enforced by Django, not by client visibility or model output.
- JWT access tokens remain in browser memory; refresh tokens are rotated in Secure HttpOnly cookies. CSRF protections apply to credential-bearing operations.
- Optional anonymous chat uses verified Turnstile tokens, server-side Django sessions, origin-level limits and global AI budgets.
- Separate React and API origins must be explicitly allowlisted for credentialed CORS; same-site HTTPS subdomains are required for the default cookie policy.
- Requests are idempotency-aware where duplicate calls could spend AI budget. Usage reservations and provider reconciliation are persisted in PostgreSQL.
- File uploads and self-registration remain disabled in production until their supporting storage and email services are configured.
- No Redis, Celery workers, distributed queues, or paid embedding infrastructure are needed to operate this controlled portfolio deployment.

## Limitations

Verified citations establish **authorization and traceability**, not formal semantic proof for every generated claim. Offline retrieval tests are deterministic engineering checks, not statistical evidence of superiority. Live-model evaluations require explicit approval and spending caps.

A manual two-service Render Blueprint and deployment checks are versioned, but DNS/TLS, a persistent production database, browser cookie validation and real Turnstile activation remain operational tasks. See [Production deployment](DEPLOYMENT.md) and the [roadmap](../roadmap/ROADMAP.md).
