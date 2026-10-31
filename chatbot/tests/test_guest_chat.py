from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.db import close_old_connections, connection
from django.urls import reverse
from django.utils import timezone

from chatbot.models import (
    AIUsageEvent,
    CandidateProfile,
    Conversation,
    GuestChatSession,
    GuestOrigin,
)
from chatbot.services.ai import AILimitExceeded, AIResponse, ask_candidate
from chatbot.services.guest_chat import (
    GuestAccessDenied,
    create_guest_session,
    origin_digest,
    verify_turnstile,
)


@pytest.fixture
def guest_settings(settings):
    settings.GUEST_CHAT_ENABLED = True
    settings.GUEST_IP_HASH_SECRET = "test-only-ip-secret"
    settings.GUEST_TURNSTILE_SITE_KEY = "site-test"
    settings.GUEST_TURNSTILE_SECRET_KEY = "secret-test"
    settings.GUEST_TRUSTED_PROXY_IPS = []
    settings.GUEST_ORIGIN_PER_MINUTE = 100
    settings.GUEST_ORIGIN_PER_DAY = 100
    settings.GUEST_GLOBAL_PER_DAY = 100
    settings.GUEST_SESSIONS_PER_ORIGIN_PER_DAY = 20
    settings.GUEST_SESSION_QUESTION_LIMIT = 10
    settings.GUEST_SESSION_HOURS = 24
    settings.GUEST_CONVERSATION_RETENTION_DAYS = 7


def guest_post(client, candidate, *, token="valid-token", question="Experience?"):
    return client.post(
        reverse("chat", args=[candidate.slug]),
        {"question": question, "cf-turnstile-response": token},
    )


@pytest.mark.django_db
def test_guest_chat_requires_verified_challenge(
    client, guest_settings, published_candidate, verified_fact
):
    with patch("chatbot.views.verify_turnstile", return_value=False) as check:
        with patch("chatbot.services.ai.invoke_candidate_chat") as provider:
            response = guest_post(client, published_candidate)
    assert response.status_code == 403
    check.assert_called_once_with("valid-token", hostname="testserver")
    provider.assert_not_called()
    assert not GuestChatSession.objects.exists()
    assert not AIUsageEvent.objects.exists()


@pytest.mark.django_db
def test_guest_session_and_history_are_isolated(
    client, guest_settings, published_candidate, verified_fact
):
    path = reverse("chat", args=[published_candidate.slug])
    page = client.get(path)
    assert page.status_code == 200
    assert b'data-action="candidate_chat"' in page.content

    with patch("chatbot.views.verify_turnstile", return_value=True) as check:
        with patch(
            "chatbot.services.ai.invoke_candidate_chat",
            return_value=AIResponse(content="Verified professional answer."),
        ) as provider:
            first = guest_post(client, published_candidate)
            second = guest_post(client, published_candidate, token="", question="More?")
    assert first.status_code == second.status_code == 200
    assert check.call_count == 1
    assert provider.call_count == 2
    assert GuestChatSession.objects.count() == 1
    conversation = Conversation.objects.get(guest_session__isnull=False)
    assert conversation.recruiter is None
    assert conversation.messages.count() == 4


    assert b"Verified professional answer." in client.get(path).content
    from django.test import Client

    outsider = Client()
    outsider_page = outsider.get(path)
    assert b"Verified professional answer." not in outsider_page.content


@pytest.mark.django_db
def test_guest_quota_enforced_after_ten_requests(
    client, guest_settings, published_candidate, verified_fact
):
    with patch("chatbot.views.verify_turnstile", return_value=True):
        with patch(
            "chatbot.services.ai.invoke_candidate_chat",
            return_value=AIResponse(content="Grounded"),
        ) as provider:
            responses = [guest_post(client, published_candidate) for _ in range(11)]
    assert [r.status_code for r in responses] == [200] * 10 + [429]
    assert provider.call_count == 10
    assert AIUsageEvent.objects.count() == 10


