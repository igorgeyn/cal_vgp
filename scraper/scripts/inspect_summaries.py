#!/usr/bin/env python3
"""
Comprehensive inspection of generated ballot measure summaries.

Analyzes:
- Coverage statistics
- Length distribution
- Quality indicators (preambles, too short/long, etc.)
- Sample summaries by category
- Potential issues flagged for review

Usage:
    python scripts/inspect_summaries.py [--export]
"""

import sqlite3
import argparse
import re
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime

DB_PATH = Path(__file__).parent.parent / "data" / "ballot_measures.db"
REPORT_PATH = Path(__file__).parent.parent / "data" / "summary_inspection_report.txt"

# Quality flags
PREAMBLE_PATTERNS = [
    r'^here is',
    r'^this is a',
    r'^summary:',
    r'^the summary',
    r'^in summary',
    r'^to summarize',
]

QUALITY_ISSUES = {
    'too_short': lambda s: len(s) < 50,
    'too_long': lambda s: len(s) > 500,
    'has_preamble': lambda s: any(re.match(p, s.lower()) for p in PREAMBLE_PATTERNS),
    'ends_badly': lambda s: s.rstrip()[-1] not in '.?!"\')',
    'has_bullet_points': lambda s: '•' in s or '\n-' in s or '\n*' in s,
    'mentions_vote': lambda s: 'vote yes' in s.lower() or 'vote no' in s.lower(),
    'too_many_sentences': lambda s: s.count('. ') > 4,
}


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_summary_stats(conn):
    """Get overall summary coverage statistics."""
    cursor = conn.execute("""
        SELECT
            COUNT(*) as total_active,
            SUM(CASE WHEN summary_text IS NOT NULL AND summary_text != '' THEN 1 ELSE 0 END) as has_summary,
            SUM(CASE WHEN summary_text IS NULL OR summary_text = '' THEN 1 ELSE 0 END) as no_summary
        FROM measures
        WHERE is_active = 1
    """)
    return dict(cursor.fetchone())


def get_summaries_by_category(conn):
    """Get summary counts by category type and topic."""
    cursor = conn.execute("""
        SELECT
            category_type,
            topic_primary,
            COUNT(*) as total,
            SUM(CASE WHEN summary_text IS NOT NULL AND summary_text != '' THEN 1 ELSE 0 END) as has_summary
        FROM measures
        WHERE is_active = 1
        GROUP BY category_type, topic_primary
        ORDER BY total DESC
    """)
    return cursor.fetchall()


def get_all_summaries(conn):
    """Get all summaries with metadata for analysis."""
    cursor = conn.execute("""
        SELECT
            id, title, summary_text, county, year,
            category_type, topic_primary, vote_threshold,
            passed, percent_yes
        FROM measures
        WHERE is_active = 1
          AND summary_text IS NOT NULL
          AND summary_text != ''
    """)
    return cursor.fetchall()


def analyze_summary_quality(summaries):
    """Analyze summaries for quality issues."""
    issues = defaultdict(list)
    length_distribution = []
    word_counts = []

    for row in summaries:
        summary = row['summary_text']
        measure_id = row['id']
        length_distribution.append(len(summary))
        word_counts.append(len(summary.split()))

        for issue_name, check_fn in QUALITY_ISSUES.items():
            if check_fn(summary):
                issues[issue_name].append({
                    'id': measure_id,
                    'county': row['county'],
                    'year': row['year'],
                    'category': row['category_type'],
                    'summary': summary[:200] + '...' if len(summary) > 200 else summary
                })

    return issues, length_distribution, word_counts


def get_sample_summaries(conn, n=5):
    """Get random sample summaries for manual review."""
    cursor = conn.execute(f"""
        SELECT
            id, title, summary_text, county, year,
            category_type, topic_primary, vote_threshold,
            passed, percent_yes
        FROM measures
        WHERE is_active = 1
          AND summary_text IS NOT NULL
          AND summary_text != ''
        ORDER BY RANDOM()
        LIMIT {n}
    """)
    return cursor.fetchall()


