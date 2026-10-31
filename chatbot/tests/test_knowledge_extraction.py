import json
from datetime import timedelta
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone
from pydantic import ValidationError

from chatbot.models import (
    AIProjectBudget,
    AIUsageEvent,
    CandidateDocument,
    CandidateExtractionRun,
    CandidateFact,
)
from chatbot.services.ai import (
    AIExtractionResponse,
    ExtractedFactSchema,
    invoke_fact_extraction,
)
from chatbot.services.knowledge_extraction import (
    ExtractionUnavailable,
    KnowledgeExtractionError,
    extract_candidate_facts,
)

SOURCE = (
    "Worked on Django REST APIs at Example Systems. "
    "Improved PostgreSQL query performance with indexes. "
    "Built a background task processing system with Python."
)
QUOTE = "Improved PostgreSQL query performance with indexes."


@pytest.fixture
def extraction_settings(settings):
    settings.AI_ENABLED = True
    settings.OPENAI_API_KEY = "fake-extraction-key"
    settings.AI_OPERATION_POLICIES = {
        **settings.AI_OPERATION_POLICIES,
        "knowledge_extraction": True,
    }
    settings.AI_USAGE_LIMITS = {
        **settings.AI_USAGE_LIMITS,
        "knowledge_extraction": {
            "identity_per_minute": 20,
            "identity_per_day": 20,
            "candidate_per_day": 20,
        },
    }


@pytest.fixture
def processed_document(published_candidate):
    return CandidateDocument.objects.create(
        candidate=published_candidate,
        file="candidate-documents/synthetic.docx",
        document_type=CandidateDocument.DocumentType.RESUME,
        original_filename="synthetic.docx",
        detected_content_type=(
            "application/vnd.openxmlformats-officedocument."
            "wordprocessingml.document"
        ),
        size_bytes=512,
        processing_status=CandidateDocument.ProcessingStatus.PROCESSED,
        extracted_text=SOURCE,
    )


def sample_response(quote=QUOTE, content="Optimized PostgreSQL queries."):
    return AIExtractionResponse(
        facts=(
            ExtractedFactSchema(
                fact_type="skill",
                content=content,
                evidence_quote=quote,
            ),
        ),
        input_tokens=100,
        output_tokens=40,
        request_id="synthetic-request-id",
    )


def run_extraction(candidate, document, owner=None):
    return extract_candidate_facts(
        candidate=candidate,
        document=document,
        initiated_by=owner or candidate.user,
    )


@pytest.mark.django_db
def test_extract_creates_only_pending_private_proposals_and_usage(
    extraction_settings, published_candidate, processed_document
):
    with patch(
        "chatbot.services.knowledge_extraction.invoke_fact_extraction",
        return_value=sample_response(),
    ) as provider:
        outcome = run_extraction(published_candidate, processed_document)

    assert outcome.proposed_count == 1
    assert not outcome.already_completed
    provider.assert_called_once_with(source_text=SOURCE)
    fact = CandidateFact.objects.get()
    assert fact.candidate == published_candidate
    assert fact.source_document == processed_document
    assert fact.verification_status == CandidateFact.VerificationStatus.PENDING
    assert fact.is_public is False
    assert fact.source_reference == QUOTE
    assert fact.import_key.startswith("extract-v1-")
    run = CandidateExtractionRun.objects.get(document=processed_document)
    assert run.status == CandidateExtractionRun.Status.SUCCEEDED
    assert run.proposed_count == 1
    usage = AIUsageEvent.objects.get()
    assert usage.operation == AIUsageEvent.Operation.KNOWLEDGE_EXTRACTION
    assert usage.initiated_by == published_candidate.user
    assert usage.status == AIUsageEvent.Status.SUCCEEDED
    assert usage.input_tokens == 100
    assert usage.output_tokens == 40
    assert usage.settled_at is not None
    assert AIProjectBudget.objects.count() == 1


