#!/usr/bin/env python3
"""
Surgical one-shot patch: re-read DATE from CEDA raw xlsx files (2022/2023/2024)
and update election_date for matching rows in the main DB whose date is null.

Background: the Excel-path parser at scraper/src/parsers/ceda.py was missing
election_date in its BallotMeasure constructor (now fixed forward-looking).
This script fills in the dates that were dropped during prior ingest, without
re-running the full ingest pipeline.

Match key: measure_id <-> MeasID (CEDA's row identifier; same string format
on both sides, e.g. '202400001').

After running this, the date->type imputation logic from earlier should be
re-run on the same rows to populate election_type. This script does that step
too as a follow-up, scoped to rows it just updated.
"""
import argparse
import logging
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import DB_PATH, DATA_DIR

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

RAW_DIR = DATA_DIR / "raw"
# Years to patch. Idempotent: re-running on already-patched years is a no-op
# because the UPDATE only fires when election_date IS NULL.
YEARS = [2011, 2022, 2023, 2024]


def collect_dates_from_xlsx(year: int) -> dict:
    """Return {measure_id: 'YYYY-MM-DD'} for the given year's CEDA file."""
    import pandas as pd
    path = RAW_DIR / f"ceda_data_{year}.xlsx"
    if not path.exists():
        logger.warning("Raw file not found: %s", path)
        return {}

    xl = pd.ExcelFile(path)
    # Find the Measures sheet (handles 'Measures 2024', 'Measures_2022', etc.)
    sheet = None
    for s in xl.sheet_names:
        if 'measure' in s.lower():
            sheet = s
            break
    if not sheet:
        logger.warning("No Measures sheet in %s", path.name)
        return {}

    df = pd.read_excel(xl, sheet_name=sheet)
    if 'MeasID' not in df.columns or 'DATE' not in df.columns:
        logger.warning("Expected columns missing in %s/%s. Have: %s",
                       path.name, sheet, list(df.columns))
        return {}

    dates = {}
    for _, row in df.iterrows():
        mid = row['MeasID']
        date = row['DATE']
        if pd.isna(mid) or pd.isna(date):
            continue
        # MeasID may be int or string; normalize
        mid_str = str(mid).strip()
        if mid_str.endswith('.0'):
            mid_str = mid_str[:-2]
        # DATE is a Timestamp; format as YYYY-MM-DD
        date_str = pd.Timestamp(date).strftime('%Y-%m-%d')
        dates[mid_str] = date_str

    logger.info("  %s: collected %d (measure_id -> date) pairs", path.name, len(dates))
    return dates


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--skip-impute', action='store_true',
                        help="Don't re-run election_type imputation on the patched rows")
    args = parser.parse_args()

    # Aggregate dates from all years
    all_dates = {}
    for year in YEARS:
        all_dates.update(collect_dates_from_xlsx(year))
    logger.info("Total (measure_id -> date) pairs from raw files: %d", len(all_dates))

    # Apply
    conn = sqlite3.connect(str(DB_PATH))
    try:
        # See how many DB rows we'd update
        cur = conn.execute("""
            SELECT COUNT(*) FROM measures
             WHERE data_source = 'CEDA'
               AND election_date IS NULL
               AND measure_id IS NOT NULL
        """)
        candidate_count = cur.fetchone()[0]
        logger.info("CEDA rows in DB with no election_date: %d", candidate_count)

        # How many of those will we be able to match?
        placeholders = ','.join('?' * len(all_dates))
        ids = list(all_dates.keys())
        cur = conn.execute(f"""
            SELECT COUNT(*) FROM measures
             WHERE data_source = 'CEDA'
               AND election_date IS NULL
               AND measure_id IN ({placeholders})
        """, ids)
        matched_count = cur.fetchone()[0]
        logger.info("Matchable: %d of %d (would patch)", matched_count, candidate_count)

        if args.dry_run:
            logger.info("Dry run; not writing.")
            return 0

        # Patch in a transaction
        conn.execute("BEGIN")
        rows_updated = 0
        for mid, date_str in all_dates.items():
            cur = conn.execute("""
                UPDATE measures SET election_date = ?
                 WHERE data_source = 'CEDA'
                   AND election_date IS NULL
                   AND measure_id = ?
            """, (date_str, mid))
            rows_updated += cur.rowcount
        conn.execute("COMMIT")
        logger.info("Patched %d rows with election_date.", rows_updated)

        # Follow-up: re-run date->type imputation for any of those rows that
        # still have null election_type (skipping any that already had type).
        if not args.skip_impute:
            conn.execute("BEGIN")
            cur = conn.execute("""
                UPDATE measures
                   SET election_type = LOWER(CASE strftime('%m', election_date)
                                          WHEN '11' THEN 'general'
                                          WHEN '03' THEN 'primary'
                                          WHEN '06' THEN 'primary'
                                          ELSE 'special'
                                        END),
                       election_type_imputed = 1
                 WHERE data_source = 'CEDA'
                   AND election_date IS NOT NULL
                   AND (election_type IS NULL OR TRIM(election_type) = '')
            """)
            imputed_count = cur.rowcount
            conn.execute("COMMIT")
            logger.info("Imputed election_type for %d newly-dated rows.", imputed_count)
    finally:
        conn.close()

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
