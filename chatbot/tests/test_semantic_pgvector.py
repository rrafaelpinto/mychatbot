import json
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.conf import settings
from django.core.management import call_command

from chatbot.evaluation.baseline import evaluate_baseline, load_dataset
from chatbot.evaluation.semantic_pgvector import synthetic_semantic_pgvector
from chatbot.models import (
    AIProjectBudget,
    AIUsageEvent,
    CandidateFact,
    CandidateFactEmbedding,
    CandidateProfile,
)
from chatbot.services.ai_budget import reservation_micro_usd
from chatbot.services.embeddings import (
    BudgetedOpenAIEmbeddings,
    DeterministicTestEmbeddings,
    EmbeddingUnavailable,
    content_fingerprint,
)
from chatbot.services.semantic_index import index_candidate_public_facts
from chatbot.services.semantic_retrieval import SemanticPgvectorRetriever

DATASET = Path(__file__).resolve().parents[1] / "evaluation" / "data" / "synthetic_v1.json"


@pytest.mark.django_db
def test_semantic_query_filters_private_foreign_and_stale_facts(
    published_candidate, verified_fact, other_user
):
    embedder = DeterministicTestEmbeddings()
    other = CandidateProfile.objects.create(user=other_user, name="Other candidate")
    candidates = [
        (verified_fact, True),
        (
            CandidateFact.objects.create(
                candidate=published_candidate,
                fact_type=CandidateFact.FactType.SKILL,
                content="Private Django API work",
                verification_status=CandidateFact.VerificationStatus.VERIFIED,
                is_public=False,
            ),
            True,
        ),
        (
            CandidateFact.objects.create(
                candidate=other,
                fact_type=CandidateFact.FactType.SKILL,
                content="Django APIs for another account",
                verification_status=CandidateFact.VerificationStatus.VERIFIED,
                is_public=True,
            ),
            True,
        ),
        (
            CandidateFact.objects.create(
                candidate=published_candidate,
                fact_type=CandidateFact.FactType.SKILL,
                content="Django experimental results",
                verification_status=CandidateFact.VerificationStatus.VERIFIED,
                is_public=True,
            ),
            False,
        ),
    ]
    for fact, fresh in candidates:
        CandidateFactEmbedding.objects.create(
            fact=fact,
            embedding_model=settings.AI_EMBEDDING_MODEL,
            content_sha256=(
                content_fingerprint(fact.content)
                if fresh
                else content_fingerprint("old content")
            ),
            vector=embedder.embed_query(fact.content),
        )

    retriever = SemanticPgvectorRetriever(
        embeddings=embedder, model=settings.AI_EMBEDDING_MODEL
    )
    result = retriever.retrieve(
        candidate=published_candidate, question="Django backend services", history=[]
    )
    assert [item["id"] for item in result] == [verified_fact.pk]
    assert all(set(item) == {"id", "fact_type", "content"} for item in result)


@pytest.mark.django_db
def test_semantic_revocation_and_text_edit_fail_closed(
    published_candidate, verified_fact
):
    embedder = DeterministicTestEmbeddings()
    CandidateFactEmbedding.objects.create(
        fact=verified_fact,
        embedding_model=settings.AI_EMBEDDING_MODEL,
        content_sha256=content_fingerprint(verified_fact.content),
        vector=embedder.embed_query(verified_fact.content),
    )
    retriever = SemanticPgvectorRetriever(
        embeddings=embedder, model=settings.AI_EMBEDDING_MODEL
    )
    def query():
        return retriever.retrieve(
            candidate=published_candidate, question="Django work", history=[]
        )
    assert any(x["id"] == verified_fact.pk for x in query())
    verified_fact.content = "Different approved project entirely."
    verified_fact.save(update_fields=["content"])
    assert query() == []
    verified_fact.is_public = False
    verified_fact.save(update_fields=["is_public"])
    assert query() == []


@pytest.mark.django_db
def test_semantic_empty_index_returns_nothing(published_candidate, verified_fact):
    result = SemanticPgvectorRetriever(
        embeddings=DeterministicTestEmbeddings(),
        model=settings.AI_EMBEDDING_MODEL,
    ).retrieve(candidate=published_candidate, question="Django", history=[])
    assert result == []


@pytest.mark.django_db
def test_semantic_synthetic_benchmark_uses_real_pgvector_and_rolls_back():
    dataset = load_dataset(DATASET)
    before = CandidateFactEmbedding.objects.count()
    with synthetic_semantic_pgvector(dataset) as retriever:
        report = evaluate_baseline(
            dataset, input_limit_bytes=8192, overhead_bytes=1600,
            retriever=retriever
        )
        assert report["strategy"] == "semantic_pgvector"
        assert report["metrics"]["cases"] == 30
        assert report["approved_facts"] == 13
        assert CandidateFactEmbedding.objects.count() == before + 13
        assert all(
            not {"private-plan", "draft-certificate", "rejected-promotion"}
            & set(row["retrieved_fact_keys"])
            for row in report["cases"]
        )
    assert CandidateFactEmbedding.objects.count() == before


@pytest.mark.django_db
def test_three_way_cli_is_offline_and_returns_same_case_set():
    output = StringIO()
    with patch("chatbot.services.embeddings.OpenAI") as provider:
        call_command("evaluate_candidate_agent", strategy="compare", json=True, stdout=output)
    provider.assert_not_called()
    result = json.loads(output.getvalue())
    assert set(result["strategies"]) == {
        "full_context", "postgres_fts", "semantic_pgvector"
    }
    assert all(row["metrics"]["cases"] == 30 for row in result["strategies"].values())
    assert "synthetic" not in str(result.get("strategy", "")).lower()
    assert "not a real" in result["semantic_embedding_note"]


