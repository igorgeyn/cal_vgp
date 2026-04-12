#!/usr/bin/env python3
"""
Build analysis-ready dataset from CalBallot SQLite database.

Produces a clean CSV with:
- Fixed percent_yes (normalized to 0-100 scale)
- Coded legal approval thresholds
- Education keyword flag (validated)
- Scope: CEDA local measures, 1998-2024

Output: analysis/data/local_measures_analysis.csv
"""
import sys
import sqlite3
import re
import csv
from pathlib import Path
from collections import Counter

DB_PATH = Path(__file__).parent.parent / "scraper" / "data" / "ballot_measures.db"
OUTPUT_PATH = Path(__file__).parent / "data" / "local_measures_analysis.csv"


def extract_measures(conn):
    """Extract CEDA local measures with all fields."""
    cursor = conn.execute("""
        SELECT id, year, county, measure_letter, measure_id,
               title, ballot_question, description,
               category_type, category_topic,
               yes_votes, no_votes, total_votes,
               percent_yes, percent_no,
               passed, pass_fail,
               election_type, election_date, decade,
               data_source, has_summary, summary_text
        FROM measures
        WHERE is_active = 1 AND is_duplicate = 0
          AND data_source = 'CEDA'
          AND year BETWEEN 1998 AND 2024
        ORDER BY year, county, measure_letter
    """)
    columns = [desc[0] for desc in cursor.description]
    rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
    print(f"Extracted {len(rows)} CEDA local measures (1998-2024)")
    return rows


def fix_percent_yes(measures):
    """Normalize percent_yes to 0-100 scale and recompute from votes where possible."""
    fixed = 0
    recomputed = 0

    for m in measures:
        pct = m['percent_yes']
        yes = m['yes_votes']
        no = m['no_votes']

        # Recompute from raw votes if available (most authoritative)
        if yes is not None and no is not None and (yes + no) > 0:
            computed = round(100.0 * yes / (yes + no), 4)
            if pct is not None and abs(computed - pct) > 1.0:
                # Stored value is wrong, use computed
                m['percent_yes'] = computed
                m['percent_no'] = round(100.0 - computed, 4)
                recomputed += 1
            elif pct is None:
                m['percent_yes'] = computed
                m['percent_no'] = round(100.0 - computed, 4)
                recomputed += 1
            else:
                # Stored value agrees with computed, keep it
                pass
        elif pct is not None:
            # No raw votes — fix the stored value
            if pct > 100:
                m['percent_yes'] = round(pct / 100.0, 4)
                m['percent_no'] = round(100.0 - m['percent_yes'], 4) if m['percent_yes'] <= 100 else None
                fixed += 1
            elif 0 < pct <= 1:
                m['percent_yes'] = round(pct * 100.0, 4)
                m['percent_no'] = round(100.0 - m['percent_yes'], 4)
                fixed += 1

    print(f"percent_yes: {recomputed} recomputed from votes, {fixed} fixed from stored values")

    # Verify all are now 0-100
    bad = sum(1 for m in measures if m['percent_yes'] is not None and (m['percent_yes'] < 0 or m['percent_yes'] > 100))
    print(f"  Remaining out-of-range: {bad}")
    return measures


