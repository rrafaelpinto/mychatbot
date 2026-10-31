# Paid Candidate Agent Evaluation

This experiment is independent from the public demo and **never runs in CI**.
Production continues to use `full_context`.

## Scope

Run the **versioned, fictional** 30-question corpus against three strategies:

1. Full-context with all verified public facts.
2. PostgreSQL FTS with the existing lexical ranker.
3. LangChain and pgvector with actual `text-embedding-3-small` vectors.

The experiment generates 13 corpus embeddings and up to 30 query embeddings,
then up to 90 `gpt-4o-mini` answers. Each strategy uses the exact same
production system/user messages and parser (unless no facts are retrieved, in
which case it refuses without a provider call). An optional separate
model-based judge checks whether each non-refusal is supported by its cited
facts and relevant to the question. The judge is **not ground truth**.

## Controlled paid execution

Use an isolated local or dedicated evaluation PostgreSQL database with the
`vector` extension and migrations, **never the production database**. The
benchmark inserts synthetic records inside a transaction and rolls them back.

```sh
uv run python manage.py migrate
AI_EVALUATION_PAID_ENABLED=true uv run python manage.py evaluate_candidate_agent_live \\
  --allow-paid --max-usd 1.00 --output .local/evaluation-paid.json
```

`OPENAI_API_KEY` must already exist in the secure environment. No key, real
candidate content, private documents or raw credentials belong in the
repository or report. The command requires both a feature flag and an
explicit `--allow-paid`, and refuses to overwrite existing reports.
`--skip-judge` is available for an initial, less expensive run.

**Cost cap:** at most US$1.00 of *estimated token-based provider spend*
per run, using the project-configured provider prices. The runner reserves
a pessimistic bound before every individual API request, reconciles the
reported token usage, never retries a provider request automatically, and
stops when another request would exceed the cap. A failed request without
usage data retains its reservation. Actual provider invoices can differ
from local estimates if prices change or accounting differs.

This cap applies to the experiment process and is **not** a substitute for
an external OpenAI project spending limit. Set an OpenAI project limit too,
and verify current model pricing before executing. The existing AI
application budget and public session quotas remain untouched because no
production candidate or AI usage records are created.

## Metrics and interpretation

The JSON report records the dataset SHA-256, provider models, retrieval
metrics, recall@5, MRR@5, prompt bytes, optional citation/refusal results,
average/p95 response and retrieval latencies, total token usage and
estimated dollars, separately identifying embedding and chat/judge calls.

Retrieval recall over all returned facts is distinct from `recall_at_5`:
the full-context strategy currently sends all 13 approved facts, while
ranked FTS/pgvector return at most five. Both numbers are provided to avoid
mistaking full-context coverage for ranked retrieval performance.

The response evaluation combines deterministic checks (gold fact ID
overlap, unauthorized citations and refusal mode) with optional fallible
automated judgment on the *content* of non-refusal answers. Do not
interpret a citation match as proof of semantic correctness, or model
judgments as human annotation. Report missing/uncertain evaluations, do
not silently treat them as successes.

## Production decision

No strategy is enabled automatically. Prefer the simpler full-context
implementation for the small portfolio corpus unless another strategy
demonstrably preserves answer grounding and recall, reduces measured
cost or latency, and has acceptable operational overhead.

The experiment can only be described as **real** if its paid command
successfully executes with a configured provider key and returns a report.
CI's existing deterministic test-vector comparison is an integration
test, not real embedding quality evidence.
