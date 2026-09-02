---
name: django-authorization-review
description: Review ResumeBot Django changes for ownership, publication, conversation, private-data, and paid-AI authorization boundaries. Use when a task adds or changes a view, policy, queryset, API, task, or AI operation that selects candidate-scoped data.
---

# Django Authorization Review

Identify the protected resource, every actor, and every entry point before judging individual decorators.

For each affected operation:

1. Trace object selection and confirm it is owner/publication scoped before private fields are loaded or returned.
2. Find the reusable rule in `chatbot.policies`; add or change one only when the domain question is genuinely new.
3. Keep account activation, candidate status, publication, and AI eligibility distinct.
4. Confirm templates only reflect permission and do not grant it.
5. For AI paths, verify denial happens before usage creation or provider invocation.
6. Add negative request tests for another user, unpublished state, suspended state, and direct identifiers/slugs relevant to the change.

Prefer a concealed 404 when an arbitrary caller should not learn that a candidate-scoped object exists. Staff access must be explicit, not inferred from frontend navigation. Flag any public exposure of account email, phone, source documents, unverified facts, or other fields without an explicit visibility decision.
