#!/usr/bin/env python3
"""
One-shot ingest of the freshly-downloaded CEDA 2015 file.

Parses just data/raw/ceda_data_2015.xlsx (NOT the other CEDA files), runs
the same dedup-aware ingest path used by the full pipeline. Existing rows
won't be touched — there are no 2015 CEDA rows in the DB today.

After ingest, runs the date->type imputation for the new rows so they get
classified the same way the rest of the corpus is.
"""
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

RAW_FILE = DATA_DIR / "raw" / "ceda_data_2015.xlsx"


def main():
    if not RAW_FILE.exists():
        logger.error("Not found: %s", RAW_FILE)
        return 1

    # Parse only this one file. CEDAParser.parse_file() handles the
    # standardize + convert-to-BallotMeasure path including the election_date
    # fix we just shipped.
    parser = CEDAParser(RAW_FILE.parent)
    measures = parser.parse_file(RAW_FILE)
    for m in measures:
        m.data_source = "CEDA"
    logger.info("Parsed %d measures from %s", len(measures), RAW_FILE.name)

    if not measures:
        logger.error("Parser returned no measures.")
        return 1

    # Ingest via the same dedup-aware path the full pipeline uses
    sys.path.insert(0, str(Path(__file__).parent))
    from pipeline import ingest_measures

    # Use context manager so the transaction commits on success / rolls back
    # on exception. Database.close() alone does NOT commit.
    with Database(DB_PATH) as db:
        stats = ingest_measures(db, measures, dry_run=False)
    logger.info("Ingest stats: %s", stats)

    # Run date->type imputation for the newly-inserted 2015 rows
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
               AND year = 2015
               AND election_date IS NOT NULL
               AND (election_type IS NULL OR TRIM(election_type) = '')
        """)
        conn.execute("COMMIT")
        logger.info("Imputed election_type for %d new 2015 rows.", cur.rowcount)
    finally:
        conn.close()

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
