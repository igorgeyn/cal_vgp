#!/usr/bin/env python3
"""
Fix data quality issues identified by audit.

Issues addressed:
1. 3 active duplicates (is_active=1 AND is_duplicate=1)
2. has_summary flag inconsistency (8,906 rows)
3. 7 incorrect passed values at 50% threshold
4. Election date format normalization
5. Bad summary for id 11434
6. Threshold edge cases investigation

Usage:
    python scripts/fix_data_quality_issues.py [--dry-run]
"""

import sqlite3
import argparse
from pathlib import Path
from datetime import datetime
import re

DB_PATH = Path(__file__).parent.parent / "data" / "ballot_measures.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def fix_active_duplicates(conn, dry_run=False):
    """Fix 3 records that are marked as duplicate but still active."""
    print("\n1. FIXING ACTIVE DUPLICATES")
    print("-" * 40)

    cursor = conn.execute("""
        SELECT id, measure_id, county, year, master_id
        FROM measures
        WHERE is_active = 1 AND is_duplicate = 1
    """)
    rows = cursor.fetchall()

    print(f"Found {len(rows)} active duplicates:")
    for row in rows:
        print(f"  ID {row['id']}: {row['measure_id']} ({row['county']}, {row['year']}) -> master {row['master_id']}")

    if not dry_run and rows:
        conn.execute("""
            UPDATE measures
            SET is_active = 0
            WHERE is_active = 1 AND is_duplicate = 1
        """)
        print(f"Fixed: Set is_active=0 for {len(rows)} records")
    elif dry_run:
        print("DRY RUN: Would set is_active=0")

    return len(rows)


def fix_has_summary_flag(conn, dry_run=False):
    """Fix has_summary flag to match actual summary_text presence."""
    print("\n2. FIXING has_summary FLAG")
    print("-" * 40)

    # Count mismatches
    cursor = conn.execute("""
        SELECT
            SUM(CASE WHEN has_summary = 0 AND summary_text IS NOT NULL AND summary_text != '' THEN 1 ELSE 0 END) as should_be_1,
            SUM(CASE WHEN has_summary = 1 AND (summary_text IS NULL OR summary_text = '') THEN 1 ELSE 0 END) as should_be_0
        FROM measures
        WHERE is_active = 1
    """)
    row = cursor.fetchone()
    should_be_1 = row['should_be_1'] or 0
    should_be_0 = row['should_be_0'] or 0

    print(f"has_summary=0 but has text: {should_be_1}")
    print(f"has_summary=1 but no text: {should_be_0}")

    if not dry_run:
        # Fix has_summary=0 when text exists
        if should_be_1 > 0:
            conn.execute("""
                UPDATE measures
                SET has_summary = 1
                WHERE is_active = 1
                  AND has_summary = 0
                  AND summary_text IS NOT NULL
                  AND summary_text != ''
            """)
            print(f"Fixed: Set has_summary=1 for {should_be_1} records")

        # Fix has_summary=1 when no text
        if should_be_0 > 0:
            conn.execute("""
                UPDATE measures
                SET has_summary = 0
                WHERE is_active = 1
                  AND has_summary = 1
                  AND (summary_text IS NULL OR summary_text = '')
            """)
            print(f"Fixed: Set has_summary=0 for {should_be_0} records")
    else:
        print("DRY RUN: Would update has_summary flags")

    return should_be_1 + should_be_0


def fix_incorrect_passed_50pct(conn, dry_run=False):
    """Fix passed=0 when percent_yes >= 50 at 50% threshold."""
    print("\n3. FIXING INCORRECT passed VALUES (50% threshold)")
    print("-" * 40)

    cursor = conn.execute("""
        SELECT id, measure_id, county, year, percent_yes, passed, vote_threshold
        FROM measures
        WHERE is_active = 1
          AND vote_threshold = '50%'
          AND passed = 0
          AND percent_yes >= 50
    """)
    rows = cursor.fetchall()

    print(f"Found {len(rows)} records with passed=0 but percent_yes >= 50:")
    for row in rows:
        print(f"  ID {row['id']}: {row['percent_yes']:.1f}% yes, marked as failed")

    if not dry_run and rows:
        # For exactly 50%, it's a tie - check if it should pass
        # For > 50%, it definitely passed
        conn.execute("""
            UPDATE measures
            SET passed = 1
            WHERE is_active = 1
              AND vote_threshold = '50%'
              AND passed = 0
              AND percent_yes > 50
        """)
        # Check how many had exactly 50%
        cursor = conn.execute("""
            SELECT id, percent_yes FROM measures
            WHERE is_active = 1 AND vote_threshold = '50%' AND passed = 0 AND percent_yes = 50
        """)
        ties = cursor.fetchall()
        print(f"Fixed: Set passed=1 for records with >50%")
        if ties:
            print(f"Note: {len(ties)} records have exactly 50% - ties may fail, leaving as is")
    elif dry_run:
        print("DRY RUN: Would set passed=1 for records with >50%")

    return len(rows)


