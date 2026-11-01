import json
from unittest.mock import patch

import pytest
from django.core.cache import cache
from django.test import Client
from django.urls import reverse
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken

from chatbot.models import CandidateFactReviewEvent, Message
from chatbot.services.ai import AIResponse


@pytest.fixture(autouse=True)
def clear_auth_throttle_cache():
    cache.clear()


def browser():
    client = Client(enforce_csrf_checks=True)
    response = client.get(reverse("api-auth-csrf"))
    assert response.status_code == 200
    assert response.cookies["csrftoken"]
    return client, {"HTTP_X_CSRFTOKEN": response.json()["csrf_token"]}


def login(client, csrf, username="candidate-owner", ***):
    return client.post(
        reverse("api-auth-token"),
        data=json.dumps({"username": username, "password": password}),
        content_type="application/json",
        **csrf,
    )


@pytest.mark.django_db
def test_login_requires_csrf_and_returns_only_in_memory_access(user):
    client = Client(enforce_csrf_checks=True)
    payload = json.dumps({"username": user.username, "password": "password"})
    assert (
        client.post(
            reverse("api-auth-token"), payload, content_type="application/json"
        ).status_code
        == 403
    )
    client, csrf = browser()
    response = login(client, csrf)
    assert response.status_code == 200
    assert set(response.json()) == {"access", "token_type", "expires_in"}
    assert response.json()["expires_in"] == 300
    assert "refresh" not in response.content.decode()
    cookie = response.cookies["resumebot_refresh"]
    assert cookie["httponly"]
    assert cookie["path"] == "/api/v1/auth/"
    assert cookie["samesite"] == "Lax"
    assert response["Cache-Control"] == "no-store"
    assert (
        client.get(
            reverse("api-me"),
            HTTP_AUTHORIZATION=f"***'access']}",
        ).status_code
        == 200
    )


@pytest.mark.django_db
def test_refresh_and_logout_require_csrf(user):
    client, csrf = browser()
    assert login(client, csrf).status_code == 200
    assert client.post(reverse("api-auth-refresh")).status_code == 403
    assert client.post(reverse("api-auth-logout")).status_code == 403
    assert client.post(reverse("api-auth-logout"), **csrf).status_code == 204


@pytest.mark.django_db
def test_refresh_rotates_and_blacklists_previous_cookie(user):
    client, csrf = browser()
    assert login(client, csrf).status_code == 200
    old = client.cookies["resumebot_refresh"].value
    rotated = client.post(reverse("api-auth-refresh"), **csrf)
    assert rotated.status_code == 200
    new = client.cookies["resumebot_refresh"].value
    assert old != new
    assert "refresh" not in rotated.json()
    assert BlacklistedToken.objects.count() == 1
    client.cookies["resumebot_refresh"] = old
    assert client.post(reverse("api-auth-refresh"), **csrf).status_code == 401
    client.cookies["resumebot_refresh"] = new
    assert client.post(reverse("api-auth-refresh"), **csrf).status_code == 200


@pytest.mark.django_db
def test_logout_does_not_destroy_django_session(user):
    client, csrf = browser()
    client.force_login(user)
    assert login(client, csrf).status_code == 200
    original = client.cookies["resumebot_refresh"].value
    response = client.post(reverse("api-auth-logout"), **csrf)
    assert response.status_code == 204
    assert response.cookies["resumebot_refresh"].value == ""
    assert client.get(reverse("api-me")).status_code == 200
    client.cookies["resumebot_refresh"] = original
    assert client.post(reverse("api-auth-refresh"), **csrf).status_code == 401


@pytest.mark.django_db
def test_login_rejects_invalid_and_disabled_users(user):
    client, csrf = browser()
    assert login(client, csrf, ***).status_code == 401
    user.is_active = False
    user.save(update_fields=["is_active"])
    assert login(client, csrf).status_code == 401
    assert "resumebot_refresh" not in client.cookies


@pytest.mark.django_db
def test_login_throttle_limits_password_guessing(user):
    client, csrf = browser()
    for _ in range(5):
        assert login(client, csrf, ***).status_code == 401
    assert login(client, csrf, ***).status_code == 429


@pytest.mark.django_db
def test_explicit_cors_allowlist_and_untrusted_origin_csrf(settings, user):
    settings.CORS_ALLOWED_ORIGINS = ["https://app.example.test"]
    client, csrf = browser()
    allowed = client.options(
        reverse("api-auth-token"),
        HTTP_ORIGIN="https://app.example.test",
        HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
    )
    assert allowed["Access-Control-Allow-Origin"] == "https://app.example.test"
    assert allowed["Access-Control-Allow-Credentials"] == "true"
    blocked = client.options(
        reverse("api-auth-token"),
        HTTP_ORIGIN="https://untrusted.example.test",
        HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
    )
    assert "Access-Control-Allow-Origin" not in blocked
    assert (
        client.post(
            reverse("api-auth-token"),
            data=json.dumps({"username": user.username, "password": "password"}),
            content_type="application/json",
            HTTP_ORIGIN="https://untrusted.example.test",
            **csrf,
        ).status_code
        == 403
    )


