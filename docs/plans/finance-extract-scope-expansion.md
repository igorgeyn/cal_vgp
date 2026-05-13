---
plan: Finance extract scope expansion (close the Ballotpedia gap)
status: DRAFT 2026-05-13 — Codex round-1 + round-2 + round-3 integrated; Phase 0 done; Phase 1 DDL gated on user go-ahead
target: v3 total-support-side-money reconciles to source-table filtered SUM; Ballotpedia within ±25% is a smoke test
---

# Finance extract scope expansion

End-to-end plan to extend the CAL-ACCESS extract pipeline beyond Form 460
Schedule A monetary contributions, so our v2 totals stop running 40–60%
below headline public-reporting figures (Ballotpedia, OpenSecrets,
CalMatters) for high-IE-spending ballot propositions.

## Why

Today's v2 captures only **monetary contributions to recipient committees**
(Form 460 Schedule A → CAL-ACCESS `RCPT_CD`). For high-IE props the gap
is large:

| Prop | v2 total | Public total | Gap |
|---|---|---|---|
| PROP_22_2020 (gig workers) | $97M | $224M+ | −$127M (~57%) |
| PROP_27_2022 (sports betting) | $146M | $418M | −$273M (~65%) |
| PROP_8_2018 (dialysis) | $110M | $130M | −$20M (~15%) |

Most of the missing money is **Independent Expenditure** spending —
when a major donor (e.g. FanDuel) pays an ad agency directly to run "Yes
on 27" advertising, bypassing the official Yes-on-27 PAC. Plus some
in-kind, some loans, some untagged side-committees.

## Phase 0 — Source data acquisition (gating prerequisite)

Our local `data/CalAccess/DATA/` dump is incomplete for this work:

**Present:** `RCPT_CD`, `SMRY_CD`, `CVR_CAMPAIGN_DISCLOSURE_CD`,
`FILER_FILINGS_CD`, `FILER_TO_FILER_TYPE_CD`, `FILERNAME_CD`, `FILERS_CD`,
`BALLOT_MEASURES_CD`

**Missing (we need these):**

- `LOAN_CD` — loans received (Schedule B)
- `EXPN_CD` — expenditures (Schedule E + general committee spending)
- `S496_CD` — 24-hour Independent Expenditure late filings
- `S497_CD` — 24-hour late contributions / expenditures
- `S401_CD` — slate mailer contributions (may matter for some props)
- `DEBT_CD` — accrued expenses (probably out of scope; spending not money in)

**Action:** download fresh CAL-ACCESS dump from sos.ca.gov + build a
source capability matrix:

- `https://campaignfinance.cdn.sos.ca.gov/dbwebexport.zip` (the public
  full export; ~10GB compressed, ~50GB uncompressed)
- Verify checksum matches sos.ca.gov publication
- Inventory all `*_CD.TSV` files — confirm presence of the 6 we need
- Sample-read headers to verify schema matches CAL-ACCESS docs
  (CalAccess has minor schema drift between dump dates; verify before
  assuming column names)

**Source capability matrix.** For each target table, document what's
actually available before Phase 1 DDL. Output: `data/CalAccess/SOURCE_MATRIX.md`.

For each of `RCPT_CD`, `LOAN_CD`, `S496_CD`, `S497_CD`, `EXPN_CD`,
`S401_CD`, capture:

- Amount field(s) — name and semantics (`AMOUNT` vs `LOAN_AMT1..8` etc)
- Date field — transaction date column name and format
- Form-type field — `FORM_TYPE` values present + counts (e.g. for
  `RCPT_CD`, distribution of `A` vs `C` vs others)
- Measure attribution — does the table itself have `BAL_NUM` / `BAL_NAME`,
  or must it be joined via FILING_ID to `CVR_CAMPAIGN_DISCLOSURE_CD`?
  **(critical for S496_CD — round-2 Codex flag below)**
- Stance field — `SUP_OPP_CD` or equivalent
- Amendment fields — `AMEND_ID`, and a count of how many filings have
  multiple amendments
- Memo flag — `MEMO_CODE` column presence, value distribution
- Transaction-line ID — `TRAN_ID` or `LINE_ITEM` column (used for
  dedupe across late vs periodic reports)
- Filer reference — `FILER_ID`, `FILER_NAML`

This matrix is the prerequisite for DDL. Several Phase 1 assumptions
(e.g., "S496_CD has BAL_NUM per filing") need to be validated against
the actual dump.

**Critical correction from Codex round-2:** S496_CD has only ~13 fields,
no `BAL_NUM` and no `SUP_OPP_CD` on the row itself. Measure attribution
must be joined via `FILING_ID` to the cover-sheet table
(`CVR_CAMPAIGN_DISCLOSURE_CD`). S497_CD and EXPN_CD do expose
ballot/stance fields directly. Phase 4 implementation must account for
this difference.

**Estimated time:** 2–4 hours (download + matrix build + spot-check
existing v2 numbers against current HEAD for baseline snapshot)

## Phase 1 — Schema design

Decisions are now resolved (see "Key decisions" + "Anti-double-count
rules" + flow taxonomy below). Concrete deliverables of Phase 1, in
order:

### 1a — Versioning decision (Decision 6)

**Resolved: separate `finance_statewide_v3.db` file.**

Codex round-2 flagged the missing versioning decision. New file vs.
new tables in existing v2.db. Choosing the separate file because:

- Clean atomic switchover (build v3.db end-to-end, validate, then flip
  consumers in one commit)
- Easy rollback (just point consumers back at v2.db)
- v2.db stays as the verified-monetary reference; v3 is the new
  scope-expanded surface
- File size isn't a constraint (v2.db is ~70MB; v3.db likely 200-400MB
  with full transaction-level fact table)

