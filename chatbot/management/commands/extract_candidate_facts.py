from django.core.management.base import BaseCommand, CommandError

from chatbot.models import CandidateDocument, CandidateProfile
from chatbot.services.knowledge_extraction import (
    KnowledgeExtractionError,
    extract_candidate_facts,
)


class Command(BaseCommand):
    """Extract private fact proposals from an existing processed document."""

    help = "Extract pending and private candidate facts with explicit AI opt-in."

    def add_arguments(self, parser):
        parser.add_argument(
            "--candidate", required=True, help="Existing candidate slug"
        )
        parser.add_argument("--document", required=True, type=int, help="Document ID")

    def handle(self, *args, **options):
        candidate = CandidateProfile.objects.filter(slug=options["candidate"]).first()
        document = CandidateDocument.objects.filter(
            pk=options["document"], candidate=candidate
        ).first()
        if candidate is None or document is None:
            raise CommandError("Candidate or document not found.")

        try:
            outcome = extract_candidate_facts(
                candidate=candidate,
                document=document,
                initiated_by=candidate.user,
            )
        except KnowledgeExtractionError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(
            f"{outcome.proposed_count} private pending suggestions; "
            f"already completed: {outcome.already_completed}."
        )