def get_samples_by_category(conn, n_per_category=2):
    """Get sample summaries from each category type."""
    cursor = conn.execute("""
        SELECT DISTINCT category_type
        FROM measures
        WHERE is_active = 1
          AND category_type IS NOT NULL
          AND category_type != ''
    """)
    categories = [row[0] for row in cursor.fetchall()]

    samples = {}
    for cat in categories[:10]:  # Top 10 categories
        cursor = conn.execute(f"""
            SELECT
                id, title, summary_text, county, year,
                category_type, topic_primary
            FROM measures
            WHERE is_active = 1
              AND summary_text IS NOT NULL
              AND summary_text != ''
              AND category_type = ?
            ORDER BY RANDOM()
            LIMIT {n_per_category}
        """, (cat,))
        samples[cat] = cursor.fetchall()

    return samples


def get_measures_without_summaries(conn, limit=20):
    """Get measures that still don't have summaries."""
    cursor = conn.execute(f"""
        SELECT
            id, title, county, year, category_type,
            LENGTH(title) as title_length
        FROM measures
        WHERE is_active = 1
          AND (summary_text IS NULL OR summary_text = '')
        ORDER BY LENGTH(title) DESC
        LIMIT {limit}
    """)
    return cursor.fetchall()


def percentile(data, p):
    """Calculate percentile of a list."""
    if not data:
        return 0
    sorted_data = sorted(data)
    k = (len(sorted_data) - 1) * p / 100
    f = int(k)
    c = f + 1 if f + 1 < len(sorted_data) else f
    return sorted_data[f] + (sorted_data[c] - sorted_data[f]) * (k - f)


