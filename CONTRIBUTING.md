# Contributing

Thanks for helping keep this list useful for other students! Adding a job takes about two minutes.

## Add a job from a story screenshot (fastest)

1. Fork this repo and clone your fork.
2. Save the story screenshot into `screenshots/` (PNG or JPG), e.g. `screenshots/shield-ground-control.png`.
3. Next to it, add a sidecar JSON with the same file name, e.g. `screenshots/shield-ground-control.json`:

   ```json
   {
     "company": "Shield",
     "position": "Engineer II, Software - Ground Control Station - Full Stack - New Grad - 6140",
     "location": "Washington, D.C.",
     "apply_url": "https://jobs.lever.co/shield/abc123",
     "type": "new_grad",
     "salary": null
   }
   ```

   Field notes:
   - `type` must be `internship` or `new_grad`.
   - `apply_url` should be the exact application link from the story. If the story only shows a domain (e.g. `jobs.lever.co`) and not a full posting URL, put the domain only — never guess a full URL.
   - `salary` is optional — include it only when the story or posting states it; otherwise use `null`.
4. Preview what the daily run would do (changes nothing):
   ```bash
   python3 scripts/run_daily.py --dry-run --source screenshots
   ```
   The run classifies the story (job posts only), checks it against `jobs.json` for duplicates, and reports what it would add. If it says "duplicate of …", the job is already listed — don't force it in.
5. Commit the screenshot, the sidecar JSON, and the updated `jobs.json`/`README.md`, and open a pull request.

## Add a job manually

1. Fork this repo and clone your fork.
2. Open `jobs.json` and append one object to the array:

   ```json
   {
     "company": "Acme Corp",
     "position": "Software Engineer Intern - Summer 2027",
     "location": "New York, NY",
     "apply_url": "https://example.com/careers/12345",
     "type": "internship",
     "source": "zero2sudo story",
     "date_seen": "2026-11-08",
     "salary": "$50/hr"
   }
   ```

   Field notes:
   - `type` must be `internship` or `new_grad`.
   - `apply_url` should be the exact application link from the story. If the story only shows a domain (e.g. `jobs.lever.co`) and not a full posting URL, put the domain only — never guess a full URL.
   - `salary` is optional — include it only when the story or posting states it; otherwise use `null`.
   - `date_seen` is the date (YYYY-MM-DD) you first saw the role in a story.
   - `source` is usually `"zero2sudo story"`. If you found the role elsewhere, say so honestly (e.g. `"employer careers page"`).
3. Regenerate the README tables:
   ```bash
   python3 scripts/update_readme.py
   ```
4. Commit both `jobs.json` and `README.md`, and open a pull request.

## Rules

- **Only jobs spotted in @zero2sudo's stories** (or confirmed on the employer's own careers page as the same role). Don't copy rows from other lists wholesale.
- Don't invent apply URLs, salaries, or deadlines — if it wasn't in the story, leave it out or mark it unknown.
- One job per object; don't duplicate a role that's already listed (check `jobs.json` first). The daily run enforces this automatically — a duplicate is logged and skipped.
- The daily run only looks at stories from the last 24 hours, and each story is processed once (tracked in `state/seen_stories.json`). A screenshot older than that is ignored unless you add the job manually.
- Instagram stories expire after 24h, so a screenshot or the story text in the PR description helps reviewers verify the entry.