Trade-off: temporary period during Phase 5 frontend migration where
some consumers read v2 and others read v3. Mitigation: ship Phase 5 as
an atomic commit (operations + API + insights + briefing all migrate
together), don't trickle.

### 1b — Transaction-level fact table (Codex rounds 2 + 3)

Codex round-2 caught that summary/top-donors/timeline tables alone
aren't enough — without a normalized internal fact table, provenance
fields in `finance_top_donors_by_type` become lossy (one donor can
have multiple payees, filers, attribution sources, source rows). The
fact table is the foundation; everything else is derived.

Codex round-3 caught a NOT NULL contradiction in the original sketch
(quarantined rows can't have `finance_campaign_id` / `measure_db_id` /
`stance` because their attribution failed) and added cover-sheet
lineage columns to support debugging "why did this filing attach to
this prop?". Same-table quarantine retained because cross-table dedupe
needs every row in one place.

**`finance_flow_v3`** — one row per source-table transaction line
(accepted or quarantined):

```sql
CREATE TABLE finance_flow_v3 (
    flow_id              INTEGER PRIMARY KEY,

    -- Attribution result (NULL for quarantined / unattributed rows)
    finance_campaign_id  TEXT,
    measure_db_id        INTEGER,
    stance               TEXT,                 -- 'support' | 'oppose'
    receipt_type         TEXT,                 -- 'monetary_contribution'
                                               -- 'loan'
                                               -- 'in_kind'
                                               -- 'independent_expenditure'
    amount               REAL,
    txn_date             TEXT,                 -- ISO date
    week_start           TEXT,                 -- Monday ISO

    -- Source provenance (always populated)
    source_table         TEXT NOT NULL,        -- 'RCPT_CD' | 'LOAN_CD' | ...
    source_form_type     TEXT NOT NULL,        -- 'A' | 'C' | 'F465P3' | ...
    filing_id            TEXT NOT NULL,
    amend_id             INTEGER NOT NULL,
    source_line_item     TEXT,                 -- LINE_ITEM column
    source_tran_id       TEXT,                 -- TRAN_ID column
    source_bakref_tid    TEXT,                 -- BAKREF_TID (links across schedules)
    source_memo_refno    TEXT,                 -- MEMO_REFNO (informational memo ref)
    source_xref_schnm    TEXT,                 -- XREF_SCHNM (cross-schedule xref)
    amount_field_used    TEXT,                 -- 'AMOUNT' | 'LOAN_AMT1' | ...

    -- Cover-sheet lineage (populated via FILING_ID join to CVR_CAMPAIGN_DISCLOSURE_CD;
    -- preserved even when attribution succeeds so debugging stays cheap)
    cover_form_type      TEXT,                 -- F460 / F461 / F465 / F496 / etc.
    cover_filer_id       TEXT,
    cover_filer_name     TEXT,
    cover_committee_id   TEXT,
    cover_bal_num        TEXT,
    cover_bal_name       TEXT,
    cover_bal_juris      TEXT,
    cover_sup_opp_cd     TEXT,
    cover_elect_date     TEXT,
    cover_from_date      TEXT,
    cover_thru_date      TEXT,
    attribution_method   TEXT,                 -- 'row_fields' | 'cover_sheet'
                                               -- | 'crosswalk' | 'inferred' | 'failed'

    -- Donor / payee identity
    committee_id         TEXT,                 -- filer of the line-item
    committee_name       TEXT,
    donor_name_raw       TEXT,
    donor_name_canon     TEXT,
    reported_filer       TEXT,                 -- IE rows: filing committee
    payee_name           TEXT,                 -- IE rows: vendor
    attribution_source   TEXT,                 -- 'funding_source' | 'filer'
                                               -- | 'inferred' | 'unknown'
    donor_type           TEXT,
    donor_sector         TEXT,

    -- Memo + dedupe keys
    memo_code            TEXT,                 -- present-and-truthy = excluded as memo
    source_fingerprint   TEXT,                 -- pre-attribution row fingerprint
    dedupe_key           TEXT,                 -- post-attribution cross-source dedupe key

    -- Lifecycle
    quarantine_reason    TEXT                  -- NULL = accepted
);

-- Source-row lookup (for upserts + amendment supersession)
CREATE INDEX idx_flow_source_row
    ON finance_flow_v3 (source_table, filing_id, amend_id, source_line_item);

-- FORM_TYPE distribution queries
CREATE INDEX idx_flow_source_form
    ON finance_flow_v3 (source_table, source_form_type);

-- Hot aggregation paths (accepted rows only)
CREATE INDEX idx_flow_accepted_campaign_stance_type
    ON finance_flow_v3 (finance_campaign_id, stance, receipt_type)
    WHERE quarantine_reason IS NULL;

CREATE INDEX idx_flow_accepted_measure_stance
    ON finance_flow_v3 (measure_db_id, stance)
    WHERE quarantine_reason IS NULL;

CREATE INDEX idx_flow_accepted_type_date
    ON finance_flow_v3 (receipt_type, txn_date)
    WHERE quarantine_reason IS NULL;

CREATE INDEX idx_flow_dedupe
    ON finance_flow_v3 (dedupe_key)
    WHERE quarantine_reason IS NULL;

-- Quarantine analysis
CREATE INDEX idx_flow_quarantine
    ON finance_flow_v3 (quarantine_reason, source_table, source_form_type);
```

