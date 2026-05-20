# Campaign Finance Data

## Current state (2026-05-20, post-Phase 5)

Combined scope: **monetary contributions + loans + in-kind +
independent expenditures** across **181 statewide propositions**
totaling **$5,750,344,165.78** of reportable money. Sourced from two
SQLite databases that the read layer stitches together — the v2 db
owns monetary contributions, the v3 db owns the expanded scope. UI
consumers see one coherent total; the v2/v3 split is hidden behind
`FinanceDatabase.get_combined_*` methods.

Recent headline shift: the v2-only era reported $3.24B as the
"total receipts" — the Phase 5 atomic flip (2026-05-19,
commit `bec2abe`) added v3's $2.51B of non-monetary spending,
bringing the combined total to $5.75B. The methodology note in the
Insights panel documents this shift; numerical sentinels are
preserved.

`better_funded_win_rate` is **65.2%** (v2-only was also 65% — IE
money tends to follow monetary lead in most fights).

## Live databases

### `finance_statewide_v2.db`

The original production finance DB. Year-scoped by
`finance_campaign_id` (e.g. `PROP_16_2020`). Schema documented in
`scraper/src/finance/schema.py`. Five tables:

- `finance_campaign` — crosswalk: `(prop_num, election_year)` → `measure_db_id`
- `finance_summary` — per-`(campaign, stance)` total receipts, committees, top-5 share, HHI
- `finance_top_donors` — per-`(campaign, stance, donor)` aggregated amounts (capped at top-20)
- `finance_timeline_weekly` — per-`(campaign, stance, week_start)` weekly + cumulative
- `finance_row_quarantine` — every source row rejected by the rebuild gates, with reason code

### `finance_statewide_v3.db`

Phase 4 (2026-05-15) added the expanded-scope DB. Carries
**loans + in-kind + independent expenditures** as a single
`finance_flow_v3` fact table — no monetary contributions yet (those
still live in v2 only; a future "v3 monetary ingest" sub-phase could
collapse the split). Schema:

- `finance_flow_v3` — fact table; 912K rows total, 47,942 accepted
  (rest are quarantine or dedup-loser, kept for audit)
- `finance_summary_by_type`, `finance_top_donors_by_type`,
  `finance_timeline_weekly_by_type` — derived tables, rebuilt by
  `scripts/v3/rebuild_derived.py`
- `finance_summary_total`, `finance_top_donors_total`,
  `finance_timeline_weekly_total` — SQL views collapsing the
  receipt-type dimension; computed at query time from the flow table

Read-layer note: the app reads v3 by aggregating `finance_flow_v3`
directly (not the derived tables/views) for single-source-of-truth
correctness — the views' `MAX(measure_db_id)` per campaign could
otherwise collapse cross-measure-spanning campaigns to one arbitrary
measure. The derived tables exist as audit artifacts + potential
fast-path re-introduction.

`finance_statewide.db` (no `_v2`) — the original v1 contaminated DB.
Audit-only; nothing live reads it. Referenced as
`FINANCE_DB_LEGACY_PATH` in `schema.py`.

## Build pipeline

### v2 (monetary)

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

### v3 (loans + in-kind + IE)

From the repo root:

```bash
# 1. Initialize the v3 db schema (idempotent — won't clobber data)
python scripts/v3/init_db.py

# 2. Ingest the three scopes (each idempotent on the flow PK):
python scripts/v3/ingest_loans.py
python scripts/v3/ingest_inkind.py
python scripts/v3/ingest_ies.py

# 3. Post-ingest cross-source dedup pass
python scripts/v3/dedup_ies.py

# 4. Rebuild derived tables (by_type tables; views recompute at query time)
python scripts/v3/rebuild_derived.py
```

v3 inherits v2's `(prop_num, election_year) → measure_db_id`
crosswalk, so the v2 build must run first.

## v2 rebuild rules (Codex-reviewed 2026-05-04)

The v2 rebuild quarantines any row that fails one of these gates:

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

## v3 attribution layer (14 Codex rounds, 2026-05-15)

v3 ingests are harder than v2's because the source rows often don't
have a clean `BAL_NUM`/`BAL_NAME` — IE filings in particular are
filed by donors paying vendors directly, with measure attribution
inferred from row-level fields, cover-sheet fields, or curated
committee overrides. The resolver in `scripts/v3/resolver.py` runs a
conservative attribution pass with these guards (each introduced
across 14 rounds of Codex review against real-data edge cases):

