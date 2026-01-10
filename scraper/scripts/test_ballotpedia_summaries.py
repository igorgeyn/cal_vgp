#!/usr/bin/env python3
"""
Test Ballotpedia summary extraction on a small sample
"""
import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.scrapers.ballotpedia_counties import BallotpediaCountyScraper

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Test summary extraction on a few measures"""

    print("=" * 60)
    print("TEST: Ballotpedia Summary Extraction")
    print("=" * 60)

    scraper = BallotpediaCountyScraper()

    # Test on Alameda County (should have recent measures)
    print("\n📊 Testing Alameda County...")
    measures = scraper.scrape_county("Alameda")

    # Filter to 2020+ measures with summaries
    recent_with_summaries = [m for m in measures if m.year >= 2020 and m.has_summary]
    recent_without_summaries = [m for m in measures if m.year >= 2020 and not m.has_summary]

    print(f"\n✅ Results:")
    print(f"   Total measures found: {len(measures)}")
    print(f"   Recent measures (2020+): {len([m for m in measures if m.year >= 2020])}")
    print(f"   With summaries: {len(recent_with_summaries)}")
    print(f"   Without summaries: {len(recent_without_summaries)}")

    # Show examples
    if recent_with_summaries:
        print(f"\n📋 Sample Measures with Summaries:")
        for measure in recent_with_summaries[:3]:
            print(f"\n{'─' * 60}")
            print(f"Measure: {measure.measure_id} ({measure.year})")
            print(f"Title: {measure.title}")
            print(f"URL: {measure.source_url}")

            if measure.summary_title:
                print(f"\n✓ Summary Title ({len(measure.summary_title)} chars):")
                print(f"  {measure.summary_title[:200]}")

            if measure.ballot_question:
                print(f"\n✓ Ballot Question ({len(measure.ballot_question)} chars):")
                print(f"  {measure.ballot_question[:200]}")

            if measure.summary_text:
                print(f"\n✓ Summary Text ({len(measure.summary_text)} chars):")
                print(f"  {measure.summary_text[:300]}...")

    if recent_without_summaries:
        print(f"\n⚠️  Sample Measures WITHOUT Summaries:")
        for measure in recent_without_summaries[:3]:
            print(f"   - {measure.measure_id} ({measure.year}): {measure.title}")
            print(f"     URL: {measure.source_url}")

    print("\n" + "=" * 60)
    print("Test Complete!")
    print("=" * 60)


if __name__ == '__main__':
    main()
