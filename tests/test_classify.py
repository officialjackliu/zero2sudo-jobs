"""Tests for classify.py job-only filtering.

Run from the repo root:
    python3 -m unittest discover -s tests -v
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import classify  # noqa: E402

# Fixture: the real Shield story from Nov 8, 2026 (from the user's screenshot).
SHIELD_STORY = """Shield
Engineer II,
Software - Ground Control Station -
Full Stack - New
Grad - 6140
Washington, D.C.
Hivemind Solutions Division - Flight
System Integration /
Full Time Employee / On-Site
JOBS.LEVER.CO"""

POLL_STORY = """Which company pays new grads the best?
Google
Meta
Amazon
Tap to vote - Poll ends in 12h"""

QA_STORY = """Q&A — Ask me anything about SWE recruiting!
Drop your questions below and I'll answer them tonight."""

ADVICE_STORY = """How to pass the Amazon OA: 5 tips I wish I knew
1. Practice timed rounds
2. Read the question twice
3. Don't panic on the hard one"""

SUCCESS_STORY = """From 0 offers to 3 offers in one month!
Congrats to Rahul — he just signed with a top fintech.
Here's how he did it."""

INSIDER_STORY = """Insider Info: what is a staff engineer, really?
A deep dive into levels, scope, and what changes at each rung.
Everything you need to know."""


class TestClassifierAcceptsJobs(unittest.TestCase):
    def test_shield_story_is_a_job(self):
        is_job, reason = classify.is_job_post(SHIELD_STORY)
        self.assertTrue(is_job, reason)
        self.assertIn("apply link", reason)

    def test_role_hiring_location_without_link(self):
        text = (
            "Acme Corp is hiring!\n"
            "Software Engineer Intern - Summer 2027\n"
            "New York, NY — Apply now, link in bio"
        )
        is_job, reason = classify.is_job_post(text)
        self.assertTrue(is_job, reason)

    def test_new_grad_role_with_greenhouse_link(self):
        text = (
            "Notion\nSoftware Engineering Intern - Frontend - Summer 2027\n"
            "New York City, NY\nhttps://boards.greenhouse.io/notion/jobs/123"
        )
        is_job, reason = classify.is_job_post(text)
        self.assertTrue(is_job, reason)


class TestClassifierRejectsNonJobs(unittest.TestCase):
    def test_poll_rejected(self):
        is_job, reason = classify.is_job_post(POLL_STORY)
        self.assertFalse(is_job)
        self.assertIn("poll", reason)

    def test_qa_rejected(self):
        is_job, reason = classify.is_job_post(QA_STORY)
        self.assertFalse(is_job)
        self.assertIn("q&a", reason)

    def test_advice_rejected(self):
        is_job, reason = classify.is_job_post(ADVICE_STORY)
        self.assertFalse(is_job)
        self.assertIn("advice", reason)

    def test_success_story_rejected(self):
        is_job, reason = classify.is_job_post(SUCCESS_STORY)
        self.assertFalse(is_job)
        self.assertIn("success story", reason)

    def test_insider_info_rejected(self):
        is_job, reason = classify.is_job_post(INSIDER_STORY)
        self.assertFalse(is_job)
        self.assertIn("insider-info", reason)

    def test_vague_text_rejected(self):
        is_job, reason = classify.is_job_post("Big week ahead. Stay tuned.")
        self.assertFalse(is_job)
        self.assertIn("not enough job signals", reason)

    def test_empty_text_rejected(self):
        is_job, _ = classify.is_job_post("")
        self.assertFalse(is_job)


if __name__ == "__main__":
    unittest.main()
