from unittest.mock import patch

import pytest
from django.urls import reverse

from chatbot.models import AIUsageEvent, CandidateFact, Conversation, Message
from chatbot.services.ai import (
    AIOperationDisabled,
    AIResponse,
    AIUnavailable,
    NoVerifiedFacts,
    ask_candidate,
    candidate_chat_messages,
)


@pytest.mark.django_db
def test_ai_gateway_is_mockable_and_records_usage(
    recruiter, published_candidate, verified_fact
):
    response = AIResponse(
        content="I built production Django services.",
        input_tokens=42,
        output_tokens=12,
        request_id="request-123",
    )
    with patch(
        "chatbot.services.ai.invoke_candidate_chat", return_value=response
    ) as provider:
        result = ask_candidate(
            candidate=published_candidate,
            initiated_by=recruiter,
            question="What did you build?",
        )

    assert result == response
    provider.assert_called_once_with(
        facts=[
            {
                "id": verified_fact.pk,
                "fact_type": verified_fact.fact_type,
                "content": verified_fact.content,
            }
        ],
        question="What did you build?",
        history=[],
    )
    usage = AIUsageEvent.objects.get()
    assert usage.status == AIUsageEvent.Status.SUCCEEDED
    assert usage.input_tokens == 42
    assert usage.output_tokens == 12
    assert usage.provider_request_id == "request-123"


@pytest.mark.django_db
def test_unverified_facts_are_never_sent_to_provider(recruiter, published_candidate):
    CandidateFact.objects.create(
        candidate=published_candidate,
        fact_type=CandidateFact.FactType.SKILL,
        content="Unreviewed AWS claim",
        verification_status=CandidateFact.VerificationStatus.PENDING,
    )

    with patch("chatbot.services.ai.invoke_candidate_chat") as provider:
        with pytest.raises(NoVerifiedFacts):
            ask_candidate(
                candidate=published_candidate,
                initiated_by=recruiter,
                question="Do you know AWS?",
            )

    provider.assert_not_called()
    assert not AIUsageEvent.objects.exists()


@pytest.mark.django_db
def test_chat_persists_conversation_messages_after_gateway_success(
    client, recruiter, published_candidate, verified_fact
):
    client.force_login(recruiter)
    with patch(
        "chatbot.services.ai.invoke_candidate_chat",
        return_value=AIResponse(content="Grounded response"),
    ):
        response = client.post(
            reverse("chat", args=[published_candidate.slug]),
            {"question": "What is your experience?"},
        )

    assert response.status_code == 200
    conversation = Conversation.objects.get(
        candidate=published_candidate, recruiter=recruiter
    )
    assert list(conversation.messages.values_list("role", "content")) == [
        (Message.Role.USER, "What is your experience?"),
        (Message.Role.ASSISTANT, "Grounded response"),
    ]


@pytest.mark.django_db
def test_chat_question_length_is_bounded_before_provider(
    client, recruiter, published_candidate, verified_fact
):
    client.force_login(recruiter)

    with patch("chatbot.services.ai.invoke_candidate_chat") as provider:
        response = client.post(
            reverse("chat", args=[published_candidate.slug]),
            {"question": "x" * 1001},
        )

    assert response.status_code == 400
    provider.assert_not_called()


@pytest.mark.django_db
def test_unconfigured_provider_fails_gracefully_and_records_failure(
    settings, recruiter, published_candidate, verified_fact
):
    settings.OPENAI_API_KEY = ""

    with pytest.raises(AIUnavailable):
        ask_candidate(
            candidate=published_candidate,
            initiated_by=recruiter,
            question="What is your experience?",
        )

    usage = AIUsageEvent.objects.get()
    assert usage.status == AIUsageEvent.Status.FAILED
    assert usage.error_code == "AIUnavailable"
    assert usage.completed_at is not None


@pytest.mark.django_db
@pytest.mark.parametrize("setting_name", ["AI_ENABLED", "AI_CANDIDATE_CHAT_ENABLED"])
def test_disabled_ai_policy_does_not_call_provider(
    settings, recruiter, published_candidate, verified_fact, setting_name
):
    settings.AI_ENABLED = True
    settings.AI_OPERATION_POLICIES = {"candidate_chat": True}
    if setting_name == "AI_ENABLED":
        settings.AI_ENABLED = False
    else:
        settings.AI_OPERATION_POLICIES = {"candidate_chat": False}

    with patch("chatbot.services.ai.invoke_candidate_chat") as provider:
        with pytest.raises(AIOperationDisabled):
            ask_candidate(
                candidate=published_candidate,
                initiated_by=recruiter,
                question="What did you build?",
            )

    provider.assert_not_called()
    assert not AIUsageEvent.objects.exists()


@pytest.mark.django_db
def test_disabled_ai_returns_503_without_disabling_public_profiles(
    client, settings, recruiter, published_candidate, verified_fact
):
    settings.AI_ENABLED = False
    client.force_login(recruiter)

    with patch("chatbot.services.ai.invoke_candidate_chat") as provider:
        chat_response = client.post(
            reverse("chat", args=[published_candidate.slug]),
            {"question": "What did you build?"},
        )
        profile_response = client.get(
            reverse("public_profile", args=[published_candidate.slug])
        )

    assert chat_response.status_code == 503
    assert profile_response.status_code == 200
    provider.assert_not_called()
    assert not AIUsageEvent.objects.exists()


@pytest.mark.django_db
def test_ai_authorization_precedes_disabled_operation(settings, recruiter, other_user):
    from chatbot.models import CandidateProfile
    from chatbot.services.ai import AINotAuthorized

    settings.AI_ENABLED = False
    candidate = CandidateProfile.objects.create(user=other_user, name="Private")
    with patch("chatbot.services.ai.invoke_candidate_chat") as provider:
        with pytest.raises(AINotAuthorized):
            ask_candidate(
                candidate=candidate,
                initiated_by=recruiter,
                question="What did you build?",
            )

    provider.assert_not_called()
    assert not AIUsageEvent.objects.exists()


def test_candidate_agent_prompt_requires_first_person_grounded_answers():
    messages = candidate_chat_messages(
        facts=[{"id": 1, "fact_type": "skill", "content": "I build Django APIs."}],
        question="What backend technologies do you use?",
        history=[],
    )
    instruction = messages[0]["content"]
    assert "first-person voice" in instruction
    assert "using I, my, and me" in instruction
    assert "third person" in instruction
    assert "verified candidate facts" in instruction
    assert "fact_ids" in instruction
