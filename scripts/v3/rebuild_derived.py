"""Rebuild the materialized derived tables from finance_flow_v3.

The three derived tables are:
  - finance_summary_by_type
  - finance_top_donors_by_type
  - finance_timeline_weekly_by_type

Each phase that ingests new fact-table rows must call this script to
recompute the materialized aggregations. The aggregate VIEWs
(finance_*_total) read finance_flow_v3 directly and don't need a
rebuild.

Idempotent: each rebuild is a DELETE-then-INSERT inside one
transaction. Run after ingest_loans / ingest_inkind / ingest_ie.

Usage:
    python scripts/v3/rebuild_derived.py
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from v3 import lib
else:
    from . import lib


def rebuild_summary_by_type(cur: sqlite3.Cursor, verbose: bool) -> int:
    """Rebuild finance_summary_by_type from finance_flow_v3.

    For each (finance_campaign_id, stance, receipt_type) of accepted
    flow rows: compute total, n_committees (COALESCE for IE rows),
    n_transactions, top5_share, hhi. top5/HHI are computed from the
    donor distribution WITHIN that receipt_type — never summed across.
    """
    cur.execute("DELETE FROM finance_summary_by_type")

    # Pull accepted rows.
    # NULLIF(TRIM(col), '') strips empty / whitespace-only values so
    # COALESCE doesn't short-circuit on them — CAL-ACCESS ships empty-
    # string cover_committee_id ubiquitously; without NULLIF, every
    # accepted row's committee_key collapsed to '' and the per-slice
    # COUNT(DISTINCT) returned 1 universally (Codex round-2 finding).
    rows = cur.execute(
        "SELECT finance_campaign_id, measure_db_id, stance, receipt_type, "
        "       COALESCE("
        "           NULLIF(TRIM(committee_id), ''), "
        "           NULLIF(TRIM(cover_committee_id), ''), "
        "           NULLIF(TRIM(cover_filer_id), ''), "
        "           NULLIF(TRIM(reported_filer), '')"
        "       ) AS committee_key, "
        "       donor_name_canon, amount "
        "FROM finance_flow_v3 "
        "WHERE quarantine_reason IS NULL"
    ).fetchall()

    # Group: (cid, stance, type) -> { donor_amounts, committee_set, count }
    buckets: dict[tuple[str, str, str], dict] = defaultdict(
        lambda: {
            "measure_db_id": None,
            "donor_amounts": defaultdict(float),
            "committees": set(),
            "n_transactions": 0,
        }
    )
    for cid, mdb, stance, rtype, ck, donor, amt in rows:
        b = buckets[(cid, stance, rtype)]
        b["measure_db_id"] = mdb
        b["donor_amounts"][donor or ""] += amt or 0
        if ck:
            b["committees"].add(ck)
        b["n_transactions"] += 1

    inserts = []
    for (cid, stance, rtype), b in buckets.items():
        donor_totals = sorted(b["donor_amounts"].values(), reverse=True)
        grand_total = sum(donor_totals)
        if grand_total <= 0:
            top5_share = None
            hhi = None
        else:
            top5_share = 100.0 * sum(donor_totals[:5]) / grand_total
            hhi = sum(
                (100.0 * dt / grand_total) ** 2 for dt in donor_totals
            )
        inserts.append((
            cid,
            b["measure_db_id"],
            stance,
            rtype,
            grand_total,
            len(b["committees"]) or None,
            b["n_transactions"],
            top5_share,
            hhi,
        ))
    cur.executemany(
        "INSERT INTO finance_summary_by_type "
        "(finance_campaign_id, measure_db_id, stance, receipt_type, "
        " total_amount, n_committees, n_transactions, top5_share, hhi) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        inserts,
    )
    if verbose:
        print(f"  finance_summary_by_type: {len(inserts):,} rows")
    return len(inserts)


def rebuild_top_donors_by_type(cur: sqlite3.Cursor, verbose: bool) -> int:
    """Rebuild finance_top_donors_by_type from finance_flow_v3.

    One row per (finance_campaign_id, stance, receipt_type,
    donor_name_canon). attribution_source_mode is the modal
    attribution_source by dollar weight.
    """
    cur.execute("DELETE FROM finance_top_donors_by_type")

    rows = cur.execute(
        "SELECT finance_campaign_id, measure_db_id, stance, receipt_type, "
        "       donor_name_canon, donor_type, donor_sector, "
        "       attribution_source, amount "
        "FROM finance_flow_v3 "
        "WHERE quarantine_reason IS NULL AND donor_name_canon IS NOT NULL"
    ).fetchall()

    # Group by (cid, stance, type, donor); track attribution-source totals
    donor_buckets: dict = defaultdict(lambda: {
        "measure_db_id": None,
        "donor_type": None,
        "donor_sector": None,
        "total_amount": 0.0,
        "n_underlying_rows": 0,
        "attr_totals": defaultdict(float),
    })
    for cid, mdb, stance, rtype, donor, dtype, dsec, asrc, amt in rows:
        key = (cid, stance, rtype, donor)
        b = donor_buckets[key]
        b["measure_db_id"] = mdb
        if dtype and b["donor_type"] is None:
            b["donor_type"] = dtype
        if dsec and b["donor_sector"] is None:
            b["donor_sector"] = dsec
        b["total_amount"] += amt or 0
        b["n_underlying_rows"] += 1
        if asrc:
            b["attr_totals"][asrc] += amt or 0

    inserts = []
    for (cid, stance, rtype, donor), b in donor_buckets.items():
        mode = None
        if b["attr_totals"]:
            mode = max(b["attr_totals"].items(), key=lambda kv: kv[1])[0]
        inserts.append((
            cid,
            b["measure_db_id"],
            stance,
            rtype,
            donor,
            b["donor_type"],
            b["donor_sector"],
            b["total_amount"],
            b["n_underlying_rows"],
            mode,
        ))
    cur.executemany(
        "INSERT INTO finance_top_donors_by_type "
        "(finance_campaign_id, measure_db_id, stance, receipt_type, "
        " donor_name_canon, donor_type, donor_sector, total_amount, "
        " n_underlying_rows, attribution_source_mode) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        inserts,
    )
    if verbose:
        print(f"  finance_top_donors_by_type: {len(inserts):,} rows")
    return len(inserts)


def rebuild_timeline_by_type(cur: sqlite3.Cursor, verbose: bool) -> int:
    """Rebuild finance_timeline_weekly_by_type from finance_flow_v3.

    One row per (finance_campaign_id, stance, receipt_type, week_start).
    cumulative_amount is the running sum ordered by week_start within
    each (campaign, stance, type) group.
    """
    cur.execute("DELETE FROM finance_timeline_weekly_by_type")

    rows = cur.execute(
        "SELECT finance_campaign_id, measure_db_id, stance, receipt_type, "
        "       week_start, amount "
        "FROM finance_flow_v3 "
        "WHERE quarantine_reason IS NULL AND week_start IS NOT NULL"
    ).fetchall()

    weekly: dict[tuple[str, str, str, str], dict] = defaultdict(lambda: {
        "measure_db_id": None,
        "weekly_amount": 0.0,
    })
    for cid, mdb, stance, rtype, wk, amt in rows:
        b = weekly[(cid, stance, rtype, wk)]
        b["measure_db_id"] = mdb
        b["weekly_amount"] += amt or 0

    # Compute cumulative within each (cid, stance, rtype) ordered by week
    by_group: dict[tuple[str, str, str], list[tuple[str, float, int | None]]] = defaultdict(list)
    for (cid, stance, rtype, wk), b in weekly.items():
        by_group[(cid, stance, rtype)].append(
            (wk, b["weekly_amount"], b["measure_db_id"])
        )

    inserts = []
    for (cid, stance, rtype), weeks in by_group.items():
        weeks.sort(key=lambda x: x[0])
        running = 0.0
        for wk, amt, mdb in weeks:
            running += amt
            inserts.append((cid, mdb, stance, rtype, wk, amt, running))
    cur.executemany(
        "INSERT INTO finance_timeline_weekly_by_type "
        "(finance_campaign_id, measure_db_id, stance, receipt_type, "
        " week_start, weekly_amount, cumulative_amount) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        inserts,
    )
    if verbose:
        print(f"  finance_timeline_weekly_by_type: {len(inserts):,} rows")
    return len(inserts)


def rebuild_all(v3_db: Path, verbose: bool = True) -> dict:
    """Rebuild all 3 materialized derived tables atomically."""
    con = sqlite3.connect(str(v3_db), isolation_level=None)
    try:
        cur = con.cursor()
        cur.execute("BEGIN")
        try:
            if verbose:
                print(f"Rebuilding derived tables in {v3_db.name}...")
            s = rebuild_summary_by_type(cur, verbose)
            d = rebuild_top_donors_by_type(cur, verbose)
            t = rebuild_timeline_by_type(cur, verbose)
            cur.execute("COMMIT")
        except Exception:
            cur.execute("ROLLBACK")
            raise
    finally:
        con.close()
    return {"summary_rows": s, "donor_rows": d, "timeline_rows": t}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--v3-db", default=str(lib.V3_DB))
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    rebuild_all(Path(args.v3_db), verbose=not args.quiet)


if __name__ == "__main__":
    main()
