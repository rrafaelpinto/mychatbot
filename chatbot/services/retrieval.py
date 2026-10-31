import re
from collections.abc import Iterable, Mapping, Sequence
from functools import reduce
from operator import or_

from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector

STOP_WORDS = {
    "about",
    "also",
    "candidate",
    "could",
    "does",
    "have",
    "has",
    "how",
    "into",
    "their",
    "them",
    "there",
    "this",
    "those",
    "used",
    "using",
    "what",
    "when",
    "where",
    "which",
    "with",
    "work",
    "worked",
    "would",
}
TERM_PATTERN = re.compile(r"[a-zA-Z][a-zA-Z0-9]{2,}")


class FullContextRetriever:
    """Include every verified and explicitly public fact, without ranking."""

    name = "full_context"

    def retrieve(
        self,
        *,
        facts: Iterable[Mapping],
        question: str,
        history: Sequence[str],
    ) -> list[dict]:
        """Return approved facts in deterministic order for candidate chat."""
        del question, history
        return sorted(
            [
                {
                    "id": fact["id"],
                    "fact_type": fact["fact_type"],
                    "content": fact["content"],
                }
                for fact in facts
                if fact["verification_status"] == "verified"
                and fact["is_public"] is True
            ],
            key=lambda fact: fact["id"],
        )


class PostgresFTSRetriever:
    """Rank approved candidate facts with native PostgreSQL full-text search."""

    name = "postgres_fts"
    max_results = 5
    max_terms = 12
    language = "english"

    @classmethod
    def search_terms(cls, *, question: str, history: Sequence[str]) -> list[str]:
        """Extract a bounded set of lexical terms from untrusted questions."""
        terms = []
        texts = [question, *list(history)[-1:]]
        for text in texts:
            for term in TERM_PATTERN.findall(text[:500].lower()):
                if term not in STOP_WORDS and term not in terms:
                    terms.append(term)
                    if len(terms) >= cls.max_terms:
                        return terms
        return terms

    def retrieve(self, *, candidate, question: str, history: Sequence[str]):
        """Retrieve only currently approved facts within the selected candidate."""
        terms = self.search_terms(question=question, history=history)
        if not terms:
            return []

        query = reduce(
            or_,
            (
                SearchQuery(term, config=self.language, search_type="plain")
                for term in terms
            ),
        )
        vector = SearchVector("content", config=self.language)
        queryset = (
            candidate.facts.filter(verification_status="verified", is_public=True)
            .annotate(search_document=vector)
            .filter(search_document=query)
            .annotate(search_rank=SearchRank(vector, query))
            .order_by("-search_rank", "id")[: self.max_results]
        )
        return list(queryset.values("id", "fact_type", "content"))


def retrieve_candidate_facts(*, candidate, question: str, history: list[str]):
    """Retrieve the approved production corpus using full-context prompting."""
    approved = candidate.facts.filter(
        verification_status="verified", is_public=True
    ).values("id", "fact_type", "content", "verification_status", "is_public")
    return FullContextRetriever().retrieve(
        facts=approved,
        question=question,
        history=history,
    )
