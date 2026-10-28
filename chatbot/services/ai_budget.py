from datetime import UTC, date
from decimal import ROUND_CEILING, Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from chatbot.models import AIProjectBudget, AIUsageEvent


class AIBudgetExceeded(Exception):
    """A paid operation cannot reserve project budget."""


def reservation_micro_usd(model: str) -> int:
    """Return a conservative maximum cost for a configured model call."""
    if model != "gpt-4o-mini":
        raise AIBudgetExceeded("AI model pricing is not configured.")
    input_rate = Decimal(str(settings.AI_INPUT_USD_PER_MILLION))
    output_rate = Decimal(str(settings.AI_OUTPUT_USD_PER_MILLION))
    if input_rate <= 0 or output_rate <= 0:
        raise AIBudgetExceeded("AI model pricing is not configured.")
    micro_usd = (
        Decimal(settings.AI_MAX_INPUT_TOKENS) * input_rate
        + Decimal(settings.AI_MAX_OUTPUT_TOKENS) * output_rate
    )
    return int(micro_usd.to_integral_value(rounding=ROUND_CEILING))


def reserve_project_budget(*, usage: AIUsageEvent, now=None) -> None:
    """Reserve both UTC calendar windows while holding the project budget lock."""
    now = now or timezone.now()
    today = now.date()
    month = date(today.year, today.month, 1)
    amount = reservation_micro_usd(usage.model)
    daily_cap = int(
        (Decimal(str(settings.AI_DAILY_BUDGET_USD)) * 1_000_000).to_integral_value()
    )
    monthly_cap = int(
        (Decimal(str(settings.AI_MONTHLY_BUDGET_USD)) * 1_000_000).to_integral_value()
    )
    if daily_cap <= 0 or monthly_cap <= 0:
        raise AIBudgetExceeded("AI project budget is unavailable.")

    with transaction.atomic():
        budget, _ = AIProjectBudget.objects.get_or_create(
            pk=1,
            defaults={"daily_window": today, "monthly_window": month},
        )
        budget = AIProjectBudget.objects.select_for_update().get(pk=budget.pk)
        if budget.daily_window != today:
            budget.daily_window = today
            budget.daily_reserved_micro_usd = 0
        if budget.monthly_window != month:
            budget.monthly_window = month
            budget.monthly_reserved_micro_usd = 0

        if (
            budget.daily_reserved_micro_usd + amount > daily_cap
            or budget.monthly_reserved_micro_usd + amount > monthly_cap
        ):
            raise AIBudgetExceeded("AI project budget exhausted.")

        budget.daily_reserved_micro_usd += amount
        budget.monthly_reserved_micro_usd += amount
        budget.save()
        usage.reserved_micro_usd = amount
        usage.save(update_fields=["reserved_micro_usd"])


def settle_usage(*, usage_id: int) -> None:
    """Settle a successful call once; keep full reserve if usage is unknown."""
    with transaction.atomic():
        budget = AIProjectBudget.objects.select_for_update().get(pk=1)
        usage = AIUsageEvent.objects.select_for_update().get(pk=usage_id)
        if (
            usage.settled_at is not None
            or usage.status != AIUsageEvent.Status.SUCCEEDED
        ):
            return
        if usage.input_tokens is None or usage.output_tokens is None:
            return
        if usage.model != "gpt-4o-mini":
            return

        input_rate = Decimal(str(settings.AI_INPUT_USD_PER_MILLION))
        output_rate = Decimal(str(settings.AI_OUTPUT_USD_PER_MILLION))
        if input_rate <= 0 or output_rate <= 0:
            return

        actual = int(
            (
                Decimal(usage.input_tokens) * input_rate
                + Decimal(usage.output_tokens) * output_rate
            ).to_integral_value(rounding=ROUND_CEILING)
        )
        # An unexpectedly expensive request is never refunded.
        credit = max(0, usage.reserved_micro_usd - actual)
        admitted_date = usage.created_at.astimezone(UTC).date()
        admitted_month = date(admitted_date.year, admitted_date.month, 1)
        if budget.daily_window == admitted_date:
            budget.daily_reserved_micro_usd = max(
                0, budget.daily_reserved_micro_usd - credit
            )
        if budget.monthly_window == admitted_month:
            budget.monthly_reserved_micro_usd = max(
                0, budget.monthly_reserved_micro_usd - credit
            )
        budget.save(
            update_fields=["daily_reserved_micro_usd", "monthly_reserved_micro_usd"]
        )
        usage.actual_micro_usd = actual
        usage.settled_at = timezone.now()
        usage.save(update_fields=["actual_micro_usd", "settled_at"])
