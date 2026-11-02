import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac

from chatbot.models import AccountAccess, CandidateProfile, EmailChallenge


class CodeUnavailable(Exception):
    """An email challenge cannot be sent."""


def normalize_email(email):
    return email.strip().lower()


def digest_code(email, code):
    return salted_hmac("email-login", email + ":" + code).hexdigest()


def resolve_account(email):
    access = AccountAccess.objects.filter(email=email).first()
    if access:
        return access
    users = list(get_user_model().objects.filter(email__iexact=email)[:2])
    if len(users) != 1:
        return None
    user = users[0]
    access, _ = AccountAccess.objects.get_or_create(
        user=user,
        defaults={
            "email": email,
            "role": "candidate"
            if CandidateProfile.objects.filter(user=user).exists()
            else "recruiter",
        },
    )
    return access if access.email == email else None


def request_code(*, email, name="", role=""):
    email = normalize_email(email)
    now = timezone.now()
    code = f"{secrets.randbelow(1_000_000):06d}"
    with transaction.atomic():
        challenge, _ = EmailChallenge.objects.get_or_create(
            email=email,
            defaults={
                "code_digest": "",
                "expires_at": now,
                "sent_at": now - timedelta(days=1),
            },
        )
        challenge = EmailChallenge.objects.select_for_update().get(pk=challenge.pk)
        if (
            now - challenge.sent_at
        ).total_seconds() < settings.EMAIL_CODE_RESEND_SECONDS:
            return
        known = resolve_account(email) is not None
        if not known and not (name and role and settings.PUBLIC_REGISTRATION_ENABLED):
            return
        challenge.code_digest = digest_code(email, code)
        challenge.expires_at = now + timedelta(seconds=settings.EMAIL_CODE_TTL_SECONDS)
        challenge.sent_at = now
        challenge.attempts = 0
        challenge.consumed_at = None
        challenge.registration_name = name if not known else ""
        challenge.registration_role = role if not known else ""
        challenge.save()
        try:
            send_mail(
                "Your ResumeBot sign-in code",
                f"Your code is {code}. It expires in {settings.EMAIL_CODE_TTL_SECONDS // 60} minutes. If you did not request it, ignore this email.",
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=False,
            )
        except Exception as exc:
            raise CodeUnavailable("Email delivery is temporarily unavailable.") from exc


def verify_code(*, email, code):
    email = normalize_email(email)
    now = timezone.now()
    with transaction.atomic():
        challenge = (
            EmailChallenge.objects.select_for_update().filter(email=email).first()
        )
        if (
            not challenge
            or challenge.consumed_at
            or challenge.expires_at <= now
            or challenge.attempts >= settings.EMAIL_CODE_MAX_ATTEMPTS
        ):
            return None
        challenge.attempts += 1
        challenge.save(update_fields=["attempts"])
        if not constant_time_compare(challenge.code_digest, digest_code(email, code)):
            return None
        access = (
            AccountAccess.objects.select_related("user").filter(email=email).first()
        )
        if access is None:
            if (
                not settings.PUBLIC_REGISTRATION_ENABLED
                or not challenge.registration_role
            ):
                return None
            user = get_user_model()(
                username="user-" + secrets.token_hex(16),
                email=email,
                first_name=challenge.registration_name[:150],
            )
            user.set_unusable_password()
            user.save()
            access = AccountAccess.objects.create(
                user=user, email=email, role=challenge.registration_role
            )
            if access.role == AccountAccess.Role.CANDIDATE:
                CandidateProfile.objects.create(
                    user=user, name=challenge.registration_name
                )
        if not access.user.is_active:
            return None
        access.email_verified_at = now
        access.save(update_fields=["email_verified_at"])
        challenge.consumed_at = now
        challenge.save(update_fields=["consumed_at"])
        return access.user
