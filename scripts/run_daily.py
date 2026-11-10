#!/usr/bin/env python3
"""Daily run: fetch recent @zero2sudo stories, add new job posts only.

Pipeline (each step logs what it did and why):
  1. Fetch stories from the chosen source, keeping only stories posted
     in the last 24 hours.
  2. Skip any story ID already recorded in state/seen_stories.json —
     a story is processed at most once, even if it is still visible.
  3. Classify each remaining story: job posts only. Chats, polls,
     Q&A, advice, success stories, and explainers are skipped with a
     reason (see scripts/classify.py). When in doubt, skip.
  4. Extract job fields (sidecar JSON, or OCR text parsed
     conservatively). If fields cannot be read confidently, the story
     is marked "needs manual entry" — never guessed.
  5. Dedupe against jobs.json (scripts/jobs.py). A job already listed
     is logged as "duplicate of <existing>" and not added again.
  6. Append genuinely new jobs, save jobs.json, rebuild the README
     (scripts/update_readme.py), and record every processed story in
     the state file.

Usage:
    python3 scripts/run_daily.py [--source screenshots|instagram] [--dry-run]

--dry-run prints the summary and changes nothing. Exit code is 0 on a
clean run (including a clean no-op) and non-zero when any story errored.
"""

import argparse
import json
import subprocess
import sys
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))

import classify  # noqa: E402
import extract  # noqa: E402
import fetch  # noqa: E402
import jobs as jobs_mod  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CHICAGO = ZoneInfo("America/Chicago")
WINDOW = timedelta(hours=24)
STATE_VERSION = 1


def load_state(path: Path) -> dict:
    if not path.exists():
        return {"version": STATE_VERSION, "stories": {}}
    with path.open(encoding="utf-8") as f:
        state = json.load(f)
    if not isinstance(state, dict) or "stories" not in state:
        raise ValueError(f"state file {path} is malformed")
    return state


def save_state(state: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
        f.write("\n")
    tmp.replace(path)


def rebuild_readme() -> None:
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "update_readme.py")],
        check=True,
    )


