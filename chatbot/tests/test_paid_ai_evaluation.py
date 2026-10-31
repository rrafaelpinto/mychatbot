import json
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from chatbot.evaluation.baseline import load_dataset
from chatbot.evaluation.live_experiment import evaluate_live, run_paid_dataset
from chatbot.evaluation.paid_provider import (
    ExperimentBudget,
    ExperimentLimitError,
    ExperimentProvider,
)
from chatbot.models import CandidateFact, CandidateFactEmbedding, CandidateProfile
from chatbot.services.ai import UNSUPPORTED_ANSWER, candidate_chat_messages
from chatbot.services.embeddings import DeterministicTestEmbeddings

DATASET = Path(__file__).resolve().parents[1] / "evaluation" / "data" / "synthetic_v1.json"


def budget(limit="1.00"):
    return ExperimentBudget(
        max_usd=limit,
        input_rate="0.15",
        output_rate="0.60",
        embedding_rate="0.02",
    )


def usage(prompt=20, completion=10):
    return SimpleNamespace(prompt_tokens=prompt, completion_tokens=completion)


class FakeProvider:
    def __init__(self):
        self.budget = budget()
        self.embedder = DeterministicTestEmbeddings()
        self.answer_count = 0
        self.judge_count = 0

    def embed(self, text):
        return self.embedder.embed_query(text)

    def answer(self, *, facts, question, history):
        self.answer_count += 1
        return f"According to the candidate facts: {facts[0]['content']}", (
            facts[0]["id"],
        )

    def judge(self, *, question, answer, evidence):
        self.judge_count += 1
        return {"supported": bool(evidence), "relevant": bool(question)}


def test_budget_refuses_more_than_approved_one_usd():
    for value in ("1.01", "5", "0", "-0.5"):
        with pytest.raises(ExperimentLimitError, match="at most"):
            budget(value)


def test_budget_checks_cost_before_invoking_provider():
    guard = budget("0.000001")
    called = []
    with pytest.raises(ExperimentLimitError, match="exhausted"):
        guard.call(
            kind="chat",
            prompt="Hello",
            max_output=500,
            execute=lambda: called.append(True),
        )
    assert called == []


def test_budget_uses_actual_provider_usage_and_records_latency():
    guard = budget()
    result = guard.call(
        kind="chat",
        prompt="What projects?",
        max_output=500,
        execute=lambda: SimpleNamespace(usage=usage()),
    )
    assert result.usage.prompt_tokens == 20
    assert len(guard.records) == 1
    assert guard.records[0].output_tokens == 10
    assert guard.summary()["input_tokens"] == 20
    assert guard.summary()["estimated_spend_usd"] == "0.000009"
    assert guard.records[0].latency_ms >= 0


def test_unknown_provider_error_keeps_the_spending_reservation():
    guard = budget()

    def fail():
        raise RuntimeError("Provider timeout")

    with pytest.raises(RuntimeError, match="timeout"):
        guard.call(
            kind="embedding", prompt="Some synthetic fact", max_output=0,
            execute=fail
        )
    assert guard.spent > Decimal("0")
    assert guard.records == []


def test_missing_usage_preserves_reserved_cost():
    guard = budget()
    with pytest.raises(ExperimentLimitError, match="token usage"):
        guard.call(
            kind="chat",
            prompt="Some question",
            max_output=500,
            execute=lambda: SimpleNamespace(usage=None),
        )
    assert guard.spent > Decimal("0")
    assert guard.records == []


def test_same_production_prompt_is_reused_for_paid_evaluation():
    facts = [{"id": 101, "fact_type": "skill", "content": "Django"}]
    messages = candidate_chat_messages(
        facts=facts, question="What framework?", history=["What projects?"]
    )
    assert isinstance(messages, list)
    assert [message["role"] for message in messages] == ["system", "user"]
    payload = json.loads(messages[1]["content"])
    assert payload["verified_candidate_facts"] == facts
    assert payload["previous_recruiter_questions"] == ["What projects?"]


def test_provider_parses_real_response_contract_without_network(settings):
    settings.OPENAI_API_KEY = "test-key"
    completion = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content='{"answer":"I use Django.","fact_ids":[101]}'
                )
            )
        ],
        usage=usage(),
    )
    client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=lambda **kwargs: completion)
        )
    )
    provider = ExperimentProvider(key="test-key", budget=budget(), client=client)
    answer, ids = provider.answer(
        facts=[{"id": 101, "fact_type": "skill", "content": "Django"}],
        question="Framework?",
        history=[],
    )
    assert answer == "I use Django."
    assert ids == (101,)
    assert provider.budget.summary()["by_operation"]["chat"]["calls"] == 1


