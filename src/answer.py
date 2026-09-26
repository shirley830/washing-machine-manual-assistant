"""Create an evidence-gated extractive answer from retrieved manual passages."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from retrieve import (
    RetrievalInputError,
    canonical,
    extract_error_codes,
    retrieve,
    tokenize,
)


STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "brand",
    "code",
    "do",
    "does",
    "error",
    "for",
    "how",
    "i",
    "in",
    "is",
    "it",
    "machine",
    "mean",
    "model",
    "my",
    "of",
    "on",
    "should",
    "the",
    "this",
    "to",
    "washer",
    "washing",
    "what",
}

TOKEN_ALIASES = {
    "cleaning": "clean",
    "cleaned": "clean",
    "connects": "connect",
    "connected": "connect",
    "connecting": "connect",
    "programmes": "program",
    "programme": "program",
    "programs": "program",
    "settings": "setting",
    "using": "use",
    "used": "use",
    "uses": "use",
}

SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\s*[•▶■]\s*")


def normalize_token(token: str) -> str:
    """Apply small transparent normalizations used by the evidence gate."""
    token = TOKEN_ALIASES.get(token, token)
    if len(token) > 4 and token.endswith("s"):
        token = token[:-1]
    return token


def content_terms(text: str) -> set[str]:
    """Return meaningful question terms after removing generic words."""
    return {
        normalize_token(token)
        for token in tokenize(text)
        if normalize_token(token) not in STOPWORDS
        and not canonical(token).isdigit()
    }


def evidence_coverage(question: str, passage: str) -> tuple[float, set[str]]:
    """Measure how many meaningful question terms occur in one passage."""
    required = content_terms(question)
    passage_terms = {normalize_token(token) for token in tokenize(passage)}
    matched = required & passage_terms
    if not required:
        return 0.0, matched
    return len(matched) / len(required), matched


def evidence_is_sufficient(
    question: str, results: list[dict[str, Any]], minimum_coverage: float = 0.6
) -> tuple[bool, str, float]:
    """Require exact technical codes or sufficient key-term coverage."""
    if not results or results[0]["score"] <= 0:
        return False, "No relevant passage was found in the selected manual.", 0.0

    question_codes = extract_error_codes(question)
    if question_codes:
        for result in results:
            if question_codes & extract_error_codes(result["text"]):
                return True, "An exact error code appears in the evidence.", 1.0
        return False, "The requested error code does not appear in the evidence.", 0.0

    coverage, matched = evidence_coverage(question, results[0]["text"])
    if coverage < minimum_coverage:
        matched_text = ", ".join(sorted(matched)) or "none"
        return (
            False,
            f"The best passage covers too few key terms (matched: {matched_text}).",
            coverage,
        )
    return True, "The best passage contains the required key terms.", coverage


def extract_answer_sentences(question: str, passage: str, limit: int = 3) -> str:
    """Select a few highly overlapping sentences without inventing new claims."""
    required = content_terms(question)
    question_codes = extract_error_codes(question)
    candidates: list[tuple[int, int, str]] = []

    for position, raw_sentence in enumerate(SENTENCE_SPLIT.split(passage)):
        sentence = raw_sentence.strip()
        if not sentence:
            continue
        sentence_terms = {normalize_token(token) for token in tokenize(sentence)}
        overlap = len(required & sentence_terms)
        code_bonus = 5 * len(question_codes & extract_error_codes(sentence))
        candidates.append((overlap + code_bonus, position, sentence))

    selected = sorted(candidates, key=lambda item: (-item[0], item[1]))[:limit]
    selected = sorted(selected, key=lambda item: item[1])
    return " ".join(sentence for _, _, sentence in selected)


def answer_question(
    *, brand: str, model: str, question: str, top_k: int = 3
) -> dict[str, Any]:
    """Return an extractive answer or a traceable refusal."""
    results = retrieve(
        brand=brand,
        model=model,
        question=question,
        top_k=top_k,
    )
    sufficient, reason, coverage = evidence_is_sufficient(question, results)
    if not sufficient:
        return {
            "status": "refusal",
            "answer": (
                "I could not find sufficient evidence in the official manual for "
                f"{brand} {model}."
            ),
            "reason": reason,
            "coverage": round(coverage, 3),
            "citations": [],
        }

    best = results[0]
    return {
        "status": "answer",
        "answer": extract_answer_sentences(question, best["text"]),
        "reason": reason,
        "coverage": round(coverage, 3),
        "citations": [
            {
                "chunk_id": best["chunk_id"],
                "brand": best["brand"],
                "model": best["model"],
                "page": best["page"],
                "source_file": best["source_file"],
                "source_url": best["source_url"],
            }
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Answer from one supported manual or refuse without evidence."
    )
    parser.add_argument("--brand", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--question", required=True)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        response = answer_question(
            brand=args.brand,
            model=args.model,
            question=args.question,
        )
    except (RetrievalInputError, FileNotFoundError) as error:
        response = {
            "status": "refusal",
            "answer": str(error),
            "reason": "The request cannot be safely routed to one supported manual.",
            "coverage": 0.0,
            "citations": [],
        }

    if args.json:
        print(json.dumps(response, ensure_ascii=False, indent=2))
    else:
        print(response["answer"])
        if response["citations"]:
            citation = response["citations"][0]
            print(
                f"Source: {citation['brand']} {citation['model']}, "
                f"page {citation['page']} ({citation['source_file']})"
            )
        else:
            print(f"Reason: {response['reason']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
