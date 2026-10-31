import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from chatbot.evaluation.live_experiment import run_paid_dataset
from chatbot.evaluation.paid_provider import ExperimentLimitError


class Command(BaseCommand):
    """Run an opt-in, capped paid evaluation on synthetic candidate facts."""

    help = "Evaluate three retrieval strategies with real model calls (explicit opt-in)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dataset",
            type=Path,
            default=(
                Path(__file__).resolve().parents[2]
                / "evaluation"
                / "data"
                / "synthetic_v1.json"
            ),
        )
        parser.add_argument("--output", type=Path, required=True)
        parser.add_argument("--allow-paid", action="store_true")
        parser.add_argument("--max-usd", default="1.00")
        parser.add_argument("--skip-judge", action="store_true")

    def handle(self, *args, **options):
        if not options["allow_paid"] or not settings.AI_EVALUATION_PAID_ENABLED:
            raise CommandError(
                "Paid evaluation requires --allow-paid and AI_EVALUATION_PAID_ENABLED=true."
            )
        if not settings.OPENAI_API_KEY:
            raise CommandError("OPENAI_API_KEY is not configured.")
        if options["output"].exists():
            raise CommandError("Refusing to overwrite an existing evaluation report.")

        try:
            report = run_paid_dataset(
                path=options["dataset"],
                key=settings.OPENAI_API_KEY,
                max_usd=options["max_usd"],
                judge=not options["skip_judge"],
            )
        except (ExperimentLimitError, ValueError) as exc:
            raise CommandError(str(exc)) from exc

        output = options["output"]
        try:
            output.parent.mkdir(parents=True, exist_ok=True)
            with output.open("x", encoding="utf-8") as stream:
                json.dump(report, stream, indent=2, sort_keys=True)
                stream.write("\n")
        except OSError as exc:
            raise CommandError("Could not persist the evaluation report.") from exc

        spent = report["provider_usage"]["estimated_spend_usd"]
        self.stdout.write(
            f"Paid evaluation completed; estimated USD {spent}; "
            f"report: {output}"
        )
