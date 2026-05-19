# Codex review request: Phase 5 step 1 (v3 read methods) — extended

> **For Codex:** Self-contained extended review. This file is longer than
> `phase5_step1_review.md` because it gives you full project context so
> you can be opinionated about correctness, ergonomics, and risk without
> needing follow-up questions. Live commit on the user's `main`: `4542d4a`.

---

## Table of contents

1. Project context
2. The v3 finance expansion — why it exists
3. Where Phase 5 step 1 sits in the build arc
4. The rounds 10–14 bug-fix arc (vigilance calibration)
5. v3 db schema cheatsheet
6. v2 patterns that v3 must coexist with
7. The diff and what it changes
8. Design decisions already confirmed
9. Specific things to scrutinize
10. Test coverage and gaps
11. Verification framework and how this layer interacts with it
12. Deliverable: what we want back from this review

---

## 1. Project context

**CalBallot / Cal VGP** is a public, free-to-use static site that
exposes California ballot-measure data (Props 1A through current
cycle) plus campaign-finance context. Built by Igor as
research/educational tooling.

Architecture:
- **Source:** California Secretary of State CAL-ACCESS bulk dumps
  (~600K filings, ~10M transactions) + Ballotpedia + ICPSR + CEDA.
- **Pipeline:** Python ingest → SQLite databases → static site
  generator → GitHub Pages.
- **Output:** `index.html` (the static site, served free), JSON
  payloads for AJAX consumers, a small REST API for briefing
  generation.
- **Money in scope:** ~$5–6 billion of California ballot-measure
  campaign finance over ~25 years.

**Public-facing dollar amounts matter.** Headline numbers (per-measure
totals, top-donor lists, sector breakdowns) are what users see and
take away. Wrong attribution or wrong rollup arithmetic produces
incorrect public claims — Igor treats this as the highest correctness
risk on the project.

**Codebase scale:** ~30K lines of Python + ~5K lines of JS. Finance
subsystem ~6K lines split across `scraper/src/finance/`,
`scraper/scripts/`, and `scripts/v3/`. ~250 tests in the scraper
suite, ~120 of those finance-specific.

## 2. The v3 finance expansion — why it exists

**v2 (current production, shipped 2026-05-04):** ingests only Form 460
Schedule A monetary contributions (committee-receives-cash transactions).
Total in-scope retained: ~$3.24B across 181 statewide proposition
campaigns. Built on top of a year-scoped `finance_campaign_id` (e.g.
`PROP_16_2020`) primary key — fixed v1's cross-cycle contamination
where bare `PROP_xx` keys conflated 2020 PROP_16 with 2010 PROP_16
finance.

**The v2 gap:** v2 misses three categories of money that voters and
researchers consider equally part of "campaign spending":
- **Loans** (LOAN_CD, Form 460 B1): non-cash committee receipts that
  later flip to cash flows.
- **In-kind contributions** (RCPT_CD Schedule C): services/goods
  donated to a committee.
- **Independent Expenditures** (EXPN_CD F461P5/F465P3, S496_CD): money
  spent directly by donors on advocacy (ads, mailers) WITHOUT going
  through the committee — major-donor spending on PROP_22_2020 was
  almost all IE.

For prop fights with heavy IE activity (PROP_22_2020 gig-worker law,
PROP_27_2022 sports betting), v2's monetary-only totals run 30–60%
of what Ballotpedia reports as the total. Closing this gap is the
v3 expansion's purpose.

**v3 result (already shipped through Phase 4):** unified `finance_flow_v3`
fact table carrying all 4 receipt types, with conservative attribution
and rigorous quarantine for ambiguous rows. v3 totals: 47,942
accepted rows / $2.51B (loan + in-kind + IE only — adds to v2's
$3.24B for ~$5.75B combined under a careful methodology note).

## 3. Where Phase 5 step 1 sits in the build arc

Phase plan, as executed:

- **Phase 0:** scope + design (decided on `finance_flow_v3` shape,
  conservative attribution, post-ingest dedup).
