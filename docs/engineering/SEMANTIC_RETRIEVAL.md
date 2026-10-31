# Semantic Retrieval with LangChain and pgvector

This milestone adds the third Candidate Agent retrieval strategy, but
**full_context remains the live production default**. No new paid activity
is triggered by public chat, by uploads or by CI.

## Index lifecycle

A `CandidateFactEmbedding` row links a 256-dimensional vector to an
individual fact, model name and SHA-256 of the original fact content.
Only explicitly verified, public, candidate-owned facts can be indexed.
When a fact changes or is unpublished, semantic retrieval rejects its
stored vector even before any reindexing.

Use a PostgreSQL installation with the `vector` extension enabled and
the migrations applied:

```sh
uv run python manage.py migrate
```

The initial experiment uses **exact cosine-distance search**. The
dataset is small, so an approximate HNSW index is intentionally deferred
until profiling shows it is necessary.

## Paid indexing and preview (explicit opt-in)

Set `AI_ENABLED=true`, the appropriate positive project budgets,
`OPENAI_API_KEY`, and the individual operation flags:

```sh
AI_SEMANTIC_INDEX_ENABLED=true
AI_SEMANTIC_QUERY_ENABLED=true
```

Run the owner-scoped administrative operations:

```sh
uv run python manage.py index_candidate_embeddings --candidate candidate-slug --limit 10
uv run python manage.py preview_semantic_retrieval --candidate candidate-slug --question "Describe Django projects"
```

Indexing skips current vectors, uses a limited batch size and rechecks
fact visibility/content under a row lock before persistence. Both commands
use a LangChain Embeddings adapter backed by the OpenAI SDK with per-call
quota, project-budget reservation and usage settlement. The configured
embedding model is `text-embedding-3-small` with 256 dimensions.
The input cost estimate defaults to $0.02 per million tokens; validate
the current provider price before enabling these operations.
The reservation bound is 2,048 input tokens and input is limited to
2,048 UTF-8 bytes. Failed/unknown-usage calls retain their reserve.

The query preview is a trusted management command, **not a public
endpoint**. Public embedding query costs would require explicit further
evaluation before enabling this strategy in live chat.

## Three-way offline comparison

```sh
uv run python manage.py evaluate_candidate_agent --strategy compare --json
```

The benchmark constructs synthetic records in a transaction and rolls
back all inserts after completion. It uses a LangChain runnable pipeline,
real pgvector cosine-distance ORM lookup and **deterministic test vectors**.
The test embedder hashes lexical tokens locally, without OpenAI calls.
Therefore its recall and precision **must not be represented as the
quality of a real semantic model**. These numbers validate SQL filtering,
dimensions, mapping, ordering, consistent metrics and evaluation wiring.

The existing full-context and PostgreSQL FTS results remain
reproducible. A meaningful semantic *quality* comparison will require
a controlled, explicitly funded evaluation with real embeddings,
representative candidate facts, response-level assessment, and
per-strategy latency and token-cost measurements before production
selection.
