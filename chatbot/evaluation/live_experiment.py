import hashlib
import json
import math
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from django.conf import settings
from langchain_core.embeddings import Embeddings

from chatbot.evaluation.baseline import evaluate_baseline, load_dataset
from chatbot.evaluation.postgres_fts import synthetic_postgres_fts
from chatbot.models import CandidateFactEmbedding
from chatbot.services.ai import (
    UNSUPPORTED_ANSWER,
    AIUnavailable,
    build_candidate_payload,
)
from chatbot.services.embeddings import content_fingerprint
from chatbot.services.retrieval import FullContextRetriever
from chatbot.services.semantic_retrieval import SemanticPgvectorRetriever

from .paid_provider import ExperimentBudget, ExperimentLimitError, ExperimentProvider


class CachedEvaluationEmbeddings(Embeddings):
    """Use already paid-for query vectors inside the LangChain retrieval chain."""

    def __init__(self, vectors):
        self.vectors = vectors

    def embed_query(self, text):
        """Return an exact precomputed vector without network calls."""
        return self.vectors[text]

    def embed_documents(self, texts):
        """Return precomputed vectors for the supplied texts."""
        return [self.embed_query(text) for text in texts]


class RecordedRetriever:
    """Replay retrieved rows so all evaluation metrics use identical contexts."""

    def __init__(self, name, rows):
        self.name = name
        self.rows = rows

    def retrieve(self, *, facts, question, history):
        """Return the previously measured, candidate-scoped retrieval output."""
        del facts
        return self.rows[(question, tuple(history))]


def _query_text(case):
    return " ".join([case["question"], *case.get("history", [])[-1:]])


def _p95(values):
    if not values:
        return None
    ordered = sorted(values)
    return round(ordered[math.ceil(0.95 * len(ordered)) - 1], 2)


def _retrieval_at_five(cases, retrieved, key_by_id):
    relevant = 0
    expected_total = 0
    reciprocal = []
    for case in cases:
        expected = set(case["expected_fact_keys"])
        if not expected:
            continue
        rows = retrieved[(case["question"], tuple(case.get("history", [])))][:5]
        keys = [key_by_id[item["id"]] for item in rows]
        relevant += len(expected.intersection(keys))
        expected_total += len(expected)
        ranks = [rank for rank, key in enumerate(keys, 1) if key in expected]
        reciprocal.append(1 / min(ranks) if ranks else 0)
    return {
        "recall_at_5": round(relevant / expected_total, 4),
        "mrr_at_5": round(sum(reciprocal) / len(reciprocal), 4),
    }


def _quality(rows):
    answered = [row for row in rows if row["provider_called"]]
    judged = [row["judge"] for row in answered if row["judge"] is not None]
    latencies = [row["response_latency_ms"] for row in answered]
    supported = [item["supported"] for item in judged]
    relevant = [item["relevant"] for item in judged]
    return {
        "generated_answers": len(answered),
        "refusals": sum(row["refused"] for row in rows),
        "citation_authorization_failures": sum(
            bool(row["invalid_citations"]) for row in rows
        ),
        "judge_scored_answers": len(judged),
        "judge_supported_rate": (
            round(sum(supported) / len(supported), 4) if supported else None
        ),
        "judge_relevance_rate": (
            round(sum(relevant) / len(relevant), 4) if relevant else None
        ),
        "mean_response_latency_ms": (
            round(sum(latencies) / len(latencies), 2) if latencies else None
        ),
        "p95_response_latency_ms": _p95(latencies),
    }