- **Phase 1:** Loans ingest (LOAN_CD B1) — shipped.
- **Phase 2:** Schedule C in-kind ingest (RCPT_CD C) — shipped.
- **Phase 3:** in-kind reconciliation + first end-to-end Layer 2 check.
- **Phase 4:** IE ingest (EXPN_CD F461P5/F465P3 + S496_CD) — the big
  one. Independent expenditures are the hardest receipt type because
  IE rows don't have a "receiving committee" — they're filed by the
  donor, paying a vendor (ad agency, mailing house), explicitly
  declaring which prop and which stance. Attribution comes from:
    (a) row-level fields (BAL_NUM, BAL_NAME, SUP_OPP_CD), or
    (b) cover-sheet fields (filing-level metadata), or
    (c) curated overrides for known committees.
  Plus a cross-source dedup pass: same economic transaction can
  appear in S496_CD AND EXPN_CD (24-hour notice + scheduled report);
  we keep one and quarantine the duplicate.
- **Phase 5 (CURRENT):**
  - **Step 1 (THIS REVIEW):** library/API migration. Add 4 read
    methods to `FinanceDatabase` so consumers have a v3-aware way to
    query the db. UI continues reading v2 until step 2.
  - **Step 2 (NEXT):** atomic frontend commit. ALL UI surfaces flip
    to v3 in one commit because half-flipped UIs (e.g. hero card on
    v3 totals but modal on v2) would show inconsistent headline
    numbers. Touches: measure modal Finance tab, hero card, Insights
    Module 1 (total), Module 3 (top donors), Module 4 (marquee
    fights), API endpoint, briefing pipeline, methodology copy.
- **Phase 6:** final verification + CHANGELOG + docs.

**The reason step 1 is a separate commit from step 2:** step 1 is
pure code addition (no behavior change for any existing consumer);
step 2 changes user-visible numbers. Splitting lets us review the
new SQL/rollup logic *before* it's wired into the UI, so any
correctness bug surfaces in tests/review rather than as a visible
production regression. This review is exactly that gate.

## 4. The rounds 10–14 bug-fix arc (vigilance calibration)

Phase 4 was originally "shipped" at commit `fe0da9f` after rounds 1–9
of Codex reviews. Then rounds 10–14 caught **5 successive correctness
bugs** the earlier rounds missed:

| Round | Bug | $ misattributed |
|-------|-----|-----------------|
| 10 | Trace tests gap (no source-row-anchored coverage of IE attribution) | (process) |
| 11 | AG queue IDs like `19-0026` greedy-matched as "19" → PROP_19_2020 | $117.5M |
| 12 | Multi-prop separators (`26/27`, `RM/4`, `11/2020`) misattributed | $388.3M |
| 13 | Regional measures (`Regional Measure 3`) misattributed to statewide props | $680K |
| 13 (reverse) | BAL_NAME false-positives quarantining valid rows | +$232M recovered |
| 14 | Bare local letter measures (`Measure A`, `Measure C`) misattributed | $27K |

The pattern: **upstream resolver logic kept finding edge cases in real
CAL-ACCESS data that the test fixtures didn't anticipate.** Igor and
Codex have iterated to where the resolver is now well-fortified, but
the lesson stands: the data is messier than synthetic tests predict.

**Implication for this review:** Phase 5 step 1 is *downstream* of
resolver/attribution — it's post-attribution rollup. So the bug
families to look for are different:
- **Arithmetic correctness** in rollup SUMs.
- **Boundary conditions** (empty sets, single-element sets, all-null
  fields).
- **SQL semantics** (NULL handling in window functions, GROUP BY
  aggregates over LEFT JOINs, json_group_array of NULLs).
- **Migration risk** — anything in the new methods' return shape that
  the UI couldn't render correctly.

Igor's preference is to err **conservative**: it's better to return
NULL or empty than to return a number that's wrong by 0.001%.

## 5. v3 db schema cheatsheet

### Fact table

