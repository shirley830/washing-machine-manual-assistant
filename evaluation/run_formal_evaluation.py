"""Run retrieval and grounded-answer evaluation on the fixed 50-case set."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from generate import grounded_answer  # noqa: E402
from retrieve import RetrievalInputError, retrieve  # noqa: E402


DEFAULT_CASES = PROJECT_ROOT / "evaluation" / "formal_evaluation_50.csv"
DEFAULT_RESULTS = PROJECT_ROOT / "evaluation" / "formal_results_50.csv"
DEFAULT_RETRIEVAL_RESULTS = (
    PROJECT_ROOT / "evaluation" / "formal_retrieval_results_50.csv"
)

RESULT_FIELDS = [
    "case_id",
    "category",
    "brand",
    "model",
    "question",
    "expected_behavior",
    "expected_answer",
    "acceptable_evidence_chunk_ids",
    "retrieved_top3_chunk_ids",
    "retrieval_rank",
    "retrieval_hit_at_3",
    "system_status",
    "system_reason",
    "system_answer",
    "cited_chunk_ids",
    "cited_pages",
    "behavior_pass",
    "model_used",
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "latency_seconds",
    "estimated_cost_usd",
    "faithfulness_review",
    "faithfulness_label",
    "faithfulness_notes",
    "error",
]


def parse_bool(value: str) -> bool:
    return value.strip().casefold() == "true"


def acceptable_ids(case: dict[str, str]) -> list[str]:
    raw = case.get("acceptable_evidence_chunk_ids", "").strip()
    if raw:
        return [value.strip() for value in raw.split("|") if value.strip()]
    primary = case.get("evidence_chunk_id", "").strip()
    return [primary] if primary else []


def refusal_for_unroutable(error: RetrievalInputError) -> dict[str, Any]:
    return {
        "status": "refusal",
        "answer": str(error),
        "citations": [],
        "usage": None,
    }


def evaluate_case(case: dict[str, str], generate_answers: bool) -> dict[str, str]:
    accepted = acceptable_ids(case)
    retrieved: list[dict[str, Any]] = []
    retrieval_error = ""
    try:
        retrieved = retrieve(
            brand=case["brand"],
            model=case["model"],
            question=case["question"],
            top_k=3,
        )
    except RetrievalInputError as error:
        retrieval_error = str(error)

    retrieved_ids = [result["chunk_id"] for result in retrieved]
    matching_ranks = [
        retrieved_ids.index(chunk_id) + 1
        for chunk_id in accepted
        if chunk_id in retrieved_ids
    ]
    retrieval_rank = min(matching_ranks) if matching_ranks else None

    response: dict[str, Any] = {
        "status": "not_run",
        "answer": "",
        "citations": [],
        "usage": None,
    }
    generation_error = ""
    if generate_answers:
        try:
            response = grounded_answer(
                brand=case["brand"],
                model=case["model"],
                question=case["question"],
            )
        except RetrievalInputError as error:
            response = refusal_for_unroutable(error)
        except Exception as error:  # preserve completed cases if one API call fails
            generation_error = f"{type(error).__name__}: {error}"
            response = {
                "status": "error",
                "answer": "",
                "citations": [],
                "usage": None,
            }

    expected_status = (
        "answer" if case["expected_behavior"] == "answer_with_citation" else "refusal"
    )
    citations = response.get("citations", [])
    cited_ids = [citation["chunk_id"] for citation in citations]
    cited_pages = [str(citation["page"]) for citation in citations]
    behavior_pass = response["status"] == expected_status
    if expected_status == "answer":
        behavior_pass = behavior_pass and bool(citations)

    usage = response.get("usage") or {}
    return {
        "case_id": case["case_id"],
        "category": case["category"],
        "brand": case["brand"],
        "model": case["model"],
        "question": case["question"],
        "expected_behavior": case["expected_behavior"],
        "expected_answer": case["expected_answer"],
        "acceptable_evidence_chunk_ids": "|".join(accepted),
        "retrieved_top3_chunk_ids": "|".join(retrieved_ids),
        "retrieval_rank": str(retrieval_rank or ""),
        "retrieval_hit_at_3": str(bool(retrieval_rank)).upper(),
        "system_status": response["status"],
        "system_reason": response.get("reason", ""),
        "system_answer": response.get("answer", ""),
        "cited_chunk_ids": "|".join(cited_ids),
        "cited_pages": "|".join(cited_pages),
        "behavior_pass": str(behavior_pass).upper(),
        "model_used": str(usage.get("model", "")),
        "input_tokens": str(usage.get("input_tokens", "")),
        "output_tokens": str(usage.get("output_tokens", "")),
        "total_tokens": str(usage.get("total_tokens", "")),
        "latency_seconds": str(usage.get("latency_seconds", "")),
        "estimated_cost_usd": str(usage.get("estimated_cost_usd", "")),
        "faithfulness_review": case["faithfulness_review"],
        "faithfulness_label": "",
        "faithfulness_notes": "",
        "error": generation_error,
    }


def save_results(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def print_summary(rows: list[dict[str, str]]) -> None:
    answerable = [row for row in rows if row["category"] == "answerable"]
    retrieval_hits = sum(parse_bool(row["retrieval_hit_at_3"]) for row in answerable)
    behavior_passes = sum(parse_bool(row["behavior_pass"]) for row in rows)
    api_rows = [row for row in rows if row["total_tokens"]]
    total_tokens = sum(int(row["total_tokens"]) for row in api_rows)
    total_cost = sum(float(row["estimated_cost_usd"] or 0) for row in api_rows)
    print(
        json.dumps(
            {
                "recall_at_3": f"{retrieval_hits}/{len(answerable)}",
                "recall_at_3_rate": round(retrieval_hits / len(answerable), 4),
                "behavior_pass": f"{behavior_passes}/{len(rows)}",
                "api_calls": len(api_rows),
                "total_tokens": total_tokens,
                "estimated_cost_usd": round(total_cost, 8),
            },
            indent=2,
        )
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--generate",
        action="store_true",
        help="Call the configured OpenRouter model for routable cases.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Reuse passing rows already present in the output and rerun failures only.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.output is None:
        args.output = DEFAULT_RESULTS if args.generate else DEFAULT_RETRIEVAL_RESULTS
    with args.cases.open(newline="", encoding="utf-8") as handle:
        cases = list(csv.DictReader(handle))

    prior_by_id: dict[str, dict[str, str]] = {}
    if args.resume and args.output.exists():
        with args.output.open(newline="", encoding="utf-8") as handle:
            prior_by_id = {
                row["case_id"]: row for row in csv.DictReader(handle)
            }

    results: list[dict[str, str]] = []
    for index, case in enumerate(cases, start=1):
        prior = prior_by_id.get(case["case_id"])
        if prior and parse_bool(prior.get("behavior_pass", "")):
            result = {field: prior.get(field, "") for field in RESULT_FIELDS}
            action = "reused"
        else:
            result = evaluate_case(case, args.generate)
            action = "evaluated"
        results.append(result)
        save_results(args.output, results)
        print(
            f"[{index:02d}/{len(cases)}] {case['case_id']} "
            f"{action} "
            f"retrieval={result['retrieval_hit_at_3']} "
            f"status={result['system_status']} "
            f"behavior={result['behavior_pass']}",
            flush=True,
        )

    print_summary(results)
    return 0 if all(parse_bool(row["behavior_pass"]) for row in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
