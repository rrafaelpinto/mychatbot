import json
import re
from pathlib import Path

from chatbot.services.ai import (
    UNSUPPORTED_ANSWER,
    AIUnavailable,
    build_candidate_payload,
    parse_candidate_answer,
)
from chatbot.services.retrieval import FullContextRetriever

KEY_RE = re.compile(r"[a-z][a-z0-9_-]{1,63}\Z")
CASE_TYPES = {"answerable", "unanswerable", "adversarial"}
FACT_TYPES = {"summary", "experience", "education", "skill", "project", "other"}
STATUSES = {"pending", "verified", "rejected"}


class EvaluationDatasetError(ValueError):
    """The evaluation fixture does not satisfy the versioned contract."""


def _require(condition, message):
    if not condition:
        raise EvaluationDatasetError(message)


def load_dataset(path: Path) -> dict:
    """Read and validate a versioned evaluation corpus and annotated questions."""
    try:
        dataset = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise EvaluationDatasetError("Cannot read evaluation dataset.") from exc
    _require(isinstance(dataset, dict), "Dataset must be an object.")
    _require(dataset.get("version") == 1, "Unsupported dataset version.")
    _require(isinstance(dataset.get("facts"), list), "Facts must be a list.")
    _require(isinstance(dataset.get("cases"), list), "Cases must be a list.")
    _require(bool(dataset["facts"]), "Corpus must not be empty.")
    _require(bool(dataset["cases"]), "Evaluation cases must not be empty.")

    fact_keys = set()
    fact_ids = set()
    approved_keys = set()
    for fact in dataset["facts"]:
        _require(isinstance(fact, dict), "Every fact must be an object.")
        _require(
            set(fact)
            == {
                "key", "id", "fact_type", "content",
                "verification_status", "is_public",
            },
            "Unexpected fact fields.",
        )
        key = fact["key"]
        _require(
            isinstance(key, str) and bool(KEY_RE.fullmatch(key)),
            "Invalid fact key.",
        )
        _require(key not in fact_keys, "Duplicate fact key.")
        _require(
            type(fact["id"]) is int and fact["id"] > 0,
            "Invalid fact numeric ID.",
        )
        _require(fact["id"] not in fact_ids, "Duplicate fact numeric ID.")
        _require(fact["fact_type"] in FACT_TYPES, "Unknown fact category.")
        _require(
            isinstance(fact["content"], str) and bool(fact["content"].strip())
            and len(fact["content"]) <= 4000,
            "Invalid fact content.",
        )
        _require(
            fact["verification_status"] in STATUSES
            and type(fact["is_public"]) is bool,
            "Invalid verification or visibility.",
        )
        _require(
            not fact["is_public"] or fact["verification_status"] == "verified",
            "Public facts must be verified.",
        )
        fact_keys.add(key)
        fact_ids.add(fact["id"])
        if fact["is_public"] and fact["verification_status"] == "verified":
            approved_keys.add(key)

    case_ids = set()
    for case in dataset["cases"]:
        _require(isinstance(case, dict), "Every case must be an object.")
        _require(
            {"id", "category", "question", "expected_fact_keys"} <= set(case)
            and set(case) <= {
                "id", "category", "question", "expected_fact_keys", "history"
            },
            "Unexpected evaluation case fields.",
        )
        case_id = case["id"]
        _require(
            isinstance(case_id, str) and bool(KEY_RE.fullmatch(case_id.lower())),
            "Invalid case identifier.",
        )
        _require(case_id not in case_ids, "Duplicate case identifier.")
        _require(case["category"] in CASE_TYPES, "Unknown case category.")
        _require(
            isinstance(case["question"], str)
            and 1 <= len(case["question"].strip()) <= 1000,
            "Invalid evaluation question.",
        )
        expected = case["expected_fact_keys"]
        _require(
            isinstance(expected, list)
            and all(isinstance(key, str) for key in expected)
            and len(set(expected)) == len(expected),
            "Invalid expected fact keys.",
        )
        _require(set(expected) <= approved_keys, "Expected private or missing fact.")
        if case["category"] == "answerable":
            _require(bool(expected), "Answerable cases must cite a gold fact.")
        if case["category"] == "unanswerable":
            _require(not expected, "Unanswerable cases cannot have gold facts.")
        history = case.get("history", [])
        _require(
            isinstance(history, list)
            and len(history) <= 4
            and all(
                isinstance(item, str) and len(item) <= 500 for item in history
            ),
            "Invalid evaluation history.",
        )
        case_ids.add(case_id)

    return dataset


