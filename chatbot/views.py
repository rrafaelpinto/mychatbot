from django.contrib import messages as django_messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from .forms import CandidateProfileForm, ChatQuestionForm
from .models import CandidateProfile, Conversation, Message
from .policies import can_read_conversation
from .services.ai import AIServiceError, AIUnavailable, ask_candidate
from .services.documents import (
    DocumentProcessingError,
    create_candidate_document,
    process_candidate_document,
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
    return render(request, "public_profile.html", {"candidate": candidate})


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


@login_required
def chat(request, slug):
    candidate = get_object_or_404(
        CandidateProfile.objects.publicly_viewable(), slug=slug
    )
    conversation = Conversation.objects.filter(
        candidate=candidate, recruiter=request.user
    ).first()

    if request.method == "POST":
        form = ChatQuestionForm(request.POST)
        if not form.is_valid():
            return JsonResponse({"error": "Enter a valid question."}, status=400)

        question = form.cleaned_data["question"]
        try:
            ai_response = ask_candidate(
                candidate=candidate,
                initiated_by=request.user,
                question=question,
            )
        except AIUnavailable:
            return JsonResponse(
                {"error": "The Candidate Agent is temporarily unavailable."},
                status=503,
            )
        except AIServiceError as exc:
            return JsonResponse({"error": str(exc)}, status=409)

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
        return JsonResponse({"response": ai_response.content})

    history = conversation.messages.all() if conversation else Message.objects.none()
    return render(
        request,
        "chat.html",
        {"candidate": candidate, "history": history},
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
