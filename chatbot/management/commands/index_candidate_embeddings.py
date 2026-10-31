from django.core.management.base import BaseCommand, CommandError

from chatbot.models import CandidateProfile
from chatbot.services.embeddings import EmbeddingUnavailable
from chatbot.services.semantic_index import index_candidate_public_facts


class Command(BaseCommand):
    """Explicitly index approved candidate facts within monetary quotas."""

    help = "Generate private pgvector embeddings for verified public facts."

    def add_arguments(self, parser):
        parser.add_argument("--candidate", required=True)
        parser.add_argument("--limit", type=int, default=10)

    def handle(self, *args, **options):
        candidate = CandidateProfile.objects.filter(slug=options["candidate"]).first()
        if candidate is None:
            raise CommandError("Candidate not found.")
        try:
            count = index_candidate_public_facts(
                candidate=candidate,
                initiated_by=candidate.user,
                max_new=options["limit"],
            )
        except (EmbeddingUnavailable, ValueError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(f"Indexed {count} approved candidate facts.")
