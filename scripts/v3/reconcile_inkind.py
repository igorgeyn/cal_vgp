"""Layer 2 source reconciliation for the Schedule C ingest.

Re-runs the same filters as ingest_inkind.py against the raw RCPT_CD
source, sums by (finance_campaign_id, stance), and compares against
finance_flow_v3's in_kind slice. Must match within $1.00 per
campaign.

Codex round-5 caveat: this shares load_filing_attribution_index code
with ingest_inkind, so attribution bugs reflect in both sides
(necessary but not sufficient). Independent waterfall checks are
deferred to the verification framework.

Usage:
    python scripts/v3/reconcile_inkind.py
"""
from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from v3 import lib
    from v3.attribution import build_filing_attribution_index
else:
    from . import lib
    from .attribution import build_filing_attribution_index


PER_CAMPAIGN_TOLERANCE = 1.00


def filtered_source_totals(dump_dir: Path, v2_db: Path,
                           manual_overrides_path: Path | None,
                           ) -> dict[tuple[str, str], float]:
    """Reproduce the ingest filters and sum amounts per (cid, stance)."""
    idx = build_filing_attribution_index(
        dump_dir, v2_db,
        manual_overrides_path=manual_overrides_path,
        verbose=False,
    )

    rcpt_path = dump_dir / "RCPT_CD.TSV"

    # Pass 1: latest amend per FILING_ID
    latest_amend: dict[str, int] = {}
    with rcpt_path.open(encoding="latin-1", newline="") as f:
        reader = csv.reader(f, delimiter="\t")
        header = next(reader)
        cols = {n: i for i, n in enumerate(header)}
        fid_idx = cols.get("FILING_ID")
        amend_idx = cols.get("AMEND_ID")
        for row in reader:
            if fid_idx is None or fid_idx >= len(row):
                continue
            fid = row[fid_idx]
            if not fid:
                continue
            try:
                amend = int(row[amend_idx] or 0) if (
                    amend_idx is not None and amend_idx < len(row)
                ) else 0
            except ValueError:
                amend = 0
            if amend > latest_amend.get(fid, -1):
                latest_amend[fid] = amend

    # Pass 2: filter Schedule C rows
    totals: dict[tuple[str, str], float] = defaultdict(float)
    with rcpt_path.open(encoding="latin-1", newline="") as f:
        reader = csv.reader(f, delimiter="\t")
        header = next(reader)
        cols = {n: i for i, n in enumerate(header)}

        def c(row, name):
            i = cols.get(name)
            return row[i] if i is not None and i < len(row) else ""

        for row in reader:
            fid = c(row, "FILING_ID")
            if not fid:
                continue
            try:
                amend = int(c(row, "AMEND_ID") or 0)
            except ValueError:
                amend = 0
            if amend != latest_amend.get(fid, -1):
                continue
            if (c(row, "FORM_TYPE") or "").strip() != "C":
                continue
            if not lib.is_null(c(row, "MEMO_CODE")):
                continue
            amt_raw = c(row, "AMOUNT")
            if lib.is_null(amt_raw):
                continue
            try:
                amount = float(amt_raw)
            except (ValueError, TypeError):
                continue
            if amount <= 0:
                continue
            if lib.parse_calaccess_date(c(row, "RCPT_DATE")) is None:
                continue
            attr = idx.get(fid)
            if attr is None:
                continue
            if attr.finance_campaign_id is None:
                continue
            if attr.stance is None:
                continue
            totals[(attr.finance_campaign_id, attr.stance)] += amount
    return dict(totals)


def v3_inkind_totals(v3_db: Path) -> dict[tuple[str, str], float]:
    con = sqlite3.connect(str(v3_db))
    out = {}
    for r in con.execute(
        "SELECT finance_campaign_id, stance, SUM(amount) "
        "FROM finance_flow_v3 "
        "WHERE source_table='RCPT_CD' AND source_form_type='C' "
        "  AND receipt_type='in_kind' AND quarantine_reason IS NULL "
        "GROUP BY finance_campaign_id, stance"
    ):
        cid, stance, total = r
        out[(cid, stance)] = total
    con.close()
    return out


def reconcile(dump_dir: Path, v2_db: Path, v3_db: Path,
              manual_overrides_path: Path | None,
              verbose: bool = True) -> int:
    src = filtered_source_totals(dump_dir, v2_db, manual_overrides_path)
    v3 = v3_inkind_totals(v3_db)

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

    print(f"=== Layer 2 reconciliation (RCPT_CD Schedule C) ===")
    print(f"Source (filtered SUM): {len(src)} (cid,stance) keys, "
          f"${src_total:,.2f}")
    print(f"v3 in_kind slice:      {len(v3)} (cid,stance) keys, "
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
    parser.add_argument(
        "--manual-overrides",
        default=str(Path("data/CalAccess/manual_attribution_overrides.json")),
    )
    args = parser.parse_args()

    overrides = (Path(args.manual_overrides)
                 if args.manual_overrides
                 and Path(args.manual_overrides).exists()
                 else None)
    sys.exit(reconcile(Path(args.dump_dir), Path(args.v2_db),
                       Path(args.v3_db), overrides, verbose=True))


if __name__ == "__main__":
    main()
