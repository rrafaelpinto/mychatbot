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

Production mode rejects debug and enables HTTPS redirect, secure cookies, and HSTS. Set `DJANGO_TRUST_X_FORWARDED_PROTO=true` only behind a trusted proxy that overwrites the forwarded-protocol header.
HSTS preload remains opt-in through `DJANGO_SECURE_HSTS_PRELOAD=true`; enable it only after HTTPS and subdomain coverage are intentionally permanent.

Public candidate images use normal media storage during development. Candidate source documents use a separate storage backend with no public URL. Production static/media delivery is a deployment concern and is not provided by Django.

## Development guidance

Stable engineering rules and the definition of done are in `AGENTS.md`. Architecture decisions are under `docs/adr/`. Private learning notes, prompts, research, and session artifacts belong under the fully ignored `.local/` directory.
