# ResumeBot

ResumeBot is a Django application for candidate-owned professional profiles and a focused Candidate Agent. The core trust rule is simple:

> The language model is never the source of candidate truth. Only candidate-verified facts may support an AI answer.

Phase 1 provides the backend, domain, security, test, and developer-tooling foundation. React, RAG, vector search, Job Description analysis, tailored resumes, and advanced agent orchestration are intentionally deferred.

## Architecture

The project is a modular Django monolith backed by PostgreSQL:

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
- PostgreSQL 16 or another supported modern PostgreSQL release

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

Tests use SQLite by default for speed and hermetic local execution. CI sets `TEST_WITH_POSTGRES=true` and runs the same suite against PostgreSQL. PostgreSQL remains authoritative for database behavior; add PostgreSQL-specific tests whenever constraints, locking, JSON, indexing, or query semantics matter.

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
  Reconciliation is idempotent for settled operations.
- Clients may send an `Idempotency-Key` header (1–128 printable ASCII characters)
  with chat POST requests. Reusing a key for the same identity, candidate, and
  operation returns HTTP 409 without another paid provider call. Clients should
  use a fresh key for each intentional request; omitted keys preserve legacy behavior.
- Django admin exposes read-only AI usage, reserved and settled costs, and the
  current project budget counters. Monetary figures are stored in micro-USD.
  Other models fail closed until pricing/reservation support is added.

Production mode rejects debug and enables HTTPS redirect, secure cookies, and HSTS. Set `DJANGO_TRUST_X_FORWARDED_PROTO=true` only behind a trusted proxy that overwrites the forwarded-protocol header.
HSTS preload remains opt-in through `DJANGO_SECURE_HSTS_PRELOAD=true`; enable it only after HTTPS and subdomain coverage are intentionally permanent.

Public candidate images use normal media storage during development. Candidate source documents use a separate storage backend with no public URL. Production static/media delivery is a deployment concern and is not provided by Django.

## Development guidance

Engineering conventions and the definition of done are in [`AGENTS.md`](AGENTS.md). Product direction and phase status are in [`docs/roadmap/ROADMAP.md`](docs/roadmap/ROADMAP.md), and accepted architecture decisions are under [`docs/adr/`](docs/adr/).
