import pytest

from chatbot.models import CandidateDocument, CandidateFact, CandidateProfile


@pytest.fixture(autouse=True)
def private_document_storage(tmp_path):
    storage = CandidateDocument._meta.get_field("file").storage
    original_location = storage._location
    storage._location = str(tmp_path / "private-documents")
    storage.__dict__.pop("base_location", None)
    storage.__dict__.pop("location", None)
    yield
    storage._location = original_location
    storage.__dict__.pop("base_location", None)
    storage.__dict__.pop("location", None)


@pytest.fixture
def user(django_user_model):
    return django_user_model.objects.create_user(
        username="candidate-owner",
        email="private-account@example.com",
        password="password",
    )


@pytest.fixture
def recruiter(django_user_model):
    return django_user_model.objects.create_user(
        username="recruiter",
        email="recruiter@example.com",
        password="password",
    )


@pytest.fixture
def other_user(django_user_model):
    return django_user_model.objects.create_user(
        username="other-user",
        email="other@example.com",
        password="password",
    )


@pytest.fixture
def published_candidate(user):
    return CandidateProfile.objects.create(
        user=user,
        name="Published Candidate",
        professional_summary="Backend engineer",
        linkedin="https://www.linkedin.com/in/published-candidate/",
        contact_email="professional@example.com",
        phone="+55 84 99999-0000",
        status=CandidateProfile.Status.ACTIVE,
        publication_status=CandidateProfile.PublicationStatus.PUBLISHED,
    )


@pytest.fixture
def verified_fact(published_candidate):
    return CandidateFact.objects.create(
        candidate=published_candidate,
        fact_type=CandidateFact.FactType.EXPERIENCE,
        content="Built production Django services at Example Corp.",
        verification_status=CandidateFact.VerificationStatus.VERIFIED,
        is_public=True,
    )
