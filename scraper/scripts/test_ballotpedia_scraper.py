#!/usr/bin/env python3
"""
Test Ballotpedia county scraper on a single county
"""
import sys
import logging
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.scrapers.ballotpedia_counties import BallotpediaCountyScraper

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def main():
    print("=" * 70)
    print("Ballotpedia County Scraper - Test Run")
    print("=" * 70)

    scraper = BallotpediaCountyScraper()

    # Test on Los Angeles County
    print("\n🔍 Testing on Los Angeles County...")
    measures = scraper.scrape_county("Los Angeles")

    print(f"\n✅ Found {len(measures)} measures")

    # Show some examples
    print("\n📊 Sample measures:\n")
    for i, measure in enumerate(measures[:10], 1):
        status = "✓ PASSED" if measure.passed is True else "✗ FAILED" if measure.passed is False else "? PENDING"
        print(f"[{i}] {measure.year} - {measure.measure_id or 'NO_ID'}: {measure.title[:80]}...")
        print(f"    {status} | {measure.county} | {measure.election_type}")
        print()

    # Stats by year
    print("\n📈 Measures by Year:")
    year_counts = {}
    for measure in measures:
        year_counts[measure.year] = year_counts.get(measure.year, 0) + 1

    for year in sorted(year_counts.keys(), reverse=True):
        print(f"  {year}: {year_counts[year]} measures")

    print("\n" + "=" * 70)

if __name__ == '__main__':
    main()
