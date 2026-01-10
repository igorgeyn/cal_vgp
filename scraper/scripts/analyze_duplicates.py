#!/usr/bin/env python3
"""
Analyze duplicate URLs in the database
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.operations import Database

def main():
    db = Database()
    conn = db.connect()

    # Count total measures needing summaries
    cursor = conn.execute("""
        SELECT COUNT(*) as total
        FROM measures
        WHERE data_source = 'Ballotpedia'
          AND year >= 2020
          AND is_active = 1
          AND (has_summary = 0 OR has_summary IS NULL)
          AND source_url IS NOT NULL
          AND source_url != ''
    """)
    total = cursor.fetchone()[0]
    print(f'Total measures without summaries: {total}')

    # Count unique URLs among those
    cursor = conn.execute("""
        SELECT COUNT(DISTINCT source_url) as unique_urls
        FROM measures
        WHERE data_source = 'Ballotpedia'
          AND year >= 2020
          AND is_active = 1
          AND (has_summary = 0 OR has_summary IS NULL)
          AND source_url IS NOT NULL
          AND source_url != ''
    """)
    unique = cursor.fetchone()[0]
    print(f'Unique URLs among those: {unique}')
    print(f'Duplicate count: {total - unique} ({(total - unique) / total * 100:.1f}%)')

    # Show examples
    cursor = conn.execute("""
        SELECT source_url, COUNT(*) as count
        FROM measures
        WHERE data_source = 'Ballotpedia'
          AND year >= 2020
          AND is_active = 1
          AND (has_summary = 0 OR has_summary IS NULL)
          AND source_url IS NOT NULL
          AND source_url != ''
        GROUP BY source_url
        HAVING COUNT(*) > 1
        ORDER BY COUNT(*) DESC
        LIMIT 5
    """)

    print('\nMost duplicated URLs (top 5):')
    for row in cursor.fetchall():
        url = row[0]
        count = row[1]
        print(f'  {count}x: {url}')

    db.close()

if __name__ == '__main__':
    main()
