# Codex review round 3: Phase 5 step 1 follow-up

> **For Codex:** Third pass on Phase 5 step 1 of the Cal VGP v3 finance
> expansion. Round-1 (review doc `phase5_step1_review.md` /
> `_deep.md`) flagged 3 issues. Round-2 (`_round2.md`) flagged 3 more.
> This doc shows what was fixed since round-2 and asks you to look at
> the new shape. Live commit: `7a3eb55` on `main` (parent: `d2d2a5f`
> was your round-2 target).

---

## TL;DR of changes since your round-2 review

You flagged in round-2:
1. **n_committees still materially wrong** — empty-string
   short-circuits COALESCE. CAL-ACCESS ships `cover_committee_id = ''`
   on every accepted row, so `COUNT(DISTINCT '')` = 1 universally for
   every IE slice. 278 IE by-type slices wrong, ~$1.886B covered.
   Example: measure 10932 oppose IE reporting 1 vs correct 141.
2. **NULL-donor sort crash** — `lst.sort(key=lambda d: ...,
   d["donor_name_canon"])` raises `TypeError` if a NULL donor and a
   non-NULL donor share an amount. Previous test missed this because
   amounts differed.
3. **Audit artifacts (views + by-type tables) still using broken
   semantics** if they're kept.

What was implemented:
1. ✅ All `COALESCE(committee_id, cover_committee_id, cover_filer_id,
   reported_filer)` → `COALESCE(NULLIF(TRIM(committee_id), ''), ...)`
   wrapped at every column. Applied in 3 places: `operations.py`,
   `scripts/v3/schema.sql`, `scripts/v3/rebuild_derived.py`.
2. ✅ Sort key changed to tuple `(-amount, name is None, name or "")`
   so NULL donors sort last among ties deterministically.
3. ✅ Live db re-applied: dropped + recreated views from the fixed
   `schema.sql`, ran `rebuild_derived.py` to repopulate the by-type
   tables with corrected counts.

## Validation done

- **35 v3 tests pass** (was 30 — added 5 round-2 cases).
- **118 v2 tests still green.** Full finance suite 153/153.
- **Layer 1 8/8 PASS**, all 3 reconciles $0 diff, dedup invariant
  exact, 10/10 trace tests pass.
- **Spot-check confirms fix:** measure 10932 oppose IE 1 → 141;
  PROP_27_2022 oppose IE 1 → 8 (8 distinct tribal/casino filers).
- **Live diagnostic:** confirmed CAL-ACCESS data has 0
  whitespace-only values in any of the 4 committee columns. The
  TRIM is defense-in-depth, not actively firing on real data.

## What's now NEW that wasn't in round-2

The round-2 fixes introduce minor new surfaces. Please scrutinize:

### A. TRIM-spaces-only limitation

SQLite's default `TRIM(X)` strips ASCII space (0x20) only — NOT
tabs, newlines, or carriage returns. The fix handles:
- NULL values → stays NULL
- Empty string `''` → NULL via `NULLIF`
- Space-only `'   '` → NULL via `TRIM` then `NULLIF`

But does NOT handle:
- Tab-only `'\t'` → passes through TRIM, becomes a non-empty
  distinct value
- Newline-only / CR-only → same
- Mixed-whitespace `' \t '` → TRIM strips the leading/trailing spaces
  but leaves the tab in the middle; if the entire value is
  whitespace including non-space chars, it stays non-empty.

**Live diagnostic confirms zero whitespace-only values across all
4 columns today**, so this is defense-in-depth only. Test
`test_space_only_committee_key_does_not_mask_real_filers` documents
the limitation in its docstring with an explicit pointer for the
expansion path (`TRIM(col, char(9)||char(10)||char(13)||' ')`).

**Verify:**
1. Is the documented limitation acceptable, or should we expand to
   the explicit char set now?
2. Are there other dirty-string CAL-ACCESS fields we haven't
   considered (e.g., `donor_name_canon` empty-string blocking
   donor matching upstream)?

### B. Parity between rebuilt artifacts and app read path

