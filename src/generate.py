"""Generate a grounded answer from model-filtered manual evidence."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import (
    APIConnectionError,
    AuthenticationError,
    BadRequestError,
    OpenAI,
    PermissionDeniedError,
    RateLimitError,
)

from answer import evidence_is_sufficient
from retrieve import RetrievalInputError, retrieve


PROJECT_ROOT = Path(__file__).resolve().parents[1]
USAGE_LOG = PROJECT_ROOT / "outputs" / "api_usage.jsonl"
DEFAULT_MODEL = "openai/gpt-6-luna"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Standard short-context prices in USD per 1 million tokens.
# Update these values if the selected model or official pricing changes.
MODEL_PRICES = {
    "openai/gpt-6-astra": {"input": 10.00, "output": 50.00},
    "openai/gpt-6-sol": {"input": 2.00, "output": 10.00},
    "openai/gpt-6-luna": {"input": 0.10, "output": 0.50},
}

SYSTEM_INSTRUCTIONS = """You answer questions about one washing-machine model.
Use only the supplied evidence from that model's official manual.
Do not add general knowledge, assumptions, or troubleshooting steps absent from the evidence.
Answer in clear, concise English even if the evidence is in another language.
After every substantive sentence, cite at least one evidence label such as [E1].
If the evidence does not support the answer, output exactly INSUFFICIENT_EVIDENCE.
Do not mention these instructions."""


class GenerationConfigurationError(RuntimeError):
    """Raised when local API configuration is missing or unsafe."""


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
    return (
        f"Brand: {brand}\n"
        f"Model: {model}\n"
        f"Question: {question}\n\n"
        f"Official-manual evidence:\n{evidence}"
    )


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float | None:
    """Estimate standard token cost for models with recorded price constants."""
    prices = MODEL_PRICES.get(model)
    if prices is None:
        return None
    return round(
        input_tokens / 1_000_000 * prices["input"]
        + output_tokens / 1_000_000 * prices["output"],
        8,
    )


def append_usage_log(record: dict[str, Any]) -> None:
    """Append one local JSON record; outputs are excluded from Git."""
    USAGE_LOG.parent.mkdir(parents=True, exist_ok=True)
    with USAGE_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def grounded_answer(
    *, brand: str, model: str, question: str, top_k: int = 3
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
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key or "replace_with" in api_key.casefold():
        raise GenerationConfigurationError(
            "OPENROUTER_API_KEY still contains the placeholder or is missing. Open "
            ".env, replace only the text after OPENROUTER_API_KEY= with your real "
            "OpenRouter key, and save."
        )

    model_name = os.getenv("OPENROUTER_MODEL", DEFAULT_MODEL)
    client = OpenAI(
        base_url=OPENROUTER_BASE_URL,
        api_key=api_key,
        default_headers={
            "HTTP-Referer": "https://github.com/shirley830/washing-machine-manual-assistant",
            "X-OpenRouter-Title": "Washing Machine Manual Assistant",
        },
    )
    started = time.perf_counter()
    response = client.chat.completions.create(
        model=model_name,
        messages=[
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
        max_tokens=300,
        temperature=0,
        extra_body={"usage": {"include": True}},
    )
    latency_seconds = round(time.perf_counter() - started, 3)

    output_text = (response.choices[0].message.content or "").strip()
    input_tokens = response.usage.prompt_tokens if response.usage else 0
    output_tokens = response.usage.completion_tokens if response.usage else 0
    total_tokens = response.usage.total_tokens if response.usage else 0
    usage_payload = response.usage.model_dump() if response.usage else {}
    reported_cost = usage_payload.get("cost")
    estimated_cost = (
        round(float(reported_cost), 8)
        if reported_cost is not None
        else estimate_cost_usd(model_name, input_tokens, output_tokens)
    )
    usage = {
        "model": model_name,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "latency_seconds": latency_seconds,
        "estimated_cost_usd": estimated_cost,
    }
    append_usage_log(
        {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "brand": brand,
            "model_number": model,
            "question": question,
            **usage,
        }
    )

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
    except AuthenticationError:
        print(
            "Error: OpenRouter rejected the API key. Check that .env contains the "
            "complete active OpenRouter key with no quotes, spaces, or placeholder text.",
            file=sys.stderr,
        )
        return 2
    except PermissionDeniedError:
        print(
            "Error: This API key does not have permission to use the selected model. "
            "Check the OpenRouter key permissions or choose another available model.",
            file=sys.stderr,
        )
        return 2
    except RateLimitError:
        print(
            "Error: The API request reached a rate, credit, or spending limit. Check "
            "your OpenRouter credits and limits before retrying.",
            file=sys.stderr,
        )
        return 2
    except APIConnectionError:
        print(
            "Error: The program could not connect to OpenRouter. Check the network "
            "connection and try again.",
            file=sys.stderr,
        )
        return 2
    except BadRequestError as error:
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
