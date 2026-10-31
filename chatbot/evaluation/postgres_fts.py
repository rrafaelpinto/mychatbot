from contextlib import contextmanager
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.db import connection, transaction

from chatbot.models import CandidateFact, CandidateProfile
from chatbot.services.retrieval import PostgresFTSRetriever

from .baseline import EvaluationDatasetError


class SyntheticPostgresFTSRetriever:
    """Map temporary database records back to stable synthetic fixture IDs."""

    name = "postgres_fts"

    def __init__(self, *, candidate, id_map):
        self.candidate = candidate
        self.id_map = id_map
        self.retriever = PostgresFTSRetriever()

    def retrieve(self, *, facts, question, history):
        """Return ranked synthetic facts with stable evaluation identifiers."""
        del facts
        result = self.retriever.retrieve(
            candidate=self.candidate, question=question, history=history
        )
        return [
            {**item, "id": self.id_map[item["id"]]}
            for item in result
        ]


@contextmanager
def synthetic_postgres_fts(dataset):
    """Evaluate the real ORM strategy in a transaction that always rolls back."""
    if connection.vendor != "postgresql":
        raise EvaluationDatasetError("PostgreSQL is required for FTS comparison.")

    with transaction.atomic():
        identity = uuid4().hex
        owner = get_user_model().objects.create_user(
            username=f"fts-eval-{identity}", password=None
        )
        candidate = CandidateProfile.objects.create(
            user=owner, name=f"Synthetic Evaluation {identity[:12]}"
        )
        id_map = {}
        for fact in dataset["facts"]:
            saved = CandidateFact.objects.create(
                candidate=candidate,
                fact_type=fact["fact_type"],
                content=fact["content"],
                verification_status=fact["verification_status"],
                is_public=fact["is_public"],
                import_key=f"eval-{fact['key']}",
            )
            id_map[saved.pk] = fact["id"]

        try:
            yield SyntheticPostgresFTSRetriever(
                candidate=candidate, id_map=id_map
            )
        finally:
            transaction.set_rollback(True)
