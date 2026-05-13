---
plan: Finance extract scope expansion (close the Ballotpedia gap)
status: DRAFT 2026-05-13 — Codex round-1 (decisions) integrated; awaiting Codex round-2 (full plan review)
target: v3 total-support-side-money within ±10% of Ballotpedia for top 5 high-IE props
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

**Action:** download fresh CAL-ACCESS dump from sos.ca.gov:

- `https://campaignfinance.cdn.sos.ca.gov/dbwebexport.zip` (the public
  full export; ~10GB compressed, ~50GB uncompressed)
- Verify checksum matches sos.ca.gov publication
- Inventory all `*_CD.TSV` files — confirm presence of the 5 above
- Sample-read headers to verify schema matches CAL-ACCESS docs (CalAccess
  has minor schema drift between dump dates; verify before assuming
  column names)

**Estimated time:** 1–2 hours (mostly download)

## Phase 1 — Schema design & plan review

Decisions are now resolved (see "Key decisions" + "Anti-double-count
rules" + flow taxonomy below). Concrete deliverables of Phase 1:

- **DDL** for the three new v3 tables: `finance_summary_by_type`,
  `finance_top_donors_by_type`, `finance_timeline_weekly_by_type`
- **DDL for views**: `finance_summary_total`, `finance_top_donors_total`
- Pluck `finance_summary` (v2 existing) and `finance_top_donors` (v2
  existing) — **no schema change**; they remain monetary-only.
- Codex round-2 review of the full plan + DDL before Phase 2.

## Phase 2 — Loans (`LOAN_CD`)

Smallest scope, easiest to verify. Loans are typically small fraction of
campaign money (often $0 for ballot measures since they don't borrow).

- Extend `extract_calaccess_finance.py` to read `LOAN_CD` alongside
  `RCPT_CD`, joining on FILING_ID
- Add `receipt_type='loan'` rows to output CSV
- Verify reconciliation: sum of LOAN_CD amounts per ballot-measure filing
  matches new `finance_summary` loan column

## Phase 3 — In-kind contributions

Need to verify upstream whether in-kind lives in `RCPT_CD` (distinguished
by `FORM_TYPE` or `REC_TYPE` field) or in a separate table.

**Investigation:** sample-read a few hundred rows of `RCPT_CD.TSV`
filtered to known ballot-measure filings; check distribution of
`FORM_TYPE` / `REC_TYPE`. If in-kind = `FORM_TYPE='C'` (Schedule C), then
we just need to relax our current implicit Schedule-A filter. If it lives
elsewhere, additional table ingestion required.

## Phase 4 — Independent Expenditures (biggest impact)

This is where most of the missing money lives. Three sources to ingest:

1. **`S496_CD`** — 24-hour late IE filings (mandatory for IEs > $1K in
   the 90 days before an election)
2. **F461 filings** in `CVR_CAMPAIGN_DISCLOSURE_CD` — Major Donor /
   Independent Expenditure committee disclosures. Schedules associated
   with these are in `EXPN_CD`
3. **`EXPN_CD` Schedule E entries** for filings by official PACs that
   themselves made IEs against other props (rare but happens)

Each requires its own prop-attribution logic:

- S496_CD has a `BAL_NUM` field on each filing → direct prop attribution
- F461 EXPN_CD entries reference `BAKREF_TID` (links the expenditure to
  the supported/opposed measure)
- Stance is explicit (`SUP_OPP_CD`)

**Risk:** IE attribution edge cases. E.g., an IE committee that supports
TWO different props in the same filing. Need to split per-prop on a
pro-rata or per-line basis. Document the rule.

## Phase 5 — Frontend integration

Decisions from Phase 1 cascade here:

- **Modal Finance tab**: show breakdown (Monetary / In-kind / Loans /
  IEs / Total) or single Total with hover tooltip?
- **Hero card top-funded-side**: use Total or stay on Monetary?
- **Insights panel** Module 1 (hero stats): "campaigns / total / win
  rate" — does Total now include IE spending? If yes, win-rate math
  re-runs and the 65% number will shift.
- **Insights Module 4 (marquee fights)**: now include IE spending in the
  per-side dollar amounts

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

## Anti-double-count rules (added by Codex)

Critical: direct receipts + PAC expenditures double-count if naively
summed (money flows in as receipt, then out as expenditure of the same
dollars). The expansion below intentionally avoids this trap, but the
rule must be explicit in the rebuild:

**Allowed sums (no double-count):**

- Monetary contributions to PAC (`RCPT_CD`)
- Loans received by PAC (`LOAN_CD`)
- In-kind contributions to PAC (RCPT_CD Schedule C or equivalent)
- IE spending by major donors (`S496_CD` / F461 funders) — money that
  bypassed the PAC

**Disallowed sums (would double-count):**

- PAC's own expenditures (`EXPN_CD` for the recipient committee) — this
  is the PAC spending dollars we already counted as receipts. We do NOT
  ingest PAC expenditures in this expansion.

**Edge case: a recipient committee that also makes IEs against other
props.** E.g., a labor PAC that opposes Prop X (its primary affiliation)
may also make IE spending against unrelated Prop Y. The IE money is
attributed to Prop Y's `oppose` side, NOT counted as part of Prop X.
This is handled by the per-filing `BAL_NUM` / `BAKREF_TID` field on each
expenditure record, not by the committee's primary affiliation.

**Edge case: same donor appears in multiple types for the same prop.**
E.g., FanDuel gives $5M to Yes-on-27 PAC (monetary) AND spends $20M
directly on ads (IE). Both legitimately count: they're disjoint flows
of FanDuel money. `finance_top_donors_total` view should sum the funder
across types (FanDuel = $25M total support), but the breakdown view
keeps them separate ($5M monetary + $20M IE).

## Verification strategy

Layered verification at every phase boundary so a regression is contained
and traceable.

### Layer 1 — No-regression on monetary

Under the v3 parallel-tables design, the existing `finance_summary` and
`finance_top_donors` v2 tables remain monetary-only and are written by
the same rebuild path as today. So no-regression should be *trivially*
true. But verify it explicitly:

1. Snapshot v2 `finance_summary` for all 181 campaigns to
   `plans/finance-extract-baseline.json`
2. Snapshot v2 `finance_top_donors` top-5 per campaign per stance
3. After every phase: re-run a comparison: v2 `finance_summary` must
   equal the snapshot **to the penny**; v2 `finance_top_donors` top-5
   identical.
4. ALSO verify: `finance_summary_by_type` WHERE `receipt_type =
   'monetary_contribution'` must equal the v2 `finance_summary` slice
   for the same campaigns. (Cross-check that the v3 monetary slice and
   the v2 monetary table agree — catches bugs where the new code path
   drifts from the old.)

Any deviation in either check = bug. Halt and investigate.

### Layer 2 — Source-table reconciliation

For each new receipt type, sum the new `finance_summary` entries and
compare to direct SQL against the source CAL-ACCESS table:

- LOAN_CD: `SELECT SUM(AMOUNT) FROM LOAN_CD WHERE FILING_ID IN
  (ballot-measure filing IDs)` = total loans column in v2
- In-kind: similar
- IE: per-prop sum = sum of `S496_CD` + relevant `EXPN_CD` Schedule E

Tolerance: $1 per campaign (rounding). Larger gaps = bug.

### Layer 3 — Ballotpedia spot-check (the headline test)

5 reference props with reliable Ballotpedia totals:

| Prop | Target support | Target oppose | Source |
|---|---|---|---|
| PROP_22_2020 | $224.3M | $20.0M | Ballotpedia |
| PROP_27_2022 | $169.1M | $249.3M | Ballotpedia |
| PROP_32_2012 | $74M | $60M | Ballotpedia |
| PROP_8_2018 | $20.7M | $111.5M | Ballotpedia |
| PROP_50_2025 | $165M | $0M | Current sentinel |

**Acceptance criteria:** post-change **Total support-side money / Total
opposition-side money** (sum across monetary + loan + in_kind + IE
in `finance_summary_total` view) within **±10%** of Ballotpedia for
**≥4 of 5 props**.

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

### Layer 5 — Dollar-trace test

Pick one **known specific IE transaction** with public reporting (e.g.,
the FanDuel $20M to ad-agency-X on date-Y). Verify:

1. It appears in our IE ingest output
2. It's attributed to PROP_27_2022 support
3. The dollar amount matches CAL-ACCESS web display

This catches systemic extraction bugs (wrong field parsed, etc.) that
aggregate reconciliation might miss.

## Risks

- **CAL-ACCESS schema drift:** column names sometimes change between
  dumps. Verify against documentation before assuming.
- **IE attribution edge cases:** committees that support multiple props
  in one filing; donor-of-donor chains in major-donor filings; gray-area
  cases (e.g. "issue advocacy" that doesn't legally qualify as IE but
  influences the vote).
- **Headline number shift will surprise users.** If the homepage shows
  total receipts go from $3.24B to ~$6-8B, that's a major perceptual
  change. We should ship the methodology note + breakdown together so
  users can see what shifted and why.
- **We may not match Ballotpedia exactly.** Their methodology may
  include things we still don't capture (slate mailers, contributions
  through 527 organizations, out-of-state spending). The ±10% target is
  the realistic ceiling without months of iteration.
- **Backward compatibility:** every downstream consumer of v2
  (operations.py, generate_insights, generator.py, briefing pipeline,
  API) needs a WHERE-clause review. Some queries that currently sum
  `total_receipts` may inadvertently start summing all receipt types
  → numbers shift unexpectedly. Mitigated by single-table-with-
  discriminator design + explicit migration.

## Effort estimate

| Phase | Effort | Cumulative |
|---|---|---|
| 0 — Source data acquisition | 1–2 hours | 1–2 |
| 1 — Schema design + Codex plan review | 3–4 hours | 4–6 |
| 2 — LOAN_CD ingestion + verify | 2–4 hours | 6–10 |
| 3 — In-kind ingestion + verify | 4–6 hours | 10–16 |
| 4 — IE ingestion + verify (biggest) | 1–2 days | 18–32 |
| 5 — Frontend integration | 4–6 hours | 22–38 |
| 6 — Final verification + docs | 2–3 hours | 24–41 |

**Total: ~3–5 days of focused work over 1–2 weeks.**

Phase 4 is the big rock; everything else compounds onto Phase 4's
foundation.

## Next steps (this session)

1. User reviews this plan and answers the 4 key decisions
2. Codex review pass on the plan with user's decisions baked in
3. Begin Phase 0 (source data acquisition)

Nothing irreversible happens until decisions are made and Codex has
weighed in.