def process_story(story: dict, job_list: list[dict], now: datetime) -> dict:
    """Process one story. Returns an outcome dict with a verdict.

    Verdicts: added | duplicate | non_job | needs_manual | too_old
    """
    story_id = story["story_id"]
    posted_at = story.get("posted_at")

    # 1. 24-hour window (unknown post time counts as in-window, with a note).
    if posted_at is not None and posted_at < now - WINDOW:
        return {
            "verdict": "too_old",
            "reason": f"posted {posted_at.date()}, outside the 24h window",
        }

    # 2. Extract text: sidecar first, then OCR, then media-understanding.
    text = story.get("text") or ""
    method = "provided"
    sidecar = None
    image_path = story.get("image_path")
    if image_path:
        result = extract.extract_text(image_path)
        text = result["text"]
        method = result["method"]
        sidecar = result.get("sidecar")
        if result["needs_vision"] and not sidecar:
            return {
                "verdict": "needs_manual",
                "reason": f"no readable text ({method}); drop a sidecar JSON "
                "next to the screenshot or connect a vision step",
            }
    if not text.strip():
        return {
            "verdict": "needs_manual",
            "reason": "no text available for this story",
        }

    # 3. Job-only classification.
    is_job, reason = classify.is_job_post(text)
    if not is_job:
        return {"verdict": "non_job", "reason": reason}

    # 4. Build the candidate job.
    if sidecar is not None:
        candidate = dict(sidecar)
        candidate.setdefault("source", "zero2sudo story")
        candidate.setdefault("date_seen", now.date().isoformat())
    else:
        candidate = extract.parse_job_text(text)
        if candidate is None:
            return {
                "verdict": "needs_manual",
                "reason": "looks like a job post but company/position/location "
                "could not be read confidently from the text",
            }
        candidate["date_seen"] = now.date().isoformat()

    # 5. Dedupe against jobs.json.
    status, detail = jobs_mod.add_job(job_list, candidate)
    if status == "duplicate":
        return {"verdict": "duplicate", "reason": detail}
    return {"verdict": "added", "reason": detail}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Daily @zero2sudo story job run")
    parser.add_argument(
        "--source", choices=("screenshots", "instagram"), default="screenshots",
        help="where stories come from (default: screenshots)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="report what would happen; write nothing",
    )
    parser.add_argument("--jobs-path", default=str(ROOT / "jobs.json"))
    parser.add_argument("--state-path", default=str(ROOT / "state" / "seen_stories.json"))
    parser.add_argument("--screenshots-dir", default=str(ROOT / "screenshots"))
    args = parser.parse_args(argv)

    now = datetime.now(CHICAGO)
    jobs_path = Path(args.jobs_path)
    state_path = Path(args.state_path)
    counts = {
        "added": 0,
        "duplicate": 0,
        "non_job": 0,
        "seen": 0,
        "too_old": 0,
        "needs_manual": 0,
        "errors": 0,
    }

    try:
        job_list = jobs_mod.load_jobs(jobs_path)
        state = load_state(state_path)
        stories = fetch.fetch(
            args.source,
            directory=Path(args.screenshots_dir) if args.source == "screenshots" else None,
        )
    except Exception as exc:  # noqa: BLE001 - top-level failure, report and exit 1
        print(f"ERROR: setup failed: {exc}", file=sys.stderr)
        return 1

    seen = state["stories"]
    state_changed = False
    jobs_changed = False

    for story in stories:
        story_id = story["story_id"]
        entry = seen.get(story_id)

        # Skip stories already processed — unless a needs-manual story
        # gained a sidecar JSON since, in which case it gets one retry.
        if entry is not None:
            sidecar_path = story.get("sidecar_path")
            retry = (
                entry.get("verdict") == "needs_manual"
                and sidecar_path
                and Path(sidecar_path).exists()
                and str(Path(sidecar_path).stat().st_mtime)
                != str(entry.get("sidecar_mtime", ""))
            )
            if not retry:
                counts["seen"] += 1
                print(f"SKIP seen: {story_id} ({entry.get('verdict')})")
                continue
            print(f"RETRY: {story_id} (sidecar JSON added since last run)")

        try:
            outcome = process_story(story, job_list, now)
        except Exception:  # noqa: BLE001 - per-story failure, count and continue
            counts["errors"] += 1
            print(f"ERROR: {story_id}\n{traceback.format_exc()}", file=sys.stderr)
            continue

        verdict = outcome["verdict"]
        counts[verdict if verdict in counts else "errors"] += 1
        print(f"{verdict.upper()}: {story_id} — {outcome['reason']}")

        if verdict == "added":
            jobs_changed = True
        if verdict not in ("too_old",):
            record = {
                "posted_at": (
                    story["posted_at"].isoformat()
                    if story.get("posted_at")
                    else None
                ),
                "source": story.get("source"),
                "verdict": verdict,
                "reason": outcome["reason"],
                "processed_at": now.isoformat(),
            }
            sidecar_path = story.get("sidecar_path")
            if sidecar_path and Path(sidecar_path).exists():
                record["sidecar_mtime"] = str(Path(sidecar_path).stat().st_mtime)
            seen[story_id] = record
            state_changed = True

    if args.dry_run:
        print("\n[dry-run] no files were written.")
    else:
        if jobs_changed:
            jobs_mod.save_jobs(job_list, jobs_path)
            rebuild_readme()
        if state_changed:
            save_state(state, state_path)

    print(
        "\nSummary: added {added} | duplicates skipped {duplicate} | "
        "non-job skipped {non_job} | already seen {seen} | too old {too_old} | "
        "needs manual {needs_manual} | errors {errors}".format(**counts)
    )
    return 1 if counts["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