```sql
CREATE TABLE finance_flow_v3 (
    flow_id              INTEGER PRIMARY KEY,
    finance_campaign_id  TEXT,                 -- canonical (post-collapse)
    source_crosswalk_campaign_id TEXT,         -- pre-collapse provenance
    measure_db_id        INTEGER,              -- FK to measures.id (UI key)
    stance               TEXT,                 -- 'support' | 'oppose'
    receipt_type         TEXT,                 -- 'monetary_contribution' |
                                               -- 'loan' | 'in_kind' |
                                               -- 'independent_expenditure'
    amount               REAL,
    txn_date             TEXT,                 -- ISO YYYY-MM-DD
    week_start           TEXT,                 -- Monday ISO YYYY-MM-DD
    source_table         TEXT NOT NULL,        -- 'RCPT_CD' | 'LOAN_CD' |
                                               -- 'EXPN_CD' | 'S496_CD'
    source_form_type     TEXT NOT NULL,        -- 'A' | 'C' | 'B1' |
                                               -- 'F461P5' | 'F465P3' | 'F496'
    filing_id            TEXT NOT NULL,
    amend_id             INTEGER NOT NULL,
    -- source-row anchoring fields (for trace tests):
    source_line_item     TEXT,
    source_tran_id       TEXT,
    -- the rest: cover-sheet fields, donor/committee/payee names,
    -- attribution metadata, source/economic fingerprints, dedup fields:
    committee_id         TEXT,
    cover_committee_id   TEXT,
    cover_filer_id       TEXT,
    reported_filer       TEXT,
    donor_name_canon     TEXT,
    donor_type           TEXT,
    donor_sector         TEXT,
    attribution_source   TEXT,                 -- 'funding_source' | 'filer'
    attribution_method   TEXT,                 -- 'row_fields' | 'cover_sheet'
                                               -- | 'filer_name_explicit' | etc.
    quarantine_reason    TEXT                  -- NULL = accepted
)
```

912,629 total rows; 47,942 accepted (`quarantine_reason IS NULL`);
~864K quarantined or dedup-loser. Aggregation queries filter
`WHERE quarantine_reason IS NULL`.

### Derived tables (built by `scripts/v3/rebuild_derived.py`)

```sql
CREATE TABLE finance_summary_by_type (
    finance_campaign_id, measure_db_id, stance, receipt_type,
    total_amount, n_committees, n_transactions, top5_share, hhi,
    PRIMARY KEY (finance_campaign_id, stance, receipt_type)
)
CREATE TABLE finance_top_donors_by_type (
    finance_campaign_id, measure_db_id, stance, receipt_type,
    donor_name_canon, donor_type, donor_sector,
    total_amount, n_underlying_rows, attribution_source_mode,
    PRIMARY KEY (finance_campaign_id, stance, receipt_type, donor_name_canon)
)
CREATE TABLE finance_timeline_weekly_by_type (
    finance_campaign_id, measure_db_id, stance, receipt_type,
    week_start, weekly_amount, cumulative_amount,
    PRIMARY KEY (finance_campaign_id, stance, receipt_type, week_start)
)
```

Counts: 652 / 8,511 / 7,488 rows respectively. These collapse the
flow table to per-(campaign, stance, receipt_type) summaries.

### Derived views (totals — collapse the receipt_type dimension)

These are SQL **VIEWS** (computed at query time from the flow table,
not stored). The key one for review purposes:

