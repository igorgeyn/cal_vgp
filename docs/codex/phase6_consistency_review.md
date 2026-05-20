# Codex Phase 6 review: internal + external consistency

> **For Codex:** Phase 6 is the closeout for the v3 finance work —
> mostly documentation updates plus one new verification script.
> We want a **consistency-focused review across multiple touched
> docs**, not a code-correctness review per se.
>
> Live commits on `main`:
> - `1a42413` — `scripts/v3/verify_phase_g.py` (new, 222 lines)
> - `a9c8648` — `scraper/data/finance/README.md` (rewrite for combined v2+v3)
> - `8267343` — `docs/DATA_PIPELINE.md` (header) + `docs/KNOWN_ISSUES.md` (3 new issues)
> - `bce834c` — `scraper/CHANGELOG.md` (2.3.0 entry) + `docs/WORKING_LIST.md` (restructure)
>
> This is a different shape of review than rounds 1-5. Those were
> "does this code do what it claims?" Phase 6 is about **telling a
> consistent story** across multiple files. Where rounds 1-5 reviews
> caught arithmetic and SQL bugs, this review wants to catch narrative
> drift, contradictions between docs, and stale claims.

---

## What to look for

### A. Internal consistency within each doc

Do the claims hold together inside a single document? Examples to flag:

- Header summary numbers contradicting body details.
- Promised features in one section not mentioned elsewhere.
- TOC that doesn't match actual headings.
- Cross-references to sections that don't exist or moved.

### B. External consistency across docs

The Phase 6 docs collectively tell one story. Do they agree?

- `finance/README.md` says "$5,750,344,165.78 across 181 measures" —
  does `CHANGELOG.md` say the same? `KNOWN_ISSUES.md`? `WORKING_LIST.md`?
- Verification counts: `finance/README.md` claims "187 finance unit
  tests + Layer 1 (8/8) + Layer 2 reconciles ($0 diff) + Layer 3
  traces (10/10) + Phase G (9/9)." Do per-doc claims agree?
