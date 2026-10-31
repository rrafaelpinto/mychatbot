from django.conf import settings
from django.db import transaction

from chatbot.models import AIUsageEvent, CandidateFact, CandidateFactEmbedding
from chatbot.policies import can_edit_candidate
from chatbot.services.embeddings import (
    BudgetedOpenAIEmbeddings,
    EmbeddingUnavailable,
    content_fingerprint,
)


def index_candidate_public_facts(*, candidate, initiated_by, max_new: int = 10):
    """Refresh approved candidate vectors through budgeted LangChain embeddings."""
    if not can_edit_candidate(initiated_by, candidate):
        raise EmbeddingUnavailable("Not authorized to index candidate facts.")
    if not 1 <= max_new <= 20:
        raise ValueError("Invalid indexing batch size.")

    embeddings = BudgetedOpenAIEmbeddings(
        candidate=candidate,
        initiated_by=initiated_by,
        operation=AIUsageEvent.Operation.EMBEDDING_INDEX,
    )
    indexed = 0
    facts = CandidateFact.objects.filter(
        candidate=candidate, verification_status="verified", is_public=True
    ).order_by("pk")
    for fact in facts:
        digest = content_fingerprint(fact.content)
        existing = CandidateFactEmbedding.objects.filter(fact=fact).first()
        if (
            existing
            and existing.embedding_model == settings.AI_EMBEDDING_MODEL
            and existing.content_sha256 == digest
        ):
            continue
        if indexed >= max_new:
            break
        vector = embeddings.embed_query(fact.content)
        with transaction.atomic():
            current = CandidateFact.objects.select_for_update().get(pk=fact.pk)
            if (
                current.verification_status != "verified"
                or not current.is_public
                or content_fingerprint(current.content) != digest
            ):
                continue
            CandidateFactEmbedding.objects.update_or_create(
                fact=current,
                defaults={
                    "embedding_model": settings.AI_EMBEDDING_MODEL,
                    "content_sha256": digest,
                    "vector": vector,
                },
            )
        indexed += 1
    return indexed