```sql
CREATE VIEW finance_summary_total AS
WITH per_donor AS (
    SELECT finance_campaign_id, stance, donor_name_canon,
           SUM(amount) AS donor_total
    FROM   finance_flow_v3
    WHERE  quarantine_reason IS NULL
    GROUP  BY finance_campaign_id, stance, donor_name_canon
),
campaign_totals AS (
    SELECT finance_campaign_id, stance,
           SUM(donor_total) AS grand_total
    FROM   per_donor
    GROUP  BY finance_campaign_id, stance
),
ranked AS (
    SELECT finance_campaign_id, stance, donor_total,
           ROW_NUMBER() OVER (
               PARTITION BY finance_campaign_id, stance
               ORDER BY donor_total DESC
           ) AS rk
    FROM per_donor
),
top5 AS (
    SELECT finance_campaign_id, stance, SUM(donor_total) AS top5_sum
    FROM ranked WHERE rk <= 5
    GROUP BY finance_campaign_id, stance
),
hhi_calc AS (
    SELECT pd.finance_campaign_id, pd.stance,
           SUM(
               (100.0 * pd.donor_total / NULLIF(ct.grand_total, 0)) *
               (100.0 * pd.donor_total / NULLIF(ct.grand_total, 0))
           ) AS hhi
    FROM per_donor pd
    JOIN campaign_totals ct USING (finance_campaign_id, stance)
    GROUP BY pd.finance_campaign_id, pd.stance
),
flow_agg AS (
    SELECT finance_campaign_id,
           MAX(measure_db_id)           AS measure_db_id,
           stance,
           SUM(amount)                  AS total_amount,
           COUNT(DISTINCT COALESCE(
               committee_id, cover_committee_id,
               cover_filer_id, reported_filer
           ))                           AS n_committees,
           COUNT(*)                     AS n_transactions
    FROM   finance_flow_v3
    WHERE  quarantine_reason IS NULL
    GROUP  BY finance_campaign_id, stance
)
SELECT
    fa.finance_campaign_id, fa.measure_db_id, fa.stance,
    fa.total_amount, fa.n_committees, fa.n_transactions,
    CASE WHEN ct.grand_total > 0
         THEN 100.0 * t5.top5_sum / ct.grand_total ELSE NULL
    END AS top5_share,
    h.hhi AS hhi
FROM flow_agg fa
LEFT JOIN campaign_totals ct USING (finance_campaign_id, stance)
LEFT JOIN top5 t5 USING (finance_campaign_id, stance)
LEFT JOIN hhi_calc h USING (finance_campaign_id, stance);
```

```sql
CREATE VIEW finance_top_donors_total AS
WITH flow_accepted AS (
    SELECT finance_campaign_id, measure_db_id, stance,
           donor_name_canon, receipt_type, attribution_source,
           donor_type, donor_sector, amount
    FROM   finance_flow_v3 WHERE quarantine_reason IS NULL
),
per_donor AS (
    SELECT finance_campaign_id,
           MAX(measure_db_id)                        AS measure_db_id,
           stance, donor_name_canon,
           SUM(amount)                               AS total_amount,
           MAX(donor_type)                           AS donor_type,
           MAX(donor_sector)                         AS donor_sector,
           json_group_array(DISTINCT receipt_type)   AS flow_types,
           json_group_array(DISTINCT attribution_source) AS attribution_sources,
           COUNT(*)                                  AS n_underlying_rows
    FROM   flow_accepted
    GROUP  BY finance_campaign_id, stance, donor_name_canon
),
per_donor_attribution AS (
    SELECT finance_campaign_id, stance, donor_name_canon,
           attribution_source, SUM(amount) AS attr_total
    FROM   flow_accepted
    GROUP  BY finance_campaign_id, stance, donor_name_canon, attribution_source
),
ranked_attribution AS (
    SELECT finance_campaign_id, stance, donor_name_canon,
           attribution_source,
           ROW_NUMBER() OVER (
               PARTITION BY finance_campaign_id, stance, donor_name_canon
               ORDER BY attr_total DESC
           ) AS rk
    FROM per_donor_attribution
)
SELECT pd.finance_campaign_id, pd.measure_db_id, pd.stance,
       pd.donor_name_canon, pd.total_amount, pd.donor_type, pd.donor_sector,
       pd.flow_types, pd.attribution_sources,
       ra.attribution_source AS primary_attribution_source,
       pd.n_underlying_rows
FROM per_donor pd
LEFT JOIN ranked_attribution ra
       ON ra.finance_campaign_id = pd.finance_campaign_id
      AND ra.stance               = pd.stance
      AND ra.donor_name_canon     = pd.donor_name_canon
      AND ra.rk                   = 1;
```

