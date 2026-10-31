import hashlib
import hmac
import ipaddress
import json
from datetime import timedelta
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import UUID

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from chatbot.models import GuestChatSession, GuestOrigin


class GuestAccessDenied(Exception):
    """An anonymous visitor cannot start or reuse a chat session."""


class GuestVerificationUnavailable(Exception):
    """The bot verification provider cannot validate the challenge."""


def origin_digest(request) -> str:
    """Hash the client IP, accepting forwarded headers only from trusted proxies."""
    raw_ip = request.META.get("REMOTE_ADDR", "")
    try:
        remote = ipaddress.ip_address(raw_ip)
        trusted = {
            ipaddress.ip_address(value) for value in settings.GUEST_TRUSTED_PROXY_IPS
        }
        if remote in trusted:
            forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
            for segment in reversed(forwarded.split(",")):
                if not segment.strip():
                    continue
                address = ipaddress.ip_address(segment.strip())
                if address not in trusted:
                    remote = address
                    break
    except ValueError as exc:
        raise GuestAccessDenied("Invalid visitor origin.") from exc

    return hmac.new(
        settings.GUEST_IP_HASH_SECRET.encode(),
        remote.packed,
        hashlib.sha256,
    ).hexdigest()


def verify_turnstile(token: str, *, hostname: str) -> bool:
    """Validate a single-use Turnstile token with Cloudflare Siteverify."""
    if not token or len(token) > 2048:
        return False

    payload = urlencode(
        {"secret": settings.GUEST_TURNSTILE_SECRET_KEY, "response": token}
    ).encode()
    request = Request(
        "https://challenges.cloudflare.com/turnstile/v0/siteverify",
        data=payload,
        method="POST",
    )
    try:
        with urlopen(request, timeout=settings.GUEST_TURNSTILE_TIMEOUT) as response:
            result = json.load(response)
    except (TimeoutError, HTTPError, URLError, ValueError) as exc:


    return (
        result.get("success") is True
        and result.get("hostname", "").lower() == hostname.lower()
        and result.get("action") == "candidate_chat"
    )


def current_guest_session(request, candidate, digest):
    """Resolve an active browser session without trusting a client-supplied identity."""
    value = request.session.get("guest_chat_session")
    if not value:
        return None
    try:
        session_id = UUID(str(value))
    except (ValueError, TypeError):
        return None
    return GuestChatSession.objects.filter(
        pk=session_id,
        candidate=candidate,
        origin__digest=digest,
        expires_at__gt=timezone.now(),
    ).first()


def create_guest_session(*, candidate, digest):
    """Create a verified session under the origin's concurrency lock."""
    now = timezone.now()
    with transaction.atomic():
        origin, _ = GuestOrigin.objects.get_or_create(digest=digest)
        origin = GuestOrigin.objects.select_for_update().get(pk=origin.pk)
        recent_sessions = GuestChatSession.objects.filter(
            origin=origin, created_at__gte=now - timedelta(days=1)
        ).count()
        if recent_sessions >= settings.GUEST_SESSIONS_PER_ORIGIN_PER_DAY:
            raise GuestAccessDenied("Too many guest sessions from this origin.")

        return GuestChatSession.objects.create(
            candidate=candidate,
            origin=origin,
            expires_at=now + timedelta(hours=settings.GUEST_SESSION_HOURS),
        )


def release_guest_operation(*, session_id, usage_id):
    """Release only the lease owned by this operation."""
    GuestChatSession.objects.filter(pk=session_id, active_usage_id=usage_id).update(
        active_usage=None, in_flight_until=None
    )
