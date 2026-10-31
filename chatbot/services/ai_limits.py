from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from chatbot.models import AIProjectBudget, AIUsageEvent, CandidateProfile, GuestChatSession, GuestOrigin
from chatbot.services.ai_budget import reserve_project_budget


class AIDuplicateRequest(Exception):
    """An AI request key has already been used."""


class AIQuotaExceeded(Exception):
    """An AI request exceeded its operation limits."""


def admit_ai_operation(
    *,
    identity_id: int | None = None,
    guest_session_id=None,
    candidate_id: int,
    operation: str,
    idempotency_key: str | None = None,
) -> AIUsageEvent:
    """Atomically enforce limits and record an admitted paid operation."""
    limits = settings.AI_USAGE_LIMITS[operation]
    now = timezone.now()
    minute_start = now - timedelta(seconds=60)
    day_start = now - timedelta(hours=24)

    if (identity_id is None) == (guest_session_id is None):
        raise ValueError("Exactly one AI identity is required.")

    with transaction.atomic():
        guest = None
        origin = None
        if guest_session_id is not None:
            guest_id = GuestChatSession.objects.only("origin_id").get(
                pk=guest_session_id
            )
            origin = GuestOrigin.objects.select_for_update().get(
                pk=guest_id.origin_id
            )
            guest = GuestChatSession.objects.select_for_update().get(
                pk=guest_session_id
            )
            if guest.origin_id != origin.pk or guest.candidate_id != candidate_id:
                raise AIQuotaExceeded("Invalid guest session.")
            if guest.expires_at <= now:
                raise AIQuotaExceeded("Guest session expired.")
            if guest.in_flight_until and guest.in_flight_until > now:
                raise AIQuotaExceeded("A guest request is already in progress.")
        else:
            get_user_model().objects.select_for_update().get(pk=identity_id)

        CandidateProfile.objects.select_for_update().get(pk=candidate_id)
        events = AIUsageEvent.objects.filter(operation=operation)

        if guest is not None:
            from datetime import date

            budget, _ = AIProjectBudget.objects.get_or_create(
                pk=1,
                defaults={"daily_window": now.date(), "monthly_window": date(now.year, now.month, 1)},
            )
            AIProjectBudget.objects.select_for_update().get(pk=budget.pk)
            session_events = events.filter(guest_session=guest)
            origin_events = events.filter(guest_origin=origin)

            if session_events.count() >= settings.GUEST_SESSION_QUESTION_LIMIT:
                raise AIQuotaExceeded("Guest session question limit exceeded.")
            if origin_events.filter(created_at__gte=minute_start).count() >= settings.GUEST_ORIGIN_PER_MINUTE:
                raise AIQuotaExceeded("Guest origin rate limit exceeded.")
            if origin_events.filter(created_at__gte=day_start).count() >= settings.GUEST_ORIGIN_PER_DAY:
                raise AIQuotaExceeded("Guest origin daily limit exceeded.")
            if events.filter(guest_origin__isnull=False, created_at__gte=day_start).count() >= settings.GUEST_GLOBAL_PER_DAY:
                raise AIQuotaExceeded("Guest daily capacity exhausted.")
            duplicate = session_events
        else:
            if events.filter(
                initiated_by_id=identity_id, created_at__gte=minute_start
            ).count() >= limits["identity_per_minute"]:
                raise AIQuotaExceeded("AI rate limit exceeded.")
            if events.filter(
                initiated_by_id=identity_id, created_at__gte=day_start
            ).count() >= limits["identity_per_day"]:
                raise AIQuotaExceeded("AI identity quota exceeded.")
            duplicate = events.filter(initiated_by_id=identity_id)

        if idempotency_key is not None and duplicate.filter(
            candidate_id=candidate_id, idempotency_key=idempotency_key
        ).exists():
            raise AIDuplicateRequest("This AI request has already been submitted.")

        if events.filter(
            candidate_id=candidate_id, created_at__gte=day_start
        ).count() >= limits["candidate_per_day"]:
            raise AIQuotaExceeded("AI candidate quota exceeded.")

        usage = AIUsageEvent.objects.create(
            initiated_by_id=identity_id,
            guest_session=guest,
            guest_origin=origin,
            candidate_id=candidate_id,
            operation=operation,
            model=settings.OPENAI_MODEL,
            idempotency_key=idempotency_key,
        )
        reserve_project_budget(usage=usage, now=now)
        if guest is not None:
            guest.active_usage = usage
            guest.in_flight_until = now + timedelta(
                seconds=max(90, settings.OPENAI_TIMEOUT_SECONDS * 3)
            )
            guest.save(update_fields=["active_usage", "in_flight_until"])
        return usage
