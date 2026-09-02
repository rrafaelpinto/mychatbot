# ADR 0002: Clean schema with separated lifecycle, publication, and source truth

## Status

Accepted — 2026-09-01

## Context

No production database or users exist. The legacy `Candidate` combined nullable ownership, contact data, a mutable resume blob, publication, and an unused activation boolean. LLM-formatted output could overwrite the only candidate source.

## Decision

Replace the migration history with one ResumeBot 2.0 initial migration. `CandidateProfile` has mandatory user ownership, explicit `PENDING_APPROVAL`, `ACTIVE`, and `SUSPENDED` lifecycle states, plus separate `DRAFT`/`PUBLISHED` publication state. A database constraint permits publication only for active candidates.

`CandidateDocument` privately stores raw sources and unverified extraction. `CandidateFact` stores reviewable professional facts with verification state and optional document provenance. Conversation messages and AI output never become candidate facts automatically.

## Alternatives considered

- Migrate legacy booleans/blob incrementally: unnecessary compatibility work for nonexistent data and preserves ambiguous semantics.
- Model every resume entity now: stronger structure eventually, but speculative before extraction/review workflows exist.
- Keep only free-form resume text: simple, but violates the verified-source invariant.

## Consequences and trade-offs

The schema clearly expresses the initial trust boundary and can grow toward explicit Experience/Education/Project entities. `CandidateFact` is intentionally limited Phase 1 scaffolding, not a permanent excuse for an unconstrained entity-attribute-value model. The clean migration cannot upgrade an old database, which is acceptable because none exists.
