#!/usr/bin/env python3
"""
Pull ACS 5-year demographics for all 58 CA counties from the Census API
and write to scraper/data/ca_county_demographics.json.

Re-runnable annually when ACS publishes a new release.

Variables fetched:
    B11001_001E - Total households
    B19013_001E - Median household income (last 12 months, inflation-adjusted)
    B01003_001E - Total population

Usage:
    python scripts/ingest_ca_census.py
    python scripts/ingest_ca_census.py --year 2023   # specific ACS release
"""
import argparse
import json
import logging
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import DATA_DIR

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

OUT_PATH = DATA_DIR / "ca_county_demographics.json"
CA_FIPS = "06"


def normalize_county_name(census_name: str) -> str:
    """'Alameda County, California' -> 'ALAMEDA' to match the main DB."""
    name = census_name
    for suffix in (', California', ' County'):
        if name.endswith(suffix):
            name = name[:-len(suffix)]
    return name.strip().upper()


def fetch_acs(year: int) -> list:
    url = (
        f"https://api.census.gov/data/{year}/acs/acs5"
        f"?get=NAME,B11001_001E,B19013_001E,B01003_001E"
        f"&for=county:*&in=state:{CA_FIPS}"
    )
    logger.info("Fetching %s", url)
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read())


def to_int(s):
    if s is None:
        return None
    s = str(s).strip()
    if not s or s in ('-', '*', 'null'):
        return None
    try:
        v = int(s)
        # ACS uses negative sentinels for suppressed values
        return v if v >= 0 else None
    except ValueError:
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--year', type=int, default=2023,
                        help="ACS 5-year release year (default 2023)")
    args = parser.parse_args()

    rows = fetch_acs(args.year)
    header = rows[0]
    idx = {col: header.index(col) for col in
           ('NAME', 'B11001_001E', 'B19013_001E', 'B01003_001E')}

    counties = {}
    statewide_households = 0
    statewide_population = 0

    for r in rows[1:]:
        name = r[idx['NAME']]
        key = normalize_county_name(name)
        households = to_int(r[idx['B11001_001E']])
        median_income = to_int(r[idx['B19013_001E']])
        population = to_int(r[idx['B01003_001E']])

        counties[key] = {
            'name': name,
            'households': households,
            'median_household_income': median_income,
            'population': population,
        }
        if households:
            statewide_households += households
        if population:
            statewide_population += population

    payload = {
        'meta': {
            'source': 'US Census ACS 5-year',
            'release_year': args.year,
            'fetched_url_template': f'https://api.census.gov/data/{args.year}/acs/acs5',
            'variables': {
                'B11001_001E': 'Total households',
                'B19013_001E': 'Median household income (12-month, inflation-adjusted)',
                'B01003_001E': 'Total population',
            },
            'county_count': len(counties),
        },
        'statewide': {
            'name': 'California',
            'households': statewide_households,
            'population': statewide_population,
            # statewide median is not the sum of county medians; we'd need
            # state-level ACS pull to populate this honestly. Leave null.
            'median_household_income': None,
        },
        'counties': counties,
    }

    OUT_PATH.write_text(json.dumps(payload, indent=2))
    logger.info("Wrote %d counties to %s", len(counties), OUT_PATH)
    logger.info("Statewide: %d households, %d population",
                statewide_households, statewide_population)


if __name__ == '__main__':
    main()
