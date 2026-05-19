# Codex review round 2: Phase 5 step 1 follow-up

> **For Codex:** This is a follow-up to your round-1 review of Phase 5
> step 1 (`phase5_step1_review.md` / `phase5_step1_review_deep.md` in
> this directory). You flagged 3 issues; this doc shows what was fixed
> and asks you to look at the new shape. Live commit: `d2d2a5f` on
> `main` (parent: `4542d4a` was your round-1 target).

---

## TL;DR of changes since your round-1 review

You flagged:
1. **n_committees inconsistency** between summary_total path and
   breakdown_by_type for IE.
2. **primary_attribution_source rollup** not actually amount-weighted.
3. **measure_db_id guard** missing from rollup queries — "cheap
   defensive check."

What was implemented:
1. ✅ **NULL-preserving via `NULLIF(COUNT(...), 0)`** at SQL level +
   new `_opt_int` helper at Python level.
2. ✅ **New `_amount_weighted_attribution_sources` helper** that queries
   the flow table with `ROW_NUMBER() OVER (PARTITION BY stance, donor
   ORDER BY SUM(amount) DESC)`. Replaces the previous JSON-based
   first-non-null pick. By-type return field renamed
   `attribution_source_mode` → `attribution_source`.
3. ✅ **Bigger fix than suggested:** filtering the per-campaign
   views/tables by `measure_db_id` actually doesn't work because they
   store `MAX(measure_db_id)` per campaign, collapsing
   cross-measure-spanning campaigns to one (arbitrary) measure. Fix:
   **aggregate all 4 methods directly from `finance_flow_v3`** instead
   of going through derived tables/views.

## Validation done

- 30 v3 tests pass (was 18 — added 12 new for the Codex-suggested
  scenarios + the rewrite).
- 118 v2 tests still green.
- **Reconciliation:** sum of `get_finance_summary_total` across all
  181 measures = $2,510,050,967.24, matches raw flow `SUM(amount)
  WHERE quarantine_reason IS NULL` to the penny.
- **Per-measure invariant:** breakdown_by_type sums = summary_total
  for every (stance) of every measure tested (PROP_27_2022,
  PROP_22_2020 spot-checked).
- Smoke-tested against real v3 db: PROP_27_2022 returns sensible top
  donors per stance (San Manuel oppose, FanDuel/DraftKings support)
  with correct flow_types unions across types.

## What's now NEW that wasn't in round-1

The flow-direct rewrite introduces new concerns that didn't exist in
the round-1 code. Please scrutinize these:

### A. Performance under flow-direct reads

The methods now scan/aggregate `finance_flow_v3` (912K total rows;
~48K accepted) per call. Previously they hit pre-aggregated derived
tables (652 / 8,511 / 7,488 rows). The new SQL filters on
`measure_db_id = ? AND finance_campaign_id IN (?,?,?...)` so it
*should* use the indexes on those columns — but I haven't verified
the query plan.

**Verify:**
1. Does `finance_flow_v3` have indexes on `measure_db_id`,
   `finance_campaign_id`, and `quarantine_reason`? (I haven't checked.)
2. What's the expected per-call latency at the read-path scale (UI
   modal opens, briefing-pipeline iterations across all measures)?
3. Is there a case where the aggregator does a full-table scan
   despite the filters?

If performance is a concern, options are:
- Add indexes (cheap, one-time).
- Add an index on `(measure_db_id, finance_campaign_id, quarantine_reason)`.
- Keep the derived tables in sync and use them as a fast path, with
  flow as fallback. (Complex; probably not worth it.)
- Cache method results in a per-`FinanceDatabase`-instance dict (UI
  typically queries one measure at a time, so caching has little
  effect; briefing pipeline iterates more).

### B. Correctness of `NULLIF(COUNT(DISTINCT COALESCE(...)), 0)`

The SQL pattern:
```sql
NULLIF(
    COUNT(DISTINCT COALESCE(
        committee_id, cover_committee_id,
        cover_filer_id, reported_filer
    )),
    0
) AS n_committees
```

