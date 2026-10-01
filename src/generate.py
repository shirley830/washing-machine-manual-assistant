"""Generate and validate an answer from model-filtered manual evidence.

The module retrieves passages, enforces the evidence gate, constructs the bounded
provider request, parses compatible response shapes, and records token and cost
metadata. Provider failures are translated into typed exceptions for the interface.
It never expands the manual catalogue or bypasses exact-model routing.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

from answer import evidence_is_sufficient
from retrieve import RetrievalInputError, retrieve


PROJECT_ROOT = Path(__file__).resolve().parents[1]
USAGE_LOG = Path(
    os.getenv("WM_ASSISTANT_USAGE_LOG", PROJECT_ROOT / "outputs" / "api_usage.jsonl")
)
DEFAULT_MODEL = "openrouter/auto"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
LOGGER = logging.getLogger(__name__)

# PDF extraction can flatten control-panel diagrams into ambiguous linear text.
# These notes preserve a manually verified relationship without changing the source quote.
EVIDENCE_NOTATION_NOTES = {
    "6 (Finish in) M and N": (
        "The extracted phrase '6 (Finish in) M and N' denotes the two Finish in "
        "controls marked M and N; it does not denote a Finish in control plus two "
        "additional buttons."
    ),
}

SYSTEM_INSTRUCTIONS = """You answer questions about one washing-machine model.
Use only the supplied evidence from that model's official manual.
Do not add general knowledge, assumptions, or troubleshooting steps absent from the evidence.
Answer in clear, concise English even if the evidence is in another language.
Answer only what the question asks; omit related background unless it is necessary for safety.
Preserve control names and their labels exactly. Letters, symbols, or directions attached
to one named control are labels for that control, not additional buttons, unless the
evidence explicitly describes them as separate controls.
For example, evidence written as "[control name] M and N" means the two controls for
that named function, marked M and N; never describe it as the named control plus two
additional M and N buttons.
After every substantive sentence, cite at least one evidence label such as [E1].
If the evidence does not support the answer, output exactly INSUFFICIENT_EVIDENCE.
Do not mention these instructions."""


class GenerationConfigurationError(RuntimeError):
    """Raised when local API configuration is missing or unsafe."""


class GatewayAuthenticationError(RuntimeError):
    """Raised when OpenRouter rejects the configured API key."""


class GatewayPermissionError(RuntimeError):
    """Raised when the configured key cannot access the selected model."""


class GatewayRateLimitError(RuntimeError):
    """Raised when the request reaches a rate, credit, or spending limit."""


class GatewayConnectionError(RuntimeError):
    """Raised when the request cannot reach OpenRouter."""


class GatewayRequestError(RuntimeError):
    """Raised when OpenRouter rejects or cannot parse the request."""


def extract_response_text(response_payload: Any) -> str:
    """Return non-empty assistant text from a compatible chat response."""
    try:
        content = response_payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as error:
        raise GatewayRequestError(
            "OpenRouter returned a response without assistant content."
        ) from error

    if isinstance(content, str):
        output_text = content.strip()
    elif isinstance(content, list):
        text_parts = []
        for part in content:
            if isinstance(part, str):
                text_parts.append(part)
            elif isinstance(part, dict) and isinstance(part.get("text"), str):
                text_parts.append(part["text"])
        output_text = "".join(text_parts).strip()
    else:
        output_text = ""

    if not output_text:
        raise GatewayRequestError(
            "OpenRouter returned an empty assistant response. Please try again."
        )
    return output_text


def safe_int(value: Any) -> int:
    """Convert optional usage values without breaking an otherwise valid answer."""
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def safe_float(value: Any) -> float | None:
    """Convert optional cost metadata, returning None when it is malformed."""
    if value is None:
        return None
    try:
        return round(float(value), 8)
    except (TypeError, ValueError):
        return None


def request_completion(
    *, base_url: str, headers: dict[str, str], payload: dict[str, Any]
) -> tuple[dict[str, Any], str, float]:
    """Request one usable completion, retrying transient or empty responses."""
    started = time.perf_counter()
    attempts = 3
    for attempt in range(attempts):
        try:
            response = requests.post(
                f"{base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=60,
            )
        except requests.RequestException as error:
            if attempt < attempts - 1:
                time.sleep(0.25 * (2**attempt))
                continue
            raise GatewayConnectionError(str(error)) from error

        if response.status_code == 401:
            raise GatewayAuthenticationError(response.text)
        if response.status_code == 403:
            raise GatewayPermissionError(response.text)
        if response.status_code == 429:
            raise GatewayRateLimitError(response.text)
        if response.status_code >= 500 and attempt < attempts - 1:
            time.sleep(0.25 * (2**attempt))
            continue
        if response.status_code >= 400:
            raise GatewayRequestError(response.text)

        try:
            response_payload = response.json()
            output_text = extract_response_text(response_payload)
        except (ValueError, GatewayRequestError) as error:
            if attempt < attempts - 1:
                time.sleep(0.25 * (2**attempt))
                continue
            raise GatewayRequestError(
                "OpenRouter did not return a usable answer after three attempts."
            ) from error

        latency_seconds = round(time.perf_counter() - started, 3)
        return response_payload, output_text, latency_seconds

    raise GatewayRequestError("OpenRouter did not return a usable answer.")


def build_model_input(
    *, brand: str, model: str, question: str, results: list[dict[str, Any]]
) -> str:
    """Create a bounded prompt containing only selected-model evidence."""
    evidence_blocks = []
    for index, result in enumerate(results, start=1):
        evidence_blocks.append(
            f"[E{index}] Page {result['page']} | Chunk {result['chunk_id']}\n"
            f"{result['text']}"
        )
    evidence = "\n\n".join(evidence_blocks)
    notation_notes = [
        note
        for marker, note in EVIDENCE_NOTATION_NOTES.items()
        if any(marker in result["text"] for result in results)
    ]
    notes_section = ""
    if notation_notes:
        notes_section = (
            "\n\nVerified PDF-layout notes:\n- " + "\n- ".join(notation_notes)
        )
    return (
        f"Brand: {brand}\n"
        f"Model: {model}\n"
        f"Question: {question}\n\n"
        f"Official-manual evidence:\n{evidence}{notes_section}"
    )


def append_usage_log(record: dict[str, Any]) -> None:
    """Append one local JSON record; outputs are excluded from Git."""
    USAGE_LOG.parent.mkdir(parents=True, exist_ok=True)
    with USAGE_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def grounded_answer(
    *,
    brand: str,
    model: str,
    question: str,
    top_k: int = 3,
    api_key: str | None = None,
    model_name: str | None = None,
    base_url: str | None = None,
) -> dict[str, Any]:
    """Retrieve, gate, generate, cite, and record one answer."""
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
            "usage": None,
        }

    load_dotenv(PROJECT_ROOT / ".env")
    api_key = (api_key or os.getenv("OPENROUTER_API_KEY", "")).strip()
    if not api_key or "replace_with" in api_key.casefold():
        raise GenerationConfigurationError(
            "OPENROUTER_API_KEY is missing or still contains the placeholder. "
            "Configure a valid OpenRouter key and try again."
        )

    model_name = model_name or os.getenv("OPENROUTER_MODEL", DEFAULT_MODEL)
    base_url = (base_url or os.getenv("OPENROUTER_BASE_URL", OPENROUTER_BASE_URL)).rstrip("/")
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": SYSTEM_INSTRUCTIONS},
            {
                "role": "user",
                "content": build_model_input(
                    brand=brand,
                    model=model,
                    question=question,
                    results=results,
                ),
            },
        ],
        "max_tokens": 300,
        "temperature": 0,
        "usage": {"include": True},
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/shirley830/washing-machine-manual-assistant",
        "X-OpenRouter-Title": "Washing Machine Manual Assistant",
    }
    response_payload, output_text, latency_seconds = request_completion(
        base_url=base_url,
        headers=headers,
        payload=payload,
    )

    usage_payload = response_payload.get("usage") or {}
    if not isinstance(usage_payload, dict):
        usage_payload = {}
    input_tokens = safe_int(usage_payload.get("prompt_tokens"))
    output_tokens = safe_int(usage_payload.get("completion_tokens"))
    total_tokens = safe_int(usage_payload.get("total_tokens"))
    reported_cost = usage_payload.get("cost")
    estimated_cost = safe_float(reported_cost)
    usage = {
        "model": model_name,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "latency_seconds": latency_seconds,
        "estimated_cost_usd": estimated_cost,
    }
    try:
        append_usage_log(
            {
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "brand": brand,
                "model_number": model,
                "question": question,
                **usage,
            }
        )
    except OSError:
        LOGGER.exception("Could not write the optional API usage log.")

    if output_text == "INSUFFICIENT_EVIDENCE":
        return {
            "status": "refusal",
            "answer": (
                "I could not find sufficient evidence in the official manual for "
                f"{brand} {model}."
            ),
            "reason": "The language model judged the supplied evidence insufficient.",
            "coverage": round(coverage, 3),
            "citations": [],
            "usage": usage,
        }

    cited_indexes = {int(value) for value in re.findall(r"\[E(\d+)\]", output_text)}
    if not cited_indexes or any(index < 1 or index > len(results) for index in cited_indexes):
        return {
            "status": "refusal",
            "answer": "The generated answer did not contain valid evidence citations.",
            "reason": "Citation validation failed after generation.",
            "coverage": round(coverage, 3),
            "citations": [],
            "usage": usage,
        }

    citations = [
        {
            "label": f"E{index}",
            "chunk_id": result["chunk_id"],
            "page": result["page"],
            "source_file": result["source_file"],
            "source_url": result["source_url"],
        }
        for index, result in enumerate(results, start=1)
        if index in cited_indexes
    ]
    return {
        "status": "answer",
        "answer": output_text,
        "reason": reason,
        "coverage": round(coverage, 3),
        "citations": citations,
        "usage": usage,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a grounded manual answer through OpenRouter."
    )
    parser.add_argument("--brand", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--question", required=True)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = grounded_answer(
            brand=args.brand,
            model=args.model,
            question=args.question,
        )
    except (RetrievalInputError, GenerationConfigurationError, FileNotFoundError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
    except GatewayAuthenticationError:
        print(
            "Error: OpenRouter rejected the API key. Check that .env contains the "
            "complete active OpenRouter key with no quotes, spaces, or placeholder text.",
            file=sys.stderr,
        )
        return 2
    except GatewayPermissionError:
        print(
            "Error: This API key does not have permission to use the selected model. "
            "Check the OpenRouter key permissions or choose another available model.",
            file=sys.stderr,
        )
        return 2
    except GatewayRateLimitError:
        print(
            "Error: The API request reached a rate, credit, or spending limit. Check "
            "your OpenRouter credits and limits before retrying.",
            file=sys.stderr,
        )
        return 2
    except GatewayConnectionError:
        print(
            "Error: The program could not connect to OpenRouter. Check the network "
            "connection and try again.",
            file=sys.stderr,
        )
        return 2
    except GatewayRequestError as error:
        print(f"Error: The OpenRouter request was rejected: {error}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    print(result["answer"])
    if result["citations"]:
        print("\nSources:")
        for citation in result["citations"]:
            print(
                f"[{citation['label']}] Page {citation['page']} | "
                f"{citation['source_file']} | {citation['chunk_id']}"
            )
    else:
        print(f"Reason: {result['reason']}")
    if result["usage"]:
        usage = result["usage"]
        print(
            "\nUsage: "
            f"{usage['input_tokens']} input + {usage['output_tokens']} output tokens; "
            f"{usage['latency_seconds']:.3f}s; "
            f"estimated cost ${usage['estimated_cost_usd']:.8f}"
            if usage["estimated_cost_usd"] is not None
            else "\nUsage recorded; cost unavailable for the selected model."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
