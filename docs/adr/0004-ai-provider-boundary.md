# ADR 0004: Authorization-first AI gateway with verified-fact context

## Status

Accepted — 2026-09-01

## Context

Views previously invoked process-global LangChain chains directly, made one call per resume chunk, had no usage record, and mixed untrusted resume/question content into prompts. Provider output could overwrite source truth and was inserted into the DOM as HTML.

## Decision

`chatbot.services.ai` is the single OpenAI boundary for candidate chat. It authorizes the identity/candidate first, selects only verified facts, records a minimal `AIUsageEvent`, makes one bounded provider call, and returns standardized errors/metadata. Views persist generated answers only as conversation messages. Browser code renders all content as text.

The service is intentionally thin: full rate limits, quotas, budget reservation, pricing, RAG, tools, and orchestration are deferred.

## Alternatives considered

- Improve the legacy LangChain chunk loop: invests in architecture scheduled for replacement and retains cost fan-out.
- Build a multi-provider interface hierarchy: speculative with one provider.
- Disable chat entirely: safest, but loses a useful end-to-end boundary and portfolio behavior.

## Consequences and trade-offs

Provider mocking and the “deny before paid call” invariant are straightforward. Usage metadata prepares cost governance without pretending to be billing. Free-form verified facts are still a limited grounding source; Phase 2 must add evaluations, scope controls, and richer structured evidence before expanding access.
