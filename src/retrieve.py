"""Retrieve model-specific manual passages with a local BM25 baseline."""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = PROJECT_ROOT / "data" / "manuals_manifest.csv"
DEFAULT_CHUNKS = PROJECT_ROOT / "outputs" / "chunks.jsonl"

TOKEN_PATTERN = re.compile(r"[^\W_]+(?:[-:/][^\W_]+)*", re.IGNORECASE)
ERROR_CODE_PATTERN = re.compile(r"\b[a-z]\s*:?\s*\d{2,}\b", re.IGNORECASE)

# Transparent domain vocabulary used to bridge English questions and German manuals.
# The original question remains unchanged for display and logging.
QUERY_EXPANSIONS = {
    "add laundry": "adding laundry garments programme start pause",
    "child lock": "kindersicherung aktivieren deaktivieren",
    "detergent drawer": "waschmittelschublade",
    "drain pump": "laugenpumpe reinigen",
    "emergency release": "notentriegelung",
    "excessive foam": "starke schaumbildung sofortmaßnahme",
    "main wash": "hauptwaschgang",
    "network settings": "netzwerkeinstellungen zurücksetzen",
    "power failure": "stromausfall",
    "remote start": "remote start deactivated circumstances",
    "sort laundry": "wäsche sortieren",
    "unlock the door manually": "notentriegelung tür entriegeln",
}


class RetrievalInputError(ValueError):
    """Raised when retrieval cannot safely start with the supplied metadata."""


def canonical(value: str) -> str:
    """Normalize brand and model strings for case-insensitive matching."""
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def tokenize(text: str) -> list[str]:
    """Create simple lowercase tokens without external dependencies."""
    return [token.casefold() for token in TOKEN_PATTERN.findall(text)]


def expand_query(query: str) -> str:
    """Append a small auditable bilingual vocabulary to the user's query."""
    normalized = " ".join(tokenize(query))
    additions = [
        expansion
        for phrase, expansion in QUERY_EXPANSIONS.items()
        if phrase in normalized
    ]
    if not additions:
        return query
    return f"{query} {' '.join(additions)}"


def extract_error_codes(text: str) -> set[str]:
    """Normalize error codes so E30 and E:30 are treated as equivalent."""
    return {canonical(code) for code in ERROR_CODE_PATTERN.findall(text)}


def query_concept_phrases(query_terms: list[str]) -> list[str]:
    """Map common user wording to short phrases used in the manuals."""
    terms = set(query_terms)
    phrases: list[str] = []
    if "first" in terms and ("time" in terms or "use" in terms or "using" in terms):
        phrases.append("first use")
    return phrases


def load_manifest(path: Path) -> list[dict[str, str]]:
    """Load the supported brand/model catalogue."""
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def resolve_manual(
    manifest: list[dict[str, str]], brand: str, model: str
) -> dict[str, str]:
    """Return one supported manual or raise a user-facing validation error."""
    if not brand.strip() or not model.strip():
        raise RetrievalInputError(
            "Please provide both the washing-machine brand and exact model."
        )

    requested_brand = canonical(brand)
    requested_model = canonical(model)
    for row in manifest:
        if (
            canonical(row["brand"]) == requested_brand
            and canonical(row["model"]) == requested_model
        ):
            return row

    supported = ", ".join(f"{row['brand']} {row['model']}" for row in manifest)
    raise RetrievalInputError(
        f"Unsupported brand/model: {brand} {model}. Supported models: {supported}."
    )


def load_model_chunks(
    path: Path, manual: dict[str, str]
) -> list[dict[str, Any]]:
    """Load only chunks belonging to the already validated manual."""
    selected: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            chunk = json.loads(line)
            if (
                canonical(chunk["brand"]) == canonical(manual["brand"])
                and canonical(chunk["model"]) == canonical(manual["model"])
            ):
                selected.append(chunk)

    if not selected:
        raise RetrievalInputError(
            "No indexed passages were found for this supported model. Run "
            "`python src/ingest.py` before retrieval."
        )
    return selected


