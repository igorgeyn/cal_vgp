# Codex round-4 closeout review: Phase 5 step 2b fixes

> **For Codex:** Closeout pass on the round-4 fixes you flagged and
> planned. Two commits on `main`:
> - `a1582c8` — correctness + copy (findings #3, #4, #5, sixth, dead-code)
> - `df6e73f` — donor aliases + concentration honesty (#1, #2)
>
> Order, scope, and approach for each fix followed your action plan in
> `phase5_step2b_action_plan_request.md`. We want to confirm the
> implementations match what you'd expect, the test coverage is right,
> and nothing else surfaces on a closeout look.

---

## Recap: what we did and why

### Commit 1 — `a1582c8` (correctness + copy)

| Finding | Implementation |
|---------|---------------|
| **#3** n_measures | Replaced `max(v2_count, v3_count)` with a TRUE union: query distinct `(year, measure_db_id)` from v2's `finance_timeline_weekly JOIN finance_campaign` AND v3's `finance_flow_v3`, union in Python via `defaultdict(set)`. Dollar totals delegate to existing per-source helpers so reconciliation stays exact. Live spot-check: **2005 went 20 → 25**; total unchanged at $5,750,344,165.78. |
| **#4** n_transactions | Removed from `get_combined_summary` row dict + from `FinanceSideResponse` Pydantic model. Docstring documents the omission. v3-only consumers can still call `get_finance_breakdown_by_type` for transaction counts. |
| **#5** stale copy | `generate_insights.py:1615` methodology block rewritten to describe combined scope. `generator.py:12099` mini-callout "campaigns" → "measures". |
| 6th finding | "v3" → "combined v2+v3" wording sweep: `build_finance_insights` docstring, `data_source` insights.json field, `_load_finance_data` log line. |
| Dead-code | Removed `if False else []` in `get_combined_top_donors`. Replaced with clean v2_rollup-or-empty assignment + documented "v2 capped at top-20" limitation comment. |

Tests added (+2): `test_combined_summary_omits_n_transactions`,
`test_combined_calendar_year_n_measures_is_true_union` (with
disjoint v2+v3 measure sets to prove union > max).

### Commit 2 — `df6e73f` (aliases + concentration honesty)

| Finding | Implementation |
|---------|---------------|
| **#1** concentration | `get_combined_summary` now returns **None** for `top5_share` / `hhi` on any row where `monetary_amount > 0`. v3-only rows (monetary=0) pass through v3's exact metrics. Docstring + Phase 6 docs document this as a known limit until full v2 monetary donor distributions are materialized. |
| **#2** donor canonicalization | New module `src/finance/donor_aliases.py` with `canonicalize_display_donor(name)`. 8 curated entries covering observed cross-source splits in marquee fights + top measures. Applied at `get_combined_top_donors` merge keys + `_build_finance_supplements` cross-measure donor aggregation. Underlying v2/v3 storage canonicalization untouched. |

Aliases added (narrow per your guidance):
- Uber Technologies (comma diff)
- Postmates (comma diff)
- FanDuel / Betfair Interactive US LLC (consumer brand vs LLC)
- FBG Enterprises LLC (responsible-officer suffix; 2 officer variants)
- Penn Interactive Ventures LLC (responsible-officer suffix)
- Pala Band of Mission Indians (with/without affiliated-casino name)
- AIMCO (3 affiliated-entity wording variants)
- Instacart / Maplebear (consumer brand vs legal entity)

Aliases intentionally NOT added (per your "avoid over-merging" caveat):
- SEIU Local 1000 / Local 1021 (distinct filing entities)
- UFCW Local 770 / Local 135 (distinct locals)
- ALA-CA / ALA-IN-CA / ALA (parent vs state-chapter ambiguity)
- Essex / Prometheus "and affiliated entities" suffixes

Tests added (+4): concentration None when monetary>0, concentration
passthrough when v3-only, Uber alias merge, SEIU non-merge regression
guard.

### Phase 6 prep (commit `8ec9049`)

Per your closing recommendation, captured the 4 methodology bullets
in `docs/WORKING_LIST.md` so Phase 6 picks them up:
1. Headline totals exact.
2. Donor lists display/canonicalization-limited.
3. Concentration metrics None when monetary>0 (v2 tail not materialized).
4. Calendar-year n_measures is true union (post-#3 fix).

Plus added "v3 monetary ingest" as a non-blocking follow-up — it's
the architectural fix that would let `get_combined_*` collapse and
resolve the concentration None caveat.

## Live impact spot-checks

**PROP_27_2022 support top 5 (before round-4 → after round-4):**
- Before: FanDuel split ($18.3M + $18.3M), FBG split ($12.5M + $12.5M),
  Penn Interactive sole ($25M)
- After: FanDuel $36.7M, DraftKings $36.4M, FBG $25M, Penn $25M,
  BetMGM $8.3M

**PROP_22_2020 support top 5 (before → after):**
- Uber unified: $30M + $30M → $61.2M
- Instacart unified: $21M + $18M → $39.6M (consumer brand vs Maplebear LLC)
- Lyft / DoorDash / Postmates clean (already consistent)

**Reconciliation: total_receipts $5,750,344,165.78 (unchanged);
better_funded_win_rate 65.2% (unchanged).** Aliases rename only,
don't double-count or drop dollars.

## Tests at closeout

178 finance tests pass total (118 v2 + 60 v3, +6 new this round).
v3 file structure:
```
TestSummaryTotal:                4
TestBreakdownByType:             3
TestTopDonorsTotal:              6
TestTopDonorsByType:             5
TestNCommitteesNullPreservation: 2
TestAttributionSourceAmountWeighted: 3
TestThreeCampaignCollision:      2
TestLimitBoundaries:             3
TestMeasureGuardDefenseInDepth:  1
TestEmptyStringCommitteeKey:     3
TestNullDonorSortTiebreak:       1
TestAttributionSourceTieBreak:   1
TestSqlNullLastOrdering:         2
TestTimelineTotal:               6
TestCalendarYearReceiptsV3:      5
TestCombinedMethods:             9  (+4 this round)
TestAcceptedRowNullDonorInvariant: 1
```

## What we want from this review

### A. Implementation correctness

Did the implementations match your action plan? Specifically:

1. **#1 None policy**: was returning None for `monetary > 0` the
   right interpretation of "do not present combined HHI/top5 as
   exact concentration metrics if they depend on truncated v2
   donors"? You wrote "either set ... to None ... or rename/copy-
   label them as 'visible donor concentration.' My preference:
   return None ... Conservative and harder to misread." Code does
   exactly that. Anything to refine?

2. **#2 alias scope**: do the 8 curated aliases cover the visible
   cases without over-merging? Specifically the AIMCO case (3
   formatting variants merged) — is that legitimate, or should
   "AND AFFILIATED ENTITIES" suffix stay distinct? We argued the
   variants on the SAME measure clearly identify one filer; you
   warned about affiliated-entities suffixes that "could
   legitimately encompass different contributor sets."

3. **#3 union shape**: we put the new SQL inside
   `get_combined_calendar_year_receipts` rather than changing v2/v3
   helpers, exactly as you recommended. The SQL queries
   `finance_timeline_weekly JOIN finance_campaign` for v2's set —
   is that the right v2 table choice (vs `finance_top_donors`,
   which is also year-aware but capped)?

4. **#4 omission**: clean break from the API. Any consumer we
   missed that still expects `n_transactions`?

5. **#5 copy**: methodology block rewrite is in the diff below. Is
   the wording sufficiently honest about the combined scope?

### B. Net assessment

Are we ready to ship Phase 5 (call it done) and move to Phase 6 docs?

### C. Anything we missed

You spotted a 6th issue during the planning pass ("v3" wording where
"combined" was meant). Anything else surfaces on a closeout look?
Particularly the alias map's coverage — there may be visible splits
on lower-traffic measures we didn't notice.

---

## Operations.py diff for commit 1 (a1582c8)

```diff
diff --git a/scraper/src/api/server.py b/scraper/src/api/server.py
@@ -790,9 +790,11 @@ class FinanceSideResponse(BaseModel):
     # Optional because the count is best-effort across two data sources
     # and may not be defined for v3-only slices.
     n_committees: Optional[int]
-    n_transactions: Optional[int]
     top5_share: Optional[float]
     hhi: Optional[float]
+    # n_transactions intentionally omitted: v2 doesn't carry a per-side
+    # transaction count, so a combined transaction count would be
+    # v3-only and misleading next to combined dollar totals.

diff --git a/scraper/src/finance/operations.py b/scraper/src/finance/operations.py
@@ -1006,11 +1006,17 @@ class FinanceDatabase:
     def get_combined_summary(self, measure_db_id: int) -> List[Dict]:
-        (v3). Each row: {stance, total_receipts, n_committees,
-        n_transactions, top5_share, hhi, monetary_amount,
-        non_monetary_amount}.
+        (v3). Each row: {stance, total_receipts, monetary_amount,
+        non_monetary_amount, n_committees, top5_share, hhi}.
+        ...
+        n_transactions is intentionally omitted: v2 doesn't carry a
+        transaction count, so a "combined" transaction count would be
+        v3-only and misleading next to combined dollar totals.

@@ -1065,7 +1065,6 @@
-            n_transactions = (v3.get("n_transactions") or None)
             top5_share, hhi = self._recompute_top5_hhi(
                 total, donors_sorted.get(stance, [])
             )
@@ -1074,7 +1073,6 @@
                 "monetary_amount": round(monetary, 2),
                 "non_monetary_amount": round(non_monetary, 2),
                 "n_committees": n_committees,
-                "n_transactions": n_transactions,
                 "top5_share": top5_share,
                 "hhi": hhi,
             })

@@ -1126,17 +1126,14 @@
-        # Pull a large slice from each side so the merge doesn't lose
-        # donors that ranked low individually but pop on combined total.
-        v2_top = self.get_top_donors(
-            self.resolve_campaign(measure_db_id=measure_db_id) or "",
-            limit=10_000,
-        ) if False else []
-        # v2 get_top_donors keys on finance_campaign_id; for multi-
-        # campaign measures use aggregate_for_measure which merges.
+        # Use aggregate_for_measure for v2 (it merges across collision
+        # campaigns); v3's get_top_donors_total already does per-measure
+        # rollup. donor_limit=10_000 asks for "everything" — v2's
+        # underlying finance_top_donors table is capped at top-20 per
+        # campaign/stance, so the merge may miss low-rank monetary
+        # donors. Documented limitation; tracked separately.
         v2_rollup = self.aggregate_for_measure(measure_db_id, donor_limit=10_000)
-        if v2_rollup:
-            v2_top = v2_rollup["donors"]
+        v2_top = v2_rollup["donors"] if v2_rollup else []
         v3_top = self.get_top_donors_total(measure_db_id, limit=10_000)

@@ -1230,35 +1230,57 @@
-        v2_rows = self.get_calendar_year_receipts()
-        v3_rows = self.get_calendar_year_receipts_v3()
-        merged: Dict[int, Dict] = {}
-        for r in v2_rows:
-            merged.setdefault(r["year"], { ... })
-            merged[r["year"]]["total"] += float(r.get("total_receipts") or 0)
-            merged[r["year"]]["v2_count"] = int(r.get("n_measures") or 0)
-        for r in v3_rows:
-            entry = merged.setdefault(r["year"], { ..., "v2_count": 0, })
-            entry["total"] += float(r.get("total_amount") or 0)
-            entry["v3_count"] = int(r.get("n_measures") or 0)
+        # Dollars merge: reuse existing per-source helpers.
+        merged_dollars: Dict[int, float] = defaultdict(float)
+        for r in self.get_calendar_year_receipts():
+            merged_dollars[r["year"]] += float(r.get("total_receipts") or 0)
+        for r in self.get_calendar_year_receipts_v3():
+            merged_dollars[r["year"]] += float(r.get("total_amount") or 0)
+
+        # True (year -> measure_db_id) union from both source tables.
+        year_measures: Dict[int, set] = defaultdict(set)
+        for row in self.conn.execute(
+            """
+            SELECT CAST(substr(t.week_start, 1, 4) AS INTEGER) AS year,
+                   c.measure_db_id AS mid
+            FROM   finance_timeline_weekly t
+            JOIN   finance_campaign c USING (finance_campaign_id)
+            WHERE  c.status = 'matched'
+              AND  c.measure_db_id IS NOT NULL
+              AND  t.week_start IS NOT NULL
+            """
+        ):
+            if row["year"] is not None:
+                year_measures[int(row["year"])].add(int(row["mid"]))
+        for row in self.v3_conn.execute(
+            """
+            SELECT CAST(substr(week_start, 1, 4) AS INTEGER) AS year,
+                   measure_db_id AS mid
+            FROM   finance_flow_v3
+            WHERE  quarantine_reason IS NULL
+              AND  week_start IS NOT NULL
+              AND  measure_db_id IS NOT NULL
+            """
+        ):
+            if row["year"] is not None:
+                year_measures[int(row["year"])].add(int(row["mid"]))
+
         return [
             {
-                "year": e["year"],
-                "total_receipts": round(e["total"], 2),
-                "n_measures": max(
-                    e.get("v2_count", 0), e.get("v3_count", 0)
-                ),
+                "year": year,
+                "total_receipts": round(merged_dollars.get(year, 0.0), 2),
+                "n_measures": len(year_measures[year]),
             }
-            for e in sorted(merged.values(), key=lambda x: x["year"])
+            for year in sorted(year_measures.keys())
         ]
```

## donor_aliases.py + operations.py diff for commit 2 (df6e73f)

The full content of `scraper/src/finance/donor_aliases.py` (new file):

```python
"""
Curated cross-source donor-name aliases for the combined v2 + v3 display layer.
...
This module applies ONLY at combined merge / display time
(get_combined_top_donors, _build_finance_supplements). It does NOT touch
the underlying v2 or v3 storage canonicalization — those stay independent
so reconciliation against the source dbs remains exact.

**Scope is intentionally narrow:** only pairs where the two names clearly
reference the same legal entity with minor formatting differences. We do
NOT merge:
- Different organizational levels (SEIU Local 1000 vs SEIU Local 1021,
  UFCW Local 770 vs Local 135 — those are distinct filing entities even
  though the parent unions are related).
- Parent-org / subsidiary distinctions ("PG&E Corporation" vs "Pacific
  Gas and Electric Company") — those have separate political activity.
- "Affiliated entities" suffixes that may genuinely encompass different
  contributor sets ("Essex Property Trust" vs "Essex ... AND AFFILIATED
  ENTITIES" — could be legitimately distinct accounting).
"""
from typing import Optional


_DONOR_ALIASES_RAW = {
    # Uber: comma diff only between v2 and v3 canonicalization.
    "UBER TECHNOLOGIES, INC": "Uber Technologies, Inc",
    "UBER TECHNOLOGIES INC": "Uber Technologies, Inc",
    # Postmates: comma diff only.
    "POSTMATES INC": "Postmates, Inc",
    "POSTMATES, INC": "Postmates, Inc",
    # FanDuel: v2 uses the consumer-facing brand wrapping; v3 has the LLC
    # legal entity. Same underlying donor.
    "FANDUEL SPORTSBOOK (BETFAIR INTERACTIVE US)":
        "FanDuel Sportsbook (Betfair Interactive US LLC)",
    "BETFAIR INTERACTIVE US LLC D/B/A FANDUEL GROUP, INC":
        "FanDuel Sportsbook (Betfair Interactive US LLC)",
    # FBG Enterprises (DraftKings affiliate): v2 carries the LLC with a
    # responsible-officer suffix; v3 has the clean LLC name.
    "FBG ENTERPRISES, LLC": "FBG Enterprises, LLC",
    "FBG ENTERPRISES OPCO, LLC(RESPONSIBLE OFFICER: ARI BOROD)":
        "FBG Enterprises, LLC",
    "FBG ENTERPRISES OPCO, LLC(RESPONSIBLE OFFICER: JON KAPLOWITZ)":
        "FBG Enterprises, LLC",
    # Penn Interactive: same responsible-officer-suffix pattern.
    "PENN INTERACTIVE VENTURES, LLC": "Penn Interactive Ventures, LLC",
    "PENN INTERACTIVE VENTURES, LLC(RESPONSIBLE OFFICER: JON KAPLOWITZ)":
        "Penn Interactive Ventures, LLC",
    # Instacart / Maplebear: legal entity name vs consumer brand.
    "INSTACART": "Instacart",
    "MAPLEBEAR INC. D/B/A INSTACART": "Instacart",
    # Pala Band: v3 sometimes inlines the casino entity name.
    "PALA BAND OF MISSION INDIANS": "Pala Band of Mission Indians",
    "PALA BAND OF MISSION INDIANS AND AFFILIATED ENTITY PALA CASINO SPA RESORT":
        "Pala Band of Mission Indians",
    # AIMCO: ampersand vs "and" + with/without "affiliated entities".
    "APARTMENT INVESTMENT AND MANAGEMENT COMPANY (AIMCO)":
        "Apartment Investment and Management Company (AIMCO)",
    "APARTMENT INVESTMENT AND MANAGEMENT COMPANY (AIMCO) AND AFFILIATED ENTITIES":
        "Apartment Investment and Management Company (AIMCO)",
    "APARTMENT INVESTMENT AND MANAGEMENT COMPANY (AIMCO) & AFFILIATED ENTITIES":
        "Apartment Investment and Management Company (AIMCO)",
}

_DONOR_ALIASES = {k.upper(): v for k, v in _DONOR_ALIASES_RAW.items()}


def canonicalize_display_donor(name: Optional[str]) -> Optional[str]:
    """Return the canonical display name for a donor, if a curated
    alias exists; otherwise return the input unchanged. None in → None out.
    """
    if not name:
        return name
    return _DONOR_ALIASES.get(name.strip().upper(), name)
```

Operations.py diff for commit 2 (key changes — concentration None
policy + alias application at merge):

```diff
@@ -17,6 +17,7 @@ from collections import defaultdict
 from pathlib import Path
 from typing import Iterable, List, Dict, Optional

+from .donor_aliases import canonicalize_display_donor
 from .donor_sectors import get_donor_sector
 from .schema import FINANCE_DB_PATH, FINANCE_DB_V3_PATH

@@ -1008,15 +1009,22 @@ class FinanceDatabase:
         """Per-stance totals across MONETARY (v2) + LOAN + IN-KIND + IE
         (v3). Each row: {stance, total_receipts, monetary_amount,
         non_monetary_amount, n_committees, top5_share, hhi}.
-        top5_share / hhi recomputed against the merged donor list.
+
+        **Concentration metrics (top5_share, hhi) policy (Codex
+        round-4 #1):** v2's per-donor distribution is materialized
+        as the top-20 per (campaign, stance) only — exact totals are
+        preserved but tail donors below the cap are missing. That
+        means top5/HHI computed against the merged donor list would
+        underestimate concentration for any measure whose v2 monetary
+        slice is non-trivial. To avoid presenting partial concentration
+        as exact, we return None for top5_share / hhi on any row where
+        monetary_amount > 0 (i.e., where the v2 truncation matters).
+        v3-only rows (monetary_amount = 0) get their v3 metrics
+        passed through, since the v3 donor list is complete.
         """

@@ -1028,31 +1036,6 @@ class FinanceDatabase:
-        # Merged donor list per stance for top5/hhi recompute.
-        v3_donors_full = self.get_top_donors_total(measure_db_id, limit=10_000)
-        donors_by_stance: Dict[str, Dict[str, float]] = defaultdict(dict)
-        if v2_rollup:
-            for d in v2_rollup["donors"]:
-                donors_by_stance[d["stance"]][d["donor_name_canon"]] = ...
-        for d in v3_donors_full:
-            donors_by_stance[d["stance"]][d["donor_name_canon"]] = ...
-        donors_sorted: Dict[str, List[Dict]] = { ... }
-
         all_stances = sorted(set(v2_by_stance) | set(v3_by_stance))

@@ -1065,9 +1048,19 @@
-            top5_share, hhi = self._recompute_top5_hhi(
-                total, donors_sorted.get(stance, [])
-            )
+
+            # Concentration metrics — conservative policy above.
+            if monetary > 0:
+                # v2 contributed; concentration would be biased low due
+                # to top-20 cap. Return None until v2's tail is
+                # materialized (separate phase, tracked in Phase 6 docs).
+                top5_share = None
+                hhi = None
+            else:
+                # v3-only — passthrough exact concentration from v3.
+                top5_share = v3.get("top5_share")
+                hhi = v3.get("hhi")

@@ -1140,13 +1133,18 @@
-        # Merge per (stance, donor_name_canon).
+        # Merge per (stance, alias-canonicalized donor name). Aliases
+        # collapse cross-source canonicalization drift (Codex round-4
+        # #2 — e.g. v2's "UBER TECHNOLOGIES, INC" and v3's "UBER
+        # TECHNOLOGIES INC" into one entry); see donor_aliases.py.
+        # Unaliased names pass through unchanged.
         merged: Dict[tuple, Dict] = {}
         for d in v2_top:
-            key = (d["stance"], d["donor_name_canon"])
+            display_name = canonicalize_display_donor(d["donor_name_canon"])
+            key = (d["stance"], display_name)
             entry = merged.setdefault(key, {
                 "stance": d["stance"],
-                "donor_name_canon": d["donor_name_canon"],
+                "donor_name_canon": display_name,
                 ...
             })
             entry["total_amount"] += float(d.get("total_amount") or 0)
             entry["flow_types"].add("monetary_contribution")
         for d in v3_top:
-            key = (d["stance"], d["donor_name_canon"])
+            display_name = canonicalize_display_donor(d["donor_name_canon"])
+            key = (d["stance"], display_name)
             entry = merged.setdefault(key, {
                 ...
-                "donor_name_canon": d["donor_name_canon"],
+                "donor_name_canon": display_name,
                 ...
             })
```

For the full diffs:
```
git show a1582c8
git show df6e73f
git show 8ec9049  # WORKING_LIST Phase 6 prep
```
