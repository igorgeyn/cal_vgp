#!/usr/bin/env python3
"""
Scrape all California counties from Ballotpedia and add to database
"""
import sys
import logging
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.scrapers.ballotpedia_counties import BallotpediaCountyScraper
from src.database.operations import Database
from src.database.utils import normalize_measure_data

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    print("=" * 70)
    print("Ballotpedia County Scraper - All 58 California Counties")
    print("=" * 70)

    # Initialize
    scraper = BallotpediaCountyScraper()

    print(f"\n📡 Scraping all {len(scraper.CALIFORNIA_COUNTIES)} counties...")
    print("⏱️  This will take a few minutes (1 second delay between counties)\n")

    # Scrape all counties
    all_measures = scraper.scrape_all_counties()

    print(f"\n✅ Scraped {len(all_measures)} total measures")

    # Add to database
    print(f"\n💾 Adding measures to database...")

    added = 0
    updated = 0
    skipped = 0

    # Use context manager to ensure commits
    with Database() as db:
        for i, measure in enumerate(all_measures, 1):
            if i % 100 == 0:
                print(f"  Processing: {i}/{len(all_measures)}...")

            try:
                # Insert measure - database will handle deduplication via fingerprinting
                measure_id = db.insert_measure(measure)

                if measure_id:
                    added += 1
                else:
                    # Likely a duplicate (fingerprint collision)
                    skipped += 1

            except Exception as e:
                # Check if it's a duplicate error
                if "UNIQUE constraint failed" in str(e) or "duplicate" in str(e).lower():
                    skipped += 1
                else:
                    logger.warning(f"Failed to add measure {measure.measure_id}: {e}")
                    skipped += 1

    print("\n" + "=" * 70)
    print("Summary:")
    print("=" * 70)
    print(f"✅ Added:   {added} new measures")
    print(f"🔄 Updated: {updated} existing measures")
    print(f"⏭️  Skipped: {skipped} measures")
    print(f"📊 Total:   {len(all_measures)} measures scraped")
    print("=" * 70)

    # Stats by county
    print("\n📈 Top 10 Counties by Measure Count:")
    county_counts = {}
    for measure in all_measures:
        county_counts[measure.county] = county_counts.get(measure.county, 0) + 1

    for county, count in sorted(county_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"  {county:20s}: {count:3d} measures")


if __name__ == '__main__':
    main()