**Rationale for the partial indexes** (Codex round-3): hot aggregation
paths read only accepted rows; quarantined rows are typically 30-70%
of source data. Partial indexes keep hot-path indexes ~3x smaller and
exclude them from cache thrash. Quarantine-analysis queries get their
own index so Phase 6 diagnostics don't bottleneck.

**Why same-table quarantine** (despite the nullable attribution
columns): cross-source dedupe in Rule 5 needs every row visible to a
single query. If a periodic F460 RCPT_CD row supersedes a late S497_CD
row, both must be in the same table to compute precedence. Plus,
"quarantined" isn't always permanent — when Phase 4 IE attribution
improves, some previously-quarantined IE rows may move to accepted.
Easier as an UPDATE than a cross-table migration.

**RCPT_CD `FORM_TYPE = 'I'` and `'F401A'` handling** (Codex round-3 +
matrix finding): out of scope for v3, but loaded into the same table
as quarantine rows with `quarantine_reason = 'unsupported_form_type'`
so Phase 6 reports can quantify the excluded dollar volume.
Intermediary receipts (`I`) require additional semantic work to map
real funders through intermediary committees; slate-mailer receipts
(`F401A`) double-count risk against `S401_CD`. Both deferred to v3.1.

### 1c — Derived tables

All derived from `finance_flow_v3` via deterministic SQL transforms:

- **`finance_summary_by_type`** — grouped by
  `(finance_campaign_id, stance, receipt_type)`. Columns:
  `total_amount`, `n_committees`, `n_transactions`, `top5_share`, `hhi`.
  **Critical:** `top5_share` and `hhi` are recomputed per-grouping
  from the underlying donor distribution; never summed across types.

- **`finance_top_donors_by_type`** — grouped by
  `(finance_campaign_id, stance, receipt_type, donor_name_canon)`.
  Includes the per-grouping `attribution_source` (most common across
  rows) and `n_underlying_rows`.

- **`finance_timeline_weekly_by_type`** — grouped by
  `(finance_campaign_id, stance, receipt_type, week_start)`. Cumulative
  totals computed from weekly via SQL window function over a
  **filled week spine** (every Monday between earliest-and-latest
  campaign week; zero-fill missing).

### 1d — Aggregate views (Codex round-2 gotchas integrated)

- **`finance_summary_total`** — VIEW grouping `finance_flow_v3` by
  `(finance_campaign_id, stance)` directly. **Not** `finance_summary_by_type`
  summed across types. Because `top5_share` / `hhi` must be recomputed
  against the merged-across-types donor distribution, not aggregated
  from per-type values.

- **`finance_top_donors_total`** — VIEW grouping `finance_flow_v3` by
  `(finance_campaign_id, stance, donor_name_canon)`. Columns include:
  - `total_amount` (sum across types)
  - `flow_types` — JSON array of types this donor appears in (e.g.
    `["monetary_contribution", "independent_expenditure"]`)
  - `attribution_sources` — JSON array
  - `primary_attribution_source` — most common attribution_source by
    dollar weight
  - **Does NOT expose** a single `payee_name` or `reported_filer` —
    those are role-specific to IE rows and lossy at aggregate. Detailed
    provenance stays in `finance_flow_v3`.

- **`finance_timeline_weekly_total`** — VIEW recomputing weekly +
  cumulative from `finance_flow_v3` directly over the filled week
  spine. Not derived from `_by_type` by SUM.

### 1e — Pre-Phase-2 prep

- Re-snapshot **current v2 numbers** from HEAD (not the stale 2026-05-04
  baseline) into `data/CalAccess/v2_pre_v3_baseline.json` — used for
  Layer 1 no-regression checks. Includes:
  - `finance_summary` rows for all 181 campaigns
  - `finance_top_donors` top-5 per (campaign, stance)
  - Snapshot hash so we can confirm at end-of-Phase-6 that v3's
    monetary slice still matches.

- Capture Ballotpedia reference figures with URL + capture-date in
  `data/CalAccess/ballotpedia_baselines.json` (Codex round-2 note:
  these change over time; freeze them at a known capture point).

## Phase 2 — Loans (`LOAN_CD`)

