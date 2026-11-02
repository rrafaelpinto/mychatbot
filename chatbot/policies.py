from dataclasses import dataclass

from django.conf import settings

from .models import CandidateProfile, Conversation


@dataclass(frozen=True)
class AIOperationPolicy:
    operation: str
    enabled: bool


def get_ai_operation_policy(operation: str) -> AIOperationPolicy:
    if operation not in settings.AI_OPERATION_POLICIES:
        raise ValueError(f"Unknown AI operation: {operation}")
    return AIOperationPolicy(
        operation=operation,
        enabled=settings.AI_OPERATION_POLICIES[operation],
    )


def can_edit_candidate(user, candidate: CandidateProfile) -> bool:
    from chatbot.access import access_state, is_candidate

    return bool(
        user.is_authenticated
        and candidate.user_id == user.id
        and access_state(user) == "active"
        and is_candidate(user)
    )


def can_view_public_candidate(candidate: CandidateProfile) -> bool:
    return bool(
        candidate.status == CandidateProfile.Status.ACTIVE
        and candidate.publication_status == CandidateProfile.PublicationStatus.PUBLISHED
    )


def can_interact_with_candidate(user, candidate: CandidateProfile) -> bool:
    from chatbot.access import access_state

    return bool(
        user.is_authenticated
        and access_state(user) == "active"
        and can_view_public_candidate(candidate)
    )


def can_read_conversation(user, conversation: Conversation) -> bool:
    return bool(
        user.is_authenticated
        and (
            user.is_superuser
            or conversation.recruiter_id == user.id
            or conversation.candidate.user_id == user.id
        )
    )
