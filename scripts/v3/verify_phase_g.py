"""
Phase G — v3 + combined integrity checks (Phase 6 closeout).

Runs structural invariants that should hold for the v3 finance pipeline
+ the combined v2+v3 read layer. Complementary to:
- Layer 1 (verify_layer1.py): v2 untouched-ness.
- Layer 2 (reconcile_*.py): each v3 ingest reconciles against its source.
- Layer 3 (verify_traces.py): source-row-anchored trace fixtures.

This adds:
- G1: v3 db exists + has expected tables/views/by-type tables.
- G2: v3 accepted total matches the canonical $2.510B.
- G3: combined summary sums across all measures = v2 monetary + v3.
- G4: calendar-year combined total reconciles to per-source sum.
- G5: per-measure breakdown sums = summary totals.
- G6: alias merge collapses known cross-source variants in marquee fights.
- G7: concentration-None policy fires for any combined row with monetary>0.
- G8: every donor_aliases canonical output with a source sector also
      has a sectors entry.
- G9: API response shape — n_transactions absent from combined summary
      (avoids accidental re-introduction).

Run: `python scripts/v3/verify_phase_g.py` from repo root.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scraper"))

from src.finance.donor_aliases import _DONOR_ALIASES_RAW, canonicalize_display_donor
from src.finance.donor_sectors import get_donor_sector
from src.finance.operations import FinanceDatabase
from src.finance.schema import FINANCE_DB_PATH, FINANCE_DB_V3_PATH


EXPECTED_V3_TOTAL = 2_510_050_967.24
EXPECTED_V2_MONETARY = 3_240_293_198.54
EXPECTED_COMBINED_TOTAL = EXPECTED_V3_TOTAL + EXPECTED_V2_MONETARY  # 5,750,344,165.78


def main() -> int:
    failures = []
    db = FinanceDatabase()
    v3 = sqlite3.connect(str(FINANCE_DB_V3_PATH))
    v3.row_factory = sqlite3.Row
    v2 = sqlite3.connect(str(FINANCE_DB_PATH))
    v2.row_factory = sqlite3.Row

    # ---- G1: schema sanity ----
    have_tables = {r[0] for r in v3.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}
    have_views = {r[0] for r in v3.execute(
        "SELECT name FROM sqlite_master WHERE type='view'"
    )}
    need_tables = {
        "finance_flow_v3",
        "finance_summary_by_type",
        "finance_top_donors_by_type",
        "finance_timeline_weekly_by_type",
    }
    need_views = {
        "finance_summary_total",
        "finance_top_donors_total",
        "finance_timeline_weekly_total",
    }
    missing_t = need_tables - have_tables
    missing_v = need_views - have_views
    if missing_t or missing_v:
        failures.append(f"G1: missing tables={missing_t} views={missing_v}")
    else:
        print(f"  [PASS] G1: v3 db has all expected tables ({len(need_tables)}) "
              f"and views ({len(need_views)})")

    # ---- G2: v3 accepted total ----
    v3_total = v3.execute(
        "SELECT ROUND(SUM(amount), 2) FROM finance_flow_v3 "
        "WHERE quarantine_reason IS NULL"
    ).fetchone()[0]
    if abs(v3_total - EXPECTED_V3_TOTAL) > 1.0:
        failures.append(
            f"G2: v3 accepted total ${v3_total:,.2f} != expected "
            f"${EXPECTED_V3_TOTAL:,.2f}"
        )
    else:
        print(f"  [PASS] G2: v3 accepted total = ${v3_total:,.2f}")

    # ---- G3: combined summary across all measures = $5.75B ----
    combined_total = 0.0
    mids = [int(r[0]) for r in v3.execute(
        "SELECT DISTINCT measure_db_id FROM finance_flow_v3 "
        "WHERE quarantine_reason IS NULL AND measure_db_id IS NOT NULL"
    )]
    # Also include any v2 measures that don't have v3 flows
    for r in v2.execute(
        "SELECT DISTINCT measure_db_id FROM finance_campaign "
        "WHERE measure_db_id IS NOT NULL AND status='matched'"
    ):
        if int(r[0]) not in mids:
            mids.append(int(r[0]))
    for mid in mids:
        for row in db.get_combined_summary(mid):
            combined_total += row["total_receipts"]
    if abs(combined_total - EXPECTED_COMBINED_TOTAL) > 1.0:
        failures.append(
            f"G3: combined total ${combined_total:,.2f} != expected "
            f"${EXPECTED_COMBINED_TOTAL:,.2f}"
        )
    else:
        print(f"  [PASS] G3: combined total across {len(mids)} measures = "
              f"${combined_total:,.2f}")

    # ---- G4: calendar-year combined = per-source sum ----
    cy_sum = sum(r["total_receipts"] for r in db.get_combined_calendar_year_receipts())
    if abs(cy_sum - EXPECTED_COMBINED_TOTAL) > 1.0:
        failures.append(
            f"G4: calendar_year combined sum ${cy_sum:,.2f} != expected "
            f"${EXPECTED_COMBINED_TOTAL:,.2f}"
        )
    else:
        print(f"  [PASS] G4: combined calendar-year sum reconciles "
              f"(${cy_sum:,.2f})")

    # ---- G5: per-measure breakdown = summary total ----
    drift = 0
    for mid in mids[:30]:  # sample 30; full check would 181x quadratic
        bt_sum = sum(
            r["total_amount"]
            for r in db.get_combined_breakdown_by_type(mid)
        )
        st_sum = sum(
            r["total_receipts"]
            for r in db.get_combined_summary(mid)
        )
        if abs(bt_sum - st_sum) > 0.01:
            drift += 1
    if drift:
        failures.append(
            f"G5: {drift} measures have breakdown != summary sum"
        )
    else:
        print(f"  [PASS] G5: breakdown sums = summary totals "
              f"(30/30 sampled measures)")

    # ---- G6: alias merge on a marquee fight ----
    # PROP_22_2020 should show ONE Uber Technologies entry, not two
    p22 = db.get_combined_top_donors(10933, stance="support", limit=10)
    uber = [d for d in p22 if "uber" in (d["donor_name_canon"] or "").lower()]
    if len(uber) != 1:
        failures.append(
            f"G6: PROP_22 support has {len(uber)} Uber entries; expected 1"
        )
    elif uber[0]["donor_name_canon"] != "Uber Technologies, Inc":
        failures.append(
            f"G6: Uber canonical = {uber[0]['donor_name_canon']!r}; "
            f"expected 'Uber Technologies, Inc'"
        )
    else:
        print(f"  [PASS] G6: alias merge collapses Uber variants on PROP_22 "
              f"(${uber[0]['total_amount']:,.0f})")

    # ---- G7: concentration None policy ----
    # Pick a measure with both v2 and v3 money; assert top5/hhi=None.
    sample = db.get_combined_summary(10939)  # PROP_27_2022
    monetary_rows = [r for r in sample if r["monetary_amount"] > 0]
    bad = [
        r for r in monetary_rows
        if r["top5_share"] is not None or r["hhi"] is not None
    ]
    if bad:
        failures.append(
            f"G7: PROP_27_2022 rows with monetary>0 have non-None "
            f"top5/hhi: {bad}"
        )
    else:
        print(f"  [PASS] G7: combined summary rows with monetary>0 have "
              f"top5/hhi=None ({len(monetary_rows)} sampled)")

    # ---- G8: every alias canonical with a source sector has a canonical sector ----
    drift = []
    for source, canonical in _DONOR_ALIASES_RAW.items():
        source_sector = get_donor_sector(source)
        canonical_sector = get_donor_sector(canonical)
        if source_sector and canonical_sector != source_sector:
            drift.append((source, source_sector, canonical, canonical_sector))
    if drift:
        for d in drift:
            failures.append(f"G8: alias drift {d[0]!r}({d[1]}) -> {d[2]!r}({d[3]})")
    else:
        print(f"  [PASS] G8: all alias canonicals preserve source sectors "
              f"({len(_DONOR_ALIASES_RAW)} entries scanned)")

    # ---- G9: combined summary shape — no n_transactions ----
    sample_row = db.get_combined_summary(10939)[0]
    if "n_transactions" in sample_row:
        failures.append(
            "G9: combined summary still exposes n_transactions "
            "(Codex round-4 #4 regression)"
        )
    else:
        print(f"  [PASS] G9: n_transactions absent from combined summary")

    db.close()
    v2.close()
    v3.close()

    print()
    if failures:
        print(f"=== Phase G: {len(failures)} failures ===")
        for f in failures:
            print(f"  [FAIL] {f}")
        return 1
    print("=== Phase G: 9/9 PASS ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