Smallest scope, easiest to verify. Loans are typically small fraction of
campaign money (often $0 for ballot measures since they don't borrow).

**Codex round-2 correction:** LOAN_CD does NOT have a single `AMOUNT`
column. It has `LOAN_AMT1` through `LOAN_AMT8`, and the semantics of
each column depend on `FORM_TYPE`. Schedule B Part 1 (loans received)
is what we want; Schedule B Part 2 (guarantors), repayments,
outstanding balances, and loans made are explicitly out of scope.

Concrete:

- Extend `extract_calaccess_finance.py` to read `LOAN_CD` alongside
  `RCPT_CD`, joining on FILING_ID
- Filter to Schedule B Part 1 receive-loan rows (specific FORM_TYPE
  values determined by Phase 0 source matrix)
- Map `LOAN_AMT1` (or correct column per FORM_TYPE rule) as the loan
  amount
- Add `receipt_type='loan'` rows to `finance_flow_v3`
- Verify reconciliation: sum of accepted loan rows per
  (campaign, stance) matches direct SQL against LOAN_CD filtered to
  the same FORM_TYPE / amendment / non-memo rules

## Phase 3 — In-kind contributions (Schedule C)

**Codex round-2 confirmation:** in-kind contributions live in `RCPT_CD`
with `FORM_TYPE = 'C'` (Schedule C), parallel to `FORM_TYPE = 'A'`
(Schedule A monetary). Our current extract implicitly filters to
Schedule A only; relaxing that filter to also keep Schedule C is the
core change.

Concrete:

- Relax the `RCPT_CD` filter to keep both `FORM_TYPE='A'` (monetary)
  and `FORM_TYPE='C'` (in-kind)
- Tag each row's `receipt_type` based on `FORM_TYPE`:
  - `'A'` → `monetary_contribution`
  - `'C'` → `in_kind`
- Verify reconciliation per receipt_type against filtered RCPT_CD SUM

## Phase 4 — Independent Expenditures (biggest impact)

**Codex round-2 fix.** Original plan listed three sources for IE
spending; round-2 corrected several attribution and source-table
assumptions. The corrected list:

1. **`S496_CD`** — 24-hour late IE filings (mandatory for IEs > $1K in
   the 90 days before an election). **Critical:** S496_CD does NOT
   have `BAL_NUM` or `SUP_OPP_CD` on the row itself. Measure +
   stance attribution must be joined via `FILING_ID` to the cover-sheet
   table (`CVR_CAMPAIGN_DISCLOSURE_CD`), then to BAL_NUM/SUP_OPP_CD on
   that cover sheet. Need to confirm via Phase 0 matrix whether the
   cover-sheet measure attribution itself comes from a separate line
   in S496_CD or from a parent filing.
2. **F461 filings** in `CVR_CAMPAIGN_DISCLOSURE_CD` — Major Donor /
   Independent Expenditure committee disclosures. Schedules associated
   with these are in `EXPN_CD`
3. **`EXPN_CD` Schedule E entries** for filings by official PACs that
   themselves made IEs against other props (rare but happens)

Each requires its own prop-attribution logic:

2. **`EXPN_CD` — F461 Part 5 (Schedule E equivalent) and F465 Part 3
   (supplemental IE report)** — official IE filings from major-donor
   and IE committees. Per Codex round-2:
   - `EXPN_CD FORM_TYPE = 'F461P5'` — major donor IE schedule
   - `EXPN_CD FORM_TYPE = 'F465P3'` — Form 465 (supplemental IE report)
     part 3
   - Both have ballot-measure attribution fields documented on the row
   - `BAKREF_TID` may link back to parent forms; investigate during
     Phase 0 matrix

3. **`S497_CD` — 24-hour late contributions/expenditures** — DEMOTED
   from primary source to cross-check / investigation. Per Codex
   round-2: late reports frequently duplicate later periodic filings
   (S497-reported IEs reappear in F465P3 / F461P5). Use S497_CD only
   as a fallback when the same transaction isn't found in EXPN_CD
   filings, and only after dedup-precedence rules are settled.

4. **Slate mailers (`S401_CD`)** — not in scope for first pass; revisit
   if Ballotpedia gap remains material after IE ingestion. Slate-mailer
   organizations are a distinct contribution vehicle and may
   double-count if naively added on top of IE.

**Attribution risks (now explicit):**

- S496_CD measure attribution requires cover-sheet join (round-2 fix)
- Multi-prop IE filings: one filing covering 2+ props needs to be
  split per-prop on a per-line basis if amounts are itemized, or
  pro-rata if not. Most filings itemize.
- F461 major-donor filings sometimes name the funding entity at filing
  level + payee per line. Capture both: `attribution_source = funding_source`
  if the funder is named distinctly from the filer/payee.
- IE-by-recipient-committees (a PAC primarily supporting Prop X spending
  on IEs against Prop Y): attribute to Prop Y's `oppose` stance via
  the per-expenditure-line `BAL_NUM` / `SUP_OPP_CD`, NOT to the PAC's
  primary affiliation.

## Phase 5 — Frontend integration

**Sequencing (Codex round-2 addition):** API/operations layer migrates
**before** the visual UI. The library must support both reading
patterns (v2 monetary-only and v3 by-type / total) before any UI
references the new surface.

Concrete order within Phase 5:

1. **Library/API migration (no UI change yet).** Add new methods on
   `FinanceDatabase`:
   - `get_finance_summary_total(measure_db_id)` — uses `finance_summary_total`
     view
   - `get_finance_breakdown_by_type(measure_db_id)` — uses
     `finance_summary_by_type`
   - `get_top_donors_total(campaign_id, stance, limit=N)` — uses
     `finance_top_donors_total`
   - `get_top_donors_by_type(campaign_id, stance, receipt_type,
     limit=N)` — uses `finance_top_donors_by_type`
   - Existing `get_top_donors()`, `aggregate_for_measure()`, etc. keep
     reading v2 monetary-only tables. No breakage.

2. **Atomic visible-change commit.** All UI surfaces flip to the new
   surface in one commit, along with the methodology copy update:
   - Modal Finance tab: total + breakdown layout
   - Hero card / Insights Module 1: total replaces monetary
   - Insights Module 4 (marquee fights): includes IE
   - Insights Module 3 (top donors): uses `_total` ranked list
   - Briefing pipeline finance facts: uses `_total`
   - API endpoint: returns both `total` and `breakdown` payloads
   - Methodology note replaces "we don't include IE" copy with "we
     now include..."
   - `insights.json` regenerated; `index.html` regenerated

   Atomic because: if hero shows total but modal shows monetary,
   user sees inconsistent numbers and trust craters. Ship together.

## Phase 6 — Final verification + docs

- Re-run all 68 checks from `plans/finance-rebuild-verification.md`
- Update methodology note in panel + README + insights JSON
- Update `CHANGELOG.md` with the scope expansion
- Update `plans/finance-rebuild-verification.md` with new baseline
  numbers + new Phase G checks for IE / in-kind / loan integrity

## Key decisions (Codex round-1 integrated 2026-05-13)

### Decision 1 — Aggregation semantics

**Resolved: (c) both, with careful language.** Show direct receipts and
IE spending separately in the data model; combine for the public-facing
"scale of money" headline. **Never use the word "raised" for the combined
number** — IE money is spent *in support of* a measure, not raised *by*
the campaign committee. They're different economic objects.

UI copy convention:

- Headline: **"Total support-side money: $418M"** (or "Total opposition")
- Breakdown sub-line: **"Direct receipts $146M · Independent spending $272M"**

Loans + in-kind get rolled into the breakdown when material; collapsed
when negligible. Data model preserves all four types-specific totals.

### Decision 2 — Receipt-type storage

**Resolved: v3 parallel-tables approach with backward-compat views.**

Adding `receipt_type` as a discriminator to existing v2 tables would
change the grain from `(campaign, stance)` to `(campaign, stance,
receipt_type)`. Every existing consumer that assumes one row per stance
would silently produce duplicated or fragmented totals. Codex flagged
this as a v3 migration, not a small additive column.

Concrete plan:

- **`finance_summary`** (v2 existing) — stays put. Direct monetary only.
  No grain change. Backward-compat for all existing consumers until they
  migrate.
- **`finance_summary_by_type`** (NEW) — new grain `(campaign, stance,
  receipt_type)`. Used by new consumers wanting breakdown.
- **`finance_summary_total`** (NEW view) — sums `finance_summary_by_type`
  across `receipt_type`, grain `(campaign, stance)`. Used by new
  consumers wanting headline number.
- **`finance_top_donors`** — same pattern: existing v2 table stays
  monetary-only; new `finance_top_donors_by_type` has the type grain;
  optional `finance_top_donors_total` view aggregates funder-side
  contributions across types.
- **`finance_timeline_weekly`** — same pattern: existing v2 monetary-only;
  new `finance_timeline_weekly_by_type`.

This means **every v2 consumer continues to work unchanged**. The Finance
panel + modal + Insights + briefing each migrate one at a time to the
`_by_type` / `_total` surfaces. Phase 5 (frontend) does the migration
deliberately and verifiably.

### Decision 3 — IE donor attribution

**Resolved: (a) funding source when extractable, with provenance fields.**

Codex's structural point: an IE filing names up to three different
parties:

- **Funder** — who gave the money (e.g. FanDuel)
- **Filer** — the IE committee that filed the report (often a reporting
  shell)
- **Payee** — the vendor that received the spend (e.g. Ad Agency LLC)

These are three distinct roles. Don't overload `donor_name_canon`.

Schema additions for IE rows in `finance_top_donors_by_type`:

- `donor_name_canon` — populated with the funder when extractable, else
  the filer
- `attribution_source` — one of `funding_source` / `filer` / `inferred` /
  `unknown` — tells consumers how trustworthy the donor field is
- `reported_filer` — the IE committee's name (always populated for IE
  rows; redundant with donor_name_canon when the filer is also the
  funder)
