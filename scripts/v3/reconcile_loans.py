"""Layer 2 source reconciliation for the loan ingest.

For each (finance_campaign_id, stance), the sum of v3 finance_flow_v3
rows where receipt_type='loan' AND quarantine_reason IS NULL must
equal the sum of LOAN_CD source rows after applying THE SAME filters:

- FORM_TYPE = 'B1'
- Latest AMEND_ID per (FILING_ID, LINE_ITEM)
- MEMO_CODE blank
- LOAN_AMT1 > 0
- Cover sheet attribution resolves to a matched (finance_campaign_id,
  stance)

Raw SUM(LOAN_AMT1) over LOAN_CD without these filters will overstate
because it includes guarantors, refused stances, etc. The
reconciliation source query must mirror the ingest rules.

Tolerance: $1 per campaign (rounding accumulation across ~270 rows).
Larger gaps = bug.

Usage:
    python scripts/v3/reconcile_loans.py
"""
from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from v3 import lib
    from v3.ingest_loans import load_cover_attributions
else:
    from . import lib
    from .ingest_loans import load_cover_attributions


PENNY = 0.005
PER_CAMPAIGN_TOLERANCE = 1.00


def filtered_source_totals(dump_dir: Path, v2_db: Path) -> dict:
    """Reproduce the ingest filters and sum LOAN_AMT1 per (cid, stance)."""
    attribs = load_cover_attributions(v2_db, dump_dir, verbose=False)
    loan_path = dump_dir / "LOAN_CD.TSV"

    # Latest amend per (FILING_ID, LINE_ITEM)
    latest_amend: dict[tuple[str, str], int] = {}
    with loan_path.open(encoding="latin-1", newline="") as f:
        reader = csv.reader(f, delimiter="\t")
        header = next(reader)
        cols = {n: i for i, n in enumerate(header)}
        for row in reader:
            def c(n):
                i = cols.get(n)
                return row[i] if i is not None and i < len(row) else ""
            fid = c("FILING_ID")
            line = c("LINE_ITEM")
            if not fid:
                continue
            try:
                a = int(c("AMEND_ID") or 0)
            except ValueError:
                a = 0
            if a > latest_amend.get((fid, line), -1):
                latest_amend[(fid, line)] = a

    totals: dict[tuple[str, str], float] = defaultdict(float)
    with loan_path.open(encoding="latin-1", newline="") as f:
        reader = csv.reader(f, delimiter="\t")
        header = next(reader)
        cols = {n: i for i, n in enumerate(header)}
        for row in reader:
            def c(n):
                i = cols.get(n)
                return row[i] if i is not None and i < len(row) else ""
            fid = c("FILING_ID")
            line = c("LINE_ITEM")
            try:
                amend = int(c("AMEND_ID") or 0)
            except ValueError:
                amend = 0
            if amend != latest_amend.get((fid, line), -1):
                continue
            if (c("FORM_TYPE") or "").strip() != "B1":
                continue
            if not lib.is_null(c("MEMO_CODE")):
                continue
            attr = attribs.get(fid)
            if attr is None or attr.finance_campaign_id is None:
                continue
            if attr.stance is None:
                continue
            try:
                amount = float(c("LOAN_AMT1") or 0)
            except (ValueError, TypeError):
                amount = 0.0
            if amount <= 0:
                continue
            # Also need parseable LOAN_DATE1 (ingest gate)
            if lib.parse_calaccess_date(c("LOAN_DATE1")) is None:
                continue
            totals[(attr.finance_campaign_id, attr.stance)] += amount
    return dict(totals)


def v3_loan_totals(v3_db: Path) -> dict:
    con = sqlite3.connect(str(v3_db))
    out = {}
    for r in con.execute(
        "SELECT finance_campaign_id, stance, SUM(amount) "
        "FROM finance_flow_v3 "
        "WHERE source_table='LOAN_CD' AND receipt_type='loan' "
        "  AND quarantine_reason IS NULL "
        "GROUP BY finance_campaign_id, stance"
    ):
        cid, stance, total = r
        out[(cid, stance)] = total
    con.close()
    return out


def reconcile(dump_dir: Path, v2_db: Path, v3_db: Path,
              verbose: bool = True) -> int:
    src = filtered_source_totals(dump_dir, v2_db)
    v3 = v3_loan_totals(v3_db)

    src_keys = set(src.keys())
    v3_keys = set(v3.keys())

    only_src = src_keys - v3_keys
    only_v3 = v3_keys - src_keys
    mismatches = []
    for key in src_keys & v3_keys:
        diff = abs(src[key] - v3[key])
        if diff > PER_CAMPAIGN_TOLERANCE:
            mismatches.append((key, src[key], v3[key], diff))

    src_total = sum(src.values())
    v3_total = sum(v3.values())

    print(f"=== Layer 2 reconciliation (LOAN_CD) ===")
    print(f"Source (filtered SUM): {len(src)} (cid,stance) keys, "
          f"${src_total:,.2f}")
    print(f"v3 loan slice:         {len(v3)} (cid,stance) keys, "
          f"${v3_total:,.2f}")
    print()

    if only_src:
        print(f"FAIL: {len(only_src)} (cid,stance) in source but not v3 "
              f"(first 5):")
        for k in list(only_src)[:5]:
            print(f"  {k} src=${src[k]:,.2f}")
    if only_v3:
        print(f"FAIL: {len(only_v3)} (cid,stance) in v3 but not source "
              f"(first 5):")
        for k in list(only_v3)[:5]:
            print(f"  {k} v3=${v3[k]:,.2f}")
    if mismatches:
        print(f"FAIL: {len(mismatches)} value mismatch(es) over "
              f"${PER_CAMPAIGN_TOLERANCE:.2f} tolerance (first 5):")
        for k, s, v, d in mismatches[:5]:
            print(f"  {k} src=${s:,.2f} v3=${v:,.2f} diff=${d:,.2f}")

    if only_src or only_v3 or mismatches:
        print()
        print("Result: FAIL")
        return 1

    grand_diff = abs(src_total - v3_total)
    print(f"All {len(src)} keys match within ${PER_CAMPAIGN_TOLERANCE:.2f}.")
    print(f"Grand total diff: ${grand_diff:,.2f}")
    print()
    print("Result: PASS")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dump-dir", default=str(lib.DUMP_DIR))
    parser.add_argument("--v2-db", default=str(lib.V2_DB))
    parser.add_argument("--v3-db", default=str(lib.V3_DB))
    args = parser.parse_args()

    sys.exit(reconcile(Path(args.dump_dir), Path(args.v2_db),
                       Path(args.v3_db), verbose=True))


if __name__ == "__main__":
    main()
