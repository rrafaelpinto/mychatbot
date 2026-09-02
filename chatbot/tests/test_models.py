import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from chatbot.models import CandidateProfile


@pytest.mark.django_db
def test_candidate_defaults_to_pending_private_draft(user):
    candidate = CandidateProfile.objects.create(user=user, name="New Candidate")

    assert candidate.status == CandidateProfile.Status.PENDING_APPROVAL
    assert candidate.publication_status == CandidateProfile.PublicationStatus.DRAFT
    assert candidate.slug == "new-candidate"


@pytest.mark.django_db
def test_candidate_ownership_is_required():
    with pytest.raises(IntegrityError):
        CandidateProfile.objects.create(user=None, name="Orphan")


@pytest.mark.django_db
def test_only_active_candidate_can_be_published(user):
    candidate = CandidateProfile.objects.create(user=user, name="Pending Candidate")

    with pytest.raises(ValidationError):
        candidate.publish()


@pytest.mark.django_db
def test_slug_collision_receives_safe_unique_suffix(user, other_user):
    first = CandidateProfile.objects.create(user=user, name="Same Name")
    second = CandidateProfile.objects.create(user=other_user, name="Same Name")

    assert first.slug == "same-name"
    assert second.slug.startswith("same-name-")
    assert first.slug != second.slug