def investigate_threshold_edge_cases(conn):
    """Investigate passed=1 with percent_yes < threshold."""
    print("\n4. INVESTIGATING THRESHOLD EDGE CASES")
    print("-" * 40)

    # 66.67% threshold edge cases
    cursor = conn.execute("""
        SELECT id, measure_id, county, year, percent_yes, passed, vote_threshold
        FROM measures
        WHERE is_active = 1
          AND vote_threshold = '66.67%'
          AND passed = 1
          AND percent_yes < 66.67
        ORDER BY percent_yes
    """)
    rows = cursor.fetchall()

    print(f"Found {len(rows)} records passing at <66.67% with 66.67% threshold:")
    for row in rows:
        pct = row['percent_yes']
        # Check if it's a rounding issue (66.6666... rounds to 66.67)
        is_edge = abs(pct - 66.6666666666667) < 0.01
        status = "(edge case - 66.666...)" if is_edge else "(DATA ERROR?)"
        print(f"  ID {row['id']}: {pct:.10f}% {status}")

    # Count actual errors vs edge cases
    errors = [r for r in rows if r['percent_yes'] < 66.0]
    print(f"\nActual errors (< 66%): {len(errors)}")
    for row in errors:
        print(f"  ID {row['id']}: {row['measure_id']} ({row['county']}, {row['year']}) - {row['percent_yes']:.2f}%")

    return len(errors)


def normalize_election_dates(conn, dry_run=False):
    """Normalize election_date to ISO format (YYYY-MM-DD)."""
    print("\n5. NORMALIZING ELECTION DATES")
    print("-" * 40)

    # Find non-ISO dates
    cursor = conn.execute("""
        SELECT DISTINCT election_date
        FROM measures
        WHERE election_date IS NOT NULL
          AND election_date NOT LIKE '____-__-__'
          AND election_date != ''
    """)
    formats = cursor.fetchall()

    print(f"Found {len(formats)} non-ISO date formats:")
    for row in formats:
        print(f"  '{row['election_date']}'")

    if not dry_run:
        # Fix "Month Day, Year" format (e.g., "November 3, 2026")
        cursor = conn.execute("""
            SELECT id, election_date FROM measures
            WHERE election_date LIKE '%,%'
        """)
        text_dates = cursor.fetchall()

        months = {
            'January': '01', 'February': '02', 'March': '03', 'April': '04',
            'May': '05', 'June': '06', 'July': '07', 'August': '08',
            'September': '09', 'October': '10', 'November': '11', 'December': '12'
        }

        for row in text_dates:
            date_str = row['election_date']
            # Parse "November 3, 2026"
            match = re.match(r'(\w+)\s+(\d+),\s+(\d{4})', date_str)
            if match:
                month_name, day, year = match.groups()
                month = months.get(month_name)
                if month:
                    iso_date = f"{year}-{month}-{day.zfill(2)}"
                    conn.execute("UPDATE measures SET election_date = ? WHERE id = ?",
                                (iso_date, row['id']))

        # Fix ISO with time (e.g., "2025-11-04T00:00:00")
        conn.execute("""
            UPDATE measures
            SET election_date = SUBSTR(election_date, 1, 10)
            WHERE election_date LIKE '____-__-__T%'
        """)

        print("Fixed: Normalized date formats to YYYY-MM-DD")
    else:
        print("DRY RUN: Would normalize dates")

    return len(formats)


def fix_bad_summary(conn, dry_run=False):
    """Fix the bad summary for id 11434."""
    print("\n6. FIXING BAD SUMMARY (ID 11434)")
    print("-" * 40)

    cursor = conn.execute("""
        SELECT id, measure_id, county, year, title, summary_text
        FROM measures WHERE id = 11434
    """)
    row = cursor.fetchone()

    if row:
        print(f"Current summary: '{row['summary_text']}'")
        print(f"Title: '{row['title'][:200]}...'")

        # This is a placeholder summary, need to regenerate
        # For now, mark it as needing regeneration by clearing summary
        if not dry_run:
            conn.execute("""
                UPDATE measures
                SET summary_text = NULL, has_summary = 0
                WHERE id = 11434
            """)
            print("Fixed: Cleared bad summary (will need regeneration)")
        else:
            print("DRY RUN: Would clear bad summary")
    else:
        print("ID 11434 not found")

    return 1 if row else 0


def main():
    parser = argparse.ArgumentParser(description="Fix data quality issues")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without making changes")
    args = parser.parse_args()

    conn = get_connection()

    print("=" * 60)
    print("DATA QUALITY FIX SCRIPT")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    print("=" * 60)

    total_fixes = 0

    try:
        # Run fixes
        total_fixes += fix_active_duplicates(conn, args.dry_run)
        total_fixes += fix_has_summary_flag(conn, args.dry_run)
        total_fixes += fix_incorrect_passed_50pct(conn, args.dry_run)
        investigate_threshold_edge_cases(conn)  # Just investigation, no fix
        total_fixes += normalize_election_dates(conn, args.dry_run)
        total_fixes += fix_bad_summary(conn, args.dry_run)

        if not args.dry_run:
            conn.commit()
            print("\n" + "=" * 60)
            print(f"COMPLETE: {total_fixes} issues addressed")
            print("=" * 60)
        else:
            print("\n" + "=" * 60)
            print(f"DRY RUN COMPLETE: {total_fixes} issues would be addressed")
            print("=" * 60)

    except Exception as e:
        conn.rollback()
        print(f"\nERROR: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
