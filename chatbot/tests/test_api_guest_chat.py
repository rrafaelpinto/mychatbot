"""Security and contract regression tests for session-scoped guest API."""

import json
from unittest.mock import patch

import pytest
from django.test import Client
from django.urls import reverse

from chatbot.models import AIUsageEvent, CandidateProfile, GuestChatSession
from chatbot.services.ai import AIResponse


@pytest.fixture
def guest_settings(settings):
    settings.GUEST_CHAT_ENABLED = True
    settings.GUEST_IP_HASH_SECRET = "test-guest-api"
    settings.GUEST_TURNSTILE_SITE_KEY = "site-test"
    settings.GUEST_TURNSTILE_SECRET_KEY = "secret-test"
    settings.GUEST_TRUSTED_PROXY_IPS = []
    settings.GUEST_ORIGIN_PER_MINUTE = 100
    settings.GUEST_ORIGIN_PER_DAY = 100
    settings.GUEST_GLOBAL_PER_DAY = 100
    settings.GUEST_SESSIONS_PER_ORIGIN_PER_DAY = 20
    settings.GUEST_SESSION_QUESTION_LIMIT = 10


def browser():
    client = Client(enforce_csrf_checks=True)
    token = client.get(reverse("api-auth-csrf")).json()["csrf_token"]
    return client, {"HTTP_X_CSRFTOKEN": token}


def guest_post(client, candidate, csrf, *, token="challenge", key="request-key", origin=None):
    headers = {"HTTP_IDEMPOTENCY_KEY": key, **csrf}
    if origin:
        headers["HTTP_ORIGIN"] = origin
    return client.post(
        reverse("api-candidate-guest-chat", args=[candidate.slug]),
        json.dumps({"question": "Professional experience?", "turnstile_token": token}),
        content_type="application/json",
        **headers,
    )


@pytest.mark.django_db
def test_guest_api_requires_csrf_and_turnstile_before_any_spend(
    guest_settings, published_candidate
):
    client, csrf = browser()
    url = reverse("api-candidate-guest-chat", args=[published_candidate.slug])
    assert client.post(url, "{}", content_type="application/json").status_code == 403
    with patch("chatbot.api.guest.verify_turnstile", return_value=False) as check:
        with patch("chatbot.api.guest.ask_candidate") as provider:
            response = guest_post(client, published_candidate, csrf)
    assert response.status_code == 403
    check.assert_called_once_with("challenge", hostname="testserver")
    provider.assert_not_called()
    assert not GuestChatSession.objects.exists()
    assert not AIUsageEvent.objects.exists()


@pytest.mark.django_db
def test_guest_history_is_session_scoped_and_public_evidence_only(
    guest_settings, published_candidate, verified_fact
):
    client, csrf = browser()
    url = reverse("api-candidate-guest-chat", args=[published_candidate.slug])
    initial = client.get(url)
    assert initial.status_code == 200
    assert initial["Cache-Control"] == "no-store"
    assert initial.json()["turnstile_site_key"] == "site-test"
    assert initial.json()["history"] == []
    with patch("chatbot.api.guest.verify_turnstile", return_value=True) as check:
        with patch(
            "chatbot.api.guest.ask_candidate",
            return_value=AIResponse(
                content="Approved claim",
                cited_fact_ids=(verified_fact.pk,),
                evidence=(
                    {
                        "id": verified_fact.pk,
                        "fact_type": verified_fact.fact_type,
                        "content": verified_fact.content,
                    },
                ),
            ),
        ) as provider:
            assert guest_post(client, published_candidate, csrf, key="one").status_code == 200
            assert guest_post(
                client, published_candidate, csrf, token="", key="two"
            ).status_code == 200
    assert check.call_count == 1
    assert provider.call_count == 2
    assert provider.call_args.kwargs["guest_session"] is not None
    assert provider.call_args.kwargs["initiated_by"] is None
    history = client.get(url).json()["history"]
    assert len(history) == 4
    assert history[1]["evidence"][0]["id"] == verified_fact.pk
    assert "source_document" not in json.dumps(history)
    assert "guest_session" not in json.dumps(history)
    outsider, _ = browser()
    assert outsider.get(url).json()["history"] == []
    assert GuestChatSession.objects.count() == 1

    verified_fact.is_public = False
    verified_fact.save(update_fields=["is_public"])
    redacted = client.get(url).json()["history"]
    assert "Approved claim" not in json.dumps(redacted)
    assert redacted[1]["evidence"] == []


@pytest.mark.django_db
def test_guest_api_uses_frontend_origin_for_turnstile_hostname(
    guest_settings, settings, published_candidate
):
    settings.CORS_ALLOWED_ORIGINS = ["https://app.example.test"]
    settings.CSRF_TRUSTED_ORIGINS = ["https://app.example.test"]
    client, csrf = browser()
    with patch("chatbot.api.guest.verify_turnstile", return_value=True) as verify:
        with patch(
            "chatbot.api.guest.ask_candidate",
            return_value=AIResponse(content="Approved"),
        ):
            accepted = guest_post(
                client, published_candidate, csrf, origin="https://app.example.test"
            )
    assert accepted.status_code == 200
    verify.assert_called_once_with("challenge", hostname="app.example.test")
    outsider, outsider_csrf = browser()
    with patch("chatbot.api.guest.verify_turnstile") as verify:
        rejected = guest_post(
            outsider, published_candidate, outsider_csrf,
            origin="https://attacker.example.test",
        )
    assert rejected.status_code == 403
    verify.assert_not_called()


@pytest.mark.django_db
def test_guest_api_reuses_backend_usage_quota(
    guest_settings, published_candidate, verified_fact, settings
):
    settings.GUEST_SESSION_QUESTION_LIMIT = 1
    client, csrf = browser()
    with patch("chatbot.api.guest.verify_turnstile", return_value=True):
        with patch(
            "chatbot.services.ai.invoke_candidate_chat",
            return_value=AIResponse(content="Approved"),
        ) as provider:
            first = guest_post(client, published_candidate, csrf, key="one")
            second = guest_post(client, published_candidate, csrf, token="", key="two")
    assert first.status_code == 200
    assert first.json()["remaining"] == 0
    assert second.status_code == 429
    assert provider.call_count == 1
    assert AIUsageEvent.objects.count() == 1


@pytest.mark.django_db
def test_guest_api_respects_disabled_and_unpublished_profiles(
    guest_settings, settings, published_candidate
):
    client, csrf = browser()
    url = reverse("api-candidate-guest-chat", args=[published_candidate.slug])
    settings.GUEST_CHAT_ENABLED = False
    assert client.get(url).json()["enabled"] is False
    assert guest_post(client, published_candidate, csrf).status_code == 503
    settings.GUEST_CHAT_ENABLED = True
    published_candidate.publication_status = CandidateProfile.PublicationStatus.DRAFT
    published_candidate.save(update_fields=["publication_status"])
    with patch("chatbot.api.guest.verify_turnstile") as verify:
        assert client.get(url).status_code == 404
        assert guest_post(client, published_candidate, csrf).status_code == 404
    verify.assert_not_called()


@pytest.mark.django_db
def test_guest_api_has_schema_contract(client):
    schema = client.get(reverse("api-schema") + "?format=json").json()
    path = schema["paths"]["/api/v1/candidates/{slug}/guest-chat/"]
    assert "get" in path and "post" in path
    assert "GuestStatus" in schema["components"]["schemas"]
    assert "GuestAnswer" in schema["components"]["schemas"]
