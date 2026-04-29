#!/usr/bin/env python3
"""
Ingest CA rows from the merged NCSL/Ballotpedia historical CSV into
ca_historical_measures.

Source CSV: ballot_measures_combined.csv (NCSL + Ballotpedia, 1902-2020,
all US states). Filters to st='CA', applies the column mappings and
derivations from context/vgp_historical_data_spec.md, and replaces any
prior ingest from this dataset.

Usage:
    python scripts/ingest_ca_historical.py --csv /path/to/ballot_measures_combined.csv
    python scripts/ingest_ca_historical.py --csv /path/to/csv --dry-run
"""
import argparse
import logging
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import DB_PATH

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

SOURCE_TAG = 'NCSL_Ballotpedia_Combined'

DEFAULT_CSV = Path(r"G:\My Drive\Grad School\Research\policy_learning\data\cleaned\ballot_measures_combined.csv")


def clean_type_string(s):
    """Strip the stray Unicode boundary characters seen in the `type` field."""
    if s is None:
        return None
    s = str(s)
    # Strip non-alphanumeric leading/trailing chars
    s = re.sub(r'^[^A-Za-z0-9]+', '', s)
    s = re.sub(r'[^A-Za-z0-9]+$', '', s)
    return s.strip() or None


def derive_is_marriage(description) -> int:
    """Spec rule: text-search the description for marriage + same-sex variants."""
    if not description:
        return 0
    d = str(description).lower()
    has_marriage_concept = (
        'marriage' in d or 'civil union' in d or 'domestic partner' in d
    )
    has_orientation = (
        'same' in d and 'sex' in d
    ) or 'gay' in d or 'homosexual' in d
    return 1 if (has_marriage_concept and has_orientation) else 0


def to_int_or_none(v):
    """Pandas may give floats for nullable ints; coerce to int or None."""
    if v is None:
        return None
    try:
        if v != v:  # NaN check
            return None
    except TypeError:
        pass
    try:
        return int(v)
    except (ValueError, TypeError):
        return None


def to_float_or_none(v):
    if v is None:
        return None
    try:
        f = float(v)
        if f != f:  # NaN
            return None
        return f
    except (ValueError, TypeError):
        return None


def to_bool_int(v):
    """1/0 (with NULL passthrough) for SQLite BOOLEAN columns."""
    if v is None:
        return 0
    try:
        if v != v:
            return 0
    except TypeError:
        pass
    return 1 if v == 1 or v is True else 0


def transform_row(row) -> dict:
    """Transform one CSV row into the ca_historical_measures schema."""
    pct_yes = to_float_or_none(row.get('pctyesvotes'))
    margin = (pct_yes - 50.0) if pct_yes is not None else None

    measure_type = clean_type_string(row.get('type'))
    election_type = clean_type_string(row.get('electiontype'))
    description = row.get('ballotdescrip')

    return {
        'ballot_name': row.get('ballotname'),
        'year': to_int_or_none(row.get('year')),
        'description': description,
        'pct_yes': pct_yes,
        'passed': to_int_or_none(row.get('passed')),
        'measure_type': measure_type,
        'election_type': election_type,
        'is_marijuana': to_bool_int(row.get('drug')),
        'is_gambling': to_bool_int(row.get('gambling_lottery')),
        'is_abortion': to_bool_int(row.get('abort')),
        'is_marriage': derive_is_marriage(description),
        'is_tax': to_bool_int(row.get('tax_rev')),
        'is_education': 1 if (to_bool_int(row.get('ed_prek12')) or
                              to_bool_int(row.get('ed_higher'))) else 0,
        'is_health': to_bool_int(row.get('health')),
        'is_elections': to_bool_int(row.get('elections')),
        'is_criminal': to_bool_int(row.get('criminal')),
        'is_environment': to_bool_int(row.get('environ')),
        'margin': margin,
        'is_close': 1 if margin is not None and abs(margin) < 10 else 0,
        'is_very_close': 1 if margin is not None and abs(margin) < 5 else 0,
        'is_initiative': 1 if measure_type and 'initiative' in measure_type.lower() else 0,
        'is_referendum': 1 if measure_type and 'referendum' in measure_type.lower() else 0,
        'source_dataset': SOURCE_TAG,
    }


INSERT_SQL = """
INSERT INTO ca_historical_measures (
    ballot_name, year, description, pct_yes, passed,
    measure_type, election_type,
    is_marijuana, is_gambling, is_abortion, is_marriage, is_tax,
    is_education, is_health, is_elections, is_criminal, is_environment,
    margin, is_close, is_very_close, is_initiative, is_referendum,
    source_dataset
) VALUES (
    :ballot_name, :year, :description, :pct_yes, :passed,
    :measure_type, :election_type,
    :is_marijuana, :is_gambling, :is_abortion, :is_marriage, :is_tax,
    :is_education, :is_health, :is_elections, :is_criminal, :is_environment,
    :margin, :is_close, :is_very_close, :is_initiative, :is_referendum,
    :source_dataset
)
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--csv', type=Path, default=DEFAULT_CSV)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--keep-mock', action='store_true',
                        help="Don't delete MOCK_DATA rows (default: delete them)")
    args = parser.parse_args()

    if not args.csv.exists():
        logger.error("CSV not found: %s", args.csv)
        return 1

    import pandas as pd
    logger.info("Reading %s", args.csv)
    df = pd.read_csv(args.csv)
    logger.info("Loaded %d total rows", len(df))

    ca = df[df['st'] == 'CA'].copy()
    logger.info("CA subset: %d rows (years %s-%s)",
                len(ca), int(ca['year'].min()), int(ca['year'].max()))

    records = [transform_row(row) for _, row in ca.iterrows()]
    null_pct = sum(1 for r in records if r['pct_yes'] is None)
    null_passed = sum(1 for r in records if r['passed'] is None)
    logger.info("Transformed: %d records (%d null pct_yes, %d null passed)",
                len(records), null_pct, null_passed)

    if args.dry_run:
        logger.info("Dry run. Sample transformed records:")
        for r in records[:3]:
            logger.info("  %s", r)
        return 0

    conn = sqlite3.connect(str(DB_PATH))
    try:
        # Replace any prior ingest from this source
        cur = conn.execute(
            "DELETE FROM ca_historical_measures WHERE source_dataset = ?",
            (SOURCE_TAG,),
        )
        logger.info("Removed %d prior rows tagged %s", cur.rowcount, SOURCE_TAG)

        if not args.keep_mock:
            cur = conn.execute(
                "DELETE FROM ca_historical_measures WHERE source_dataset = 'MOCK_DATA'"
            )
            logger.info("Removed %d MOCK_DATA rows", cur.rowcount)

        conn.executemany(INSERT_SQL, records)
        conn.commit()
        logger.info("Inserted %d rows tagged %s", len(records), SOURCE_TAG)
    finally:
        conn.close()

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