Intent: return None when all 4 fields are NULL across all rows in
the (stance) or (stance, receipt_type) group; otherwise return the
DISTINCT count.

Verified empirically against the live db: PROP_27_2022 IE rows now
return `n_committees=1` (via `reported_filer`), not None. That's
actually MORE useful than the previous None — UI sees "1 filer
committee" rather than "N/A".

**Verify:**
1. Is the `COALESCE` chain order intentional, or arbitrary? Currently
   it's `committee_id > cover_committee_id > cover_filer_id >
   reported_filer`. Does the order matter for the DISTINCT count?
   (I think not — DISTINCT operates on the resulting non-null value
   per row regardless of which field provided it.)
2. **Edge case:** a single accepted row with all 4 NULL → COUNT = 0
   → NULLIF returns NULL → `_opt_int(None) = None`. Is that right?
   Or should the row's existence force at least "1 unattributed"?
3. Could `MAX(donor_type)` or `MAX(donor_sector)` mask intentional
   data? Different rows for the same donor could in theory carry
   different `donor_type` values (e.g. one row tagged "committee",
   another "individual"). `MAX()` picks lex-max, ignoring counts.
   v2's `aggregate_for_measure` has the same pattern — probably not
   worth fixing in this commit.

### C. Amount-weighted attribution_source — tie behavior

The SQL:
```sql
ROW_NUMBER() OVER (
    PARTITION BY stance, donor_name_canon
    ORDER BY attr_total DESC, attribution_source
) AS rn
...
WHERE rn = 1
```

If two attribution_sources have *exactly* equal `SUM(amount)`,
secondary sort `, attribution_source` breaks the tie lexicographically
(deterministic but arbitrary).

**Verify:**
1. Is the tie-break appropriate? Alternative: tertiary by
   `MIN(txn_date)` or just leave as None and let the caller decide.
2. Test gap: I don't have a tie-case test. Worth adding?

### D. Cross-source attribution_source values

`finance_flow_v3.attribution_source` has values `'filer'` and
`'funding_source'`. The flow-direct rollup will pick whichever has
higher amount across the donor's flows.

**Verify:**
1. Could a donor legitimately have BOTH `filer` and `funding_source`
   attribution under the same measure (e.g. they filed an IE AND
   donated through a committee that was also their funding source)?
2. If yes, is "amount-weighted modal" the right rollup, or should we
   report both with their share?

The current API returns just one string per donor. v2's
`get_top_donors` doesn't have this field — it's new.

### E. Test coverage assessment

30 v3 tests now cover:

**Round-1 baseline (still passing under flow-direct):**
- Single-campaign, no-flows-returns-empty
- 2-campaign collision rollup with merged donor totals
- Quarantine filtering
- Per-stance ranking with imbalanced sides
- Stance filter narrows correctly
- Receipt-type filter narrows correctly
- flow_types union across types
- donor_sector re-resolution (stored value ignored)

**Round-2 additions (Codex-suggested + needed-for-rewrite):**
- n_committees NULL preservation (committee_id explicitly NULL,
  COALESCE chain all-NULL)
- n_committees positive (3 distinct committees, repeat committees
  don't bump the count)
- Amount-weighted attribution source ($80M filer beats $20M
  funding_source)
- Amount-weighted vs lexicographic (apple_source $10M beats
  zebra_source $1K — verifies the ORDER BY isn't just MAX)
- by_type amount-weighted within receipt_type
- 3-campaign collision (summary + top donors)
- limit=1 returns single donor per stance
- limit > donor count returns all (no padding, no error)
- by_type limit=1 partitioned by stance (returns 2 rows total —
  one per stance)
- **Cross-measure flow with shared campaign_id excluded** (the
  defense-in-depth test that originally failed under the
  view-filter approach, now passes under flow-direct)
- NULL donor_name_canon does not crash read methods (invariant
  test — accepted rows shouldn't have NULL, but methods must be
  defensive)

**What might still be missing:**
1. **Tie-break in attribution_source** (Section C).
2. **Quarantine filter under cross-measure flow share** — does the
   measure_db_id guard correctly exclude quarantined rows AS WELL AS
   wrong-measure rows? (Test would insert flows with different
   quarantine + measure combos.)
3. **A row with non-null donor_name_canon but NULL stance** (does
   the GROUP BY still produce a sensible row, or does it filter out?).
4. **Receipt_type with no flows for either stance** — should
   `get_top_donors_by_type` return empty (likely), but worth
   confirming.
5. **Performance regression test** — assert that a single read
   completes in < some reasonable wall-time. Probably overkill.
6. **The pretty-rare case of `donor_name_canon` ties** — two
   donors with identical canonical names but different
   donor_types/sectors. The SQL `MAX(donor_type)` picks one.

### F. Architectural concern: the derived tables/views are now dead

The flow-direct rewrite means `finance_summary_by_type`,
`finance_top_donors_by_type`, `finance_timeline_weekly_by_type`,
`finance_summary_total` view, `finance_top_donors_total` view, and
`finance_timeline_weekly_total` view are NOT used by the read path.

They're still populated by `scripts/v3/rebuild_derived.py` and live
in the v3 db. They serve as:
- An audit artifact ("here's what we materialized at build time").
- Potentially a fast path if performance becomes a problem.

**Verify:**
1. Should we drop these tables/views entirely from v3?
2. Should `rebuild_derived.py` be retired?
3. Or keep them as audit + future-fast-path?

My (Igor's claude) instinct: keep them, document them as "not used
by app code, but available for audit and as a potential fast-path
re-introduction." Cost is rebuild time + a few MB of disk.

### G. The `_v3_campaign_ids_for_measure` helper

Still queries `finance_flow_v3` to find what campaigns are linked to
a measure. The four read methods then re-query the same table
filtered on those campaigns. Why two queries instead of one?

Reason: the helper's results (which campaigns) are needed for the
`_amount_weighted_attribution_sources` helper call. If we inlined,
we'd need to wrap everything in one mega-query. Two queries is
simpler.

But also: the helper's filter on `quarantine_reason IS NULL` means
a measure that has ONLY quarantined v3 flows returns empty. That's
probably right (the measure has no v3-attributable data) but worth
flagging.

**Verify:** is the two-query pattern okay, or should this be one
query with a CTE that defines campaign_ids and then aggregates?

## Deliverable

Please flag:

1. **Performance:** are the flow-direct reads going to be slow under
   real workload? Do we need indexes?
2. **NULLIF correctness:** any pathological input where the SQL
   pattern doesn't do what we think?
3. **Tie cases in attribution_source amount-weighting:** is the
   tertiary sort right?
4. **Test gaps:** any new scenarios (especially Section E.1–E.6)
   worth adding before this code ships behind UI.
5. **Architectural:** should the now-unused derived tables/views be
   dropped, or kept as audit/fast-path?

Round-1 calibration was right (conservative, prefer None over wrong
numbers). Same here — flag anything you'd want fixed before the UI
flip in step 2.

---

## The full diff (commit d2d2a5f, production code only)

```diff
diff --git a/scraper/src/finance/operations.py b/scraper/src/finance/operations.py
index 375a676..457f0c6 100644
--- a/scraper/src/finance/operations.py
+++ b/scraper/src/finance/operations.py
@@ -467,6 +467,14 @@ class FinanceDatabase:
         Each row: {stance, total_amount, n_committees, n_transactions,
                    top5_share, hhi}
         Empty list if no v3 flows for this measure.
