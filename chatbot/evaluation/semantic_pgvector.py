from contextlib import contextmanager

from django.conf import settings

from chatbot.models import CandidateFactEmbedding
from chatbot.services.embeddings import (
    DeterministicTestEmbeddings,
    content_fingerprint,
)
from chatbot.services.semantic_retrieval import SemanticPgvectorRetriever

from .postgres_fts import synthetic_postgres_fts


class SyntheticSemanticRetriever:
    """Map pgvector retrieval IDs to stable synthetic fixture IDs."""

    name = "semantic_pgvector"

    def __init__(self, *, candidate, id_map):
        self.candidate = candidate
        self.id_map = id_map
        self.retriever = SemanticPgvectorRetriever(
            embeddings=DeterministicTestEmbeddings(),
            model=settings.AI_EMBEDDING_MODEL,
        )

    def retrieve(self, *, facts, question, history):
        """Retrieve evaluated synthetic facts without generating paid embeddings."""
        del facts
        results = self.retriever.retrieve(
            candidate=self.candidate, question=question, history=history
        )
        return [{**row, "id": self.id_map[row["id"]]} for row in results]


@contextmanager
def synthetic_semantic_pgvector(dataset):
    """Index synthetic facts and roll back all changes after evaluation."""
    with synthetic_postgres_fts(dataset) as adapter:
        candidate = adapter.candidate
        embedder = DeterministicTestEmbeddings()
        facts = list(
            candidate.facts.filter(
                verification_status="verified", is_public=True
            ).order_by("pk")
        )
        vectors = embedder.embed_documents([fact.content for fact in facts])
        for fact, vector in zip(facts, vectors, strict=True):
            CandidateFactEmbedding.objects.create(
                fact=fact,
                embedding_model=settings.AI_EMBEDDING_MODEL,
                content_sha256=content_fingerprint(fact.content),
                vector=vector,
            )
        yield SyntheticSemanticRetriever(candidate=candidate, id_map=adapter.id_map)