def load_responses(path: Path, *, case_ids: set[str]) -> dict:
    """Validate an optional, explicitly captured model-response artifact."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise EvaluationDatasetError("Cannot read response artifact.") from exc
    _require(
        isinstance(data, dict)
        and data.get("version") == 1
        and isinstance(data.get("responses"), list),
        "Invalid response artifact.",
    )
    responses = {}
    for row in data["responses"]:
        _require(
            isinstance(row, dict) and set(row) == {"id", "output"},
            "Invalid response row.",
        )
        _require(
            isinstance(row["id"], str)
            and row["id"] in case_ids
            and row["id"] not in responses,
            "Unknown or duplicate response case.",
        )
        responses[row["id"]] = row["output"]
    return responses


def _ratio(numerator: int, denominator: int):
    return round(numerator / denominator, 4) if denominator else None


def evaluate_baseline(
    dataset: dict,
    *,
    input_limit_bytes: int,
    overhead_bytes: int,
    responses: dict | None = None,
) -> dict:
    """Measure full-context retrieval without sending any data to a model."""
    _require(
        type(input_limit_bytes) is int and input_limit_bytes > 0,
        "Input budget must be positive.",
    )
    _require(
        type(overhead_bytes) is int and overhead_bytes >= 0,
        "Input overhead must be nonnegative.",
    )
    retriever = FullContextRetriever()
    facts = dataset["facts"]
    key_by_id = {fact["id"]: fact["key"] for fact in facts}
    rows = []
    total_expected = 0
    total_retrieved = 0
    total_relevant = 0
    complete_cases = 0
    overflow_cases = 0
    total_payload_bytes = 0
    answered = []

    for case in dataset["cases"]:
        history = case.get("history", [])
        retrieved = retriever.retrieve(
            facts=facts, question=case["question"], history=history
        )
        retrieved_ids = {fact["id"] for fact in retrieved}
        retrieved_keys = {key_by_id[pk] for pk in retrieved_ids}
        expected = set(case["expected_fact_keys"])
        matched = expected & retrieved_keys

        payload_bytes = len(
            build_candidate_payload(
                facts=retrieved, question=case["question"], history=history
            ).encode("utf-8")
        )
        input_bytes = payload_bytes + overhead_bytes
        within_limit = input_bytes <= input_limit_bytes

        total_expected += len(expected)
        total_retrieved += len(retrieved_keys)
        total_relevant += len(matched)
        complete_cases += int(expected <= retrieved_keys)
        overflow_cases += int(not within_limit)
        total_payload_bytes += payload_bytes
        rows.append(
            {
                "id": case["id"],
                "category": case["category"],
                "expected_fact_keys": sorted(expected),
                "retrieved_fact_keys": sorted(retrieved_keys),
                "matched_fact_keys": sorted(matched),
                "input_payload_bytes": payload_bytes,
                "input_plus_overhead_bytes": input_bytes,
                "approx_input_tokens": (input_bytes + 3) // 4,
                "within_input_budget": within_limit,
            }
        )

        if responses is not None and case["id"] in responses:
            output = responses[case["id"]]
            valid = False
            text = ""
            cited = ()
            try:
                text, cited = parse_candidate_answer(
                    json.dumps(output, ensure_ascii=False)
                )
                valid = True
            except (AIUnavailable, TypeError, ValueError):
                pass
            cited_ids = set(cited)
            correct_ids = {
                fact["id"] for fact in facts if fact["key"] in expected
            }
            answered.append(
                {
                    "id": case["id"],
                    "valid": valid,
                    "refusal_mode_correct": (
                        valid and (text == UNSUPPORTED_ANSWER) == (not expected)
                    ),
                    "cited": len(cited_ids),
                    "cited_relevant": len(cited_ids & correct_ids),
                    "cited_unauthorized": len(cited_ids - retrieved_ids),
                    "expected": len(expected),
                }
            )

    metrics = {
        "cases": len(rows),
        "answerable": sum(
            case["category"] == "answerable" for case in dataset["cases"]
        ),
        "unanswerable": sum(
            case["category"] == "unanswerable" for case in dataset["cases"]
        ),
        "adversarial": sum(
            case["category"] == "adversarial" for case in dataset["cases"]
        ),
        "retrieval_recall": _ratio(total_relevant, total_expected),
        "retrieval_precision": _ratio(total_relevant, total_retrieved),
        "complete_evidence_case_rate": _ratio(complete_cases, len(rows)),
        "over_budget_cases": overflow_cases,
        "mean_payload_bytes": round(total_payload_bytes / len(rows)),
    }
    result = {
        "schema_version": 1,
        "strategy": retriever.name,
        "dataset_version": dataset["version"],
        "corpus_facts": len(facts),
        "approved_facts": len(retriever.retrieve(facts=facts, question="", history=[])),
        "input_limit_bytes": input_limit_bytes,
        "input_overhead_bytes": overhead_bytes,
        "metrics": metrics,
        "cases": rows,
    }
    if responses is not None:
        result["response_metrics"] = {
            "evaluated_cases": len(answered),
            "invalid_output_cases": sum(not row["valid"] for row in answered),
            "refusal_mode_accuracy": _ratio(
                sum(row["refusal_mode_correct"] for row in answered), len(answered)
            ),
            "citation_precision": _ratio(
                sum(row["cited_relevant"] for row in answered),
                sum(row["cited"] for row in answered),
            ),
            "citation_recall": _ratio(
                sum(row["cited_relevant"] for row in answered),
                sum(row["expected"] for row in answered),
            ),
            "unauthorized_citations": sum(
                row["cited_unauthorized"] for row in answered
            ),
        }
    return result
