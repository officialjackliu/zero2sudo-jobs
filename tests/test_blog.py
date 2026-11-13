"""Tests for public Direct Consideration HTML extraction."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import blog  # noqa: E402


HTML = """
<h2>Notion Frontend and iOS SWE Internships</h2>
<p>Cohort: Internship</p>
<p>Notion posted roles in New York.</p>
<a href="https://jobs.example/notion-frontend?utm_source=zero2sudo">Apply to Notion, Frontend →</a>
<h2>Shield AI New Grad Software Roles</h2>
<p>Cohort: New Grad</p>
<p>Shield AI posted roles in Washington, D.C.</p>
<a href="https://jobs.example/shield-ii">Apply to Shield AI, Engineer II →</a>
"""


class TestBlogParser(unittest.TestCase):
    def test_extracts_exact_application_links_and_types(self):
        jobs = blog.parse_post(HTML, "https://directconsideration.com/p/test")
        self.assertEqual(len(jobs), 2)
        self.assertEqual(jobs[0]["company"], "Notion")
        self.assertEqual(jobs[0]["position"], "Frontend")
        self.assertEqual(jobs[0]["location"], "New York")
        self.assertEqual(jobs[0]["type"], "internship")
        self.assertEqual(jobs[0]["notes"], "Notion posted roles in New York.")
        self.assertEqual(
            jobs[0]["apply_url"],
            "https://jobs.example/notion-frontend?utm_source=zero2sudo",
        )
        self.assertEqual(jobs[1]["company"], "Shield AI")
        self.assertEqual(jobs[1]["type"], "new_grad")

    def test_ignores_blocks_without_a_location(self):
        html = """
        <h2>Unknown Role</h2>
        <p>Apply anywhere.</p>
        <a href="https://jobs.example/unknown">Apply →</a>
        """
        self.assertEqual(blog.parse_post(html, "https://example.com/post"), [])

    def test_discovers_unique_post_urls(self):
        html = """
        <a href="/p/direct-consideration-027">Latest</a>
        <a href="https://directconsideration.com/p/direct-consideration-027">Again</a>
        <a href="/about">About</a>
        """
        self.assertEqual(
            blog.discover_posts(html),
            ["https://directconsideration.com/p/direct-consideration-027"],
        )

    def test_generic_company_link_uses_heading_as_position(self):
        html = """
        <h2>Beli Summer 2027 SWE Internship</h2>
        <p>Cohort: Internship</p>
        <p>Beli has a Software Engineer Intern role for Summer 2027 in New York, NY.</p>
        <a href="https://jobs.example/beli">Apply to Beli →</a>
        """
        job = blog.parse_post(html, "https://example.com/post")[0]
        self.assertEqual(job["company"], "Beli")
        self.assertEqual(job["position"], "Beli Summer 2027 SWE Internship")
        self.assertEqual(job["location"], "New York, NY")
        self.assertIn("Software Engineer Intern", job["notes"])

    def test_does_not_import_event_links_after_daily_drops(self):
        html = """
        <h2>Example Internship</h2>
        <p>Example posted a role in Austin, TX.</p>
        <a href="https://jobs.example/job">Apply to Example →</a>
        <h2>Events Watchlist</h2>
        <a href="https://events.example/event">Register for the event →</a>
        """
        jobs = blog.parse_post(html, "https://example.com/post")
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["company"], "Example")

    def test_grouped_palantir_links_keep_company_and_distinct_roles(self):
        html = """
        <h2>Palantir SWE Internships</h2>
        <p>Palantir posted Software Engineer internships in Denver, CO and New York, NY.</p>
        <a href="https://jobs.example/palantir-denver">Apply to Connectivity Platform and Product (Denver) →</a>
        <a href="https://jobs.example/palantir-ny">Apply to Connectivity Platform and Product (New York) →</a>
        <a href="https://jobs.example/palantir-data">Apply to Data Connectors →</a>
        """
        jobs = blog.parse_post(html, "https://example.com/post")
        self.assertEqual([job["company"] for job in jobs], ["Palantir"] * 3)
        self.assertEqual(
            [job["position"] for job in jobs],
            [
                "Connectivity Platform and Product (Denver)",
                "Connectivity Platform and Product (New York)",
                "Data Connectors",
            ],
        )


if __name__ == "__main__":
    unittest.main()
