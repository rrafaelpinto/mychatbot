from django.conf import settings
from django.contrib import messages as django_messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import Http404
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from .forms import CandidateFactReviewForm, CandidateProfileForm, ChatQuestionForm
from .models import (
    AIUsageEvent,
    CandidateFact,
    CandidateFactReviewEvent,
    CandidateProfile,
    Conversation,
    Message,
)
from .policies import can_read_conversation
from .services.ai import (
    AILimitExceeded,
    AIRequestAlreadySubmitted,
    AIServiceError,
    AIUnavailable,
    ask_candidate,
    public_evidence,
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

@login_required
def candidate_fact_review_list(request):
    candidate = get_object_or_404(CandidateProfile, user=request.user)
    statuses = {
        "pending": CandidateFact.VerificationStatus.PENDING,
        "verified": CandidateFact.VerificationStatus.VERIFIED,
        "rejected": CandidateFact.VerificationStatus.REJECTED,
    }
    selected = request.GET.get("status", "pending")
    if selected not in {*statuses, "all"}:
        raise Http404("Unknown review status.")

    facts = CandidateFact.objects.filter(candidate=candidate).select_related(
        "source_document"
    )
    if selected != "all":
        facts = facts.filter(verification_status=statuses[selected])
    return render(
        request,
        "fact_review_list.html",
        {
            "candidate": candidate,
            "facts": facts.order_by("-updated_at", "-pk"),
            "selected_status": selected,
            "pending_count": CandidateFact.objects.filter(
                candidate=candidate,
                verification_status=CandidateFact.VerificationStatus.PENDING,
            ).count(),
        },
    )


@login_required
def candidate_fact_review_detail(request, fact_id):
    candidate = get_object_or_404(CandidateProfile, user=request.user)
    fact = get_object_or_404(
        CandidateFact.objects.select_related("source_document"),
        pk=fact_id,
        candidate=candidate,
    )

    if request.method == "POST":
        action = request.POST.get("action", "")
        if action not in {
            "save", "approve", "reject", "reopen", "publish", "unpublish"
        }:
            raise Http404("Unknown review action.")

        with transaction.atomic():
            fact = get_object_or_404(
                CandidateFact.objects.select_for_update().select_related(
                    "source_document"
                ),
                pk=fact_id,
                candidate=candidate,
            )
            previous_type = fact.fact_type
            previous_content = fact.content
            previous_status = fact.verification_status
            previous_public = fact.is_public
            original_version = fact.updated_at.isoformat()
            form = CandidateFactReviewForm(request.POST, instance=fact)

            if form.is_valid():
                if form.cleaned_data["version"] != original_version:
                    form.add_error(
                        None,
                        "This fact was modified elsewhere. Reload before reviewing.",
                    )
                else:
                    changed = (
                        form.cleaned_data["fact_type"] != previous_type
                        or form.cleaned_data["content"] != previous_content
                    )
                    error = _fact_review_action_error(
                        action=action,
                        changed=changed,
                        status=previous_status,
                        is_public=previous_public,
                    )
                    if error:
                        form.add_error(None, error)
                    else:
                        if action == "save" and changed:
                            fact.verification_status = (
                                CandidateFact.VerificationStatus.PENDING
                            )
                            fact.is_public = False
                        elif action == "approve":
                            fact.verification_status = (
                                CandidateFact.VerificationStatus.VERIFIED
                            )
                            fact.is_public = False
                        elif action == "reject":
                            fact.verification_status = (
                                CandidateFact.VerificationStatus.REJECTED
                            )
                            fact.is_public = False
                        elif action == "reopen":
                            fact.verification_status = (
                                CandidateFact.VerificationStatus.PENDING
                            )
                            fact.is_public = False
                        elif action == "publish":
                            fact.is_public = True
                        elif action == "unpublish":
                            fact.is_public = False

                        if action != "save" or changed:
                            fact.full_clean()
                            fact.save(
                                update_fields=[
                                    "fact_type",
                                    "content",
                                    "verification_status",
                                    "is_public",
                                    "updated_at",
                                ]
                            )
                            CandidateFactReviewEvent.objects.create(
                                fact=fact,
                                reviewed_by=request.user,
                                action=(
                                    CandidateFactReviewEvent.Action.EDITED
                                    if action == "save"
                                    else action
                                ),
                                previous_status=previous_status,
                                new_status=fact.verification_status,
                                previous_public=previous_public,
                                new_public=fact.is_public,
                            )
                        django_messages.success(request, "Fact review saved.")
                        return redirect("candidate_fact_review_detail", fact_id=fact.pk)
    else:
        form = CandidateFactReviewForm(instance=fact)

    return render(
        request,
        "fact_review_detail.html",
        {
            "candidate": candidate,
            "fact": fact,
            "form": form,
            "events": fact.review_events.select_related("reviewed_by")[:20],
        },
    )


def _fact_review_action_error(*, action, changed, status, is_public):
    if action != "save" and changed:
        return "Save your text changes before choosing a review decision."
    if action == "save":
        return None
    if action == "approve" and status != CandidateFact.VerificationStatus.PENDING:
        return "Only pending facts can be approved."
    if action == "reject" and status == CandidateFact.VerificationStatus.REJECTED:
        return "This fact has already been rejected."
    if action == "reopen" and status != CandidateFact.VerificationStatus.REJECTED:
        return "Only rejected facts can be reopened."
    if action == "publish" and (
        status != CandidateFact.VerificationStatus.VERIFIED or is_public
    ):
        return "Only verified private facts can be published."
    if action == "unpublish" and not is_public:
        return "Only public facts can be unpublished."
    return None



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
        request,
        "public_profile.html",
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
                    evidence_fact_ids=list(ai_response.cited_fact_ids),
                ),
            ]
        )
        conversation.save(update_fields=["updated_at"])
        remaining = None
        if guest is not None:
            remaining = max(
                0,
                settings.GUEST_SESSION_QUESTION_LIMIT
                - AIUsageEvent.objects.filter(
                    guest_session=guest,
                    operation=AIUsageEvent.Operation.CANDIDATE_CHAT,
                ).count(),
            )
        return JsonResponse(
            {
                "response": ai_response.content,
                "evidence": ai_response.evidence,
                "guest_verified": guest is not None,
                "remaining": remaining,
            }
        )

    history = list(conversation.messages.all()) if conversation else []
    for message in history:
        message.public_evidence = ()
        if message.role == Message.Role.ASSISTANT and message.evidence_fact_ids:
            evidence = public_evidence(candidate, message.evidence_fact_ids)
            if evidence is None:
                message.content = (
                    "This answer is no longer available because its evidence changed."
                )
            else:
                message.public_evidence = evidence
    remaining = None
    if guest is not None:
        remaining = max(
            0,
            settings.GUEST_SESSION_QUESTION_LIMIT
            - AIUsageEvent.objects.filter(
                guest_session=guest,
                operation=AIUsageEvent.Operation.CANDIDATE_CHAT,
            ).count(),
        )
    return render(
        request,
        "chat.html",
        {
            "candidate": candidate,
            "history": history,
            "guest_remaining": remaining,
            "suggested_questions": [
                "What are your main backend skills?",
                "Which professional projects have you worked on?",
                "What experience do you have with Django and PostgreSQL?",
                "What is your educational background?",
            ],
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
