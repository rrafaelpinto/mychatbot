from django.conf import settings
from django.contrib import messages as django_messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from .forms import CandidateProfileForm, ChatQuestionForm
from .models import CandidateProfile, Conversation, Message
from .policies import can_read_conversation
from .services.ai import (
    AILimitExceeded,
    AIRequestAlreadySubmitted,
    AIServiceError,
    AIUnavailable,
    ask_candidate,
)
from .services.documents import (
    DocumentProcessingError,
    create_candidate_document,
    process_candidate_document,
)
from .services.guest_chat import (
    GuestAccessDenied,
    GuestVerificationUnavailable,
    create_guest_session,
    current_guest_session,
    origin_digest,
    verify_turnstile,
)


def about(request):
    return render(request, "about.html")


def candidates(request):
    profiles = CandidateProfile.objects.publicly_viewable()
    return render(request, "candidates.html", {"candidates": profiles})


def public_profile(request, slug):
    candidate = get_object_or_404(
        CandidateProfile.objects.publicly_viewable(), slug=slug
    )
    return render(

        {"candidate": candidate, "guest_chat_enabled": settings.GUEST_CHAT_ENABLED},
    )


@login_required
def profile(request):
    candidate = get_object_or_404(CandidateProfile, user=request.user)
    return render(
        request,
        "profile.html",
        {"candidate": candidate, "documents": candidate.documents.all()},
    )


@login_required
def manager_candidate(request):
    candidate = CandidateProfile.objects.filter(user=request.user).first()
    title = "Edit profile" if candidate else "Register as candidate"

    if request.method == "POST":
        form = CandidateProfileForm(request.POST, request.FILES, instance=candidate)
        if form.is_valid():
            saved_candidate = form.save(commit=False)
            saved_candidate.user = request.user
            saved_candidate.save()
            document_upload = form.cleaned_data.get("document")
            if document_upload:
                try:
                    document = create_candidate_document(
                        saved_candidate, document_upload
                    )
                    process_candidate_document(document)
                except (DocumentProcessingError, ValidationError):
                    django_messages.warning(
                        request,
                        "Your profile was saved, but the document could not be processed.",
                    )
                else:
                    django_messages.success(
                        request, "Profile and source document saved successfully."
                    )
            else:
                django_messages.success(request, "Profile saved successfully.")
            return redirect("profile")
        django_messages.error(request, "Please correct the errors below.")
    else:
        form = CandidateProfileForm(instance=candidate)

    return render(
        request,
        "manager_candidate.html",
        {"form": form, "title": title},
    )


def chat(request, slug):
    candidate = get_object_or_404(
        CandidateProfile.objects.publicly_viewable(), slug=slug
    )
    guest = None
    if request.user.is_authenticated:
        conversation = Conversation.objects.filter(
            candidate=candidate, recruiter=request.user
        ).first()
    elif not settings.GUEST_CHAT_ENABLED:
        if request.method == "POST":
            return JsonResponse({"error": "Guest chat is disabled."}, status=503)
        conversation = None
    else:
        try:
            digest = origin_digest(request)
        except GuestAccessDenied:
            return JsonResponse({"error": "Guest access is unavailable."}, status=403)
        guest = current_guest_session(request, candidate, digest)
        conversation = (
            Conversation.objects.filter(
                candidate=candidate, guest_session=guest
            ).first()
            if guest
            else None
        )

    if request.method == "POST":
        form = ChatQuestionForm(request.POST)
        if not form.is_valid():
            return JsonResponse({"error": "Enter a valid question."}, status=400)

        question = form.cleaned_data["question"]
        idempotency_key = request.headers.get("Idempotency-Key")
        if idempotency_key is not None and (
            not 1 <= len(idempotency_key) <= 128
            or not idempotency_key.isascii()
            or not idempotency_key.isprintable()
        ):
            return JsonResponse({"error": "Invalid idempotency key."}, status=400)

        if not request.user.is_authenticated:
            if guest is None:
                token = request.POST.get("cf-turnstile-response", "")
                try:
                    verified = verify_turnstile(
                        token, hostname=request.get_host().split(":")[0]
                    )
                except GuestVerificationUnavailable:
                    return JsonResponse(
                        {"error": "Bot verification is temporarily unavailable."},
                        status=503,
                    )
                if not verified:
                    return JsonResponse(
                        {"error": "Bot verification failed."}, status=403
                    )
                try:
                    guest = create_guest_session(candidate=candidate, digest=digest)
                except GuestAccessDenied:
                    return JsonResponse(
                        {"error": "Guest session limit exceeded."}, status=429
                    )
                request.session["guest_chat_session"] = str(guest.pk)
                request.session.set_expiry(settings.GUEST_SESSION_HOURS * 3600)

        try:
            ai_response = ask_candidate(
                candidate=candidate,
                initiated_by=request.user if request.user.is_authenticated else None,
                guest_session=guest,
                question=question,
                idempotency_key=idempotency_key,
            )
        except AIRequestAlreadySubmitted as exc:
            return JsonResponse({"error": str(exc)}, status=409)
        except AILimitExceeded as exc:
            return JsonResponse({"error": str(exc)}, status=429)
        except AIUnavailable:
            return JsonResponse(
                {"error": "The Candidate Agent is temporarily unavailable."},
                status=503,
            )
        except AIServiceError as exc:
            return JsonResponse({"error": str(exc)}, status=409)

        if guest is not None:
            conversation, _ = Conversation.objects.get_or_create(
                candidate=candidate, guest_session=guest
            )
        else:
            conversation, _ = Conversation.objects.get_or_create(
                candidate=candidate, recruiter=request.user
            )
        Message.objects.bulk_create(
            [
                Message(
                    conversation=conversation,
                    role=Message.Role.USER,
                    content=question,
                ),
                Message(
                    conversation=conversation,
                    role=Message.Role.ASSISTANT,
                    content=ai_response.content,
                ),
            ]
        )
        conversation.save(update_fields=["updated_at"])
        return JsonResponse(
            {"response": ai_response.content, "guest_verified": guest is not None}
        )

    history = conversation.messages.all() if conversation else Message.objects.none()
    return render(
        request,
        "chat.html",
        {
            "candidate": candidate,
            "history": history,
            "guest_chat_enabled": settings.GUEST_CHAT_ENABLED,
            "turnstile_site_key": (
                settings.GUEST_TURNSTILE_SITE_KEY
                if not request.user.is_authenticated and guest is None
                else ""
            ),
        },
    )


@staff_member_required
def conversations(request):
    records = Conversation.objects.select_related("candidate", "recruiter")
    return render(request, "interactions.html", {"conversations": records})


@login_required
def conversation_detail(request, conversation_id):
    conversation = get_object_or_404(
        Conversation.objects.select_related("candidate", "recruiter"),
        pk=conversation_id,
    )
    if not can_read_conversation(request.user, conversation):
        return JsonResponse({"error": "Not found."}, status=404)
    return render(
        request,
        "view_interaction.html",
        {"conversation": conversation, "history": conversation.messages.all()},
    )
