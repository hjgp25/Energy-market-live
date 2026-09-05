#!/usr/bin/env python3
"""
Automatically refresh site/rigcount.json from the public Baker Hughes
Rig Count overview page.

The script intentionally reads only the summary table on:
https://rigcount.bakerhughes.com/

It does not require an API key.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
OUTFILE = ROOT / "site" / "rigcount.json"

URLS = [
    "https://rigcount.bakerhughes.com/",
    "https://bakerhughesrigcount.gcs-web.com/",
    "https://rigcount.bakerhughes.com/?outputType=chromeless",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
}

def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()

def to_int(text: str) -> int:
    cleaned = normalize(text).replace(",", "")
    match = re.search(r"[+-]?\d+", cleaned)
    if not match:
        raise ValueError(f"No integer found in {text!r}")
    return int(match.group(0))

def get_html() -> tuple[str, str]:
    last_error = None
    for url in URLS:
        try:
            response = requests.get(url, headers=HEADERS, timeout=30)
            response.raise_for_status()
            if len(response.text) < 1000:
                raise RuntimeError("Response was unexpectedly short")
            return response.text, response.url
        except Exception as exc:
            last_error = exc
            print(f"Warning: failed to fetch {url}: {exc}", file=sys.stderr)
    raise RuntimeError(f"Unable to fetch Baker Hughes overview: {last_error}")

def parse_table(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    candidate = None

    for table in soup.find_all("table"):
        headers = [normalize(th.get_text(" ", strip=True)).lower() for th in table.find_all("th")]
        joined = " | ".join(headers)
        if "area" in joined and "count" in joined and "last count" in joined:
            candidate = table
            break

    if candidate is None:
        # Fallback: find a table containing the expected row names.
        for table in soup.find_all("table"):
            text = normalize(table.get_text(" ", strip=True)).lower()
            if "u.s." in text and "canada" in text and "international" in text:
                candidate = table
                break

    if candidate is None:
        raise RuntimeError("Could not find the Baker Hughes summary table")

    rows = []
    for tr in candidate.find_all("tr"):
        cells = [normalize(c.get_text(" ", strip=True)) for c in tr.find_all(["th", "td"])]
        if cells:
            rows.append(cells)

    # Expected public table columns:
    # Area | Last Count | Count | Change from Prior Count |
    # Date of Prior Count | Change from Last Year | Date of Last Year's Count
    parsed = {}
    for cells in rows:
        if len(cells) < 4:
            continue
        label = cells[0].lower().replace("\xa0", " ")
        item = {
            "last_count": cells[1],
            "count": to_int(cells[2]),
            "change": to_int(cells[3]),
        }
        if label in {"u.s.", "us", "u.s"} or label.startswith("u.s."):
            parsed["us"] = item
        elif label.startswith("canada"):
            parsed["canada"] = item
        elif label.startswith("international"):
            parsed["international"] = item

    missing = {"us", "canada", "international"} - parsed.keys()
    if missing:
        raise RuntimeError(f"Missing expected rows: {sorted(missing)}")

    us = parsed["us"]
    ca = parsed["canada"]
    parsed["north_america"] = {
        "last_count": us["last_count"],
        "count": us["count"] + ca["count"],
        "change": us["change"] + ca["change"],
    }
    return parsed

def main() -> int:
    html, final_url = get_html()
    data = parse_table(html)

    payload = {
        "source": "Baker Hughes Rig Count",
        "source_url": final_url,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        **data,
    }

    OUTFILE.parent.mkdir(parents=True, exist_ok=True)
    previous = None
    if OUTFILE.exists():
        try:
            previous = json.loads(OUTFILE.read_text(encoding="utf-8"))
        except Exception:
            previous = None

    # Avoid changing fetched_at when the actual published values/dates did not change.
    comparable_keys = ("us", "canada", "north_america", "international")
    if previous and all(previous.get(k) == payload.get(k) for k in comparable_keys):
        print("Baker Hughes values are unchanged; keeping existing rigcount.json.")
        return 0

    OUTFILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