def generate_report(conn, export_path=None):
    """Generate comprehensive inspection report."""
    report_lines = []

    def add(line=""):
        report_lines.append(line)

    add("=" * 80)
    add("BALLOT MEASURE SUMMARY INSPECTION REPORT")
    add(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    add("=" * 80)
    add()

    # 1. Coverage Statistics
    add("1. COVERAGE STATISTICS")
    add("-" * 40)
    stats = get_summary_stats(conn)
    coverage_pct = stats['has_summary'] / stats['total_active'] * 100
    add(f"Total active measures:     {stats['total_active']:,}")
    add(f"With summaries:            {stats['has_summary']:,} ({coverage_pct:.1f}%)")
    add(f"Without summaries:         {stats['no_summary']:,} ({100-coverage_pct:.1f}%)")
    add()

    # 2. Length Distribution
    add("2. SUMMARY LENGTH DISTRIBUTION")
    add("-" * 40)
    summaries = get_all_summaries(conn)
    issues, lengths, word_counts = analyze_summary_quality(summaries)

    add(f"Total summaries analyzed:  {len(summaries):,}")
    add()
    add("Character length:")
    add(f"  Min:        {min(lengths):,}")
    add(f"  25th pctl:  {percentile(lengths, 25):.0f}")
    add(f"  Median:     {percentile(lengths, 50):.0f}")
    add(f"  75th pctl:  {percentile(lengths, 75):.0f}")
    add(f"  Max:        {max(lengths):,}")
    add(f"  Average:    {sum(lengths)/len(lengths):.0f}")
    add()
    add("Word count:")
    add(f"  Min:        {min(word_counts)}")
    add(f"  Median:     {percentile(word_counts, 50):.0f}")
    add(f"  Max:        {max(word_counts)}")
    add(f"  Average:    {sum(word_counts)/len(word_counts):.1f}")
    add()

    # Length buckets
    add("Length distribution (characters):")
    buckets = [(0, 100), (100, 200), (200, 300), (300, 400), (400, 500), (500, float('inf'))]
    for low, high in buckets:
        count = sum(1 for l in lengths if low <= l < high)
        pct = count / len(lengths) * 100
        label = f"{low}-{high}" if high != float('inf') else f"{low}+"
        bar = "█" * int(pct / 2)
        add(f"  {label:>8}: {count:>5} ({pct:>5.1f}%) {bar}")
    add()

    # 3. Quality Issues
    add("3. QUALITY ISSUES DETECTED")
    add("-" * 40)
    total_issues = sum(len(v) for v in issues.values())
    add(f"Total issues found: {total_issues} across {len(summaries):,} summaries")
    add()

    issue_descriptions = {
        'too_short': 'Too short (<50 chars)',
        'too_long': 'Too long (>500 chars)',
        'has_preamble': 'Has preamble (e.g., "Here is...")',
        'ends_badly': 'Doesn\'t end with punctuation',
        'has_bullet_points': 'Contains bullet points',
        'mentions_vote': 'Contains "vote yes/no" (biased)',
        'too_many_sentences': 'Too many sentences (>4)',
    }

    for issue_name, issue_list in sorted(issues.items(), key=lambda x: -len(x[1])):
        count = len(issue_list)
        pct = count / len(summaries) * 100
        desc = issue_descriptions.get(issue_name, issue_name)
        add(f"  {desc}: {count} ({pct:.2f}%)")

    add()

    # 4. Examples of Issues
    add("4. EXAMPLES OF FLAGGED SUMMARIES")
    add("-" * 40)
    for issue_name, issue_list in issues.items():
        if issue_list:
            add(f"\n{issue_descriptions.get(issue_name, issue_name).upper()}:")
            for item in issue_list[:3]:  # Show 3 examples per issue
                add(f"  ID {item['id']} ({item['county']}, {item['year']}):")
                add(f"    \"{item['summary']}\"")
    add()

    # 5. Sample Summaries by Category
    add("5. SAMPLE SUMMARIES BY CATEGORY")
    add("-" * 40)
    samples_by_cat = get_samples_by_category(conn, n_per_category=2)
    for category, samples in samples_by_cat.items():
        add(f"\n{category}:")
        for row in samples:
            add(f"  [{row['county']}, {row['year']}]")
            add(f"  Title: {row['title'][:100]}...")
            add(f"  Summary: {row['summary_text']}")
            add()

    # 6. Random Samples for Manual Review
    add("6. RANDOM SAMPLES FOR MANUAL REVIEW")
    add("-" * 40)
    random_samples = get_sample_summaries(conn, n=10)
    for i, row in enumerate(random_samples, 1):
        outcome = "Passed" if row['passed'] == 1 else "Failed" if row['passed'] == 0 else "Unknown"
        add(f"\nSample {i}: ID {row['id']}")
        add(f"  Location: {row['county']}, {row['year']}")
        add(f"  Type: {row['category_type']} ({row['topic_primary']})")
        add(f"  Outcome: {outcome}" + (f" ({row['percent_yes']:.1f}% yes)" if row['percent_yes'] else ""))
        add(f"  Title: {row['title'][:150]}{'...' if len(row['title']) > 150 else ''}")
        add(f"  Summary: {row['summary_text']}")

    add()

    # 7. Measures Still Without Summaries
    add("7. MEASURES WITHOUT SUMMARIES (sample)")
    add("-" * 40)
    no_summary = get_measures_without_summaries(conn, limit=15)
    if no_summary:
        add(f"Showing {len(no_summary)} of {stats['no_summary']} measures without summaries:")
        add()
        for row in no_summary:
            add(f"  ID {row['id']}: {row['county']}, {row['year']} ({row['category_type']})")
            add(f"    Title ({row['title_length']} chars): {row['title'][:100]}...")
    else:
        add("All measures have summaries!")

    add()
    add("=" * 80)
    add("END OF REPORT")
    add("=" * 80)

    report_text = "\n".join(report_lines)

    # Print to console
    print(report_text)

    # Export if requested
    if export_path:
        with open(export_path, 'w') as f:
            f.write(report_text)
        print(f"\nReport exported to: {export_path}")

    return report_text


def main():
    parser = argparse.ArgumentParser(description="Inspect generated summaries")
    parser.add_argument("--export", action="store_true", help="Export report to file")
    args = parser.parse_args()

    conn = get_connection()

    export_path = REPORT_PATH if args.export else None
    generate_report(conn, export_path)

    conn.close()


if __name__ == "__main__":
    main()
