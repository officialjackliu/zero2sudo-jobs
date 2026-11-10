#!/usr/bin/env python3
"""Regenerate the job tables in README.md from jobs.json.

Usage:
    python3 scripts/update_readme.py

Reads jobs.json (the source of truth) and rewrites only the regions of
README.md delimited by the JOBS markers:

    <!-- JOBS:INTERNSHIPS --> ... <!-- /JOBS:INTERNSHIPS -->
    <!-- JOBS:NEW_GRAD -->    ... <!-- /JOBS:NEW_GRAD -->

Everything outside those regions is left untouched, so the script is safe
to run repeatedly (idempotent) and by GitHub Actions.

Table columns (mirroring the speedyapply/2027-SWE-College-Jobs style):
    Company | Position | Location | Posting | Age

"Age" is computed from each job's date_seen (days since it was first
spotted). Jobs are sorted newest first within each section.
"""

import json
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
JOBS_PATH = ROOT / "jobs.json"
README_PATH = ROOT / "README.md"

SECTIONS = (
    ("INTERNSHIPS", "internship"),
    ("NEW_GRAD", "new_grad"),
)


def age_label(date_seen: str, today) -> str:
    """Days since date_seen, rendered like '0d', '1d', '12d'."""
    seen = datetime.fromisoformat(date_seen).date()
    days = max((today - seen).days, 0)
    return f"{days}d"


def apply_cell(job: dict) -> str:
    """Render the Posting cell.

    If apply_url is a full job posting URL, render an "Apply" link.
    If it is only a domain (exact posting URL unknown), link the domain
    itself so the table never pretends to know a URL it does not.
    """
    url = (job.get("apply_url") or "").strip()
    if not url:
        return "-"
    # A bare domain has no path beyond the host (e.g. https://jobs.lever.co).
    path = url.split("://", 1)[-1].split("/", 1)
    if len(path) == 1 or not path[1].strip("/"):
        domain = path[0]
        return f"[{domain}]({url})"
    return f"[Apply]({url})"


def escape(text: str) -> str:
    """Escape characters that would break a Markdown table cell."""
    return str(text).replace("|", "\\|").replace("\n", " ")


def build_table(jobs: list[dict], today) -> str:
    """Build the Markdown table for one section's jobs."""
    lines = [
        "| Company | Position | Location | Posting | Age |",
        "|---|---|---|---|---|",
    ]
    for job in sorted(jobs, key=lambda j: j.get("date_seen", ""), reverse=True):
        salary = job.get("salary")
        position = job["position"]
        if salary:
            position = f"{position} ({salary})"
        lines.append(
            "| **{company}** | {position} | {location} | {posting} | {age} |".format(
                company=escape(job["company"]),
                position=escape(position),
                location=escape(job["location"]),
                posting=apply_cell(job),
                age=age_label(job["date_seen"], today),
            )
        )
    if not jobs:
        lines.append("| *No jobs yet — check back soon.* | | | | |")
    return "\n".join(lines)


def replace_region(text: str, marker: str, new_body: str) -> str:
    """Replace the content between <!-- MARKER --> and <!-- /MARKER -->."""
    pattern = re.compile(
        r"(<!-- " + re.escape(marker) + r" -->)\n.*?\n(<!-- /" + re.escape(marker) + r" -->)",
        re.DOTALL,
    )
    replacement = r"\1\n" + new_body + "\n" + r"\2"
    new_text, count = pattern.subn(replacement, text)
    if count != 1:
        raise SystemExit(f"ERROR: expected exactly one {marker} region in README.md, found {count}")
    return new_text


def main() -> None:
    with JOBS_PATH.open(encoding="utf-8") as f:
        jobs = json.load(f)

    with README_PATH.open(encoding="utf-8") as f:
        readme = f.read()

    today = datetime.now(ZoneInfo("America/Chicago")).date()

    for marker, job_type in SECTIONS:
        section_jobs = [j for j in jobs if j.get("type") == job_type]
        readme = replace_region(readme, f"JOBS:{marker}", build_table(section_jobs, today))

    # Update the "last updated" line, if the marker exists.
    # Use a lambda replacement: a plain "\1" + date string would be
    # misparsed (e.g. "\12026..." reads as backreference 12).
    last_updated_pattern = re.compile(
        r"(<!-- LAST_UPDATED -->).*?(<!-- /LAST_UPDATED -->)", re.DOTALL
    )
    readme, count = last_updated_pattern.subn(
        lambda m: m.group(1) + today.isoformat() + m.group(2), readme
    )
    if count != 1:
        raise SystemExit("ERROR: expected exactly one LAST_UPDATED region in README.md")

    with README_PATH.open("w", encoding="utf-8") as f:
        f.write(readme)

    counts = {t: sum(1 for j in jobs if j.get("type") == t) for _, t in SECTIONS}
    print(f"README.md updated: {counts['internship']} internship(s), "
          f"{counts['new_grad']} new-grad role(s).")


if __name__ == "__main__":
    main()
