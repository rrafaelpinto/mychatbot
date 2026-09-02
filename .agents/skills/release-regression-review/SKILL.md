---
name: release-regression-review
description: Perform the final ResumeBot regression and release-readiness review for a completed code change. Use before handoff when migrations, authorization, uploads, dependencies, AI boundaries, settings, or CI behavior may have changed.
---

# Release Regression Review

Review the actual diff and affected request flows before running the standard commands.

Check that:

- no secret, real PII, source document, `.local/` content, or generated environment artifact entered Git;
- dependency changes are declared in `pyproject.toml`, resolved in `uv.lock`, and contain no duplicate requirements source;
- migrations match models and have understandable fresh/upgrade behavior;
- authorization and privacy decisions are server-side with negative tests;
- untrusted input/model output is not rendered as HTML or logged;
- views do not call provider SDKs directly and denial precedes paid calls;
- README, configuration examples, ADRs, and `AGENTS.md` remain accurate.

Run `uv sync --locked`, Ruff lint, Ruff format check, pytest, migration drift check, and Django system/deployment checks appropriate to the environment. Report failures precisely; do not mutate external deployments, rotate live credentials, or publish changes unless separately authorized.
