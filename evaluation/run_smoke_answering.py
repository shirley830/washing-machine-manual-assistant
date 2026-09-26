"""Check answer/refusal routing and evidence citations on the smoke test set."""

from __future__ import annotations

import csv
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from answer import answer_question  # noqa: E402
from retrieve import RetrievalInputError  # noqa: E402


TEST_SET = PROJECT_ROOT / "evaluation" / "smoke_test.csv"


def run_case(case: dict[str, str]) -> tuple[bool, str]:
    try:
        response = answer_question(
            brand=case["brand"],
            model=case["model"],
            question=case["question"],
        )
    except RetrievalInputError:
        response = {"status": "refusal", "citations": []}

    if case["answerable"] == "TRUE":
        citation_ids = {
            citation["chunk_id"] for citation in response.get("citations", [])
        }
        passed = (
            response["status"] == "answer"
            and case["evidence_chunk_id"] in citation_ids
        )
        detail = (
            f"status={response['status']}, expected={case['evidence_chunk_id']}, "
            f"citations={sorted(citation_ids)}"
        )
        return passed, detail

    passed = response["status"] == "refusal" and not response.get("citations")
    return passed, f"status={response['status']}, citations={response.get('citations', [])}"


def main() -> int:
    with TEST_SET.open(newline="", encoding="utf-8") as handle:
        cases = list(csv.DictReader(handle))

    passed_count = 0
    for case in cases:
        passed, detail = run_case(case)
        passed_count += int(passed)
        print(f"{'PASS' if passed else 'FAIL'} {case['case_id']}: {detail}")

    print(f"\nAnswer/refusal checks: {passed_count}/{len(cases)} passed")
    return 0 if passed_count == len(cases) else 1


if __name__ == "__main__":
    raise SystemExit(main())
