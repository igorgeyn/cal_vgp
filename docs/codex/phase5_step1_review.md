# Codex review request: Phase 5 step 1 (v3 read methods)

> **For Codex:** This is a self-contained review request. Read this whole
> file — context, design choices, things to scrutinize, and the full diff
> are all below. Live commit: `4542d4a` on `main`.

## Context

This is the **library/API migration step** of Phase 5 of the v3 finance
expansion. Phase 4 (already shipped, rounds 10–14 fixes integrated)
built `finance_statewide_v3.db` carrying loans + in-kind + IE on top of
the v2 monetary contributions. v3 totals: 47,942 accepted rows / $2.51B,
all reconciles $0 diff to source.

This commit adds **4 read methods** to the existing `FinanceDatabase`
class in `scraper/src/finance/operations.py`. They wrap the v3 db so
the upcoming UI flip (step 2) has a clean API to call. v2 methods are
unchanged.

The atomic UI commit follows step 1, so step 1 is the **right time to
catch correctness bugs in the rollup logic**. The bug families we've
been hunting through rounds 10–14 (attribution misroutes) are upstream
in resolver/ingest, but this layer introduces a *new* bug surface:
post-attribution **rollup arithmetic** for year-offset collisions
(multiple `finance_campaign_id`s sharing a `measure_db_id`).

## Files in scope

- `scraper/src/finance/schema.py` — adds `FINANCE_DB_V3_PATH` constant
- `scraper/src/finance/operations.py` — lazy `v3_conn` + 4 new methods