def evaluate_live(*, dataset, provider, include_judge=True):
    """Benchmark the three candidate retrievers using real model-generated data."""
    approved = {
        fact["id"]: fact
        for fact in dataset["facts"]
        if fact["verification_status"] == "verified" and fact["is_public"]
    }
    key_by_id = {fact["id"]: fact["key"] for fact in dataset["facts"]}
    index_vectors = {
        fact_id: provider.embed(fact["content"]) for fact_id, fact in approved.items()
    }
    query_vectors = {
        text: provider.embed(text)
        for text in dict.fromkeys(_query_text(case) for case in dataset["cases"])
    }

    selected = defaultdict(dict)
    retrieval_latencies = defaultdict(list)
    full_context = FullContextRetriever()
    with synthetic_postgres_fts(dataset) as adapter:
        candidate = adapter.candidate
        for row in candidate.facts.filter(
            verification_status="verified", is_public=True
        ):
            CandidateFactEmbedding.objects.create(
                fact=row,
                embedding_model=settings.AI_EMBEDDING_MODEL,
                content_sha256=content_fingerprint(row.content),
                vector=index_vectors[adapter.id_map[row.pk]],
            )
        semantic = SemanticPgvectorRetriever(
            embeddings=CachedEvaluationEmbeddings(query_vectors),
            model=settings.AI_EMBEDDING_MODEL,
        )
        retrievers = {
            "full_context": lambda case: full_context.retrieve(
                facts=dataset["facts"],
                question=case["question"],
                history=case.get("history", []),
            ),
            "postgres_fts": lambda case: adapter.retrieve(
                facts=dataset["facts"],
                question=case["question"],
                history=case.get("history", []),
            ),
            "semantic_pgvector": lambda case: [
                {**row, "id": adapter.id_map[row["id"]]}
                for row in semantic.retrieve(
                    candidate=candidate,
                    question=case["question"],
                    history=case.get("history", []),
                )
            ],
        }
        for case in dataset["cases"]:
            key = case["question"], tuple(case.get("history", []))
            for name, retrieve in retrievers.items():
                started = time.perf_counter()
                result = retrieve(case)
                retrieval_latencies[name].append((time.perf_counter() - started) * 1000)
                if any(
                    row["id"] not in approved
                    or row["content"] != approved[row["id"]]["content"]
                    for row in result
                ):
                    raise ExperimentLimitError(
                        "Retriever disclosed a private or changed fact."
                    )
                selected[name][key] = result

    reports = {}
    for name, retrieved in selected.items():
        answers = {}
        results = []
        for case in dataset["cases"]:
            key = case["question"], tuple(case.get("history", []))
            facts = retrieved[key]
            start = time.perf_counter()
            called = bool(facts)
            cited = ()
            answer = UNSUPPORTED_ANSWER
            valid = True
            if called:
                payload_bytes = len(
                    build_candidate_payload(
                        facts=facts,
                        question=case["question"],
                        history=case.get("history", []),
                    ).encode("utf-8")
                )
                if (
                    payload_bytes + settings.AI_CHAT_INPUT_OVERHEAD_BYTES
                    > settings.AI_MAX_INPUT_TOKENS
                ):
                    raise ExperimentLimitError(
                        "Production prompt context limit exceeded."
                    )
                try:
                    answer, cited = provider.answer(
                        facts=facts,
                        question=case["question"],
                        history=case.get("history", []),
                    )
                except AIUnavailable:
                    valid = False
            elapsed = (time.perf_counter() - start) * 1000
            allowed = {item["id"] for item in facts}
            invalid = sorted(set(cited) - allowed)
            if invalid:
                answer, cited = UNSUPPORTED_ANSWER, ()
            evidence = [item for item in facts if item["id"] in cited]
            judgment = None
            if include_judge and answer != UNSUPPORTED_ANSWER and valid:
                judgment = provider.judge(
                    question=case["question"],
                    answer=answer,
                    evidence=evidence,
                )
            answers[case["id"]] = {"answer": answer, "fact_ids": list(cited)}
            results.append(
                {
                    "id": case["id"],
                    "provider_called": called,
                    "valid": valid,
                    "refused": answer == UNSUPPORTED_ANSWER,
                    "invalid_citations": invalid,
                    "judge": judgment,
                    "response_latency_ms": round(elapsed, 2),
                }
            )

        scored = evaluate_baseline(
            dataset,
            input_limit_bytes=settings.AI_MAX_INPUT_TOKENS,
            overhead_bytes=settings.AI_CHAT_INPUT_OVERHEAD_BYTES,
            responses=answers,
            retriever=RecordedRetriever(name, retrieved),
        )
        scored["retrieval_at_5"] = _retrieval_at_five(
            dataset["cases"], retrieved, key_by_id
        )
        scored["response_quality"] = _quality(results)
        scored["retrieval_latency_ms"] = {
            "mean": round(
                sum(retrieval_latencies[name]) / len(retrieval_latencies[name]), 2
            ),
            "p95": _p95(retrieval_latencies[name]),
        }
        scored["answer_details"] = results
        reports[name] = scored

    return {
        "schema_version": 1,
        "run_type": "paid_openai",
        "dataset_version": dataset["version"],
        "dataset_sha256": hashlib.sha256(
            json.dumps(dataset, sort_keys=True).encode("utf-8")
        ).hexdigest(),
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "chat_model": settings.OPENAI_MODEL,
        "embedding_model": settings.AI_EMBEDDING_MODEL,
        "embedding_dimensions": settings.AI_EMBEDDING_DIMENSIONS,
        "automated_judge_enabled": include_judge,
        "provider_usage": provider.budget.summary(),
        "strategies": reports,
        "production_strategy": "full_context",
        "limitations": [
            "LLM judge results are fallible and not human-verified.",
            "Citation ID correctness does not establish claim-level truth.",
            "The 30-case synthetic dataset cannot establish statistical superiority.",
            "Provider cost is an estimate using configured token prices.",
        ],
    }


def run_paid_dataset(*, path: Path, key: str, max_usd="1.00", judge=True, client=None):
    """Execute an explicitly authorized synthetic benchmark under a cost cap."""
    dataset = load_dataset(path)
    budget = ExperimentBudget(
        max_usd=max_usd,
        input_rate=settings.AI_INPUT_USD_PER_MILLION,
        output_rate=settings.AI_OUTPUT_USD_PER_MILLION,
        embedding_rate=settings.AI_EMBEDDING_INPUT_USD_PER_MILLION,
    )
    provider = ExperimentProvider(key=key, budget=budget, client=client)
    return evaluate_live(dataset=dataset, provider=provider, include_judge=judge)
