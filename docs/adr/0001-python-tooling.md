# ADR 0001: Python 3.12, uv, pyproject.toml, Ruff, and pytest

## Status

Accepted — 2026-09-01

## Context

The repository used a hand-maintained snapshot of direct and transitive packages, declared no Python version, configured an undeclared Django app, and had no project lint/test configuration or lockfile. The snapshot failed under an implicitly selected Python 3.14 and worked under Python 3.12.

## Decision

Python is bounded to `>=3.12,<3.13`. `pyproject.toml` is the dependency and tool source of truth, uv resolves and synchronizes the committed `uv.lock`, Ruff handles lint/import ordering/formatting, and pytest with pytest-django runs tests. Runtime and development dependencies are separate. The old `requirements.txt` is removed because there is no deployment consumer.

## Alternatives considered

- Keep pip/requirements: familiar, but preserves direct/transitive ambiguity and lacks a project lock workflow.
- Poetry/PDM: capable, but adds no needed benefit over the approved uv toolchain.
- Support several Python versions now: broader, but increases compatibility work before a stable baseline.

## Consequences and trade-offs

Clean setup and CI are reproducible and use the same commands. Python upgrades require deliberate dependency/CI validation. Consumers that later require requirements format must use a generated export rather than create a second source of truth.
