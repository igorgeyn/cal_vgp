#!/usr/bin/env python3
"""
Complete workflow for adding summaries to ballot measures
Combines web scraping (Ballotpedia) with AI generation (Ollama) as fallback
"""
import sys
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.operations import Database


def count_measures_by_summary_status():
    """Count measures with/without summaries"""
    db = Database()
    conn = db.connect()

    cursor = conn.execute("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN has_summary = 1 THEN 1 ELSE 0 END) as with_summary,
            SUM(CASE WHEN has_summary = 0 OR has_summary IS NULL THEN 1 ELSE 0 END) as without_summary
        FROM measures
        WHERE year >= 2020 AND is_active = 1
    """)

    result = cursor.fetchone()
    db.close()

    return {
        'total': result[0],
        'with_summary': result[1],
        'without_summary': result[2]
    }


def run_script(script_name, description):
    """Run a Python script and return success status"""
    print(f"\n{'=' * 60}")
    print(f"Step: {description}")
    print('=' * 60)

    script_path = Path(__file__).parent / script_name
    if not script_path.exists():
        print(f"❌ Error: {script_name} not found")
        return False

    try:
        # Run the script
        result = subprocess.run(
            [sys.executable, str(script_path)],
            check=False,
            text=True
        )

        if result.returncode == 0:
            print(f"✓ {description} completed successfully")
            return True
        else:
            print(f"⚠️  {description} completed with warnings")
            return True  # Continue even with warnings

    except Exception as e:
        print(f"❌ Error running {script_name}: {e}")
        return False


def main():
    """Complete summary workflow"""

    print("=" * 60)
    print("COMPLETE SUMMARY WORKFLOW")
    print("=" * 60)
    print()
    print("This workflow will:")
    print("  1. Scrape summaries from Ballotpedia (high quality)")
    print("  2. Generate AI summaries for remaining measures (fallback)")
    print("  3. Show final statistics")
    print()

    # Show initial status
    stats = count_measures_by_summary_status()
    print(f"📊 Current Status (2020+):")
    print(f"   Total measures: {stats['total']}")
    print(f"   With summaries: {stats['with_summary']} ({stats['with_summary']/stats['total']*100:.1f}%)")
    print(f"   Need summaries: {stats['without_summary']} ({stats['without_summary']/stats['total']*100:.1f}%)")

    if stats['without_summary'] == 0:
        print("\n✅ All measures already have summaries!")
        return

    print("\n" + "─" * 60)
    response = input("Proceed with workflow? (y/n): ")
    if response.lower() != 'y':
        print("Cancelled.")
        return

    # Step 1: Ballotpedia scraping (optimized, deduplicated)
    print("\n\n")
    print("PHASE 1: Ballotpedia Summary Scraping")
    print("─" * 60)
    print("This will fetch high-quality summaries from Ballotpedia.")
    print("Estimated time: ~14 minutes for ~286 unique URLs")

    response = input("\nRun Ballotpedia scraper? (y/n): ")
    if response.lower() == 'y':
        success = run_script(
            'update_ballotpedia_summaries_deduped.py',
            'Ballotpedia Summary Scraping'
        )
        if not success:
            print("\n⚠️  Warning: Ballotpedia scraping had issues. Continue anyway? (y/n)")
            if input().lower() != 'y':
                return

        # Show updated stats
        stats = count_measures_by_summary_status()
        print(f"\n📊 After Ballotpedia scraping:")
        print(f"   With summaries: {stats['with_summary']} ({stats['with_summary']/stats['total']*100:.1f}%)")
        print(f"   Still need: {stats['without_summary']} ({stats['without_summary']/stats['total']*100:.1f}%)")
    else:
        print("Skipping Ballotpedia scraping...")

    # Step 2: AI summary generation for remaining measures
    if stats['without_summary'] > 0:
        print("\n\n")
        print("PHASE 2: AI Summary Generation (Fallback)")
        print("─" * 60)
        print(f"This will generate AI summaries for the remaining {stats['without_summary']} measures.")
        print("Uses Ollama (local, free) to create summaries from titles/descriptions.")

        response = input("\nRun AI summary generator? (y/n): ")
        if response.lower() == 'y':
            success = run_script(
                'generate_ai_summaries.py',
                'AI Summary Generation'
            )

            if success:
                # Show final stats
                stats = count_measures_by_summary_status()
                print(f"\n📊 After AI generation:")
                print(f"   With summaries: {stats['with_summary']} ({stats['with_summary']/stats['total']*100:.1f}%)")
                print(f"   Still need: {stats['without_summary']} ({stats['without_summary']/stats['total']*100:.1f}%)")
        else:
            print("Skipping AI generation...")

    # Final summary
    print("\n\n")
    print("=" * 60)
    print("WORKFLOW COMPLETE")
    print("=" * 60)

    stats = count_measures_by_summary_status()
    print(f"\n📊 Final Statistics (2020+):")
    print(f"   Total measures: {stats['total']}")
    print(f"   With summaries: {stats['with_summary']} ({stats['with_summary']/stats['total']*100:.1f}%)")
    print(f"   Coverage: {stats['with_summary']/stats['total']*100:.1f}%")

    if stats['with_summary'] == stats['total']:
        print("\n✅ SUCCESS: 100% of measures now have summaries!")
    else:
        print(f"\n⚠️  {stats['without_summary']} measures still need summaries")

    print("\n📋 Next Steps:")
    print("  1. Run 'make website' to rebuild with new summaries")
    print("  2. Check the website to verify summary display")
    print("  3. Review AI-generated summaries for quality")

    print("\n" + "=" * 60)


if __name__ == '__main__':
    main()
