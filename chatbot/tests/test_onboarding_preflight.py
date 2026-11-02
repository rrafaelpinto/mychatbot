from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from chatbot.models import AccountAccess, EmailChallenge

pytestmark = pytest.mark.django_db


@pytest.fixture
def ready(settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    settings.EMAIL_HOST = "smtp.example.test"
    settings.EMAIL_HOST_USER = "smtp-user"
    settings.EMAIL_HOST_PASSWORD = "smtp-secret"
    settings.EMAIL_TIMEOUT = 10
    settings.DEFAULT_FROM_EMAIL = "ResumeBot <accounts@example.test>"
    settings.FRONTEND_URL = "https://app.example.test"
    settings.CORS_ALLOWED_ORIGINS = [settings.FRONTEND_URL]
    settings.CSRF_TRUSTED_ORIGINS = [settings.FRONTEND_URL]
    settings.PUBLIC_REGISTRATION_ENABLED = False
    settings.CANDIDATE_UPLOADS_ENABLED = False
    return settings


def test_ready_configuration_does_not_send_mail_or_create_records(ready, recruiter):
    output = StringIO()
    before = AccountAccess.objects.count(), EmailChallenge.objects.count()
    with patch("django.core.mail.backends.smtp.EmailBackend.open") as smtp:
        call_command("check_onboarding", stdout=output)
        smtp.assert_not_called()
    assert before == (AccountAccess.objects.count(), EmailChallenge.objects.count())
    assert "configuration checks passed" in output.getvalue()
    assert "Public registration enabled: False" in output.getvalue()
    assert "smtp-secret" not in output.getvalue()
    assert recruiter.email not in output.getvalue()


@pytest.mark.parametrize("backend", ["console", "locmem", "dummy"])
def test_non_smtp_backends_cannot_pass_activation_preflight(ready, backend):
    ready.EMAIL_BACKEND = f"django.core.mail.backends.{backend}.EmailBackend"
    with pytest.raises(CommandError, match="EMAIL_BACKEND"):
        call_command("check_onboarding", stdout=StringIO())


@pytest.mark.parametrize(
    "origin",
    [
        "http://app.example.test",
        "https://localhost",
        "https://user:password@app.example.test",
        "https://app.example.test/path",
        "https://app.example.test?token=secret",
    ],
)
def test_frontend_must_be_an_exact_https_origin(ready, origin):
    ready.FRONTEND_URL = origin
    with pytest.raises(CommandError, match="FRONTEND_URL") as error:
        call_command("check_onboarding", stdout=StringIO())
    assert origin not in str(error.value)


def test_missing_smtp_and_origin_settings_are_reported_together(ready):
    ready.EMAIL_HOST = ""
    ready.EMAIL_HOST_PASSWORD = ""
    ready.DEFAULT_FROM_EMAIL = "noreply@localhost"
    ready.CORS_ALLOWED_ORIGINS = []
    ready.CSRF_TRUSTED_ORIGINS = []
    with pytest.raises(CommandError) as error:
        call_command("check_onboarding", stdout=StringIO())
    for name in (
        "EMAIL_HOST",
        "EMAIL_HOST_PASSWORD",
        "DEFAULT_FROM_EMAIL",
        "API_CORS_ALLOWED_ORIGINS",
        "DJANGO_CSRF_TRUSTED_ORIGINS",
    ):
        assert name in str(error.value)


def test_duplicates_are_detected_before_account_access_migration(
    ready, django_user_model
):
    django_user_model.objects.create_user(username="first", email="Same@example.test")
    django_user_model.objects.create_user(
        username="second", email="\t same@example.test \n"
    )
    assert not AccountAccess.objects.exists()
    with pytest.raises(
        CommandError, match="Duplicate normalized email groups: 1"
    ) as error:
        call_command("check_onboarding", stdout=StringIO())
    assert "same@example.test" not in str(error.value).lower()
    assert not AccountAccess.objects.exists()


def test_missing_email_is_reported_without_exposing_identity(ready, django_user_model):
    django_user_model.objects.create_user(username="no-email")
    output = StringIO()
    call_command("check_onboarding", stdout=output)
    assert "Accounts without email: 1" in output.getvalue()
    assert "no-email" not in output.getvalue()


def test_upload_roots_cannot_overlap_or_use_checkout(ready, tmp_path):
    ready.MEDIA_ROOT = tmp_path / "public"
    ready.PRIVATE_MEDIA_ROOT = ready.MEDIA_ROOT / "private"
    with pytest.raises(CommandError, match="non-nested"):
        call_command("check_onboarding", uploads=True, stdout=StringIO())
    ready.PRIVATE_MEDIA_ROOT = ready.BASE_DIR / "private_media"
    with pytest.raises(CommandError, match="outside the application checkout"):
        call_command("check_onboarding", uploads=True, stdout=StringIO())
    ready.PRIVATE_MEDIA_ROOT = tmp_path / "private"
    call_command("check_onboarding", uploads=True, stdout=StringIO())
    assert not ready.MEDIA_ROOT.exists()
    assert not ready.PRIVATE_MEDIA_ROOT.exists()


@pytest.mark.parametrize("timeout", [None, 0, -1, float("inf"), float("nan")])
def test_timeout_must_be_finite_and_positive(ready, timeout):
    ready.EMAIL_TIMEOUT = timeout
    with pytest.raises(CommandError, match="EMAIL_TIMEOUT"):
        call_command("check_onboarding", stdout=StringIO())