+
+        Implementation reads directly from `finance_flow_v3` rather than
+        the `finance_summary_total` view because the view's `MAX(measure_db_id)`
+        per (campaign, stance) collapses cross-measure-spanning campaigns
+        (pathological today, defense-in-depth) and because the view's
+        n_committees uses `COUNT(DISTINCT COALESCE(...))` which returns 0
+        for all-NULL slices (e.g. IE rows). Going through flow lets us
+        preserve None for the not-applicable case via `NULLIF(..., 0)`.
         """
         campaign_ids = self._v3_campaign_ids_for_measure(measure_db_id)
         if not campaign_ids:
@@ -476,27 +484,34 @@ class FinanceDatabase:
         raw = self.v3_conn.execute(
             f"""
             SELECT stance,
-                   SUM(total_amount) AS total_amount,
-                   SUM(n_committees) AS n_committees,
-                   SUM(n_transactions) AS n_transactions
-            FROM finance_summary_total
-            WHERE finance_campaign_id IN ({placeholders})
-            GROUP BY stance
+                   SUM(amount) AS total_amount,
+                   NULLIF(
+                       COUNT(DISTINCT COALESCE(
+                           committee_id, cover_committee_id,
+                           cover_filer_id, reported_filer
+                       )),
+                       0
+                   ) AS n_committees,
+                   COUNT(*) AS n_transactions
+            FROM   finance_flow_v3
+            WHERE  measure_db_id = ?
+              AND  finance_campaign_id IN ({placeholders})
+              AND  quarantine_reason IS NULL
+            GROUP  BY stance
             """,
-            campaign_ids,
+            (measure_db_id, *campaign_ids),
         ).fetchall()
 
-        # Recompute top5_share + hhi against the merged donor list per
-        # stance — view-level metrics are per-campaign, would be wrong
-        # under rollup.
         donor_rows = self.v3_conn.execute(
             f"""