- `payee_name` — the vendor (kept for future reporting / analytics; not
  shown in donor lists since it's not the funding source)

For monetary rows: `attribution_source='funding_source'`, `reported_filer`
and `payee_name` null.

### Decision 4 — Frontend default headline

**Resolved: total, with breakdown visible.** Headline uses the
combined-types number; the breakdown is a sub-line on the same card,
not a modal-only detail. This avoids the current undercount without
hiding the methodology.

Example modal Finance tab:

```
SUPPORT
$418M total support-side money
  ↳ $146M direct receipts · $272M independent spending

TOP DONORS (support, all flows)
  1. FanDuel Sportsbook       $58M  [Direct + IE]
  2. DraftKings (Crown Gaming) $52M  [Direct + IE]
  ...
```

Hero card / Insights win-rate math re-runs against the new total. The
current 65% better-funded-win-rate will shift — likely down, since IE
spending tends to be heavier on the losing side of contentious props
(both Prop 22 sides had huge IE money; Prop 27 oppose had massive
tribal IE). Document the shift in Phase 6.

### Decision 5 — Flow taxonomy & user-facing labels (added by Codex)

**Resolved: explicit taxonomy, locked before Phase 2 begins.**

Internal `receipt_type` values:

| Internal value | Source CAL-ACCESS data | Public label |
|---|---|---|
| `monetary_contribution` | `RCPT_CD` (current) | "Direct contributions" |
| `loan` | `LOAN_CD` | "Loans" |
| `in_kind` | `RCPT_CD` Schedule C entries (FORM_TYPE filter) OR separate non-monetary table — TBD Phase 0 | "In-kind support" |
| `independent_expenditure` | `S496_CD` + F461 filings via `EXPN_CD` | "Independent spending" |

Aggregated header label: **"Total support-side money"** (or
"opposition-side"). Never "raised" once IE is included.

## Anti-double-count rules (Codex round-2 expanded)

Critical: direct receipts + PAC expenditures double-count if naively
summed (money flows in as receipt, then out as expenditure of the same
dollars). Codex round-2 flagged the original rule as directionally right
but incomplete. The full rule set, applied at the rebuild stage:

### Rule 1 — Allowed flows (sum across these is the "total support-side / opposition-side money")

- Monetary contributions to recipient committee (`RCPT_CD FORM_TYPE='A'`)
- Loans received by recipient committee (`LOAN_CD` Schedule B Part 1)
- In-kind contributions to recipient committee (`RCPT_CD FORM_TYPE='C'`)
- IE spending by major donors / IE committees (`EXPN_CD FORM_TYPE='F461P5'`
  + `F465P3`, plus S496_CD as fallback)

### Rule 2 — Disallowed flows (would double-count or are out of scope)

- PAC's own general expenditures (`EXPN_CD` rows from a recipient
  committee filing under non-IE form types) — the PAC spending its
  own receipts. We do NOT ingest these.
