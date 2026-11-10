"""Tests for extract.py parsing (best-effort, never invents fields).

Run from the repo root:
    python3 -m unittest discover -s tests -v
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import extract  # noqa: E402

SHIELD_TEXT = """Shield
Engineer II,
Software - Ground Control Station -
Full Stack - New
Grad - 6140
Washington, D.C.
Hivemind Solutions Division - Flight
System Integration /
Full Time Employee / On-Site
JOBS.LEVER.CO"""


class TestParseJobText(unittest.TestCase):
    def test_shield_text_parses(self):
        job = extract.parse_job_text(SHIELD_TEXT)
        self.assertIsNotNone(job)
        assert job is not None
        self.assertEqual(job["company"], "Shield")
        self.assertIn("Ground Control Station", job["position"])
        self.assertEqual(job["location"], "Washington, D.C.")
        self.assertIn("lever.co", job["apply_url"])
        self.assertEqual(job["type"], "new_grad")

    def test_incomplete_text_returns_none(self):
        # No location and no clean company line -> do not guess.
        self.assertIsNone(extract.parse_job_text("Software Engineer\nApply now!"))
        self.assertIsNone(extract.parse_job_text(""))
        self.assertIsNone(extract.parse_job_text("Just a photo of a sunset."))


class TestOcrFallback(unittest.TestCase):
    def test_missing_ocr_stack_reports_unavailable(self):
        text, method = extract.ocr_image("/nonexistent.png")
        # Either tesseract is missing (unavailable) or the file is bad;
        # in both cases the result must be empty, never invented text.
        self.assertEqual(text, "")
        self.assertEqual(method, "unavailable")


if __name__ == "__main__":
    unittest.main()
