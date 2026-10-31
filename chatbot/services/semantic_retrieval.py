from langchain_core.runnables import RunnableLambda
from pgvector.django import CosineDistance

from chatbot.models import CandidateFactEmbedding
from chatbot.services.embeddings import content_fingerprint


class SemanticPgvectorRetriever:
    """Retrieve currently approved and version-matched candidate fact vectors."""

    name = "semantic_pgvector"
    max_results = 5

    def __init__(self, *, embeddings, model: str):
        self.embeddings = embeddings
        self.model = model
        self.chain = RunnableLambda(self._embed_query) | RunnableLambda(
            self._select_facts
        )

    def _embed_query(self, context):
        text = " ".join([context["question"], *context["history"][-1:]])
        return {
            "candidate": context["candidate"],
            "vector": self.embeddings.embed_query(text),
        }

    def _select_facts(self, context):
        candidate = context["candidate"]
        query = (
            CandidateFactEmbedding.objects.filter(
                fact__candidate=candidate,
                fact__verification_status="verified",
                fact__is_public=True,
                embedding_model=self.model,
            )
            .select_related("fact")
            .annotate(distance=CosineDistance("vector", context["vector"]))
            .order_by("distance", "fact_id")
        )
        selected = []
        for stored in query[:30]:
            fact = stored.fact
            if stored.content_sha256 != content_fingerprint(fact.content):
                continue
            selected.append(
                {"id": fact.pk, "fact_type": fact.fact_type, "content": fact.content}
            )
            if len(selected) >= self.max_results:
                break
        return selected

    def retrieve(self, *, candidate, question: str, history):
        """Invoke the LangChain embedding and pgvector retrieval pipeline."""
        return self.chain.invoke(
            {"candidate": candidate, "question": question, "history": history}
        )
