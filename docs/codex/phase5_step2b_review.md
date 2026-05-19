# Codex review: Phase 5 step 2b — atomic UI flip to combined v2 + v3

> **For Codex:** Step 2b ships the user-visible part of Phase 5 — all
> consumer surfaces now show **combined v2 monetary + v3 (loans + in-kind
> + IE)** totals. Live commit: `bec2abe` on `main`. Step 1's library
> layer was reviewed across rounds 1–3 (`phase5_step1_review*.md` in
> this directory); this is a new commit on top, with different surfaces.

---

## TL;DR of the Phase 5 build arc

- **Step 1** (`4542d4a` → `43dc55e`, reviewed across 3 rounds): added 4
  v3 read methods (`get_finance_summary_total`, `get_finance_breakdown_by_type`,
  `get_top_donors_total`, `get_top_donors_by_type`) that aggregate
  directly from `finance_flow_v3`. No UI change.
- **Step 2a** (`fd30c3a`): added 2 more v3 read methods needed for
  step 2b's atomic flip (`get_finance_timeline_total`,
  `get_calendar_year_receipts_v3`). 11 new tests.
- **Step 2b** (`bec2abe`, THIS REVIEW): added 5 `get_combined_*`
  methods that stitch v2 monetary onto v3 non-monetary, then flipped
  all 4 consumer surfaces (API, briefing, modal data, insights
  generator) to use them. Plus methodology copy updates. 9 files
  touched, +1514 / −786 lines.

## Architectural decision

v3 currently ingests **only** loans + in-kind + IE — no monetary
contributions. Total v3 accepted is $2.51B; v2 still owns the $3.24B
of monetary. For the UI flip to show ~$5.75B combined per the
WORKING_LIST plan, two paths:

1. **Ingest monetary into v3** (separate sub-phase): bigger up-front
   cost, cleaner architecture long-term.
2. **Stitch at consumer layer**: 5 new `get_combined_*` methods that
   call v2 + v3 methods and merge in Python.

User chose option 2 (recommended). The 5 combined methods hide the
split from consumers. If v3 grows monetary ingest later, the
combined methods can collapse into v3 counterparts.

## What changed in the 9 touched files

| File | What |
|------|------|
| `scraper/src/finance/operations.py` | +5 combined methods (266 lines) |
| `scraper/src/api/server.py` | 3 endpoints use combined; `FinanceSideResponse` adds `monetary_amount` + `non_monetary_amount`; `n_committees: Optional[int]` |
| `scraper/src/research/sources/finance.py` | Briefing facts use combined methods; prose updated to lead with combined total + monetary/non-monetary split |
| `scraper/src/website/generator.py` | `_load_finance_data` uses combined methods, translates to v2-shape field names so embedded JS modal template stays untouched; methodology prose updated in 2 spots |
| `scraper/scripts/generate_insights.py` | `build_finance_insights` + `_build_finance_supplements` rewritten to use combined data for headline totals, top donors, repeat donors, marquee fights, annual_receipts, calendar_year_receipts |
| `scraper/tests/test_finance_db_v3.py` | +6 combined-method tests (TestCombinedMethods class) |
| `scraper/data/insights.json` | Regenerated (data artifact, not reviewed) |
| `index.html` + `scraper/index.html` | Regenerated static site (data artifacts) |

## Validation done

- 172 finance tests pass (118 v2 + 54 v3, +6 combined).
- Reconciliation: insights.json `annual_receipts` sum = `calendar_year_receipts`
  sum = **$5,750,344,165.78** to the penny = v2 ($3,240,293,198.54) +
  v3 ($2,510,050,967.24).
- Win-rate: **65.2%** (v2 was 65%, barely changed — IE follows
  monetary lead in most fights).
- Top donors include both v2-heavy (CTA $202M Labor) and v3-heavy
  (AHF $185M Healthcare, San Manuel $166M Tribal Gaming) actors.
- Cross-source donor merge confirmed: PROP_27_2022 San Manuel
  combined $153.2M across 3 channels (monetary + in-kind + IE).

## Specific things to scrutinize

### A. Merge correctness in `get_combined_summary`

The merge happens in Python:
```python
v2_rollup = self.aggregate_for_measure(measure_db_id, donor_limit=10_000)
v3_summary = self.get_finance_summary_total(measure_db_id)
# ... index by stance, sum monetary + non_monetary, recompute top5/hhi
```