The fix was applied identically in:
1. `operations.py` — the app's `get_finance_summary_total` /
   `get_finance_breakdown_by_type` methods (read directly from
   `finance_flow_v3`).
2. `scripts/v3/schema.sql` — the `finance_summary_total` view.
3. `scripts/v3/rebuild_derived.py` — the `finance_summary_by_type`
   table row-pull.

After rebuild, the live db should have **byte-identical n_committees
values** between the app methods, the view, and the by-type table
for every (campaign, stance[, receipt_type]) slice.

**Verify:**
1. Is there a test that asserts this parity invariant — i.e., for
   every (measure_db_id, stance, receipt_type), the value returned
   by `get_finance_breakdown_by_type` equals
   `SELECT n_committees FROM finance_summary_by_type WHERE ...`?
   I don't think there is one. Worth adding?
2. Same parity check for the `finance_summary_total` view vs
   `get_finance_summary_total`. (The view does `MAX(measure_db_id)`
   per campaign so the parity would only hold for measures with
   one campaign — but for that subset it should be exact.)

### C. v2 `aggregate_for_measure` has the same NULL-donor sort pattern

The v2 code at `scraper/src/finance/operations.py` line ~268 (you
can grep `for stance, lst in donors_by_stance.items(): lst.sort(...)`
) has the same vulnerable sort:

```python
for stance, lst in donors_by_stance.items():
    lst.sort(key=lambda d: (-d["total_amount"], d["donor_name_canon"]))
```

This is OUTSIDE the round-2 fix's scope (v2 is untouched in this
phase). v2's `finance_top_donors` table probably enforces non-null
`donor_name_canon` at build time, so the crash path doesn't fire in
practice — but the code is structurally vulnerable to the same bug.

**Verify:**
1. Should the v2 sort be fixed too as a precaution, even though
   v2 data hasn't hit the crash path?
2. Or is the round-2 doc's "out of scope for v3" framing right?

### D. Did the rebuilt by-type table actually re-key correctly?

Before the rebuild, `finance_summary_by_type` had wrong n_committees
for hundreds of slices. After rebuild, the values should now match
both the view (mod the MAX(measure_db_id) quirk) and the app read
path.

I confirmed two slices empirically:
- measure 10932 oppose IE: by-type table = 141 ✓
- PROP_27_2022 / measure 10939 oppose IE: by-type table = 8 ✓

**Verify:**
1. Could there be slices where the rebuild produced an unexpected
   value (e.g., where the by-type Python implementation's
   set-of-committee-keys logic computes differently than the
   in-SQL `COUNT(DISTINCT COALESCE(...))` in operations.py)?
2. The rebuild uses Python `set()` semantics; the app uses SQL
   `COUNT(DISTINCT)`. Both treat NULL as a no-add. Are there subtle
   differences in how they handle whitespace (e.g., does Python's
   set treat `'  Foo'` and `'Foo'` as distinct)?

Looking at the rebuild SQL:
```python
"COALESCE("
"  NULLIF(TRIM(committee_id), ''), "
"  NULLIF(TRIM(cover_committee_id), ''), "
"  NULLIF(TRIM(cover_filer_id), ''), "
"  NULLIF(TRIM(reported_filer), '')"
") AS committee_key"
```

