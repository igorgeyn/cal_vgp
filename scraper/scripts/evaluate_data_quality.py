#!/usr/bin/env python3
"""
Comprehensive Data Quality Evaluation Pipeline for CalBallot.

Evaluates:
1. Completeness - Missing values across all fields
2. Consistency - Data type validation, value ranges, cross-field logic
3. Accuracy - Vote math, percentage calculations, outcome logic
4. Uniqueness - Duplicate detection, fingerprint integrity
5. Timeliness - Data freshness, coverage gaps
6. Validity - Format validation, enum constraints, referential integrity
7. Summary Quality - AI-generated content analysis
8. Finance Data Quality - Campaign finance data validation

Usage:
    python scripts/evaluate_data_quality.py [--export] [--verbose]

Output:
    - Console report with scores and issues
    - Optional JSON export for programmatic analysis
"""

import sqlite3
import json
import re
import argparse
from pathlib import Path
from datetime import datetime
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional, Tuple
import hashlib

# Paths
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent / "data"
DB_PATH = DATA_DIR / "ballot_measures.db"
# TODO: Audit logic below queries v1-only tables (measure_finance_summary,
# transaction_record, committee) that don't exist in finance_statewide_v2.db.
# Pointing at the legacy DB so this script keeps working against the audit-
# only artifact; full rewrite needed before this can audit v2 (different
# schema, finance_campaign_id keying, no transaction_record table).
FINANCE_DB_PATH = DATA_DIR / "finance" / "finance_statewide.db"
EMBEDDINGS_PATH = DATA_DIR / "embedding_metadata.json"
REPORT_PATH = DATA_DIR / "data_quality_report.json"


@dataclass
class QualityScore:
    """Score for a quality dimension."""
    dimension: str
    score: float  # 0-100
    weight: float  # Importance weight
    issues_count: int
    critical_issues: int
    warnings: int
    details: Dict[str, Any]


@dataclass
class QualityIssue:
    """Individual quality issue."""
    dimension: str
    severity: str  # 'critical', 'warning', 'info'
    field: str
    description: str
    affected_count: int
    sample_ids: List[int]