- Loan repayments, forgiveness, guarantor entries (`LOAN_CD` rows where
  FORM_TYPE indicates Schedule B Part 2 or repayment subtypes).
- Loans made BY a committee to others (out of scope; not money in).
- Debt / accrued expenses (`DEBT_CD`).

### Rule 3 — Amendment precedence

For every `FILING_ID`, keep only the latest `AMEND_ID`. Older amendments
are superseded. This is already done at the filing-level for
`CVR_CAMPAIGN_DISCLOSURE_CD`; needs to be enforced at the line-item
level for each source table.

### Rule 4 — Memo rows

Exclude rows where `MEMO_CODE` is set (truthy) unless proven additive
during Phase 0 source-matrix work. Memo rows are typically informational
breakouts of a transaction that's already counted elsewhere.

### Rule 5 — Late-report vs periodic-report precedence

The same underlying transaction can appear in:

- S496_CD (24-hour IE late filing)
- S497_CD (24-hour late contribution / expenditure)
- F461P5 (major donor IE schedule, periodic report)
- F465P3 (Form 465 supplemental IE report, periodic)
- F460 Schedule A (monetary contributions, periodic)

**Precedence (in order of preference):**

1. **EXPN_CD periodic IE entries** (F461P5, F465P3) — most complete
2. **RCPT_CD monetary** (F460 Schedule A) — periodic, authoritative for
   contributions
3. **LOAN_CD periodic** — periodic, authoritative for loans
4. **S496_CD / S497_CD late filings** — only when the same TRAN_ID /
   line-item is absent from the periodic source

**Dedupe key** (Codex round-3): use the post-attribution
`finance_campaign_id`, not raw `BAL_NUM`. The campaign_id is the
normalized, crosswalk-resolved attribution target; BAL_NUM is sparse
and not the granularity we de-duplicate against.

Accepted-row `dedupe_key` (column on `finance_flow_v3`):

```
receipt_type | finance_campaign_id | stance | donor_name_canon |
payee_name | txn_date | amount | committee_id
```

For rows where attribution failed (`finance_campaign_id IS NULL`), a
separate `source_fingerprint` column carries a row-level fingerprint
derived from `(source_table, source_form_type, filing_id,
source_line_item, source_tran_id)`. This is for traceability and
re-runnable rebuilds, not for cross-source dedupe.

Cover-sheet fields (`cover_bal_num`, `cover_elect_date`, etc.) are
**preserved alongside** `finance_campaign_id` for debugging "why did
this row attach to this prop?" — but they don't appear in the dedupe
key itself.

### Rule 6 — IE attribution to the targeted prop, not the filer's affiliation

A committee primarily affiliated with Prop X may make IE spending
against Prop Y on the same ballot. Attribution rule: every expenditure
line's own `BAL_NUM` + `SUP_OPP_CD` determines the (prop, stance) it
counts toward. Do NOT attribute by the filer's primary affiliation.

### Edge case: same donor, multiple flows, same prop

E.g., FanDuel gives $5M to Yes-on-27 PAC (monetary) AND spends $20M
directly on ads (IE). Both legitimately count: they're disjoint flows
of FanDuel money. `finance_top_donors_total` view sums the funder across
types (FanDuel = $25M total support); `finance_top_donors_by_type` keeps
them separate ($5M monetary + $20M IE). No double-count.

### Edge case: same donor, same flow type, different reporting period

E.g., FanDuel gives $8.33M on 2022-07-15 reported on the 24-hour late
filing AND the semi-annual F460. Rule 5 precedence collapses these to
the periodic-source row only. The Gate 7 dedupe key
(`finance_campaign_id, stance, txn_date, amount, donor_canon,
donor_type, committee`) already catches this within a source; cross-source
dedup uses the same key plus `receipt_type` and `payee_name`.

## Verification strategy

Layered verification at every phase boundary so a regression is contained
and traceable.

### Layer 1 — No-regression on monetary (Codex round-3 tightened)

Under the v3 parallel-tables design, the existing `finance_summary` and
`finance_top_donors` v2 tables remain monetary-only and are written by
the same rebuild path as today. So no-regression should be *trivially*
true. But verify it explicitly. Baseline is at
`data/CalAccess/v2_pre_v3_baseline.json` (194 campaigns, 301 summary
rows, $3,240,293,198.54 grand total, SHA-256 self-hash). Layer 1
assertions, all of which must pass before any phase completes:

1. **Exact same `finance_summary` keys.** The set of
   `(finance_campaign_id, stance)` keys after rebuild == the baseline
   key set. No keys added or removed unless an explicit Phase note
   documents why.
2. **Exact same `finance_summary` values.** For every key:
   `total_receipts`, `n_committees`, `top5_share`, `hhi` all equal
   the baseline values to the penny / to 4 decimal places.
3. **Exact same top-5 donor keys.** For every `(campaign, stance)`,
   the set of top-5 `donor_name_canon` is identical to baseline.
4. **Exact same top-5 donor values.** Per donor: `donor_type` matches
   and `total_amount` equal to the penny.
