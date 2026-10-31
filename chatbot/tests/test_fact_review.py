from unittest.mock import patch

import pytest
from django.test import Client
from django.urls import reverse

from chatbot.models import CandidateFact, CandidateFactReviewEvent, CandidateProfile
from chatbot.services.ai import NoVerifiedFacts, ask_candidate


@pytest.fixture
def pending_fact(published_candidate):
    return CandidateFact.objects.create(
        candidate=published_candidate,
        fact_type=CandidateFact.FactType.PROJECT,
        content="Built Python services for Example Corporation.",
        source_reference="Reviewed private project notes",
    )


def review_url(fact):
    return reverse("candidate_fact_review_detail", args=[fact.pk])


def review_post(client, fact, action, **overrides):
    payload = {
        "action": action,
        "fact_type": fact.fact_type,
        "content": fact.content,
        "version": fact.updated_at.isoformat(),
    }
    payload.update(overrides)
    return client.post(review_url(fact), payload)


@pytest.mark.django_db
def test_only_candidate_owner_can_list_and_review(
    client, user, other_user, recruiter, pending_fact
):
    list_url = reverse("candidate_fact_review_list")
    for url in (list_url, review_url(pending_fact)):
        assert client.get(url).status_code == 302
        for outsider in (recruiter, other_user):
            client.force_login(outsider)
            assert client.get(url).status_code == 404
        client.force_login(user)
        assert client.get(url).status_code == 200


@pytest.mark.django_db
def test_staff_cannot_read_another_candidates_private_evidence(
    client, recruiter, pending_fact
):
    recruiter.is_staff = True
    recruiter.save(update_fields=["is_staff"])
    client.force_login(recruiter)
    assert client.get(review_url(pending_fact)).status_code == 404
    assert client.get(reverse("candidate_fact_review_list")).status_code == 404


@pytest.mark.django_db
def test_other_candidate_cannot_change_fact_with_forged_post(
    client, recruiter, pending_fact
):
    CandidateProfile.objects.create(user=recruiter, name="Different candidate")
    client.force_login(recruiter)
    response = review_post(client, pending_fact, "approve")
    assert response.status_code == 404
    pending_fact.refresh_from_db()
    assert pending_fact.verification_status == CandidateFact.VerificationStatus.PENDING
    assert not CandidateFactReviewEvent.objects.exists()


@pytest.mark.django_db
def test_approval_is_private_until_separately_published(
    client, user, published_candidate, pending_fact
):
    client.force_login(user)
    assert review_post(client, pending_fact, "approve").status_code == 302
    pending_fact.refresh_from_db()
    assert pending_fact.verification_status == CandidateFact.VerificationStatus.VERIFIED
    assert not pending_fact.is_public

    with patch("chatbot.services.ai.invoke_candidate_chat") as provider:
        with pytest.raises(NoVerifiedFacts):
            ask_candidate(
                candidate=published_candidate,
                initiated_by=user,
                question="What did you build?",
            )
    provider.assert_not_called()

    assert review_post(client, pending_fact, "publish").status_code == 302
    pending_fact.refresh_from_db()
    assert pending_fact.is_public
    assert list(
        CandidateFact.objects.filter(
            candidate=published_candidate,
            is_public=True,
            verification_status=CandidateFact.VerificationStatus.VERIFIED,
        ).values_list("id", flat=True)
    ) == [pending_fact.pk]
    assert list(pending_fact.review_events.values_list("action", flat=True)) == [
        "published",
        "approved",
    ]


@pytest.mark.django_db
def test_verified_fact_text_change_revokes_approval_and_publication(
    client, user, verified_fact
):
    client.force_login(user)
    changed = "Revised claim based on reviewed evidence."
    assert (
        review_post(client, verified_fact, "save", content=changed).status_code == 302
    )
    verified_fact.refresh_from_db()
    assert verified_fact.content == changed
    assert verified_fact.verification_status == CandidateFact.VerificationStatus.PENDING
    assert verified_fact.is_public is False
    event = verified_fact.review_events.get()
    assert event.action == "edited"
    assert event.previous_status == CandidateFact.VerificationStatus.VERIFIED
    assert event.previous_public is True
    assert event.new_public is False


