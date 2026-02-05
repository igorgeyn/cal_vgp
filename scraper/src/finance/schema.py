"""
Finance database schema for statewide proposition campaign finance data.

Separate SQLite database — does not modify the main ballot_measures.db.
"""
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent.parent / "data"
FINANCE_DB_PATH = DATA_DIR / "finance" / "finance_statewide.db"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS committee (
    committee_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    filer_type TEXT,
    source TEXT DEFAULT 'stub',
    last_updated TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS transaction_record (
    txn_id INTEGER PRIMARY KEY AUTOINCREMENT,
    committee_id TEXT NOT NULL REFERENCES committee(committee_id),
    date TEXT NOT NULL,
    amount REAL NOT NULL,
    txn_type TEXT DEFAULT 'monetary',
    donor_name_raw TEXT,
    donor_name_canon TEXT,
    donor_type TEXT,
    donor_sector TEXT,
    source TEXT DEFAULT 'stub',
    last_updated TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS measure_committee_link (
    measure_id TEXT NOT NULL,
    committee_id TEXT NOT NULL REFERENCES committee(committee_id),
    stance TEXT NOT NULL CHECK(stance IN ('support','oppose')),
    link_method TEXT DEFAULT 'stub',
    confidence REAL DEFAULT 1.0,
    source TEXT DEFAULT 'stub',
    last_updated TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (measure_id, committee_id)
);

CREATE TABLE IF NOT EXISTS measure_finance_summary (
    measure_id TEXT NOT NULL,
    stance TEXT NOT NULL CHECK(stance IN ('support','oppose')),
    total_receipts REAL DEFAULT 0,
    n_committees INTEGER DEFAULT 0,
    top5_share REAL,
    hhi REAL,
    last_updated TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (measure_id, stance)
);

CREATE TABLE IF NOT EXISTS measure_finance_timeline_weekly (
    measure_id TEXT NOT NULL,
    stance TEXT NOT NULL CHECK(stance IN ('support','oppose')),
    week_start TEXT NOT NULL,
    weekly_receipts REAL DEFAULT 0,
    cumulative_receipts REAL DEFAULT 0,
    last_updated TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (measure_id, stance, week_start)
);

CREATE TABLE IF NOT EXISTS measure_top_donors (
    measure_id TEXT NOT NULL,
    stance TEXT NOT NULL CHECK(stance IN ('support','oppose')),
    donor_name_canon TEXT NOT NULL,
    donor_type TEXT,
    donor_sector TEXT,
    total_amount REAL DEFAULT 0,
    last_updated TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (measure_id, stance, donor_name_canon)
);
"""
