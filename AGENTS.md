# ResumeBot Engineering Guide

## Product and architecture invariants

- Django remains the backend and PostgreSQL the primary datastore.
- Verified candidate facts are the only source of truth for factual AI answers.
- Raw documents, extracted proposals, verified facts, and AI-generated content remain separate.
- Account activation, candidate approval, publication, and AI entitlement are different concerns.
- Privacy defaults to private. Authentication email and phone are never implicitly public.
- Authorization and paid-operation checks are server-side and reusable outside views.
- A denied AI operation must fail before any provider call.
- Treat uploads, recruiter input, retrieved content, and model output as untrusted.
- Do not render model or user content as HTML.
- Do not add React, RAG, Redis, LangGraph, vector search, or background infrastructure without a concrete approved requirement.

## Commands

```text
uv sync
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run python manage.py check
uv run python manage.py makemigrations --check --dry-run
```

Use Python 3.12. Manage dependencies only through `pyproject.toml` and commit `uv.lock` changes. Do not recreate a hand-maintained `requirements.txt` unless a concrete deployment consumer requires a generated export.

## Change rules

- Inspect affected flows, policies, tests, and migrations before editing.
- Put HTTP translation in views, reusable authorization in `chatbot.policies`, document processing in `chatbot.services.documents`, and paid calls in `chatbot.services.ai`.
- Never call OpenAI directly from a view, model, template, or task.
- Keep migrations clean and review schema/data effects. Phase 1 has no legacy database, but future migrations must preserve real state once it exists.
- Add tests for behavior and invariants, especially negative authorization and exact provider-call boundaries.
- Use synthetic test data; never add real resumes, credentials, or PII fixtures.
- Keep application errors sanitized and logs free of resume/contact contents.
- Record only consequential accepted decisions as ADRs.

## Private workspace

`.local/` is fully ignored and may contain learning notes, prompts, research, scratch work, sessions, and LinkedIn drafts. It must never contain runtime requirements or the sole record of an engineering decision. Do not commit AI transcripts or raw collaboration artifacts.

## Definition of done

- behavior and security invariants have tests;
- unauthorized paths do not cross provider or private-data boundaries;
- migrations have no unexplained drift;
- `uv run pytest`, Ruff lint, Ruff format check, and Django checks pass;
- configuration and documentation reflect the change;
- no secret, real PII, generated artifact, or private working material entered Git.
