"""Trace test verifier — Codex round-10 source-row-anchored checks.

Loads data/CalAccess/ie_trace_tests.json and for each entry, finds
the row in finance_flow_v3 keyed by (source_table, source_form_type,
filing_id, source_line_item, source_tran_id) and asserts the
expected fields match. These are the manual-eyeball backstop for
the kind of attribution-logic bugs that shared-code reconciles
miss (e.g. the round-11 AG-queue misattribution surfaced).

Usage:
    python scripts/v3/verify_traces.py
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from v3 import lib
else:
    from . import lib


TRACES_PATH = Path("data/CalAccess/ie_trace_tests.json")
PENNY = 0.005


def _query_row(con: sqlite3.Connection, anchor: dict) -> dict | None:
    """Find a unique row matching the anchor tuple."""
    where = []
    params = []
    for field, val in anchor.items():
        if val is None:
            where.append(f"{field} IS NULL")
        else:
            where.append(f"{field} = ?")
            params.append(val)
    sql = "SELECT * FROM finance_flow_v3 WHERE " + " AND ".join(where)
    cur = con.cursor()
    cur.row_factory = sqlite3.Row
    rows = list(cur.execute(sql, params))
    if not rows:
        return None
    if len(rows) > 1:
        raise SystemExit(
            f"anchor matched {len(rows)} rows (should be 1): {anchor}"
        )
    return dict(rows[0])


def _check(label: str, ok: bool, msg: str = "") -> int:
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {label}")
    if msg and not ok:
        for line in msg.splitlines():
            print(f"         {line}")
    return 0 if ok else 1


def verify_one(con: sqlite3.Connection, name: str, entry: dict) -> int:
    print(f"\n=== {name} ===")
    anchor = entry["anchor"]
    expected = entry["expected"]
    row = _query_row(con, anchor)
    if row is None:
        return _check(
            f"row found for anchor {anchor}",
            False,
            "no row matched the anchor",
        )

    failures = 0
    for field, want in expected.items():
        got = row.get(field)
        if field == "amount":
            if want is None and got is None:
                ok = True
            elif want is not None and got is not None:
                ok = abs(float(got) - float(want)) < PENNY
            else:
                ok = False
            failures += _check(
                f"{field}: expected={want} got={got}",
                ok,
                f"diff > ${PENNY}" if not ok else "",
            )
        else:
            ok = (got == want)
            failures += _check(
                f"{field}: expected={want!r} got={got!r}", ok,
            )
    return failures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--traces", default=str(TRACES_PATH))
    parser.add_argument("--v3-db", default=str(lib.V3_DB))
    args = parser.parse_args()

    traces_path = Path(args.traces)
    if not traces_path.exists():
        raise SystemExit(f"Missing traces file: {traces_path}")
    raw = json.loads(traces_path.read_text(encoding="utf-8"))
    traces = {k: v for k, v in raw.items() if not k.startswith("_")}

    con = sqlite3.connect(str(args.v3_db))
    entries_failed = 0
    field_failures_total = 0
    try:
        for name, entry in traces.items():
            field_failures = verify_one(con, name, entry)
            field_failures_total += field_failures
            if field_failures > 0:
                entries_failed += 1
    finally:
        con.close()

    entries_passed = len(traces) - entries_failed
    print()
    print(f"=== Trace verification: "
          f"{entries_passed}/{len(traces)} entries passed "
          f"({field_failures_total} field failures across "
          f"{entries_failed} failed entries) ===")
    sys.exit(0 if entries_failed == 0 else 1)


if __name__ == "__main__":
    main()
