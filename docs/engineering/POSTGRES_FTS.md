# PostgreSQL Full-Text Retrieval Benchmark

The Candidate Agent's production retrieval remains **full_context**. This
change provides a separately evaluated PostgreSQL full-text candidate fact
retriever without enabling it for public requests.

## Compare the strategies

Requires a configured local PostgreSQL database and applied migrations.

```sh
uv run python manage.py migrate
uv run python manage.py evaluate_candidate_agent --strategy compare --json
uv run python manage.py evaluate_candidate_agent --strategy postgres_fts --fail-on-overflow
```

The comparison uses the **same 30-case synthetic dataset**, payload serializer,
approval rules, per-case gold fact IDs, and evaluation metrics as the
full-context baseline. An isolated transaction creates synthetic candidate and
fact rows, runs the actual ORM retrieval against PostgreSQL, and rolls back
all writes, including when evaluation fails. This is not read-only at the
database statement level: use a local/CI database, **not production**, for
evaluation. No real candidate data or external AI provider is accessed.

The PostgreSQL retriever uses `SearchVector`, `SearchQuery` with plain
lexemes, and `SearchRank` sorted deterministically. A partial functional
GIN index covers only explicitly verified, public facts. It returns up to
five ranked facts and restricts all results to the requested candidate;
private, pending, rejected, and revoked content cannot appear.

The lexical query is bounded to 12 unique terms from the current question
and the last contextual question, with generic stopwords excluded. Terms
are passed as ORM parameters, never interpolated as SQL or raw `tsquery`.
The `english` text-search dictionary is intentional because the synthetic
candidate corpus and demonstration are in English.

## Interpretation and limitations

Use these measures to compare retrieval, not answer generation:

- `retrieval_recall`: share of all expected evidence references recovered.
- `retrieval_precision`: useful evidence references among all retrieved
  references, aggregated over all 30 cases.
- `complete_evidence_case_rate`: cases with all annotated evidence returned.
- `mean_payload_bytes`: mean actual serialized prompt payload size.
- `over_budget_cases`: conservative prompt size guard failures.

An empty lexical result is **not** equivalent to an unsupported professional
claim. Synonyms and paraphrases may have evidence the keyword query missed.
LLM response correctness, model latency and real token expenditure are not
measured by this offline comparison. No fallback or change of production
strategy is introduced. The semantic retrieval comparison with pgvector will
use this same benchmark before a production selection is made.

The index improves query planning for larger public corpora, but the tiny
synthetic dataset does not establish production query latency or index ROI.
