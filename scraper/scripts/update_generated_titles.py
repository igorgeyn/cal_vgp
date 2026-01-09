#!/usr/bin/env python3
"""
Update database with generated titles from cache
Run this after generating titles to persist them to the database
"""
import sys
import logging
from pathlib import Path
import json

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.operations import Database
from src.utils import TitleGenerator

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Update database with generated titles from cache"""

    print("=" * 60)
    print("Update Database with Generated Titles")
    print("=" * 60)

    # Initialize
    db = Database()
    title_gen = TitleGenerator()

    # Load cache
    if not title_gen.cache_path.exists():
        print("\n⚠️  No title cache found at:", title_gen.cache_path)
        print("Run 'python scripts/generate_titles.py' first to generate titles.")
        return

    print(f"\n📂 Loading cache from: {title_gen.cache_path}")
    print(f"   Found {len(title_gen.cache)} cached titles\n")

    # Get all measures
    conn = db.connect()
    cursor = conn.execute("SELECT id, measure_id, title FROM measures WHERE is_active = 1")
    measures = cursor.fetchall()

    print(f"📊 Processing {len(measures)} measures from database...\n")

    updated = 0
    skipped = 0

    for row in measures:
        measure_id = row['measure_id']
        title = row['title'] or ''
        db_id = row['id']

        # Check if title needs generation
        if not title_gen.should_generate_title(title):
            skipped += 1
            continue

        # Look for generated title in cache
        cache_key = f"{measure_id}_{title[:100]}" if measure_id else title[:100]

        if cache_key in title_gen.cache:
            generated_title = title_gen.cache[cache_key]

            # Update database
            try:
                conn.execute("""
                    UPDATE measures
                    SET generated_title = ?,
                        original_title = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (generated_title, title, db_id))

                print(f"✓ [{measure_id or db_id}] {generated_title}")
                updated += 1

            except Exception as e:
                logger.error(f"Failed to update measure {db_id}: {e}")

    # Commit changes
    conn.commit()
    db.close()

    print("\n" + "=" * 60)
    print(f"✅ Updated {updated} measures with generated titles")
    print(f"⏭️  Skipped {skipped} measures (titles don't need generation)")
    print("=" * 60)


if __name__ == '__main__':
    main()
