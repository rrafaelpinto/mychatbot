# ResumeBot

ResumeBot is a Django application for candidate-owned professional profiles and a focused Candidate Agent. The core trust rule is simple:

> The language model is never the source of candidate truth. Only candidate-verified facts may support an AI answer.

The implementation demonstrates Python 3.12, Django, PostgreSQL, scoped access
policies, bounded anonymous LLM chat, LangChain-assisted knowledge extraction,
human-reviewed citations, budget governance, PostgreSQL full-text search,
pgvector experiments, and reproducible evaluations. The intended audience
is recruiters and technical reviewers, not a high-traffic SaaS service.

**Production uses full-context retrieval.** FTS and semantic pgvector retrieval
remain benchmarked alternatives; paid live-model comparison is deferred.
No candidate document or AI-generated fact is published automatically.

For production prerequisites and operations, see the
[deployment runbook](docs/engineering/DEPLOYMENT.md) and
[architecture overview](docs/engineering/ARCHITECTURE.md).

## Architecture

The backend is a modular Django monolith backed by PostgreSQL. A separately
built React/TypeScript application lives in [`frontend/`](frontend/) and uses
versioned DRF/OpenAPI endpoints. It is deployed independently; Django and
WhiteNoise do not serve the React bundle. The frontend includes public
profiles, authenticated candidate chat and an owner-only review workspace.

The backend domain includes:

- `CandidateProfile` owns candidate lifecycle, publication, and privacy-controlled profile data.
- `CandidateDocument` stores private raw source documents and unverified extracted text.
- `CandidateFact` stores reviewable facts and optional source provenance.
- `Conversation` and `Message` represent recruiter interaction history.
- `chatbot.policies` contains reusable server-side authorization decisions.
- `chatbot.services.ai` is the only paid provider boundary and records minimal usage metadata.

Candidates start in `PENDING_APPROVAL` with a private `DRAFT`. Only an `ACTIVE` and `PUBLISHED` profile can be viewed publicly or receive Candidate Agent interactions. Platform approval/publication is currently manual through Django admin.

## Requirements

- Python 3.12
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- PostgreSQL 16 or another supported modern PostgreSQL release with pgvector

## Setup

Install locked runtime and development dependencies:

```sh
uv sync
```

Create a local PostgreSQL database, copy the placeholder environment file, and replace local values:

```sh
createdb resumebot
cp .env.example .env
set -a
source .env
set +a
```

The application deliberately does not auto-load `.env`; environment injection remains explicit and works the same way in deployment. Never commit `.env` or reuse credentials from repository history.

Initialize the clean schema and run the server:

```sh
uv run python manage.py migrate
uv run python manage.py createsuperuser
uv run python manage.py runserver
```

Account registration uses email activation. Development defaults to Django's console email backend, so activation links are printed to the terminal. Candidate approval and publication are separate admin-controlled states.

## Quality commands

```sh
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run python manage.py check
uv run python manage.py makemigrations --check --dry-run
```

Apply formatting locally with:

```sh
uv run ruff format .
```

CI uses PostgreSQL with pgvector as the authoritative database environment.
Some tests can use SQLite locally, but pgvector migrations, concurrency and
retrieval integration require PostgreSQL. Use `TEST_WITH_POSTGRES=true`
with a local PostgreSQL instance for complete coverage.

## Configuration

The main variables are documented in `.env.example`.

- `RESUMEBOT_ENV=development|production` controls environment hardening.
- `DJANGO_SECRET_KEY` and `DJANGO_ALLOWED_HOSTS` are mandatory in production.
- PostgreSQL uses the `POSTGRES_*` variables.
- `PRIVATE_MEDIA_ROOT` may point to a non-public document location.
- `OPENAI_API_KEY` enables the Candidate Agent; tests never require it.
- `OPENAI_MODEL` and `OPENAI_TIMEOUT_SECONDS` control the current provider call.
- `AI_ENABLED` is the global switch for paid AI operations. It defaults to true in
  development and false in production, where it must be explicitly enabled.
- `AI_CANDIDATE_CHAT_ENABLED` controls the named `candidate_chat` operation.
  These switches only gate AI and do not disable public profile pages.
- `AI_CHAT_IDENTITY_PER_MINUTE`, `AI_CHAT_IDENTITY_PER_DAY`, and
  `AI_CHAT_CANDIDATE_PER_DAY` set admitted-request limits for the chat operation.
  Day limits use rolling 24-hour windows. Admitted attempts count even on provider failure.
  PostgreSQL row locks enforce limits across concurrent workers; no cache is required.
- `AI_DAILY_BUDGET_USD` and `AI_MONTHLY_BUDGET_USD` cap reservations in UTC
  calendar windows; both default to zero in production until explicitly configured.
- `AI_INPUT_USD_PER_MILLION` and `AI_OUTPUT_USD_PER_MILLION` supply the
  configured `gpt-4o-mini` price assumptions. Update them when pricing changes.
- Each admitted operation reserves the full configured maximum token cost before
  the provider call. Reservations are not released or adjusted in this slice;
  confirmed provider token usage is now settled after success. Unused funds are
  credited back to the matching UTC calendar windows; missing usage data,
  provider failures and ambiguous outcomes retain the full reservation.
  Reconciliation is idempotent for settled operations. Token prices are
  snapshotted at admission, preventing later configuration changes from
  repricing previously admitted calls. If settlement fails after a successful
  provider response, the response remains available and the event remains
  unsettled for operational recovery; no second provider request is made.
