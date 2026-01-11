#!/usr/bin/env python3
"""
Export ballot measures data in various formats
"""
import sys
import csv
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.operations import Database

def export_csv(output_file=None, year_filter=None, with_summaries_only=False):
    """Export to CSV format"""
    db = Database()
    conn = db.connect()

    query = '''
        SELECT
            measure_id,
            year,
            county,
            jurisdiction,
            title,
            summary_title,
            summary_text,
            LENGTH(summary_text) as summary_length,
            passed,
            pass_fail,
            yes_votes,
            no_votes,
            total_votes,
            percent_yes,
            percent_no,
            topic_primary,
            topic_secondary,
            measure_type,
            data_source,
            has_summary,
            election_date,
            election_type,
            source_url,
            ballot_question,
            description
        FROM measures
        WHERE is_active = 1
    '''

    conditions = []
    if year_filter:
        conditions.append(f"year >= {year_filter}")
    if with_summaries_only:
        conditions.append("has_summary = 1")

    if conditions:
        query += " AND " + " AND ".join(conditions)

    query += " ORDER BY year DESC, county, measure_id"

    cursor = conn.execute(query)

    if not output_file:
        output_file = f'data/exports/ballot_measures_{datetime.now().strftime("%Y%m%d")}.csv'

    Path(output_file).parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([col[0] for col in cursor.description])
        rows = cursor.fetchall()
        writer.writerows(rows)

    db.close()
    return output_file, len(rows)

def export_json(output_file=None, year_filter=None, with_summaries_only=False):
    """Export to JSON format"""
    db = Database()
    conn = db.connect()

    query = '''
        SELECT
            measure_id,
            year,
            county,
            jurisdiction,
            title,
            summary_title,
            summary_text,
            passed,
            pass_fail,
            yes_votes,
            no_votes,
            total_votes,
            percent_yes,
            percent_no,
            topic_primary,
            topic_secondary,
            measure_type,
            data_source,
            has_summary,
            election_date,
            source_url
        FROM measures
        WHERE is_active = 1
    '''

    conditions = []
    if year_filter:
        conditions.append(f"year >= {year_filter}")
    if with_summaries_only:
        conditions.append("has_summary = 1")

    if conditions:
        query += " AND " + " AND ".join(conditions)

    query += " ORDER BY year DESC, county, measure_id"

    cursor = conn.execute(query)
    columns = [col[0] for col in cursor.description]
    rows = cursor.fetchall()

    data = [dict(zip(columns, row)) for row in rows]

    if not output_file:
        output_file = f'data/exports/ballot_measures_{datetime.now().strftime("%Y%m%d")}.json'

    Path(output_file).parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, default=str)

    db.close()
    return output_file, len(data)

def export_summary_quality(output_file=None):
    """Export summary quality analysis"""
    db = Database()
    conn = db.connect()

    cursor = conn.execute('''
        SELECT
            measure_id,
            year,
            county,
            title,
            summary_text,
            LENGTH(summary_text) as length,
            CASE
                WHEN summary_text LIKE '%can''t help%' OR summary_text LIKE '%don''t have%' THEN 'AI_REFUSAL'
                WHEN LENGTH(summary_text) < 100 THEN 'TOO_SHORT'
                WHEN LENGTH(summary_text) > 1000 THEN 'TOO_LONG'
                WHEN LENGTH(summary_text) BETWEEN 200 AND 600 THEN 'GOOD'
                ELSE 'OK'
            END as quality,
            data_source
        FROM measures
        WHERE year >= 2020
            AND is_active = 1
            AND has_summary = 1
        ORDER BY quality, year DESC
    ''')

    if not output_file:
        output_file = f'data/exports/summary_quality_{datetime.now().strftime("%Y%m%d")}.csv'

    Path(output_file).parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['measure_id', 'year', 'county', 'title', 'summary_text',
                        'length', 'quality', 'data_source'])
        rows = cursor.fetchall()
        writer.writerows(rows)

    db.close()
    return output_file, len(rows)

def main():
    import argparse

    parser = argparse.ArgumentParser(description='Export ballot measures data')
    parser.add_argument('--format', choices=['csv', 'json', 'summary-quality'],
                       default='csv', help='Export format')
    parser.add_argument('--output', '-o', help='Output file path')
    parser.add_argument('--year', type=int, help='Filter by year (>= year)')
    parser.add_argument('--summaries-only', action='store_true',
                       help='Only export measures with summaries')

    args = parser.parse_args()

    print("=" * 60)
    print("BALLOT MEASURES DATA EXPORT")
    print("=" * 60)

    if args.format == 'csv':
        output, count = export_csv(args.output, args.year, args.summaries_only)
        print(f"\n✅ Exported {count} measures to CSV")
    elif args.format == 'json':
        output, count = export_json(args.output, args.year, args.summaries_only)
        print(f"\n✅ Exported {count} measures to JSON")
    elif args.format == 'summary-quality':
        output, count = export_summary_quality(args.output)
        print(f"\n✅ Exported {count} summary quality records")

    print(f"📁 File: {output}")
    print(f"📊 Size: {Path(output).stat().st_size / 1024 / 1024:.2f} MB")

if __name__ == '__main__':
    main()
