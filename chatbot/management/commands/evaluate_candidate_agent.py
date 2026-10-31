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
from chatbot.evaluation.postgres_fts import synthetic_postgres_fts


class Command(BaseCommand):
    """Run an offline Candidate Agent retrieval evaluation."""

    help = "Compare full-context and PostgreSQL FTS with synthetic candidate facts."

    def add_arguments(self, parser):
        default_dataset = (
            Path(__file__).resolve().parents[2]
            / "evaluation"
            / "data"
            / "synthetic_v1.json"
        )
        parser.add_argument("--dataset", type=Path, default=default_dataset)
        parser.add_argument("--responses", type=Path)
        parser.add_argument(
            "--strategy",
            choices=("full_context", "postgres_fts", "compare"),
            default="full_context",
        )
        parser.add_argument("--output", type=Path)
        parser.add_argument("--json", action="store_true")
        parser.add_argument("--fail-on-overflow", action="store_true")
        parser.add_argument("--max-input-bytes", type=int)

    def handle(self, *args, **options):
        strategy = options["strategy"]
        if strategy == "compare" and options["responses"] is not None:
            raise CommandError("Response replay requires one retrieval strategy.")

        try:
            dataset = load_dataset(options["dataset"])
            responses = None
            if options["responses"] is not None:
                responses = load_responses(
                    options["responses"],
                    case_ids={case["id"] for case in dataset["cases"]},
                )

            limits = {
                "input_limit_bytes": (
                    options["max_input_bytes"]
                    if options["max_input_bytes"] is not None
                    else settings.AI_MAX_INPUT_TOKENS
                ),
                "overhead_bytes": settings.AI_CHAT_INPUT_OVERHEAD_BYTES,
            }
            reports = {}
            if strategy in {"full_context", "compare"}:
                reports["full_context"] = evaluate_baseline(
                    dataset, responses=responses, **limits
                )
            if strategy in {"postgres_fts", "compare"}:
                with synthetic_postgres_fts(dataset) as retriever:
                    reports["postgres_fts"] = evaluate_baseline(
                        dataset,
                        responses=responses,
                        retriever=retriever,
                        **limits,
                    )
            if strategy == "compare":
                full = reports["full_context"]["metrics"]
                fts = reports["postgres_fts"]["metrics"]
                report = {
                    "schema_version": 1,
                    "dataset_version": dataset["version"],
                    "strategies": reports,
                    "comparison": {
                        "retrieval_recall_delta": round(
                            fts["retrieval_recall"] - full["retrieval_recall"], 4
                        ),
                        "retrieval_precision_delta": round(
                            fts["retrieval_precision"] - full["retrieval_precision"], 4
                        ),
                        "mean_payload_bytes_delta": (
                            fts["mean_payload_bytes"] - full["mean_payload_bytes"]
                        ),
                    },
                }
            else:
                report = reports[strategy]
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
            for item in reports.values():
                metrics = item["metrics"]
                self.stdout.write(
                    f"Strategy: {item['strategy']}; "
                    f"cases: {metrics['cases']}; "
                    f"retrieval recall: {metrics['retrieval_recall']}; "
                    f"retrieval precision: {metrics['retrieval_precision']}; "
                    f"over budget: {metrics['over_budget_cases']}"
                )
                if "response_metrics" in item:
                    self.stdout.write(
                        "Offline response checks: "
                        + json.dumps(item["response_metrics"], sort_keys=True)
                    )

        if options["fail_on_overflow"] and any(
            item["metrics"]["over_budget_cases"] for item in reports.values()
        ):
            raise CommandError("Evaluation cases exceed the input budget.")
