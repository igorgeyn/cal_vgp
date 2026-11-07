#!/usr/bin/env python3
"""Check reviewed official-results links and record each check in place.

The site shows a results link only when its latest recorded check succeeded,
with the real check time. A failed check is recorded as a failure, never
silently dropped, so "no link" and "link checked and broken" stay distinct.

    python scraper/scripts/check_official_results_links.py [--file PATH]

A check passes only when the page returns 200 *and* contains the entry's
``expect_text`` (for example the election date as the page writes it). One GET
per link, with a project-identifying User-Agent and no retries. Bot-challenge
pages (which often return 200) are recorded as ``bot_challenge`` failures and
are never worked around; such a link needs a person to open it and record a
``manual_check`` (see the data file's note).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.website.election_status import OFFICIAL_RESULTS_PATH, load_official_results  # noqa: E402

USER_AGENT = "cal-vgp-results-link-check/0.1 (+https://github.com/igorgeyn/cal_vgp)"
TIMEOUT_SECONDS = 30
MAX_BYTES = 5_000_000
CHALLENGE_MARKERS = ("_Incapsula_Resource", "Request unsuccessful. Incapsula",
                     "cf-challenge", "challenge-platform", "Just a moment...")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def check(url: str, expect_text: str) -> dict:
    checked_at = utc_now()
    try:
        with requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT_SECONDS,
                          allow_redirects=True, stream=True) as response:
            body = response.raw.read(MAX_BYTES, decode_content=True)
            status, final_url = response.status_code, response.url
    except requests.RequestException as error:
        return {"checked_at": checked_at, "ok": False, "reason": type(error).__name__}
    text = body.decode("utf-8", errors="replace")
    result = {"checked_at": checked_at, "http_status": status, "final_url": final_url}
    if any(marker in text for marker in CHALLENGE_MARKERS):
        return {**result, "ok": False, "reason": "bot_challenge"}
    if status != 200:
        return {**result, "ok": False, "reason": "http_status"}
    if expect_text not in text:
        return {**result, "ok": False, "reason": "expected_text_missing"}
    return {**result, "ok": True, "matched_text": expect_text}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--file", type=Path, default=OFFICIAL_RESULTS_PATH)
    args = parser.parse_args(argv)
    load_official_results(args.file)  # validate before any network call
    payload = json.loads(args.file.read_text(encoding="utf-8"))
    failures = 0
    for entry in payload["links"]:
        entry["last_check"] = check(entry["url"], entry["expect_text"])
        state = "ok" if entry["last_check"]["ok"] else entry["last_check"]["reason"]
        failures += not entry["last_check"]["ok"]
        print(f"{state:22} {entry['last_check'].get('http_status', '-')} {entry['url']}")
    args.file.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
