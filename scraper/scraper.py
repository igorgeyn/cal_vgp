#!/usr/bin/env python
"""
Simple scraper for California Secretary of State (SOS) statewide ballot measures.

* Fetches the list of qualified statewide ballot measures from:
  https://www.sos.ca.gov/elections/ballot-measures/qualified-ballot-measures
* Extracts the election date/header, the measure text, and the PDF link.
* Saves the results to a CSV file (default: ca_ballot_measures.csv).

Dependencies (already in your pyproject.toml):
    requests, beautifulsoup4, pandas

Usage (from project root):
    python ca_sos_scraper.py -o data/ca_ballot_measures.csv

Notes:
    - The SOS site occasionally changes its markup. The CSS selectors used here
      work as of June 26 2025 but may need tweaks in the future.
    - Run the script periodically to keep your dataset current.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.sos.ca.gov/elections/ballot-measures/qualified-ballot-measures"


def fetch_html(url: str = BASE_URL) -> str:
    """Download page HTML, raising for HTTP errors."""
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.text


def parse_measures(html: str) -> pd.DataFrame:
    """Parse the SOS ballot‑measure page and return a tidy DataFrame."""
    soup = BeautifulSoup(html, "html.parser")

    records: list[dict[str, str]] = []
    current_election = None

    # The page structure is simple HTML: election headers are <h2>,
    # followed by one or more <p>/<li> elements that contain <a> links
    # to the PDF text of each measure.
    for tag in soup.find_all(["h2", "a"]):
        if tag.name == "h2":
            current_election = tag.get_text(strip=True)
            continue

        if tag.name == "a":
            href = tag.get("href", "")
            if not href.lower().endswith(".pdf"):
                # Skip non‑PDF links (e.g., internal navigation)
                continue

            # Clean up the link text (remove trailing “(PDF)” etc.)
            raw_text = tag.get_text(" ", strip=True)
            text = re.sub(r"\s*\(PDF\)\s*$", "", raw_text, flags=re.I)

            records.append(
                {
                    "election": current_election,
                    "measure_text": text,
                    "pdf_url": requests.compat.urljoin(BASE_URL, href),
                }
            )

    return pd.DataFrame.from_records(records)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scrape statewide ballot measures from the CA SOS website"
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("ca_ballot_measures.csv"),
        help="Path to output CSV (default: %(default)s)",
    )
    args = parser.parse_args()

    html = fetch_html()
    df = parse_measures(html)
    df.to_csv(args.output, index=False)
    print(f"✅ Saved {len(df):,} measures to {args.output.resolve()}")


if __name__ == "__main__":
    main()