`v2_rollup["summary"][...]["total_receipts"]` is the v2 monetary
total per (stance). Adding to `v3_by_stance[...]["total_amount"]` (v3
non-monetary) gives the combined total. Then top5/HHI recomputed
against the merged donor list (union by `donor_name_canon`, sum
amounts, sort).

**Verify:**
1. Is the donor-key match by exact `donor_name_canon` string correct?
   v2 and v3 may have *different* canonicalization for the same legal
   entity (e.g. v2 has "DraftKings (Crown Gaming Inc)" while v3 might
   have "DRAFTKINGS INC"). Cross-source aggregation would treat these
   as two distinct donors. **Empirically seen:** FanDuel split across
   "FanDuel Sportsbook (Betfair Interactive...)" (v2) and
   "BETFAIR INTERACTIVE US LLC D/B/A FANDUEL GROUP" (v3) — both at
   ~$18M each in marquee_fights['PROP_27_2022'].support_top_donors.
2. The `donor_limit=10_000` is a magic number — large enough that v2
   doesn't truncate before the merge. Worth checking if any
   real-measure v2 has more than 10K donors. (Empirically no — v2's
   finance_top_donors table caps at top-20 per campaign anyway.) But
   then there's a hidden constraint: v2's `aggregate_for_measure`
   internally reads from `finance_top_donors` which is itself
   pre-truncated, so `donor_limit=10_000` doesn't actually pull
   more than 20 per campaign. Is that a correctness issue?

### B. `get_combined_breakdown_by_type` ordering

After merge:
```python
out.sort(key=lambda x: (x["stance"], x["receipt_type"]))
```

This puts `in_kind` first (alphabetical), then `independent_expenditure`,
then `loan`, then `monetary_contribution`. The UI may want
`monetary_contribution` first as the "main" type. Is this ordering
sensible for the modal panel?

### C. `get_combined_top_donors` rank stability

Merging by exact `donor_name_canon` then re-ranking by
`(-total_amount, name_is_None, name_or_empty)`. Same NULL-safe sort
pattern as the v3 methods.

**Verify:**
1. The dead-code line `v2_top = self.get_top_donors(...) if False else []`
   followed by an unconditional `v2_top = v2_rollup["donors"]` is
   confusing. Should be cleaned up. (Cosmetic, not blocking.)
2. `flow_types.add("monetary_contribution")` for every v2 donor — but
   v2's `donors` only contains people who appeared in v2's top-N per
   campaign. A donor who gave monetary but didn't make top-N would
   miss the `monetary_contribution` flow-type tag. Is this a real
   gap or fine?

### D. `n_committees` arithmetic in combined summary

```python
n_committees = (
    int(v2.get("n_committees") or 0)
    + (int(v3["n_committees"]) if v3.get("n_committees") else 0)
) or None
```

The sum may DOUBLE-COUNT committees that file across v2 and v3 (e.g.
"Californians Against PROP X" filed monetary in v2 AND IE in v3 as
the same filer). Documented as "best-effort" in the docstring.

**Verify:**
1. Acceptable? Or worth doing a true DISTINCT count from raw flow
   table + v2 committee table?
2. `or None` at the end converts 0 → None (so the API can omit the
   field). Same intent as the v3 `_opt_int` helper.

### E. `get_combined_timeline` cumulative recompute

Per-stance cumulative recomputed from the merged weekly:
```python
cumulative: Dict[str, float] = defaultdict(float)
out: List[Dict] = []
for (stance, week), amt in rows_sorted:
    cumulative[stance] += amt
    out.append({..., "cumulative_receipts": round(cumulative[stance], 2)})
```

Sort key is `(stance, week)` so each stance's cumulative is independent.

**Verify:**
1. Edge case: same week appears only in v2 (monetary committee filed
   in cycle X) but v3 didn't have any flows on that week. Should
   still emit a row with weekly_receipts = v2 only. The
   `defaultdict(float) += 0` semantics handle this — v3's missing
   week doesn't matter, defaultdict starts at 0.
2. Round-to-2 happens at each iteration. Does this introduce
   cumulative drift across hundreds of weeks? Probably negligible
   (sub-cent over thousands of rows) but worth a mental check.

### F. `get_combined_calendar_year_receipts` n_measures approximation