@pytest.mark.django_db
def test_repeating_success_is_free_and_preserves_human_review(
    extraction_settings, published_candidate, processed_document
):
    with patch(
        "chatbot.services.knowledge_extraction.invoke_fact_extraction",
        return_value=sample_response(),
    ) as provider:
        run_extraction(published_candidate, processed_document)
        fact = CandidateFact.objects.get()
        fact.verification_status = CandidateFact.VerificationStatus.VERIFIED
        fact.is_public = True
        fact.save(update_fields=["verification_status", "is_public"])
        repeated = run_extraction(published_candidate, processed_document)

    assert repeated.already_completed is True
    assert repeated.proposed_count == 1
    assert provider.call_count == 1
    assert CandidateFact.objects.count() == 1
    assert CandidateFact.objects.get().is_public is True
    assert AIUsageEvent.objects.count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize(
    "invalid_response",
    [
        sample_response(quote="Fabricated professional experience."),
        sample_response(quote="short"),
        sample_response(content=" "),
        AIExtractionResponse(
            facts=(
                ExtractedFactSchema(
                    fact_type="unsupported", content="Claim", evidence_quote=QUOTE
                ),
            ),
            input_tokens=12,
            output_tokens=10,
            request_id="synthetic",
        ),
    ],
)
def test_invalid_evidence_rolls_back_all_proposals(
    extraction_settings,
    published_candidate,
    processed_document,
    invalid_response,
):
    with patch(
        "chatbot.services.knowledge_extraction.invoke_fact_extraction",
        return_value=invalid_response,
    ):
        with pytest.raises(KnowledgeExtractionError):
            run_extraction(published_candidate, processed_document)

    assert not CandidateFact.objects.exists()
    assert CandidateExtractionRun.objects.get().status == (
        CandidateExtractionRun.Status.FAILED
    )
    usage = AIUsageEvent.objects.get()
    assert usage.status == AIUsageEvent.Status.FAILED
    assert usage.settled_at is None


@pytest.mark.django_db
def test_disabled_operation_never_calls_ai_or_reserves_budget(
    settings, published_candidate, processed_document
):
    settings.AI_ENABLED = True
    settings.AI_OPERATION_POLICIES = {
        **settings.AI_OPERATION_POLICIES,
        "knowledge_extraction": False,
    }
    with patch("chatbot.services.knowledge_extraction.invoke_fact_extraction") as ai:
        with pytest.raises(ExtractionUnavailable, match="disabled"):
            run_extraction(published_candidate, processed_document)
    ai.assert_not_called()
    assert not CandidateExtractionRun.objects.exists()
    assert not AIUsageEvent.objects.exists()


@pytest.mark.django_db
def test_wrong_candidate_owner_never_calls_provider(
    extraction_settings, published_candidate, processed_document, other_user
):
    with patch("chatbot.services.knowledge_extraction.invoke_fact_extraction") as ai:
        with pytest.raises(KnowledgeExtractionError, match="not accessible"):
            run_extraction(published_candidate, processed_document, other_user)
    ai.assert_not_called()
    assert not AIUsageEvent.objects.exists()


@pytest.mark.django_db
def test_unprocessed_or_oversized_document_fails_without_ai(
    extraction_settings, settings, published_candidate, processed_document
):
    settings.AI_EXTRACTION_MAX_SOURCE_BYTES = 12
    with patch("chatbot.services.knowledge_extraction.invoke_fact_extraction") as ai:
        with pytest.raises(KnowledgeExtractionError, match="input limit"):
            run_extraction(published_candidate, processed_document)
    ai.assert_not_called()
    assert not CandidateExtractionRun.objects.exists()

    settings.AI_EXTRACTION_MAX_SOURCE_BYTES = 6000
    processed_document.processing_status = CandidateDocument.ProcessingStatus.UPLOADED
    processed_document.save(update_fields=["processing_status"])
    with patch("chatbot.services.knowledge_extraction.invoke_fact_extraction") as ai:
        with pytest.raises(KnowledgeExtractionError, match="not processed"):
            run_extraction(published_candidate, processed_document)
    ai.assert_not_called()


@pytest.mark.django_db
def test_quota_denial_reserves_nothing_and_allows_later_retry(
    extraction_settings, settings, published_candidate, processed_document
):
    settings.AI_USAGE_LIMITS["knowledge_extraction"]["identity_per_minute"] = 0
    with patch("chatbot.services.knowledge_extraction.invoke_fact_extraction") as ai:
        with pytest.raises(ExtractionUnavailable, match="quota"):
            run_extraction(published_candidate, processed_document)
    ai.assert_not_called()
    assert not AIUsageEvent.objects.exists()
    assert CandidateExtractionRun.objects.get().status == (
        CandidateExtractionRun.Status.FAILED
    )

    settings.AI_USAGE_LIMITS["knowledge_extraction"]["identity_per_minute"] = 20
    with patch(
        "chatbot.services.knowledge_extraction.invoke_fact_extraction",
        return_value=sample_response(),
    ):
        result = run_extraction(published_candidate, processed_document)
    assert result.proposed_count == 1
    assert CandidateExtractionRun.objects.get().attempts == 2