@pytest.mark.django_db
def test_type_change_revokes_verified_public_fact(client, user, verified_fact):
    client.force_login(user)
    assert (
        review_post(
            client, verified_fact, "save", fact_type=CandidateFact.FactType.PROJECT
        ).status_code
        == 302
    )
    verified_fact.refresh_from_db()
    assert verified_fact.fact_type == CandidateFact.FactType.PROJECT
    assert verified_fact.verification_status == CandidateFact.VerificationStatus.PENDING
    assert not verified_fact.is_public


@pytest.mark.django_db
def test_edits_cannot_be_combined_with_approval_or_publication(
    client, user, verified_fact, pending_fact
):
    client.force_login(user)
    for fact, action in ((pending_fact, "approve"), (verified_fact, "unpublish")):
        response = review_post(client, fact, action, content="Unreviewed new statement")
        assert response.status_code == 200
        assert b"Save your text changes" in response.content
        fact.refresh_from_db()
        assert fact.content != "Unreviewed new statement"
    assert not CandidateFactReviewEvent.objects.exists()


@pytest.mark.django_db
def test_cannot_publish_pending_or_rejected_claim(client, user, pending_fact):
    client.force_login(user)
    response = review_post(client, pending_fact, "publish")
    assert response.status_code == 200
    assert b"Only verified private facts" in response.content
    assert review_post(client, pending_fact, "reject").status_code == 302

    pending_fact.refresh_from_db()
    response = review_post(client, pending_fact, "publish")
    assert response.status_code == 200
    pending_fact.refresh_from_db()
    assert pending_fact.verification_status == CandidateFact.VerificationStatus.REJECTED
    assert not pending_fact.is_public


@pytest.mark.django_db
def test_rejected_fact_can_be_reopened_and_reapproved(client, user, pending_fact):
    client.force_login(user)
    assert review_post(client, pending_fact, "reject").status_code == 302
    pending_fact.refresh_from_db()
    assert review_post(client, pending_fact, "reopen").status_code == 302
    pending_fact.refresh_from_db()
    assert pending_fact.verification_status == CandidateFact.VerificationStatus.PENDING
    assert review_post(client, pending_fact, "approve").status_code == 302
    pending_fact.refresh_from_db()
    assert pending_fact.verification_status == CandidateFact.VerificationStatus.VERIFIED
    assert pending_fact.is_public is False


@pytest.mark.django_db
def test_rejecting_public_fact_withdraws_it_atomically(client, user, verified_fact):
    client.force_login(user)
    assert review_post(client, verified_fact, "reject").status_code == 302
    verified_fact.refresh_from_db()
    assert (
        verified_fact.verification_status == CandidateFact.VerificationStatus.REJECTED
    )
    assert not verified_fact.is_public
    e = verified_fact.review_events.get()
    assert e.previous_public and not e.new_public


@pytest.mark.django_db
def test_publication_can_be_withdrawn_without_losing_review(
    client, user, verified_fact
):
    client.force_login(user)
    assert review_post(client, verified_fact, "unpublish").status_code == 302
    verified_fact.refresh_from_db()
    assert (
        verified_fact.verification_status == CandidateFact.VerificationStatus.VERIFIED
    )
    assert not verified_fact.is_public
    assert review_post(client, verified_fact, "publish").status_code == 302
    verified_fact.refresh_from_db()
    assert verified_fact.is_public


