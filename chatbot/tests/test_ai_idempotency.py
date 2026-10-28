from unittest.mock import patch

import pytest
from django.contrib import admin
from django.urls import reverse

from chatbot.admin import AIProjectBudgetAdmin, AIUsageEventAdmin
from chatbot.models import AIProjectBudget, AIUsageEvent
from chatbot.services.ai import AIRequestAlreadySubmitted, AIResponse, ask_candidate


@pytest.mark.django_db
def test_repeated_key_does_not_invoke_provider_twice(
    recruiter, published_candidate, verified_fact
):
    with patch(
        "chatbot.services.ai.invoke_candidate_chat",
        return_value=AIResponse(content="Answer", input_tokens=20, output_tokens=10),
    ) as provider:
        ask_candidate(
            candidate=published_candidate,
            initiated_by=recruiter,
            question="Experience?",
            idempotency_key="request-123",
        )
        reserved = AIProjectBudget.objects.get(pk=1).daily_reserved_micro_usd
        with pytest.raises(AIRequestAlreadySubmitted):
            ask_candidate(
                candidate=published_candidate,
                initiated_by=recruiter,
                question="Experience?",
                idempotency_key="request-123",
            )

    assert provider.call_count == 1
    assert AIUsageEvent.objects.count() == 1
    assert AIProjectBudget.objects.get(pk=1).daily_reserved_micro_usd == reserved


@pytest.mark.django_db
def test_repeated_key_returns_conflict_on_http(
    client, recruiter, published_candidate, verified_fact
):
    client.force_login(recruiter)
    url = reverse("chat", args=[published_candidate.slug])
    with patch(
        "chatbot.services.ai.invoke_candidate_chat",
        return_value=AIResponse(content="Answer"),
    ) as provider:
        first = client.post(
            url, {"question": "Experience?"}, HTTP_IDEMPOTENCY_KEY="request-123"
        )
        second = client.post(
            url, {"question": "Experience?"}, HTTP_IDEMPOTENCY_KEY="request-123"
        )
    assert first.status_code == 200
    assert second.status_code == 409
    assert provider.call_count == 1


@pytest.mark.django_db
def test_invalid_idempotency_key_fails_before_provider(
    client, recruiter, published_candidate, verified_fact
):
    client.force_login(recruiter)
    with patch("chatbot.services.ai.invoke_candidate_chat") as provider:
        response = client.post(
            reverse("chat", args=[published_candidate.slug]),
            {"question": "Experience?"},
            HTTP_IDEMPOTENCY_KEY="x" * 129,
        )
    assert response.status_code == 400
    provider.assert_not_called()
    assert not AIUsageEvent.objects.exists()


@pytest.mark.django_db
def test_ai_cost_admin_is_read_only(rf, admin_user):
    request = rf.get("/admin/")
    request.user = admin_user
    for model, model_admin in (
        (AIUsageEvent, AIUsageEventAdmin),
        (AIProjectBudget, AIProjectBudgetAdmin),
    ):
        instance = model_admin(model, admin.site)
        assert not instance.has_add_permission(request)
        assert not instance.has_change_permission(request)
        assert not instance.has_delete_permission(request)
