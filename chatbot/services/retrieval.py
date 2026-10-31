from collections.abc import Iterable, Mapping, Sequence


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


def retrieve_candidate_facts(*, candidate, question: str, history: list[str]):
    """Retrieve only candidate-owned facts approved for public interaction."""
    approved = candidate.facts.filter(
        verification_status="verified", is_public=True
    ).values(
        "id", "fact_type", "content", "verification_status", "is_public"
    )
    return FullContextRetriever().retrieve(
        facts=approved,
        question=question,
        history=history,
    )
