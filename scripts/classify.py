#!/usr/bin/env python3
"""Job-only classifier for @zero2sudo Instagram stories.

A story is a *job post* only when it is a specific hiring listing:
a company + a role title + hiring/apply signals (an apply link, or
"Apply"/"Hiring" wording plus a location). Everything else the creator
posts — chats, polls, Q&A, personal updates, career advice, success
stories, "insider info" explainers — must be skipped.

When in doubt, SKIP. A missed job is a one-line manual fix; a non-job
in the list breaks trust in the whole checklist.

Rules (evaluated in order — keep them readable, tune them here):
  1. Polls are never jobs.
  2. An apply link (lever.co, greenhouse, workday, ashby, careers URL,
     or any URL under a jobs/careers host) + a role keyword = a job post.
  3. Known non-job formats (Q&A, advice, success story, insider-info
     explainer, chat/personal update) are rejected with a reason.
  4. Otherwise, a job post needs a role keyword AND a hiring signal
     AND a location signal (a "City, ST" pattern, "Remote", "Hybrid",
     or "On-Site").
  5. Anything else is rejected as "not enough job signals".

`is_job_post(text)` returns (bool, reason) — the reason is logged by
the daily run so every skip is explainable.
"""

import re

# --- Signals ---------------------------------------------------------------

# Words that appear in a role title. A job post always names a role.
ROLE_KEYWORDS = (
    "intern",
    "internship",
    "new grad",
    "new graduate",
    "software engineer",
    "software developer",
    "swe",
    "engineer",
    "developer",
    "data scientist",
    "data engineer",
    "product manager",
    "program manager",
    "tpm",
    "analyst",
    "designer",
    "research scientist",
    "machine learning",
    "ml engineer",
    "ai engineer",
    "frontend",
    "front-end",
    "backend",
    "back-end",
    "full stack",
    "full-stack",
    "ios",
    "android",
    "embedded",
    "firmware",
    "quant",
    "trader",
)

# Words/phrases that signal active hiring.
HIRING_SIGNALS = (
    "apply",
    "hiring",
    "we're hiring",
    "we are hiring",
    "now hiring",
    "applications open",
    "application open",
    "open role",
    "open roles",
    "job opening",
    "job postings",
    "accepting applications",
    "apply now",
    "apply here",
    "link in bio",
)

# Hosts/domains that are (almost always) application links, plus URL
# path markers that mean "this link goes to a job application"
# (e.g. https://acme.example/careers/123).
APPLY_LINK_HOSTS = (
    "lever.co",
    "greenhouse.io",
    "boards.greenhouse.io",
    "workday.com",
    "myworkdayjobs.com",
    "ashbyhq.com",
    "jobs.",
    "careers.",
    "apply.",
)
APPLY_LINK_PATHS = ("/careers", "/jobs/", "/job/", "/apply", "/openings")

# "City, ST" (e.g. "New York, NY"), "Washington, D.C.", or a work-mode word.
_LOCATION_RE = re.compile(
    r"\b[A-Z][A-Za-z]+(?: [A-Z][A-Za-z]+)*, [A-Z]{2}\b"  # New York, NY
    r"|\b[A-Z][A-Za-z]+(?: [A-Z][A-Za-z]+)*, D\.C\."  # Washington, D.C.
)
_LOCATION_WORDS = ("remote", "hybrid", "on-site", "onsite", "in-office")

# --- Non-job formats (checked before the generic job test) ----------------
# Each entry: (label, phrases that identify it). Keep phrases specific:
# a generic word like "how" would false-positive on "how to apply".

NON_JOB_MARKERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "poll",
        ("poll", "tap to vote", "vote for", "which one do you pick", "poll ends"),
    ),
    (
        "q&a / chat",
        (
            "q&a",
            "ask me anything",
            "ask me",
            "drop your questions",
            "your questions",
            "ama ",
        ),
    ),
    (
        "career advice",
        (
            "how to pass",
            "how to crack",
            "how to get",
            "tips for",
            "resume tip",
            "interview tip",
            "my advice",
            "things i wish i knew",
            "mistakes to avoid",
        ),
    ),
    (
        "success story",
        (
            "got the offer",
            "landed the",
            "landed an",
            "just signed",
            "success story",
            "congrats to",
            "from 0 offers",
        ),
    ),
    (
        "insider-info explainer",
        (
            "insider info",
            "explained",
            "everything you need to know",
            "what is a",
            "what are",
            "deep dive",
        ),
    ),
    (
        "personal update",
        (
            "day in my life",
            "a day in the life",
            "my morning routine",
            "vlog",
            "grwm",
        ),
    ),
)

_URL_RE = re.compile(r"https?://[^\s)>\"]+|(?:[a-z0-9-]+\.)+(?:co|com|io|ai|jobs)\b", re.I)


def _contains_any(text: str, phrases) -> str | None:
    for phrase in phrases:
        if phrase in text:
            return phrase
    return None


def _has_role_keyword(text: str) -> str | None:
    return _contains_any(text, ROLE_KEYWORDS)


def _has_hiring_signal(text: str) -> str | None:
    return _contains_any(text, HIRING_SIGNALS)


def _has_apply_link(text: str) -> str | None:
    for url in _URL_RE.findall(text):
        lowered = url.lower()
        if any(host in lowered for host in APPLY_LINK_HOSTS):
            return url
        if any(marker in lowered for marker in APPLY_LINK_PATHS):
            return url
    return None


def _has_location(text: str) -> bool:
    if _LOCATION_RE.search(text):
        return True
    lowered = text.lower()
    return any(word in lowered for word in _LOCATION_WORDS)


def is_job_post(text: str) -> tuple[bool, str]:
    """Classify story text. Returns (is_job, reason)."""
    text = text or ""
    lowered = text.lower()

    # 1. Polls are never jobs, even if they mention companies.
    hit = _contains_any(lowered, NON_JOB_MARKERS[0][1])
    if hit:
        return (False, f"non-job: poll (matched {hit!r})")

    # 2. Apply link + role keyword is the strongest job evidence.
    link = _has_apply_link(text)
    role = _has_role_keyword(lowered)
    if link and role:
        return (True, f"job post: apply link ({link}) + role keyword ({role!r})")

    # 3. Known non-job formats.
    for label, phrases in NON_JOB_MARKERS[1:]:
        hit = _contains_any(lowered, phrases)
        if hit:
            return (False, f"non-job: {label} (matched {hit!r})")

    # 4. Role + hiring signal + location, without an apply link.
    hiring = _has_hiring_signal(lowered)
    if role and hiring and _has_location(text):
        return (
            True,
            f"job post: role ({role!r}) + hiring signal ({hiring!r}) + location",
        )

    # 5. Not enough evidence — skip rather than guess.
    missing = []
    if not role:
        missing.append("role keyword")
    if not hiring:
        missing.append("hiring/apply signal")
    if not _has_location(text):
        missing.append("location")
    return (False, f"non-job: not enough job signals (missing: {', '.join(missing)})")