5. **v3 monetary slice equals v2 monetary baseline.** Querying
   `finance_summary_by_type WHERE receipt_type = 'monetary_contribution'`
   must equal the v2 `finance_summary` baseline for all 194 campaigns.
   Cross-check that the new code path doesn't drift from the old.
6. **No extra monetary campaigns.** Count of distinct
   `finance_campaign_id` with `receipt_type = 'monetary_contribution'`
   must equal baseline's `campaign_count = 194` unless an explicit
   Phase note documents an intentional addition.
7. **Baseline hash unchanged.** The `_self_hash` in
   `v2_pre_v3_baseline.json` matches at every comparison run (paranoia
   check — if anyone mutates the baseline file mid-project, this
   trips).

Any deviation = bug. Halt and investigate. Specifically, do NOT
proceed to the next phase if any assertion fails.

### Layer 2 — Source-table reconciliation (THE main acceptance criterion, Codex round-2)

For each new receipt type, the sum in `finance_summary_by_type` /
`finance_flow_v3` must reconcile to direct SQL against the source
CAL-ACCESS table **after applying the same filters**. Raw `SUM(AMOUNT)`
overstates because it doesn't honor amendment / memo / non-additive
filters.

**Reconciliation pattern, per receipt type:**

```
For each receipt_type R:
    src_total = SUM(amount) over source-table rows WHERE
        - filing_id in (ballot-measure filings, matched to crosswalk)
        - amend_id = MAX(amend_id) FOR THAT FILING  -- latest amendment only
        - memo_code IS NULL OR FALSY  -- exclude memos
        - form_type IN (allowed types for R)  -- e.g. 'A' for monetary
        - dedupe applied per Rule 5 precedence
        - (for IE) attributed to a known (BAL_NUM, election_year)
    v3_total = SUM(amount) FROM finance_flow_v3 WHERE
        receipt_type = R AND quarantine_reason IS NULL
    assert abs(src_total - v3_total) < $1.00 per campaign
```

**Critical:** the reconciliation source query must apply the same
filters as the rebuild. Otherwise we'd be comparing apples to "all
source data" and the reconciliation would never pass. The filtered-SUM
script lives at `scripts/reconcile_source_totals.py` and is reused at
every phase boundary.

Tolerance: $1 per campaign (rounding accumulation). Larger gaps = bug.

### Layer 3 — Ballotpedia smoke test (demoted from gate, Codex round-2)

Codex round-2: Ballotpedia numbers change over time, their methodology
may differ from ours, and they may include sources we still don't
capture (slate mailers, 527 organizations, out-of-state spending).
Therefore: Ballotpedia is a **smoke test**, not an acceptance gate.
If we're systematically far below Ballotpedia after Phase 4, that's a
signal to investigate, not a pass/fail.

Reference figures captured with provenance:

| Prop | Target support | Target oppose | Source URL | Captured |
|---|---|---|---|---|
| PROP_22_2020 | $224.3M | $20.0M | (capture in Phase 0) | 2026-05-13 |
| PROP_27_2022 | $169.1M | $249.3M | (capture in Phase 0) | 2026-05-13 |
| PROP_32_2012 | $74M | $60M | (capture in Phase 0) | 2026-05-13 |
| PROP_8_2018 | $20.7M | $111.5M | (capture in Phase 0) | 2026-05-13 |
| PROP_50_2025 | $165M | $0M | Current sentinel | n/a |

Snapshot lives in `data/CalAccess/ballotpedia_baselines.json` with
URLs + capture dates. Re-capture before Phase 6 if any number is
materially stale.

**Smoke threshold:** post-change Total within **±25%** of Ballotpedia
for **≥4 of 5 props**. If <4/5 pass, halt and investigate. ±25% is
deliberately loose because Ballotpedia methodology drift is expected;
the real acceptance is Layer 2 source reconciliation.

If <4/5 pass, halt and investigate. Most likely failure modes:
- Missing IE committees not tagged with BAL_NUM (separate crosswalk
  expansion needed)
- Ballotpedia includes IE spending we don't (need to debug source
  ingestion)
- IE attribution rule differs from Ballotpedia's (document and decide
  whether to align)

### Layer 4 — Sentinel preservation

Existing 5 in-target-year sentinels stay at ≥95% in-target-year activity:

- PROP_16_2020, PROP_22_2020, PROP_32_2024, PROP_6_2024, PROP_50_2025

Adding IEs / loans / in-kind to these props' totals shouldn't shift the
year-distribution materially (IE money is filed in the same election
cycle as the underlying contributions).

### Layer 5 — Dollar-trace per receipt type (Codex round-2 expanded)

Codex round-2: add one trace test per source type, not just one for IE.
Each catches systemic extraction bugs (wrong field parsed, wrong
attribution, off-by-one) that aggregate reconciliation might mask.

For each of `monetary_contribution`, `in_kind`, `loan`,
`independent_expenditure`:

- Pick one specific known transaction with public/verifiable reporting
  (URL captured in `data/CalAccess/trace_tests.json`)
- Verify the transaction appears in `finance_flow_v3` with:
  - Correct `finance_campaign_id` + `stance` + `receipt_type`
  - Correct `donor_name_canon` (and `payee_name` for IE)
  - Correct `amount` (exact match to source)
  - Correct `txn_date`
  - Sensible `attribution_source` value
- Document the source URL + capture-date

Trace candidates (finalize in Phase 0):

