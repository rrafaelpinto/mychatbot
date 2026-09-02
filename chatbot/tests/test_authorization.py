from unittest.mock import patch

import pytest
from django.urls import reverse

from chatbot.models import CandidateProfile, Conversation, Message
from chatbot.services.ai import AINotAuthorized, ask_candidate


@pytest.mark.django_db
def test_candidate_cannot_edit_another_candidate(
    client, user, recruiter, published_candidate
):
    own_profile = CandidateProfile.objects.create(
        user=recruiter, name="Recruiter Profile"
    )
    client.force_login(recruiter)

    response = client.post(
        reverse("manager_candidate"),
        {
            "name": "Updated Own Profile",
            "professional_summary": "",
            "linkedin": "",
            "contact_email": "",
            "phone": "",
            "status": CandidateProfile.Status.ACTIVE,
            "publication_status": CandidateProfile.PublicationStatus.PUBLISHED,
        },
    )

    assert response.status_code == 302
    own_profile.refresh_from_db()
    published_candidate.refresh_from_db()
    assert own_profile.name == "Updated Own Profile"
    assert own_profile.status == CandidateProfile.Status.PENDING_APPROVAL
    assert own_profile.publication_status == CandidateProfile.PublicationStatus.DRAFT
    assert published_candidate.name == "Published Candidate"
    assert published_candidate.user == user


@pytest.mark.django_db
def test_unpublished_candidate_is_not_public(client, user):
    candidate = CandidateProfile.objects.create(user=user, name="Private Candidate")

    response = client.get(reverse("public_profile", args=[candidate.slug]))

    assert response.status_code == 404


@pytest.mark.django_db
def test_unpublished_candidate_direct_chat_does_not_call_provider(
    client, user, recruiter
):
    candidate = CandidateProfile.objects.create(user=user, name="Private Candidate")
    client.force_login(recruiter)

    with patch("chatbot.services.ai.invoke_candidate_chat") as provider:
        response = client.post(
            reverse("chat", args=[candidate.slug]),
            {"question": "Reveal private information"},
        )

    assert response.status_code == 404
    provider.assert_not_called()


@pytest.mark.django_db
def test_suspended_candidate_is_not_public_or_interactive(
    client, recruiter, published_candidate, verified_fact
):
    published_candidate.suspend()
    published_candidate.save()
    client.force_login(recruiter)

    with patch("chatbot.services.ai.invoke_candidate_chat") as provider:
        public_response = client.get(
            reverse("public_profile", args=[published_candidate.slug])
        )
        chat_response = client.post(
            reverse("chat", args=[published_candidate.slug]),
            {"question": "What did you build?"},
        )

    assert public_response.status_code == 404
    assert chat_response.status_code == 404
    provider.assert_not_called()


@pytest.mark.django_db
def test_ai_policy_denial_happens_before_provider_call(recruiter, other_user):
    pending = CandidateProfile.objects.create(user=other_user, name="Pending")

    with patch("chatbot.services.ai.invoke_candidate_chat") as provider:
        with pytest.raises(AINotAuthorized):
            ask_candidate(
                candidate=pending,
                initiated_by=recruiter,
                question="Tell me about your work.",
            )

    provider.assert_not_called()


@pytest.mark.django_db
def test_unauthorized_user_cannot_read_conversation(
    client, published_candidate, recruiter, other_user
):
    conversation = Conversation.objects.create(
        candidate=published_candidate, recruiter=recruiter
    )
    Message.objects.create(
        conversation=conversation,
        role=Message.Role.USER,
        content="Private recruiter question",
    )
    client.force_login(other_user)

    response = client.get(reverse("conversation_detail", args=[conversation.id]))

    assert response.status_code == 404
    assert b"Private recruiter question" not in response.content


@pytest.mark.django_db
def test_conversation_is_readable_by_recruiter_and_candidate_owner(
    client, published_candidate, recruiter, user
):
    conversation = Conversation.objects.create(
        candidate=published_candidate, recruiter=recruiter
    )

    for allowed_user in (recruiter, user):
        client.force_login(allowed_user)
        response = client.get(reverse("conversation_detail", args=[conversation.id]))
        assert response.status_code == 200