@pytest.mark.django_db
def test_index_command_is_opt_in_and_reuses_existing_vector(
    settings, published_candidate, verified_fact
):
    settings.AI_ENABLED = True
    settings.AI_OPERATION_POLICIES = {
        **settings.AI_OPERATION_POLICIES,
        "embedding_index": True,
    }
    settings.OPENAI_API_KEY = "test-key"
    embedded = DeterministicTestEmbeddings().embed_query(verified_fact.content)
    with patch.object(
        BudgetedOpenAIEmbeddings, "embed_query", return_value=embedded
    ) as provider:
        count = index_candidate_public_facts(
            candidate=published_candidate,
            initiated_by=published_candidate.user,
        )
        again = index_candidate_public_facts(
            candidate=published_candidate,
            initiated_by=published_candidate.user,
        )
    assert (count, again) == (1, 0)
    provider.assert_called_once()
    assert CandidateFactEmbedding.objects.count() == 1


@pytest.mark.django_db
def test_index_rejects_unauthorized_identity_and_no_paid_call(
    published_candidate, verified_fact, other_user
):
    with patch.object(BudgetedOpenAIEmbeddings, "embed_query") as provider:
        with pytest.raises(EmbeddingUnavailable, match="Not authorized"):
            index_candidate_public_facts(
                candidate=published_candidate,
                initiated_by=other_user,
            )
    provider.assert_not_called()


@pytest.mark.django_db
def test_embedding_budget_reservation_and_real_usage_settlement(
    settings, published_candidate, verified_fact
):
    settings.AI_ENABLED = True
    settings.AI_OPERATION_POLICIES = {
        **settings.AI_OPERATION_POLICIES,
        "embedding_index": True,
    }
    settings.OPENAI_API_KEY = "test-only-key"
    fake_response = SimpleNamespace(
        data=[SimpleNamespace(embedding=[0.1] * 256)],
        usage=SimpleNamespace(total_tokens=30),
        id="test-embedding-request",
    )
    with patch("chatbot.services.embeddings.OpenAI") as openai:
        openai.return_value.embeddings.create.return_value = fake_response
        embedding = BudgetedOpenAIEmbeddings(
            candidate=published_candidate,
            initiated_by=published_candidate.user,
            operation=AIUsageEvent.Operation.EMBEDDING_INDEX,
        ).embed_query("Django REST APIs")
    assert len(embedding) == 256
    usage = AIUsageEvent.objects.get()
    assert usage.model == "text-embedding-3-small"
    assert usage.input_tokens == 30
    assert usage.output_tokens == 0
    assert usage.settled_at is not None
    assert usage.actual_micro_usd is not None
    assert usage.actual_micro_usd <= usage.reserved_micro_usd
    assert AIProjectBudget.objects.count() == 1
    assert openai.return_value.embeddings.create.call_args.kwargs["dimensions"] == 256


@pytest.mark.django_db
def test_embedding_is_disabled_before_reservation(settings, published_candidate):
    settings.AI_ENABLED = True
    settings.AI_OPERATION_POLICIES = {
        **settings.AI_OPERATION_POLICIES,
        "embedding_query": False,
    }
    settings.OPENAI_API_KEY = "test-only-key"
    with patch("chatbot.services.embeddings.OpenAI") as client:
        with pytest.raises(EmbeddingUnavailable, match="disabled"):
            BudgetedOpenAIEmbeddings(
                candidate=published_candidate,
                initiated_by=published_candidate.user,
                operation=AIUsageEvent.Operation.EMBEDDING_QUERY,
            ).embed_query("Django")
    client.assert_not_called()
    assert not AIUsageEvent.objects.exists()


@pytest.mark.django_db
def test_invalid_provider_vector_preserves_budget_and_fails(settings, published_candidate):
    settings.AI_ENABLED = True
    settings.AI_OPERATION_POLICIES = {
        **settings.AI_OPERATION_POLICIES,
        "embedding_query": True,
    }
    settings.OPENAI_API_KEY = "test-only-key"
    response = SimpleNamespace(
        data=[SimpleNamespace(embedding=[float("nan")] * 256)],
        usage=SimpleNamespace(total_tokens=10),
        id="invalid",
    )
    with patch("chatbot.services.embeddings.OpenAI") as provider:
        provider.return_value.embeddings.create.return_value = response
        with pytest.raises(EmbeddingUnavailable):
            BudgetedOpenAIEmbeddings(
                candidate=published_candidate,
                initiated_by=published_candidate.user,
                operation=AIUsageEvent.Operation.EMBEDDING_QUERY,
            ).embed_query("Django")
    assert AIUsageEvent.objects.get().status == AIUsageEvent.Status.FAILED


def test_embedding_budget_uses_configured_input_price(settings):
    settings.AI_EMBEDDING_INPUT_USD_PER_MILLION = "0.02"
    assert reservation_micro_usd("text-embedding-3-small") == 41


def test_offline_test_embeddings_are_deterministic_not_provider_backed():
    embedder = DeterministicTestEmbeddings()
    first = embedder.embed_query("Django REST Python")
    assert len(first) == 256
    assert first == embedder.embed_query("Django REST Python")
    assert first != embedder.embed_query("React TypeScript")
