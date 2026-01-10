#!/usr/bin/env python3
"""
Update existing Ballotpedia measures with summaries
Optimized version that deduplicates URLs to avoid redundant fetches
"""
import sys
import logging
from pathlib import Path
import time

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.operations import Database
from src.scrapers.ballotpedia_counties import BallotpediaCountyScraper

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Update Ballotpedia measures with summaries (deduplicated)"""

    print("=" * 60)
    print("Update Ballotpedia Measures with Summaries (Optimized)")
    print("=" * 60)

    # Initialize
    db = Database()
    scraper = BallotpediaCountyScraper()

    # Get unique URLs that need summaries (2020+)
    conn = db.connect()
    cursor = conn.execute("""
        SELECT DISTINCT source_url
        FROM measures
        WHERE data_source = 'Ballotpedia'
          AND year >= 2020
          AND is_active = 1
          AND (has_summary = 0 OR has_summary IS NULL)
          AND source_url IS NOT NULL
          AND source_url != ''
        ORDER BY source_url
    """)

    unique_urls = [row[0] for row in cursor.fetchall()]
    total = len(unique_urls)

    print(f"\n📊 Found {total} unique URLs needing summaries")

    # Count total measures affected
    cursor = conn.execute("""
        SELECT COUNT(*)
        FROM measures
        WHERE data_source = 'Ballotpedia'
          AND year >= 2020
          AND is_active = 1
          AND (has_summary = 0 OR has_summary IS NULL)
          AND source_url IS NOT NULL
          AND source_url != ''
    """)
    total_measures = cursor.fetchone()[0]
    print(f"   This will update {total_measures} total measures")
    print(f"   Efficiency: {total_measures - total} duplicates avoided ({(total_measures - total) / total_measures * 100:.1f}% reduction)")

    if total == 0:
        print("\n✅ All Ballotpedia measures already have summaries!")
        return

    # Ask for confirmation
    print(f"\n⏱️  Estimated time: {total * 3 / 60:.1f} minutes at 3 seconds/URL")
    response = input(f"\nFetch summaries for {total} unique URLs? (y/n): ")
    if response.lower() != 'y':
        print("Cancelled.")
        return

    # Process unique URLs
    print(f"\n🔄 Fetching summaries...\n")
    updated_urls = 0
    failed_urls = 0
    skipped_urls = 0

    for i, url in enumerate(unique_urls, 1):
        print(f"[{i}/{total}] Fetching: {url[:80]}...")

        try:
            # Fetch summary once for this URL
            summary_data = scraper._fetch_measure_summary(url)

            if summary_data:
                ballot_question = summary_data.get('ballot_question')
                summary_title = summary_data.get('summary_title')
                summary_text = summary_data.get('summary_text')

                # Update ALL measures with this URL
                result = conn.execute("""
                    UPDATE measures
                    SET ballot_question = ?,
                        summary_title = ?,
                        summary_text = ?,
                        has_summary = 1,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE data_source = 'Ballotpedia'
                      AND year >= 2020
                      AND is_active = 1
                      AND source_url = ?
                      AND (has_summary = 0 OR has_summary IS NULL)
                """, (ballot_question, summary_title, summary_text, url))

                rows_updated = result.rowcount
                print(f"  ✓ Updated {rows_updated} measure(s) ({len(summary_text or '')} chars)")
                updated_urls += 1

                # Commit every 10 URLs
                if updated_urls % 10 == 0:
                    conn.commit()
            else:
                print(f"  ⚠️  No summary found")
                skipped_urls += 1

        except Exception as e:
            logger.error(f"Failed to fetch {url}: {e}")
            failed_urls += 1

        # Be nice to Ballotpedia servers - use longer delays to avoid rate limiting
        if i % 10 == 0:
            time.sleep(5)  # Longer pause every 10 URLs
        else:
            time.sleep(3)  # 3 seconds between each request

    # Final commit
    conn.commit()

    # Count how many measures actually got updated
    cursor = conn.execute("""
        SELECT COUNT(*)
        FROM measures
        WHERE data_source = 'Ballotpedia'
          AND year >= 2020
          AND is_active = 1
          AND has_summary = 1
    """)
    total_with_summaries = cursor.fetchone()[0]

    db.close()

    print("\n" + "=" * 60)
    print("✅ Summary Update Complete!")
    print(f"   Unique URLs processed: {total}")
    print(f"   Successfully fetched: {updated_urls}/{total}")
    print(f"   Skipped (no summary): {skipped_urls}/{total}")
    print(f"   Failed: {failed_urls}/{total}")
    print(f"\n   Total measures with summaries: {total_with_summaries}")
    print("=" * 60)
    print("\n📋 Next steps:")
    print("  Run 'make website' to rebuild website with new summaries")


if __name__ == '__main__':
    main()
