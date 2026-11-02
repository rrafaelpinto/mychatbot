import re
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.contrib import admin
from django.core import mail
from django.core.cache import cache
from django.test import Client
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from chatbot.admin import approve_candidates
from chatbot.models import (
    AccountAccess,
    CandidateDocument,
    CandidateFact,
    CandidateProfile,
    EmailChallenge,
)
from chatbot.services.accounts import request_code, verify_code
from chatbot.tests.test_documents import make_docx

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def reset_throttles():
    cache.clear()


def begin(client, email="new@example.test", role="candidate"):
    csrf = client.get("/api/v1/auth/csrf/").json()["csrf_token"]
    headers = {"HTTP_X_CSRFTOKEN": csrf}
    response = client.post(
        "/api/v1/auth/code/request/",
        {"email": email, "name": "Example Person", "role": role},
        content_type="application/json",
        **headers,
    )
    assert response.status_code == 200
    code = re.search(r"\b\d{6}\b", mail.outbox[-1].body).group()
    return headers, code


def finish(client, headers, code, email="new@example.test"):
    return client.post(
        "/api/v1/auth/code/verify/",
        {"email": email, "code": code},
        content_type="application/json",
        **headers,
    )


def test_candidate_must_verify_then_wait_for_approval(settings):
    settings.PUBLIC_REGISTRATION_ENABLED = True
    client = Client(enforce_csrf_checks=True)
    headers, code = begin(client)
    assert not AccountAccess.objects.exists()
    assert not CandidateProfile.objects.exists()
    assert code not in EmailChallenge.objects.get().code_digest
    response = finish(client, headers, code)
    assert response.status_code == 200
    assert response.cookies["resumebot_refresh"]["httponly"]
    account = AccountAccess.objects.get()
    assert not account.user.has_usable_password()
    assert account.email_verified_at
    auth = {"HTTP_AUTHORIZATION": "Bearer " + response.json()["access"]}
    state = client.get("/api/v1/me/", **auth).json()
    assert state["account_status"] == "pending_approval"
    assert not state["can_manage_candidate"]
    with (
        patch("chatbot.services.ai.invoke_candidate_chat") as chat,
        patch(
            "chatbot.services.knowledge_extraction.invoke_fact_extraction"
        ) as extract,
    ):
        for url in (
            "/api/v1/me/profile/",
            "/api/v1/me/facts/",
            "/api/v1/me/documents/",
            "/api/v1/candidates/",
            "/api/v1/candidates/example/chat/",
        ):
            assert client.get(url, **auth).status_code == 403
            assert (
                client.post(
                    url, {}, content_type="application/json", **auth
                ).status_code
                == 403
            )
        chat.assert_not_called()
        extract.assert_not_called()
    assert finish(client, headers, code).status_code == 401
    approve_candidates(None, None, CandidateProfile.objects.all())
    assert client.get("/api/v1/me/profile/", **auth).status_code == 200
    assert client.get("/api/v1/me/", **auth).json()["can_manage_candidate"]
    assert CandidateProfile.objects.get().publication_status == "draft"


def test_recruiter_is_active_without_candidate_permissions(settings):
    settings.PUBLIC_REGISTRATION_ENABLED = True
    client = Client(enforce_csrf_checks=True)
    headers, code = begin(client, role="recruiter")
    response = finish(client, headers, code)
    auth = {"HTTP_AUTHORIZATION": "Bearer " + response.json()["access"]}
    assert client.get("/api/v1/me/", **auth).json()["account_status"] == "active"
    assert client.get("/api/v1/candidates/", **auth).status_code == 200
    assert (
        client.post(
            "/api/v1/me/profile/",
            {"name": "Escalation"},
            content_type="application/json",
            **auth,
        ).status_code
        == 403
    )
    assert client.get("/api/v1/me/documents/", **auth).status_code == 403
    assert not CandidateProfile.objects.exists()


def test_codes_expire_lock_and_cannot_be_reused(settings):
    settings.PUBLIC_REGISTRATION_ENABLED = True
    request_code(email="code@example.test", name="Example", role="recruiter")
    challenge = EmailChallenge.objects.get()
    original = challenge.code_digest
    request_code(email="code@example.test", name="Changed", role="candidate")
    challenge.refresh_from_db()
    assert challenge.code_digest == original
    code = re.search(r"\b\d{6}\b", mail.outbox[-1].body).group()
    for _ in range(5):
        assert verify_code(email=challenge.email, code="bad") is None
    assert verify_code(email=challenge.email, code=code) is None
    challenge.attempts = 0
    challenge.expires_at = timezone.now() - timedelta(seconds=1)
    challenge.save()
    assert verify_code(email=challenge.email, code=code) is None


def test_code_requires_csrf_and_registration_flag(settings):
    settings.PUBLIC_REGISTRATION_ENABLED = False
    client = Client(enforce_csrf_checks=True)
    assert (
        client.post(
            "/api/v1/auth/code/request/",
            {"email": "x@example.test"},
            content_type="application/json",
        ).status_code
        == 403
    )
    csrf = client.get("/api/v1/auth/csrf/").json()["csrf_token"]
    response = client.post(
        "/api/v1/auth/code/request/",
        {"email": "x@example.test", "name": "Name", "role": "candidate"},
        content_type="application/json",
        HTTP_X_CSRFTOKEN=csrf,
    )
    assert response.status_code == 200
    assert not getattr(mail, "outbox", [])
    assert not AccountAccess.objects.exists()


