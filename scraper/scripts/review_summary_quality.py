#!/usr/bin/env python3
"""
Review quality of AI-generated summaries
Identifies potential issues to fix
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.operations import Database

def main():
    db = Database()
    conn = db.connect()

    print("=" * 60)
    print("SUMMARY QUALITY REVIEW")
    print("=" * 60)

    # 1. Find AI refusals
    cursor = conn.execute("""
        SELECT COUNT(*)
        FROM measures
        WHERE year >= 2020
          AND has_summary = 1
          AND (summary_text LIKE '%can''t help%'
               OR summary_text LIKE '%don''t have%'
               OR summary_text LIKE '%I''d be happy to%')
    """)
    refusals = cursor.fetchone()[0]
    print(f"\n❌ AI Refusals: {refusals}")

    # 2. Find very short summaries
    cursor = conn.execute("""
        SELECT COUNT(*)
        FROM measures
        WHERE year >= 2020
          AND has_summary = 1
          AND LENGTH(summary_text) < 100
    """)
    too_short = cursor.fetchone()[0]
    print(f"⚠️  Too Short (< 100 chars): {too_short}")

    # 3. Find very long summaries
    cursor = conn.execute("""
        SELECT COUNT(*)
        FROM measures
        WHERE year >= 2020
          AND has_summary = 1
          AND LENGTH(summary_text) > 1000
    """)
    too_long = cursor.fetchone()[0]
    print(f"⚠️  Too Long (> 1000 chars): {too_long}")

    # 4. Find good summaries
    cursor = conn.execute("""
        SELECT COUNT(*)
        FROM measures
        WHERE year >= 2020
          AND has_summary = 1
          AND LENGTH(summary_text) BETWEEN 200 AND 600
          AND summary_text NOT LIKE '%can''t help%'
          AND summary_text NOT LIKE '%don''t have%'
    """)
    good = cursor.fetchone()[0]
    print(f"✅ Good Quality (200-600 chars): {good}")

    # 5. Overall stats
    cursor = conn.execute("""
        SELECT COUNT(*),
               SUM(CASE WHEN has_summary = 1 THEN 1 ELSE 0 END)
        FROM measures
        WHERE year >= 2020
    """)
    total, with_summary = cursor.fetchone()
    print(f"\n📊 Total measures (2020+): {total}")
    print(f"   With summaries: {with_summary} ({with_summary/total*100:.1f}%)")
    print(f"   Without summaries: {total - with_summary}")

    # 6. Show examples of each problem
    print("\n" + "=" * 60)
    print("EXAMPLES OF ISSUES")
    print("=" * 60)

    print("\n❌ AI REFUSAL EXAMPLES:")
    cursor = conn.execute("""
        SELECT measure_id, year, county, summary_text
        FROM measures
        WHERE year >= 2020
          AND (summary_text LIKE '%can''t help%'
               OR summary_text LIKE '%don''t have%')
        LIMIT 3
    """)
    for row in cursor.fetchall():
        print(f"\n  {row[0]} ({row[1]}) - {row[2]}")
        print(f"  {row[3][:100]}...")

    print("\n⚠️  TOO LONG EXAMPLES:")
    cursor = conn.execute("""
        SELECT measure_id, year, county, LENGTH(summary_text)
        FROM measures
        WHERE year >= 2020
          AND LENGTH(summary_text) > 1000
        LIMIT 3
    """)
    for row in cursor.fetchall():
        print(f"  {row[0]} ({row[1]}) - {row[2]}: {row[3]} chars")

    print("\n✅ GOOD QUALITY EXAMPLES:")
    cursor = conn.execute("""
        SELECT measure_id, year, county, summary_text
        FROM measures
        WHERE year >= 2020
          AND LENGTH(summary_text) BETWEEN 200 AND 400
          AND summary_text NOT LIKE '%can''t help%'
        ORDER BY RANDOM()
        LIMIT 2
    """)
    for row in cursor.fetchall():
        print(f"\n  {row[0]} ({row[1]}) - {row[2]}")
        print(f"  {row[3]}")

    db.close()

if __name__ == '__main__':
    main()
