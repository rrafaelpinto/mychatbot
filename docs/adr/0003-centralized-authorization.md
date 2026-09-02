# ADR 0003: Centralized server-side authorization policies

## Status

Accepted — 2026-09-01

## Context

Legacy views applied some login decorators and owner filters, but direct slug access ignored privacy and activation flags. Future views, APIs, tasks, and AI services need the same answers to ownership, publication, interaction, and conversation-access questions.

## Decision

Keep reusable, deterministic policy functions in `chatbot.policies` and public queryset rules on the domain manager. Views use constrained querysets to conceal unpublished objects. The AI service repeats interaction authorization before provider invocation. Templates may hide actions for usability but never grant permission.

## Alternatives considered

- View-only conditions: locally simple, but drift across entry points.
- A third-party policy framework: potentially powerful, but unnecessary for the current small rule set.
- Prompt-based authorization: not a security boundary and cannot prevent data/provider access.

## Consequences and trade-offs

Rules are independently testable and usable from future DRF/background entry points. Developers must call the appropriate policy at application boundaries; negative invariant tests guard omissions. If the rule set becomes relationship-heavy, a dedicated policy library can be reconsidered with evidence.