-            SELECT stance, donor_name_canon, SUM(total_amount) AS total_amount
-            FROM finance_top_donors_total
-            WHERE finance_campaign_id IN ({placeholders})
-            GROUP BY stance, donor_name_canon
+            SELECT stance, donor_name_canon, SUM(amount) AS total_amount
+            FROM   finance_flow_v3
+            WHERE  measure_db_id = ?
+              AND  finance_campaign_id IN ({placeholders})
+              AND  quarantine_reason IS NULL
+            GROUP  BY stance, donor_name_canon
             """,
-            campaign_ids,
+            (measure_db_id, *campaign_ids),
         ).fetchall()
         donors_by_stance: Dict[str, List[Dict]] = defaultdict(list)
         for r in donor_rows:
@@ -517,8 +532,8 @@ class FinanceDatabase:
             out.append({
                 "stance": stance,
                 "total_amount": total,
-                "n_committees": int(r["n_committees"] or 0),
-                "n_transactions": int(r["n_transactions"] or 0),
+                "n_committees": self._opt_int(r["n_committees"]),
+                "n_transactions": self._opt_int(r["n_transactions"]),
                 "top5_share": top5_share,
                 "hhi": hhi,
             })
@@ -539,32 +554,43 @@ class FinanceDatabase:
             return []
         placeholders = ",".join("?" for _ in campaign_ids)
 
+        # Aggregate from flow directly (not from finance_summary_by_type)
+        # for the same reasons as get_finance_summary_total: avoid the
+        # MAX(measure_db_id) collapse on cross-measure-spanning campaigns,
+        # and preserve NULL n_committees semantics via NULLIF.
         raw = self.v3_conn.execute(
             f"""
             SELECT stance, receipt_type,
-                   SUM(total_amount) AS total_amount,
-                   SUM(n_committees) AS n_committees,
-                   SUM(n_transactions) AS n_transactions
-            FROM finance_summary_by_type
-            WHERE finance_campaign_id IN ({placeholders})
-            GROUP BY stance, receipt_type
-            ORDER BY stance, receipt_type
+                   SUM(amount) AS total_amount,
+                   NULLIF(
+                       COUNT(DISTINCT COALESCE(
+                           committee_id, cover_committee_id,
+                           cover_filer_id, reported_filer
+                       )),
+                       0
+                   ) AS n_committees,
+                   COUNT(*) AS n_transactions
+            FROM   finance_flow_v3
+            WHERE  measure_db_id = ?
+              AND  finance_campaign_id IN ({placeholders})
+              AND  quarantine_reason IS NULL
+            GROUP  BY stance, receipt_type
+            ORDER  BY stance, receipt_type
             """,
-            campaign_ids,
+            (measure_db_id, *campaign_ids),
         ).fetchall()
 
-        # Per-(stance, receipt_type) merged donor lists for concentration
-        # recomputation. finance_top_donors_by_type already keys on
-        # receipt_type so this is one query.
         donor_rows = self.v3_conn.execute(
             f"""
             SELECT stance, receipt_type, donor_name_canon,
