import json
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.db import connection

from chatbot.evaluation.baseline import evaluate_baseline, load_dataset
from chatbot.evaluation.postgres_fts import synthetic_postgres_fts
from chatbot.models import CandidateFact, CandidateProfile
from chatbot.services.retrieval import (
    FullContextRetriever,
    PostgresFTSRetriever,
    retrieve_candidate_facts,
)

DATASET = (
    Path(__file__).resolve().parents[1] / "evaluation" / "data" / "synthetic_v1.json"
)
requires_postgres = pytest.mark.skipif(
    connection.vendor != "postgresql", reason="PostgreSQL FTS required"
)


@requires_postgres
@pytest.mark.django_db
def test_fts_retrieval_ranks_candidate_facts_and_enforces_visibility(
    published_candidate, verified_fact, other_user
):
    relevant = CandidateFact.objects.create(
        candidate=published_candidate,
        fact_type=CandidateFact.FactType.SKILL,
        content="PostgreSQL query optimization and index analysis.",
        verification_status=CandidateFact.VerificationStatus.VERIFIED,
        is_public=True,
    )
    hidden = CandidateFact.objects.create(
        candidate=published_candidate,
        fact_type=CandidateFact.FactType.PROJECT,
        content="PostgreSQL index analysis of confidential financial data.",
        verification_status=CandidateFact.VerificationStatus.VERIFIED,
        is_public=False,
    )
    unreviewed = CandidateFact.objects.create(
        candidate=published_candidate,
        fact_type=CandidateFact.FactType.PROJECT,
        content="PostgreSQL index benchmarking without review.",
    )
    other_candidate = CandidateProfile.objects.create(
        user=other_user, name="Unrelated Candidate"
    )
    other = CandidateFact.objects.create(
        candidate=other_candidate,
        fact_type=CandidateFact.FactType.PROJECT,
        content="PostgreSQL index benchmark at another organization.",
        verification_status=CandidateFact.VerificationStatus.VERIFIED,
        is_public=True,
    )

    retriever = PostgresFTSRetriever()
    result = retriever.retrieve(
        candidate=published_candidate,
        question="PostgreSQL index optimization?",
        history=[],
    )
    ids = [fact["id"] for fact in result]
    assert relevant.pk in ids
    assert ids == [relevant.pk]
    assert hidden.pk not in ids
    assert unreviewed.pk not in ids
    assert other.pk not in ids
    assert all(set(fact) == {"id", "fact_type", "content"} for fact in result)


@requires_postgres
@pytest.mark.django_db
def test_fts_respects_revocation_immediately(published_candidate, verified_fact):
    retriever = PostgresFTSRetriever()
    question = "Django services production"
    result = retriever.retrieve(
        candidate=published_candidate, question=question, history=[]
    )
    assert verified_fact.pk in {fact["id"] for fact in result}

    verified_fact.is_public = False
    verified_fact.save(update_fields=["is_public"])
    result = retriever.retrieve(
        candidate=published_candidate, question=question, history=[]
    )
    assert result == []


@requires_postgres
@pytest.mark.django_db
def test_fts_ignores_unsafe_query_syntax_and_bounds_terms(
    published_candidate, verified_fact
):
    retriever = PostgresFTSRetriever()
    query = "'; DROP TABLE chatbot_candidatefact; -- Django " * 100
    assert len(retriever.search_terms(question=query, history=["x" * 2000])) <= 12
    result = retriever.retrieve(
        candidate=published_candidate, question=query, history=[]
    )
    assert isinstance(result, list)
    assert CandidateFact.objects.filter(pk=verified_fact.pk).exists()
    assert retriever.retrieve(
        candidate=published_candidate, question="a ! ?", history=[]
    ) == []


@requires_postgres
@pytest.mark.django_db
def test_synthetic_fts_comparison_rolls_back_and_uses_same_facts():
    dataset = load_dataset(DATASET)
    before = (
        CandidateProfile.objects.count(),
        CandidateFact.objects.count(),
    )
    with synthetic_postgres_fts(dataset) as retriever:
        output = evaluate_baseline(
            dataset,
            input_limit_bytes=8192,
            overhead_bytes=1600,
            retriever=retriever,
        )
        assert CandidateFact.objects.count() == before[1] + 16
        assert output["strategy"] == "postgres_fts"
        assert output["metrics"]["cases"] == 30
        assert output["approved_facts"] == 13
        assert all(
            "private-plan" not in case["retrieved_fact_keys"]
            and "draft-certificate" not in case["retrieved_fact_keys"]
            and "rejected-promotion" not in case["retrieved_fact_keys"]
            for case in output["cases"]
        )

    assert (
        CandidateProfile.objects.count(),
        CandidateFact.objects.count(),
    ) == before


@requires_postgres
@pytest.mark.django_db
def test_comparison_cli_reports_two_strategies_without_provider_calls():
    before = CandidateFact.objects.count()
    output = StringIO()
    with patch("chatbot.services.ai.OpenAI") as provider:
        call_command(
            "evaluate_candidate_agent",
            strategy="compare",
            json=True,
            stdout=output,
        )
    provider.assert_not_called()
    report = json.loads(output.getvalue())
    assert set(report["strategies"]) == {"full_context", "postgres_fts"}
    assert report["strategies"]["full_context"]["metrics"]["retrieval_recall"] == 1.0
    assert report["strategies"]["postgres_fts"]["metrics"]["cases"] == 30
    assert report["strategies"]["postgres_fts"]["metrics"]["over_budget_cases"] == 0
    assert CandidateFact.objects.count() == before


@requires_postgres
@pytest.mark.django_db
def test_fts_response_dataset_stable_ids_and_query_history():
    dataset = load_dataset(DATASET)
    with synthetic_postgres_fts(dataset) as retriever:
        result = retriever.retrieve(
            facts=dataset["facts"],
            question="What were the PostgreSQL query improvements?",
            history=["What database optimization was done?"],
        )
    assert all(fact["id"] in range(101, 114) for fact in result)
    assert result
    assert any("PostgreSQL" in fact["content"] for fact in result)


@pytest.mark.django_db
def test_full_context_remains_production_default(
    published_candidate, verified_fact
):
    selected = retrieve_candidate_facts(
        candidate=published_candidate,
        question="Which Django work?",
        history=["Previously discussed databases"],
    )
    expected = FullContextRetriever().retrieve(
        facts=[
            {
                "id": verified_fact.id,
                "fact_type": verified_fact.fact_type,
                "content": verified_fact.content,
                "verification_status": "verified",
                "is_public": True,
            }
        ],
        question="unused",
        history=[],
    )
    assert selected == expected
