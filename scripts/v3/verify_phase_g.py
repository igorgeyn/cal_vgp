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
    # Codex round-6: full pass over all measures takes ~1.15s; the
    # 30-measure sampling was unnecessarily cheap and could miss
    # failure patterns on lower-rank measures.
    drift = 0
    for mid in mids:
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
              f"({len(mids)}/{len(mids)} measures)")

    # ---- G6: alias merge on the marquee fights ----
    # Codex round-6: verify ALL known curated cross-source aliases
    # collapse on the relevant marquee measures, not just Uber.
    # Each entry: (measure_db_id, stance, expected canonical, substring hint).
    alias_marquee = [
        (10933, "support", "Uber Technologies, Inc", "uber"),
        (10933, "support", "Postmates, Inc", "postmates"),
        (10933, "support", "Instacart", "instacart"),
        (10939, "support",
         "FanDuel Sportsbook (Betfair Interactive US LLC)", "fanduel"),
        (10939, "support", "FBG Enterprises, LLC", "fbg"),
        (10939, "support",
         "Penn Interactive Ventures, LLC", "penn interactive"),
    ]
    g6_misses = []
    for mid, stance, expected_canonical, hint in alias_marquee:
        donors = db.get_combined_top_donors(mid, stance=stance, limit=20)
        hits = [
            d for d in donors
            if hint in (d["donor_name_canon"] or "").lower()
        ]
        if len(hits) != 1:
            g6_misses.append(
                f"measure {mid} {stance}: {len(hits)} entries match "
                f"{hint!r}; expected 1"
            )
        elif hits[0]["donor_name_canon"] != expected_canonical:
            g6_misses.append(
                f"measure {mid} {stance}: canonical "
                f"{hits[0]['donor_name_canon']!r} != {expected_canonical!r}"
            )
    if g6_misses:
        for m in g6_misses:
            failures.append(f"G6: {m}")
    else:
        print(f"  [PASS] G6: alias merge collapses {len(alias_marquee)} "
              f"marquee cross-source variants")

    # ---- G7: concentration None policy ----
    # Codex round-6: scan ALL combined rows across all measures with
    # monetary > 0, not just one measure. Also assert the sample is
    # non-empty so we don't silently pass when the monetary > 0 branch
    # isn't being exercised.
    g7_bad = []
    g7_monetary_rows = 0
    for mid in mids:
        for r in db.get_combined_summary(mid):
            if r["monetary_amount"] > 0:
                g7_monetary_rows += 1
                if r["top5_share"] is not None or r["hhi"] is not None:
                    g7_bad.append(
                        f"measure {mid} {r['stance']}: "
                        f"top5={r['top5_share']} hhi={r['hhi']}"
                    )
    if g7_monetary_rows == 0:
        failures.append(
            "G7: 0 combined rows have monetary > 0 — the None-policy "
            "branch isn't exercised, can't verify"
        )
    elif g7_bad:
        for m in g7_bad[:10]:
            failures.append(f"G7: {m}")
        if len(g7_bad) > 10:
            failures.append(f"G7: ... and {len(g7_bad) - 10} more")
    else:
        print(f"  [PASS] G7: combined summary rows with monetary>0 have "
              f"top5/hhi=None ({g7_monetary_rows} rows verified)")

    # ---- G8: every alias canonical with a source sector has a canonical sector ----
    # Codex round-6: the base "source has sector -> canonical has same
    # sector" invariant misses the case where neither side has a sector
    # but the README claims the marquee canonicals carry sectors. Add
    # an explicit expected-sector set for the curated marquee aliases.
    drift = []
    for source, canonical in _DONOR_ALIASES_RAW.items():
        source_sector = get_donor_sector(source)
        canonical_sector = get_donor_sector(canonical)
        if source_sector and canonical_sector != source_sector:
            drift.append((source, source_sector, canonical, canonical_sector))
    expected_canonical_sectors = {
        "Uber Technologies, Inc": "Gig Economy",
        "Postmates, Inc": "Gig Economy",
        "Instacart": "Gig Economy",
        "FanDuel Sportsbook (Betfair Interactive US LLC)": "Commercial Gambling",
        "FBG Enterprises, LLC": "Commercial Gambling",
        "Penn Interactive Ventures, LLC": "Commercial Gambling",
        "Pala Band of Mission Indians": "Tribal Gaming",
        "Apartment Investment and Management Company (AIMCO)": "Real Estate",
    }
    for canonical, expected in expected_canonical_sectors.items():
        got = get_donor_sector(canonical)
        if got != expected:
            drift.append(
                (f"<marquee:{canonical}>", expected, canonical, got)
            )
    if drift:
        for d in drift:
            failures.append(f"G8: alias drift {d[0]!r}({d[1]}) -> {d[2]!r}({d[3]})")
    else:
        print(f"  [PASS] G8: alias canonicals preserve source sectors "
              f"({len(_DONOR_ALIASES_RAW)} round-trip + "
              f"{len(expected_canonical_sectors)} marquee-explicit checks)")

    # ---- G9: combined summary shape + API response model -------------
    # Codex round-6: also assert the API Pydantic model doesn't declare
    # n_transactions. The method-shape check alone would still pass if
    # someone reverted the API model field; the two-layer check catches
    # that drift path.
    g9_failed = False
    sample_row = db.get_combined_summary(10939)[0]
    if "n_transactions" in sample_row:
        failures.append(
            "G9: combined summary still exposes n_transactions in row dict "
            "(Codex round-4 #4 regression)"
        )
        g9_failed = True
    api_note = ""
    try:
        from src.api.server import FinanceSideResponse
        if "n_transactions" in FinanceSideResponse.model_fields:
            failures.append(
                "G9: FinanceSideResponse Pydantic model still declares "
                "n_transactions field (API regression)"
            )
            g9_failed = True
        else:
            api_note = " (incl. FinanceSideResponse model)"
    except ImportError:
        # API module unavailable (FastAPI not in this env). Don't fail
        # Phase G on environment reasons.
        api_note = " (API model check skipped: FastAPI not importable)"
    if not g9_failed:
        print(f"  [PASS] G9: n_transactions absent from combined summary"
              f"{api_note}")

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
