#!/usr/bin/env python3
"""
Diagnose duplicate fingerprints in ballot measures database
"""

import sqlite3
from collections import defaultdict
from pathlib import Path

def diagnose_duplicates():
    """Analyze duplicate fingerprints in the database"""
    db_path = 'data/ballot_measures.db'
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    print("🔍 Analyzing Duplicate Fingerprints")
    print("=" * 60)
    
    # Find duplicate fingerprints
    cursor = conn.execute("""
        SELECT fingerprint, COUNT(*) as count
        FROM measures
        WHERE fingerprint IS NOT NULL
        GROUP BY fingerprint
        HAVING COUNT(*) > 1
        ORDER BY count DESC
    """)
    
    duplicates = cursor.fetchall()
    print(f"\n📊 Found {len(duplicates)} duplicate fingerprints")
    
    # Analyze top duplicates
    print("\n🔝 Top 10 duplicate fingerprints:")
    for i, dup in enumerate(duplicates[:10]):
        print(f"\n{i+1}. Fingerprint: {dup['fingerprint']}")
        print(f"   Count: {dup['count']} duplicates")
        
        # Get details of these duplicates
        cursor2 = conn.execute("""
            SELECT id, year, title, data_source, county, measure_letter, 
                   ballot_question, created_at
            FROM measures
            WHERE fingerprint = ?
            ORDER BY created_at
        """, (dup['fingerprint'],))
        
        for j, record in enumerate(cursor2):
            print(f"   #{j+1}: ID={record['id']}, Source={record['data_source']}")
            print(f"        Title: {record['title'][:60]}..." if record['title'] else "        No title")
            print(f"        Created: {record['created_at']}")
    
    # Analyze fingerprint patterns
    print("\n📈 Fingerprint Pattern Analysis:")
    
    # Count by measure_id component
    unknown_count = conn.execute("""
        SELECT COUNT(*) FROM measures 
        WHERE fingerprint LIKE '%|UNKNOWN|%'
    """).fetchone()[0]
    
    print(f"   Fingerprints with UNKNOWN measure_id: {unknown_count}")
    
    # Analyze by source
    print("\n📊 Duplicates by Source:")
    cursor = conn.execute("""
        SELECT data_source, COUNT(*) as total,
               SUM(CASE WHEN fingerprint IN (
                   SELECT fingerprint FROM measures 
                   GROUP BY fingerprint HAVING COUNT(*) > 1
               ) THEN 1 ELSE 0 END) as with_duplicates
        FROM measures
        WHERE fingerprint IS NOT NULL
        GROUP BY data_source
    """)
    
    for row in cursor:
        pct = (row['with_duplicates'] / row['total'] * 100) if row['total'] > 0 else 0
        print(f"   {row['data_source']}: {row['with_duplicates']}/{row['total']} ({pct:.1f}%) have duplicates")
    
    conn.close()

if __name__ == "__main__":
    diagnose_duplicates()