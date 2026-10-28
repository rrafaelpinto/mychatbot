from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from chatbot.models import AIUsageEvent, CandidateProfile


class AIQuotaExceeded(Exception):
    """An AI request exceeded its operation limits."""


def admit_ai_operation(
    *, identity_id: int, candidate_id: int, operation: str
) -> AIUsageEvent:
    """Atomically enforce limits and record an admitted paid operation."""
    limits = settings.AI_USAGE_LIMITS[operation]
    now = timezone.now()
    minute_start = now - timedelta(seconds=60)
    day_start = now - timedelta(hours=24)

    with transaction.atomic():
        get_user_model().objects.select_for_update().get(pk=identity_id)
        CandidateProfile.objects.select_for_update().get(pk=candidate_id)

        events = AIUsageEvent.objects.filter(operation=operation)
        if (
            events.filter(
                initiated_by_id=identity_id, created_at__gte=minute_start
            ).count()
            >= limits["identity_per_minute"]
        ):
            raise AIQuotaExceeded("AI rate limit exceeded.")

        if (
            events.filter(
                initiated_by_id=identity_id, created_at__gte=day_start
            ).count()
            >= limits["identity_per_day"]
        ):
            raise AIQuotaExceeded("AI identity quota exceeded.")

        if (
            events.filter(candidate_id=candidate_id, created_at__gte=day_start).count()
            >= limits["candidate_per_day"]
        ):
            raise AIQuotaExceeded("AI candidate quota exceeded.")

        return AIUsageEvent.objects.create(
            initiated_by_id=identity_id,
            candidate_id=candidate_id,
            operation=operation,
            model=settings.OPENAI_MODEL,
        )