def code_thresholds(measures):
    """Code legal approval thresholds based on measure type, topic, and year.

    California approval thresholds:
    - 50%: general taxes, ordinances, charter amendments, advisories, recalls, Gann limits
    - 55%: school facility bonds post-Prop 39 (Nov 2000)
    - 66.67%: special taxes (parcel, sales, utility, business, TOT), non-school GO bonds
    """
    # Education keywords for detecting school bonds
    edu_keywords = re.compile(
        r'school|education|unified|elementary|high school|college|university|library|libraries',
        re.IGNORECASE
    )

    threshold_counts = Counter()

    for m in measures:
        cat_type = (m['category_type'] or '').strip()
        cat_topic = (m['category_topic'] or '').strip()
        ballot_q = (m['ballot_question'] or '').strip()
        title = (m['title'] or '').strip()
        year = m['year']
        text = f"{cat_topic} {ballot_q} {title}"

        is_education = bool(edu_keywords.search(text))
        m['is_education'] = is_education

        # Default threshold based on category_type
        threshold = None
        threshold_source = 'rule'
        threshold_uncertain = False

        cat_lower = cat_type.lower()

        if cat_lower in ('ordinance', 'charter amendment', 'advisory', 'recall',
                         'gann limit', 'policy/position', 'initiative'):
            threshold = 50.0

        elif cat_lower in ('sales tax', 'utility tax', 'business tax',
                           'transient occupancy tax', 'miscellaneous tax',
                           'property tax', 'gasoline tax', 'development tax',
                           'taxes'):
            # Special taxes require 2/3
            threshold = 66.67
            # But some "property tax" might be general tax — flag as uncertain
            if cat_lower in ('miscellaneous tax', 'taxes'):
                threshold_uncertain = True

        elif cat_lower in ('go bond', 'bonds', 'mello/roos bond'):
            if is_education and year > 2000:
                # Prop 39: school facility bonds need 55% after Nov 2000
                threshold = 55.0
                threshold_source = 'keyword'
            else:
                # Non-school GO bonds or pre-Prop 39 school bonds: 2/3
                threshold = 66.67
                if year > 2000:
                    # Could be school but we didn't detect education keywords
                    threshold_uncertain = True

        else:
            # Unknown type — default to 50% but flag
            threshold = 50.0
            threshold_uncertain = True

        m['threshold_required'] = threshold
        m['threshold_source'] = threshold_source
        m['threshold_uncertain'] = threshold_uncertain
        threshold_counts[threshold] += 1

    print(f"Threshold coding:")
    for t, n in sorted(threshold_counts.items()):
        uncertain = sum(1 for m in measures if m['threshold_required'] == t and m['threshold_uncertain'])
        print(f"  {t}%: {n} measures ({uncertain} uncertain)")

    # Recode passed field based on corrected percent_yes and threshold
    recoded = 0
    for m in measures:
        pct = m['percent_yes']
        thresh = m['threshold_required']
        if pct is not None and thresh is not None:
            should_pass = pct >= thresh
            if m['passed'] != (1 if should_pass else 0):
                m['passed_original'] = m['passed']
                m['passed'] = 1 if should_pass else 0
                recoded += 1
            else:
                m['passed_original'] = m['passed']
        else:
            m['passed_original'] = m['passed']

    print(f"  Recoded {recoded} passed values based on corrected percent_yes vs threshold")

    # Compute margin
    for m in measures:
        if m['percent_yes'] is not None and m['threshold_required'] is not None:
            m['margin'] = round(m['percent_yes'] - m['threshold_required'], 4)
            m['is_trapped'] = m['percent_yes'] > 50 and m['passed'] == 0
        else:
            m['margin'] = None
            m['is_trapped'] = None

    trapped = sum(1 for m in measures if m.get('is_trapped'))
    print(f"  Threshold-trapped measures (>50% YES but failed): {trapped}")

    return measures


def write_csv(measures, output_path):
    """Write analysis dataset to CSV."""
    if not measures:
        print("No measures to write!")
        return

    # Define output columns
    columns = [
        'id', 'year', 'county', 'measure_letter', 'measure_id',
        'title', 'ballot_question',
        'category_type', 'category_topic',
        'yes_votes', 'no_votes', 'total_votes',
        'percent_yes', 'percent_no',
        'passed', 'passed_original', 'pass_fail',
        'threshold_required', 'threshold_source', 'threshold_uncertain',
        'margin', 'is_trapped', 'is_education',
        'election_type', 'election_date', 'decade',
        'has_summary', 'summary_text',
    ]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(measures)

    print(f"\nWrote {len(measures)} measures to {output_path}")


def summary_stats(measures):
    """Print summary statistics for QA."""
    print(f"\n{'='*60}")
    print(f"ANALYSIS DATASET SUMMARY")
    print(f"{'='*60}")
    print(f"Total measures: {len(measures)}")
    print(f"Years: {min(m['year'] for m in measures)}-{max(m['year'] for m in measures)}")
    print(f"Counties: {len(set(m['county'] for m in measures))}")

    # percent_yes
    with_pct = [m for m in measures if m['percent_yes'] is not None]
    print(f"\npercent_yes: {len(with_pct)} non-null")
    if with_pct:
        pcts = [m['percent_yes'] for m in with_pct]
        print(f"  Range: {min(pcts):.1f} - {max(pcts):.1f}")
        bad = [p for p in pcts if p < 0 or p > 100]
        print(f"  Out of 0-100: {len(bad)}")

    # Thresholds
    print(f"\nThresholds:")
    for t in [50.0, 55.0, 66.67]:
        n = sum(1 for m in measures if m.get('threshold_required') == t)
        uncertain = sum(1 for m in measures if m.get('threshold_required') == t and m.get('threshold_uncertain'))
        print(f"  {t}%: {n} ({uncertain} uncertain)")

    # Pass rate
    with_outcome = [m for m in measures if m['passed'] is not None]
    passed = sum(1 for m in with_outcome if m['passed'] == 1)
    print(f"\nOutcomes: {len(with_outcome)} with pass/fail")
    print(f"  Passed: {passed} ({100*passed/len(with_outcome):.1f}%)")

    # Education
    edu = sum(1 for m in measures if m.get('is_education'))
    print(f"\nEducation-flagged: {edu}")

    # Trapped
    trapped = sum(1 for m in measures if m.get('is_trapped'))
    print(f"Threshold-trapped: {trapped}")

    # Category coverage
    with_cat = sum(1 for m in measures if m.get('category_type'))
    print(f"\ncategory_type coverage: {with_cat}/{len(measures)} ({100*with_cat/len(measures):.1f}%)")


def main():
    print(f"Database: {DB_PATH}")
    print(f"Output: {OUTPUT_PATH}")

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    measures = extract_measures(conn)
    measures = fix_percent_yes(measures)
    measures = code_thresholds(measures)
    write_csv(measures, OUTPUT_PATH)
    summary_stats(measures)

    conn.close()


if __name__ == "__main__":
    main()