-                   SUM(total_amount) AS total_amount
-            FROM finance_top_donors_by_type
-            WHERE finance_campaign_id IN ({placeholders})
-            GROUP BY stance, receipt_type, donor_name_canon
+                   SUM(amount) AS total_amount
+            FROM   finance_flow_v3
+            WHERE  measure_db_id = ?
+              AND  finance_campaign_id IN ({placeholders})
+              AND  quarantine_reason IS NULL
+            GROUP  BY stance, receipt_type, donor_name_canon
             """,
-            campaign_ids,
+            (measure_db_id, *campaign_ids),
         ).fetchall()
         donors_by_slice: Dict[tuple, List[Dict]] = defaultdict(list)
         for r in donor_rows:
@@ -586,8 +612,12 @@ class FinanceDatabase:
                 "stance": r["stance"],
                 "receipt_type": r["receipt_type"],
                 "total_amount": total,
-                "n_committees": int(r["n_committees"] or 0),
-                "n_transactions": int(r["n_transactions"] or 0),
+                # NULL-preserving: finance_summary_by_type currently stores
+                # NULL n_committees for IE rows (no committee_id in the
+                # source). Coercing to 0 would misrepresent "not applicable"
+                # as "zero committees." UI must treat None as N/A.
+                "n_committees": self._opt_int(r["n_committees"]),
+                "n_transactions": self._opt_int(r["n_transactions"]),
                 "top5_share": top5_share,
                 "hhi": hhi,
             })
@@ -605,6 +635,74 @@ class FinanceDatabase:
             return []
         return [v for v in parsed if v is not None]
 
+    @staticmethod
+    def _opt_int(value) -> Optional[int]:
+        """NULL-preserving int conversion. SUM() over an all-NULL group
+        returns NULL; coercing that to 0 misrepresents "not applicable"
+        (e.g. n_committees for IE rows, which carry no committee_id /
+        cover_committee_id / cover_filer_id / reported_filer) as
+        "zero committees." Caller should treat None as "not applicable."
+        """
+        return None if value is None else int(value)
+
+    def _amount_weighted_attribution_sources(
+        self,
+        measure_db_id: int,
+        campaign_ids: List[str],
+        *,
+        stance: Optional[str] = None,
+        receipt_type: Optional[str] = None,
+    ) -> Dict[tuple, Optional[str]]:
+        """Pick the modal-by-amount attribution_source per (stance,
+        donor_name_canon) over the given campaign set, computed directly
+        from finance_flow_v3 (not from view rollups that lose the
+        amount-weighting under collision).
+
+        Returns dict keyed by (stance, donor_name_canon). Missing keys
+        imply no flows under the filter (e.g. donor only had quarantined
+        rows for the requested receipt_type).
+        """
+        if not campaign_ids:
+            return {}
+        placeholders = ",".join("?" for _ in campaign_ids)
+        params: List = [measure_db_id] + list(campaign_ids)
+        extra_clauses = ""
+        if stance is not None:
+            extra_clauses += " AND stance = ?"
+            params.append(stance)
+        if receipt_type is not None:
+            extra_clauses += " AND receipt_type = ?"
+            params.append(receipt_type)
+        cursor = self.v3_conn.execute(
+            f"""
+            WITH per_attr AS (
+                SELECT stance, donor_name_canon, attribution_source,
+                       SUM(amount) AS attr_total
+                FROM   finance_flow_v3
+                WHERE  measure_db_id = ?
+                  AND  finance_campaign_id IN ({placeholders})
+                  AND  quarantine_reason IS NULL
+                  {extra_clauses}
+                GROUP  BY stance, donor_name_canon, attribution_source
+            ),
+            ranked AS (
+                SELECT *, ROW_NUMBER() OVER (
+                    PARTITION BY stance, donor_name_canon
+                    ORDER BY attr_total DESC, attribution_source
+                ) AS rn
+                FROM per_attr
+            )
+            SELECT stance, donor_name_canon, attribution_source
+            FROM   ranked
+            WHERE  rn = 1
+            """,
+            params,
+        )
+        return {
+            (r["stance"], r["donor_name_canon"]): r["attribution_source"]
+            for r in cursor.fetchall()
+        }
+
     def get_top_donors_total(
         self,
         measure_db_id: int,
@@ -630,28 +728,29 @@ class FinanceDatabase:
             return []
         placeholders = ",".join("?" for _ in campaign_ids)
 
-        params: List = list(campaign_ids)
+        params: List = [measure_db_id] + list(campaign_ids)
         stance_clause = ""
         if stance is not None:
             stance_clause = "AND stance = ?"
             params.append(stance)
 
-        # Roll up: SUM total_amount across campaigns, then per-stance
-        # ROW_NUMBER. flow_types unioned across campaigns (parsed JSON
-        # arrays merged). primary_attribution_source picked as the
-        # source with the largest attr_total under the merged donor.
+        # Aggregate from finance_flow_v3 directly (single source of truth)
+        # rather than through finance_top_donors_total view. flow_types is
+        # a flat json_group_array over the donor's receipt_types — no
+        # nested-JSON unpacking needed.
         cursor = self.v3_conn.execute(
             f"""
             WITH per_donor AS (
                 SELECT stance, donor_name_canon,
-                       SUM(total_amount) AS total_amount,
-                       MAX(donor_type)   AS donor_type,
-                       SUM(n_underlying_rows) AS n_underlying_rows,
-                       json_group_array(flow_types) AS flow_types_nested,
-                       json_group_array(primary_attribution_source)
-                           AS attr_sources_nested
-                FROM   finance_top_donors_total
-                WHERE  finance_campaign_id IN ({placeholders}) {stance_clause}
+                       SUM(amount) AS total_amount,
+                       MAX(donor_type) AS donor_type,
+                       COUNT(*) AS n_underlying_rows,
+                       json_group_array(DISTINCT receipt_type) AS flow_types_json
+                FROM   finance_flow_v3
+                WHERE  measure_db_id = ?
+                  AND  finance_campaign_id IN ({placeholders})
+                  AND  quarantine_reason IS NULL
+                  {stance_clause}
                 GROUP  BY stance, donor_name_canon
             ),
             ranked AS (
@@ -663,30 +762,26 @@ class FinanceDatabase:
                 FROM   per_donor
             )
             SELECT stance, donor_name_canon, donor_type, total_amount,
