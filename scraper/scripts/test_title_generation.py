#!/usr/bin/env python3
"""
Test title generation on a small batch
"""
import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.operations import Database
from src.utils import TitleGenerator

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Generate titles for a test batch"""

    TEST_BATCH_SIZE = 50

    print("=" * 60)
    print(f"TEST: Generate {TEST_BATCH_SIZE} Titles")
    print("=" * 60)

    # Initialize
    db = Database()
    title_gen = TitleGenerator(database=db)

    print(f"\n✅ Using provider: {title_gen.active_provider}")

    # Get measures that need titles
    measures = db.get_all_active_measures()
    needs_title = []

    for measure in measures:
        title = measure.title or ''
        if title_gen.should_generate_title(title) and not measure.generated_title:
            needs_title.append(measure)
            if len(needs_title) >= TEST_BATCH_SIZE:
                break

    print(f"\n📊 Selected {len(needs_title)} measures for test batch")
    print(f"⏱️  Estimated time: ~{len(needs_title) * 3} seconds\n")

    response = input("Proceed with test? (y/n): ")
    if response.lower() != 'y':
        print("Cancelled.")
        return

    # Generate titles
    print("\n🤖 Generating titles...\n")
    generated = 0
    failed = 0

    for i, measure in enumerate(needs_title, 1):
        title = measure.title or measure.measure_text or ''
        measure_id = measure.measure_id or f"measure_{i}"

        print(f"[{i}/{len(needs_title)}] {measure_id}")

        new_title = title_gen.generate_title(title, measure_id)

        if new_title:
            print(f"  ✓ {new_title}")
            generated += 1

            # Save to database immediately
            try:
                conn = db.connect()
                conn.execute("""
                    UPDATE measures
                    SET generated_title = ?,
                        original_title = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (new_title, title, measure.id))
                conn.commit()
            except Exception as e:
                logger.error(f"Failed to save to database: {e}")
        else:
            print(f"  ✗ Failed")
            failed += 1

    print("\n" + "=" * 60)
    print(f"✅ Test Complete!")
    print(f"   Generated: {generated}/{len(needs_title)}")
    print(f"   Failed: {failed}/{len(needs_title)}")
    print(f"   Success rate: {generated/len(needs_title)*100:.1f}%")
    print("=" * 60)

    if generated > 0:
        print("\n✓ Titles saved directly to database")
        print("✓ Run 'make website' to see them on the site")

    db.close()


if __name__ == '__main__':
    main()
