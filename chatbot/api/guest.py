"""Session-scoped anonymous Candidate Agent API, backed by existing guest policies."""

from urllib.parse import urlsplit

from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, serializers, views
from rest_framework.response import Response

from chatbot.api.serializers import PublicFactSerializer
from chatbot.models import AIUsageEvent, CandidateProfile, Conversation, Message
from chatbot.services.ai import (
    AILimitExceeded,
    AIRequestAlreadySubmitted,
    AIServiceError,
    AIUnavailable,
    ask_candidate,
    public_evidence,
)
from chatbot.services.guest_chat import (
    GuestAccessDenied,
    GuestVerificationUnavailable,
    create_guest_session,
    current_guest_session,
    origin_digest,
    verify_turnstile,
)


class GuestChatInputSerializer(serializers.Serializer):
    question = serializers.CharField(max_length=1000, trim_whitespace=True)
    turnstile_token = serializers.CharField(
        required=False, allow_blank=True, max_length=2048, write_only=True
    )


class GuestMessageSerializer(serializers.Serializer):
    role = serializers.CharField(read_only=True)
    content = serializers.CharField(read_only=True)
    evidence = PublicFactSerializer(many=True, read_only=True)


class GuestStatusSerializer(serializers.Serializer):
    enabled = serializers.BooleanField(read_only=True)
    guest_verified = serializers.BooleanField(read_only=True)
    turnstile_site_key = serializers.CharField(allow_blank=True, read_only=True)
    remaining = serializers.IntegerField(allow_null=True, read_only=True)
    history = GuestMessageSerializer(many=True, read_only=True)


class GuestAnswerSerializer(serializers.Serializer):
    response = serializers.CharField(read_only=True)
    evidence = PublicFactSerializer(many=True, read_only=True)
    guest_verified = serializers.BooleanField(read_only=True)
    remaining = serializers.IntegerField(read_only=True)


def _no_store(response):
    response["Cache-Control"] = "no-store"
    return response


def _remaining(session):
    return max(
        0,
        settings.GUEST_SESSION_QUESTION_LIMIT
        - AIUsageEvent.objects.filter(
            guest_session=session,
            operation=AIUsageEvent.Operation.CANDIDATE_CHAT,
        ).count(),
    )


def _verified_hostname(request):
    """Accept only the API host or an explicitly configured frontend Origin."""
    origin = request.headers.get("Origin")
    if not origin:
        return request.get_host().split(":")[0]
    own_origin = f"{request.scheme}://{request.get_host()}"
    if origin != own_origin and origin not in settings.CORS_ALLOWED_ORIGINS:
        return None
    parsed = urlsplit(origin)
    if not parsed.hostname or parsed.username or parsed.password:
        return None
    return parsed.hostname


