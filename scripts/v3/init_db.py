"""Initialize / migrate the finance_statewide_v3.db schema.

Idempotent: reads scripts/v3/schema.sql and applies it. CREATE TABLE
statements use IF NOT EXISTS; indexes + views are dropped and recreated
each run so definitions can iterate during development.

Default path: scraper/data/finance/finance_statewide_v3.db
"""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_DB = REPO_ROOT / "scraper" / "data" / "finance" / "finance_statewide_v3.db"
SCHEMA_FILE = Path(__file__).parent / "schema.sql"


def init_db(db_path: Path, schema_path: Path, verbose: bool = True) -> dict:
    """Apply the schema to db_path. Returns a small dict of stats."""
    if not schema_path.exists():
        raise SystemExit(f"Schema file missing: {schema_path}")
    sql = schema_path.read_text(encoding="utf-8")

    db_path.parent.mkdir(parents=True, exist_ok=True)
    pre_existed = db_path.exists()

    con = sqlite3.connect(str(db_path))
    try:
        cur = con.cursor()
        # executescript handles multiple statements + DROP/CREATE patterns
        cur.executescript(sql)
        con.commit()

        # Inspect what landed
        tables = [r[0] for r in cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )]
        views = [r[0] for r in cur.execute(
            "SELECT name FROM sqlite_master WHERE type='view' ORDER BY name"
        )]
        indexes = [r[0] for r in cur.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='index' AND name NOT LIKE 'sqlite_%' "
            "ORDER BY name"
        )]
        flow_columns = [r[1] for r in cur.execute(
            "PRAGMA table_info(finance_flow_v3)"
        )]
        flow_row_count = cur.execute(
            "SELECT COUNT(*) FROM finance_flow_v3"
        ).fetchone()[0]
    finally:
        con.close()

    if verbose:
        print(f"DB:      {db_path}")
        print(f"         {'(updated)' if pre_existed else '(created)'}")
        print(f"Schema:  {schema_path}")
        print()
        print(f"Tables ({len(tables)}):")
        for t in tables:
            print(f"  - {t}")
        print(f"Views ({len(views)}):")
        for v in views:
            print(f"  - {v}")
        print(f"Indexes ({len(indexes)}):")
        for i in indexes:
            print(f"  - {i}")
        print()
        print(f"finance_flow_v3: {len(flow_columns)} columns, "
              f"{flow_row_count} rows")
        print(f"  columns: {', '.join(flow_columns)}")

    return {
        "db_path": str(db_path),
        "pre_existed": pre_existed,
        "tables": tables,
        "views": views,
        "indexes": indexes,
        "flow_columns": flow_columns,
        "flow_row_count": flow_row_count,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB),
                        help="Target SQLite DB path")
    parser.add_argument("--schema", default=str(SCHEMA_FILE),
                        help="Schema SQL file path")
    parser.add_argument("--quiet", action="store_true",
                        help="Suppress per-table listing")
    args = parser.parse_args()

    init_db(Path(args.db), Path(args.schema), verbose=not args.quiet)


if __name__ == "__main__":
    main()