def test_upload_is_private_and_failure_keeps_profile(
    client, published_candidate, settings
):
    settings.CANDIDATE_UPLOADS_ENABLED = True
    client.force_login(published_candidate.user)
    response = client.post("/api/v1/me/documents/", {"document": make_docx()})
    assert response.status_code == 201
    data = response.json()
    assert data["processing_status"] == "processed"
    assert not {"file", "extracted_text", "candidate"} & data.keys()
    assert CandidateDocument.objects.get().extracted_text
    assert not CandidateFact.objects.exists()
    settings.CANDIDATE_UPLOADS_ENABLED = False
    assert (
        client.post("/api/v1/me/documents/", {"document": make_docx()}).status_code
        == 503
    )
    assert CandidateDocument.objects.count() == 1


def test_document_isolation_and_disabled_extraction(
    client, published_candidate, other_user, settings
):
    settings.CANDIDATE_UPLOADS_ENABLED = True
    client.force_login(published_candidate.user)
    doc_id = client.post("/api/v1/me/documents/", {"document": make_docx()}).json()[
        "id"
    ]
    settings.AI_ENABLED = False
    with patch(
        "chatbot.services.knowledge_extraction.invoke_fact_extraction"
    ) as provider:
        assert client.post(f"/api/v1/me/documents/{doc_id}/extract/").status_code == 503
        provider.assert_not_called()
    CandidateProfile.objects.create(user=other_user, name="Other", status="active")
    client.force_login(other_user)
    assert client.get(f"/api/v1/me/documents/{doc_id}/").status_code == 404
    with patch("chatbot.api.views.extract_candidate_facts") as provider:
        assert client.post(f"/api/v1/me/documents/{doc_id}/extract/").status_code == 404
        provider.assert_not_called()


def test_admin_denies_staff_and_superuser_has_all_areas(
    client, django_user_model, settings
):
    staff = django_user_model.objects.create_user(username="staff", is_staff=True)
    client.force_login(staff)
    assert client.get("/admin/").status_code == 302
    root = django_user_model.objects.create_superuser(
        username="root", email="root@example.test", password="admin-only"
    )
    client.force_login(root)
    assert client.get("/admin/").status_code == 200
    assert client.get("/api/v1/candidates/").status_code == 200
    assert client.get("/api/v1/me/").json()["can_manage_candidate"]
    assert (
        client.post(
            "/api/v1/me/profile/", {"name": "Root"}, content_type="application/json"
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/api/v1/me/profile/", {"name": "Again"}, content_type="application/json"
        ).status_code
        == 409
    )
    settings.CANDIDATE_UPLOADS_ENABLED = False
    assert (
        client.post("/api/v1/me/documents/", {"document": make_docx()}).status_code
        == 503
    )
    assert admin.site.has_permission(type("Request", (), {"user": root})())
    token = RefreshToken.for_user(root)
    assert (
        client.get(
            "/api/v1/me/", HTTP_AUTHORIZATION=f"Bearer {token.access_token}"
        ).status_code
        == 200
    )


def test_existing_role_cannot_be_changed_through_registration(recruiter):
    request_code(
        email=recruiter.email.upper(), name="Candidate Attempt", role="candidate"
    )
    code = re.search(r"\b\d{6}\b", mail.outbox[-1].body).group()
    assert verify_code(email=recruiter.email, code=code).pk == recruiter.pk
    recruiter.account_access.refresh_from_db()
    assert recruiter.account_access.role == "recruiter"
    assert not CandidateProfile.objects.filter(user=recruiter).exists()


def test_new_superuser_can_sign_in_to_react_with_email_code(django_user_model):
    root = django_user_model.objects.create_superuser(
        username="new-root", email="root@example.test", password="admin-only"
    )
    request_code(email=root.email)
    code = re.search(r"\b\d{6}\b", mail.outbox[-1].body).group()
    assert verify_code(email=root.email, code=code).pk == root.pk
    assert root.is_superuser


@pytest.mark.django_db(transaction=True)
def test_only_one_concurrent_code_verification_succeeds(settings):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from django.db import close_old_connections, connection

    if connection.vendor != "postgresql":
        pytest.skip("Row-lock verification requires PostgreSQL.")
    settings.PUBLIC_REGISTRATION_ENABLED = True
    request_code(
        email="concurrent@example.test", name="Concurrent Example", role="recruiter"
    )
    code = re.search(r"\b\d{6}\b", mail.outbox[-1].body).group()
    barrier = Barrier(2)

    def verify():
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            result = verify_code(email="concurrent@example.test", code=code)
            return result is not None
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(lambda _: verify(), range(2)))
    assert sorted(outcomes) == [False, True]
    assert AccountAccess.objects.filter(email="concurrent@example.test").count() == 1
