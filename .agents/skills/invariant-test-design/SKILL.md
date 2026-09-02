---
name: invariant-test-design
description: Design or review ResumeBot tests around domain, isolation, verified-fact, upload, and paid-provider invariants. Use when behavior changes or when a regression test must prove an outcome rather than mirror implementation.
---

# Invariant Test Design

State the invariant in actor/action/outcome terms, then choose the narrowest test boundary that can prove it.

- Use model tests for constraints and transitions.
- Use request tests for authentication, object selection, privacy, HTTP semantics, and rendering.
- Use a fake or patch at `chatbot.services.ai.invoke_candidate_chat` for provider behavior.
- Assert exact absence of provider calls for denied, invalid, over-scope, or unverified-data paths.
- Use synthetic documents and PII. Exercise signatures, size/type rejection, private storage, and managed failure state for upload changes.
- Assert what an unauthorized response does not contain when testing leakage.

Classify old characterization behavior explicitly as a preserved invariant or intentional legacy replacement. Do not weaken an assertion merely to fit new code. Avoid testing framework internals, private helper wording, or superficial coverage. Add PostgreSQL execution when the behavior depends on database constraints, transactions, locking, indexes, JSON, or PostgreSQL queries.
