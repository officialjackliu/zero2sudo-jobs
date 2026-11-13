#!/usr/bin/env python3
"""Extract structured job links from a public Direct Consideration post.

The importer reads only public HTML and keeps the original application URL.
It does not authenticate, bypass access controls, or copy article prose.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urljoin
from urllib.request import Request, urlopen

DEFAULT_URL = "https://directconsideration.com/p/direct-consideration-025"
_LOCATION_RE = re.compile(
    r"\b(?:in|based in|hybrid in|with|locations? (?:are|listed in))\s+"
    r"([^.;]+)",
    re.IGNORECASE,
)
_KNOWN_COMPANY_PREFIXES = (
    "Palantir", "The New York Times", "General Motors", "Lila Sciences",
    "Alaska Airlines", "Capital One", "Wolverine Trading",
    "Amazon Future Engineer", "NBCUniversal", "McDonald’s",
)


@dataclass(frozen=True)
class BlogJob:
    company: str
    position: str
    location: str
    apply_url: str
    type: str
    source: str
    notes: str


def fetch_html(url: str, timeout: int = 30) -> str:
    request = Request(url, headers={"User-Agent": "zero2sudo-jobs/1.0"})
    with urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8")


class _PostLinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.urls: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        href = dict(attrs).get("href")
        if href and "/p/" in href:
            self.urls.append(urljoin("https://directconsideration.com", href))


def discover_posts(html_text: str, base_url: str = "https://directconsideration.com") -> list[str]:
    """Return unique public post URLs in homepage order."""
    parser = _PostLinkParser()
    parser.feed(html_text)
    return list(dict.fromkeys(urljoin(base_url, url) for url in parser.urls))


class _PostParser(HTMLParser):
    """Capture article headings, text, and links without external packages."""

    def __init__(self) -> None:
        super().__init__()
        self.blocks: list[dict] = []
        self._heading: str | None = None
        self._heading_text: list[str] = []
        self._in_heading = False
        self._link_href: str | None = None
        self._link_text: list[str] = []
        self._block_text: list[str] = []
        self._links: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"h2", "h3"}:
            self._finish_block()
            self._heading = tag
            self._heading_text = []
            self._block_text = []
            self._links = []
            self._in_heading = True
        elif tag == "a":
            self._link_href = dict(attrs).get("href")
            self._link_text = []

    def handle_data(self, data: str) -> None:
        if self._in_heading:
            self._heading_text.append(data)
        elif self._heading:
            self._block_text.append(data)
        if self._link_href is not None:
            self._link_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._link_href is not None:
            label = _clean(" ".join(self._link_text))
            if label and self._link_href.startswith(("http://", "https://")):
                self._links.append((label, html.unescape(self._link_href)))
            self._link_href = None
            self._link_text = []
        elif tag == self._heading:
            self._in_heading = False

    def _finish_block(self) -> None:
        if self._heading is None:
            return
        heading = _clean(" ".join(self._heading_text))
        if heading and heading.lower() != "keep reading":
            self.blocks.append(
                {
                    "heading": heading,
                    "text": _clean(" ".join(self._block_text)),
                    "links": list(self._links),
                }
            )
        self._heading = None
        self._in_heading = False

    def close(self) -> None:
        super().close()
        self._finish_block()


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _description(block: dict) -> str:
    text = block["text"]
    text = re.sub(
        r"\bCohort:\s*(?:Internship|PhD Internship|New Grad(?:\s*&\s*Senior[’']s)?)\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )
    for label, _ in block["links"]:
        text = text.replace(label, "")
    return _clean(text)


def _job_type(block: dict) -> str:
    text = f"{block['heading']} {block['text']}".lower()
    return "new_grad" if "new grad" in text or "recent college" in text else "internship"


def _company(label: str, heading: str) -> str:
    heading_company = _heading_company(heading)
    value = re.sub(r"^apply to\s+", "", label, flags=re.IGNORECASE)
    value = re.sub(r"\s*→$", "", value).strip()
    if heading.startswith(_KNOWN_COMPANY_PREFIXES):
        return heading_company
    if "," in value:
        value = value.split(",", 1)[0].strip()
    else:
        prefix = re.match(
            r"^(NYT|TikTok)\b", value, flags=re.IGNORECASE
        )
        if prefix:
            value = prefix.group(1)
    if value.lower() in {"swe", "mobile developer", "connectivity platform and product",
                         "data connectors", "data", "ai, & ml", "pm",
                         "cybersecurity", "data analytics"}:
        value = _heading_company(heading)
    if value == "NYT":
        return "The New York Times"
    if value:
        return value
    return heading.split()[0]


def _heading_company(heading: str) -> str:
    for prefix in _KNOWN_COMPANY_PREFIXES:
        if heading.startswith(prefix):
            return prefix
    return heading.split()[0]


def _position(label: str, heading: str) -> str:
    value = re.sub(r"^apply to\s+", "", label, flags=re.IGNORECASE)
    value = re.sub(r"\s*→$", "", value).strip()
    if "," in value:
        value = value.split(",", 1)[1].strip()
    else:
        value = re.sub(r"^(?:NYT|TikTok)\s+", "", value, flags=re.IGNORECASE)
    heading_company = _heading_company(heading).lower()
    if value and value.lower() not in {
        "tesla", "zoox", "tinder", "samsara", "moody", "salesforce",
        "pinterest", "stripe", "microsoft", "datarobot", "beli", "amazon",
        "mcdonald's", "addepar", "nvidia", "cisco", "uipath", "apple",
    } and value.lower() != heading_company:
        return value
    return heading


def _location(text: str) -> str:
    dc = re.search(r"\b[A-Z][A-Za-z]+, D\.C\.", text)
    if dc:
        return dc.group(0)
    locations = re.findall(
        r"\b[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*,\s*[A-Z]{2}\b", text
    )
    unique = list(dict.fromkeys(locations))
    if unique:
        return "; ".join(unique)
    match = _LOCATION_RE.search(text)
    if match:
        return _clean(match.group(1)).rstrip(",")
    return ""


def parse_post(html_text: str, source_url: str) -> list[dict]:
    parser = _PostParser()
    parser.feed(html_text)
    parser.close()
    jobs = []
    for block in parser.blocks:
        if block["heading"].lower() in {"events watchlist", "keep reading"}:
            break
        location = _location(block["text"])
        if not location:
            continue
        for label, apply_url in block["links"]:
            if not label.lower().startswith("apply to "):
                continue
            jobs.append(
                {
                    "company": _company(label, block["heading"]),
                    "position": _position(label, block["heading"]),
                    "location": location,
                    "apply_url": apply_url,
                    "type": _job_type(block),
                    "source": source_url,
                    "salary": None,
                    "notes": _description(block),
                }
            )
    return jobs


def fetch_jobs(url: str = DEFAULT_URL) -> list[dict]:
    return parse_post(fetch_html(url), url)


def fetch_latest_posts(url: str = "https://directconsideration.com") -> list[str]:
    return discover_posts(fetch_html(url), url)
