"""Run the answerable smoke-test cases and report retrieval Recall@3."""

from __future__ import annotations

import csv
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from retrieve import retrieve  # noqa: E402


TEST_SET = PROJECT_ROOT / "evaluation" / "smoke_test.csv"


def main() -> int:
    with TEST_SET.open(newline="", encoding="utf-8") as handle:
        cases = list(csv.DictReader(handle))

    answerable_cases = [case for case in cases if case["answerable"] == "TRUE"]
    hits = 0

    for case in answerable_cases:
        results = retrieve(
            brand=case["brand"],
            model=case["model"],
            question=case["question"],
            top_k=3,
        )
        retrieved_ids = [result["chunk_id"] for result in results]
        passed = case["evidence_chunk_id"] in retrieved_ids
        hits += int(passed)
        status = "PASS" if passed else "FAIL"
        print(
            f"{status} {case['case_id']}: expected {case['evidence_chunk_id']} | "
            f"retrieved {', '.join(retrieved_ids)}"
        )

    recall_at_3 = hits / len(answerable_cases) if answerable_cases else 0.0
    print(
        f"\nRecall@3: {hits}/{len(answerable_cases)} "
        f"({recall_at_3:.1%})"
    )
    return 0 if hits == len(answerable_cases) else 1


if __name__ == "__main__":
    raise SystemExit(main())
