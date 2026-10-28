from unittest.mock import patch

import pytest

from chatbot.models import AIUsageEvent
from chatbot.services.ai import AIResponse, ask_candidate
from chatbot.services.ai_budget import settle_usage


@pytest.mark.django_db
def test_settlement_uses_prices_snapshotted_at_admission(
    settings, recruiter, published_candidate, verified_fact
):
    settings.AI_INPUT_USD_PER_MILLION = "0.15"
    settings.AI_OUTPUT_USD_PER_MILLION = "0.60"
    with patch(
        "chatbot.services.ai.invoke_candidate_chat",
        return_value=AIResponse(content="Answer"),
    ):
        ask_candidate(
            candidate=published_candidate, initiated_by=recruiter, question="Hello"
        )
    event = AIUsageEvent.objects.get()
    assert str(event.input_price_per_million) == "0.150000"
    assert str(event.output_price_per_million) == "0.600000"
    settings.AI_INPUT_USD_PER_MILLION = "100"
    settings.AI_OUTPUT_USD_PER_MILLION = "100"
    AIUsageEvent.objects.filter(pk=event.pk).update(input_tokens=10, output_tokens=10)
    settle_usage(usage_id=event.pk)
    event.refresh_from_db()
    assert event.actual_micro_usd == 8


@pytest.mark.django_db
def test_settlement_failure_does_not_discard_paid_response(
    recruiter, published_candidate, verified_fact
):
    with (
        patch(
            "chatbot.services.ai.invoke_candidate_chat",
            return_value=AIResponse(
                content="Answer", input_tokens=10, output_tokens=10
            ),
        ) as provider,
        patch("chatbot.services.ai.settle_usage", side_effect=RuntimeError("db issue")),
    ):
        result = ask_candidate(
            candidate=published_candidate, initiated_by=recruiter, question="Hello"
        )
    assert result.content == "Answer"
    provider.assert_called_once()
    event = AIUsageEvent.objects.get()
    assert event.status == AIUsageEvent.Status.SUCCEEDED
    assert event.settled_at is None
