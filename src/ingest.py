"""Extract model-labelled text chunks from the washing-machine manuals."""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

from pypdf import PdfReader


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = PROJECT_ROOT / "data" / "manuals_manifest.csv"
DEFAULT_SUPPLEMENTS = PROJECT_ROOT / "data" / "manual_supplements.csv"
DEFAULT_MANUALS_DIR = PROJECT_ROOT / "data" / "manuals"
DEFAULT_OUTPUT = PROJECT_ROOT / "outputs" / "chunks.jsonl"


def normalize_text(text: str) -> str:
    """Remove extraction noise while preserving paragraph boundaries."""
    text = text.replace("\u00ad", "").replace("\u00a0", " ")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]

    paragraphs: list[str] = []
    current: list[str] = []
    for line in lines:
        if line:
            current.append(line)
        elif current:
            paragraphs.append(" ".join(current))
            current = []
    if current:
        paragraphs.append(" ".join(current))

    return "\n\n".join(paragraphs)


def choose_split(text: str, start: int, target_end: int) -> int:
    """Choose a readable split point close to the requested end position."""
    if target_end >= len(text):
        return len(text)

    search_start = max(start + 1, target_end - 250)
    window = text[search_start:target_end]
    candidates = [
        window.rfind("\n\n"),
        window.rfind(". "),
        window.rfind("。"),
        window.rfind(" "),
    ]
    best = max(candidates)
    return search_start + best + 1 if best >= 0 else target_end


def chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Split one page into overlapping character-based chunks."""
    if not text:
        return []
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = choose_split(text, start, min(start + chunk_size, len(text)))
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)

    return chunks


def load_manifest(path: Path) -> list[dict[str, str]]:
    """Load and minimally validate the manual manifest."""
    required = {"brand", "model", "filename", "source_url"}
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Manifest is missing columns: {', '.join(sorted(missing))}")
        rows = list(reader)

    if not rows:
        raise ValueError("Manifest contains no manuals")
    return rows


def ingest_manual(
    record: dict[str, str],
    manuals_dir: Path,
    chunk_size: int,
    overlap: int,
) -> tuple[list[dict[str, object]], int, int]:
    """Extract all chunks and basic page statistics for one manual."""
    pdf_path = manuals_dir / record["filename"]
    if not pdf_path.is_file():
        raise FileNotFoundError(f"Manual not found: {pdf_path}")

    reader = PdfReader(pdf_path)
    chunks: list[dict[str, object]] = []
    empty_pages = 0

    for page_number, page in enumerate(reader.pages, start=1):
        text = normalize_text(page.extract_text() or "")
        if not text:
            empty_pages += 1
            continue

        for page_chunk_number, chunk in enumerate(
            chunk_text(text, chunk_size=chunk_size, overlap=overlap), start=1
        ):
            chunk_id = (
                f"{record['brand']}_{record['model']}_"
                f"p{page_number:03d}_c{page_chunk_number:02d}"
            ).lower().replace(" ", "_")
            chunks.append(
                {
                    "chunk_id": chunk_id,
                    "brand": record["brand"],
                    "model": record["model"],
                    "source_file": record["filename"],
                    "source_url": record["source_url"],
                    "page": page_number,
                    "extraction_method": "pdf_text",
                    "text": chunk,
                }
            )

    return chunks, len(reader.pages), empty_pages


def load_supplement_chunks(
    supplements_path: Path,
    records: list[dict[str, str]],
) -> list[dict[str, object]]:
    """Load visibly verified text that a PDF's text layer cannot represent."""
    if not supplements_path.is_file():
        return []

    record_lookup = {
        (record["brand"], record["model"], record["filename"]): record
        for record in records
    }
    chunks: list[dict[str, object]] = []
    with supplements_path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        for supplement_number, row in enumerate(reader, start=1):
            key = (row["brand"], row["model"], row["filename"])
            if key not in record_lookup:
                raise ValueError(
                    "Supplement does not match a manifest entry: "
                    f"{row['brand']} {row['model']} {row['filename']}"
                )
            record = record_lookup[key]
            page = int(row["page"])
            chunk_id = (
                f"{row['brand']}_{row['model']}_p{page:03d}_"
                f"supplement_{supplement_number:02d}"
            ).lower().replace(" ", "_")
            chunks.append(
                {
                    "chunk_id": chunk_id,
                    "brand": row["brand"],
                    "model": row["model"],
                    "source_file": row["filename"],
                    "source_url": record["source_url"],
                    "page": page,
                    "extraction_method": "manual_transcription",
                    "verification_note": row["verification_note"],
                    "text": normalize_text(row["text"]),
                }
            )
    return chunks


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--supplements", type=Path, default=DEFAULT_SUPPLEMENTS)
    parser.add_argument("--manuals-dir", type=Path, default=DEFAULT_MANUALS_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--chunk-size", type=int, default=1200)
    parser.add_argument("--overlap", type=int, default=200)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    records = load_manifest(args.manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)

    all_chunks: list[dict[str, object]] = []
    for record in records:
        chunks, page_count, empty_pages = ingest_manual(
            record,
            manuals_dir=args.manuals_dir,
            chunk_size=args.chunk_size,
            overlap=args.overlap,
        )
        all_chunks.extend(chunks)
        print(
            f"{record['brand']} {record['model']}: "
            f"{page_count} pages, {len(chunks)} chunks, {empty_pages} empty pages"
        )

    supplement_chunks = load_supplement_chunks(args.supplements, records)
    all_chunks.extend(supplement_chunks)
    if supplement_chunks:
        print(f"Added {len(supplement_chunks)} manually verified supplement chunk(s)")

    with args.output.open("w", encoding="utf-8") as handle:
        for chunk in all_chunks:
            handle.write(json.dumps(chunk, ensure_ascii=False) + "\n")

    print(f"Wrote {len(all_chunks)} chunks to {args.output}")


if __name__ == "__main__":
    main()
