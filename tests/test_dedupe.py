"""Tests for jobs.py dedupe logic.

Run from the repo root:
    python3 -m unittest discover -s tests -v
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import jobs  # noqa: E402

SHIELD = {
    "company": "Shield",
    "position": "Engineer II, Software - Ground Control Station - Full Stack - New Grad - 6140",
    "location": "Washington, D.C.",
    "apply_url": "https://jobs.lever.co/shield/6140",
    "type": "new_grad",
    "source": "zero2sudo story",
    "date_seen": "2026-11-08",
    "salary": None,
}


def variant(**overrides):
    job = dict(SHIELD)
    job.update(overrides)
    return job


class TestNormalize(unittest.TestCase):
    def test_case_punctuation_whitespace(self):
        self.assertEqual(
            jobs.normalize_text("  Engineer II,  Software - Ground Control! "),
            "engineer ii software ground control",
        )

    def test_cpp_kept_distinct(self):
        # "+" is meaningful: C++ must not collapse into C.
        self.assertNotEqual(jobs.normalize_text("C++ Engineer"), jobs.normalize_text("C Engineer"))
        self.assertEqual(jobs.normalize_text("C++ Engineer"), "c++ engineer")


class TestDedupeKey(unittest.TestCase):
    def test_same_job_different_casing_punctuation_whitespace(self):
        # The Shield job reposted with different casing/punctuation/spacing.
        repost = variant(
            company="  SHIELD ",
            position="engineer ii software ground control station full stack new grad 6140",
            location="Washington, D.C.",
            apply_url="https://shield.ai/careers/6140",
        )
        existing = [dict(SHIELD)]
        status, reason = jobs.add_job(existing, repost)
        self.assertEqual(status, "duplicate")
        self.assertIn("duplicate of Shield", reason)
        self.assertEqual(len(existing), 1)

    def test_same_company_different_role_is_not_duplicate(self):
        # A different role at the same company is a different job — but
        # only when it is really a different posting: it must also have
        # its own apply URL (the same URL would mean the same posting).
        other_role = variant(
            position="Engineer I, Software - Autonomy - New Grad - 6139",
            apply_url="https://jobs.lever.co/shield/6139",
        )
        existing = [dict(SHIELD)]
        status, _ = jobs.add_job(existing, other_role)
        self.assertEqual(status, "added")
        self.assertEqual(len(existing), 2)

    def test_same_role_different_location_is_not_duplicate(self):
        other_city = variant(
            location="Austin, TX",
            apply_url="https://jobs.lever.co/shield/6140-austin",
        )
        existing = [dict(SHIELD)]
        status, _ = jobs.add_job(existing, other_city)
        self.assertEqual(status, "added")
        self.assertEqual(len(existing), 2)

    def test_identical_apply_url_is_duplicate(self):
        # Same posting URL, even with a (hypothetically) reworded title.
        same_url = variant(
            company="Shield",
            position="Software Engineer II, Ground Control Station",
            location="Washington, D.C.",
            apply_url="https://jobs.lever.co/shield/6140",
        )
        existing = [dict(SHIELD)]
        status, reason = jobs.add_job(existing, same_url)
        self.assertEqual(status, "duplicate")
        self.assertIn("duplicate of", reason)

    def test_bare_domain_url_does_not_dedupe(self):
        # Two different Shield roles sharing only the jobs.lever.co
        # domain must NOT count as duplicates.
        bare = variant(apply_url="https://jobs.lever.co")
        other = variant(
            position="Engineer I, Software - Autonomy - New Grad - 6139",
            apply_url="https://jobs.lever.co",
        )
        existing = [dict(SHIELD, apply_url="https://jobs.lever.co")]
        status, _ = jobs.add_job(existing, other)
        self.assertEqual(status, "added")

    def test_add_new_job_appends(self):
        existing = []
        status, reason = jobs.add_job(existing, dict(SHIELD))
        self.assertEqual(status, "added")
        self.assertEqual(len(existing), 1)
        self.assertEqual(existing[0]["company"], "Shield")
        self.assertIn("Shield", reason)

    def test_missing_required_field_raises(self):
        with self.assertRaises(ValueError):
            jobs.add_job([], variant(company=""))


if __name__ == "__main__":
    unittest.main()
