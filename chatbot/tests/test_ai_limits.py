from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

import pytest
from django.db import close_old_connections, connection
from django.urls import reverse

from chatbot.models import AIUsageEvent
from chatbot.services.ai import AILimitExceeded, AIResponse, ask_candidate


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("limit", "value"),
    [
        ("identity_per_minute", 1),
        ("identity_per_day", 1),
        ("candidate_per_day", 1),
    ],
)
def test_ai_limits_deny_before_provider(
    settings, recruiter, published_candidate, verified_fact, limit, value
):
    settings.AI_USAGE_LIMITS = {
        "candidate_chat": {
            "identity_per_minute": 10,
            "identity_per_day": 10,
            "candidate_per_day": 10,
            limit: value,
        }
    }
    with patch(
        "chatbot.services.ai.invoke_candidate_chat",
        return_value=AIResponse(content="Approved"),
    ) as provider:
        ask_candidate(
            candidate=published_candidate,
            initiated_by=recruiter,
            question="First",
        )
        with pytest.raises(AILimitExceeded):
            ask_candidate(
                candidate=published_candidate,
                initiated_by=recruiter,
                question="Second",
            )

    assert provider.call_count == 1
    assert AIUsageEvent.objects.count() == 1


@pytest.mark.django_db
def test_ai_quota_denial_returns_429(
    client, settings, recruiter, published_candidate, verified_fact
):
    settings.AI_USAGE_LIMITS = {
        "candidate_chat": {
            "identity_per_minute": 0,
            "identity_per_day": 10,
            "candidate_per_day": 10,
        }
    }
    client.force_login(recruiter)
    with patch("chatbot.services.ai.invoke_candidate_chat") as provider:
        response = client.post(
            reverse("chat", args=[published_candidate.slug]),
            {"question": "Hello"},
        )

    assert response.status_code == 429
    provider.assert_not_called()
    assert not AIUsageEvent.objects.exists()


@pytest.mark.skipif(
    connection.vendor != "postgresql", reason="Requires PostgreSQL locks"
)
@pytest.mark.django_db(transaction=True)
def test_concurrent_ai_admission_does_not_exceed_candidate_quota(
    settings, recruiter, published_candidate, verified_fact
):
    settings.AI_USAGE_LIMITS = {
        "candidate_chat": {
            "identity_per_minute": 1,
            "identity_per_day": 1,
            "candidate_per_day": 1,
        }
    }
    candidate_id = published_candidate.pk
    recruiter_id = recruiter.pk
    barrier = Barrier(2)

    def invoke():
        close_old_connections()
        try:
            from django.contrib.auth import get_user_model

            from chatbot.models import CandidateProfile

            user = get_user_model().objects.get(pk=recruiter_id)
            candidate = CandidateProfile.objects.get(pk=candidate_id)
            barrier.wait(timeout=10)
            try:
                ask_candidate(candidate=candidate, initiated_by=user, question="Hello")
                return True
            except AILimitExceeded:
                return False
        finally:
            close_old_connections()

    with patch(
        "chatbot.services.ai.invoke_candidate_chat",
        return_value=AIResponse(content="Approved"),
    ) as provider:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(invoke) for _ in range(2)]
            admitted = [future.result(timeout=15) for future in futures]

    assert sorted(admitted) == [False, True]
    assert provider.call_count == 1
    assert AIUsageEvent.objects.count() == 1
