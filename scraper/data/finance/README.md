# Campaign Finance Data

## Live database

`finance_statewide_v2.db` — the production finance DB. Year-scoped by
`finance_campaign_id` (e.g. `PROP_16_2020`). Schema documented in
`scraper/src/finance/schema.py`. Five tables:

- `finance_campaign` — crosswalk: `(prop_num, election_year)` → `measure_db_id`
- `finance_summary` — per-`(campaign, stance)` total receipts, committees, top-5 share, HHI
- `finance_top_donors` — per-`(campaign, stance, donor)` aggregated amounts
- `finance_timeline_weekly` — per-`(campaign, stance, week_start)` weekly + cumulative
- `finance_row_quarantine` — every source row rejected by the rebuild gates, with reason code

`finance_statewide.db` (no `_v2`) — the old contaminated DB. Audit-only;
nothing live reads it. Referenced as `FINANCE_DB_LEGACY_PATH` in `schema.py`.

## Build pipeline

```bash
# 1. Source CSV must already exist:
#    data/finance/calaccess_raw/ballot_measure_receipts_clean.csv
#    (extracted from CAL-ACCESS dumps; not regenerated here)

# 2. Build the (prop_num, election_year) -> measure_db_id crosswalk
python -m scripts.build_finance_crosswalk
#    -> writes data/finance/finance_crosswalk.csv

# 3. Rebuild the v2 DB from source CSV + crosswalk
python -m scripts.rebuild_finance_db
#    -> writes data/finance/finance_statewide_v2.db
```

Both scripts are idempotent. Re-run any time the source CSV refreshes.

`scripts/build_statewide_prop_finance_db.py` is the deprecated v1 ETL —
it had the cross-cycle contamination bug. It will refuse to run.

## Rebuild rules (Codex-reviewed 2026-05-04)

The rebuild quarantines any row that fails one of these gates:

| Gate | What it does |
|---|---|
| `non_numeric_prop_num` | Filters recall petitions, circulating initiatives, and import garbage in `prop_num` |
| `no_year` / `bad_year` / `out_of_range_year` | Drops rows without a usable election year (or with placeholder years like 1900-01-01) |
| `unparseable_date` / `before_1995` | Drops rows without a parseable transaction date or with placeholder pre-1995 dates |
| `no_campaign` | Drops rows whose `(prop_num, year)` doesn't match a measure in the crosswalk |
| `date_off_cycle` | Drops rows where `abs(txn_year - election_year) > 1` (Codex's row-level hygiene rule) |
| `unknown_stance` | Drops rows where `stance` isn't `support`/`oppose` AND committee-name recovery couldn't infer one |
| `non_positive_amount` | Drops refunds and zero-amount rows (we aggregate gross receipts) |
| `exact_duplicate` | Drops exact-row duplicates after acceptance (53.5% of source CSV rows are duplicates) |

Stance recovery: when source `stance` is empty, the rebuild infers from
committee name via regex patterns ("STOP", "DEFEAT", "YES ON", "VOTE NO")
plus an explicit override table for high-dollar committees that don't quote
the prop number (see `COMMITTEE_STANCE_OVERRIDES` in `rebuild_finance_db.py`).

Donor canonicalization: a hand-curated regex map collapses common
high-value donor name variants (CTA, AFSCME, AFT, R.J. Reynolds, San
Manuel, Lyft, DraftKings, FanDuel, Cal Apartment Assn, Philip Morris).
See `DONOR_ALIAS_PATTERNS` in `rebuild_finance_db.py`. No fuzzy matching.

## Current state (2026-05-12)

- **181 matched campaigns** (1999–2025) covering **$3.24B** in retained receipts
- **1,589,936 source rows quarantined** with reason codes (mostly recall money, empty-year rows, and exact duplicates)
- 105 / 105 two-stance campaigns return both support + oppose donors
- All five named sentinels (PROP_16_2020, PROP_22_2020, PROP_32_2024, PROP_6_2024, PROP_50_2025) at 100% in-target-year activity

See `plans/finance-rebuild-verification.md` for the full verification report
and `plans/finance-panel-redesign.md` for the rebuild story.

## Scope and methodology

**What the receipt totals include:** itemized monetary contributions
recorded in CAL-ACCESS `RCPT_CD` for filings tagged with the prop's
`BAL_NUM` / `BAL_NAME`, after cross-filing dedupe.

**What they do NOT include:**

- Non-monetary / in-kind contributions (Form 460 Schedule C)
- Loans received (Form 460 Schedule B / `LOAN_CD`)
- Independent expenditures by major donors (Form 461 / `S496_CD`) —
  e.g. if a sportsbook paid an ad agency directly to support a prop,
  bypassing the official Yes-on-X PAC, that spending is not captured
- Receipts to side-committees that didn't tag their filings with the
  prop's `BAL_NUM` (a CAL-ACCESS data-entry gap; Prop 27 (2022) is a
  known example — Ballotpedia lists two oppose committees, we have one)

**Why our totals differ from press citations:** common public-reporting
figures (Ballotpedia, OpenSecrets news posts, CalMatters explainers)
combine all of the above scopes, often using committee-reported cumulative
totals from Form 460 cover sheets rather than itemized line sums. Our
numbers are the strictest defensible subset: verifiable monetary inflow
to the official committees, de-duplicated across cross-filing repetition.
Expect our totals to run **roughly 40–60% of headline figures** for
high-IE-spending props like PROP_22_2020 and PROP_27_2022.

**Cross-filing dedupe (Gate 7 in rebuild_finance_db.py):** the same
Schedule A transaction is legitimately reported across multiple distinct
CAL-ACCESS `FILING_ID`s — Form 497 24-hour late filing, Form 460
pre-election, Form 460 semi-annual, Form 460 annual closer all carry the
same itemized contributions for transactions inside their reporting
window. `extract_calaccess_finance.py` filters to latest amendment **per
FILING_ID** but does not collapse across FILING_IDs. The rebuild's Gate 7
does that work, keyed on `(campaign, stance, date, amount,
canonicalize_donor(donor_raw), donor_type, committee)`. The canonical-
donor key (2026-05-12 change) catches casing-variant duplicates
("D/B/A" vs "d/b/a") that the prior raw-name key missed.