@pytest.mark.django_db
def test_profile_patch_rejects_approval_and_private_fields(published_candidate):
    client, csrf = browser()
    access = login(client, csrf).json()["access"]
    auth = {"HTTP_AUTHORIZATION": f"***"}
    url = reverse("api-me-profile")
    assert (
        client.patch(
            url,
            data=json.dumps({"status": "active", "phone": "hidden"}),
            content_type="application/json",
            **auth,
        ).status_code
        == 400
    )
    assert (
        client.patch(
            url,
            data=json.dumps({"professional_summary": "Verified portfolio"}),
            content_type="application/json",
            **auth,
        ).status_code
        == 200
    )
    published_candidate.refresh_from_db()
    assert published_candidate.professional_summary == "Verified portfolio"


@pytest.mark.django_db
def test_review_rejects_stale_version_and_other_account(
    published_candidate, verified_fact, other_user
):
    client, csrf = browser()
    url = reverse("api-me-fact-review", kwargs={"fact_id": verified_fact.pk})
    version = verified_fact.updated_at.isoformat()
    assert (
        client.post(
            url,
            json.dumps({"action": "unpublish", "version": version}),
            content_type="application/json",
        ).status_code
        == 401
    )
    token = login(client, csrf).json()["access"]
    auth = {"HTTP_AUTHORIZATION": f"***"}
    assert (
        client.post(
            url,
            json.dumps({"action": "publish", "version": version}),
            content_type="application/json",
            **auth,
        ).status_code
        == 200
    )
    verified_fact.refresh_from_db()
    assert not verified_fact.is_public
    assert CandidateFactReviewEvent.objects.filter(fact=verified_fact).count() == 1
    assert (
        client.post(
            url,
            json.dumps({"action": "unpublish", "version": version}),
            content_type="application/json",
            **auth,
        ).status_code
        == 409
    )
    client, csrf = browser()
    other_access = login(client, csrf, username=other_user.username).json()["access"]
    assert (
        client.post(
            url,
            json.dumps(
                {"action": "unpublish", "version": verified_fact.updated_at.isoformat()}
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"***",
        ).status_code
        == 404
    )


@pytest.mark.django_db
def test_authenticated_chat_preserves_provider_boundary_and_history(
    published_candidate, verified_fact
):
    client, csrf = browser()
    url = reverse("api-candidate-chat", kwargs={"slug": published_candidate.slug})
    assert client.post(url, "{}", content_type="application/json").status_code == 401
    token = login(client, csrf).json()["access"]
    headers = {"HTTP_AUTHORIZATION": f"***"}
    response = AIResponse(
        content="Verified Django experience.",
        cited_fact_ids=(verified_fact.pk,),
        evidence=(
            {
                "id": verified_fact.pk,
                "fact_type": verified_fact.fact_type,
                "content": verified_fact.content,
            },
        ),
    )
    with patch("chatbot.api.views.ask_candidate", return_value=response) as provider:
        result = client.post(
            url,
            json.dumps({"question": "What frameworks?"}),
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY="request-one",
            **headers,
        )
    assert result.status_code == 200
    assert result.json()["response"] == response.content
    assert provider.call_args.kwargs["initiated_by"] == published_candidate.user
    assert provider.call_args.kwargs["idempotency_key"] == "request-one"
    assert (
        Message.objects.filter(conversation__candidate=published_candidate).count() == 2
    )
    assert len(client.get(url, **headers).json()) == 2


@pytest.mark.django_db
def test_chat_rejects_unpublished_candidate_before_provider(published_candidate):
    client, csrf = browser()
    token = login(client, csrf).json()["access"]
    published_candidate.publication_status = "draft"
    published_candidate.save()
    url = reverse("api-candidate-chat", kwargs={"slug": published_candidate.slug})
    with patch("chatbot.api.views.ask_candidate") as provider:
        assert (
            client.post(
                url,
                json.dumps({"question": "Your projects?"}),
                content_type="application/json",
                HTTP_AUTHORIZATION=f"***",
            ).status_code
            == 404
        )
        provider.assert_not_called()


@pytest.mark.django_db
def test_openapi_exposes_jwt_endpoints(client):
    schema = client.get(reverse("api-schema") + "?format=json").json()
    for path in (
        "/api/v1/auth/csrf/",
        "/api/v1/auth/token/",
        "/api/v1/auth/refresh/",
        "/api/v1/auth/logout/",
        "/api/v1/me/facts/{fact_id}/review/",
        "/api/v1/candidates/{slug}/chat/",
    ):
        assert path in schema["paths"]
2026-11-01T00:06:43.0936588
