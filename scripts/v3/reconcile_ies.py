"""Layer 2 source reconciliation for the IE ingest.

Per Codex round-10 design: PER-SOURCE checks (catch extraction +
filter bugs) PLUS one dedup-consistency check.

Optimized: builds the attribution index ONCE, scans EXPN_CD twice
(amend + data), aggregates both F461P5 and F465P3 in a single pass.

Reports:
  S496_CD F496       — source SUM vs v3 S496 slice (pre-dedup)
  EXPN_CD F461P5     — source SUM vs v3 F461P5 slice (pre-dedup)
  EXPN_CD F465P3     — source SUM vs v3 F465P3 slice (pre-dedup)
  DEDUP CONSISTENCY  — internal v3 check (no source scan)

Pre-dedup means we count dedup losers too — losers came from a
specific source, and the reconcile verifies extraction/attribution
not dedup logic. The dedup check verifies the dedup logic
separately.

Usage:
    python scripts/v3/reconcile_ies.py
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
    from v3 import lib, resolver as resolver_mod
    from v3.attribution import (build_filing_attribution_index,
                                 _load_v2_crosswalk,
                                 _load_manual_overrides)
else:
    from . import lib, resolver as resolver_mod
    from .attribution import (build_filing_attribution_index,
                               _load_v2_crosswalk,
                               _load_manual_overrides)


PER_CAMPAIGN_TOLERANCE = 1.00
EXPN_ALLOW = {"F461P5", "F465P3"}


def s496_source_totals(dump_dir: Path, idx: dict
                       ) -> dict[tuple[str, str], float]:
    path = dump_dir / "S496_CD.TSV"
    latest_amend: dict[str, int] = {}
    with path.open(encoding="latin-1", newline="") as f:
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
                a = int(row[amend_idx] or 0) if (
                    amend_idx is not None and amend_idx < len(row)
                ) else 0
            except ValueError:
                a = 0
            if a > latest_amend.get(fid, -1):
                latest_amend[fid] = a

    totals: dict[tuple[str, str], float] = defaultdict(float)
    with path.open(encoding="latin-1", newline="") as f:
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
            if lib.parse_calaccess_date(c(row, "EXP_DATE")) is None:
                continue
            attr = idx.get(fid)
            if attr is None:
                continue
            if attr.finance_campaign_id is None or attr.stance is None:
                continue
            totals[(attr.finance_campaign_id, attr.stance)] += amount
    return dict(totals)


def expn_source_totals_both(
    dump_dir: Path, idx: dict,
    resolver: resolver_mod.AttributionResolver,
) -> dict[str, dict[tuple[str, str], float]]:
    """Returns {'F461P5': {(cid, stance): $}, 'F465P3': {...}}.

    One amend pass + one data pass over EXPN_CD; aggregates both form
    types simultaneously.
    """
    path = dump_dir / "EXPN_CD.TSV"

    # Pass 1: latest amend per FILING_ID, pre-filtered to allow-list
    latest_amend: dict[str, int] = {}
    with path.open(encoding="latin-1", newline="") as f:
        reader = csv.reader(f, delimiter="\t")
        header = next(reader)
        cols = {n: i for i, n in enumerate(header)}
        fid_idx = cols.get("FILING_ID")
        amend_idx = cols.get("AMEND_ID")
        form_idx = cols.get("FORM_TYPE")
        for row in reader:
            if form_idx is None or form_idx >= len(row):
                continue
            if (row[form_idx] or "").strip() not in EXPN_ALLOW:
                continue
            fid = row[fid_idx] if (fid_idx is not None
                                   and fid_idx < len(row)) else ""
            if not fid:
                continue
            try:
                a = int(row[amend_idx] or 0) if (
                    amend_idx is not None and amend_idx < len(row)
                ) else 0
            except ValueError:
                a = 0
            if a > latest_amend.get(fid, -1):
                latest_amend[fid] = a

    # Pass 2: data extraction
    totals: dict[str, dict[tuple[str, str], float]] = {
        "F461P5": defaultdict(float),
        "F465P3": defaultdict(float),
    }
    with path.open(encoding="latin-1", newline="") as f:
        reader = csv.reader(f, delimiter="\t")
        header = next(reader)
        cols = {n: i for i, n in enumerate(header)}

        def c(row, name):
            i = cols.get(name)
            return row[i] if i is not None and i < len(row) else ""

        for row in reader:
            ft = (c(row, "FORM_TYPE") or "").strip()
            if ft not in EXPN_ALLOW:
                continue
            fid = c(row, "FILING_ID")
            if not fid:
                continue
            try:
                amend = int(c(row, "AMEND_ID") or 0)
            except ValueError:
                amend = 0
            if amend != latest_amend.get(fid, -1):
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
            txn_date = lib.parse_calaccess_date(c(row, "EXPN_DATE"))
            if txn_date is None:
                continue

            attr = idx.get(fid)
            row_bal_num = c(row, "BAL_NUM")
            row_bal_name = c(row, "BAL_NAME")
            row_sup_opp_cd = c(row, "SUP_OPP_CD")

            # Codex round-12: mirror ingest_ies's row_has_ambig pre-
            # check. Multi-prop / non-statewide rows must NOT fall
            # back to cover sheet. Otherwise reconcile over-accepts.
            row_has_ambig = (
                resolver_mod.has_multi_prop_signal(
                    row_bal_num if not lib.is_null(row_bal_num) else ""
                )
                or resolver_mod.has_multi_prop_signal(
                    row_bal_name if not lib.is_null(row_bal_name) else ""
                )
            )

            row_prop = (
                row_bal_num
                if row_bal_num and not lib.is_null(row_bal_num) else
                (row_bal_name
                 if row_bal_name and not lib.is_null(row_bal_name) else None)
            )

            resolved_cid = None
            resolved_stance = None
            if row_prop and not row_has_ambig:
                date_hints = [txn_date]
                if attr:
                    for raw in (attr.cover_elect_date,
                                attr.cover_thru_date,
                                attr.cover_from_date):
                        d = lib.parse_calaccess_date(raw)
                        if d is not None:
                            date_hints.append(d)
                r = resolver.resolve_from_row_fields(
                    row_bal_num=(row_bal_num
                                 if not lib.is_null(row_bal_num) else None),
                    row_bal_name=(row_bal_name
                                  if not lib.is_null(row_bal_name) else None),
                    row_sup_opp_cd=(row_sup_opp_cd
                                    if not lib.is_null(row_sup_opp_cd)
                                    else None),
                    date_hints=date_hints,
                    cover_bal_num=(attr.cover_bal_num if attr else None),
                    cover_sup_opp_cd=(
                        attr.cover_sup_opp_cd if attr else None
                    ),
                )
                if r.resolved:
                    resolved_cid = r.finance_campaign_id
                    resolved_stance = r.stance
            # Cover fallback ONLY when row signal isn't multi-prop
            if (resolved_cid is None
                    and not row_has_ambig
                    and attr and attr.finance_campaign_id):
                resolved_cid = attr.finance_campaign_id
                resolved_stance = attr.stance
            if resolved_cid is None or resolved_stance is None:
                continue
            totals[ft][(resolved_cid, resolved_stance)] += amount

    return {ft: dict(v) for ft, v in totals.items()}


def _v3_pre_dedup_totals(v3_db: Path, source_table: str,
                          source_form_type: str
                          ) -> dict[tuple[str, str], float]:
    con = sqlite3.connect(str(v3_db))
    out = {}
    for r in con.execute(
        "SELECT finance_campaign_id, stance, SUM(amount) "
        "FROM finance_flow_v3 "
        "WHERE source_table=? AND source_form_type=? "
        "  AND receipt_type='independent_expenditure' "
        "  AND (quarantine_reason IS NULL OR "
        "       quarantine_reason='duplicate_economic_fingerprint') "
        "GROUP BY finance_campaign_id, stance",
        (source_table, source_form_type),
    ):
        cid, stance, total = r
        if cid is None or stance is None:
            continue
        out[(cid, stance)] = total
    con.close()
    return out


def compare(name: str, src: dict, v3: dict) -> int:
    only_src = set(src.keys()) - set(v3.keys())
    only_v3 = set(v3.keys()) - set(src.keys())
    mismatches = []
    for k in set(src.keys()) & set(v3.keys()):
        diff = abs(src[k] - v3[k])
        if diff > PER_CAMPAIGN_TOLERANCE:
            mismatches.append((k, src[k], v3[k], diff))

    print(f"=== {name} ===")
    print(f"  Source: {len(src)} keys / ${sum(src.values()):,.2f}")
    print(f"  v3:     {len(v3)} keys / ${sum(v3.values()):,.2f}")

    fail = bool(only_src or only_v3 or mismatches)
    if only_src:
        print(f"  FAIL: {len(only_src)} key(s) in source only (first 3):")
        for k in list(only_src)[:3]:
            print(f"    {k}: src=${src[k]:,.2f}")
    if only_v3:
        print(f"  FAIL: {len(only_v3)} key(s) in v3 only (first 3):")
        for k in list(only_v3)[:3]:
            print(f"    {k}: v3=${v3[k]:,.2f}")
    if mismatches:
        print(f"  FAIL: {len(mismatches)} value mismatch(es) (first 3):")
        for k, s, v, d in mismatches[:3]:
            print(f"    {k}: src=${s:,.2f} v3=${v:,.2f} diff=${d:,.2f}")

    if fail:
        print("  Result: FAIL\n")
        return 1
    print(f"  Result: PASS — all {len(src)} keys within "
          f"${PER_CAMPAIGN_TOLERANCE:.2f}\n")
    return 0


def reconcile_dedup_consistency(v3_db: Path) -> int:
    con = sqlite3.connect(str(v3_db))
    pre = con.execute(
        "SELECT ROUND(SUM(amount), 2) FROM finance_flow_v3 "
        "WHERE receipt_type='independent_expenditure' "
        "   OR quarantine_reason='duplicate_economic_fingerprint'"
    ).fetchone()[0] or 0.0
    post = con.execute(
        "SELECT ROUND(SUM(amount), 2) FROM finance_flow_v3 "
        "WHERE receipt_type='independent_expenditure' "
        "  AND quarantine_reason IS NULL"
    ).fetchone()[0] or 0.0
    losers = con.execute(
        "SELECT ROUND(SUM(amount), 2), COUNT(*) FROM finance_flow_v3 "
        "WHERE quarantine_reason='duplicate_economic_fingerprint'"
    ).fetchone()
    loser_dollars = losers[0] or 0.0
    loser_count = losers[1] or 0
    winner_missing = con.execute(
        "SELECT COUNT(*) FROM finance_flow_v3 "
        "WHERE quarantine_reason='duplicate_economic_fingerprint' "
        "  AND dedupe_winner_flow_id IS NULL"
    ).fetchone()[0]
    con.close()

    print("=== Dedup consistency ===")
    print(f"  Pre-dedup IE sum:        ${pre:,.2f}")
    print(f"  Post-dedup IE sum:       ${post:,.2f}")
    print(f"  Loser dollars:           ${loser_dollars:,.2f} "
          f"({loser_count:,} rows)")
    print(f"  pre - post:              ${pre - post:,.2f}")
    delta = abs((pre - post) - loser_dollars)
    print(f"  |pre - post - losers|:   ${delta:,.2f}")

    fail = False
    if winner_missing > 0:
        print(f"  FAIL: {winner_missing} loser(s) have NULL winner pointer")
        fail = True
    if delta > 0.01:
        print(f"  FAIL: pre - post differs from loser dollars by ${delta:,.2f}")
        fail = True
    if fail:
        print("  Result: FAIL\n")
        return 1
    print("  Result: PASS\n")
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
    dump_dir = Path(args.dump_dir)
    v2_db = Path(args.v2_db)
    v3_db = Path(args.v3_db)

    # Build attribution index + resolver ONCE
    print("Building filing-attribution index (one-shot)...")
    idx = build_filing_attribution_index(
        dump_dir, v2_db,
        manual_overrides_path=overrides,
        verbose=False,
    )
    crosswalk, match_via_by_cid = _load_v2_crosswalk(v2_db)
    overrides_loaded = _load_manual_overrides(overrides)
    resolver = resolver_mod.AttributionResolver(
        crosswalk, manual_overrides=overrides_loaded,
        match_via_by_cid=match_via_by_cid,
    )
    print(f"  {len(idx):,} filings resolved")
    print()

    exit_code = 0

    print("Scanning S496_CD source...")
    s496_src = s496_source_totals(dump_dir, idx)
    s496_v3 = _v3_pre_dedup_totals(v3_db, "S496_CD", "F496")
    exit_code |= compare("S496_CD F496 (pre-dedup)", s496_src, s496_v3)

    print("Scanning EXPN_CD source (both form types in one pass)...")
    expn_src = expn_source_totals_both(dump_dir, idx, resolver)
    for ft in ("F461P5", "F465P3"):
        v3 = _v3_pre_dedup_totals(v3_db, "EXPN_CD", ft)
        exit_code |= compare(f"EXPN_CD {ft} (pre-dedup)", expn_src[ft], v3)

    exit_code |= reconcile_dedup_consistency(v3_db)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
