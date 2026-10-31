import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from chatbot.evaluation.baseline import (
    EvaluationDatasetError,
    evaluate_baseline,
    load_dataset,
    load_responses,
)


class Command(BaseCommand):
    """Run a deterministic, offline full-context candidate evaluation."""

    help = "Benchmark synthetic full-context retrieval without any AI API calls."

    def add_arguments(self, parser):
        default_dataset = (
            Path(__file__).resolve().parents[2]
            / "evaluation"
            / "data"
            / "synthetic_v1.json"
        )
        parser.add_argument("--dataset", type=Path, default=default_dataset)
        parser.add_argument("--responses", type=Path)
        parser.add_argument("--output", type=Path)
        parser.add_argument("--json", action="store_true")
        parser.add_argument("--fail-on-overflow", action="store_true")
        parser.add_argument("--max-input-bytes", type=int)

    def handle(self, *args, **options):
        try:
            dataset = load_dataset(options["dataset"])
            responses = None
            if options["responses"] is not None:
                responses = load_responses(
                    options["responses"],
                    case_ids={case["id"] for case in dataset["cases"]},
                )
            report = evaluate_baseline(
                dataset,
                input_limit_bytes=(
                    options["max_input_bytes"]
                    if options["max_input_bytes"] is not None
                    else settings.AI_MAX_INPUT_TOKENS
                ),
                overhead_bytes=settings.AI_CHAT_INPUT_OVERHEAD_BYTES,
                responses=responses,
            )
        except EvaluationDatasetError as exc:
            raise CommandError(str(exc)) from exc

        serialized = json.dumps(report, indent=2, sort_keys=True) + "\n"
        if options["output"] is not None:
            try:
                options["output"].write_text(serialized, encoding="utf-8")
            except OSError as exc:
                raise CommandError("Cannot write evaluation output.") from exc
        if options["json"]:
            self.stdout.write(serialized, ending="")
        else:
            metrics = report["metrics"]
            self.stdout.write(
                f"Strategy: {report['strategy']}; "
                f"cases: {metrics['cases']}; "
                f"retrieval recall: {metrics['retrieval_recall']}; "
                f"retrieval precision: {metrics['retrieval_precision']}; "
                f"over budget: {metrics['over_budget_cases']}"
            )
            if "response_metrics" in report:
                self.stdout.write(
                    "Offline response checks: "
                    + json.dumps(report["response_metrics"], sort_keys=True)
                )

        if options["fail_on_overflow"] and report["metrics"]["over_budget_cases"]:
            raise CommandError("Evaluation cases exceed the input budget.")
