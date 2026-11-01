import json

import pytest
from django.urls import reverse

from chatbot.models import CandidateFact, CandidateProfile


@pytest.mark.django_db
def test_public_list_includes_only_active_published_candidates(
    client, published_candidate, other_user
):
    CandidateProfile.objects.create(
        user=other_user,
        name="Hidden Candidate",
        professional_summary="Private profile",
        status=CandidateProfile.Status.PENDING_APPROVAL,
    )
    response = client.get(reverse("api-candidates"))
    assert response.status_code == 200
    assert response.json()["count"] == 1
    assert [row["slug"] for row in response.json()["results"]] == [
        published_candidate.slug
    ]


@pytest.mark.django_db
def test_public_profile_only_exposes_whitelisted_fields_and_approved_facts(
    client, published_candidate, verified_fact
):
    published_candidate.phone = "private-phone"
    published_candidate.contact_email = "private-contact@example.test"
    published_candidate.linkedin = "https://example.test/private"
    published_candidate.show_contact_email = False
    published_candidate.show_linkedin = False
    published_candidate.save()
    CandidateFact.objects.create(
        candidate=published_candidate,
        fact_type=CandidateFact.FactType.SKILL,
        content="Private project details",
        verification_status=CandidateFact.VerificationStatus.VERIFIED,
        is_public=False,
        source_reference="private-filename.pdf",
    )
    CandidateFact.objects.create(
        candidate=published_candidate,
        fact_type=CandidateFact.FactType.SKILL,
        content="Unverified proposal",
        verification_status=CandidateFact.VerificationStatus.PENDING,
        is_public=False,
    )
    response = client.get(
        reverse("api-candidate-detail", kwargs={"slug": published_candidate.slug})
    )
    assert response.status_code == 200
    result = response.json()
    assert set(result) == {
        "slug",
        "name",
        "professional_summary",
        "image_url",
        "linkedin",
        "contact_email",
        "facts",
    }
    assert result["linkedin"] is None
    assert result["contact_email"] is None
    assert result["facts"] == [
        {
            "id": verified_fact.pk,
            "fact_type": verified_fact.fact_type,
            "content": verified_fact.content,
        }
    ]
    response_text = response.content.decode()
    assert "private-phone" not in response_text
    assert "private-contact@example.test" not in response_text
    assert "private-filename.pdf" not in response_text
    assert "Private project details" not in response_text
    assert "Unverified proposal" not in response_text


@pytest.mark.django_db
def test_public_contact_visibility_requires_explicit_consent(
    client, published_candidate
):
    published_candidate.show_contact_email = True
    published_candidate.show_linkedin = True
    published_candidate.save()
    result = client.get(
        reverse("api-candidate-detail", kwargs={"slug": published_candidate.slug})
    ).json()
    assert result["contact_email"] == published_candidate.contact_email
    assert result["linkedin"] == published_candidate.linkedin


@pytest.mark.django_db
def test_suspended_or_draft_candidate_is_not_available_via_api(
    client, published_candidate
):
    url = reverse("api-candidate-detail", kwargs={"slug": published_candidate.slug})
    published_candidate.publication_status = CandidateProfile.PublicationStatus.DRAFT
    published_candidate.save()
    assert client.get(url).status_code == 404
    published_candidate.publication_status = (
        CandidateProfile.PublicationStatus.PUBLISHED
    )
    published_candidate.save()
    assert client.get(url).status_code == 200


@pytest.mark.django_db
def test_owner_routes_require_authentication(client, published_candidate):
    for route in ("api-me", "api-me-profile", "api-me-facts"):
        response = client.get(reverse(route))
        assert response.status_code == 403


@pytest.mark.django_db
def test_owner_reads_only_their_account_candidate_and_facts(
    client, published_candidate, verified_fact, other_user
):
    client.force_login(other_user)
    account = client.get(reverse("api-me"))
    assert account.status_code == 200
    assert account.json()["username"] == other_user.username
    assert client.get(reverse("api-me-profile")).status_code == 404
    assert client.get(reverse("api-me-facts")).json()["results"] == []

    client.force_login(published_candidate.user)
    profile = client.get(reverse("api-me-profile"))
    assert profile.status_code == 200
    assert profile.json()["slug"] == published_candidate.slug
    assert "phone" not in profile.json()
    assert "user" not in profile.json()
    facts = client.get(reverse("api-me-facts")).json()["results"]
    assert len(facts) == 1
    assert facts[0]["id"] == verified_fact.pk
    assert "source_document" not in facts[0]
    assert "source_reference" not in facts[0]
    assert "import_key" not in facts[0]


@pytest.mark.django_db
def test_owner_fact_list_never_exposes_other_candidates(
    client, published_candidate, verified_fact, other_user
):
    other_profile = CandidateProfile.objects.create(
        user=other_user, name="Other Candidate"
    )
    other_fact = CandidateFact.objects.create(
        candidate=other_profile,
        fact_type=CandidateFact.FactType.EXPERIENCE,
        content="Private other account work",
    )
    client.force_login(published_candidate.user)
    payload = client.get(reverse("api-me-facts")).json()
    assert payload["count"] == 1
    assert payload["results"][0]["id"] == verified_fact.id
    assert other_fact.id not in {row["id"] for row in payload["results"]}
    assert "Private other account work" not in json.dumps(payload)


@pytest.mark.django_db
def test_read_only_api_rejects_mutations_without_changing_data(
    client, published_candidate, verified_fact
):
    client.force_login(published_candidate.user)
    for route in ("api-me-profile", "api-me-facts"):
        assert (
            client.patch(
                reverse(route),
                data=json.dumps({"content": "Unapproved update"}),
                content_type="application/json",
            ).status_code
            == (400 if route == "api-me-profile" else 405)
        )
    url = reverse("api-candidate-detail", kwargs={"slug": published_candidate.slug})
    assert client.delete(url).status_code == 405
    verified_fact.refresh_from_db()
    assert verified_fact.content != "Unapproved update"


@pytest.mark.django_db
def test_openapi_schema_and_swagger_are_exposed_without_private_fields(client):
    result = client.get(reverse("api-schema") + "?format=json")
    assert result.status_code == 200
    schema = result.json()
    assert schema["openapi"].startswith("3.")
    assert "/api/v1/candidates/" in schema["paths"]
    assert "/api/v1/candidates/{slug}/" in schema["paths"]
    assert "/api/v1/me/profile/" in schema["paths"]
    assert "/api/v1/me/facts/" in schema["paths"]
    body = json.dumps(schema["components"]["schemas"]["PublicCandidateDetail"])
    assert "phone" not in body
    assert "source_reference" not in body
    assert "source_document" not in body
    assert client.get(reverse("api-docs")).status_code == 200
