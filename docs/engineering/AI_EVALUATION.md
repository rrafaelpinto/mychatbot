# Candidate Agent Evaluation: Full-Context Baseline

Phase 3 uses a versioned, **synthetic** corpus to compare alternative retrieval
strategies without checking real candidate documents into source control.

## Reproduce the baseline

```sh
uv run python manage.py evaluate_candidate_agent --fail-on-overflow
uv run python manage.py evaluate_candidate_agent --json
uv run python manage.py evaluate_candidate_agent \\
  --output .local/full-context-baseline.json
```

The default dataset is
`chatbot/evaluation/data/synthetic_v1.json`: 16 fictional professional
facts, including three excluded private/unreviewed/rejected entries, and
30 annotated cases covering factual questions, unsupported requests,
multi-turn follow-ups and adversarial instructions.

The command is **offline**. It never calls OpenAI, creates usage events,
consumes an AI budget or reads an actual candidate's private corpus.
Use it to compare retrieval strategies in CI and local development.

## Interpretation

The current production strategy sends all verified, explicitly public
facts to the Candidate Agent. The baseline uses that same full-context
selection and the same JSON payload serializer.

- `retrieval_recall`: relevant expected fact keys included / all expected
  keys (micro-averaged). A value of 1.0 is expected when every approved
  fact fits in full context; this is not model accuracy.
- `retrieval_precision`: expected relevant fact keys included / all facts
  delivered to the model, across **all cases**. The denominator includes
  contexts for unanswerable questions, exposing full-context noise.
- `complete_evidence_case_rate`: share of cases with every required
  evidence key in the retrieved context.
- `over_budget_cases`: serialized payload UTF-8 byte length plus the
  configured conservative overhead exceeds `AI_MAX_INPUT_TOKENS`.
- `approx_input_tokens`: a byte-length / 4 heuristic, **not** exact tokenizer
  output or billable OpenAI usage. No actual latency or monetary cost is
  measured by this offline evaluation.

The byte-based capacity check intentionally mirrors the current
application's conservative admission guard. It is not a token-count
guarantee. The full-context baseline makes no claim about semantic
grounding, response correctness or prompt-injection resistance.

## Offline model-response replay

A separately captured model-output file can be scored without any paid
API calls:

```sh
uv run python manage.py evaluate_candidate_agent \\
  --responses .local/model-responses.json --json
```

Response format, with synthetic IDs:

```json
{
  "version": 1,
  "responses": [
    {
      "id": "A01",
      "output": {
        "answer": "I built a Django REST API.",
        "fact_ids": [101]
      }
    }
  ]
}
```

The runner uses the production JSON answer parser. It reports response
format errors, refusal behavior, citation overlap against annotated
evidence IDs and references to IDs not provided in the retrieved context.
The resulting measures are *reference-level checks only*: the fact that
an answer cites an expected ID does not establish semantic entailment.

For meaningful comparisons, capture answers for the **same versioned
dataset**, model and prompt settings. Never commit response artifacts
containing real candidate information. The optional paid model
evaluation and LLM-as-judge belong in a later milestone with explicit
budget controls; CI does not call a paid provider.

## Retrieval comparison

PostgreSQL FTS is now benchmarkable with the same dataset using
`evaluate_candidate_agent --strategy compare`. See
[PostgreSQL FTS evaluation](POSTGRES_FTS.md) for index, transaction,
privacy and interpretation details.

LangChain + pgvector remains the next strategy to benchmark. Measure
real latency and provider token costs only when explicitly budgeted and
authorized before selecting a production strategy.

## LangChain + pgvector experiment

The offline three-way comparison also exercises a pgvector cosine-distance
retriever through LangChain runnables. Its deterministic test vectors are
not genuine semantic embeddings, so **do not compare its recall directly as
real semantic model quality**. See [semantic retrieval](SEMANTIC_RETRIEVAL.md)
for configuration and evaluation limitations.