- Monetary: FanDuel $8.33M to Yes-on-27 PAC on 2022-07-15
- In-kind: TBD (Phase 0 — pick from any prop with material Schedule C)
- Loan: TBD (Phase 0 — search LOAN_CD for ballot-measure committee
  loans; ballot props rarely borrow, may need fallback example)
- IE: TBD (Phase 0 — pick a publicly-reported FanDuel or San Manuel
  IE spend; Ballotpedia / CalMatters articles cite specifics)

## Existing schema risks (Codex round-2 addition)

**Stale baseline.** "181 campaigns / $3.24B" reflects 2026-05-12 state,
not necessarily HEAD. Phase 1e re-snapshots current numbers before
locking the no-regression baseline.

**Measure rollup interaction.** Some `finance_campaign_id`s share a
`measure_db_id` after year-offset recovery (the Bucket A fix from
matcher v2). The v2 layer handles this via
`FinanceDatabase.aggregate_for_measure(measure_db_id)`, which rolls up
campaigns sharing a measure_db_id into a single measure-level view.

v3 design implications:

- `finance_flow_v3` rows are **campaign-grain** (one row per accepted
  transaction with its `finance_campaign_id`). This is the right grain
  for traceability.
- `finance_summary_by_type` / `finance_summary_total` are also
  **campaign-grain** so they roll up cleanly through existing
  `aggregate_for_measure()`-style logic.
- Public-facing APIs (modal, briefing, insights) continue to call
  `aggregate_for_measure(measure_db_id)` to merge collision pairs
  into a single user-facing measure record. Phase 5 library migration
  needs a v3-aware version: `aggregate_for_measure_v3(measure_db_id)`
  that hits the new tables and views.

**Consumer audit before atomic Phase 5 commit:** every place that
currently calls `get_top_donors()`, `aggregate_for_measure()`, or reads
`finance_summary` directly needs a decision: stay on v2 monetary or
migrate to v3. Phase 5 commit includes a checklist + grep of consumer
call sites.

## Risks

- **CAL-ACCESS schema drift:** column names sometimes change between
  dumps. Verify against documentation before assuming. Phase 0 source
  matrix catches this.
- **IE attribution edge cases:** multi-prop filings; donor-of-donor
  chains in major-donor filings; gray-area cases ("issue advocacy"
  that doesn't legally qualify as IE).
- **S496_CD attribution gap (round-2 fix):** S496_CD itself has no
  BAL_NUM. Cover-sheet join required; if the join is missing data for
  some filings, we'll silently lose IE money. Phase 0 source matrix
  must confirm join completeness.
- **Headline number shift will surprise users.** Homepage total
  receipts going from $3.24B to ~$6-8B is a major perceptual change.
  Phase 5 atomic commit + methodology copy mitigates.
- **We may not match Ballotpedia exactly.** Their methodology may
  include things we still don't capture (slate mailers, 527s,
  out-of-state). Ballotpedia is now a smoke test (±25%), not an
  acceptance gate.
- **v2.db → v3.db cutover:** consumers reading v2 during cutover get
  stale numbers. Phase 5 atomic commit limits the cutover window.
- **Late-vs-periodic dedup precedence rule (Rule 5):** if precedence
  is wrong, we could either undercount (drop periodic in favor of
  late) or double-count (keep both). Reconciliation layer 2 catches
  this; trace tests on each receipt type verify it.

## Effort estimate (revised after Codex round-2)

| Phase | Effort | Cumulative |
|---|---|---|
| 0 — Source data + capability matrix + baselines | 4–6 hours | 4–6 |
| 1 — Schema design (DDL: flow table + by-type + views) | 6–8 hours | 10–14 |
| 2 — LOAN_CD ingestion + verify | 3–5 hours | 13–19 |
| 3 — In-kind ingestion + verify | 3–5 hours | 16–24 |
| 4 — IE ingestion + dedup precedence + verify (biggest) | 2–3 days | 32–48 |
| 5 — Library migration + atomic frontend commit | 8–12 hours | 40–60 |
| 6 — Final verification + docs | 4–6 hours | 44–66 |

**Total: ~6–8 days of focused work over 2–3 weeks.** Higher than
original estimate because Codex round-2 surfaced (a) the transaction-
level fact table as foundational rather than optional, (b) the
late-vs-periodic dedup precedence as a non-trivial design problem, and
(c) the atomic-commit frontend migration requirement.

Phase 4 remains the big rock — IE ingestion has the most complex
attribution + dedup logic.

## Next steps

**Phase 0: DONE (2026-05-13, commit `61e4527`).** Source matrix
built, baseline snapshotted, Ballotpedia baselines captured. Codex
round-3 review integrated above (NOT NULL fix, cover-sheet lineage
columns, partial indexes, quarantine of unsupported FORM_TYPEs,
campaign_id-keyed dedupe, tightened Layer 1 assertions).

**Phase 1: ready to begin on user go-ahead.** Deliverables:

1. `scripts/v3/schema.sql` — full DDL for `finance_flow_v3` +
   derived tables + views, matching section 1b above exactly.
2. `scripts/v3/init_db.py` — idempotent migration runner that creates
   `scraper/data/finance/finance_statewide_v3.db` from `schema.sql`.
3. `scripts/v3/verify_layer1.py` — Layer 1 no-regression checker
   reading from `v2_pre_v3_baseline.json`.
4. Smoke test: run `init_db.py` to confirm DDL parses + indexes create
   cleanly. No data loaded yet.

Phase 1 deliverables are still cheap to throw away if anything
surfaces. Phase 2 (LOAN_CD ingestion) is where the first real data
touches v3.db.

Nothing irreversible happens until decisions are made and Codex has
weighed in.