-                   n_underlying_rows, flow_types_nested, attr_sources_nested
+                   n_underlying_rows, flow_types_json
             FROM   ranked
             WHERE  rn <= ?
             ORDER  BY stance, total_amount DESC, donor_name_canon
             """,
             (*params, limit),
         )
+        donor_rows = cursor.fetchall()
+
+        # Amount-weighted attribution source per (stance, donor) computed
+        # from the flow table directly. One query for the whole result
+        # set (scoped to this measure + campaigns + optional stance).
+        attr_source_map = self._amount_weighted_attribution_sources(
+            measure_db_id, campaign_ids, stance=stance,
+        )
 
         rows: List[Dict] = []
-        for r in cursor.fetchall():
-            # Merge nested json arrays: per_donor's json_group_array of
-            # json arrays produces e.g. '["[\"loan\",\"in_kind\"]","[...]"]'.
-            # Parse each leg, union into one flat list.
-            flow_types: List[str] = []
-            seen: set = set()
-            for leg in self._parse_json_array(r["flow_types_nested"]):
-                for ft in self._parse_json_array(leg):
-                    if ft not in seen:
-                        flow_types.append(ft)
-                        seen.add(ft)
-            attr_legs: List[str] = []
-            for leg in self._parse_json_array(r["attr_sources_nested"]):
-                if leg and leg not in attr_legs:
-                    attr_legs.append(leg)
+        for r in donor_rows:
+            flow_types = self._parse_json_array(r["flow_types_json"])
+            key = (r["stance"], r["donor_name_canon"])
             rows.append({
                 "stance": r["stance"],
                 "donor_name_canon": r["donor_name_canon"],
@@ -694,8 +789,8 @@ class FinanceDatabase:
                 "donor_sector": get_donor_sector(r["donor_name_canon"]),
                 "total_amount": float(r["total_amount"] or 0),
                 "flow_types": flow_types,
-                "primary_attribution_source": attr_legs[0] if attr_legs else None,
-                "n_underlying_rows": int(r["n_underlying_rows"] or 0),
+                "primary_attribution_source": attr_source_map.get(key),
+                "n_underlying_rows": self._opt_int(r["n_underlying_rows"]),
             })
         return rows
 
@@ -712,14 +807,20 @@ class FinanceDatabase:
 
         Each row: {stance, receipt_type, donor_name_canon, donor_type,
                    donor_sector, total_amount, n_underlying_rows,
-                   attribution_source_mode}
+                   attribution_source}
+
+        attribution_source is amount-weighted over the flow table for
+        the (measure_db_id, receipt_type, stance, donor) cohort —
+        replaces v3's pre-rollup `attribution_source_mode` column which
+        was per-(campaign, stance, receipt_type, donor) and would drift
+        under cross-campaign rollup via lexicographic MAX().
         """
         campaign_ids = self._v3_campaign_ids_for_measure(measure_db_id)
         if not campaign_ids:
             return []
         placeholders = ",".join("?" for _ in campaign_ids)
 