```python
"n_measures": max(e.get("v2_count", 0), e.get("v3_count", 0)),
```

v2 doesn't expose the measure SET per year (only the COUNT). v3 has
the same problem in the existing v3 method. MAX-of-counts assumes
the v2 and v3 measure sets overlap heavily — likely true, but not
guaranteed. For example, if v2 has 5 measures in year 2010 and v3
has 8 (different non-overlapping measures), the truth is 13; MAX
would say 8.

**Verify:**
1. Is the MAX heuristic acceptable for the spending-arc chart, or
   worth pulling true distinct measure_db_id from the flow tables
   directly? The cost is one extra query per side, joining on year.

### G. The `insights_generator._build_finance_supplements` rewrite

This function was rewritten from v2 SQL to a hybrid: v2 SQL for
monetary aggregates + v3 SQL for non-monetary, merged in Python.

**Verify:**
1. `top_donors_overall` and `repeat_donors`: the merge does
   `donor_totals[r["name"]]["cids"].add(...)` from both v2 and v3.
   v2 cids and v3 cids should be identical (v3 inherits v2's
   crosswalk) — verify this holds and consider whether a single
   distinct-cid count from either side would suffice.
2. The annual_receipts loop opens a v2 connection mid-function:
   ```python
   v2_summary = sqlite3.connect(str(FINANCE_DB_PATH))
   ```
   This duplicates the connection the FinanceDatabase already has.
   Cosmetic, not blocking.

### H. The methodology copy update

Two prose strings updated to describe combined scope:
- Line 935: "Money matters but isn't decisive: across all reportable
  spending (direct receipts, in-kind, loans, and independent
  expenditures), the better-funded side wins about 65% of the time"
- Line 937 (long methodology note): describes 4 scopes, names the
  v2 + v3 db split, calls out conservative attribution + dedup, and
  preserves the calendar-vs-election-year toggle caveat.

**Verify:** is the prose accurate enough for a public-facing
methodology note? Anything misleading or imprecise?

### I. The 6 new tests

`TestCombinedMethods` covers:
- v2 monetary + v3 non-monetary sum (1+1 case)
- v2-only measure (no v3 flows)
- v3-only measure (no v2 monetary — rare)
- Cross-source donor merge by exact name (San Manuel + Tribal
  Gaming sector re-resolve)
- 4-receipt-type breakdown
- Timeline week-merge

**Verify what might be missing:**
1. Donor canonicalization drift (B above) — should there be a test
   asserting that two SLIGHTLY different canon names (e.g.
   "ACME, INC" vs "ACME INC") stay separate, with a docstring noting
   this is the current behavior and may need future fix?
2. Multi-stance test where v2 only has support and v3 only has oppose
   — combined summary should produce 2 rows.
3. n_committees double-count scenario test.
4. limit boundary on `get_combined_top_donors` (limit=1, limit > total
   donors).

### J. JS-shape compatibility

The embedded JS modal template at `generator.py:7706-7785` reads
`summary.total_receipts`, `summary.n_committees`, `t.cumulative_receipts`
etc. The `_load_finance_data` method translates v3-style
`total_amount` / `weekly_amount` / `cumulative_amount` back to
v2-style names so the JS template stays untouched. **The JS doesn't
yet render `breakdown_by_type`** (the new per-receipt-type panel) —
it's emitted to financeData but the template ignores it. Future JS
work could surface it.

**Verify:** is the v3-to-v2 field-rename translation correct, or do
any fields silently drop? Specifically:
- `monetary_amount` and `non_monetary_amount` are NEW fields in
  combined summary — the JS doesn't read them yet. Worth adding
  a `<small>` breakdown to the modal in a follow-up.

## Deliverable

Please flag:

1. Any correctness issue in the v2+v3 merge logic (Sections A, C, E).
2. The donor canonicalization drift (Section A.1) — is this a
   blocker for shipping, or fine to defer?
3. Whether the `n_measures` MAX approximation (Section F) needs a
   real distinct count.
4. Any test coverage gap from Section I that's blocker for shipping.
5. Methodology copy accuracy (Section H).
6. Cosmetic cleanups (the dead `if False else []` line in
   `get_combined_top_donors`).

The static site is regenerated and live with the new numbers; if
there's a correctness bug, it's user-visible. Conservatism preferred
over precision — flag anything that even MIGHT be wrong.