A `finance_timeline_weekly_total` view also exists but isn't used by
the methods under review.

### "Year-offset collisions" — what they mean

In CAL-ACCESS, reporting-year and election-year can diverge by 1–3
years (e.g. 2008's Prop 4 had committees filing under reporting-year
2010 for late activity). The v2 crosswalk recovers this via a
lookback gate — when it works, BOTH `finance_campaign_id`s
(`PROP_4_2008` and `PROP_4_2010`) link to the same `measure_db_id`
(e.g. 1189). Querying by measure_db_id needs to roll up both.

This is the **rollup arithmetic surface** that this review is most
concerned with.

## 6. v2 patterns that v3 must coexist with

v2 lives in `scraper/src/finance/operations.py`'s `FinanceDatabase`
class (same class as v3 methods). Key patterns that v3 follows:

- **Per-stance ROW_NUMBER for top donors:** `get_top_donors` (v2)
  uses `ROW_NUMBER() OVER (PARTITION BY stance ORDER BY total_amount
  DESC)` so the smaller side of an imbalanced fight isn't crowded
  out (e.g. PROP_1_2024's oppose was originally 30:1 outspent — flat
  ORDER BY hid them entirely).
- **Sector re-resolution at query time:** v2's `get_top_donors`
  calls `get_donor_sector(donor_name_canon)` for each row rather
  than reading a stored column. Lets curated additions to
  `donor_sectors.py` land in the UI without a rebuild.
- **`aggregate_for_measure` rollup pattern:** v2 has this for the
  collision case. It sums receipts across colliding campaigns and
  recomputes top5/HHI against the merged donor list. v3 methods
  follow the same pattern.

The v3 methods reuse `get_donor_sector` from `donor_sectors.py` — the
sector taxonomy is unchanged between v2 and v3.

## 7. The diff and what it changes

See `phase5_step1_review.md` in this directory for the full inline
diff. Summary:

- **`scraper/src/finance/schema.py`** (+4 lines): adds
  `FINANCE_DB_V3_PATH` constant.
- **`scraper/src/finance/operations.py`** (+355 lines): adds
  - lazy `v3_conn` property on `FinanceDatabase`
  - 2 private helpers (`_v3_campaign_ids_for_measure`,
    `_recompute_top5_hhi`, `_parse_json_array`)
  - 4 new public read methods (`get_finance_summary_total`,
    `get_finance_breakdown_by_type`, `get_top_donors_total`,
    `get_top_donors_by_type`)
  - `close()` updated to close v3 conn if opened

No existing methods are modified. All v3 additions go after the
existing `close()` method.

## 8. Design decisions already confirmed

These were explicitly chosen with Igor before implementation:

1. **Same `FinanceDatabase` class, second connection** (not a separate
   `FinanceV3Database` class). Reason: gives consumers a single query
   layer to migrate from, with v2 methods kept stable so the migration
   is incremental.

2. **`measure_db_id` keying, not `finance_campaign_id`.** Reason: UI
   already has a measure handle, and `measure_db_id` correctly
   subsumes the collision case. Tradeoff: methods must roll up
   campaign-keyed view rows internally — the rollup logic is the
   bug surface.

3. **Built-in rollup with recomputed top5/hhi.** Reason: the view-level
   top5/hhi values are per-campaign; under rollup they're wrong.
   Recomputing in Python against the merged donor list is the right
   semantics. (Alternative was "thin wrapper returning raw view rows"
   — rejected because it pushes correctness logic into the UI.)