- Clients may send an `Idempotency-Key` header (1–128 printable ASCII characters)
  with chat POST requests. Reusing a key for the same identity, candidate, and
  operation returns HTTP 409 without another paid provider call. Clients should
  use a fresh key for each intentional request; omitted keys preserve legacy behavior.
- Django admin exposes read-only AI usage, reserved and settled costs, and the
  current project budget counters. Monetary figures are stored in micro-USD.
  Other models fail closed until pricing/reservation support is added.

Production mode rejects debug and enables HTTPS redirect, secure cookies, and HSTS.
Public registration, password reset and filesystem uploads are disabled by
default in production. Static assets are served through WhiteNoise; user media
requires separately configured durable storage and safe delivery. Set `DJANGO_TRUST_X_FORWARDED_PROTO=true` only behind a trusted proxy that overwrites the forwarded-protocol header.
HSTS preload remains opt-in through `DJANGO_SECURE_HSTS_PRELOAD=true`; enable it only after HTTPS and subdomain coverage are intentionally permanent.

Public candidate images use normal media storage during development. Candidate
source documents use a separate storage backend with no public URL.
Production uses WhiteNoise for immutable static assets, **not** for user media.
See the deployment runbook before enabling uploads.

## Candidate knowledge

Candidate facts are private by default, even after verification. The Candidate Agent
uses only facts that are both verified and explicitly marked public. Source resumes
and extracted text remain private. To prepare a candidate knowledge corpus, see
[Safe fact import](docs/engineering/FACT_IMPORT.md). No real resume or candidate
fact pack is committed to the repository.

## Development guidance

Engineering conventions and the definition of done are in [`AGENTS.md`](AGENTS.md). Product direction and phase status are in [`docs/roadmap/ROADMAP.md`](docs/roadmap/ROADMAP.md), and accepted architecture decisions are under [`docs/adr/`](docs/adr/).

## Contextual answers and public evidence

The Candidate Agent sends a bounded list of previous recruiter questions, not
previous model responses. Conversations are fetched from the server-side
authenticated user or the verified guest session, never from client-supplied
history. The model receives only verified and explicitly public fact IDs,
types, and content, and must return JSON with a factual answer and supporting
fact IDs. The backend validates every cited ID against currently approved
facts before exposing evidence; invalid citations result in a refusal.
This provides reference authorization, not proof of semantic faithfulness.
Claim-level support remains a separate evaluation limitation.

Only the fact content and type are shown as evidence; source documents and
private provenance labels remain inaccessible. Previously cited answers are
hidden from the rendered history if their supporting facts are withdrawn.

## Anonymous demonstration access

Guest chat is disabled by default. See
[Anonymous chat operation](docs/engineering/GUEST_CHAT.md) for Turnstile setup,
proxy trust, quotas, data retention, and the cleanup command. Existing
registered-user conversations keep their original authorization and quotas.

## AI evaluation baseline

Use `uv run python manage.py evaluate_candidate_agent --fail-on-overflow` to
run the offline, deterministic synthetic full-context baseline. See
[AI evaluation methodology](docs/engineering/AI_EVALUATION.md) for dataset
coverage, metrics, response replay and limitations. CI never calls the AI provider.

## Controlled real-model evaluation

The offline retrieval benchmark remains the CI default. An optional, explicitly
budget-capped experiment can evaluate real embeddings, model answers, citations,
latencies, tokens and cost using synthetic facts only. See
[paid Candidate Agent evaluation](docs/engineering/PAID_AI_EVALUATION.md).
No paid evaluation runs automatically or changes production retrieval.

## Versioned REST API and frontend roadmap

Django REST Framework provides a versioned, read-only candidate API with
OpenAPI documentation at `/api/schema/` and Swagger UI at `/api/docs/`.
This API deliberately preserves existing Django pages and the guest-chat
protection boundary while JWT and React are built separately.
See [API v1](docs/engineering/REST_API.md) and the
[Phase 4 architecture plan](docs/engineering/PHASE4_API_FRONTEND.md).

The future `frontend/` React/TypeScript/Vite app will build and deploy
independently of Django. WhiteNoise serves **only** Django's own static
assets, not the separate React application.

## JWT API and independent frontend authentication

The API supports 5-minute bearer access tokens and a rotating, revocable
`HttpOnly` refresh cookie with CSRF protection. Django Admin continues to
use sessions, and guest Candidate Agent access retains its Turnstile session
and cost limits. Owner profile PATCH, fact review and authenticated chat
reuse existing backend authorization and audit rules.

For frontend integration, deployment origins, token lifecycle and the
security threat model, see [JWT API Security](docs/engineering/JWT_API_SECURITY.md).
No React build is bundled into Django.

## Phase 4 visual prototype

A standalone, responsive **fictional** design preview is available under
[`prototypes/visual/`](prototypes/visual/). It proposes ResumeBot's
professional identity, public profile, evidence-led Agent and UI states,
with light/dark mode. It makes no API calls and does not replace the
existing Django pages. See [Design system](docs/design/DESIGN_SYSTEM.md)
and [Visual review](docs/design/VISUAL_REVIEW.md). The independently
deployable React implementation remains a separate reviewed PR.