@pytest.mark.django_db
def test_new_cookie_does_not_bypass_origin_limits(
    guest_settings, published_candidate, verified_fact
):
    from django.test import Client

    from_first = Client()
    from_second = Client()
    from_second.cookies.clear()
    from django.conf import settings

    settings.GUEST_ORIGIN_PER_DAY = 1
    with patch("chatbot.views.verify_turnstile", return_value=True):
        with patch(
            "chatbot.services.ai.invoke_candidate_chat",
            return_value=AIResponse(content="Grounded"),
        ) as provider:
            first = guest_post(from_first, published_candidate)
            second = guest_post(from_second, published_candidate)
    assert first.status_code == 200
    assert second.status_code == 429
    assert provider.call_count == 1


@pytest.mark.django_db
def test_global_guest_limit_is_independent_of_ip(
    guest_settings, published_candidate, verified_fact
):
    from django.conf import settings
    from django.test import Client

    settings.GUEST_GLOBAL_PER_DAY = 1
    with patch("chatbot.views.verify_turnstile", return_value=True):
        with patch(
            "chatbot.services.ai.invoke_candidate_chat",
            return_value=AIResponse(content="Grounded"),
        ) as provider:
            first = guest_post(Client(REMOTE_ADDR="192.0.2.1"), published_candidate)
            second = guest_post(Client(REMOTE_ADDR="192.0.2.2"), published_candidate)
    assert first.status_code == 200
    assert second.status_code == 429
    assert provider.call_count == 1


@pytest.mark.django_db
def test_expired_guest_session_must_reverify(
    client, guest_settings, published_candidate, verified_fact
):
    with patch("chatbot.views.verify_turnstile", return_value=True):
        with patch(
            "chatbot.services.ai.invoke_candidate_chat",
            return_value=AIResponse(content="Answer"),
        ):
            assert guest_post(client, published_candidate).status_code == 200

    GuestChatSession.objects.update(expires_at=timezone.now() - timedelta(minutes=1))
    with patch("chatbot.views.verify_turnstile", return_value=False):
        with patch("chatbot.services.ai.invoke_candidate_chat") as provider:
            response = guest_post(client, published_candidate, token="expired")
    assert response.status_code == 403
    provider.assert_not_called()


@pytest.mark.django_db
def test_guest_cannot_access_unpublished_candidate(client, guest_settings, user):
    private = CandidateProfile.objects.create(user=user, name="Private profile")
    with patch("chatbot.views.verify_turnstile") as check:
        response = guest_post(client, private)
    assert response.status_code == 404
    check.assert_not_called()


@pytest.mark.django_db
def test_guest_duplicate_request_does_not_spend_twice(
    client, guest_settings, published_candidate, verified_fact
):
    url = reverse("chat", args=[published_candidate.slug])
    with patch("chatbot.views.verify_turnstile", return_value=True):
        with patch(
            "chatbot.services.ai.invoke_candidate_chat",
            return_value=AIResponse(content="Answer"),
        ) as provider:
            first = client.post(
                url,
                {"question": "First", "cf-turnstile-response": "token"},
                HTTP_IDEMPOTENCY_KEY="same-key",
            )
            second = client.post(
                url, {"question": "Second"}, HTTP_IDEMPOTENCY_KEY="same-key"
            )
    assert first.status_code == 200
    assert second.status_code == 409
    assert provider.call_count == 1


@pytest.mark.django_db
def test_session_generation_limit(guest_settings, published_candidate):
    from django.conf import settings

    settings.GUEST_SESSIONS_PER_ORIGIN_PER_DAY = 1
    one = create_guest_session(candidate=published_candidate, digest="a" * 64)
    assert one.pk
    with pytest.raises(GuestAccessDenied):
        create_guest_session(candidate=published_candidate, digest="a" * 64)