4. **`donor_sector` re-resolved at query time.** Reason: curated
   sector additions to `donor_sectors.py` should land in UI
   immediately without a v3 rebuild. The stored `donor_sector` column
   on the flow table is intentionally NOT used in the read path
   (it's an audit artifact).

5. **`v3_conn` is lazy.** Only opened on first v3 method call. v2-only
   consumers (and fresh checkouts without a v3 db) aren't broken.

## 9. Specific things to scrutinize

### A. Rollup arithmetic correctness

In `get_finance_summary_total`:
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

The `finance_top_donors_total` view computes `total_amount` per
(campaign, stance, donor) as `SUM(amount) FROM finance_flow_v3 WHERE
quarantine_reason IS NULL`. Summing that across collision campaigns
*should* equal `SUM(amount) FROM finance_flow_v3 GROUP BY
(measure, stance, donor)` directly.

**Verify:**
1. Can the view ever return a per-(campaign, stance, donor) total
   that differs from the equivalent direct SUM on the flow table?
2. Is there a NULL handling case (e.g. donor_name_canon IS NULL)
   where the view drops rows but the flow table wouldn't?
3. The flow_agg CTE in the view does `MAX(measure_db_id)` — could
   a measure_db_id ever be NULL on accepted rows? (per acceptance
   gate it shouldn't be, but worth confirming.)

### B. SQL injection / parameterization

All 4 methods build `IN ({placeholders})` clauses where `placeholders`
is `",".join("?" for _ in campaign_ids)`. The `campaign_ids` come from
`_v3_campaign_ids_for_measure`, which queries with a single `?`
parameter (`measure_db_id`) and returns `r[0]` strings.

The `?`-style binding is parameterized properly. The string-formatted
`{placeholders}` is just `?,?,?` literal — no user data interpolated.

`receipt_type` in `get_top_donors_by_type` is passed as a `?` parameter
too. `stance` likewise when filtered.

**Verify:** is there any path where untrusted input reaches an
f-string interpolation? (Igor doesn't think so but a fresh look helps.)

### C. flow_types union logic in `get_top_donors_total`

The trickiest part. The view's `flow_types` column is already a
JSON array string (from `json_group_array(DISTINCT receipt_type)`).
The Python-side rollup does `json_group_array(flow_types)` which
produces a JSON array OF JSON array STRINGS (SQLite's
`json_group_array` doesn't recurse into JSON values — it treats them
as opaque strings).

So `flow_types_nested` looks like:
```
'["[\"loan\",\"in_kind\"]","[\"independent_expenditure\"]"]'
```

The Python code unpacks with two `_parse_json_array` calls:
```python
for leg in self._parse_json_array(r["flow_types_nested"]):  # outer
    for ft in self._parse_json_array(leg):                  # inner
        if ft not in seen:
            flow_types.append(ft)
            seen.add(ft)
```

**Verify:**
1. Is the nested-JSON assumption correct, or does
   `json_group_array` of a JSON column actually treat the inner
   value as parsed JSON (no double-encoding)?
2. What happens for a single-campaign measure where `flow_types`
   already contains the full list — does the rollup return the same
   list, or unwrap to a list of strings somehow?
3. Edge case: a donor with `receipt_type = NULL` somehow making it
   to the view (shouldn't happen given acceptance gates, but...).

The 18 hermetic tests have one test for this case
(`test_unions_flow_types_across_campaigns`) — but only at the
2-campaign rollup level. The single-campaign case isn't explicitly
tested.

### D. `primary_attribution_source` rollup choice

```python
attr_legs: List[str] = []
for leg in self._parse_json_array(r["attr_sources_nested"]):
    if leg and leg not in attr_legs:
        attr_legs.append(leg)
# ...
"primary_attribution_source": attr_legs[0] if attr_legs else None,
```

This takes the **first** non-null primary_attribution_source from
the merged campaigns, NOT the one with the largest `attr_total`.

Argument for current: typically one source dominates a donor's
attribution; picking any non-null is fine for display purposes.

Argument against: a donor with attribution split 51/49 across two
sources across two collision campaigns would get one or the other
with no transparency about the split.

**Verify:** does this feel principled, or should the rollup
re-rank by SUM(attr_total) like the per-campaign view does
internally?

### E. `n_committees` rollup correctness

```python
SUM(n_committees) AS n_committees
```

Per-campaign `n_committees` is `COUNT(DISTINCT COALESCE(committee_id,
cover_committee_id, cover_filer_id, reported_filer))`. Summing
across campaigns DOUBLE-COUNTS committees that file across both
collision campaigns (e.g. the same Planned Parenthood committee
filing under PROP_4_2008 and PROP_4_2010).

v2's `aggregate_for_measure` has the same caveat (documented as
"best-effort; may double-count"). Whether to fix here:
- **Fix:** query the flow table directly with `COUNT(DISTINCT ...
  WHERE finance_campaign_id IN (...))`. One extra query per stance.
- **Don't fix:** match v2 semantics for consistency, accept the
  rare double-count.

**Verify:** is the double-count materially misleading anywhere, or is
"best-effort" the right tradeoff?

### F. `n_committees = 0` surprise for non-monetary types

Smoke-tested against the real v3 db: `n_committees` for IE rows
comes back as 0, because IE rows don't carry a `committee_id` in the
"receiving committee" sense — they're spent direct to vendors. The
COALESCE chain in the view doesn't help because IE flows have NULL
across all four fields.

This is **data**, not bug. But it's a UI rendering question: should
the modal show "0 committees" for the IE row, or hide that metric
for non-monetary types?

**Verify:** is there a third option (e.g. report `n_payees` for IE
rows, since IE has `payee_name` instead)? Or just hide the column
for IE?

### G. Stance filter ergonomics

```python
def get_top_donors_total(
    self, measure_db_id, *, stance=None, limit=10,
) -> List[Dict]:
```

When `stance=None`, both stances come back ranked per-stance. When
a string, filtered to that stance.

Keyword-only argument feels right for now (avoids `f(100, None, 10)`
positional confusion). v2's `get_top_donors` doesn't support
filtering by stance.

**Verify:** is this the right ergonomic, or should we be stricter
(require explicit stance)? Should the v2 method grow a matching
filter?

### H. Test coverage gaps

The 18 hermetic tests in `tests/test_finance_db_v3.py` cover:
- Single-campaign baseline
- Collision rollup (2 campaigns sharing measure_db_id)
- `no flows → empty list` boundary
- Quarantine filtering
- Per-stance ranking with imbalanced sides
- Stance filter narrows correctly
- Receipt-type filter narrows correctly
- flow_types union across types (single-donor crossing 3 types)
- donor_sector re-resolved (stale stored value overridden)

**Verify what's missing:**
1. **3+-campaign collision case** (only tested 2-campaign).
2. **Single-campaign returning `flow_types`** as a single-element
   list (not a nested-unwrap case).
3. **Limit boundary** (limit=1, limit larger than donor count).
4. **stance + receipt_type combined filter** in
   `get_top_donors_by_type`.
5. **NULL donor_name_canon row** behavior.
6. **All-quarantined measure** (some flows exist but every one is
   quarantined).
7. **Numerical edge cases:** total_amount = 0 with non-zero rows,
   negative amounts (refunds — does v3 have any?).
8. **Concurrent v2 + v3 access** in one `FinanceDatabase` instance.

## 10. Verification framework and how this layer interacts with it

The v3 build is gated by a multi-layer verification framework:

- **Layer 0 — Unit tests:** ~120 finance-suite tests (107+ resolver,
  18 v3 method tests). Hermetic. Fast.
- **Layer 1 — v2 no-regression:** `scripts/v3/verify_layer1.py` runs
  8 checks confirming v2 baseline tables/values haven't changed (v3
  must not touch v2 data). Includes a self-hash check on the v2 db
  file. All 8 PASS at the current state.
- **Layer 2 — Source reconciliation:** for each ingest scope (loans,
  in-kind, IE), a script (`reconcile_loans.py` etc.) re-extracts the
  source CAL-ACCESS data using the SAME attribution code path and
  compares to the v3 db. Must be $0 diff to the penny per
  (campaign, stance) key. All currently $0.
- **Layer 3 — Trace tests:** 10 source-row-anchored fixtures in
  `data/CalAccess/ie_trace_tests.json`. Each pins a specific
  (source_table, source_form_type, filing_id, source_line_item,
  source_tran_id) row to its expected attribution outcome. Catches
  attribution-LOGIC bugs that shared-code reconciles can't.

**This review layer's relationship to the framework:** the new methods
read derived tables/views. Layer 2 reconciles against the flow table
SUMs, which is upstream of these methods. Layer 3 traces are anchored
to flow rows, also upstream. So **Layer 0 (unit tests) is the
verification primary for this layer**.

If a bug exists in the rollup arithmetic, none of Layers 1-3 will
catch it. That's why Layer 0 coverage matters here, and why the
review focuses on what's missing.

## 11. Risks if a bug ships

If a correctness bug slips through review and into the UI step (step
2), the symptoms would be:

- **Headline number wrong on a measure modal.** E.g. PROP_4_2008
  shows $1.2M oppose when the real merged total is $1.0M.
- **Top donor list wrong.** E.g. Planned Parenthood appears twice
  (once per collision campaign) instead of merged once.
- **HHI / top5_share misleading.** E.g. HHI computed against
  unmerged donor list shows concentration higher than reality.
- **Sector chip missing on a known donor.** If sector lookup is
  bypassed somehow.

All these are user-visible and would require a follow-up commit to
fix, plus a public note. Cost of one bug in production: ~1 day
investigation + fix + verify + redeploy.

## 12. Deliverable

Please flag:

1. **Correctness:** any path where the rollup arithmetic returns
   wrong values.
2. **SQL:** any case where the query semantics differ from intent
   (NULL handling, GROUP BY over LEFT JOIN, json_group_array of
   nested values).
3. **Tests:** specific scenarios from section H (or new ones) that
   should be added before this code ships behind UI.
4. **Ergonomics:** any API surface concern that would cost rework
   at the UI-flip step (parameter naming, return shape, etc.).
5. **Migration risk:** anything in the new methods' interaction with
   the existing v2 `FinanceDatabase` that could create a
   v2-vs-v3-confusion bug for consumers during the migration period.

**Calibration:** Igor's standard is conservative — prefer false
negatives (None / empty) over false positives (wrong numbers).
Flag anything that even MIGHT be wrong; we'll dig in with you.

The full diff is in `phase5_step1_review.md` (sibling file in this
directory).

---

## Reference: file layout for orientation

```
scraper/
  src/finance/
    schema.py           # +4 lines: FINANCE_DB_V3_PATH
    operations.py       # +355 lines: v3 methods (this review)
    donor_sectors.py    # unchanged — get_donor_sector() called by v3
  tests/
    test_finance_db_v3.py   # 18 new hermetic tests (not in diff)
    test_finance_db.py      # 105 existing v2 tests (untouched, still green)
  scripts/
    rebuild_finance_db.py   # v2 build (untouched)
    extract_calaccess_finance.py  # v1/v2 (untouched)

scripts/v3/                 # all of Phase 4 build pipeline (untouched)
  resolver.py               # attribution logic + rounds 10-14 fixes
  ingest_ies.py             # IE ingest
  ingest_loans.py           # Loans ingest
  ingest_inkind.py          # In-kind ingest
  dedup_ies.py              # post-ingest dedup
  rebuild_derived.py        # derived tables build
  reconcile_*.py            # Layer 2 reconciliation
  verify_*.py               # Layer 1/3 verification
  test_resolver.py          # 107+ unit tests for resolver

data/
  CalAccess/                # raw bulk source data
    ie_trace_tests.json     # 10 trace fixtures
scraper/data/finance/
  finance_statewide_v2.db   # v2 production db
  finance_statewide_v3.db   # v3 (this review's target)

docs/codex/
  phase5_step1_review.md       # SHORT review file (with full diff)
  phase5_step1_review_deep.md  # THIS FILE (extended context)
```