def test_judge_schema_rejects_non_boolean_outputs():
    completion = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content='{"supported":"yes","relevant":true}'
                )
            )
        ],
        usage=usage(),
    )
    client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=lambda **kwargs: completion)
        )
    )
    provider = ExperimentProvider(key="fake-key", budget=budget(), client=client)
    result = provider.judge(
        question="What work?", answer="I built APIs.", evidence=[]
    )
    assert result is None
    assert provider.budget.summary()["by_operation"]["judge"]["calls"] == 1


@pytest.mark.django_db
def test_mocked_three_way_live_pipeline_uses_pgvector_and_leaks_nothing():
    dataset = load_dataset(DATASET)
    provider = FakeProvider()
    before = (
        CandidateProfile.objects.count(),
        CandidateFact.objects.count(),
        CandidateFactEmbedding.objects.count(),
    )
    report = evaluate_live(dataset=dataset, provider=provider, include_judge=True)
    assert report["run_type"] == "paid_openai"
    assert set(report["strategies"]) == {
        "full_context", "postgres_fts", "semantic_pgvector"
    }
    assert provider.answer_count > 0
    assert provider.judge_count == provider.answer_count
    assert report["automated_judge_enabled"] is True
    assert report["production_strategy"] == "full_context"
    for name, scored in report["strategies"].items():
        assert scored["strategy"] == name
        assert scored["metrics"]["cases"] == 30
        assert 0 <= scored["retrieval_at_5"]["recall_at_5"] <= 1
        assert 0 <= scored["retrieval_at_5"]["mrr_at_5"] <= 1
        assert scored["response_quality"]["citation_authorization_failures"] == 0
        assert all(
            not {"private-plan", "draft-certificate", "rejected-promotion"}
            & set(row["retrieved_fact_keys"])
            for row in scored["cases"]
        )
    assert (
        CandidateProfile.objects.count(),
        CandidateFact.objects.count(),
        CandidateFactEmbedding.objects.count(),
    ) == before


@pytest.mark.django_db
def test_mocked_evaluation_can_skip_fallible_llm_judge():
    provider = FakeProvider()
    report = evaluate_live(
        dataset=load_dataset(DATASET), provider=provider, include_judge=False
    )
    assert provider.judge_count == 0
    assert report["automated_judge_enabled"] is False
    assert all(
        row["response_quality"]["judge_scored_answers"] == 0
        for row in report["strategies"].values()
    )


@pytest.mark.django_db
def test_paid_command_requires_explicit_double_opt_in(settings, tmp_path):
    output = tmp_path / "report.json"
    settings.AI_EVALUATION_PAID_ENABLED = False
    settings.OPENAI_API_KEY = "fake-key"
    with patch(
        "chatbot.management.commands.evaluate_candidate_agent_live.run_paid_dataset"
    ) as provider:
        with pytest.raises(CommandError, match="requires"):
            call_command(
                "evaluate_candidate_agent_live", allow_paid=True, output=output
            )
    provider.assert_not_called()
    assert not output.exists()


@pytest.mark.django_db
def test_paid_command_without_key_never_calls_provider(settings, tmp_path):
    settings.AI_EVALUATION_PAID_ENABLED = True
    settings.OPENAI_API_KEY = ""
    with patch(
        "chatbot.management.commands.evaluate_candidate_agent_live.run_paid_dataset"
    ) as provider:
        with pytest.raises(CommandError, match="not configured"):
            call_command(
                "evaluate_candidate_agent_live",
                allow_paid=True,
                output=tmp_path / "report.json",
            )
    provider.assert_not_called()


@pytest.mark.django_db
def test_paid_command_writes_report_only_when_explicitly_enabled(settings, tmp_path):
    settings.AI_EVALUATION_PAID_ENABLED = True
    settings.OPENAI_API_KEY = "mock-key"
    output = tmp_path / "report.json"
    mock_report = {"provider_usage": {"estimated_spend_usd": "0.123456"}}
    with patch(
        "chatbot.management.commands.evaluate_candidate_agent_live.run_paid_dataset",
        return_value=mock_report,
    ) as runner:
        call_command(
            "evaluate_candidate_agent_live",
            allow_paid=True,
            output=output,
        )
    assert json.loads(output.read_text(encoding="utf-8")) == mock_report
    runner.assert_called_once()
    with pytest.raises(CommandError, match="overwrite"):
        call_command(
            "evaluate_candidate_agent_live",
            allow_paid=True,
            output=output,
        )