def bm25_scores(query: str, chunks: list[dict[str, Any]]) -> list[float]:
    """Calculate BM25 scores, with a small exact error-code bonus."""
    expanded_query = expand_query(query)
    query_terms = tokenize(expanded_query)
    if not query_terms:
        raise RetrievalInputError("Please enter a question containing searchable words.")

    tokenized_documents = [tokenize(chunk["text"]) for chunk in chunks]
    document_frequencies: Counter[str] = Counter()
    for tokens in tokenized_documents:
        document_frequencies.update(set(tokens))

    document_count = len(tokenized_documents)
    average_length = sum(map(len, tokenized_documents)) / document_count
    query_counts = Counter(query_terms)
    query_codes = extract_error_codes(query)
    concept_phrases = query_concept_phrases(tokenize(query))
    k1 = 1.5
    b = 0.75

    scores: list[float] = []
    for chunk, tokens in zip(chunks, tokenized_documents, strict=True):
        term_counts = Counter(tokens)
        document_length = len(tokens)
        score = 0.0

        for term, query_frequency in query_counts.items():
            term_frequency = term_counts.get(term, 0)
            if not term_frequency:
                continue
            document_frequency = document_frequencies[term]
            inverse_document_frequency = math.log(
                1 + (document_count - document_frequency + 0.5)
                / (document_frequency + 0.5)
            )
            length_adjustment = k1 * (
                1 - b + b * document_length / max(average_length, 1)
            )
            score += (
                inverse_document_frequency
                * (term_frequency * (k1 + 1))
                / (term_frequency + length_adjustment)
                * query_frequency
            )

        matching_codes = query_codes & extract_error_codes(chunk["text"])
        score += 4.0 * len(matching_codes)
        normalized_document = " ".join(tokens)
        for phrase in concept_phrases:
            score += 2.0 * normalized_document.count(phrase)
        scores.append(score)

    return scores


def retrieve(
    *,
    brand: str,
    model: str,
    question: str,
    top_k: int = 3,
    manifest_path: Path = DEFAULT_MANIFEST,
    chunks_path: Path = DEFAULT_CHUNKS,
) -> list[dict[str, Any]]:
    """Validate the model, rank its chunks, and return the best passages."""
    if top_k < 1:
        raise RetrievalInputError("top_k must be at least 1.")

    manual = resolve_manual(load_manifest(manifest_path), brand, model)
    chunks = load_model_chunks(chunks_path, manual)
    scores = bm25_scores(question, chunks)
    ranked = sorted(
        zip(chunks, scores, strict=True),
        key=lambda item: (-item[1], item[0]["page"], item[0]["chunk_id"]),
    )

    results: list[dict[str, Any]] = []
    for rank, (chunk, score) in enumerate(ranked[:top_k], start=1):
        results.append(
            {
                "rank": rank,
                "score": round(score, 4),
                "chunk_id": chunk["chunk_id"],
                "brand": chunk["brand"],
                "model": chunk["model"],
                "page": chunk["page"],
                "source_file": chunk["source_file"],
                "source_url": chunk["source_url"],
                "extraction_method": chunk["extraction_method"],
                "text": chunk["text"],
            }
        )
    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Retrieve passages from one supported washing-machine manual."
    )
    parser.add_argument("--brand", required=True, help="Washing-machine brand")
    parser.add_argument("--model", required=True, help="Exact model number")
    parser.add_argument("--question", required=True, help="User question")
    parser.add_argument("--top-k", type=int, default=3, help="Number of passages")
    parser.add_argument(
        "--json", action="store_true", help="Print machine-readable JSON"
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        results = retrieve(
            brand=args.brand,
            model=args.model,
            question=args.question,
            top_k=args.top_k,
        )
    except (RetrievalInputError, FileNotFoundError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return 0

    for result in results:
        print(
            f"[{result['rank']}] {result['brand']} {result['model']} | "
            f"page {result['page']} | score {result['score']:.4f} | "
            f"{result['chunk_id']}"
        )
        print(result["text"])
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