This returns a value (possibly with internal whitespace — `'  Foo'`
isn't stripped to `'Foo'`, only leading/trailing). The Python set
then de-dupes by exact string match. The app's `COUNT(DISTINCT)`
also de-dupes by exact string match. They should agree.

But what about `'Foo'` vs `'foo'` (casing)? Both implementations
preserve casing in the distinct count. If CAL-ACCESS has the same
committee under both casings on different rows, both
implementations would count them as 2 distinct values. That's
existing-behavior, not a new concern, but worth flagging.

### E. SQL-injection / parameterization unchanged

The round-2 changes only added literal SQL constants
(`NULLIF(TRIM(col), '')` with hardcoded `''`). No new user data
enters the SQL string-formatting path. Round-1 verified no injection
path; round-2 doesn't change that.

### F. Performance impact of the added TRIM/NULLIF calls

Each `COALESCE` now wraps 4 columns in `NULLIF(TRIM(col), '')`. For
the app read path, this runs once per row aggregated (47K rows per
call worst case). The TRIM/NULLIF combo is cheap per row, but at
scale it could add measurable overhead.

Codex round-2 measured pre-fix: ~1.5ms summary, ~1.7ms breakdown,
~2.4ms top donors per measure (p50). Post-fix should be similar; my
hermetic tests don't exercise scale.

**Verify:**
1. Is the TRIM-on-every-row penalty measurable in practice?
2. Worth pre-computing a `committee_key_canon` column on the flow
   table at ingest time?

### G. Test coverage

Round-2 added 5 tests:
- empty-string `cover_committee_id` does not mask real filers
- space-only committee key does not mask (documents TRIM limitation)
- committee_id populated still correct (regression guard)
- NULL donor + tied amount does not crash
- attribution_source tie breaks lexicographically (documents
  deterministic-but-arbitrary behavior)

Cumulative v3 tests: 35.

**Verify what might still be missing:**
1. **Parity test** (Section B): app read = by-type table for every
   slice.
2. **Multi-column mixed-whitespace flow**: e.g., `committee_id` is
   `'   '` and `cover_committee_id` is `'real_id'` — the fix
   correctly skips to `cover_committee_id`. (Test only covers
   "all four columns whitespace" case.)
3. **Stress test on the rebuilt artifacts**: assertion that
   `SELECT COUNT(*) FROM finance_summary_by_type WHERE n_committees
   = 1` is plausible (i.e., not still 320+ rows after rebuild).
4. **Negative test on the TRIM limitation**: explicit assertion
   that tab-only does NOT get stripped (documents the limitation
   in code, not just docstring).

## Deliverable

Please flag:

1. Any remaining correctness issue in the COALESCE / TRIM / NULLIF
   pattern.
2. Any parity-invariant test that would catch a future divergence
   between app read path, view, and by-type table.
3. Whether the TRIM limitation (spaces-only) is acceptable or
   should be expanded to the explicit whitespace char set.
4. Whether v2's same-shaped sort is worth fixing in this phase.
5. Any test gap from Section G that's a blocker for the UI step.

After this round, if no blocker, plan is to proceed to Phase 5 step 2
(atomic frontend commit).

---

## The full diff (commit 7a3eb55, production code only)

```diff
diff --git a/scraper/src/finance/operations.py b/scraper/src/finance/operations.py
index 457f0c6..0831a74 100644
--- a/scraper/src/finance/operations.py
+++ b/scraper/src/finance/operations.py
@@ -487,8 +487,10 @@ class FinanceDatabase:
                    SUM(amount) AS total_amount,
                    NULLIF(
                        COUNT(DISTINCT COALESCE(
-                           committee_id, cover_committee_id,
-                           cover_filer_id, reported_filer
+                           NULLIF(TRIM(committee_id), ''),
+                           NULLIF(TRIM(cover_committee_id), ''),
+                           NULLIF(TRIM(cover_filer_id), ''),
+                           NULLIF(TRIM(reported_filer), '')
                        )),
                        0
                    ) AS n_committees,
@@ -520,7 +522,14 @@ class FinanceDatabase:
                 "total_amount": float(r["total_amount"] or 0),
             })
         for lst in donors_by_stance.values():
-            lst.sort(key=lambda d: (-d["total_amount"], d["donor_name_canon"]))
+            # NULL-safe tiebreak: sort None donor names last among ties.
+            # Comparing None directly to str via `d["donor_name_canon"]`
+            # alone would raise TypeError when amounts tie. Codex round-2.
+            lst.sort(key=lambda d: (
+                -d["total_amount"],
+                d["donor_name_canon"] is None,
+                d["donor_name_canon"] or "",
+            ))
 
         out: List[Dict] = []
         for r in raw:
@@ -564,8 +573,10 @@ class FinanceDatabase:
                    SUM(amount) AS total_amount,
                    NULLIF(
                        COUNT(DISTINCT COALESCE(
-                           committee_id, cover_committee_id,
-                           cover_filer_id, reported_filer
+                           NULLIF(TRIM(committee_id), ''),
+                           NULLIF(TRIM(cover_committee_id), ''),
+                           NULLIF(TRIM(cover_filer_id), ''),
+                           NULLIF(TRIM(reported_filer), '')
                        )),
                        0
                    ) AS n_committees,
@@ -599,7 +610,12 @@ class FinanceDatabase:
                 "total_amount": float(r["total_amount"] or 0),
             })
         for lst in donors_by_slice.values():
-            lst.sort(key=lambda d: (-d["total_amount"], d["donor_name_canon"]))
+            # NULL-safe tiebreak — see get_finance_summary_total.
+            lst.sort(key=lambda d: (
+                -d["total_amount"],
+                d["donor_name_canon"] is None,
+                d["donor_name_canon"] or "",
+            ))
 
         out: List[Dict] = []
         for r in raw:
diff --git a/scripts/v3/rebuild_derived.py b/scripts/v3/rebuild_derived.py
index 096bf6a..7b40d35 100644
--- a/scripts/v3/rebuild_derived.py
+++ b/scripts/v3/rebuild_derived.py
@@ -41,11 +41,20 @@ def rebuild_summary_by_type(cur: sqlite3.Cursor, verbose: bool) -> int:
     """
     cur.execute("DELETE FROM finance_summary_by_type")
 
-    # Pull accepted rows
+    # Pull accepted rows.
+    # NULLIF(TRIM(col), '') strips empty / whitespace-only values so
+    # COALESCE doesn't short-circuit on them — CAL-ACCESS ships empty-
+    # string cover_committee_id ubiquitously; without NULLIF, every
+    # accepted row's committee_key collapsed to '' and the per-slice
+    # COUNT(DISTINCT) returned 1 universally (Codex round-2 finding).
     rows = cur.execute(
         "SELECT finance_campaign_id, measure_db_id, stance, receipt_type, "
-        "       COALESCE(committee_id, cover_committee_id, "
-        "                cover_filer_id, reported_filer) AS committee_key, "
+        "       COALESCE("
+        "           NULLIF(TRIM(committee_id), ''), "
+        "           NULLIF(TRIM(cover_committee_id), ''), "
+        "           NULLIF(TRIM(cover_filer_id), ''), "
+        "           NULLIF(TRIM(reported_filer), '')"
+        "       ) AS committee_key, "
         "       donor_name_canon, amount "
         "FROM finance_flow_v3 "
         "WHERE quarantine_reason IS NULL"
diff --git a/scripts/v3/schema.sql b/scripts/v3/schema.sql
index 90fca26..58ddf6c 100644
--- a/scripts/v3/schema.sql
+++ b/scripts/v3/schema.sql
@@ -286,14 +286,23 @@ flow_agg AS (
     -- n_committees: COALESCE so IE rows that have no row-level
     -- committee_id but do have a cover_committee_id / reported_filer
     -- contribute to the committee count rather than getting silently
-    -- treated as one "NULL committee"
+    -- treated as one "NULL committee".
+    --
+    -- NULLIF(TRIM(col), '') strips empty / whitespace-only values so
+    -- COALESCE doesn't short-circuit on them — CAL-ACCESS ships empty-
+    -- string cover_committee_id ubiquitously (every accepted row has
+    -- cover_committee_id = ''), so without NULLIF the COUNT(DISTINCT)
+    -- universally returned 1 (the empty string) and never reached the
+    -- real cover_filer_id / reported_filer values. Codex round-2.
     SELECT finance_campaign_id,
            MAX(measure_db_id)           AS measure_db_id,
            stance,
            SUM(amount)                  AS total_amount,
            COUNT(DISTINCT COALESCE(
-               committee_id, cover_committee_id,
-               cover_filer_id, reported_filer
+               NULLIF(TRIM(committee_id), ''),
+               NULLIF(TRIM(cover_committee_id), ''),
+               NULLIF(TRIM(cover_filer_id), ''),
+               NULLIF(TRIM(reported_filer), '')
            ))                           AS n_committees,
            COUNT(*)                     AS n_transactions
     FROM   finance_flow_v3
```
