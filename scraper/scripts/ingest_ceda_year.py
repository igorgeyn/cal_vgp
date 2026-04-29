#!/usr/bin/env python3
"""
Ingest a single CEDA year file from data/raw/ceda_data_{year}.xlsx.

Generalized from ingest_ceda_2015.py — useful any time a missing CEDA year
is downloaded. Only processes the specified year; leaves other CEDA files
in raw/ untouched. Existing rows for that year are merged via the same
dedup-aware logic as the full pipeline (matching fingerprint -> update,
new rows -> insert).

Usage:
    python scripts/ingest_ceda_year.py --year 2011
    python scripts/ingest_ceda_year.py --year 2015
"""
import argparse
import logging
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import DB_PATH, DATA_DIR
from src.parsers.ceda import CEDAParser
from src.database.operations import Database

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--year', type=int, required=True,
                        help='CEDA year to ingest (file: ceda_data_{year}.xlsx)')
    args = parser.parse_args()

    raw_file = DATA_DIR / "raw" / f"ceda_data_{args.year}.xlsx"
    if not raw_file.exists():
        logger.error("Not found: %s", raw_file)
        return 1

    # Parse only this one file
    ceda = CEDAParser(raw_file.parent)
    measures = ceda.parse_file(raw_file)
    for m in measures:
        m.data_source = "CEDA"
    logger.info("Parsed %d measures from %s", len(measures), raw_file.name)

    if not measures:
        logger.error("Parser returned no measures.")
        return 1

    # Ingest via the same dedup-aware path the full pipeline uses
    sys.path.insert(0, str(Path(__file__).parent))
    from pipeline import ingest_measures

    with Database(DB_PATH) as db:
        stats = ingest_measures(db, measures, dry_run=False)
    logger.info("Ingest stats: %s", stats)

    # Run date->type imputation for newly-dated rows of this year
    conn = sqlite3.connect(str(DB_PATH))
    try:
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
               AND year = ?
               AND election_date IS NOT NULL
               AND (election_type IS NULL OR TRIM(election_type) = '')
        """, (args.year,))
        conn.execute("COMMIT")
        logger.info("Imputed election_type for %d %s rows.", cur.rowcount, args.year)
    finally:
        conn.close()

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
