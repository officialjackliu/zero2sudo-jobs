#!/usr/bin/env python3
"""Story sources for the daily run.

Every adapter returns the same shape — a list of story dicts:

    {
        "story_id":  str,    # stable across runs; same story => same id
        "posted_at": datetime | None,  # America/Chicago, None if unknown
        "image_path": str | None,      # local file, or None when the
                                       # source cannot download the media
        "text":      str | None,       # text already known for the story
        "source":    str,              # "screenshots" or "instagram"
        "sidecar_path": str | None,    # screenshots adapter only
    }

Adapters:
  (a) screenshots — drop story screenshots into screenshots/. Works
      today, no login, no API. story_id is the SHA-256 of the file, so
      re-dropping the same screenshot is a no-op. posted_at is the
      file's modification time (a proxy for when the story was saved).
  (b) instagram_cli — lists @zero2sudo's current stories through the
      Muse instagram-cli connector (stories-tray + story-media +
      media-understanding). Requires Instagram to be connected; it is
      currently NOT connected, so this adapter raises a clear error
      until then. The CLI cannot download story media, so image_path
      is None and the adapter relies on media-understanding text.

NOT implemented, on purpose:
  * Instagram password scraping / instaloader login sessions. That
    means storing the user's Instagram credentials, violating
    Instagram's terms, and sessions that break constantly — plus a
    login from an unfamiliar automation IP risks the user's account.
    If story fetching ever needs to be fully automatic, the supported
    path is the connected instagram-cli adapter above, not a scraper.
"""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
CHICAGO = ZoneInfo("America/Chicago")
INSTAGRAM_CLI = "/opt/hatch/bin/instagram-cli"
CREATOR_USERNAME = "zero2sudo"
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fetch_screenshots(directory: Path | str | None = None) -> list[dict]:
    """Stories from screenshots/ — one entry per image file, sorted."""
    directory = Path(directory) if directory else ROOT / "screenshots"
    stories = []
    if not directory.exists():
        return stories
    for image in sorted(directory.iterdir()):
        if not image.is_file() or image.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        mtime = datetime.fromtimestamp(image.stat().st_mtime, tz=CHICAGO)
        sidecar = image.with_suffix(".json")
        stories.append(
            {
                "story_id": f"screenshot:{_sha256_file(image)}",
                "posted_at": mtime,
                "image_path": str(image),
                "text": None,
                "source": "screenshots",
                "sidecar_path": str(sidecar) if sidecar.exists() else None,
            }
        )
    return stories


def _run_cli(args: list[str]) -> dict:
    """Run instagram-cli and parse its JSON output."""
    proc = subprocess.run(
        [INSTAGRAM_CLI, *args], capture_output=True, text=True, timeout=120
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"instagram-cli {' '.join(args)} failed "
            f"(exit {proc.returncode}): {proc.stderr.strip() or proc.stdout.strip()}"
        )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"instagram-cli returned non-JSON output: {exc}")


def _first_account_id() -> str:
    result = _run_cli(["accounts"])
    accounts = result.get("accounts") or []
    if not accounts:
        raise RuntimeError(
            "Instagram is not connected. Connect it first (see README.md), "
            "then re-run with --source instagram."
        )
    return str(accounts[0]["user_fbid"])


def _collect_ids(node, key=("id", "media_id")):
    """Collect story media IDs from a loosely-shaped CLI response."""
    found = []
    if isinstance(node, dict):
        for k, value in node.items():
            if k in key and isinstance(value, (str, int)):
                found.append(str(value))
            else:
                found.extend(_collect_ids(value, key))
    elif isinstance(node, list):
        for item in node:
            found.extend(_collect_ids(item, key))
    return found


def fetch_instagram_cli() -> list[dict]:
    """Current @zero2sudo stories via the connected instagram-cli.

    NOTE: untested live — Instagram is not connected in this
    environment yet. Raises a clear error until it is.
    """
    account_id = _first_account_id()
    tray = _run_cli(["stories-tray", "--account-id", account_id, "--count", "200"])
    media_ids = _collect_ids(tray)
    stories = []
    for media_id in media_ids:
        try:
            media = _run_cli(
                ["story-media", "--account-id", account_id, "--ids", media_id]
            )
        except RuntimeError:
            continue
        permalink = ""
        posted_at = None
        # story-media returns permalinks + posting times; walk it loosely.
        stack = [media]
        while stack:
            node = stack.pop()
            if isinstance(node, dict):
                permalink = node.get("permalink") or node.get("url") or permalink
                raw_time = node.get("posted_at") or node.get("taken_at")
                if raw_time and posted_at is None:
                    try:
                        posted_at = datetime.fromtimestamp(
                            int(raw_time), tz=CHICAGO
                        )
                    except (ValueError, TypeError):
                        posted_at = None
                stack.extend(node.values())
            elif isinstance(node, list):
                stack.extend(node)
        if CREATOR_USERNAME not in permalink:
            continue
        text = None
        try:
            understanding = _run_cli(
                ["media-understanding", "--account-id", account_id,
                 "--media-ids", media_id]
            )
            bits = []
            stack = [understanding]
            while stack:
                node = stack.pop()
                if isinstance(node, dict):
                    for k in ("narrative", "summary", "description", "text"):
                        if isinstance(node.get(k), str):
                            bits.append(node[k])
                    stack.extend(node.values())
                elif isinstance(node, list):
                    stack.extend(node)
            text = "\n".join(bits) if bits else None
        except RuntimeError:
            text = None
        stories.append(
            {
                "story_id": f"instagram:{media_id}",
                "posted_at": posted_at,
                "image_path": None,  # the CLI cannot download story media
                "text": text,
                "source": "instagram",
                "sidecar_path": None,
            }
        )
    return stories


def fetch(source: str, **kwargs) -> list[dict]:
    """Dispatch to an adapter. source is 'screenshots' or 'instagram'."""
    if source == "screenshots":
        return fetch_screenshots(kwargs.get("directory"))
    if source == "instagram":
        return fetch_instagram_cli()
    raise ValueError(f"unknown source: {source!r} (expected screenshots|instagram)")