- **AG queue IDs rejected** (`19-0026`, `2024-V1`, etc.): not
  proposition numbers, never greedy-matched.
- **Multi-prop separators rejected** (`26/27`, `RM/4`, `11/2020`,
  digit-flanked `AND`): ambiguous targets quarantine.
- **Regional / local measure phrases rejected** (`Regional Measure
  3`, `City Measure A`, `Yes on Measure B`): non-statewide signal.
- **Bare local letter measures rejected** (`Measure A`, `Measure C`
  at start-of-string): local-ballot syntax.
- **Field-specific ambiguity helpers**: `has_ambiguous_bal_num`
  (strict, for BAL_NUM) vs `has_ambiguous_bal_name` (semantic, for
  BAL_NAME) — different fields carry different signal weights.
- **Tracking-ID rejection** (year-prefixed `2024-V1` etc.).

When attribution fails, the row is quarantined with a `reason` code
(`ambiguous_multi_prop`, `filer_name_no_prop`, etc.). Accepted rows
get an `attribution_method` value: `row_fields`, `cover_sheet`,
`filer_name_explicit`, `single_crosswalk_candidate_winddown`, or
`manual_override`.

### Post-ingest dedup

The same economic transaction can appear across multiple CAL-ACCESS
forms (S496 24-hour notice + Form 461 scheduled report). `dedup_ies.py`
runs a post-ingest pass keyed on an `economic_fingerprint` that
includes payee + target campaign + stance + amount + date. When
multiple rows match the fingerprint, source-table priority resolves
the winner (F461P5 > F465P3 > S496). Losers retain their original
attribution for audit provenance but get `quarantine_reason =
'duplicate_economic_fingerprint'` so aggregation queries
(`WHERE quarantine_reason IS NULL`) skip them. Result: $36.27M of
IE-side double-counting eliminated, dedup invariant verified by
`reconcile_ies.py` to the penny.

## Combined read layer

UI consumers call `FinanceDatabase.get_combined_*` methods that
internally stitch v2 monetary onto v3 non-monetary per measure:

- `get_combined_summary(measure_db_id)` → per-stance totals with
  `monetary_amount` / `non_monetary_amount` split, `n_committees`,
  `top5_share`, `hhi`
- `get_combined_breakdown_by_type(measure_db_id)` → 4 rows per
  stance: `monetary_contribution`, `loan`, `in_kind`,
  `independent_expenditure`
- `get_combined_top_donors(measure_db_id, *, stance, limit)` →
  per-stance top-N with `flow_types` union; donor aliases applied
- `get_combined_timeline(measure_db_id)` → weekly + cumulative
  merge per stance
- `get_combined_calendar_year_receipts()` → cross-measure spending
  arc; `n_measures` is the true union of measure_db_ids per year

v3-only methods (`get_finance_summary_total`, etc.) exist for callers
that want only the v3 slice. The atomic UI flip in step 2b moved
every consumer surface (modal, briefing pipeline, insights generator,
API endpoints) to the combined methods.

### Cross-source donor aliases

v2 and v3 canonicalize donor names independently, so the same legal
entity sometimes appears under two slightly different canon strings
(comma diffs, D/B/A wrappings, `RESPONSIBLE OFFICER:...` suffixes).
`src/finance/donor_aliases.py` carries a curated map applied at
combined-merge time only — underlying v2/v3 storage canonicalization
stays independent so source-table reconciliation remains exact.

Current alias entries cover Uber, Postmates, FanDuel, FBG, Penn
Interactive, Pala Band, AIMCO, Instacart/Maplebear. **Generic**
"and affiliated entities" suffix merging is intentionally NOT done,
but specific same-filer cases where the entity is clearly identical
are merged (AIMCO's three formatting variants are curated; Pala Band's
casino-name suffix is curated). SEIU Locals / UFCW Locals stay
distinct (different filing entities, even though parent unions are
related).

Every alias canonical output that has a meaningful sector is also
listed in `donor_sectors.py` so the sector-chip lookup survives the
merge. A round-trip invariant test (`test_all_donor_alias_canonicals_round_trip`)
catches future aliases that miss a sectors entry.

## Methodology notes (Codex round-4/5 calibration)

Four important caveats for interpreting the combined numbers:

1. **Headline totals are exact** under current methodology.
   $5,750,344,165.78 across 181 measures reconciles to v2 monetary
   ($3,240,293,198.54) + v3 (loans+in-kind+IE, $2,510,050,967.24)
   to the penny. Both calendar-year and annual-receipts lenses sum
   to the same total.

