import pytest
from django.urls import reverse

from chatbot.models import Conversation, Message


@pytest.mark.django_db
def test_private_contact_data_and_account_email_are_not_exposed_publicly(
    client, published_candidate, user
):
    response = client.get(reverse("public_profile", args=[published_candidate.slug]))

    assert response.status_code == 200
    body = response.content.decode()
    assert user.email not in body
    assert published_candidate.contact_email not in body
    assert published_candidate.phone not in body
    assert published_candidate.linkedin not in body


@pytest.mark.django_db
def test_explicit_linkedin_visibility_is_honored(client, published_candidate):
    published_candidate.show_linkedin = True
    published_candidate.save(update_fields=["show_linkedin"])

    response = client.get(reverse("public_profile", args=[published_candidate.slug]))

    assert published_candidate.linkedin in response.content.decode()


@pytest.mark.django_db
def test_professional_email_requires_explicit_public_opt_in(
    client, published_candidate
):
    published_candidate.show_contact_email = True
    published_candidate.save(update_fields=["show_contact_email"])

    response = client.get(reverse("public_profile", args=[published_candidate.slug]))

    assert published_candidate.contact_email in response.content.decode()


@pytest.mark.django_db
def test_stored_model_output_is_html_escaped(client, recruiter, published_candidate):
    conversation = Conversation.objects.create(
        candidate=published_candidate, recruiter=recruiter
    )
    Message.objects.create(
        conversation=conversation,
        role=Message.Role.ASSISTANT,
        content='<img src=x onerror="alert(1)">',
    )
    client.force_login(recruiter)

    response = client.get(reverse("chat", args=[published_candidate.slug]))
    body = response.content.decode()

    assert "&lt;img" in body
    assert '<img src=x onerror="alert(1)">' not in body
    assert "document.createTextNode(content)" in body
    assert ".append('<" not in body


@pytest.mark.django_db
def test_obsolete_state_changing_format_get_is_removed(client, user):
    client.force_login(user)

    response = client.get("/format_resume/")

    assert response.status_code == 404
