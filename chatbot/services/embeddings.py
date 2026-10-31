import hashlib
import logging
import math
import re

from django.conf import settings
from django.utils import timezone
from langchain_core.embeddings import Embeddings
from openai import OpenAI

from chatbot.models import AIUsageEvent
from chatbot.policies import can_edit_candidate, get_ai_operation_policy
from chatbot.services.ai_budget import AIBudgetExceeded, settle_usage
from chatbot.services.ai_limits import AIQuotaExceeded, admit_ai_operation


class EmbeddingUnavailable(Exception):
    """An embedding operation is unavailable or not authorized."""


def content_fingerprint(content: str) -> str:
    """Hash the exact content used to generate a fact vector."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


class BudgetedOpenAIEmbeddings(Embeddings):
    """Provide LangChain embeddings with reserved per-call project budget."""

    def __init__(self, *, candidate, initiated_by, operation):
        if operation not in (
            AIUsageEvent.Operation.EMBEDDING_INDEX,
            AIUsageEvent.Operation.EMBEDDING_QUERY,
        ):
            raise ValueError("Unsupported embedding operation.")
        if not can_edit_candidate(initiated_by, candidate):
            raise EmbeddingUnavailable("Not authorized to embed candidate data.")
        self.candidate = candidate
        self.initiated_by = initiated_by
        self.operation = operation

    def _embed(self, text: str) -> list[float]:
        if (
            not settings.AI_ENABLED
            or not get_ai_operation_policy(self.operation).enabled
            or not settings.OPENAI_API_KEY
        ):
            raise EmbeddingUnavailable("Embedding operation is disabled.")
        if (
            not text.strip()
            or len(text.encode("utf-8")) > settings.AI_EMBEDDING_MAX_INPUT_BYTES
        ):
            raise EmbeddingUnavailable("Embedding input exceeds the limit.")

        try:
            event = admit_ai_operation(
                identity_id=self.initiated_by.pk,
                candidate_id=self.candidate.pk,
                operation=self.operation,
                model=settings.AI_EMBEDDING_MODEL,
            )
        except (AIQuotaExceeded, AIBudgetExceeded) as exc:
            raise EmbeddingUnavailable("Embedding quota or budget exceeded.") from exc

        try:
            response = OpenAI(
                api_key=settings.OPENAI_API_KEY,
                timeout=settings.OPENAI_TIMEOUT_SECONDS,
                max_retries=0,
            ).embeddings.create(
                model=settings.AI_EMBEDDING_MODEL,
                input=text,
                dimensions=settings.AI_EMBEDDING_DIMENSIONS,
            )
            vector = list(response.data[0].embedding)
            if len(vector) != settings.AI_EMBEDDING_DIMENSIONS or not all(
                math.isfinite(x) for x in vector
            ):
                raise ValueError("Invalid embedding dimensions or values.")
            usage = response.usage
            event.status = AIUsageEvent.Status.SUCCEEDED
            event.input_tokens = usage.total_tokens if usage else None
            event.output_tokens = 0
            event.provider_request_id = getattr(response, "id", "") or ""
            event.completed_at = timezone.now()
            event.save(
                update_fields=[
                    "status",
                    "input_tokens",
                    "output_tokens",
                    "provider_request_id",
                    "completed_at",
                ]
            )
            try:
                settle_usage(usage_id=event.pk)
            except Exception:
                logging.getLogger(__name__).exception(
                    "Embedding budget settlement failed for event %s", event.pk
                )
            return vector
        except Exception as exc:
            if event.status != AIUsageEvent.Status.SUCCEEDED:
                AIUsageEvent.objects.filter(pk=event.pk).update(
                    status=AIUsageEvent.Status.FAILED,
                    completed_at=timezone.now(),
                    error_code="embedding_provider_failed",
                )
            raise EmbeddingUnavailable("Embedding provider unavailable.") from exc

    def embed_query(self, text: str) -> list[float]:
        """Generate one budgeted query embedding."""
        return self._embed(text)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Generate budgeted vectors one request at a time."""
        return [self._embed(text) for text in texts]


class DeterministicTestEmbeddings(Embeddings):
    """Produce offline lexical vectors for integration tests, not semantic quality."""

    dimensions = 256

    @staticmethod
    def _vector(text: str) -> list[float]:
        vector = [0.0] * 256
        for term in set(re.findall(r"[a-z0-9]{3,}", text.lower())):
            digest = hashlib.sha256(term.encode("utf-8")).digest()
            position = int.from_bytes(digest[:4], "big") % 256
            vector[position] += 1.0
        length = math.sqrt(sum(x * x for x in vector))
        if length:
            return [value / length for value in vector]
        return vector

    def embed_query(self, text: str) -> list[float]:
        """Embed test input locally without any API calls."""
        return self._vector(text)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed synthetic test documents deterministically."""
        return [self._vector(text) for text in texts]
