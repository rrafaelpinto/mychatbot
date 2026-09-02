from io import BytesIO
from unittest.mock import patch

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from docx import Document

from chatbot.models import CandidateDocument, CandidateFact, CandidateProfile
from chatbot.services.documents import (
    create_candidate_document,
    process_candidate_document,
)
from chatbot.validators import DOCX_CONTENT_TYPE, validate_candidate_document


def make_docx(content: str = "Private resume content") -> SimpleUploadedFile:
    buffer = BytesIO()
    document = Document()
    document.add_paragraph(content)
    document.save(buffer)
    return SimpleUploadedFile(
        "../../unsafe resume.docx",
        buffer.getvalue(),
        content_type=DOCX_CONTENT_TYPE,
    )


def test_invalid_document_type_is_rejected():
    uploaded = SimpleUploadedFile(
        "resume.txt", b"not a document", content_type="text/plain"
    )

    with pytest.raises(ValidationError):
        validate_candidate_document(uploaded)


def test_mismatched_document_signature_is_rejected():
    uploaded = SimpleUploadedFile(
        "resume.pdf", b"not really a PDF", content_type="application/pdf"
    )

    with pytest.raises(ValidationError):
        validate_candidate_document(uploaded)


@pytest.mark.django_db
def test_invalid_document_upload_is_rejected_by_profile_view(client, user):
    client.force_login(user)
    invalid = SimpleUploadedFile(
        "resume.pdf", b"not really a PDF", content_type="application/pdf"
    )

    response = client.post(
        reverse("manager_candidate"),
        {
            "name": "Candidate",
            "professional_summary": "",
            "linkedin": "",
            "contact_email": "",
            "phone": "",
            "document": invalid,
        },
    )

    assert response.status_code == 200
    assert b"valid PDF or DOCX" in response.content
    assert not CandidateProfile.objects.exists()
    assert not CandidateDocument.objects.exists()


@pytest.mark.django_db
def test_source_document_uses_private_safe_storage_name(
    published_candidate,
):
    document = create_candidate_document(published_candidate, make_docx())

    assert document.original_filename == "unsafe_resume.docx"
    assert "unsafe resume" not in document.file.name
    assert document.file.name.startswith(
        f"candidate-documents/{published_candidate.id}/"
    )
    with pytest.raises(ValueError):
        _url = document.file.url


@pytest.mark.django_db
def test_document_processing_extracts_without_printing_pii(
    published_candidate,
):
    document = create_candidate_document(published_candidate, make_docx("Secret PII"))

    with patch("builtins.print") as print_mock:
        process_candidate_document(document)

    document.refresh_from_db()
    assert document.processing_status == CandidateDocument.ProcessingStatus.PROCESSED
    assert document.extracted_text == "Secret PII"
    print_mock.assert_not_called()


@pytest.mark.django_db
def test_fact_evidence_cannot_cross_candidate_boundary(published_candidate, other_user):
    document = create_candidate_document(published_candidate, make_docx())
    other_candidate = CandidateProfile.objects.create(
        user=other_user, name="Other Candidate"
    )
    fact = CandidateFact(
        candidate=other_candidate,
        fact_type=CandidateFact.FactType.EXPERIENCE,
        content="Cross-tenant evidence",
        source_document=document,
    )

    with pytest.raises(ValidationError, match="same candidate"):
        fact.full_clean()