@pytest.mark.django_db
def test_recent_running_extraction_is_exclusive(
    extraction_settings, published_candidate, processed_document
):
    CandidateExtractionRun.objects.create(
        document=processed_document,
        source_sha256=__import__("hashlib").sha256(SOURCE.encode()).hexdigest(),
    )
    with patch("chatbot.services.knowledge_extraction.invoke_fact_extraction") as ai:
        with pytest.raises(KnowledgeExtractionError, match="in progress"):
            run_extraction(published_candidate, processed_document)
    ai.assert_not_called()
    assert not AIUsageEvent.objects.exists()


@pytest.mark.django_db
def test_stale_run_can_be_retried(
    extraction_settings, published_candidate, processed_document
):
    import hashlib

    run = CandidateExtractionRun.objects.create(
        document=processed_document,
        source_sha256=hashlib.sha256(SOURCE.encode()).hexdigest(),
        started_at=timezone.now() - timedelta(hours=1),
    )
    with patch(
        "chatbot.services.knowledge_extraction.invoke_fact_extraction",
        return_value=sample_response(),
    ):
        run_extraction(published_candidate, processed_document)
    run.refresh_from_db()
    assert run.status == CandidateExtractionRun.Status.SUCCEEDED
    assert run.attempts == 2


@pytest.mark.django_db
def test_failed_provider_attempt_is_recorded_without_publishing(
    extraction_settings, published_candidate, processed_document
):
    with patch(
        "chatbot.services.knowledge_extraction.invoke_fact_extraction",
        side_effect=RuntimeError("Provider failure with confidential context"),
    ):
        with pytest.raises(KnowledgeExtractionError, match="failed"):
            run_extraction(published_candidate, processed_document)
    assert not CandidateFact.objects.exists()
    assert CandidateExtractionRun.objects.get().status == (
        CandidateExtractionRun.Status.FAILED
    )
    assert AIUsageEvent.objects.get().status == AIUsageEvent.Status.FAILED


@pytest.mark.django_db
def test_admin_command_does_not_output_private_document_contents(
    extraction_settings, published_candidate, processed_document
):
    output = StringIO()
    with patch(
        "chatbot.services.knowledge_extraction.invoke_fact_extraction",
        return_value=sample_response(),
    ):
        call_command(
            "extract_candidate_facts",
            candidate=published_candidate.slug,
            document=processed_document.pk,
            stdout=output,
        )
    assert "1 private pending suggestions" in output.getvalue()
    assert SOURCE not in output.getvalue()
    assert QUOTE not in output.getvalue()


@pytest.mark.django_db
def test_admin_command_rejects_document_from_other_candidate(
    extraction_settings, published_candidate, other_user, processed_document
):
    from chatbot.models import CandidateProfile

    other = CandidateProfile.objects.create(user=other_user, name="Other candidate")
    with pytest.raises(CommandError, match="not found"):
        call_command(
            "extract_candidate_facts",
            candidate=other.slug,
            document=processed_document.pk,
        )
    assert not AIUsageEvent.objects.exists()


def test_langchain_extraction_pipeline_validates_pydantic_and_usage(settings):
    settings.OPENAI_API_KEY = "synthetic-key"
    completion = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=json.dumps(
                        {
                            "facts": [
                                {
                                    "fact_type": "skill",
                                    "content": "Optimized PostgreSQL queries.",
                                    "evidence_quote": QUOTE,
                                }
                            ]
                        }
                    )
                )
            )
        ],
        usage=SimpleNamespace(prompt_tokens=40, completion_tokens=22),
        id="synthetic-completion-id",
    )
    with patch("chatbot.services.ai.OpenAI") as openai:
        openai.return_value.chat.completions.create.return_value = completion
        response = invoke_fact_extraction(source_text=SOURCE)
    assert response.facts[0].evidence_quote == QUOTE
    assert response.facts[0].fact_type == "skill"
    assert response.input_tokens == 40
    assert response.output_tokens == 22
    assert response.request_id == "synthetic-completion-id"
    kwargs = openai.return_value.chat.completions.create.call_args.kwargs
    assert kwargs["response_format"] == {"type": "json_object"}
    assert kwargs["messages"][0]["role"] == "system"
    assert SOURCE in kwargs["messages"][1]["content"]
    assert kwargs["max_tokens"] == settings.AI_MAX_OUTPUT_TOKENS


def test_langchain_rejects_invalid_provider_response(settings):
    settings.OPENAI_API_KEY = "synthetic-key"
    completion = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content='{"facts":"not a list"}'))],
        usage=None,
        id="bad-response",
    )
    with patch("chatbot.services.ai.OpenAI") as openai:
        openai.return_value.chat.completions.create.return_value = completion
        with pytest.raises((ValidationError, Exception)):
            invoke_fact_extraction(source_text=SOURCE)
