# Internship & New Grad Jobs — from @zero2sudo

A community checklist of software engineering **internships** and **new graduate** roles, sourced from the Instagram stories of creator [@zero2sudo](https://www.instagram.com/zero2sudo/). Built for students who want one simple, checkable list instead of hunting through expiring stories.

> **Last updated:** <!-- LAST_UPDATED -->2026-11-08<!-- /LAST_UPDATED -->

## How to use

1. Find a role in the tables below.
2. Click the link in the **Posting** column to open the application page.
3. Apply, then come back and check the list again — it is refreshed daily.

`jobs.json` is the source of truth for this list. The tables in this README are generated from it by `scripts/update_readme.py` — edit the JSON, never the tables by hand.

## Internships

<!-- JOBS:INTERNSHIPS -->
| Company | Position | Location | Posting | Age |
|---|---|---|---|---|
| *No jobs yet — check back soon.* | | | | |
<!-- /JOBS:INTERNSHIPS -->

## New Grad

<!-- JOBS:NEW_GRAD -->
| Company | Position | Location | Posting | Age |
|---|---|---|---|---|
| **Shield** | Engineer II, Software - Ground Control Station - Full Stack - New Grad - 6140 | Washington, D.C. | [jobs.lever.co](https://jobs.lever.co) | 0d |
<!-- /JOBS:NEW_GRAD -->

## Sources

- **[@zero2sudo](https://www.instagram.com/zero2sudo/) on Instagram** — the primary source. He posts job openings (and other job-search info) to his stories.
- **Inspiration / format:** [speedyapply/2027-SWE-College-Jobs](https://github.com/speedyapply/2027-SWE-College-Jobs) — the README table style this repo mirrors. No rows are copied from that repo; every job here was spotted in a zero2sudo story.

**A note on stories:** Instagram stories disappear after 24 hours, so this list is a snapshot — a job may already be gone from his story by the time you read it here. `date_seen` in `jobs.json` records when a role was first spotted. Always verify a posting is still open before applying, and check the employer's own careers page for the exact role.

## How updates work

The daily program (`scripts/run_daily.py`, run by GitHub Actions every morning at 8:00 AM CT) does three things the user asked for, in plain terms:

1. **It only looks at the last 24 hours.** Stories disappear after a day, so each run only considers stories posted in the last 24 hours. Every story it touches is recorded in `state/seen_stories.json` (story ID + when it was seen + what happened to it), and a story in that file is never processed twice — even if it is still visible.
2. **Job posts only.** Each story is classified before anything is extracted (rules in `scripts/classify.py`). A real job post has a company, a role title, and a hiring signal — an apply link, or "Apply"/"Hiring" wording plus a location. Everything else is skipped and logged: chats, polls, Q&A, personal updates, career advice, success stories, and "insider info" explainers. When in doubt, the program skips it — a missed job is a one-line manual fix, a wrong entry breaks trust in the list.
3. **No duplicate jobs.** Before adding anything, the program checks it against `jobs.json` (rules in `scripts/jobs.py`). Two entries are the same job when the company, role, and location match (ignoring case, punctuation, and extra spaces), or when they share the exact same application link. A duplicate is logged as "duplicate of …" and never added again.

How new stories get in:

- **Screenshots (works today, no login).** Drop a story screenshot into `screenshots/` and, next to it, a sidecar JSON with the same file name (`story-abc.json`) holding the company, position, location, apply link, and type (`internship` or `new_grad`). See [CONTRIBUTING.md](CONTRIBUTING.md) for the format. The daily run reads the screenshot + sidecar, classifies it, dedupes it, and adds it if it is new. Screenshots without a sidecar are OCR'd when possible; if the text cannot be read, the story is logged as "needs manual entry" and skipped — the program never guesses job details.
- **Instagram (needs the account connected).** `scripts/fetch.py` can list @zero2sudo's current stories through the connected instagram-cli, but Instagram is not connected yet, so this path is dormant. It never uses password scraping or login sessions (see `scripts/fetch.py` for why).
- **The README is rebuilt automatically.** After new jobs are added, `scripts/update_readme.py` regenerates the tables above from `jobs.json` and the workflow commits the result if anything changed. You can also run the whole thing locally:
  ```bash
  python3 -m unittest discover -s tests   # tests first
  python3 scripts/run_daily.py --dry-run  # preview, changes nothing
  python3 scripts/run_daily.py            # real run
  ```
4. **Optional secondary source (not enabled):** the workflow contains a commented-out step for pulling the public [speedyapply/2027-SWE-College-Jobs](https://github.com/speedyapply/2027-SWE-College-Jobs) list as a cross-check. It is off by default because this repo's scope is zero2sudo's story postings — enable it only if the maintainers decide to broaden the list.

## Contributing

Found a job in a zero2sudo story that isn't listed yet? See [CONTRIBUTING.md](CONTRIBUTING.md) — it's a two-minute edit to `jobs.json`.
