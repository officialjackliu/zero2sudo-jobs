#!/usr/bin/env python3
"""Job model, normalization, and dedupe logic for the zero2sudo job list.

jobs.json is the source of truth. Every job is a plain dict with these fields:

    company    str   e.g. "Shield"
    position   str   e.g. "Engineer II, Software - Ground Control Station - ..."
    location   str   e.g. "Washington, D.C."
    apply_url  str   full posting URL, or a bare domain when that is all the
                     story showed (never a guessed URL)
    type       str   "internship" or "new_grad"
    source     str   e.g. "zero2sudo story"
    date_seen  str   YYYY-MM-DD, first date the role was spotted
    salary     str | None
    notes      str   optional free text

Dedupe rule (the user's hard requirement — no duplicate jobs):
a candidate is a duplicate of an existing job when EITHER

  1. its normalized (company, position, location) matches an existing
     job's, or
  2. its apply_url is a *specific* posting URL (not a bare domain) and
     that URL matches an existing job's apply_url.

Normalization for comparison only (display text is kept verbatim):
lowercase, strip punctuation except "+" and "#" (so "C++" stays distinct
from "C"), collapse whitespace. The full position text is compared —
job-ID suffixes like " - 6140" are NOT stripped, because two postings of
the same role at the same company in the same city with different IDs
are rare, and stripping IDs risks merging genuinely different postings.

Bare-domain apply URLs (e.g. https://jobs.lever.co) are deliberately
excluded from rule 2: many different jobs share one employer's domain,
so a domain match proves nothing.
"""

import json
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_JOBS_PATH = ROOT / "jobs.json"

REQUIRED_FIELDS = ("company", "position", "location", "type")
VALID_TYPES = ("internship", "new_grad")

# Punctuation is stripped for comparison, except "+" and "#" which carry
# meaning in tech role names (C++, C#).
_PUNCT_RE = re.compile(r"[^a-z0-9+#]+")
_WS_RE = re.compile(r"\s+")


def normalize_text(value: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace.

    >>> normalize_text("  Engineer II,  Software - Ground Control! ")
    'engineer ii software ground control'
    >>> normalize_text("C++ Engineer")
    'c++ engineer'
    """
    value = (value or "").lower()
    value = _PUNCT_RE.sub(" ", value)
    return _WS_RE.sub(" ", value).strip()


def dedupe_key(job: dict) -> tuple[str, str, str]:
    """Normalized (company, position, location) — the primary dedupe key."""
    return (
        normalize_text(job.get("company", "")),
        normalize_text(job.get("position", "")),
        normalize_text(job.get("location", "")),
    )


def normalize_url(url: str) -> str:
    """Normalize a URL for comparison: lowercase, drop scheme/www,
    drop query and fragment, drop trailing slash."""
    url = (url or "").strip().lower()
    url = re.sub(r"^https?://", "", url)
    url = re.sub(r"^www\.", "", url)
    url = url.split("?", 1)[0].split("#", 1)[0]
    return url.rstrip("/")


def is_specific_url(url: str) -> bool:
    """True when the URL points at a specific posting, not a bare domain.

    "https://jobs.lever.co/shield/abc" is specific; "https://jobs.lever.co"
    is not (it is just the employer's job board front page).
    """
    normalized = normalize_url(url)
    parts = normalized.split("/", 1)
    return len(parts) == 2 and bool(parts[1].strip())


def load_jobs(path: Path | str = DEFAULT_JOBS_PATH) -> list[dict]:
    """Load jobs.json. Returns [] when the file does not exist yet."""
    path = Path(path)
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        jobs = json.load(f)
    if not isinstance(jobs, list):
        raise ValueError(f"{path} must contain a JSON array of jobs")
    return jobs


def save_jobs(jobs: list[dict], path: Path | str = DEFAULT_JOBS_PATH) -> None:
    """Write jobs.json (pretty-printed, trailing newline)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(jobs, f, indent=2, ensure_ascii=False)
        f.write("\n")


def _validate(candidate: dict) -> None:
    for field in REQUIRED_FIELDS:
        if not str(candidate.get(field, "")).strip():
            raise ValueError(f"job is missing required field: {field}")
    if candidate["type"] not in VALID_TYPES:
        raise ValueError(
            f"job type must be one of {VALID_TYPES}, got {candidate['type']!r}"
        )


def find_duplicate(jobs: list[dict], candidate: dict) -> dict | None:
    """Return the existing job this candidate duplicates, or None.

    Checks the (company, position, location) key first, then a specific
    apply_url match.
    """
    key = dedupe_key(candidate)
    for job in jobs:
        if dedupe_key(job) == key:
            return job
    candidate_url = normalize_url(candidate.get("apply_url", ""))
    if candidate_url and is_specific_url(candidate.get("apply_url", "")):
        for job in jobs:
            existing_url = normalize_url(job.get("apply_url", ""))
            if existing_url and existing_url == candidate_url:
                return job
    return None


def describe(job: dict) -> str:
    """One-line human description used in duplicate-skip log lines."""
    return f"{job.get('company')} — {job.get('position')} ({job.get('location')})"


def add_job(
    jobs: list[dict], candidate: dict, date_seen: str | None = None
) -> tuple[str, str]:
    """Try to add a candidate job.

    Returns ("added", reason) or ("duplicate", reason). Raises ValueError
    for a candidate missing required fields. Does not write to disk —
    the caller owns saving.
    """
    _validate(candidate)
    existing = find_duplicate(jobs, candidate)
    if existing is not None:
        return ("duplicate", f"duplicate of {describe(existing)}")

    job = {
        "company": candidate["company"].strip(),
        "position": candidate["position"].strip(),
        "location": candidate["location"].strip(),
        "apply_url": (candidate.get("apply_url") or "").strip(),
        "type": candidate["type"],
        "source": (candidate.get("source") or "zero2sudo story").strip(),
        "date_seen": date_seen
        or (candidate.get("date_seen") or _today_chicago()),
        "salary": candidate.get("salary"),
    }
    if candidate.get("notes"):
        job["notes"] = candidate["notes"]
    jobs.append(job)
    return ("added", f"added {describe(job)}")


def _today_chicago() -> str:
    return datetime.now(ZoneInfo("America/Chicago")).date().isoformat()