-        params: List = list(campaign_ids) + [receipt_type]
+        params: List = [measure_db_id, receipt_type] + list(campaign_ids)
         stance_clause = ""
         if stance is not None:
             stance_clause = "AND stance = ?"
@@ -729,13 +830,14 @@ class FinanceDatabase:
             f"""
             WITH per_donor AS (
                 SELECT stance, receipt_type, donor_name_canon,
-                       SUM(total_amount) AS total_amount,
-                       MAX(donor_type)   AS donor_type,
-                       SUM(n_underlying_rows) AS n_underlying_rows,
-                       MAX(attribution_source_mode) AS attribution_source_mode
-                FROM   finance_top_donors_by_type
-                WHERE  finance_campaign_id IN ({placeholders})
+                       SUM(amount) AS total_amount,
+                       MAX(donor_type) AS donor_type,
+                       COUNT(*) AS n_underlying_rows
+                FROM   finance_flow_v3
+                WHERE  measure_db_id = ?
                   AND  receipt_type = ?
+                  AND  finance_campaign_id IN ({placeholders})
+                  AND  quarantine_reason IS NULL
                   {stance_clause}
                 GROUP  BY stance, receipt_type, donor_name_canon
             ),
@@ -748,13 +850,20 @@ class FinanceDatabase:
                 FROM   per_donor
             )
             SELECT stance, receipt_type, donor_name_canon, donor_type,
-                   total_amount, n_underlying_rows, attribution_source_mode
+                   total_amount, n_underlying_rows
             FROM   ranked
             WHERE  rn <= ?
             ORDER  BY stance, total_amount DESC, donor_name_canon
             """,
             (*params, limit),
         )
+        donor_rows = cursor.fetchall()
+
+        # Amount-weighted attribution source, scoped to this receipt_type.
+        attr_source_map = self._amount_weighted_attribution_sources(
+            measure_db_id, campaign_ids,
+            stance=stance, receipt_type=receipt_type,
+        )
 
         return [
             {
@@ -764,10 +873,12 @@ class FinanceDatabase:
                 "donor_type": r["donor_type"],
                 "donor_sector": get_donor_sector(r["donor_name_canon"]),
                 "total_amount": float(r["total_amount"] or 0),
-                "n_underlying_rows": int(r["n_underlying_rows"] or 0),
-                "attribution_source_mode": r["attribution_source_mode"],
+                "n_underlying_rows": self._opt_int(r["n_underlying_rows"]),
+                "attribution_source": attr_source_map.get(
+                    (r["stance"], r["donor_name_canon"])
+                ),
             }
-            for r in cursor.fetchall()
+            for r in donor_rows
         ]
```
