#!/usr/bin/env python3
"""
Update existing Ballotpedia measures with summaries
Re-scrapes measure pages to extract summary information
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
    """Update Ballotpedia measures with summaries"""

    print("=" * 60)
    print("Update Ballotpedia Measures with Summaries")
    print("=" * 60)

    # Initialize
    db = Database()
    scraper = BallotpediaCountyScraper()

    # Get all Ballotpedia measures from 2020+ without summaries
    conn = db.connect()
    cursor = conn.execute("""
        SELECT id, measure_id, year, county, source_url
        FROM measures
        WHERE data_source = 'Ballotpedia'
          AND year >= 2020
          AND is_active = 1
          AND (has_summary = 0 OR has_summary IS NULL)
          AND source_url IS NOT NULL
          AND source_url != ''
        ORDER BY year DESC, county
    """)

    measures_to_update = cursor.fetchall()
    total = len(measures_to_update)

    print(f"\n📊 Found {total} Ballotpedia measures (2020+) needing summaries")

    if total == 0:
        print("\n✅ All Ballotpedia measures already have summaries!")
        return

    # Ask for confirmation
    response = input(f"\nThis will fetch summaries for {total} measures. Proceed? (y/n): ")
    if response.lower() != 'y':
        print("Cancelled.")
        return

    # Process measures
    print(f"\n🔄 Fetching summaries...\n")
    updated = 0
    failed = 0
    skipped = 0

    for i, row in enumerate(measures_to_update, 1):
        db_id = row['id']
        measure_id = row['measure_id']
        year = row['year']
        county = row['county']
        url = row['source_url']

        print(f"[{i}/{total}] {measure_id or 'N/A'} ({year}) {county}")

        try:
            # Fetch summary
            summary_data = scraper._fetch_measure_summary(url)

            if summary_data:
                ballot_question = summary_data.get('ballot_question')
                summary_title = summary_data.get('summary_title')
                summary_text = summary_data.get('summary_text')

                # Update database
                conn.execute("""
                    UPDATE measures
                    SET ballot_question = ?,
                        summary_title = ?,
                        summary_text = ?,
                        has_summary = 1,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (ballot_question, summary_title, summary_text, db_id))

                print(f"  ✓ Updated with summary ({len(summary_text or '')} chars)")
                updated += 1

                # Commit every 10 measures
                if updated % 10 == 0:
                    conn.commit()
            else:
                print(f"  ⚠️  No summary found")
                skipped += 1

        except Exception as e:
            logger.error(f"Failed to update measure {db_id}: {e}")
            failed += 1

        # Be nice to Ballotpedia servers - use longer delays to avoid rate limiting
        if i % 10 == 0:
            time.sleep(5)  # Longer pause every 10 measures
        else:
            time.sleep(3)  # 3 seconds between each request

    # Final commit
    conn.commit()
    db.close()

    print("\n" + "=" * 60)
    print("✅ Summary Update Complete!")
    print(f"   Updated: {updated}/{total}")
    print(f"   Skipped (no summary): {skipped}/{total}")
    print(f"   Failed: {failed}/{total}")
    print("=" * 60)
    print("\n📋 Next steps:")
    print("  Run 'make website' to rebuild website with new summaries")


if __name__ == '__main__':
    main()
