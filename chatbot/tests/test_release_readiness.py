import os
import subprocess
import sys
from io import BytesIO
from unittest.mock import patch

import pytest
from django.core.exceptions import PermissionDenied
from django.db import DatabaseError
from django.urls import reverse

from chatbot.forms import CandidateProfileForm
from chatbot.storage import DisabledPublicUploadStorage, PrivateDocumentStorage


@pytest.mark.django_db
def test_database_readiness_endpoint_is_public_and_does_not_cache(client):
    response = client.get(reverse("healthz"))
    assert response.status_code == 200
    assert response.content == b"ok"
    assert response["Cache-Control"] == "no-store"

    head = client.head(reverse("healthz"))
    assert head.status_code == 200
    assert client.post(reverse("healthz")).status_code == 405


def test_readiness_returns_generic_503_when_database_unavailable(client):
    with patch("chatbot.views.connection.cursor", side_effect=DatabaseError):
        response = client.get(reverse("healthz"))
    assert response.status_code == 503
    assert response.content == b"unavailable"
    assert response["Cache-Control"] == "no-store"


def test_upload_controls_disable_both_fields_and_ignore_posted_files(settings):
    settings.CANDIDATE_UPLOADS_ENABLED = False
    form = CandidateProfileForm(
        data={"name": "Safe profile", "professional_summary": "Public demo"}
    )
    assert form.fields["image"].disabled
    assert form.fields["document"].disabled
    assert form.is_valid()
    assert not form.cleaned_data["document"]


def test_disabled_media_storages_reject_writes(settings, tmp_path):
    settings.CANDIDATE_UPLOADS_ENABLED = False
    public = DisabledPublicUploadStorage(location=tmp_path / "public")
    with pytest.raises(PermissionDenied):
        public.save("test.txt", BytesIO(b"must not persist"))
    private = PrivateDocumentStorage()
    with pytest.raises(PermissionDenied):
        private.save("test.txt", BytesIO(b"must not persist"))


def test_closed_signup_is_not_shown_in_public_navigation(client, settings):
    settings.PUBLIC_REGISTRATION_ENABLED = False
    response = client.get(reverse("about"))
    assert response.status_code == 200
    assert b"Sign up</a>" not in response.content


def production_settings_subprocess(extra_env, code):
    env = dict(os.environ)
    env.update(
        {
            "DJANGO_SETTINGS_MODULE": "mychatbot.settings",
            "RESUMEBOT_ENV": "production",
            "DJANGO_DEBUG": "false",
            "DJANGO_SECRET_KEY": "production-test-secret-" + "a" * 45,
            "DJANGO_ALLOWED_HOSTS": "resumebot.example.com",
        }
    )
    env.pop("DATABASE_URL", None)
    env.pop("CANDIDATE_UPLOADS_ENABLED", None)
    env.pop("PUBLIC_REGISTRATION_ENABLED", None)
    env.pop("GUEST_CHAT_ENABLED", None)
    env.update(extra_env)
    return subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def test_production_defaults_are_closed_and_registration_route_absent():
    result = production_settings_subprocess(
        {},
        (
            "import django; django.setup(); "
            "from django.conf import settings; "
            "from django.urls import reverse, NoReverseMatch; "
            "assert not settings.PUBLIC_REGISTRATION_ENABLED; "
            "assert not settings.CANDIDATE_UPLOADS_ENABLED; "
            "assert not settings.GUEST_CHAT_ENABLED; "
            "assert not settings.AI_ENABLED; "
            "assert settings.STORAGES['default']['BACKEND'] == "
            "'chatbot.storage.DisabledPublicUploadStorage'; "
            "try:\n reverse('django_registration_register')\n"
            "except NoReverseMatch:\n pass\n"
            "else:\n raise AssertionError('signup route unexpectedly active')"
        ),
    )
    assert result.returncode == 0, result.stderr


def test_production_database_url_can_be_parsed_without_db_connection():
    result = production_settings_subprocess(
        {
            "DATABASE_URL": (
                "postgresql://resume_user:password@db.internal:5432/resumebot"
                "?sslmode=require"
            )
        },
        (
            "from django.conf import settings; "
            "db=settings.DATABASES['default']; "
            "assert db['HOST']=='db.internal'; "
            "assert db['NAME']=='resumebot'; "
            "assert db['OPTIONS']['sslmode']=='require'"
        ),
    )
    assert result.returncode == 0, result.stderr


def test_production_uploads_require_explicit_distinct_persistent_paths():
    result = production_settings_subprocess(
        {"CANDIDATE_UPLOADS_ENABLED": "true"},
        "import mychatbot.settings",
    )
    assert result.returncode != 0
    assert "distinct persistent public/private media roots" in result.stderr


def test_production_guest_chat_requires_a_scheduled_retention_cleanup():
    result = production_settings_subprocess(
        {
            "GUEST_CHAT_ENABLED": "true",
            "GUEST_TURNSTILE_SITE_KEY": "synthetic-site",
            "GUEST_TURNSTILE_SECRET_KEY": "synthetic-secret",
            "GUEST_IP_HASH_SECRET": "synthetic-hash",
        },
        "import mychatbot.settings",
    )
    assert result.returncode != 0
    assert "active guest session cleanup schedule" in result.stderr