- Methodology bullets: `finance/README.md` lists 4 (exact totals,
  donor display-limited, concentration-None policy, n_measures union).
  Reflected the same way in `KNOWN_ISSUES.md` (#9, #10, #11) and
  CHANGELOG?
- Commit references: WORKING_LIST cites `1a42413 → 8267343` etc.
  Real commits with the claimed content?

### C. Accuracy vs the actual state of the tool

For any numerical or behavioral claim, can it be verified against
live code/data? Suggested verification commands:

```bash
# Totals reconciliation
python -c "import sqlite3
v2 = sqlite3.connect('scraper/data/finance/finance_statewide_v2.db')
v3 = sqlite3.connect('scraper/data/finance/finance_statewide_v3.db')
print('v2:', v2.execute('SELECT ROUND(SUM(total_receipts),2) FROM finance_summary').fetchone())
print('v3:', v3.execute('SELECT ROUND(SUM(amount),2) FROM finance_flow_v3 WHERE quarantine_reason IS NULL').fetchone())"

# Test counts
python -m pytest scraper/tests/test_finance_db.py scraper/tests/test_finance_db_v3.py scraper/tests/test_finance_crosswalk.py --collect-only -q | tail -3

# Phase G live execution
python scripts/v3/verify_phase_g.py

# Win-rate
python -c "import json; d=json.load(open('scraper/data/insights.json')); print(d['finance']['better_funded_win_rate'])"
```

Claims to scrutinize:
- "$5,750,344,165.78"
- "65.2% better_funded_win_rate"
- "187 finance tests pass" (full suite) vs "172" or "165" (subsets) — multiple counts appear; which is "the" claim?
- "9/9 Phase G PASS"
- "47,942 accepted v3 rows / $2.510B"
- "$36.27M of IE double-counting eliminated"
- "AIDS HEALTHCARE FOUNDATION $184,898,113" (in insights.json)
- "5 Codex rounds on Phase 5" (count verifiable via `docs/codex/`)
- "14 Codex rounds on Phase 4" (count verifiable via commit history grep)

### D. verify_phase_g.py — false-pass risks

The 9 checks all pass on live data. Each was written with a specific
invariant in mind. Do any have **false-pass loopholes** where the
check would still pass even if the underlying invariant were
violated? Specific concerns:

- **G5** samples only 30 measures. Enough? Would the check fire on a
  failure pattern affecting only lower-rank measures?
- **G7** samples one measure_db_id (10939 / PROP_27_2022). Does that
  measure exercise the "monetary > 0" branch with both stances?
  Should we test multiple measures?
- **G6** asserts Uber's combined total ($61,214,728). Hardcoded
  dollar amount → brittle on data refresh, or right behavior?
- **G8** walks `_DONOR_ALIASES_RAW` directly. Privacy-prefix
  convention means a rename silently breaks the check. Acceptable?
- **G9** checks `"n_transactions" not in sample_row` on
  PROP_27_2022. If the method returned `None` instead of omitting
  the field, this check still passes. Stronger assert needed?

### E. Methodology bullets in finance/README.md

Four claims under "Methodology notes (Codex round-4/5 calibration)":

1. **Headline totals are exact under current methodology.**
   $5,750,344,165.78 reconciles to v2 + v3 sums to the penny.
2. **Donor lists are display/canonicalization-limited.**
3. **Concentration metrics are unavailable when monetary contributes.**
4. **Calendar-year n_measures is a true union.**

Are these 4:
- Accurately describing current code?
- Internally consistent — does bullet 1 ("totals exact") contradict
  bullet 3 ("concentration unavailable")? Probably not (totals ≠
  concentration) but worth pressure-testing the framing.
- Externally consistent with `KNOWN_ISSUES.md` #9, #10, #11?

### F. Stale content

Doc rot is the failure mode. Candidates:

- `docs/DATA_PIPELINE.md` Section 9 (Finance Data Pipeline) wasn't
  touched in Phase 6 — body still describes v1 design. Top-of-doc
  disclaimer was updated. Sufficient, or should Section 9 also be
  marked snapshot?
- `docs/PROJECT_HISTORY.md` — not touched in Phase 6. Does it need
  an update?
- The "Last Updated: February 2026" header in KNOWN_ISSUES.md.

---

## Files to review

All paths relative to repo root. Codex can read them directly via
`git show` or filesystem.

| File | Phase 6 change | What to scrutinize |
|------|----------------|---------------------|
| `scripts/v3/verify_phase_g.py` | New (222 lines) | The 9 checks (G1-G9). Embedded below for convenience. |
| `scraper/data/finance/README.md` | Rewrite (~243 net new lines, 322 total) | Methodology bullets (Section "Methodology notes"). Combined scope description. v3 attribution layer description. Verification framework table. |
| `docs/KNOWN_ISSUES.md` | +3 new issues (#9, #10, #11) at the end (lines ~140-225) | Wording of the 3 new entries. Do they agree with finance/README.md? Revision history entry. |
| `scraper/CHANGELOG.md` | +1 new entry [2.3.0] at top (lines 12-58) | The 2.3.0 entry. Dates, commit-ref-free narrative. |
| `docs/WORKING_LIST.md` | Major restructure of header + first ~100 lines | "Next chunk" priorities. Phase 4/5/6 shipped summary. Verification stack summary. |
| `docs/DATA_PIPELINE.md` | Updated header disclaimer (lines 10-25) + file-tree listing (line ~73) | Top-of-doc disclaimer. Does it adequately point readers at the live design? |

## verify_phase_g.py — inlined

The new code is the most substantive Phase 6 change. Embedded here so
you don't have to fetch separately:

```python
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

    # ---- G8: every alias canonical with a source sector also has a canonical sector ----
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
```

---

## Specific deliverables

Please return:

1. **Internal-consistency findings** — per-doc inconsistencies.
2. **External-consistency findings** — places where docs contradict
   each other.
3. **Accuracy findings** — claims that don't match what the live
   tool does (with verification commands you ran).
4. **`verify_phase_g.py` false-pass risks** — checks that could pass
   while their invariants are violated.
5. **Stale content** — anything that should be marked snapshot or
   updated.

Each finding ideally has file:line ref, severity (blocking / cleanup
/ nice-to-have), and a recommended fix.

Calibration: prior rounds have demonstrated that prose drift in this
project is real — the "v3" wording sweep already missed two spots
across the prior round. Be skeptical.
