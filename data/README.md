# Data Guide

This directory contains the source catalogue and the processed retrieval data used by the application. It is designed so that a fresh repository clone can answer questions without downloading the original manuals or rebuilding the index.

## Supported manuals

| Brand | Exact model | Official source |
| --- | --- | --- |
| Gaggenau | WM260162CN | Gaggenau product manual |
| Gaggenau | WM260164 | Gaggenau product manual |
| Gaggenau | WM262700-26 | Gaggenau product manual |
| SMEG | WM24UWH | SMEG product manual |
| Zanussi | ZWG1120M | Electrolux/Zanussi product manual |

The exact filenames and official URLs are recorded in [`manuals_manifest.csv`](manuals_manifest.csv). Brand and model values in that file are the canonical routing values used by ingestion, retrieval, evaluation, and the interface.

## Files

| File | Purpose | Version-control policy |
| --- | --- | --- |
| `manuals_manifest.csv` | Canonical brand, model, local filename, and official source URL for every supported manual. | Committed |
| `chunks.jsonl` | Prebuilt, page-labelled passage index used at runtime. | Committed |
| `manual_supplements.csv` | Documented text supplements for relevant passages that the PDF extractor does not recover reliably. | Committed |
| `manuals/*.pdf` | Local copies of source manuals used only when rebuilding the index. | Not committed |

The original PDF manuals are not runtime dependencies and are intentionally excluded from Git. This avoids republishing manufacturer documents while preserving provenance through the manifest. Reviewers can inspect the official source URLs and can run the application directly from the committed passage index.

## Passage-index schema

Each line of `chunks.jsonl` is one JSON object. The important fields are:

| Field | Meaning |
| --- | --- |
| `chunk_id` | Stable identifier combining the model, page, and passage number. |
| `brand` and `model` | Exact routing metadata applied before ranking. |
| `source_file` and `source_url` | Manual provenance. |
| `page` | Page shown to the user in the evidence citation. |
| `text` | Normalised passage searched by the local retriever. |

The supplement file follows the same provenance principle. Every supplement names the affected brand, model, page, text, and reason. It is not a replacement answer: it restores manual text that is visible in the source document but unreliable in automated extraction.

## Rebuilding the index

1. Place the five manifest-listed PDFs in `data/manuals/` using the exact filenames in `manuals_manifest.csv`.
2. Activate the project environment and install `requirements.txt`.
3. Run `python src/ingest.py` from the repository root.
4. Re-run retrieval, formal evaluation, and regression tests before committing the new index.

The command replaces `chunks.jsonl`. A rebuilt index should not be accepted merely because ingestion completes: page labels, exact-model routing, evaluation results, and source citations must still pass.

## Model-isolation guardrail

The catalogue deliberately includes a conflicting error-code pair. `E30` for Zanussi ZWG1120M concerns the door, while `E:30 / -80` for Gaggenau WM260164 concerns drainage. These passages verify that model filtering happens before ranking and that content from another manual cannot enter the answer context. The matching cases are documented in [`../evaluation/formal_evaluation_50.csv`](../evaluation/formal_evaluation_50.csv).

