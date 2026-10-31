from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from chatbot.models import AIUsageEvent, CandidateProfile
from chatbot.services.embeddings import BudgetedOpenAIEmbeddings, EmbeddingUnavailable
from chatbot.services.semantic_retrieval import SemanticPgvectorRetriever


class Command(BaseCommand):
    """Run a budgeted owner-only semantic retrieval preview."""

    help = "Preview candidate-scoped semantic search; not a public chat endpoint."

    def add_arguments(self, parser):
        parser.add_argument("--candidate", required=True)
        parser.add_argument("--question", required=True)

    def handle(self, *args, **options):
        candidate = CandidateProfile.objects.filter(slug=options["candidate"]).first()
        if candidate is None:
            raise CommandError("Candidate not found.")
        embeddings = BudgetedOpenAIEmbeddings(
            candidate=candidate,
            initiated_by=candidate.user,
            operation=AIUsageEvent.Operation.EMBEDDING_QUERY,
        )
        try:
            results = SemanticPgvectorRetriever(
                embeddings=embeddings, model=settings.AI_EMBEDDING_MODEL
            ).retrieve(candidate=candidate, question=options["question"], history=[])
        except EmbeddingUnavailable as exc:
            raise CommandError(str(exc)) from exc
        for fact in results:
            self.stdout.write(f"{fact['id']} | {fact['fact_type']} | {fact['content']}")
