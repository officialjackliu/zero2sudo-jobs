#!/usr/bin/env python3
"""Import linked jobs from a public Direct Consideration post.

Usage:
    python3 scripts/import_blog.py --url URL --date-seen YYYY-MM-DD --dry-run
    python3 scripts/import_blog.py --url URL --date-seen YYYY-MM-DD
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import blog  # noqa: E402
import jobs  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Import linked blog jobs")
    parser.add_argument("--url", default=blog.DEFAULT_URL)
    parser.add_argument("--latest", action="store_true",
                        help="import every post linked from the public homepage")
    parser.add_argument("--date-seen", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--jobs-path", default=str(ROOT / "jobs.json"))
    args = parser.parse_args(argv)

    try:
        urls = blog.fetch_latest_posts() if args.latest else [args.url]
        candidates = [
            job for url in urls for job in blog.fetch_jobs(url)
        ]
        job_list = jobs.load_jobs(args.jobs_path)
    except Exception as exc:
        print(f"ERROR: import setup failed: {exc}", file=sys.stderr)
        return 1

    added = duplicate = errors = 0
    for candidate in candidates:
        try:
            status, reason = jobs.add_job(job_list, candidate, args.date_seen)
        except ValueError as exc:
            errors += 1
            print(f"ERROR: {candidate.get('apply_url')}: {exc}", file=sys.stderr)
            continue
        print(f"{status.upper()}: {reason}")
        if status == "added":
            added += 1
        else:
            duplicate += 1

    if not args.dry_run and added:
        jobs.save_jobs(job_list, args.jobs_path)
        import subprocess
        subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "update_readme.py")],
            check=True,
        )
    elif args.dry_run:
        print("[dry-run] no files were written.")

    print(
        f"Summary: extracted {len(candidates)} | added {added} | "
        f"duplicates {duplicate} | errors {errors}"
    )
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
