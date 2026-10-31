from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from chatbot.models import GuestChatSession, GuestOrigin


class Command(BaseCommand):
    """Delete expired guest conversation content and unused origin identifiers."""

    help = "Remove guest sessions and messages after the configured retention period."

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(
            days=settings.GUEST_CONVERSATION_RETENTION_DAYS
        )
        with transaction.atomic():
            sessions = GuestChatSession.objects.filter(created_at__lt=cutoff)
            count = sessions.count()
            sessions.delete()
            GuestOrigin.objects.filter(
                sessions__isnull=True, created_at__lt=cutoff
            ).delete()
        self.stdout.write(f"Removed {count} expired guest sessions.")
