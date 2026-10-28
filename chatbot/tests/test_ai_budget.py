from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier
from unittest.mock import patch

import pytest
from django.db import close_old_connections, connection

from chatbot.models import AIProjectBudget, AIUsageEvent
from chatbot.services.ai import AILimitExceeded, AIResponse, ask_candidate
from chatbot.services.ai_budget import reservation_micro_usd


@pytest.fixture
def budget_config(settings):
    settings.AI_DAILY_BUDGET_USD = "1"
    settings.AI_MONTHLY_BUDGET_USD = "2"
    settings.AI_INPUT_USD_PER_MILLION = "0.15"
    settings.AI_OUTPUT_USD_PER_MILLION = "0.60"
    settings.AI_MAX_INPUT_TOKENS = 128000
    settings.AI_MAX_OUTPUT_TOKENS = 500
    settings.AI_USAGE_LIMITS = {
        "candidate_chat": {
            "identity_per_minute": 100,
            "identity_per_day": 100,
            "candidate_per_day": 100,
        }
    }


@pytest.mark.django_db
def test_budget_reservation_is_persisted_before_provider(
    budget_config, recruiter, published_candidate, verified_fact
):
    amount = reservation_micro_usd("gpt-4o-mini")
    with patch(
        "chatbot.services.ai.invoke_candidate_chat",
        return_value=AIResponse(content="Approved"),
    ) as provider:
        ask_candidate(
            candidate=published_candidate, initiated_by=recruiter, question="Hello"
        )

    provider.assert_called_once()
    assert AIUsageEvent.objects.get().reserved_micro_usd == amount
    budget = AIProjectBudget.objects.get(pk=1)
    assert budget.daily_reserved_micro_usd == amount
    assert budget.monthly_reserved_micro_usd == amount


@pytest.mark.django_db
def test_exhausted_daily_budget_never_calls_provider(
    settings, budget_config, recruiter, published_candidate, verified_fact
):
    amount = reservation_micro_usd("gpt-4o-mini")
    settings.AI_DAILY_BUDGET_USD = str(
        Decimal(amount) / Decimal(1_000_000)
    )

    with patch(
        "chatbot.services.ai.invoke_candidate_chat",
        return_value=AIResponse(content="Approved"),
    ) as provider:
        ask_candidate(
            candidate=published_candidate, initiated_by=recruiter, question="First"
        )
        with pytest.raises(AILimitExceeded):
            ask_candidate(
                candidate=published_candidate, initiated_by=recruiter, question="Second"
            )

    assert provider.call_count == 1
    assert AIUsageEvent.objects.count() == 1


@pytest.mark.django_db
def test_unknown_model_fails_closed(
    settings, budget_config, recruiter, published_candidate, verified_fact
):
    settings.OPENAI_MODEL = "unconfigured-model"
    with patch("chatbot.services.ai.invoke_candidate_chat") as provider:
        with pytest.raises(AILimitExceeded):
            ask_candidate(
                candidate=published_candidate, initiated_by=recruiter, question="Hello"
            )

    provider.assert_not_called()
    assert not AIUsageEvent.objects.exists()


@pytest.mark.skipif(
    connection.vendor != "postgresql", reason="Requires PostgreSQL locks"
)
@pytest.mark.django_db(transaction=True)
def test_concurrent_budget_reservations_cannot_overspend(
    settings, budget_config, recruiter, published_candidate, verified_fact
):
    amount = reservation_micro_usd("gpt-4o-mini")
    settings.AI_DAILY_BUDGET_USD = str(
        Decimal(amount) / Decimal(1_000_000)
    )
    recruiter_id = recruiter.pk
    candidate_id = published_candidate.pk
    barrier = Barrier(2)

    def invoke():
        close_old_connections()
        try:
            from django.contrib.auth import get_user_model

            from chatbot.models import CandidateProfile

            identity = get_user_model().objects.get(pk=recruiter_id)
            candidate = CandidateProfile.objects.get(pk=candidate_id)
            barrier.wait(timeout=10)
            try:
                ask_candidate(
                    candidate=candidate, initiated_by=identity, question="Hello"
                )
                return True
            except AILimitExceeded:
                return False
        finally:
            close_old_connections()

    with patch(
        "chatbot.services.ai.invoke_candidate_chat",
        return_value=AIResponse(content="Approved"),
    ) as provider:
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: invoke(), range(2)))

    assert sorted(results) == [False, True]
    assert provider.call_count == 1
    assert AIUsageEvent.objects.count() == 1
    assert AIProjectBudget.objects.get(pk=1).daily_reserved_micro_usd == amount