@pytest.mark.django_db
def test_stale_review_form_cannot_overwrite_newer_decision(client, user, pending_fact):
    client.force_login(user)
    stale_version = pending_fact.updated_at.isoformat()
    assert review_post(client, pending_fact, "approve").status_code == 302
    pending_fact.refresh_from_db()
    response = review_post(
        client, pending_fact, "save", content="Overwritten claim", version=stale_version
    )
    assert response.status_code == 200
    assert b"modified elsewhere" in response.content
    pending_fact.refresh_from_db()
    assert pending_fact.content != "Overwritten claim"
    assert pending_fact.verification_status == CandidateFact.VerificationStatus.VERIFIED
    assert pending_fact.review_events.count() == 1


@pytest.mark.django_db
def test_validation_and_invalid_actions_do_not_modify_facts(client, user, pending_fact):
    client.force_login(user)
    invalid = review_post(client, pending_fact, "save", content=" ")
    assert invalid.status_code == 200
    assert b"required" in invalid.content.lower()
    unknown = review_post(client, pending_fact, "delete")
    assert unknown.status_code == 404
    pending_fact.refresh_from_db()
    assert pending_fact.content == "Built Python services for Example Corporation."
    assert not CandidateFactReviewEvent.objects.exists()


@pytest.mark.django_db
def test_evidence_is_private_and_html_escaped(client, user, published_candidate):
    quoted = '<script>alert("not safe")</script> source excerpt'
    fact = CandidateFact.objects.create(
        candidate=published_candidate,
        fact_type=CandidateFact.FactType.PROJECT,
        content="Example & backend project",
        source_reference=quoted,
    )
    path = review_url(fact)
    assert Client().get(path).status_code == 302
    client.force_login(user)
    page = client.get(path)
    assert page.status_code == 200
    assert b"&lt;script&gt;" in page.content
    assert quoted.encode() not in page.content
    assert b"Example &amp; backend project" in page.content


@pytest.mark.django_db
def test_filters_only_show_current_candidate_facts(
    client, user, other_user, published_candidate, pending_fact
):
    outsider = CandidateProfile.objects.create(user=other_user, name="Other candidate")
    CandidateFact.objects.create(
        candidate=outsider,
        fact_type=CandidateFact.FactType.OTHER,
        content="Confidential another candidate claim",
    )
    client.force_login(user)
    url = reverse("candidate_fact_review_list")
    page = client.get(url)
    assert pending_fact.content.encode() in page.content
    assert b"Confidential another candidate claim" not in page.content
    assert client.get(url + "?status=all").status_code == 200
    assert client.get(url + "?status=bogus").status_code == 404


@pytest.mark.django_db
def test_evidence_links_remain_private_after_publication(
    client, user, pending_fact, published_candidate
):
    client.force_login(user)
    assert review_post(client, pending_fact, "approve").status_code == 302
    pending_fact.refresh_from_db()
    assert review_post(client, pending_fact, "publish").status_code == 302

    client.logout()
    public_page = client.get(reverse("public_profile", args=[published_candidate.slug]))
    assert public_page.status_code == 200
    assert b"Reviewed private project notes" not in public_page.content
    assert client.get(review_url(pending_fact)).status_code == 302


@pytest.mark.django_db
def test_unchanged_save_does_not_create_review_event(client, user, pending_fact):
    client.force_login(user)
    assert review_post(client, pending_fact, "save").status_code == 302
    assert not CandidateFactReviewEvent.objects.exists()


@pytest.mark.django_db
def test_owner_profile_links_to_private_review(client, user, published_candidate):
    client.force_login(user)
    page = client.get(reverse("profile"))
    assert page.status_code == 200
    assert reverse("candidate_fact_review_list").encode() in page.content


@pytest.mark.django_db
def test_post_requires_csrf_token(user, pending_fact):
    client = Client(enforce_csrf_checks=True)
    client.force_login(user)
    response = review_post(client, pending_fact, "approve")
    assert response.status_code == 403
    pending_fact.refresh_from_db()
    assert pending_fact.verification_status == CandidateFact.VerificationStatus.PENDING