---

## The full operations.py diff (commit bec2abe, +266 lines)

```diff
diff --git a/scraper/src/finance/operations.py b/scraper/src/finance/operations.py
@@ -995,6 +995,272 @@ class FinanceDatabase:
             if r["year"] is not None
         ]
 
+    # ---- Combined v2 (monetary) + v3 (loans + in-kind + IE) ---------------
+    # These methods stitch the v2 monetary slice onto the v3 expanded
+    # slice so the UI sees one coherent total per measure. v3 currently
+    # doesn't ingest monetary contributions (those still live in v2 only);
+    # once a v3 monetary ingest lands, these methods can collapse into
+    # their underlying v3 counterparts. The split is hidden from
+    # consumers — they always call get_combined_*.
+    # -----------------------------------------------------------------------
+
+    def get_combined_summary(self, measure_db_id: int) -> List[Dict]:
+        """Per-stance totals across MONETARY (v2) + LOAN + IN-KIND + IE
+        (v3). Each row: {stance, total_receipts, n_committees,
+        n_transactions, top5_share, hhi, monetary_amount,
+        non_monetary_amount}. top5_share / hhi recomputed against the
+        merged donor list. n_committees is best-effort sum (may
+        double-count committees that file across v2 and v3).
+        """
+        v2_rollup = self.aggregate_for_measure(measure_db_id, donor_limit=10_000)
+        v3_summary = self.get_finance_summary_total(measure_db_id)
+
+        # Index by stance
+        v2_by_stance = {}
+        if v2_rollup:
+            for r in v2_rollup["summary"]:
+                v2_by_stance[r["stance"]] = r
+        v3_by_stance = {r["stance"]: r for r in v3_summary}
+
+        # Merged donor list per stance for top5/hhi recompute.
+        # We pull "all donors" via aggregate_for_measure with a huge
+        # donor_limit and v3's top_donors_total with a high limit too.
+        v3_donors_full = self.get_top_donors_total(measure_db_id, limit=10_000)
+        donors_by_stance: Dict[str, Dict[str, float]] = defaultdict(dict)
+        if v2_rollup:
+            for d in v2_rollup["donors"]:
+                donors_by_stance[d["stance"]][d["donor_name_canon"]] = (
+                    donors_by_stance[d["stance"]].get(d["donor_name_canon"], 0.0)
+                    + float(d["total_amount"] or 0)
+                )
+        for d in v3_donors_full:
+            donors_by_stance[d["stance"]][d["donor_name_canon"]] = (
+                donors_by_stance[d["stance"]].get(d["donor_name_canon"], 0.0)
+                + float(d["total_amount"] or 0)
+            )
+        # Sort merged lists by amount desc for top5/hhi recompute.
+        donors_sorted: Dict[str, List[Dict]] = {}
+        for stance, dmap in donors_by_stance.items():
+            donors_sorted[stance] = sorted(
+                ({"donor_name_canon": n, "total_amount": a}
+                 for n, a in dmap.items()),
+                key=lambda d: (-d["total_amount"], d["donor_name_canon"]),
+            )
+
+        all_stances = sorted(set(v2_by_stance) | set(v3_by_stance))
+        out: List[Dict] = []
+        for stance in all_stances:
+            v2 = v2_by_stance.get(stance) or {}
+            v3 = v3_by_stance.get(stance) or {}
+            monetary = float(v2.get("total_receipts") or 0)
+            non_monetary = float(v3.get("total_amount") or 0)
+            total = monetary + non_monetary
+            n_committees = (
+                int(v2.get("n_committees") or 0)
+                + (int(v3["n_committees"]) if v3.get("n_committees") else 0)
+            ) or None
+            n_transactions = (v3.get("n_transactions") or None)
+            top5_share, hhi = self._recompute_top5_hhi(
+                total, donors_sorted.get(stance, [])
+            )
+            out.append({
+                "stance": stance,
+                "total_receipts": round(total, 2),
+                "monetary_amount": round(monetary, 2),
+                "non_monetary_amount": round(non_monetary, 2),
+                "n_committees": n_committees,
+                "n_transactions": n_transactions,
+                "top5_share": top5_share,
+                "hhi": hhi,
+            })
+        return out
+
+    def get_combined_breakdown_by_type(self, measure_db_id: int) -> List[Dict]:
+        """Per-stance, per-receipt-type breakdown. Adds 'monetary_contribution'
+        rows synthesized from v2 in front of the v3 by-type rows.
+
+        Each row: {stance, receipt_type, total_amount, n_committees,
+                   n_transactions}
+        receipt_type ∈ {monetary_contribution, loan, in_kind,
+                        independent_expenditure}
+        top5_share / hhi intentionally omitted at the per-type level —
+        the UI shows breakdown for orientation, not for concentration
+        analysis (the per-stance get_combined_summary carries those).
+        """
+        v3_rows = self.get_finance_breakdown_by_type(measure_db_id)
+        v2_rollup = self.aggregate_for_measure(measure_db_id)
+        out: List[Dict] = []
+        if v2_rollup:
+            for s in v2_rollup["summary"]:
+                if not s.get("total_receipts"):
+                    continue
+                out.append({
+                    "stance": s["stance"],
+                    "receipt_type": "monetary_contribution",
+                    "total_amount": round(float(s["total_receipts"]), 2),
+                    "n_committees": int(s.get("n_committees") or 0) or None,
+                    "n_transactions": None,
+                })
+        for r in v3_rows:
+            out.append({
+                "stance": r["stance"],
+                "receipt_type": r["receipt_type"],
+                "total_amount": round(float(r["total_amount"]), 2),
+                "n_committees": r.get("n_committees"),
+                "n_transactions": r.get("n_transactions"),
+            })
+        out.sort(key=lambda x: (x["stance"], x["receipt_type"]))
+        return out
+
+    def get_combined_top_donors(
+        self,
+        measure_db_id: int,
+        *,
+        stance: Optional[str] = None,
+        limit: int = 10,
+    ) -> List[Dict]:
+        """Top-N donors per stance, merging v2 monetary + v3 sources by
+        donor_name_canon. Re-ranks by combined total within stance.
+
+        Each row: {stance, donor_name_canon, donor_type, donor_sector,
+                   total_amount, flow_types}
+        donor_sector resolved at query time.
+        """
+        # Pull a large slice from each side so the merge doesn't lose
+        # donors that ranked low individually but pop on combined total.
+        v2_top = self.get_top_donors(
+            self.resolve_campaign(measure_db_id=measure_db_id) or "",
+            limit=10_000,
+        ) if False else []
+        # v2 get_top_donors keys on finance_campaign_id; for multi-
+        # campaign measures use aggregate_for_measure which merges.
+        v2_rollup = self.aggregate_for_measure(measure_db_id, donor_limit=10_000)
+        if v2_rollup:
+            v2_top = v2_rollup["donors"]
+        v3_top = self.get_top_donors_total(measure_db_id, limit=10_000)
+
+        # Merge per (stance, donor_name_canon).
+        merged: Dict[tuple, Dict] = {}
+        for d in v2_top:
+            key = (d["stance"], d["donor_name_canon"])
+            entry = merged.setdefault(key, {
+                "stance": d["stance"],
+                "donor_name_canon": d["donor_name_canon"],
+                "donor_type": d.get("donor_type"),
+                "total_amount": 0.0,
+                "flow_types": set(),
+            })
+            entry["total_amount"] += float(d.get("total_amount") or 0)
+            entry["flow_types"].add("monetary_contribution")
+        for d in v3_top:
+            key = (d["stance"], d["donor_name_canon"])
+            entry = merged.setdefault(key, {
+                "stance": d["stance"],
+                "donor_name_canon": d["donor_name_canon"],
+                "donor_type": d.get("donor_type"),
+                "total_amount": 0.0,
+                "flow_types": set(),
+            })
+            entry["total_amount"] += float(d.get("total_amount") or 0)
+            if entry["donor_type"] is None:
+                entry["donor_type"] = d.get("donor_type")
+            for ft in d.get("flow_types", []):
+                entry["flow_types"].add(ft)
+
+        # Per-stance ranking + limit
+        by_stance: Dict[str, List[Dict]] = defaultdict(list)
+        for entry in merged.values():
+            by_stance[entry["stance"]].append(entry)
+        stances = [stance] if stance is not None else sorted(by_stance.keys())
+        out: List[Dict] = []
+        for s in stances:
+            ranked = sorted(
+                by_stance.get(s, []),
+                key=lambda d: (
+                    -d["total_amount"],
+                    d["donor_name_canon"] is None,
+                    d["donor_name_canon"] or "",
+                ),
+            )[:limit]
+            for d in ranked:
+                out.append({
+                    "stance": d["stance"],
+                    "donor_name_canon": d["donor_name_canon"],
+                    "donor_type": d["donor_type"],
+                    "donor_sector": get_donor_sector(d["donor_name_canon"]),
+                    "total_amount": round(d["total_amount"], 2),
+                    "flow_types": sorted(d["flow_types"]),
+                })
+        return out
+
+    def get_combined_timeline(self, measure_db_id: int) -> List[Dict]:
+        """Merge v2 weekly + v3 weekly per (stance, week_start), sum,
+        recompute cumulative per stance. Each row:
+        {stance, week_start, weekly_receipts, cumulative_receipts}
+        """
+        v2_rollup = self.aggregate_for_measure(measure_db_id)
+        v2_timeline = v2_rollup["timeline"] if v2_rollup else []
+        v3_timeline = self.get_finance_timeline_total(measure_db_id)
+
+        weekly: Dict[tuple, float] = defaultdict(float)
+        for r in v2_timeline:
+            weekly[(r["stance"], r["week_start"])] += float(
+                r.get("weekly_receipts") or 0
+            )
+        for r in v3_timeline:
+            weekly[(r["stance"], r["week_start"])] += float(
+                r.get("weekly_amount") or 0
+            )
+
+        # Sort and recompute cumulative per stance.
+        rows_sorted = sorted(weekly.items(), key=lambda kv: (kv[0][0], kv[0][1]))
+        cumulative: Dict[str, float] = defaultdict(float)
+        out: List[Dict] = []
+        for (stance, week), amt in rows_sorted:
+            cumulative[stance] += amt
+            out.append({
+                "stance": stance,
+                "week_start": week,
+                "weekly_receipts": round(amt, 2),
+                "cumulative_receipts": round(cumulative[stance], 2),
+            })
+        return out
+
+    def get_combined_calendar_year_receipts(self) -> List[Dict]:
+        """Cross-measure spending arc, merged v2 monetary + v3
+        (loans+in-kind+IE) by year. Each row:
+        {year, total_receipts, n_measures}
+        """
+        v2_rows = self.get_calendar_year_receipts()
+        v3_rows = self.get_calendar_year_receipts_v3()
+        merged: Dict[int, Dict] = {}
+        for r in v2_rows:
+            merged.setdefault(r["year"], {
+                "year": r["year"], "total": 0.0, "measures": set(),
+            })
+            merged[r["year"]]["total"] += float(r.get("total_receipts") or 0)
+            # v2 doesn't expose the measure set per year, just count; we
+            # approximate by storing the COUNT-as-set placeholder. Best
+            # effort: take MAX(v2_count, v3_count) for n_measures (since
+            # the actual sets likely overlap heavily).
+            merged[r["year"]]["v2_count"] = int(r.get("n_measures") or 0)
+        for r in v3_rows:
+            entry = merged.setdefault(r["year"], {
+                "year": r["year"], "total": 0.0, "measures": set(), "v2_count": 0,
+            })
+            entry["total"] += float(r.get("total_amount") or 0)
+            entry["v3_count"] = int(r.get("n_measures") or 0)
+        return [
+            {
+                "year": e["year"],
+                "total_receipts": round(e["total"], 2),
+                "n_measures": max(
+                    e.get("v2_count", 0), e.get("v3_count", 0)
+                ),
+            }
+            for e in sorted(merged.values(), key=lambda x: x["year"])
+        ]
+
```

## Reference: the other 8 files in this commit

The full diff for `bec2abe` includes test additions, consumer-surface
swaps (server.py / finance.py / generator.py / generate_insights.py),
methodology copy updates in two places of generator.py, and the
regenerated `insights.json` + `index.html` data artifacts. The
operations.py change is the substantive new code; the rest is
plumbing that calls the new methods.

To see all of it:
```
git show bec2abe
git show bec2abe -- scraper/scripts/generate_insights.py
git show bec2abe -- scraper/src/api/server.py
git show bec2abe -- scraper/src/website/generator.py
```

Or pull the commit checked out: `git checkout bec2abe`.