class DataQualityEvaluator:
    """Comprehensive data quality evaluation."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.conn = sqlite3.connect(DB_PATH)
        self.conn.row_factory = sqlite3.Row
        self.issues: List[QualityIssue] = []
        self.scores: List[QualityScore] = []

        # Try to connect to finance DB
        self.finance_conn = None
        if FINANCE_DB_PATH.exists():
            self.finance_conn = sqlite3.connect(FINANCE_DB_PATH)
            self.finance_conn.row_factory = sqlite3.Row

    def log(self, msg: str):
        """Verbose logging."""
        if self.verbose:
            print(f"  [DEBUG] {msg}")

    def add_issue(self, dimension: str, severity: str, field: str,
                  description: str, affected_count: int, sample_ids: List[int] = None):
        """Record a quality issue."""
        self.issues.append(QualityIssue(
            dimension=dimension,
            severity=severity,
            field=field,
            description=description,
            affected_count=affected_count,
            sample_ids=sample_ids or []
        ))

    def evaluate_all(self) -> Dict[str, Any]:
        """Run all quality evaluations."""
        print("=" * 80)
        print("CALBALLOT DATA QUALITY EVALUATION")
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)
        print()

        # Run all evaluations
        self.evaluate_completeness()
        self.evaluate_consistency()
        self.evaluate_accuracy()
        self.evaluate_uniqueness()
        self.evaluate_timeliness()
        self.evaluate_validity()
        self.evaluate_summary_quality()
        self.evaluate_finance_quality()
        self.evaluate_recommendations()

        # Calculate overall score
        overall = self.calculate_overall_score()

        # Generate report
        report = self.generate_report(overall)

        return report

    # =========================================================================
    # 1. COMPLETENESS - Missing values analysis
    # =========================================================================

    def evaluate_completeness(self):
        """Evaluate data completeness across all fields."""
        print("1. COMPLETENESS ANALYSIS")
        print("-" * 40)

        cursor = self.conn.execute("SELECT COUNT(*) FROM measures WHERE is_active = 1")
        total = cursor.fetchone()[0]
        print(f"Total active measures: {total:,}")

        # Define field importance tiers
        critical_fields = ['measure_id', 'year', 'title']
        important_fields = ['county', 'passed', 'percent_yes', 'summary_text', 'topic_primary']
        optional_fields = ['description', 'ballot_question', 'pdf_url', 'vote_threshold',
                          'yes_votes', 'no_votes', 'source_url']

        completeness_stats = {}
        issues_found = 0
        critical_issues = 0

        # Check each field
        for field in critical_fields + important_fields + optional_fields:
            cursor = self.conn.execute(f"""
                SELECT COUNT(*) FROM measures
                WHERE is_active = 1 AND ({field} IS NULL OR {field} = '')
            """)
            missing = cursor.fetchone()[0]
            pct_complete = ((total - missing) / total * 100) if total > 0 else 0
            completeness_stats[field] = {
                'missing': missing,
                'complete': total - missing,
                'pct_complete': round(pct_complete, 2)
            }

            # Classify severity
            if field in critical_fields and missing > 0:
                self.add_issue('completeness', 'critical', field,
                              f"Critical field missing in {missing} records",
                              missing, self._get_sample_ids(f"{field} IS NULL OR {field} = ''"))
                critical_issues += 1
                issues_found += 1
            elif field in important_fields and missing > total * 0.05:
                self.add_issue('completeness', 'warning', field,
                              f"Important field missing in {missing} records ({100-pct_complete:.1f}%)",
                              missing, self._get_sample_ids(f"{field} IS NULL OR {field} = ''"))
                issues_found += 1

        # Print summary
        print("\nField Completeness:")
        print(f"{'Field':<20} {'Complete':>10} {'Missing':>10} {'%':>8}")
        print("-" * 50)
        for field, stats in completeness_stats.items():
            tier = '***' if field in critical_fields else '**' if field in important_fields else '*'
            print(f"{field:<20} {stats['complete']:>10,} {stats['missing']:>10,} {stats['pct_complete']:>7.1f}%  {tier}")

        # Calculate score
        # Weight: critical fields 50%, important fields 35%, optional fields 15%
        critical_score = sum(completeness_stats[f]['pct_complete'] for f in critical_fields) / len(critical_fields)
        important_score = sum(completeness_stats[f]['pct_complete'] for f in important_fields) / len(important_fields)
        optional_score = sum(completeness_stats[f]['pct_complete'] for f in optional_fields) / len(optional_fields)

        weighted_score = critical_score * 0.5 + important_score * 0.35 + optional_score * 0.15

        self.scores.append(QualityScore(
            dimension='completeness',
            score=round(weighted_score, 2),
            weight=0.20,
            issues_count=issues_found,
            critical_issues=critical_issues,
            warnings=issues_found - critical_issues,
            details=completeness_stats
        ))

        print(f"\nCompleteness Score: {weighted_score:.1f}/100")
        print()

    # =========================================================================
    # 2. CONSISTENCY - Data type and cross-field validation
    # =========================================================================

    def evaluate_consistency(self):
        """Evaluate data consistency and type validation."""
        print("2. CONSISTENCY ANALYSIS")
        print("-" * 40)

        issues_found = 0
        critical_issues = 0
        consistency_checks = {}

        # Check 1: Year is valid integer in reasonable range
        cursor = self.conn.execute("""
            SELECT COUNT(*), MIN(year), MAX(year) FROM measures WHERE is_active = 1
        """)
        row = cursor.fetchone()
        total, min_year, max_year = row[0], row[1], row[2]

        cursor = self.conn.execute("""
            SELECT COUNT(*) FROM measures
            WHERE is_active = 1 AND (year < 1900 OR year > 2030 OR year IS NULL)
        """)
        invalid_years = cursor.fetchone()[0]
        consistency_checks['valid_years'] = {
            'valid': total - invalid_years,
            'invalid': invalid_years,
            'range': f"{min_year}-{max_year}"
        }
        if invalid_years > 0:
            self.add_issue('consistency', 'critical', 'year',
                          f"Invalid year values found", invalid_years,
                          self._get_sample_ids("year < 1900 OR year > 2030"))
            critical_issues += 1
            issues_found += 1

        # Check 2: Percentage values in 0-100 range
        cursor = self.conn.execute("""
            SELECT COUNT(*) FROM measures
            WHERE is_active = 1
              AND percent_yes IS NOT NULL
              AND (percent_yes < 0 OR percent_yes > 100)
        """)
        invalid_pct = cursor.fetchone()[0]
        consistency_checks['valid_percentages'] = {'invalid': invalid_pct}
        if invalid_pct > 0:
            self.add_issue('consistency', 'critical', 'percent_yes',
                          f"Percentage values out of range (0-100)", invalid_pct,
                          self._get_sample_ids("percent_yes < 0 OR percent_yes > 100"))
            critical_issues += 1
            issues_found += 1

        # Check 3: Passed field matches percent_yes and vote_threshold
        cursor = self.conn.execute("""
            SELECT COUNT(*) FROM measures
            WHERE is_active = 1
              AND passed IS NOT NULL
              AND percent_yes IS NOT NULL
              AND vote_threshold IS NOT NULL
              AND (
                  (vote_threshold = '50%' AND passed = 1 AND percent_yes < 50) OR
                  (vote_threshold = '50%' AND passed = 0 AND percent_yes >= 50) OR
                  (vote_threshold = '55%' AND passed = 1 AND percent_yes < 55) OR
                  (vote_threshold = '55%' AND passed = 0 AND percent_yes >= 55) OR
                  (vote_threshold = '66.67%' AND passed = 1 AND percent_yes < 66.67) OR
                  (vote_threshold = '66.67%' AND passed = 0 AND percent_yes >= 66.67)
              )
        """)
        threshold_mismatches = cursor.fetchone()[0]
        consistency_checks['threshold_logic'] = {'mismatches': threshold_mismatches}
        if threshold_mismatches > 0:
            self.add_issue('consistency', 'warning', 'passed/vote_threshold',
                          f"Pass/fail doesn't match vote threshold", threshold_mismatches,
                          self._get_sample_ids("""
                              passed IS NOT NULL AND percent_yes IS NOT NULL AND vote_threshold IS NOT NULL
                              AND ((vote_threshold = '50%' AND passed = 1 AND percent_yes < 50) OR
                                   (vote_threshold = '50%' AND passed = 0 AND percent_yes >= 50))
                          """))
            issues_found += 1

        # Check 4: County values are valid California counties or 'Statewide'
        valid_counties = {
            'Alameda', 'Alpine', 'Amador', 'Butte', 'Calaveras', 'Colusa', 'Contra Costa',
            'Del Norte', 'El Dorado', 'Fresno', 'Glenn', 'Humboldt', 'Imperial', 'Inyo',
            'Kern', 'Kings', 'Lake', 'Lassen', 'Los Angeles', 'Madera', 'Marin', 'Mariposa',
            'Mendocino', 'Merced', 'Modoc', 'Mono', 'Monterey', 'Napa', 'Nevada', 'Orange',
            'Placer', 'Plumas', 'Riverside', 'Sacramento', 'San Benito', 'San Bernardino',
            'San Diego', 'San Francisco', 'San Joaquin', 'San Luis Obispo', 'San Mateo',
            'Santa Barbara', 'Santa Clara', 'Santa Cruz', 'Shasta', 'Sierra', 'Siskiyou',
            'Solano', 'Sonoma', 'Stanislaus', 'Sutter', 'Tehama', 'Trinity', 'Tulare',
            'Tuolumne', 'Ventura', 'Yolo', 'Yuba', 'Statewide', 'California'
        }
        cursor = self.conn.execute("""
            SELECT DISTINCT county FROM measures WHERE is_active = 1 AND county IS NOT NULL
        """)
        all_counties = {row[0] for row in cursor.fetchall()}
        invalid_counties = all_counties - valid_counties
        consistency_checks['valid_counties'] = {
            'valid': len(all_counties - invalid_counties),
            'invalid': len(invalid_counties),
            'invalid_values': list(invalid_counties)[:10]
        }
        if invalid_counties:
            cursor = self.conn.execute(f"""
                SELECT COUNT(*) FROM measures WHERE is_active = 1 AND county IN ({','.join('?' * len(invalid_counties))})
            """, list(invalid_counties))
            count = cursor.fetchone()[0]
            self.add_issue('consistency', 'warning', 'county',
                          f"Non-standard county values: {invalid_counties}", count)
            issues_found += 1

        # Check 5: Data source values are known
        valid_sources = {'CA_SOS', 'CEDA', 'Ballotpedia', 'UC_Law_SF', 'ICPSR', 'NCSL'}
        cursor = self.conn.execute("""
            SELECT DISTINCT data_source FROM measures WHERE is_active = 1
        """)
        all_sources = {row[0] for row in cursor.fetchall() if row[0]}
        unknown_sources = all_sources - valid_sources
        consistency_checks['valid_sources'] = {
            'known': len(all_sources - unknown_sources),
            'unknown': len(unknown_sources),
            'unknown_values': list(unknown_sources)
        }

        # Check 6: Fingerprint format consistency
        cursor = self.conn.execute("""
            SELECT COUNT(*) FROM measures
            WHERE is_active = 1
              AND fingerprint IS NOT NULL
              AND fingerprint NOT LIKE '%|%|%|%'
        """)
        invalid_fingerprints = cursor.fetchone()[0]
        consistency_checks['fingerprint_format'] = {'invalid': invalid_fingerprints}
        if invalid_fingerprints > 0:
            self.add_issue('consistency', 'warning', 'fingerprint',
                          f"Fingerprints not in expected format", invalid_fingerprints)
            issues_found += 1

        # Print summary
        print(f"Year range: {consistency_checks['valid_years']['range']}")
        print(f"Invalid years: {consistency_checks['valid_years']['invalid']}")
        print(f"Invalid percentages: {consistency_checks['valid_percentages']['invalid']}")
        print(f"Threshold logic mismatches: {consistency_checks['threshold_logic']['mismatches']}")
        print(f"Non-standard counties: {len(consistency_checks['valid_counties']['invalid_values'])}")
        print(f"Invalid fingerprints: {consistency_checks['fingerprint_format']['invalid']}")

        # Calculate score
        total_checks = 6
        passed_checks = sum([
            1 if consistency_checks['valid_years']['invalid'] == 0 else 0,
            1 if consistency_checks['valid_percentages']['invalid'] == 0 else 0,
            1 if consistency_checks['threshold_logic']['mismatches'] == 0 else 0,
            1 if len(consistency_checks['valid_counties']['invalid_values']) == 0 else 0,
            1 if len(consistency_checks['valid_sources'].get('unknown_values', [])) == 0 else 0,
            1 if consistency_checks['fingerprint_format']['invalid'] == 0 else 0,
        ])
        score = (passed_checks / total_checks) * 100

        self.scores.append(QualityScore(
            dimension='consistency',
            score=round(score, 2),
            weight=0.15,
            issues_count=issues_found,
            critical_issues=critical_issues,
            warnings=issues_found - critical_issues,
            details=consistency_checks
        ))

        print(f"\nConsistency Score: {score:.1f}/100")
        print()

    # =========================================================================
    # 3. ACCURACY - Mathematical and logical accuracy
    # =========================================================================

    def evaluate_accuracy(self):
        """Evaluate data accuracy through mathematical validation."""
        print("3. ACCURACY ANALYSIS")
        print("-" * 40)

        issues_found = 0
        critical_issues = 0
        accuracy_checks = {}

        # Check 1: yes_votes + no_votes = total_votes (within tolerance)
        cursor = self.conn.execute("""
            SELECT id, yes_votes, no_votes, total_votes
            FROM measures
            WHERE is_active = 1
              AND yes_votes IS NOT NULL
              AND no_votes IS NOT NULL
              AND total_votes IS NOT NULL
        """)
        vote_records = cursor.fetchall()
        vote_math_errors = []
        for row in vote_records:
            expected_total = row['yes_votes'] + row['no_votes']
            if abs(expected_total - row['total_votes']) > 1:  # Allow rounding
                vote_math_errors.append(row['id'])

        accuracy_checks['vote_math'] = {
            'checked': len(vote_records),
            'errors': len(vote_math_errors)
        }
        if vote_math_errors:
            self.add_issue('accuracy', 'critical', 'vote_totals',
                          f"Vote math doesn't add up (yes + no != total)", len(vote_math_errors),
                          vote_math_errors[:10])
            critical_issues += 1
            issues_found += 1

        # Check 2: percent_yes matches yes_votes/total_votes (within 0.5%)
        cursor = self.conn.execute("""
            SELECT id, yes_votes, total_votes, percent_yes
            FROM measures
            WHERE is_active = 1
              AND yes_votes IS NOT NULL
              AND total_votes IS NOT NULL
              AND total_votes > 0
              AND percent_yes IS NOT NULL
        """)
        pct_records = cursor.fetchall()
        pct_errors = []
        for row in pct_records:
            calculated_pct = (row['yes_votes'] / row['total_votes']) * 100
            if abs(calculated_pct - row['percent_yes']) > 0.5:
                pct_errors.append(row['id'])

        accuracy_checks['percentage_calculation'] = {
            'checked': len(pct_records),
            'errors': len(pct_errors)
        }
        if pct_errors:
            self.add_issue('accuracy', 'warning', 'percent_yes',
                          f"Percentage doesn't match vote counts", len(pct_errors),
                          pct_errors[:10])
            issues_found += 1

        # Check 3: passed field matches percent_yes > 50 (for measures without threshold)
        cursor = self.conn.execute("""
            SELECT id, percent_yes, passed, vote_threshold
            FROM measures
            WHERE is_active = 1
              AND percent_yes IS NOT NULL
              AND passed IS NOT NULL
              AND (vote_threshold IS NULL OR vote_threshold = '' OR vote_threshold = '50%')
        """)
        outcome_records = cursor.fetchall()
        outcome_errors = []
        for row in outcome_records:
            expected_passed = 1 if row['percent_yes'] >= 50 else 0
            if row['passed'] != expected_passed:
                outcome_errors.append(row['id'])

        accuracy_checks['outcome_logic'] = {
            'checked': len(outcome_records),
            'errors': len(outcome_errors)
        }
        if outcome_errors:
            self.add_issue('accuracy', 'warning', 'passed',
                          f"Pass/fail doesn't match percentage (50% threshold)", len(outcome_errors),
                          outcome_errors[:10])
            issues_found += 1

        # Check 4: Content hash matches actual content
        cursor = self.conn.execute("""
            SELECT id, title, ballot_question, description, content_hash
            FROM measures
            WHERE is_active = 1 AND content_hash IS NOT NULL
            LIMIT 1000
        """)
        hash_records = cursor.fetchall()
        hash_errors = []
        for row in hash_records:
            content = f"{row['title'] or ''}|{row['ballot_question'] or ''}|{row['description'] or ''}"
            expected_hash = hashlib.md5(content.encode()).hexdigest()
            if row['content_hash'] != expected_hash:
                hash_errors.append(row['id'])

        accuracy_checks['content_hash'] = {
            'checked': len(hash_records),
            'errors': len(hash_errors)
        }
        if hash_errors:
            self.add_issue('accuracy', 'info', 'content_hash',
                          f"Content hash doesn't match content", len(hash_errors),
                          hash_errors[:10])
            issues_found += 1

        # Print summary
        print(f"Vote math checks: {accuracy_checks['vote_math']['checked']:,} checked, "
              f"{accuracy_checks['vote_math']['errors']} errors")
        print(f"Percentage checks: {accuracy_checks['percentage_calculation']['checked']:,} checked, "
              f"{accuracy_checks['percentage_calculation']['errors']} errors")
        print(f"Outcome logic checks: {accuracy_checks['outcome_logic']['checked']:,} checked, "
              f"{accuracy_checks['outcome_logic']['errors']} errors")
        print(f"Content hash checks: {accuracy_checks['content_hash']['checked']:,} checked, "
              f"{accuracy_checks['content_hash']['errors']} errors")

        # Calculate score
        total_checked = sum(c['checked'] for c in accuracy_checks.values())
        total_errors = sum(c['errors'] for c in accuracy_checks.values())
        score = ((total_checked - total_errors) / total_checked * 100) if total_checked > 0 else 100

        self.scores.append(QualityScore(
            dimension='accuracy',
            score=round(score, 2),
            weight=0.20,
            issues_count=issues_found,
            critical_issues=critical_issues,
            warnings=issues_found - critical_issues,
            details=accuracy_checks
        ))

        print(f"\nAccuracy Score: {score:.1f}/100")
        print()

    # =========================================================================
    # 4. UNIQUENESS - Duplicate detection
    # =========================================================================

    def evaluate_uniqueness(self):
        """Evaluate data uniqueness and duplicate handling."""
        print("4. UNIQUENESS ANALYSIS")
        print("-" * 40)

        issues_found = 0
        critical_issues = 0
        uniqueness_checks = {}

        cursor = self.conn.execute("SELECT COUNT(*) FROM measures WHERE is_active = 1")
        total_active = cursor.fetchone()[0]

        # Check 1: Fingerprint uniqueness
        cursor = self.conn.execute("""
            SELECT fingerprint, COUNT(*) as cnt
            FROM measures WHERE is_active = 1
            GROUP BY fingerprint
            HAVING COUNT(*) > 1
        """)
        dup_fingerprints = cursor.fetchall()
        uniqueness_checks['fingerprint_duplicates'] = {
            'duplicate_groups': len(dup_fingerprints),
            'total_duplicates': sum(r['cnt'] - 1 for r in dup_fingerprints)
        }
        if dup_fingerprints:
            self.add_issue('uniqueness', 'critical', 'fingerprint',
                          f"Duplicate fingerprints found", len(dup_fingerprints))
            critical_issues += 1
            issues_found += 1

        # Check 2: Measure fingerprint groups (cross-source)
        cursor = self.conn.execute("""
            SELECT measure_fingerprint, COUNT(*) as cnt, GROUP_CONCAT(DISTINCT data_source) as sources
            FROM measures WHERE is_active = 1 AND measure_fingerprint IS NOT NULL
            GROUP BY measure_fingerprint
            HAVING COUNT(*) > 1
        """)
        cross_source_groups = cursor.fetchall()
        uniqueness_checks['cross_source_duplicates'] = {
            'groups': len(cross_source_groups),
            'total_records': sum(r['cnt'] for r in cross_source_groups)
        }
        # Cross-source duplicates are expected if merged correctly
        multi_source = [r for r in cross_source_groups if ',' in (r['sources'] or '')]
        if multi_source:
            self.add_issue('uniqueness', 'info', 'measure_fingerprint',
                          f"Same measure from multiple sources", len(multi_source))

        # Check 3: Content hash duplicates
        cursor = self.conn.execute("""
            SELECT content_hash, COUNT(*) as cnt
            FROM measures WHERE is_active = 1 AND content_hash IS NOT NULL
            GROUP BY content_hash
            HAVING COUNT(*) > 1
        """)
        content_dups = cursor.fetchall()
        uniqueness_checks['content_duplicates'] = {
            'groups': len(content_dups),
            'total_records': sum(r['cnt'] for r in content_dups)
        }
        if content_dups:
            self.add_issue('uniqueness', 'warning', 'content_hash',
                          f"Identical content across records", len(content_dups))
            issues_found += 1

        # Check 4: Title + year + county duplicates
        cursor = self.conn.execute("""
            SELECT title, year, county, COUNT(*) as cnt
            FROM measures WHERE is_active = 1
            GROUP BY title, year, county
            HAVING COUNT(*) > 1
        """)
        title_dups = cursor.fetchall()
        uniqueness_checks['title_year_county_duplicates'] = {
            'groups': len(title_dups),
            'total_records': sum(r['cnt'] for r in title_dups)
        }
        if title_dups:
            self.add_issue('uniqueness', 'warning', 'title+year+county',
                          f"Same title/year/county combination", len(title_dups))
            issues_found += 1

        # Check 5: Properly marked duplicates
        cursor = self.conn.execute("""
            SELECT COUNT(*) FROM measures WHERE is_active = 0 AND is_duplicate = 1
        """)
        marked_dups = cursor.fetchone()[0]
        cursor = self.conn.execute("""
            SELECT COUNT(*) FROM measures WHERE is_active = 0
        """)
        total_inactive = cursor.fetchone()[0]
        uniqueness_checks['duplicate_handling'] = {
            'marked_duplicates': marked_dups,
            'total_inactive': total_inactive
        }

        # Print summary
        print(f"Active records: {total_active:,}")
        print(f"Fingerprint duplicates: {uniqueness_checks['fingerprint_duplicates']['duplicate_groups']} groups")
        print(f"Cross-source matches: {uniqueness_checks['cross_source_duplicates']['groups']} groups")
        print(f"Content duplicates: {uniqueness_checks['content_duplicates']['groups']} groups")
        print(f"Title/year/county duplicates: {uniqueness_checks['title_year_county_duplicates']['groups']} groups")
        print(f"Marked as duplicate: {marked_dups:,}")

        # Calculate score
        # Penalize fingerprint duplicates heavily, content duplicates moderately
        fingerprint_penalty = min(uniqueness_checks['fingerprint_duplicates']['total_duplicates'] * 5, 30)
        content_penalty = min(uniqueness_checks['content_duplicates']['groups'] * 0.5, 20)
        title_penalty = min(uniqueness_checks['title_year_county_duplicates']['groups'] * 0.2, 10)
        score = max(0, 100 - fingerprint_penalty - content_penalty - title_penalty)

        self.scores.append(QualityScore(
            dimension='uniqueness',
            score=round(score, 2),
            weight=0.10,
            issues_count=issues_found,
            critical_issues=critical_issues,
            warnings=issues_found - critical_issues,
            details=uniqueness_checks
        ))

        print(f"\nUniqueness Score: {score:.1f}/100")
        print()

    # =========================================================================
    # 5. TIMELINESS - Data freshness and coverage gaps
    # =========================================================================

    def evaluate_timeliness(self):
        """Evaluate data timeliness and coverage gaps."""
        print("5. TIMELINESS ANALYSIS")
        print("-" * 40)

        issues_found = 0
        timeliness_checks = {}
        current_year = datetime.now().year

        # Check 1: Year coverage
        cursor = self.conn.execute("""
            SELECT year, COUNT(*) as cnt
            FROM measures WHERE is_active = 1
            GROUP BY year
            ORDER BY year
        """)
        year_counts = {row['year']: row['cnt'] for row in cursor.fetchall()}

        # Find gaps
        years = sorted(year_counts.keys())
        min_year, max_year = min(years), max(years)
        expected_years = set(range(min_year, max_year + 1))
        missing_years = expected_years - set(years)
        timeliness_checks['year_coverage'] = {
            'min_year': min_year,
            'max_year': max_year,
            'total_years': len(years),
            'missing_years': sorted(missing_years),
            'year_distribution': year_counts
        }
        if missing_years:
            self.add_issue('timeliness', 'warning', 'year',
                          f"Coverage gaps: {sorted(missing_years)}", len(missing_years))
            issues_found += 1

        # Check 2: Recent data (last 5 years)
        recent_years = list(range(current_year - 4, current_year + 1))
        recent_coverage = {y: year_counts.get(y, 0) for y in recent_years}
        timeliness_checks['recent_coverage'] = recent_coverage

        # Check 3: Data freshness (updated_at)
        cursor = self.conn.execute("""
            SELECT MAX(updated_at), MIN(updated_at),
                   SUM(CASE WHEN updated_at > datetime('now', '-30 days') THEN 1 ELSE 0 END) as recent_updates
            FROM measures WHERE is_active = 1
        """)
        row = cursor.fetchone()
        timeliness_checks['freshness'] = {
            'most_recent_update': row[0],
            'oldest_update': row[1],
            'updated_last_30_days': row[2] or 0
        }

        # Check 4: Source last scrape times (from scraper_runs if available)
        try:
            cursor = self.conn.execute("""
                SELECT scraper_name, MAX(completed_at) as last_run
                FROM scraper_runs
                WHERE status = 'completed'
                GROUP BY scraper_name
            """)
            source_freshness = {row['scraper_name']: row['last_run'] for row in cursor.fetchall()}
            timeliness_checks['source_freshness'] = source_freshness
        except sqlite3.OperationalError:
            timeliness_checks['source_freshness'] = {}

        # Print summary
        print(f"Year range: {min_year} - {max_year} ({len(years)} years)")
        print(f"Missing years: {len(missing_years)} gaps")
        print(f"\nRecent coverage (last 5 years):")
        for year in recent_years:
            count = recent_coverage[year]
            bar = "█" * min(count // 20, 50)
            print(f"  {year}: {count:>5} {bar}")
        print(f"\nMost recent update: {timeliness_checks['freshness']['most_recent_update']}")
        print(f"Records updated (30 days): {timeliness_checks['freshness']['updated_last_30_days']:,}")

        # Calculate score
        # Base on: coverage completeness, recent year coverage, freshness
        coverage_score = (1 - len(missing_years) / max(len(expected_years), 1)) * 100
        recent_score = sum(1 for y, c in recent_coverage.items() if c > 0) / len(recent_years) * 100
        score = coverage_score * 0.6 + recent_score * 0.4

        self.scores.append(QualityScore(
            dimension='timeliness',
            score=round(score, 2),
            weight=0.10,
            issues_count=issues_found,
            critical_issues=0,
            warnings=issues_found,
            details=timeliness_checks
        ))

        print(f"\nTimeliness Score: {score:.1f}/100")
        print()

    # =========================================================================
    # 6. VALIDITY - Format and constraint validation
    # =========================================================================

    def evaluate_validity(self):
        """Evaluate data format and constraint validity."""
        print("6. VALIDITY ANALYSIS")
        print("-" * 40)

        issues_found = 0
        validity_checks = {}

        # Check 1: Measure ID formats
        cursor = self.conn.execute("""
            SELECT id, measure_id, county FROM measures
            WHERE is_active = 1 AND measure_id IS NOT NULL
        """)
        records = cursor.fetchall()
        invalid_measure_ids = []
        for row in records:
            mid = row['measure_id']
            county = row['county']

            # Statewide: PROP X, ACA X, SCA X, etc.
            # County: single letter or letter+number
            if county in ('Statewide', 'California'):
                if not re.match(r'^(PROP|ACA|SCA|AB|SB)\s*\d+[A-Z]?$', mid, re.I):
                    if not re.match(r'^\d+[A-Z]?$', mid):  # Just number
                        invalid_measure_ids.append(row['id'])
            else:
                # County measures: usually A, B, AA, A1, etc.
                if not re.match(r'^[A-Z]{1,3}\d*$', mid, re.I):
                    if not re.match(r'^\d+$', mid):  # Some are just numbers
                        invalid_measure_ids.append(row['id'])

        validity_checks['measure_id_format'] = {
            'checked': len(records),
            'invalid': len(invalid_measure_ids)
        }
        if len(invalid_measure_ids) > 100:
            self.add_issue('validity', 'info', 'measure_id',
                          f"Non-standard measure ID format", len(invalid_measure_ids),
                          invalid_measure_ids[:10])
            issues_found += 1

        # Check 2: URL formats
        cursor = self.conn.execute("""
            SELECT id, source_url, pdf_url FROM measures
            WHERE is_active = 1 AND (source_url IS NOT NULL OR pdf_url IS NOT NULL)
        """)
        records = cursor.fetchall()
        invalid_urls = []
        url_pattern = re.compile(r'^https?://[^\s]+$')
        for row in records:
            for url in [row['source_url'], row['pdf_url']]:
                if url and not url_pattern.match(url):
                    invalid_urls.append(row['id'])
                    break

        validity_checks['url_format'] = {
            'checked': len(records),
            'invalid': len(invalid_urls)
        }
        if invalid_urls:
            self.add_issue('validity', 'warning', 'url',
                          f"Invalid URL format", len(invalid_urls),
                          invalid_urls[:10])
            issues_found += 1

        # Check 3: Vote threshold values
        cursor = self.conn.execute("""
            SELECT vote_threshold, COUNT(*) as cnt
            FROM measures WHERE is_active = 1 AND vote_threshold IS NOT NULL
            GROUP BY vote_threshold
        """)
        threshold_values = {row['vote_threshold']: row['cnt'] for row in cursor.fetchall()}
        valid_thresholds = {'50%', '55%', '66.67%', '2/3'}
        invalid_thresholds = set(threshold_values.keys()) - valid_thresholds
        validity_checks['vote_threshold_values'] = {
            'values': threshold_values,
            'invalid': list(invalid_thresholds)
        }
        if invalid_thresholds:
            self.add_issue('validity', 'warning', 'vote_threshold',
                          f"Non-standard vote threshold: {invalid_thresholds}",
                          sum(threshold_values[t] for t in invalid_thresholds))
            issues_found += 1

        # Check 4: passed field values (should be 0, 1, or NULL)
        cursor = self.conn.execute("""
            SELECT DISTINCT passed FROM measures WHERE is_active = 1
        """)
        passed_values = [row[0] for row in cursor.fetchall()]
        invalid_passed = [v for v in passed_values if v not in (0, 1, None)]
        validity_checks['passed_values'] = {
            'values': passed_values,
            'invalid': invalid_passed
        }
        if invalid_passed:
            self.add_issue('validity', 'warning', 'passed',
                          f"Invalid passed values: {invalid_passed}",
                          len(invalid_passed))
            issues_found += 1

        # Check 5: Data source enum
        cursor = self.conn.execute("""
            SELECT DISTINCT data_source FROM measures WHERE is_active = 1
        """)
        sources = [row[0] for row in cursor.fetchall()]
        validity_checks['data_sources'] = {'values': sources}

        # Print summary
        print(f"Measure ID format: {validity_checks['measure_id_format']['invalid']} non-standard")
        print(f"URL format: {validity_checks['url_format']['invalid']} invalid")
        print(f"Vote thresholds: {list(threshold_values.keys())}")
        print(f"Passed values: {passed_values}")
        print(f"Data sources: {sources}")

        # Calculate score
        total_checks = len(records) + len(records)  # measure_id + url checks
        total_invalid = validity_checks['measure_id_format']['invalid'] + validity_checks['url_format']['invalid']
        # Don't penalize too heavily for non-standard measure IDs
        score = max(0, 100 - (total_invalid / max(total_checks, 1)) * 200)

        self.scores.append(QualityScore(
            dimension='validity',
            score=round(min(score, 100), 2),
            weight=0.10,
            issues_count=issues_found,
            critical_issues=0,
            warnings=issues_found,
            details=validity_checks
        ))

        print(f"\nValidity Score: {min(score, 100):.1f}/100")
        print()

    # =========================================================================
    # 7. SUMMARY QUALITY - AI-generated content analysis
    # =========================================================================

    def evaluate_summary_quality(self):
        """Evaluate quality of AI-generated summaries."""
        print("7. SUMMARY QUALITY ANALYSIS")
        print("-" * 40)

        issues_found = 0
        summary_checks = {}

        # Get all summaries
        cursor = self.conn.execute("""
            SELECT id, summary_text, title
            FROM measures
            WHERE is_active = 1 AND summary_text IS NOT NULL AND summary_text != ''
        """)
        summaries = cursor.fetchall()
        total_with_summary = len(summaries)

        cursor = self.conn.execute("SELECT COUNT(*) FROM measures WHERE is_active = 1")
        total_active = cursor.fetchone()[0]

        summary_checks['coverage'] = {
            'with_summary': total_with_summary,
            'without_summary': total_active - total_with_summary,
            'coverage_pct': round(total_with_summary / total_active * 100, 2) if total_active > 0 else 0
        }

        # Quality checks - patterns that indicate AI didn't follow instructions
        # Note: "This measure..." is a VALID summary start, not a preamble
        preamble_patterns = [
            r'^here is', r'^this is a summary', r'^summary:', r'^the summary',
            r'^in summary', r'^to summarize', r'^certainly', r'^sure,',
            r'^i\'d be happy', r'^here\'s a'
        ]

        quality_issues = {
            'too_short': [],
            'too_long': [],
            'has_preamble': [],
            'ends_badly': [],
            'has_bullets': [],
            'mentions_vote': [],
            'too_many_sentences': [],
            'duplicates_title': []
        }

        lengths = []
        word_counts = []

        for row in summaries:
            summary = row['summary_text']
            title = row['title'] or ''
            mid = row['id']

            lengths.append(len(summary))
            word_counts.append(len(summary.split()))

            # Check quality issues
            if len(summary) < 50:
                quality_issues['too_short'].append(mid)
            if len(summary) > 500:
                quality_issues['too_long'].append(mid)
            if any(re.match(p, summary.lower()) for p in preamble_patterns):
                quality_issues['has_preamble'].append(mid)
            if summary.rstrip() and summary.rstrip()[-1] not in '.?!"\')':
                quality_issues['ends_badly'].append(mid)
            if '•' in summary or '\n-' in summary or '\n*' in summary:
                quality_issues['has_bullets'].append(mid)
            if 'vote yes' in summary.lower() or 'vote no' in summary.lower():
                quality_issues['mentions_vote'].append(mid)
            if summary.count('. ') > 4:
                quality_issues['too_many_sentences'].append(mid)
            # Check if summary is just the title repeated
            if summary.strip().lower() == title.strip().lower()[:len(summary)].lower():
                quality_issues['duplicates_title'].append(mid)

        summary_checks['quality_issues'] = {k: len(v) for k, v in quality_issues.items()}
        summary_checks['length_stats'] = {
            'min': min(lengths) if lengths else 0,
            'max': max(lengths) if lengths else 0,
            'avg': round(sum(lengths) / len(lengths), 1) if lengths else 0,
            'median': sorted(lengths)[len(lengths)//2] if lengths else 0
        }
        summary_checks['word_count_stats'] = {
            'min': min(word_counts) if word_counts else 0,
            'max': max(word_counts) if word_counts else 0,
            'avg': round(sum(word_counts) / len(word_counts), 1) if word_counts else 0
        }

        # Record issues
        for issue_type, ids in quality_issues.items():
            if ids:
                severity = 'warning' if issue_type in ['has_preamble', 'mentions_vote'] else 'info'
                self.add_issue('summary_quality', severity, 'summary_text',
                              f"Summary issue: {issue_type}", len(ids), ids[:5])
                issues_found += 1

        # Print summary
        print(f"Coverage: {summary_checks['coverage']['coverage_pct']}% ({total_with_summary:,}/{total_active:,})")
        print(f"\nLength statistics:")
        print(f"  Characters: min={summary_checks['length_stats']['min']}, "
              f"max={summary_checks['length_stats']['max']}, "
              f"avg={summary_checks['length_stats']['avg']}")
        print(f"  Words: min={summary_checks['word_count_stats']['min']}, "
              f"max={summary_checks['word_count_stats']['max']}, "
              f"avg={summary_checks['word_count_stats']['avg']}")
        print(f"\nQuality issues:")
        for issue, count in summary_checks['quality_issues'].items():
            if count > 0:
                print(f"  {issue}: {count}")

        # Calculate score
        coverage_score = summary_checks['coverage']['coverage_pct']
        total_issues = sum(summary_checks['quality_issues'].values())
        issue_rate = total_issues / total_with_summary if total_with_summary > 0 else 0
        quality_score = max(0, 100 - issue_rate * 100)
        score = coverage_score * 0.6 + quality_score * 0.4

        self.scores.append(QualityScore(
            dimension='summary_quality',
            score=round(score, 2),
            weight=0.10,
            issues_count=issues_found,
            critical_issues=0,
            warnings=issues_found,
            details=summary_checks
        ))

        print(f"\nSummary Quality Score: {score:.1f}/100")
        print()

    # =========================================================================
    # 8. FINANCE DATA QUALITY
    # =========================================================================

    def evaluate_finance_quality(self):
        """Evaluate campaign finance data quality."""
        print("8. FINANCE DATA QUALITY")
        print("-" * 40)

        if not self.finance_conn:
            print("Finance database not available - skipping")
            self.scores.append(QualityScore(
                dimension='finance_quality',
                score=100.0,
                weight=0.05,
                issues_count=0,
                critical_issues=0,
                warnings=0,
                details={'status': 'not_available'}
            ))
            print()
            return

        issues_found = 0
        finance_checks = {}

        # Check 1: Measure coverage
        cursor = self.finance_conn.execute("""
            SELECT COUNT(DISTINCT measure_id) FROM measure_finance_summary
        """)
        measures_with_finance = cursor.fetchone()[0]

        cursor = self.conn.execute("""
            SELECT COUNT(*) FROM measures
            WHERE is_active = 1 AND county = 'Statewide' AND year >= 2016
        """)
        statewide_recent = cursor.fetchone()[0]

        finance_checks['coverage'] = {
            'measures_with_finance': measures_with_finance,
            'statewide_since_2016': statewide_recent,
            'coverage_pct': round(measures_with_finance / statewide_recent * 100, 1) if statewide_recent > 0 else 0
        }

        # Check 2: Transaction data
        cursor = self.finance_conn.execute("""
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN amount IS NULL OR amount = 0 THEN 1 ELSE 0 END) as zero_amounts,
                   SUM(CASE WHEN date IS NULL THEN 1 ELSE 0 END) as missing_dates
            FROM transaction_record
        """)
        row = cursor.fetchone()
        finance_checks['transactions'] = {
            'total': row['total'],
            'zero_amounts': row['zero_amounts'],
            'missing_dates': row['missing_dates']
        }

        # Check 3: Committee data
        cursor = self.finance_conn.execute("""
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN name IS NULL OR name = '' THEN 1 ELSE 0 END) as missing_names
            FROM committee
        """)
        row = cursor.fetchone()
        finance_checks['committees'] = {
            'total': row['total'],
            'missing_names': row['missing_names']
        }

        # Check 4: Summary data integrity
        cursor = self.finance_conn.execute("""
            SELECT measure_id, stance, total_receipts
            FROM measure_finance_summary
            WHERE total_receipts < 0
        """)
        negative_totals = cursor.fetchall()
        finance_checks['data_integrity'] = {
            'negative_totals': len(negative_totals)
        }
        if negative_totals:
            self.add_issue('finance_quality', 'warning', 'total_receipts',
                          f"Negative total receipts", len(negative_totals))
            issues_found += 1

        # Print summary
        print(f"Measures with finance data: {measures_with_finance}")
        print(f"Coverage of statewide (2016+): {finance_checks['coverage']['coverage_pct']}%")
        print(f"Total transactions: {finance_checks['transactions']['total']:,}")
        print(f"Committees: {finance_checks['committees']['total']}")
        print(f"Data integrity issues: {finance_checks['data_integrity']['negative_totals']}")

        # Calculate score
        score = 100
        if finance_checks['transactions']['zero_amounts']:
            score -= min(finance_checks['transactions']['zero_amounts'] / finance_checks['transactions']['total'] * 50, 20)
        if finance_checks['data_integrity']['negative_totals']:
            score -= 10

        self.scores.append(QualityScore(
            dimension='finance_quality',
            score=round(max(score, 0), 2),
            weight=0.05,
            issues_count=issues_found,
            critical_issues=0,
            warnings=issues_found,
            details=finance_checks
        ))

        print(f"\nFinance Quality Score: {score:.1f}/100")
        print()

    # =========================================================================
    # 9. RECOMMENDATIONS QUALITY
    # =========================================================================

    def evaluate_recommendations(self):
        """Evaluate recommendation/embedding data quality."""
        print("9. RECOMMENDATIONS QUALITY")
        print("-" * 40)

        issues_found = 0
        rec_checks = {}

        if not EMBEDDINGS_PATH.exists():
            print("Embeddings metadata not available - skipping")
            self.scores.append(QualityScore(
                dimension='recommendations',
                score=100.0,
                weight=0.05,
                issues_count=0,
                critical_issues=0,
                warnings=0,
                details={'status': 'not_available'}
            ))
            print()
            return

        with open(EMBEDDINGS_PATH, 'r') as f:
            metadata = json.load(f)

        cursor = self.conn.execute("SELECT COUNT(*) FROM measures WHERE is_active = 1")
        total_active = cursor.fetchone()[0]

        # Get measure IDs with recommendations (neighbors key in metadata)
        neighbors = metadata.get('neighbors', {})
        measure_ids = metadata.get('measure_ids', [])
        measures_with_recs = len(neighbors)
        rec_checks['coverage'] = {
            'with_recommendations': measures_with_recs,
            'total_active': total_active,
            'total_in_embeddings': len(measure_ids),
            'coverage_pct': round(measures_with_recs / total_active * 100, 2) if total_active > 0 else 0
        }

        # Check for self-references
        self_refs = 0
        invalid_refs = 0
        low_scores = 0

        # Get all measure IDs that are in the embeddings (they use source measure_id format)
        # The embeddings use CEDA-style IDs like "199800001" not database auto-increment IDs
        embedding_ids = set(measure_ids)

        for measure_id, recs in neighbors.items():
            for rec in recs:
                rec_id = str(rec.get('measure_id', ''))
                score = rec.get('score', 0)

                if rec_id == measure_id:
                    self_refs += 1
                if rec_id not in embedding_ids:
                    invalid_refs += 1
                if score < 0.5:
                    low_scores += 1

        rec_checks['quality'] = {
            'self_references': self_refs,
            'invalid_references': invalid_refs,
            'low_similarity_scores': low_scores
        }

        if self_refs > 0:
            self.add_issue('recommendations', 'warning', 'recommendations',
                          f"Self-references in recommendations", self_refs)
            issues_found += 1

        if invalid_refs > 0:
            self.add_issue('recommendations', 'warning', 'recommendations',
                          f"References to inactive/missing measures", invalid_refs)
            issues_found += 1

        # Print summary
        print(f"Coverage: {rec_checks['coverage']['coverage_pct']}% ({measures_with_recs:,}/{total_active:,})")
        print(f"Self-references: {self_refs}")
        print(f"Invalid references: {invalid_refs}")
        print(f"Low similarity scores (<0.5): {low_scores}")

        # Calculate score
        coverage_score = rec_checks['coverage']['coverage_pct']
        quality_penalty = (self_refs + invalid_refs) * 2
        score = max(0, coverage_score - quality_penalty)

        self.scores.append(QualityScore(
            dimension='recommendations',
            score=round(score, 2),
            weight=0.05,
            issues_count=issues_found,
            critical_issues=0,
            warnings=issues_found,
            details=rec_checks
        ))

        print(f"\nRecommendations Quality Score: {score:.1f}/100")
        print()

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def _get_sample_ids(self, where_clause: str, limit: int = 5) -> List[int]:
        """Get sample IDs matching a condition."""
        try:
            cursor = self.conn.execute(f"""
                SELECT id FROM measures
                WHERE is_active = 1 AND ({where_clause})
                LIMIT {limit}
            """)
            return [row[0] for row in cursor.fetchall()]
        except sqlite3.Error:
            return []

    def calculate_overall_score(self) -> float:
        """Calculate weighted overall score."""
        if not self.scores:
            return 0.0

        weighted_sum = sum(s.score * s.weight for s in self.scores)
        total_weight = sum(s.weight for s in self.scores)
        return round(weighted_sum / total_weight, 2) if total_weight > 0 else 0.0

    def generate_report(self, overall_score: float) -> Dict[str, Any]:
        """Generate comprehensive report."""
        print("=" * 80)
        print("OVERALL DATA QUALITY REPORT")
        print("=" * 80)
        print()

        # Score summary
        print("DIMENSION SCORES:")
        print(f"{'Dimension':<25} {'Score':>8} {'Weight':>8} {'Issues':>8} {'Critical':>10}")
        print("-" * 65)
        for s in self.scores:
            print(f"{s.dimension:<25} {s.score:>7.1f}% {s.weight:>7.0%} {s.issues_count:>8} {s.critical_issues:>10}")
        print("-" * 65)
        print(f"{'OVERALL':<25} {overall_score:>7.1f}%")
        print()

        # Grade
        grade = self._get_grade(overall_score)
        print(f"OVERALL GRADE: {grade}")
        print()

        # Critical issues summary
        critical_issues = [i for i in self.issues if i.severity == 'critical']
        if critical_issues:
            print("CRITICAL ISSUES:")
            for issue in critical_issues:
                print(f"  - [{issue.dimension}] {issue.field}: {issue.description}")
                if issue.sample_ids:
                    print(f"    Sample IDs: {issue.sample_ids}")
            print()

        # Warnings summary
        warnings = [i for i in self.issues if i.severity == 'warning']
        if warnings:
            print(f"WARNINGS ({len(warnings)}):")
            for issue in warnings[:10]:  # Show top 10
                print(f"  - [{issue.dimension}] {issue.field}: {issue.description} ({issue.affected_count} affected)")
            if len(warnings) > 10:
                print(f"  ... and {len(warnings) - 10} more")
            print()

        # Build report dict
        report = {
            'timestamp': datetime.now().isoformat(),
            'overall_score': overall_score,
            'grade': grade,
            'scores': [asdict(s) for s in self.scores],
            'issues': [asdict(i) for i in self.issues],
            'summary': {
                'total_issues': len(self.issues),
                'critical_issues': len(critical_issues),
                'warnings': len(warnings),
                'info': len([i for i in self.issues if i.severity == 'info'])
            }
        }

        return report

    def _get_grade(self, score: float) -> str:
        """Convert score to letter grade."""
        if score >= 95:
            return "A+"
        elif score >= 90:
            return "A"
        elif score >= 85:
            return "A-"
        elif score >= 80:
            return "B+"
        elif score >= 75:
            return "B"
        elif score >= 70:
            return "B-"
        elif score >= 65:
            return "C+"
        elif score >= 60:
            return "C"
        elif score >= 55:
            return "C-"
        elif score >= 50:
            return "D"
        else:
            return "F"

    def export_report(self, report: Dict[str, Any], path: Path):
        """Export report to JSON."""
        with open(path, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"Report exported to: {path}")

    def close(self):
        """Close database connections."""
        self.conn.close()
        if self.finance_conn:
            self.finance_conn.close()


def main():
    parser = argparse.ArgumentParser(description="Evaluate CalBallot data quality")
    parser.add_argument("--export", action="store_true", help="Export report to JSON")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = parser.parse_args()

    evaluator = DataQualityEvaluator(verbose=args.verbose)

    try:
        report = evaluator.evaluate_all()

        if args.export:
            evaluator.export_report(report, REPORT_PATH)

    finally:
        evaluator.close()


if __name__ == "__main__":
    main()