2. **Donor lists are display/canonicalization-limited.**
   Cross-source aliases are curated (see `donor_aliases.py`).
   Underlying v2/v3 storage canonicalization runs independently and
   may still split entities not yet in the alias map. The current
   curation covers the visible marquee/top-N splits; lower-traffic
   measures may surface new splits that need adding.

3. **Concentration metrics are unavailable when monetary contributes.**
   v2's `finance_top_donors` table is materialized at top-20 per
   (campaign, stance) — tail donors below the cap are dropped. That
   means HHI / top5_share computed against the merged combined
   donor list would systematically underestimate concentration on
   any measure where v2 monetary is non-trivial. `get_combined_summary`
   returns `None` for `top5_share` / `hhi` on any row where
   `monetary_amount > 0`. v3-only rows (monetary = 0) pass through
   v3's exact concentration metrics, since the v3 donor list is
   complete. Resolution path: a future v2.1 rebuild that
   materializes the full v2 monetary donor distribution, OR a v3
   monetary ingest sub-phase that lets the combined methods collapse
   into their v3 counterparts.

4. **Calendar-year `n_measures` is a true union** of measure_db_ids
   active in each year, queried from both v2's
   `finance_timeline_weekly` and v3's `finance_flow_v3` source
   tables. Prior implementation used `max(v2_count, v3_count)` which
   undercounted in 7 years where v2 and v3 had disjoint measure
   sets (Codex round-4 #3 fix, commit `a1582c8`).

## Scope and methodology

**What the receipt totals include (post-Phase 5 combined view):**

1. **Monetary contributions** (v2): itemized cash contributions
   recorded in CAL-ACCESS `RCPT_CD` Schedule A for filings tagged
   with the prop's `BAL_NUM` / `BAL_NAME`, after cross-filing
   dedupe.
2. **Loans** (v3): committee loan receipts from CAL-ACCESS
   `LOAN_CD` Form 460 Schedule B1.
3. **In-kind contributions** (v3): non-monetary contributions from
   CAL-ACCESS `RCPT_CD` Schedule C (goods, services, polling).
4. **Independent expenditures** (v3): money spent directly by
   donors (often bypassing official committees) on advocacy for or
   against a measure — `EXPN_CD` F461P5/F465P3 and `S496_CD` F496
   24-hour notice filings.

**What they do NOT include:**

- Receipts to side-committees that didn't tag their filings with the
  prop's `BAL_NUM` (a CAL-ACCESS data-entry gap; Prop 27 (2022) is a
  known example — Ballotpedia lists two oppose committees, we have one)
- Schedule E party-passthrough expenditures (party committees that
  spent generally and indirectly aided a measure)
- Local-ballot measure finance (the dbs are statewide-only)

**Why our totals may still differ from press citations:** common
public-reporting figures (Ballotpedia, OpenSecrets, CalMatters)
sometimes use committee-reported cumulative totals from Form 460
cover sheets rather than itemized line sums, or include
side-committee untagged spending we can't attribute. Post-Phase 5
the gap is much smaller than the v2-only era (where our totals ran
40–60% of press figures); we now approximate or sometimes match
press citations for high-IE props like PROP_22_2020 and PROP_27_2022.

**Cross-filing dedupe (Gate 7 in `rebuild_finance_db.py`):** the same
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

## Verification framework

Four layers, each runnable independently:

| Layer | Script | What it verifies |
|---|---|---|
| 0 — Unit tests | `pytest scraper/tests/test_finance_db.py scraper/tests/test_finance_db_v3.py scraper/tests/test_finance_crosswalk.py` | 187 hermetic tests (114 v2 FinanceDatabase + 60 v3 + 13 crosswalk) |
| 1 — v2 baseline | `python scripts/v3/verify_layer1.py` | v3 work hasn't touched v2 data (8 checks: row counts, value match to penny, self-hash) |
| 2 — Source reconcile | `reconcile_loans.py`, `reconcile_inkind.py`, `reconcile_ies.py` | Each v3 ingest reconciles against direct source SUM to the penny |
| 3 — Trace tests | `verify_traces.py` | 10 source-row-anchored fixtures (pin specific transactions to expected attribution) |
| G — Phase G integrity | `python scripts/v3/verify_phase_g.py` | 9 structural invariants for the v3 + combined read layer (alias merge, concentration-None policy, n_committees union, etc.) |

All layers green at commit `1a42413` (Phase 6 verification).

See `plans/finance-rebuild-verification.md` for the full Phase A–F
verification plan and the Phase G appendix.
