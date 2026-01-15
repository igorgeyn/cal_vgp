#!/usr/bin/env python3
"""
Initialize historical ballot measures database.
Run with --mock to generate mock data for testing.
Run with --csv PATH to import from ballot_measures_combined.csv
"""
import sys
import argparse
import logging
from pathlib import Path

# Fix Windows console encoding for emojis
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.historical_import import import_from_csv, generate_mock_data
from src.database.historical_operations import HistoricalDatabase
from src.config import DB_PATH


def main():
    parser = argparse.ArgumentParser(
        description='Initialize historical ballot measures database'
    )
    parser.add_argument(
        '--mock',
        action='store_true',
        help='Generate mock data for testing'
    )
    parser.add_argument(
        '--csv',
        type=Path,
        help='Path to ballot_measures_combined.csv'
    )
    parser.add_argument(
        '--db',
        type=Path,
        default=DB_PATH,
        help=f'Database path (default: {DB_PATH})'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output'
    )

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    print(f"Database path: {args.db}")

    # Ensure data directory exists
    args.db.parent.mkdir(parents=True, exist_ok=True)

    if args.mock:
        print("\n📊 Generating mock historical data...")
        stats = generate_mock_data(args.db)
        print(f"✅ Generated {stats['imported']} mock measures")

    elif args.csv:
        if not args.csv.exists():
            print(f"❌ CSV file not found: {args.csv}")
            sys.exit(1)

        print(f"\n📥 Importing from {args.csv}...")
        stats = import_from_csv(args.csv, args.db)
        print(f"✅ Imported {stats['imported']} measures")
        if stats.get('skipped_no_year', 0) > 0:
            print(f"⚠️  Skipped {stats['skipped_no_year']} rows with no year")
        if stats.get('errors', 0) > 0:
            print(f"❌ {stats['errors']} errors during import")

    else:
        # Try default CSV location
        default_csv = args.db.parent / 'raw' / 'ballot_measures_combined.csv'
        if default_csv.exists():
            print(f"\n📥 Found CSV at {default_csv}, importing...")
            stats = import_from_csv(default_csv, args.db)
            print(f"✅ Imported {stats['imported']} measures")
        else:
            print("\n⚠️  No CSV file found. Use --mock to generate test data.")
            print(f"   Or provide CSV path with --csv PATH")
            print(f"\n   Expected location: {default_csv}")
            sys.exit(1)

    # Print summary
    print("\n" + "="*50)
    print("📈 Topic Summary")
    print("="*50)

    with HistoricalDatabase(args.db) as db:
        topic_stats = db.get_all_topic_stats()
        for t in topic_stats:
            print(f"  {t['icon']} {t['label']}: {t['total_measures']} measures "
                  f"({t['pass_rate']}% pass rate)")

    print("\n✨ Done!")


if __name__ == '__main__':
    main()
