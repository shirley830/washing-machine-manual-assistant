"""Regression checks for grounded-generation prompt construction."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from generate import (  # noqa: E402
    GatewayRequestError,
    build_model_input,
    extract_response_text,
)
from retrieve import retrieve  # noqa: E402


class GenerationPromptTests(unittest.TestCase):
    def test_finish_in_pdf_layout_is_disambiguated(self) -> None:
        results = retrieve(
            brand="Gaggenau",
            model="WM262700-26",
            question="How do I deactivate the child lock if the door will not open?",
            top_k=3,
        )
        prompt = build_model_input(
            brand="Gaggenau",
            model="WM262700-26",
            question="How do I deactivate the child lock if the door will not open?",
            results=results,
        )

        self.assertIn("Verified PDF-layout notes", prompt)
        self.assertIn("two Finish in controls marked M and N", prompt)
        self.assertIn("gaggenau_wm262700-26_p050_c01", prompt)

    def test_response_text_is_trimmed(self) -> None:
        payload = {"choices": [{"message": {"content": "  Answer [E1]  "}}]}

        self.assertEqual(extract_response_text(payload), "Answer [E1]")

    def test_segmented_response_text_is_supported(self) -> None:
        payload = {
            "choices": [
                {
                    "message": {
                        "content": [
                            {"type": "text", "text": "Answer "},
                            {"type": "text", "text": "[E1]"},
                        ]
                    }
                }
            ]
        }

        self.assertEqual(extract_response_text(payload), "Answer [E1]")

    def test_empty_response_text_becomes_gateway_error(self) -> None:
        for content in (None, "", "   ", []):
            with self.subTest(content=content):
                payload = {"choices": [{"message": {"content": content}}]}
                with self.assertRaises(GatewayRequestError):
                    extract_response_text(payload)

    def test_missing_response_shape_becomes_gateway_error(self) -> None:
        with self.assertRaises(GatewayRequestError):
            extract_response_text({"choices": []})


if __name__ == "__main__":
    unittest.main()
