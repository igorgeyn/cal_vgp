#!/usr/bin/env python3
"""
Interactive DuckDB query tool for the ballot measures database.

Usage:
    python scripts/query.py                    # interactive REPL
    python scripts/query.py "SELECT ..."       # run a single query
    python scripts/query.py --csv "SELECT ..." # output as CSV
"""
import sys
import argparse
from pathlib import Path

try:
    import duckdb
except ImportError:
    print("Install duckdb first: pip install duckdb")
    sys.exit(1)

DB_PATH = Path(__file__).parent.parent / "data" / "ballot_measures.db"


def get_connection():
    con = duckdb.connect()
    con.execute("INSTALL sqlite; LOAD sqlite;")
    con.execute(f"ATTACH '{DB_PATH}' AS db (TYPE sqlite);")
    # Set default schema so you don't need 'db.' prefix
    con.execute("USE db;")
    return con


def run_query(con, sql, as_csv=False):
    try:
        result = con.execute(sql)
        df = result.fetchdf()
        if as_csv:
            print(df.to_csv(index=False))
        else:
            import pandas as pd
            pd.set_option('display.max_columns', None)
            pd.set_option('display.width', 200)
            pd.set_option('display.max_rows', 100)
            pd.set_option('display.max_colwidth', 60)
            print(df.to_string(index=False))
    except Exception as e:
        print(f"Error: {e}")


def interactive(con):
    print(f"DuckDB connected to {DB_PATH}")
    print(f"Tables: measures, measure_updates, scraper_runs, ca_historical_measures")
    print(f"Tip: no 'db.' prefix needed. Type 'quit' or Ctrl+C to exit.\n")

    # Show quick stats
    run_query(con, """
        SELECT
            COUNT(*) as total_rows,
            COUNT(*) FILTER (WHERE is_active=1 AND is_duplicate=0) as active,
            COUNT(DISTINCT year) as years,
            COUNT(DISTINCT county) as counties,
            MIN(year) as min_year,
            MAX(year) as max_year
        FROM measures
    """)
    print()

    while True:
        try:
            sql = input("sql> ").strip()
            if not sql:
                continue
            if sql.lower() in ("quit", "exit", "q"):
                break
            # Support multi-line: keep reading if line ends with \
            while sql.endswith("\\"):
                sql = sql[:-1] + "\n" + input("...> ").strip()
            run_query(con, sql)
        except (KeyboardInterrupt, EOFError):
            print()
            break


def main():
    parser = argparse.ArgumentParser(description="Query ballot measures with DuckDB")
    parser.add_argument("query", nargs="?", help="SQL query to run (omit for interactive mode)")
    parser.add_argument("--csv", action="store_true", help="Output as CSV")
    args = parser.parse_args()

    con = get_connection()

    if args.query:
        run_query(con, args.query, as_csv=args.csv)
    else:
        interactive(con)


if __name__ == "__main__":
    main()
