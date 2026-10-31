import hashlib
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from chatbot.models import (
    AIUsageEvent,
    CandidateDocument,
    CandidateExtractionRun,
    CandidateFact,
)
from chatbot.policies import can_edit_candidate, get_ai_operation_policy
from chatbot.services.ai import (
    AIUnavailable,
    invoke_fact_extraction,
)
from chatbot.services.ai_budget import AIBudgetExceeded, settle_usage
from chatbot.services.ai_limits import AIQuotaExceeded, admit_ai_operation

EXTRACTION_VERSION = 1
STALE_RUN_AFTER = timedelta(minutes=5)


class KnowledgeExtractionError(Exception):
    """A private source document cannot be safely extracted."""


class ExtractionUnavailable(KnowledgeExtractionError):
    """Knowledge extraction is disabled or temporarily unavailable."""


@dataclass(frozen=True)
class ExtractionOutcome:
    proposed_count: int
    already_completed: bool


def _validate_document(*, document, candidate, initiated_by):
    if document.candidate_id != candidate.pk or not can_edit_candidate(
        initiated_by, candidate
    ):
        raise KnowledgeExtractionError("Document is not accessible.")
    if (
        document.processing_status != CandidateDocument.ProcessingStatus.PROCESSED
        or not document.extracted_text.strip()
    ):
        raise KnowledgeExtractionError("Document is not processed.")
    source = document.extracted_text
    if len(source.encode("utf-8")) > min(
        settings.AI_EXTRACTION_MAX_SOURCE_BYTES,
        max(0, settings.AI_MAX_INPUT_TOKENS - 2200),
    ):
        raise KnowledgeExtractionError("Document exceeds the extraction input limit.")
    return source


def _begin_run(document, fingerprint):
    now = timezone.now()
    with transaction.atomic():
        run, created = CandidateExtractionRun.objects.get_or_create(
            document=document,
            defaults={"source_sha256": fingerprint, "started_at": now},
        )
        run = CandidateExtractionRun.objects.select_for_update().get(pk=run.pk)
        if run.source_sha256 != fingerprint:
            raise KnowledgeExtractionError("Source changed; upload a new document.")
        if run.status == CandidateExtractionRun.Status.SUCCEEDED:
            return run, True
        if (
            not created
            and run.status == CandidateExtractionRun.Status.RUNNING
            and now - run.started_at < STALE_RUN_AFTER
        ):
            raise KnowledgeExtractionError("Extraction already in progress.")
        if not created:
            run.attempts += 1
            run.status = CandidateExtractionRun.Status.RUNNING
            run.started_at = now
            run.completed_at = None
            run.error_code = ""
            run.save(
                update_fields=[
                    "attempts",
                    "status",
                    "started_at",
                    "completed_at",
                    "error_code",
                ]
            )
        return run, False


def _validate_suggestions(facts, source_text):
    if len(facts) > settings.AI_EXTRACTION_MAX_FACTS:
        raise KnowledgeExtractionError("Extraction returned too many facts.")
    validated = []
    seen = set()
    for item in facts:
        if (
            item.fact_type not in CandidateFact.FactType.values
            or not 1 <= len(item.content.strip()) <= 4000
            or not 8 <= len(item.evidence_quote) <= 255
            or item.evidence_quote not in source_text
        ):
            raise KnowledgeExtractionError("Extraction returned invalid evidence.")
        key = (item.fact_type, item.content.strip(), item.evidence_quote)
        if key in seen:
            raise KnowledgeExtractionError("Extraction returned duplicate evidence.")
        seen.add(key)
        validated.append(key)
    return validated


def _mark_run_failed(run, code):
    CandidateExtractionRun.objects.filter(pk=run.pk).update(
        status=CandidateExtractionRun.Status.FAILED,
        completed_at=timezone.now(),
        error_code=code[:64],
    )


def _mark_usage_failed(usage, code):
    AIUsageEvent.objects.filter(pk=usage.pk).update(
        status=AIUsageEvent.Status.FAILED,
        completed_at=timezone.now(),
        error_code=code[:64],
    )


def extract_candidate_facts(*, document, candidate, initiated_by):
    """Create private, reviewable facts from an explicitly authorized source."""
    source = _validate_document(
        document=document, candidate=candidate, initiated_by=initiated_by
    )
    if (
        not settings.AI_ENABLED
        or not get_ai_operation_policy(
            AIUsageEvent.Operation.KNOWLEDGE_EXTRACTION
        ).enabled
    ):
        raise ExtractionUnavailable("Knowledge extraction is disabled.")
    if not settings.OPENAI_API_KEY:
        raise ExtractionUnavailable("Knowledge extraction provider is unconfigured.")

    fingerprint = hashlib.sha256(source.encode("utf-8")).hexdigest()
    run, completed = _begin_run(document, fingerprint)
    if completed:
        return ExtractionOutcome(
            proposed_count=run.proposed_count, already_completed=True
        )

    usage = None
    try:
        usage = admit_ai_operation(
            identity_id=initiated_by.pk,
            candidate_id=candidate.pk,
            operation=AIUsageEvent.Operation.KNOWLEDGE_EXTRACTION,
        )
        CandidateExtractionRun.objects.filter(pk=run.pk).update(last_usage_event=usage)
        result = invoke_fact_extraction(source_text=source)
        facts = _validate_suggestions(result.facts, source)

        with transaction.atomic():
            CandidateExtractionRun.objects.select_for_update().get(pk=run.pk)
            for fact_type, content, quote in facts:
                digest = hashlib.sha256(
                    (fact_type + "\0" + content + "\0" + quote).encode("utf-8")
                ).hexdigest()[:24]
                import_key = f"extract-v1-{document.pk}-{digest}"
                proposal = CandidateFact(
                    candidate=candidate,
                    source_document=document,
                    fact_type=fact_type,
                    content=content,
                    source_reference=quote,
                    import_key=import_key,
                )
                proposal.full_clean()
                proposal.save()

            run.status = CandidateExtractionRun.Status.SUCCEEDED
            run.proposed_count = len(facts)
            run.completed_at = timezone.now()
            run.error_code = ""
            run.save(
                update_fields=["status", "proposed_count", "completed_at", "error_code"]
            )

        usage.status = AIUsageEvent.Status.SUCCEEDED
        usage.input_tokens = result.input_tokens
        usage.output_tokens = result.output_tokens
        usage.provider_request_id = result.request_id
        usage.completed_at = timezone.now()
        usage.save(
            update_fields=[
                "status",
                "input_tokens",
                "output_tokens",
                "provider_request_id",
                "completed_at",
            ]
        )
        try:
            settle_usage(usage_id=usage.pk)
        except Exception:
            # Keep the original monetary reservation rather than retrying a paid call.
            import logging

            logging.getLogger(__name__).exception(
                "Extraction usage settlement failed for event %s", usage.pk
            )
        return ExtractionOutcome(proposed_count=len(facts), already_completed=False)
    except (AIQuotaExceeded, AIBudgetExceeded) as exc:
        _mark_run_failed(run, type(exc).__name__)
        raise ExtractionUnavailable("Extraction quota or budget exceeded.") from exc
    except Exception as exc:
        _mark_run_failed(run, type(exc).__name__)
        if usage is not None:
            _mark_usage_failed(usage, type(exc).__name__)
        if isinstance(exc, KnowledgeExtractionError):
            raise
        if isinstance(exc, AIUnavailable):
            raise ExtractionUnavailable(
                "Knowledge extraction provider unavailable."
            ) from exc
        raise KnowledgeExtractionError("Knowledge extraction failed.") from exc
