#!/usr/bin/env python3
"""Extract job text/fields from a story image.

Design rule: this module NEVER invents job fields. It only reports what
it can actually read:

  * If a sidecar JSON file sits next to the image
    (<stem>.json with company/position/location/...), its fields are
    used verbatim — that is the manual/vision path, where a human or a
    vision-capable agent has already read the image.
  * Else, if pytesseract + tesseract are installed, the image is OCR'd
    and the raw text is returned for classification.
  * Else, the story is reported as "needs vision/manual entry" and the
    daily run skips it (it is recorded in the state file, not retried
    forever, and not added to jobs.json).

To add a story by hand: drop the screenshot in screenshots/ and add a
sidecar JSON next to it, e.g. screenshots/story-abc123.json:

    {
      "company": "Shield",
      "position": "Engineer II, Software - New Grad",
      "location": "Washington, D.C.",
      "apply_url": "https://jobs.lever.co/shield/abc",
      "type": "new_grad",
      "salary": null
    }

Optional OCR setup (only needed for the automatic path):
    pip install pytesseract pillow
    # plus the tesseract binary: apt install tesseract-ocr / brew install tesseract
"""

import json
import re
from pathlib import Path

# Conservative patterns used by parse_job_text. They only *find* text
# that is already there; nothing is guessed.
_URL_RE = re.compile(
    r"https?://[^\s)>\"]+|(?:[a-z0-9-]+\.)+(?:lever\.co|greenhouse\.io|"
    r"workday\.com|myworkdayjobs\.com|ashbyhq\.com|jobs|careers)[^\s)>\"]*",
    re.I,
)
_LOCATION_RE = re.compile(
    r"\b[A-Z][A-Za-z]+(?: [A-Z][A-Za-z]+)*, [A-Z]{2}\b"
    r"|\b[A-Z][A-Za-z]+(?: [A-Z][A-Za-z]+)*, D\.C\."
    r"|\bRemote\b|\bHybrid\b",
)

_ROLE_WORDS = (
    "intern",
    "new grad",
    "engineer",
    "developer",
    "scientist",
    "analyst",
    "manager",
    "designer",
    "research",
    "quant",
    "trader",
)


def sidecar_path(image_path: Path | str) -> Path:
    """<stem>.json next to the image."""
    image_path = Path(image_path)
    return image_path.with_suffix(".json")


def load_sidecar(image_path: Path | str) -> dict | None:
    """Load and validate a sidecar JSON. Returns None when absent.

    Raises ValueError when the sidecar exists but is missing required
    fields — a bad sidecar is an error, not a silent skip.
    """
    path = sidecar_path(image_path)
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"sidecar {path} must contain a JSON object")
    for field in ("company", "position", "location"):
        if not str(data.get(field, "")).strip():
            raise ValueError(f"sidecar {path} is missing required field: {field}")
    if data.get("type", "internship") not in ("internship", "new_grad"):
        raise ValueError(f"sidecar {path}: type must be internship or new_grad")
    return data


def ocr_image(image_path: Path | str) -> tuple[str, str]:
    """OCR an image. Returns (text, method).

    method is "tesseract" when OCR ran, or "unavailable" when pytesseract
    / tesseract is not installed. Never raises for a missing OCR stack —
    the caller treats an empty result as "needs vision".
    """
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        return ("", "unavailable")
    try:
        with Image.open(image_path) as image:
            text = pytesseract.image_to_string(image)
        return (text or "", "tesseract")
    except Exception:
        return ("", "unavailable")


def extract_text(image_path: Path | str) -> dict:
    """Extract readable text from a story image.

    Returns {"text": str, "method": str, "needs_vision": bool}.
    method is one of "sidecar", "tesseract", "unavailable".
    """
    sidecar = load_sidecar(image_path)
    if sidecar is not None:
        text = "\n".join(
            str(sidecar.get(field, ""))
            for field in ("company", "position", "location", "apply_url")
            if sidecar.get(field)
        )
        return {"text": text, "method": "sidecar", "needs_vision": False,
                "sidecar": sidecar}

    text, method = ocr_image(image_path)
    return {
        "text": text,
        "method": method,
        "needs_vision": method == "unavailable" or not text.strip(),
    }


def parse_job_text(text: str) -> dict | None:
    """Best-effort parse of OCR'd story text into job fields.

    Only fills in fields found with high confidence (an apply URL by
    regex, a "City, ST" location by regex, the longest line containing
    a role word as the position, and a short first line as the company).
    Returns None when company, position, or location cannot be found —
    the caller must then mark the story "needs manual entry", never
    fill in the blanks itself.
    """
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    if not lines:
        return None

    url_match = _URL_RE.search(text or "")
    apply_url = url_match.group(0) if url_match else ""
    if apply_url and not apply_url.startswith("http"):
        apply_url = "https://" + apply_url
    if apply_url:
        # Hosts are case-insensitive (OCR often returns "JOBS.LEVER.CO");
        # lowercase scheme + host, leave any path untouched.
        scheme, _, rest = apply_url.partition("://")
        host, slash, path = rest.partition("/")
        apply_url = f"{scheme.lower()}://{host.lower()}" + (slash + path if slash else "")

    location = ""
    loc_match = _LOCATION_RE.search(text or "")
    if loc_match:
        location = loc_match.group(0)

    position = ""
    # Role titles in story images are often line-wrapped mid-title
    # ("Engineer II,\nSoftware - Ground Control Station -\nFull Stack...").
    # Take the whole block from the first role-word line up to (but not
    # including) the location line, and join it into one title.
    role_start = next(
        (i for i, line in enumerate(lines)
         if any(word in line.lower() for word in _ROLE_WORDS)),
        None,
    )
    if role_start is not None:
        loc_idx = next(
            (i for i, line in enumerate(lines) if _LOCATION_RE.search(line)),
            len(lines),
        )
        block = lines[role_start:loc_idx] if loc_idx > role_start else []
        position = re.sub(r"\s+", " ", " ".join(block)).strip()
        position = re.sub(r"\s*-\s*$", "", position)

    company = ""
    first = lines[0]
    if len(first) <= 40 and not any(word in first.lower() for word in _ROLE_WORDS):
        company = first

    if not (company and position and location):
        return None

    job_type = "internship" if "intern" in (position + " " + text).lower() else "new_grad"
    return {
        "company": company,
        "position": position,
        "location": location,
        "apply_url": apply_url,
        "type": job_type,
        "source": "zero2sudo story",
        "salary": None,
    }