(The 18 unit tests in `scraper/tests/test_finance_db_v3.py` are not
included in the review diff below — they're hermetic with verbatim view
DDL and exercise basic cases. Please flag anything you'd test that
isn't.)

## Relevant v3 db schema (just enough to follow the diff)

```sql
-- Fact table (912K rows total, 47,942 accepted with quarantine_reason IS NULL)
CREATE TABLE finance_flow_v3 (
    flow_id, finance_campaign_id, source_crosswalk_campaign_id,
    measure_db_id, stance, receipt_type, amount, txn_date, week_start,
    source_table, source_form_type, filing_id, amend_id,
    committee_id, cover_committee_id, cover_filer_id, reported_filer,
    donor_name_canon, donor_type, donor_sector,
    attribution_source, quarantine_reason, ...
)
```

**Derived TABLES** (built by `rebuild_derived.py` from the flow table):
```sql
CREATE TABLE finance_summary_by_type (
    finance_campaign_id, measure_db_id, stance, receipt_type,
    total_amount, n_committees, n_transactions, top5_share, hhi,
    PRIMARY KEY (finance_campaign_id, stance, receipt_type)
)
CREATE TABLE finance_top_donors_by_type (
    finance_campaign_id, measure_db_id, stance, receipt_type,
    donor_name_canon, donor_type, donor_sector, total_amount,
    n_underlying_rows, attribution_source_mode,
    PRIMARY KEY (finance_campaign_id, stance, receipt_type, donor_name_canon)
)
```

**Derived VIEWS** (collapse the receipt_type dimension, computed at
query time from the flow table):
```sql
CREATE VIEW finance_summary_total AS  -- per (campaign, stance) totals
WITH per_donor AS (
    SELECT finance_campaign_id, stance, donor_name_canon,
           SUM(amount) AS donor_total
    FROM finance_flow_v3 WHERE quarantine_reason IS NULL
    GROUP BY finance_campaign_id, stance, donor_name_canon
),
campaign_totals AS (
    SELECT finance_campaign_id, stance, SUM(donor_total) AS grand_total
    FROM per_donor GROUP BY finance_campaign_id, stance
),
... [top5, hhi, flow_agg CTEs] ...
SELECT fa.finance_campaign_id, fa.measure_db_id, fa.stance,
       fa.total_amount, fa.n_committees, fa.n_transactions,
       CASE WHEN ct.grand_total > 0
            THEN 100.0 * t5.top5_sum / ct.grand_total ELSE NULL
       END AS top5_share,
       h.hhi AS hhi
FROM flow_agg fa
LEFT JOIN campaign_totals ct USING (finance_campaign_id, stance)
LEFT JOIN top5 t5 USING (finance_campaign_id, stance)
LEFT JOIN hhi_calc h USING (finance_campaign_id, stance);

CREATE VIEW finance_top_donors_total AS
-- Per-donor totals across all receipt types, with flow_types as
-- json_group_array(DISTINCT receipt_type) and attribution_sources as
-- json_group_array(DISTINCT attribution_source), plus a
-- primary_attribution_source picked by ROW_NUMBER over attr_total DESC.
... (similar shape, see operations.py comment for full DDL)
```

## Design decisions (already confirmed)

1. **Keying:** all 4 methods accept `measure_db_id`, NOT
   `finance_campaign_id`. UI's natural handle is the measure. v3 views
   are keyed by `finance_campaign_id`, so when a measure has multiple
   campaigns (year-offset recovery — e.g. PROP_4_2008 + PROP_4_2010
   both linked to measure_db_id 1189), the methods sum across them.

2. **Concentration metrics:** `top5_share` and `hhi` are **recomputed**
   per (stance[, receipt_type]) against the merged donor list. The
   view-level top5/hhi values are per-campaign and would be wrong under
   rollup.

3. **donor_sector:** re-resolved at query time via
   `donor_sectors.get_donor_sector()`. The stored `donor_sector` column
   on `finance_flow_v3` / view output is intentionally NOT used in the
   read path — curated additions to `donor_sectors.py` should land in
   the UI immediately without a `rebuild_derived.py` rerun. This
   matches v2's `get_top_donors` pattern.

4. **v3 connection is lazy.** Only opened on first v3 method call,
   so v2-only callers (and fresh checkouts without a v3 db built)
   aren't broken.

## Specific things to scrutinize

These are the areas Igor most wants a second set of eyes on:

### A. Rollup arithmetic correctness

In `get_finance_summary_total`, the merged-donor recomputation:

```python
donor_rows = self.v3_conn.execute(
    f"""
    SELECT stance, donor_name_canon, SUM(total_amount) AS total_amount
    FROM finance_top_donors_total
    WHERE finance_campaign_id IN ({placeholders})
    GROUP BY stance, donor_name_canon
    """,
    campaign_ids,
).fetchall()
```

We're summing `total_amount` from the `finance_top_donors_total` VIEW
across collision campaigns. Same donor across 2 campaigns gets one row
with summed amount. Then `_recompute_top5_hhi` computes against this
merged list.

**Hypothesis to break:** is it possible for the view's per-campaign
`total_amount` to *not* equal `SUM(amount) FROM finance_flow_v3 GROUP
BY (campaign, stance, donor)`? If the view does anything fancier (e.g.
filtering, dedup that the flow table doesn't replicate), the rollup
arithmetic could drift from the truth.

### B. SQL injection / parameterization

The 4 methods build `IN ({placeholders})` clauses with `?`-style
placeholders and pass the campaign_ids tuple. `_v3_campaign_ids_for_measure`
returns a `List[str]` from a parameterized query, so the values are
trusted SQL-wise. Confirm there's no string-interpolation gap.

### C. flow_types union logic in `get_top_donors_total`

The CTE produces `flow_types_nested` via
`json_group_array(flow_types)` where each inner `flow_types` is itself
a JSON array (from the view's `json_group_array(DISTINCT receipt_type)`).
The Python side unpacks with two `_parse_json_array` calls:

```python
for leg in self._parse_json_array(r["flow_types_nested"]):
    for ft in self._parse_json_array(leg):
        if ft not in seen:
            flow_types.append(ft)
            seen.add(ft)
```

Is the nested-JSON parse correct? The inner leg is a string-encoded
JSON array (because that's how `json_group_array` of a JSON value
behaves in SQLite — it doesn't re-parse), so each leg should parse
back to a list of strings.

### D. `primary_attribution_source` rollup choice

For each merged donor, the code does
`json_group_array(primary_attribution_source)` and takes
`attr_legs[0]` as the rollup primary. This is the first non-null
value, NOT the largest by amount. Is that the right choice? An
alternative: re-rank by SUM(amount) across the merged source legs.

Argument for current: typically one source dominates a donor's
attribution; picking any non-null is fine for display.
Argument against: a donor with attribution split 51/49 across two
sources would get either one with no transparency.

### E. `n_committees` rollup correctness

In `get_finance_summary_total`:
```python
SUM(n_committees) AS n_committees
```

This sums per-campaign distinct-committee counts. A committee that
files across 2 collision campaigns gets counted twice. v2's
`aggregate_for_measure` has the same caveat ("best-effort; may
double-count"). Should we instead query the flow table directly for
a true DISTINCT count? That'd require an extra query but be accurate.

### F. n_committees=0 surprise for non-monetary types

In smoke testing against the real v3 db, `n_committees` for IE rows
came back as 0 (because IE rows don't carry committee_id in the
"receiving committee" sense — they're spent direct to vendors). This
is *data*, not bug, but worth flagging whether the UI should display
"0 committees" for IE rows or hide that metric for non-monetary types.

### G. Stance filter behavior

`stance: Optional[str] = None` — when None, both stances come back
ranked per-stance. When a string, filtered to that stance. Is the
keyword-only argument (`*, stance=None`) the right ergonomics?
Alternative: positional. v2 doesn't have a stance filter.

### H. Anything missing from the test fixtures

The 18 hermetic tests cover:
- single-campaign, collision rollup, no-flows-returns-empty
- quarantine filtering
- per-stance ranking (smaller side not crowded out)
- stance filter
- receipt_type filter
- flow_types union across types
- donor_sector re-resolution

What would you test that isn't covered?

## Pre-existing test failures (not caused by this commit)

`test_models.py::test_ballot_measure_optional_fields` and several in
`test_database.py` fail on `main` before this commit. Confirmed by
stash-test. Out of scope for this review.

## Deliverable

Please flag:
1. Any correctness bug in the rollup arithmetic.
2. Any case where the SQL would return wrong/surprising rows.
3. Any missing test scenario worth adding before this code ships behind UI.
4. Any API ergonomics concern that would cost us at the UI-flip step.

The bug-fix arc through rounds 10–14 caught issues in resolver layer;
this commit is a different layer (post-attribution rollup), so the
nature of bugs to look for is different: arithmetic / rollup / boundary
conditions, not attribution logic.

---

## The full diff (commit 4542d4a, production code only)

```diff
diff --git a/scraper/src/finance/operations.py b/scraper/src/finance/operations.py
index d5ed040..375a676 100644
--- a/scraper/src/finance/operations.py
+++ b/scraper/src/finance/operations.py
@@ -11,21 +11,40 @@ distinct campaign in 2022 and another in 2024. Callers passing a bare
 measure_id without a year that matches multiple active campaigns will get
 a ValueError; pass `measure_db_id` or year to disambiguate.
 """
+import json
 import sqlite3
 from collections import defaultdict
 from pathlib import Path
 from typing import Iterable, List, Dict, Optional

 from .donor_sectors import get_donor_sector
-from .schema import FINANCE_DB_PATH
+from .schema import FINANCE_DB_PATH, FINANCE_DB_V3_PATH


 class FinanceDatabase:
-    def __init__(self, db_path: Optional[Path] = None):
+    def __init__(
+        self,
+        db_path: Optional[Path] = None,
+        v3_db_path: Optional[Path] = None,
+    ):
         self.db_path = db_path or FINANCE_DB_PATH
         self.conn = sqlite3.connect(str(self.db_path))
         self.conn.row_factory = sqlite3.Row

+        # v3 connection is lazy — only opened when a get_*_total /
+        # get_*_by_type method is called. Keeps v2-only consumers unaffected
+        # if the v3 db isn't present (e.g. on a fresh checkout before
+        # scripts/v3/ has been run).
+        self._v3_db_path = v3_db_path or FINANCE_DB_V3_PATH
+        self._v3_conn: Optional[sqlite3.Connection] = None
+
+    @property
+    def v3_conn(self) -> sqlite3.Connection:
+        if self._v3_conn is None:
+            self._v3_conn = sqlite3.connect(str(self._v3_db_path))
+            self._v3_conn.row_factory = sqlite3.Row
+        return self._v3_conn
+
     # ---- Resolution helpers ------------------------------------------------

     def resolve_campaign(
@@ -396,6 +415,360 @@ class FinanceDatabase:
     def close(self):
         if self.conn:
             self.conn.close()
+        if self._v3_conn is not None:
+            self._v3_conn.close()
+            self._v3_conn = None
+
+    # ---- v3: expanded-scope reads ----------------------------------------
+    # All v3 methods key on `measure_db_id` (UI's natural handle) and roll
+    # up year-offset collisions internally, mirroring `aggregate_for_measure`.
+    # When a measure has multiple finance_campaign_ids (e.g. PROP_4_2008 +
+    # PROP_4_2010 both linked to measure_db_id 1189), we SUM across them
+    # per stance and recompute top5_share / hhi against the merged donor
+    # list. UI gets one row per stance ([per receipt_type] for the by_type
+    # variants), independent of the underlying campaign-id split.
+    # ----------------------------------------------------------------------
+
+    def _v3_campaign_ids_for_measure(self, measure_db_id: int) -> List[str]:
+        """Pull every finance_campaign_id v3 has flows for under a measure.
+        v3 carries `measure_db_id` directly on the fact table, so this is a
+        single-table lookup (no join to finance_campaign).
+        """
+        rows = self.v3_conn.execute(
+            "SELECT DISTINCT finance_campaign_id "
+            "FROM finance_flow_v3 "
+            "WHERE measure_db_id = ? AND quarantine_reason IS NULL "
+            "  AND finance_campaign_id IS NOT NULL "
+            "ORDER BY finance_campaign_id",
+            (measure_db_id,),
+        ).fetchall()
+        return [r[0] for r in rows]
+
+    def _recompute_top5_hhi(
+        self,
+        total: float,
+        merged_donors: List[Dict],
+    ) -> tuple[Optional[float], Optional[float]]:
+        """Recompute top5_share (%) and HHI (0..10000) against a merged
+        donor list. Returns (None, None) when total <= 0 or no donors."""
+        if total <= 0 or not merged_donors:
+            return None, None
+        top5_amount = sum(d["total_amount"] for d in merged_donors[:5])
+        top5_share = (top5_amount / total) * 100
+        hhi = sum(
+            ((d["total_amount"] / total) * 100) ** 2 for d in merged_donors
+        )
+        return top5_share, hhi
+
+    def get_finance_summary_total(self, measure_db_id: int) -> List[Dict]:
+        """Per-stance totals across ALL receipt types (monetary + loan +
+        in-kind + IE). Rolls up multi-campaign collisions.
+
+        Each row: {stance, total_amount, n_committees, n_transactions,
+                   top5_share, hhi}
+        Empty list if no v3 flows for this measure.
+        """
+        campaign_ids = self._v3_campaign_ids_for_measure(measure_db_id)
+        if not campaign_ids:
+            return []
+        placeholders = ",".join("?" for _ in campaign_ids)
+
+        raw = self.v3_conn.execute(
+            f"""
+            SELECT stance,
+                   SUM(total_amount) AS total_amount,
+                   SUM(n_committees) AS n_committees,
+                   SUM(n_transactions) AS n_transactions
+            FROM finance_summary_total
+            WHERE finance_campaign_id IN ({placeholders})
+            GROUP BY stance
+            """,
+            campaign_ids,
+        ).fetchall()
+
+        # Recompute top5_share + hhi against the merged donor list per
+        # stance — view-level metrics are per-campaign, would be wrong
+        # under rollup.
+        donor_rows = self.v3_conn.execute(
+            f"""
+            SELECT stance, donor_name_canon, SUM(total_amount) AS total_amount
+            FROM finance_top_donors_total
+            WHERE finance_campaign_id IN ({placeholders})
+            GROUP BY stance, donor_name_canon
+            """,
+            campaign_ids,
+        ).fetchall()
+        donors_by_stance: Dict[str, List[Dict]] = defaultdict(list)
+        for r in donor_rows:
+            donors_by_stance[r["stance"]].append({
+                "donor_name_canon": r["donor_name_canon"],
+                "total_amount": float(r["total_amount"] or 0),
+            })
+        for lst in donors_by_stance.values():
+            lst.sort(key=lambda d: (-d["total_amount"], d["donor_name_canon"]))
+
+        out: List[Dict] = []
+        for r in raw:
+            stance = r["stance"]
+            total = float(r["total_amount"] or 0)
+            top5_share, hhi = self._recompute_top5_hhi(
+                total, donors_by_stance.get(stance, [])
+            )
+            out.append({
+                "stance": stance,
+                "total_amount": total,
+                "n_committees": int(r["n_committees"] or 0),
+                "n_transactions": int(r["n_transactions"] or 0),
+                "top5_share": top5_share,
+                "hhi": hhi,
+            })
+        return out
+
+    def get_finance_breakdown_by_type(self, measure_db_id: int) -> List[Dict]:
+        """Per-stance, per-receipt-type breakdown. Rolls up multi-campaign
+        collisions; top5_share + hhi recomputed against merged donors
+        within each (stance, receipt_type) slice.
+
+        Each row: {stance, receipt_type, total_amount, n_committees,
+                   n_transactions, top5_share, hhi}
+        receipt_type ∈ {monetary_contribution, loan, in_kind,
+                        independent_expenditure}
+        """
+        campaign_ids = self._v3_campaign_ids_for_measure(measure_db_id)
+        if not campaign_ids:
+            return []
+        placeholders = ",".join("?" for _ in campaign_ids)
+
+        raw = self.v3_conn.execute(
+            f"""
+            SELECT stance, receipt_type,
+                   SUM(total_amount) AS total_amount,
+                   SUM(n_committees) AS n_committees,
+                   SUM(n_transactions) AS n_transactions
+            FROM finance_summary_by_type
+            WHERE finance_campaign_id IN ({placeholders})
+            GROUP BY stance, receipt_type
+            ORDER BY stance, receipt_type
+            """,
+            campaign_ids,
+        ).fetchall()
+
+        # Per-(stance, receipt_type) merged donor lists for concentration
+        # recomputation. finance_top_donors_by_type already keys on
+        # receipt_type so this is one query.
+        donor_rows = self.v3_conn.execute(
+            f"""
+            SELECT stance, receipt_type, donor_name_canon,
+                   SUM(total_amount) AS total_amount
+            FROM finance_top_donors_by_type
+            WHERE finance_campaign_id IN ({placeholders})
+            GROUP BY stance, receipt_type, donor_name_canon
+            """,
+            campaign_ids,
+        ).fetchall()
+        donors_by_slice: Dict[tuple, List[Dict]] = defaultdict(list)
+        for r in donor_rows:
+            donors_by_slice[(r["stance"], r["receipt_type"])].append({
+                "donor_name_canon": r["donor_name_canon"],
+                "total_amount": float(r["total_amount"] or 0),
+            })
+        for lst in donors_by_slice.values():
+            lst.sort(key=lambda d: (-d["total_amount"], d["donor_name_canon"]))
+
+        out: List[Dict] = []
+        for r in raw:
+            slice_key = (r["stance"], r["receipt_type"])
+            total = float(r["total_amount"] or 0)
+            top5_share, hhi = self._recompute_top5_hhi(
+                total, donors_by_slice.get(slice_key, [])
+            )
+            out.append({
+                "stance": r["stance"],
+                "receipt_type": r["receipt_type"],
+                "total_amount": total,
+                "n_committees": int(r["n_committees"] or 0),
+                "n_transactions": int(r["n_transactions"] or 0),
+                "top5_share": top5_share,
+                "hhi": hhi,
+            })
+        return out
+
+    @staticmethod
+    def _parse_json_array(raw: Optional[str]) -> List[str]:
+        """Parse the json_group_array output from v3 views; tolerant of
+        NULL / malformed entries."""
+        if not raw:
+            return []
+        try:
+            parsed = json.loads(raw)
+        except (ValueError, TypeError):
+            return []
+        return [v for v in parsed if v is not None]
+
+    def get_top_donors_total(
+        self,
+        measure_db_id: int,
+        *,
+        stance: Optional[str] = None,
+        limit: int = 10,
+    ) -> List[Dict]:
+        """Top-N donors per stance across ALL receipt types, rolled up
+        across any year-offset-collision campaigns under one measure.
+        Ranking is partitioned by stance so the smaller side of an
+        imbalanced fight doesn't get crowded out (v2 pattern).
+
+        donor_sector is re-resolved at query time via
+        `donor_sectors.get_donor_sector` so curated updates land in the
+        UI without a v3 rebuild.
+
+        Each row: {stance, donor_name_canon, donor_type, donor_sector,
+                   total_amount, flow_types (list), primary_attribution_source,
+                   n_underlying_rows}
+        """
+        campaign_ids = self._v3_campaign_ids_for_measure(measure_db_id)
+        if not campaign_ids:
+            return []
+        placeholders = ",".join("?" for _ in campaign_ids)
+
+        params: List = list(campaign_ids)
+        stance_clause = ""
+        if stance is not None:
+            stance_clause = "AND stance = ?"
+            params.append(stance)
+
+        # Roll up: SUM total_amount across campaigns, then per-stance
+        # ROW_NUMBER. flow_types unioned across campaigns (parsed JSON
+        # arrays merged). primary_attribution_source picked as the
+        # source with the largest attr_total under the merged donor.
+        cursor = self.v3_conn.execute(
+            f"""
+            WITH per_donor AS (
+                SELECT stance, donor_name_canon,
+                       SUM(total_amount) AS total_amount,
+                       MAX(donor_type)   AS donor_type,
+                       SUM(n_underlying_rows) AS n_underlying_rows,
+                       json_group_array(flow_types) AS flow_types_nested,
+                       json_group_array(primary_attribution_source)
+                           AS attr_sources_nested
+                FROM   finance_top_donors_total
+                WHERE  finance_campaign_id IN ({placeholders}) {stance_clause}
+                GROUP  BY stance, donor_name_canon
+            ),
+            ranked AS (
+                SELECT *,
+                       ROW_NUMBER() OVER (
+                           PARTITION BY stance
+                           ORDER BY total_amount DESC, donor_name_canon
+                       ) AS rn
+                FROM   per_donor
+            )
+            SELECT stance, donor_name_canon, donor_type, total_amount,
+                   n_underlying_rows, flow_types_nested, attr_sources_nested
+            FROM   ranked
+            WHERE  rn <= ?
+            ORDER  BY stance, total_amount DESC, donor_name_canon
+            """,
+            (*params, limit),
+        )
+
+        rows: List[Dict] = []
+        for r in cursor.fetchall():
+            # Merge nested json arrays: per_donor's json_group_array of
+            # json arrays produces e.g. '["[\"loan\",\"in_kind\"]","[...]"]'.
+            # Parse each leg, union into one flat list.
+            flow_types: List[str] = []
+            seen: set = set()
+            for leg in self._parse_json_array(r["flow_types_nested"]):
+                for ft in self._parse_json_array(leg):
+                    if ft not in seen:
+                        flow_types.append(ft)
+                        seen.add(ft)
+            attr_legs: List[str] = []
+            for leg in self._parse_json_array(r["attr_sources_nested"]):
+                if leg and leg not in attr_legs:
+                    attr_legs.append(leg)
+            rows.append({
+                "stance": r["stance"],
+                "donor_name_canon": r["donor_name_canon"],
+                "donor_type": r["donor_type"],
+                "donor_sector": get_donor_sector(r["donor_name_canon"]),
+                "total_amount": float(r["total_amount"] or 0),
+                "flow_types": flow_types,
+                "primary_attribution_source": attr_legs[0] if attr_legs else None,
+                "n_underlying_rows": int(r["n_underlying_rows"] or 0),
+            })
+        return rows
+
+    def get_top_donors_by_type(
+        self,
+        measure_db_id: int,
+        receipt_type: str,
+        *,
+        stance: Optional[str] = None,
+        limit: int = 10,
+    ) -> List[Dict]:
+        """Top-N donors filtered to a single receipt_type, per stance,
+        rolled up across collision campaigns.
+
+        Each row: {stance, receipt_type, donor_name_canon, donor_type,
+                   donor_sector, total_amount, n_underlying_rows,
+                   attribution_source_mode}
+        """
+        campaign_ids = self._v3_campaign_ids_for_measure(measure_db_id)
+        if not campaign_ids:
+            return []
+        placeholders = ",".join("?" for _ in campaign_ids)
+
+        params: List = list(campaign_ids) + [receipt_type]
+        stance_clause = ""
+        if stance is not None:
+            stance_clause = "AND stance = ?"
+            params.append(stance)
+
+        cursor = self.v3_conn.execute(
+            f"""
+            WITH per_donor AS (
+                SELECT stance, receipt_type, donor_name_canon,
+                       SUM(total_amount) AS total_amount,
+                       MAX(donor_type)   AS donor_type,
+                       SUM(n_underlying_rows) AS n_underlying_rows,
+                       MAX(attribution_source_mode) AS attribution_source_mode
+                FROM   finance_top_donors_by_type
+                WHERE  finance_campaign_id IN ({placeholders})
+                  AND  receipt_type = ?
+                  {stance_clause}
+                GROUP  BY stance, receipt_type, donor_name_canon
+            ),
+            ranked AS (
+                SELECT *,
+                       ROW_NUMBER() OVER (
+                           PARTITION BY stance
+                           ORDER BY total_amount DESC, donor_name_canon
+                       ) AS rn
+                FROM   per_donor
+            )
+            SELECT stance, receipt_type, donor_name_canon, donor_type,
+                   total_amount, n_underlying_rows, attribution_source_mode
+            FROM   ranked
+            WHERE  rn <= ?
+            ORDER  BY stance, total_amount DESC, donor_name_canon
+            """,
+            (*params, limit),
+        )
+
+        return [
+            {
+                "stance": r["stance"],
+                "receipt_type": r["receipt_type"],
+                "donor_name_canon": r["donor_name_canon"],
+                "donor_type": r["donor_type"],
+                "donor_sector": get_donor_sector(r["donor_name_canon"]),
+                "total_amount": float(r["total_amount"] or 0),
+                "n_underlying_rows": int(r["n_underlying_rows"] or 0),
+                "attribution_source_mode": r["attribution_source_mode"],
+            }
+            for r in cursor.fetchall()
+        ]


 # ---------------------------------------------------------------------------
diff --git a/scraper/src/finance/schema.py b/scraper/src/finance/schema.py
index a50768d..2fd395d 100644
--- a/scraper/src/finance/schema.py
+++ b/scraper/src/finance/schema.py
@@ -12,6 +12,10 @@ from pathlib import Path

 DATA_DIR = Path(__file__).parent.parent.parent / "data"
 FINANCE_DB_PATH = DATA_DIR / "finance" / "finance_statewide_v2.db"
+# v3 expanded-scope DB (loans + in-kind + IE on top of monetary). Read-only
+# from the application layer until the atomic UI flip in Phase 5. Built by
+# scripts/v3/ingest_* + dedup_ies.py + rebuild_derived.py.
+FINANCE_DB_V3_PATH = DATA_DIR / "finance" / "finance_statewide_v3.db"
 # Old contaminated DB kept as audit artifact; not consumed by any live code.
 FINANCE_DB_LEGACY_PATH = DATA_DIR / "finance" / "finance_statewide.db"
```