@pytest.mark.django_db
def test_cleanup_purges_guest_conversation_not_usage(
    client, guest_settings, published_candidate, verified_fact
):
    with patch("chatbot.views.verify_turnstile", return_value=True):
        with patch(
            "chatbot.services.ai.invoke_candidate_chat",
            return_value=AIResponse(content="Sensitive visitor question"),
        ):
            assert guest_post(client, published_candidate).status_code == 200
    old = timezone.now() - timedelta(days=8)
    GuestChatSession.objects.update(created_at=old)
    GuestOrigin.objects.update(created_at=old)
    call_command("cleanup_guest_sessions")
    assert not GuestChatSession.objects.exists()
    assert not GuestOrigin.objects.exists()
    assert not Conversation.objects.exists()
    assert AIUsageEvent.objects.count() == 1
    assert AIUsageEvent.objects.get().guest_session_id is None
    assert AIUsageEvent.objects.get().guest_origin_id is None


def test_origin_hash_does_not_trust_spoofed_forwarded_header(
    rf, guest_settings, settings
):
    forged = rf.get("/", REMOTE_ADDR="198.51.100.10", HTTP_X_FORWARDED_FOR="192.0.2.30")
    actual = rf.get("/", REMOTE_ADDR="198.51.100.10")
    assert origin_digest(forged) == origin_digest(actual)

    settings.GUEST_TRUSTED_PROXY_IPS = ["127.0.0.1"]
    via_proxy = rf.get("/", REMOTE_ADDR="127.0.0.1", HTTP_X_FORWARDED_FOR="192.0.2.30")
    expected = rf.get("/", REMOTE_ADDR="192.0.2.30")
    assert origin_digest(via_proxy) == origin_digest(expected)


def test_siteverify_rejects_mismatched_metadata(guest_settings):
    from io import BytesIO

    class Response:
        def __init__(self, data):
            self.data = data

        def __enter__(self):
            return BytesIO(self.data)

        def __exit__(self, *args):
            return False

    with patch(
        "chatbot.services.guest_chat.urlopen",
        return_value=Response(
            b'{"success":true,"hostname":"attacker.test","action":"candidate_chat"}'
        ),
    ):
        assert not verify_turnstile("token", hostname="example.com")
    with patch(
        "chatbot.services.guest_chat.urlopen",
        return_value=Response(
            b'{"success":true,"hostname":"example.com","action":"candidate_chat"}'
        ),
    ) as request:
        assert verify_turnstile("token", hostname="example.com")
    assert request.call_count == 1


@pytest.mark.skipif(
    connection.vendor != "postgresql", reason="Requires PostgreSQL locks"
)
@pytest.mark.django_db(transaction=True)
def test_concurrent_requests_share_single_guest_lease(
    guest_settings, published_candidate, verified_fact
):
    origin = GuestOrigin.objects.create(digest="z" * 64)
    guest = GuestChatSession.objects.create(
        candidate=published_candidate,
        origin=origin,
        expires_at=timezone.now() + timedelta(hours=24),
    )
    ready = Event()
    done = Event()

    def slow_provider(**kwargs):
        ready.set()
        assert done.wait(timeout=15)
        return AIResponse(content="Answer")

    def first_request():
        close_old_connections()
        try:
            candidate = CandidateProfile.objects.get(pk=published_candidate.pk)
            session = GuestChatSession.objects.get(pk=guest.pk)
            return ask_candidate(
                candidate=candidate, guest_session=session, question="First"
            )
        finally:
            close_old_connections()

    with patch(
        "chatbot.services.ai.invoke_candidate_chat", side_effect=slow_provider
    ) as provider:
        with ThreadPoolExecutor(max_workers=1) as executor:
            first = executor.submit(first_request)
            assert ready.wait(timeout=15)
            with pytest.raises(AILimitExceeded):
                ask_candidate(
                    candidate=published_candidate,
                    guest_session=guest,
                    question="Second",
                )
            done.set()
            assert first.result(timeout=15).content == "Answer"
    assert provider.call_count == 1
    assert AIUsageEvent.objects.count() == 1
    guest.refresh_from_db()
    assert guest.active_usage_id is None


@pytest.mark.django_db
def test_missing_turnstile_does_not_create_session(
    client, guest_settings, published_candidate
):
    with patch("chatbot.services.ai.invoke_candidate_chat") as provider:
        response = guest_post(client, published_candidate, token="")
    assert response.status_code == 403
    assert not GuestChatSession.objects.exists()
    provider.assert_not_called()
