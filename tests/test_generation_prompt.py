"""Regression checks for grounded-generation prompt construction."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from generate import build_model_input  # noqa: E402
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


if __name__ == "__main__":
    unittest.main()
