#!/usr/bin/env python3
"""
Test Ballotpedia statewide proposition scraper
"""
import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.scrapers.ballotpedia_statewide import BallotpediaStatewideScraper

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Test statewide proposition scraper"""

    print("=" * 60)
    print("TEST: Ballotpedia Statewide Proposition Scraper")
    print("=" * 60)

    scraper = BallotpediaStatewideScraper()

    # Test on 2024 (most recent year with complete data)
    print("\n📊 Testing 2024 propositions...")
    measures = scraper.scrape_year(2024)

    print(f"\n✅ Results:")
    print(f"   Total propositions found: {len(measures)}")

    if measures:
        # Show statistics
        with_summaries = [m for m in measures if m.has_summary]
        with_votes = [m for m in measures if m.yes_votes is not None]

        print(f"   With summaries: {len(with_summaries)}")
        print(f"   With vote data: {len(with_votes)}")

        # Show sample measures
        print(f"\n📋 Sample Propositions:")
        for measure in measures[:3]:
            print(f"\n{'─' * 60}")
            print(f"Measure: {measure.measure_id}")
            print(f"Year: {measure.year}")
            print(f"Title: {measure.title}")
            print(f"URL: {measure.source_url}")

            if measure.yes_votes:
                print(f"\n✓ Vote Data:")
                print(f"  Yes: {measure.yes_votes:,} ({measure.yes_votes/measure.total_votes*100:.1f}%)")
                print(f"  No: {measure.no_votes:,} ({measure.no_votes/measure.total_votes*100:.1f}%)")
                print(f"  Result: {'PASSED' if measure.passed else 'FAILED'}")

            if measure.summary_title:
                print(f"\n✓ Summary Title ({len(measure.summary_title)} chars):")
                print(f"  {measure.summary_title[:200]}")

            if measure.ballot_question:
                print(f"\n✓ Ballot Question ({len(measure.ballot_question)} chars):")
                print(f"  {measure.ballot_question[:300]}...")

    print("\n" + "=" * 60)
    print("Test Complete!")
    print("=" * 60)


if __name__ == '__main__':
    main()