@method_decorator(csrf_protect, name="dispatch")
@extend_schema(tags=["Anonymous Candidate Agent"])
class GuestCandidateChatView(views.APIView):
    """Keep guest session, captcha, budget and evidence enforcement on Django."""

    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    @staticmethod
    def _candidate(slug):
        return get_object_or_404(
            CandidateProfile.objects.publicly_viewable(), slug=slug
        )

    @extend_schema(responses={200: GuestStatusSerializer})
    def get(self, request, slug):
        candidate = self._candidate(slug)
        if not settings.GUEST_CHAT_ENABLED:
            return _no_store(
                Response(
                    {
                        "enabled": False,
                        "guest_verified": False,
                        "turnstile_site_key": "",
                        "remaining": None,
                        "history": [],
                    }
                )
            )
        try:
            digest = origin_digest(request._request)
        except GuestAccessDenied:
            return _no_store(Response({"detail": "Guest access denied."}, status=403))
        guest = current_guest_session(request._request, candidate, digest)
        conversation = (
            Conversation.objects.filter(
                candidate=candidate, guest_session=guest
            ).first()
            if guest
            else None
        )
        history = []
        if conversation:
            for message in conversation.messages.all():
                content = message.content
                evidence = ()
                if message.role == Message.Role.ASSISTANT and message.evidence_fact_ids:
                    evidence = public_evidence(candidate, message.evidence_fact_ids)
                    if evidence is None:
                        content = "This answer is no longer available because its evidence changed."
                        evidence = ()
                history.append(
                    {
                        "role": message.role,
                        "content": content,
                        "evidence": evidence,
                    }
                )
        return _no_store(
            Response(
                {
                    "enabled": True,
                    "guest_verified": guest is not None,
                    "turnstile_site_key": (
                        "" if guest else settings.GUEST_TURNSTILE_SITE_KEY
                    ),
                    "remaining": _remaining(guest) if guest else None,
                    "history": history,
                }
            )
        )

    @extend_schema(
        request=GuestChatInputSerializer,
        responses={200: GuestAnswerSerializer},
    )
    def post(self, request, slug):
        candidate = self._candidate(slug)
        if not settings.GUEST_CHAT_ENABLED:
            return _no_store(
                Response({"detail": "Guest chat is disabled."}, status=503)
            )
        serializer = GuestChatInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        key = request.headers.get("Idempotency-Key")
        if key is not None and (
            not 1 <= len(key) <= 128 or not key.isascii() or not key.isprintable()
        ):
            return _no_store(
                Response({"detail": "Invalid idempotency key."}, status=400)
            )
        hostname = _verified_hostname(request._request)
        if hostname is None:
            return _no_store(
                Response({"detail": "Untrusted frontend origin."}, status=403)
            )
        try:
            digest = origin_digest(request._request)
        except GuestAccessDenied:
            return _no_store(Response({"detail": "Guest access denied."}, status=403))

        guest = current_guest_session(request._request, candidate, digest)
        if guest is None:
            try:
                verified = verify_turnstile(
                    serializer.validated_data.get("turnstile_token", ""),
                    hostname=hostname,
                )
            except GuestVerificationUnavailable:
                return _no_store(
                    Response(
                        {"detail": "Bot verification is temporarily unavailable."},
                        status=503,
                    )
                )
            if not verified:
                return _no_store(
                    Response({"detail": "Bot verification failed."}, status=403)
                )
            try:
                guest = create_guest_session(candidate=candidate, digest=digest)
            except GuestAccessDenied:
                return _no_store(
                    Response({"detail": "Guest session limit exceeded."}, status=429)
                )
            request.session["guest_chat_session"] = str(guest.pk)
            request.session.set_expiry(settings.GUEST_SESSION_HOURS * 3600)

        try:
            answer = ask_candidate(
                candidate=candidate,
                initiated_by=None,
                guest_session=guest,
                question=serializer.validated_data["question"],
                idempotency_key=key,
            )
        except AIRequestAlreadySubmitted as exc:
            return _no_store(Response({"detail": str(exc)}, status=409))
        except AILimitExceeded as exc:
            return _no_store(Response({"detail": str(exc)}, status=429))
        except AIUnavailable:
            return _no_store(
                Response(
                    {"detail": "The Candidate Agent is temporarily unavailable."},
                    status=503,
                )
            )
        except AIServiceError as exc:
            return _no_store(Response({"detail": str(exc)}, status=409))

        with transaction.atomic():
            conversation, _ = Conversation.objects.get_or_create(
                candidate=candidate, guest_session=guest
            )
            Message.objects.bulk_create(
                [
                    Message(
                        conversation=conversation,
                        role=Message.Role.USER,
                        content=serializer.validated_data["question"],
                    ),
                    Message(
                        conversation=conversation,
                        role=Message.Role.ASSISTANT,
                        content=answer.content,
                        evidence_fact_ids=list(answer.cited_fact_ids),
                    ),
                ]
            )
            conversation.save(update_fields=["updated_at"])

        return _no_store(
            Response(
                {
                    "response": answer.content,
                    "evidence": answer.evidence,
                    "guest_verified": True,
                    "remaining": _remaining(guest),
                }
            )
        )
