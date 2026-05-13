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


V3_OBJECTS = [
    # (object_type, object_name) — order matters: views first, then
    # indexes, then tables, to satisfy SQLite dependency resolution
    ("view", "finance_summary_total"),
    ("view", "finance_top_donors_total"),
    ("view", "finance_timeline_weekly_total"),
    ("index", "idx_flow_source_row"),
    ("index", "idx_flow_source_form"),
    ("index", "idx_flow_accepted_campaign_stance_type"),
    ("index", "idx_flow_accepted_measure_stance"),
    ("index", "idx_flow_accepted_type_date"),
    ("index", "idx_flow_dedupe"),
    ("index", "idx_flow_quarantine"),
    ("index", "idx_summary_bytype_campaign_stance"),
    ("index", "idx_summary_bytype_measure_stance"),
    ("index", "idx_topdonors_bytype_amount"),
    ("index", "idx_topdonors_bytype_measure"),
    ("index", "idx_timeline_bytype_measure"),
    ("table", "finance_timeline_weekly_by_type"),
    ("table", "finance_top_donors_by_type"),
    ("table", "finance_summary_by_type"),
    ("table", "finance_flow_v3"),
]


def reset_db(db_path: Path, verbose: bool = True) -> None:
    """Drop all v3 objects so a subsequent init_db applies fresh DDL.

    Codex round-4: CREATE TABLE IF NOT EXISTS leaves stale columns in
    place if the schema changes. --reset gives us a clean slate during
    dev. Safe to use in Phase 1 because no real data lives in v3 yet.
    Refuse to run if finance_flow_v3 has rows, to prevent accidental
    data loss after Phase 2+.
    """
    if not db_path.exists():
        if verbose:
            print(f"Reset: {db_path} does not exist, nothing to drop")
        return
    con = sqlite3.connect(str(db_path))
    try:
        # Safety: refuse to reset a populated v3 DB
        try:
            row_count = con.execute(
                "SELECT COUNT(*) FROM finance_flow_v3"
            ).fetchone()[0]
        except sqlite3.OperationalError:
            row_count = 0
        if row_count > 0:
            raise SystemExit(
                f"refuse to --reset: finance_flow_v3 has {row_count} rows. "
                f"Drop the DB file manually if you really mean it."
            )
        cur = con.cursor()
        cur.execute("BEGIN")
        for obj_type, obj_name in V3_OBJECTS:
            cur.execute(f"DROP {obj_type.upper()} IF EXISTS {obj_name}")
            if verbose:
                print(f"  dropped {obj_type} {obj_name}")
        con.commit()
    finally:
        con.close()


def _split_sql_statements(sql: str) -> list[str]:
    """Split a SQL script into individual statements on ';' boundaries.

    Tolerates SQL comments (`-- ...`) but doesn't handle ';' inside
    string literals. Our schema.sql has no string literals so this is
    safe. If schema.sql grows literals, switch to sqlparse.
    """
    statements = []
    buf = []
    for line in sql.splitlines():
        stripped = line.strip()
        # Drop full-line comments and blank lines from the buffer
        if not stripped or stripped.startswith("--"):
            continue
        buf.append(line)
        if stripped.endswith(";"):
            statements.append("\n".join(buf).strip())
            buf = []
    if buf:  # trailing partial statement
        tail = "\n".join(buf).strip()
        if tail:
            statements.append(tail)
    return statements


def init_db(db_path: Path, schema_path: Path, verbose: bool = True) -> dict:
    """Apply the schema to db_path. Returns a small dict of stats.

    Codex round-4: applies statements individually inside an explicit
    transaction. SQLite supports transactional DDL (CREATE/DROP), so a
    failure mid-script rolls back cleanly instead of leaving a half-
    initialized DB.
    """
    if not schema_path.exists():
        raise SystemExit(f"Schema file missing: {schema_path}")
    sql = schema_path.read_text(encoding="utf-8")
    statements = _split_sql_statements(sql)

    db_path.parent.mkdir(parents=True, exist_ok=True)
    pre_existed = db_path.exists()

    # isolation_level=None disables Python's implicit transaction
    # management; we run BEGIN/COMMIT ourselves
    con = sqlite3.connect(str(db_path), isolation_level=None)
    try:
        cur = con.cursor()
        cur.execute("BEGIN")
        try:
            for stmt in statements:
                cur.execute(stmt)
        except Exception:
            cur.execute("ROLLBACK")
            raise
        cur.execute("COMMIT")

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
    parser.add_argument("--reset", action="store_true",
                        help="Drop all v3 objects before applying "
                             "schema (refuses if finance_flow_v3 has "
                             "any rows)")
    args = parser.parse_args()

    db_path = Path(args.db)
    if args.reset:
        reset_db(db_path, verbose=not args.quiet)

    init_db(db_path, Path(args.schema), verbose=not args.quiet)


if __name__ == "__main__":
    main()
