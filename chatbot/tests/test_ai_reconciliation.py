from datetime import UTC, datetime
from decimal import ROUND_CEILING, Decimal
from unittest.mock import patch

import pytest
from django.utils import timezone

from chatbot.models import AIProjectBudget, AIUsageEvent
from chatbot.services.ai import AIResponse, AIUnavailable, ask_candidate
from chatbot.services.ai_budget import reservation_micro_usd, settle_usage


@pytest.fixture
def pricing(settings):
    settings.AI_DAILY_BUDGET_USD = "10"
    settings.AI_MONTHLY_BUDGET_USD = "100"
    settings.AI_INPUT_USD_PER_MILLION = "0.15"
    settings.AI_OUTPUT_USD_PER_MILLION = "0.60"


@pytest.mark.django_db
def test_actual_cost_settlement_credits_unused_reservation(
    pricing, recruiter, published_candidate, verified_fact
):
    reserved = reservation_micro_usd("gpt-4o-mini")
    with patch(
        "chatbot.services.ai.invoke_candidate_chat",
        return_value=AIResponse(content="Answer", input_tokens=40, output_tokens=10),
    ):
        ask_candidate(
            candidate=published_candidate, initiated_by=recruiter, question="Hello"
        )

    actual = int(
        (
            Decimal(40) * Decimal("0.15") + Decimal(10) * Decimal("0.60")
        ).to_integral_value(rounding=ROUND_CEILING)
    )
    usage = AIUsageEvent.objects.get()
    budget = AIProjectBudget.objects.get(pk=1)
    assert usage.reserved_micro_usd == reserved
    assert usage.actual_micro_usd == actual
    assert usage.settled_at is not None
    assert budget.daily_reserved_micro_usd == actual
    assert budget.monthly_reserved_micro_usd == actual

    settle_usage(usage_id=usage.pk)
    budget.refresh_from_db()
    assert budget.daily_reserved_micro_usd == actual
    assert budget.monthly_reserved_micro_usd == actual


@pytest.mark.django_db
def test_missing_provider_usage_preserves_reservation(
    pricing, recruiter, published_candidate, verified_fact
):
    with patch(
        "chatbot.services.ai.invoke_candidate_chat",
        return_value=AIResponse(content="Answer"),
    ):
        ask_candidate(
            candidate=published_candidate, initiated_by=recruiter, question="Hello"
        )
    usage = AIUsageEvent.objects.get()
    assert usage.actual_micro_usd is None
    assert usage.settled_at is None
    assert AIProjectBudget.objects.get(pk=1).daily_reserved_micro_usd == (
        usage.reserved_micro_usd
    )


@pytest.mark.django_db
def test_failed_provider_keeps_full_reservation(
    pricing, recruiter, published_candidate, verified_fact
):
    with patch(
        "chatbot.services.ai.invoke_candidate_chat",
        side_effect=AIUnavailable("Provider unavailable"),
    ):
        with pytest.raises(AIUnavailable):
            ask_candidate(
                candidate=published_candidate, initiated_by=recruiter, question="Hello"
            )
    usage = AIUsageEvent.objects.get()
    settle_usage(usage_id=usage.pk)
    assert usage.actual_micro_usd is None
    assert AIProjectBudget.objects.get(pk=1).daily_reserved_micro_usd == (
        usage.reserved_micro_usd
    )


@pytest.mark.django_db
def test_previous_window_settlement_does_not_refund_current_window(
    pricing, recruiter, published_candidate, verified_fact
):
    with patch(
        "chatbot.services.ai.invoke_candidate_chat",
        return_value=AIResponse(content="Answer"),
    ):
        ask_candidate(
            candidate=published_candidate, initiated_by=recruiter, question="Hello"
        )

    budget = AIProjectBudget.objects.get(pk=1)
    today = timezone.now().date()
    prior_year = today.year - 1
    usage = AIUsageEvent.objects.get()
    AIUsageEvent.objects.filter(pk=usage.pk).update(
        created_at=datetime(prior_year, 1, 1, tzinfo=UTC),
        input_tokens=2,
        output_tokens=2,
    )
    baseline = budget.daily_reserved_micro_usd
    settle_usage(usage_id=usage.pk)
    budget.refresh_from_db()
    assert budget.daily_reserved_micro_usd == baseline
    assert budget.monthly_reserved_micro_usd == baseline
