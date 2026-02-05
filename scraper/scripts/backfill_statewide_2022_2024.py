#!/usr/bin/env python3
"""
Backfill statewide ballot propositions for 2022 and 2024 from Ballotpedia.
"""
import sys
import logging
import argparse
from pathlib import Path
from typing import List

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.scrapers.ballotpedia_statewide import BallotpediaStatewideScraper
from src.database.operations import Database
from src.database.utils import normalize_measure_data
from src.database.models import BallotMeasure


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def backfill(years: List[int]) -> None:
    scraper = BallotpediaStatewideScraper()
    scraped = []

    for year in years:
        scraped.extend(scraper.scrape_year(year))

    logger.info(f"Scraped {len(scraped)} statewide measures for {years}")

    inserted = 0
    updated = 0
    skipped = 0
    errors = 0

    with Database() as db:
        conn = db.connect()
        for measure in scraped:
            try:
                data = normalize_measure_data(measure.to_dict())
                data['county'] = 'Statewide'
                data['state'] = 'CA'

                measure_id = data.get('measure_id')
                year = data.get('year')
                if not measure_id or not year:
                    skipped += 1
                    logger.warning(f"Skipping measure without ID/year: {data.get('title')}")
                    continue

                existing = conn.execute(
                    "SELECT id FROM measures WHERE measure_id = ? AND year = ? AND county = 'Statewide' LIMIT 1",
                    (measure_id, year)
                ).fetchone()

                if existing:
                    db.update_measure(existing['id'], data)
                    updated += 1
                else:
                    db.insert_measure(BallotMeasure(**data))
                    inserted += 1

            except Exception as exc:
                errors += 1
                logger.error(f"Error saving measure {getattr(measure, 'measure_id', None)} ({getattr(measure, 'year', None)}): {exc}")

    logger.info("Backfill complete:")
    logger.info(f"  Inserted: {inserted}")
    logger.info(f"  Updated: {updated}")
    logger.info(f"  Skipped: {skipped}")
    logger.info(f"  Errors: {errors}")


def main() -> int:
    parser = argparse.ArgumentParser(description='Backfill 2022/2024 statewide propositions from Ballotpedia')
    parser.add_argument(
        '--years',
        nargs='+',
        type=int,
        default=[2022, 2024],
        help='Years to backfill (default: 2022 2024)'
    )

    args = parser.parse_args()
    backfill(args.years)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
