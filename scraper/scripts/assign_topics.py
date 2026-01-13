#!/usr/bin/env python3
"""
Assign human-readable topic labels to measures based on cluster analysis.
Updates the database with the new topic assignments.
"""
import sys
import json
import sqlite3
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

DB_PATH = Path(__file__).parent.parent / "data" / "ballot_measures.db"
TOPIC_ANALYSIS_PATH = Path(__file__).parent.parent / "data" / "topic_analysis.json"

# Human-readable topic labels based on cluster analysis
TOPIC_LABELS = {
    0: "School Bonds",
    1: "District Taxes & Bonds",
    2: "Recalls & Appointments",
    3: "Utility Taxes",
    4: "School Facilities",
    5: "Infrastructure & Safety",
    6: "Water & Public Services",
    7: "Community Colleges",
    8: "Housing & School Bonds",
    9: "School Parcel Taxes",
    10: "School Governance",
    11: "City Charter Amendments",
    12: "Special District Taxes",
    13: "Land Use & Planning",
    14: "Local Ordinances",
    15: "City Offices",
    16: "Sales Tax & Services",
    17: "Hotel & Tourism Taxes",
    18: "Term Limits & Elections",
    19: "Cannabis Regulation"
}

def main():
    print("=" * 60)
    print("ASSIGNING TOPIC LABELS TO MEASURES")
    print("=" * 60)

    # Load topic analysis
    print("\n1. Loading topic analysis...")
    with open(TOPIC_ANALYSIS_PATH, 'r') as f:
        analysis = json.load(f)

    assignments = analysis['assignments']
    print(f"   Loaded {len(assignments)} topic assignments")

    # Connect to database
    print("\n2. Updating database...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Update each measure with its topic
    updated = 0
    for measure_id, data in assignments.items():
        cluster_id = data['cluster_id']
        topic_label = TOPIC_LABELS.get(cluster_id, f"Topic {cluster_id}")

        cursor.execute('''
            UPDATE measures
            SET topic_primary = ?
            WHERE measure_id = ?
        ''', (topic_label, measure_id))

        if cursor.rowcount > 0:
            updated += 1

    conn.commit()
    conn.close()

    print(f"   Updated {updated} measures with topic labels")

    # Show distribution
    print("\n3. Topic distribution:")
    topic_counts = {}
    for data in assignments.values():
        cluster_id = data['cluster_id']
        label = TOPIC_LABELS.get(cluster_id, f"Topic {cluster_id}")
        topic_counts[label] = topic_counts.get(label, 0) + 1

    for label, count in sorted(topic_counts.items(), key=lambda x: -x[1]):
        print(f"   {label}: {count}")

    print(f"\n{'=' * 60}")
    print("TOPIC ASSIGNMENT COMPLETE")
    print(f"{'=' * 60}")
    print(f"\nNext: Run 'make website' to rebuild with new topics")

if __name__ == '__main__':
    main()
