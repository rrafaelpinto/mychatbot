from collections import Counter
from email.utils import parseaddr
from math import isfinite
from pathlib import Path
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email
from django.db import DatabaseError

from chatbot.services.accounts import normalize_email


class Command(BaseCommand):
    help = "Check onboarding configuration and account emails without sending mail or changing data."

    def add_arguments(self, parser):
        parser.add_argument(
            "--uploads",
            action="store_true",
            help="Also validate media root configuration before enabling uploads.",
        )

    def handle(self, *args, **options):
        problems = []
        if settings.EMAIL_BACKEND != "django.core.mail.backends.smtp.EmailBackend":
            problems.append(
                "EMAIL_BACKEND must use the SMTP backend for external users."
            )
        if not settings.EMAIL_HOST.strip():
            problems.append("EMAIL_HOST is required.")
        if settings.EMAIL_HOST_USER and not settings.EMAIL_HOST_PASSWORD:
            problems.append(
                "EMAIL_HOST_PASSWORD is required when EMAIL_HOST_USER is set."
            )
        if (
            not settings.EMAIL_TIMEOUT
            or not isfinite(settings.EMAIL_TIMEOUT)
            or settings.EMAIL_TIMEOUT <= 0
        ):
            problems.append("EMAIL_TIMEOUT must be a positive number of seconds.")
        sender = parseaddr(settings.DEFAULT_FROM_EMAIL)[1]
        try:
            validate_email(sender)
            if sender.rsplit("@", 1)[1].lower() in {
                "localhost",
                "example.com",
                "example.org",
                "example.net",
            }:
                raise ValidationError("Placeholder sender.")
        except (ValidationError, IndexError):
            problems.append(
                "DEFAULT_FROM_EMAIL must be a valid non-placeholder sender."
            )

        try:
            frontend = urlsplit(settings.FRONTEND_URL)
            valid_origin = (
                frontend.scheme == "https"
                and bool(frontend.hostname)
                and not frontend.username
                and not frontend.password
                and not frontend.query
                and not frontend.fragment
                and frontend.path in {"", "/"}
                and frontend.hostname not in {"localhost", "127.0.0.1", "::1"}
            )
            if not valid_origin:
                raise ValueError("Invalid frontend origin.")
            origin = f"{frontend.scheme}://{frontend.netloc}"
            if origin not in settings.CORS_ALLOWED_ORIGINS:
                problems.append(
                    "FRONTEND_URL must be included in API_CORS_ALLOWED_ORIGINS."
                )
            if origin not in settings.CSRF_TRUSTED_ORIGINS:
                problems.append(
                    "FRONTEND_URL must be included in DJANGO_CSRF_TRUSTED_ORIGINS."
                )
        except ValueError:
            problems.append(
                "FRONTEND_URL must be an HTTPS origin without credentials, path, query or fragment."
            )

        if options["uploads"] or settings.CANDIDATE_UPLOADS_ENABLED:
            public = Path(settings.MEDIA_ROOT)
            private = Path(settings.PRIVATE_MEDIA_ROOT)
            if not public.is_absolute() or not private.is_absolute():
                problems.append(
                    "Public and private media roots must be absolute paths."
                )
            public, private = public.resolve(), private.resolve()
            if (
                public == private
                or public in private.parents
                or private in public.parents
            ):
                problems.append(
                    "Public and private media roots must be separate, non-nested directories."
                )
            base = Path(settings.BASE_DIR).resolve()
            if (
                public == base
                or private == base
                or base in public.parents
                or base in private.parents
            ):
                problems.append(
                    "Media roots must be outside the application checkout; configure persistent storage on the host."
                )
            self.stdout.write(
                "Media persistence and permissions still require verification on the host."
            )

        try:
            emails = Counter(
                normalize_email(email or "")
                for email in get_user_model()
                .objects.values_list("email", flat=True)
                .iterator()
            )
            duplicates = sum(
                1 for email, total in emails.items() if email and total > 1
            )
            if duplicates:
                problems.append(
                    f"Duplicate normalized email groups: {duplicates}. Resolve them before migrating account access."
                )
            missing = emails.get("", 0)
            if missing:
                self.stdout.write(
                    f"Accounts without email: {missing}. They cannot use email-code sign-in until an administrator supplies a unique email."
                )
        except DatabaseError as exc:
            raise CommandError(
                "Cannot inspect account emails. Check database connectivity and the existing auth schema."
            ) from exc

        self.stdout.write(
            f"Public registration enabled: {settings.PUBLIC_REGISTRATION_ENABLED}."
        )
        self.stdout.write(f"Uploads enabled: {settings.CANDIDATE_UPLOADS_ENABLED}.")
        if problems:
            raise CommandError(
                "Onboarding configuration is not ready:\n"
                + "\n".join(f"- {problem}" for problem in problems)
            )
        self.stdout.write(
            self.style.SUCCESS(
                "Onboarding configuration checks passed. SMTP delivery, DNS/TLS, storage durability and the browser flow still require a controlled verification."
            )
        )
