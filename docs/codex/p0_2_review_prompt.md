# Codex review request: P0.2, P0.2b and P2.0 (R7)

**Branch:** `phase0-election-status` (local, not pushed). The coordinator cherry-picked
agent A's commits onto it. Hashes on this branch: P0.2 `6fe4f565`, P0.2b `d2fc694d`,
P2.0 `49896ca5`, this prompt `e0db6d60`. The hashes in the headings below are the
original worktree hashes. Review the code with
`git diff 734c47d8 49896ca5 -- scraper/` (the commits in between change docs only).
**Context:** checklist sections P0.2b, P0.2 and the P2.0 outline row;
[P0.1 re-review, finding R7](p0_1_status_review_response.md#new-defect-r7--p3-checker-rejects-a-supported-unknown-state).

## What changed

### P0.2: history list jurisdiction label (`09fbdc17`)

The "Explore the historical comparison" list on the 40 county measures with history called
every CEDA record "San Bernardino County" or "San Mateo County". Most are city, school or
district measures. CEDA rows keep only the source's numeric `JUR` code until Phase 1b restores
`PLACE`, so `history_jurisdiction_label()` in `scraper/src/website/local_measure_context.py`
says only what that code supports:

| Stored `jurisdiction` | Label |
|---|---|
| `1` | County or special district measure |
| `2` | City measure |
| `3` | School or college district measure |
| empty, missing or another code | Local measure |
| a place name (none today) | shown as stored |

**Why code 1 is not "County measure".** In the raw 2015 CEDA measures file on disk
(`scraper/data/raw/ceda_data_2015.xlsx`), `JUR=1` covers 34 rows, 19 of them flagged `CSD=1`:
community services districts and county service areas (Helendale CSD, CSA #70). The five
code-1 records shown today include a LAFCO order (2768), Caltrain's Measure RR (3222) and the
Morongo Valley fire assessment (4694). "County measure" would be false for those.
**Why "school or college".** In 2015, none of the 32 code-3 place names contains "College".
Other years were not checked against raw files, and California community college districts
are not school districts by name. The wider label is true either way.
**Why no county.** The list's lead sentence already names the county, and dropping it keeps
the label short at 320px.

Raw rows are not modified. The renderer (`county_content.render_history`) is unchanged; it
prints `year · label · designation`.

### P0.2b: "• Pending" on historical explorer cards (`46afcbca`)

Igor approved "Result unknown" on November 11. Surfaces checked in `generator.py` for rows with
no outcome that are neither withdrawn nor date-driven, e.g. the 48 CEDA 2011 rows (56 such
rows in all):

| Surface | Before | After |
|---|---|---|
| Card badge (`createCard`) | `• Pending` | `• Result unknown` |
| Modal badge (`viewMeasure`) | `• Unknown` | `• Result unknown` |
| List row (`createListItem`) | `?` | unchanged |
| "Pending/Unknown" filter chip | label for an outcome filter | unchanged |
| Insights "How they ended", `Pending` bucket | `active_measures - decided_measures` | unchanged |

Both new strings use `getElectionStatusLabel('unknown')`, the shared `STATUS_LABELS` value.
The chip and the Insights bucket group date-driven and unknown rows together, so they are not
the same concept and were left alone. The badge keeps its `badge-pending` CSS class; only the
text changed. Explorer only: no static page or JSON field changes.

### P2.0: browser checker R7 (`92bcca4c`)

`check_election_status_browser.py` now classifies current rows from withdrawal, outcome and
stored-vote evidence (`has_recorded_votes`, `election_status`), never from the field under
test (`depends_on_date`, `classify_current`):

- **Date-dependent rows** (not withdrawn, no outcome, no stored votes) must carry a calendar
  status. A missing one still fails, and the row is not dropped silently.
- **Resolved rows** must carry no calendar status and no results link. They must read exactly
  `✓ Passed`, `✗ Failed` or `• Result unknown` on the card and the rendered statewide card;
  `✓`, `✗` or `?` on the list row; and the same label in the modal, with no calendar label,
  results link or pending note. Statewide resolved cards must keep their badge through the
  same-page transition.
- **Coverage** is unchanged: rows are still chosen by `upcoming_scope` and checked against
  `--expect-count`. The report adds `calendar_measures` and `resolved_measures`.
- **Local section link:** expected from the county's linked calendar rows, so a county whose
  rows are all resolved works.

## Evidence

All scratch output: `C:\Users\igorg\AppData\Local\Temp\claude\3706ee781272b6b6\d90ea535-f05d-4a6f-929d-dbc27318d103\scratchpad\agent-a\`.

**Tests**, run from `scraper/`:

- `python -m pytest tests/test_election_status.py tests/test_local_measure_context.py tests/test_county_content.py -q -p no:cacheprovider --basetemp=.pytest-tmp/agent-a-targeted`
  gives **126 passed**. That is 86 election-status tests (81 + 2 for P0.2b + 3 for R7),
  23 local-context tests (+10) and 17 county-content tests (+1).
- Full suite: **709 passed, 1 skipped, 2 failed, 17 errors** (16 more tests than the 694
  baseline). The `test_models` failure and the 17 `test_database`/`test_deduplication`
  errors are the known baseline.
- The second failure, `test_registrar_smc::test_fixture_sidecars_match_raw_bytes`, is a
  checkout artifact, not a code change. In this fresh worktree,
  `git ls-files --eol` shows the two SMC HTML fixtures as `i/lf w/crlf`, because
  `core.autocrlf=true` and `.gitattributes` has no `-text` rule for
  `scraper/tests/fixtures/registrar/smc/`. The size gap, 279,682 vs 278,039 bytes, is one CR
  per line. No commit here touches those files.

**Scratch strict build.** The generator ran from the worktree against a SQLite backup of the
production DB (opened `mode=ro`), with `--force --strict --as-of 2026-11-11`. The run used
offline `all-MiniLM-L6-v2` and copies of the finance v2/v3 DBs, which are gitignored and
absent from a fresh worktree. Output is in `candidate-a-2026-11-11\site`.

**Compared with the coordinator's `candidate-p0s-2026-11-11` (built from `f122cf05`),**
report `compare-vs-p0s.json`:

- **Files:** 12,376 in each, none added or removed. Only `index.html`, `measures-data.json`
  and **40 measure pages** changed: 12418-12449, 12451-12453, 12458 and 12463-12466. The other
  **12,332 measure pages** are byte-identical, and so are `sitemap.xml` and
  `use-calballot/index.html`.
- **Measure pages:** all 40 differ only in the history-link labels, 200 links, 5 per page
  (`page-label-only.json`). Before: San Bernardino County 100 and San Mateo County 100.
  After: Local measure 171, City measure 18, County or special district measure 10, School or
  college district measure 1. The 60 distinct records shown are 48 with no code, six code 2,
  five code 1 and one code 3.
- **JSON:** same 12,372 IDs. Changed fields:
  - `county_sections` on 40 rows; label-only, checked by normalizing the labels.
  - `local_historical_context` on 40 rows; the only subfield is `records[].jurisdiction`
    (200).
  - `last_seen_at` on 129 rows. These are build timestamps (07:49 vs 08:16 on November 11),
    the known regenerating field.
- **`index.html`:** three hunks: the `measures-data.json?v=` cache key, the card fallback
  and the modal badge.

**Browser checks:**

- `check_election_status_browser.py --expect-count 63` on the candidate at the real clock
  (reader date 2026-11-11): **0 failures**. All 63 rows read Results pending at
  1440/390/320px, with no page errors (`browser-candidate-now\`).
- `check_county_content_browser.py`: 49 reviewed measures at 3 widths, no errors, exit 0
  (`browser-county-content\`).

**R7 regression.** `scripts\make_mixed_site.py` builds a synthetic copy of the candidate JSON,
in `mixed-site\`. It edits three rows and removes their calendar fields, as attachment would:

- 12420 (local SB): `yes_votes=123, passed=None`
- 12477 (statewide): `passed=1`
- 12421 (local SB): `passed=0`

The real strict `attach_election_status()` attaches 0 of these rows, and `election_status()`
returns unknown, passed and failed.

| Run | Exit | Failures |
|---|---|---|
| New checker, mixed site | 0 | none; 60 calendar rows plus resolved unknown 1, passed 1, failed 1 |
| New checker, mixed site, `--clock 2026-11-11T23:59:00-08:00 --transition-to 2026-11-12T00:01:00-08:00` | 0 | none |
| Checker from `f122cf05`, mixed site | 1 | `current row has no calendar status (None)` for 12420, 12421 and 12477 (R7 reproduced) |
| New checker, mixed site with 12422's `election_status` deleted (`mixed-site-dropped\`) | 1 | `12422: current row has no calendar status (None)`, plus the San Bernardino local section link count at 3 widths |

The section-link failures in the last row are real. The explorer takes the county's first
row with `official_results`, now 12422 without a calendar status, so the county link
disappears.

**Visual checks** (`screenshots\`, plus `report.json`):

- County modal 12437 with the history list open, at 1440 and 390px. All four labels show,
  with no overflow and no page errors.
- Historical card 6103 (Alameda Measure A, 2011, stored votes, `passed` NULL) at 1440 and
  390px. The rendered badge reads `• RESULT UNKNOWN` (CSS uppercases it), and the modal badge
  reads `• Result unknown`.

**Protected files:** hashes are unchanged before and after. Production DB `ef1359e4…`, root
`index.html` `b0257999…`, root `measures-data.json` `1921e5d4…`.

## Open questions

1. **Labels.** Is "County or special district measure" right for code 1, given the 2015
   evidence? Is "School or college district measure" too cautious for code 3? Should a label
   name the county, e.g. "City measure in San Mateo County"?
2. **Modal badge.** P0.2b also changed the modal's `• Unknown` to `• Result unknown`. Igor's
   approval named "Pending". Is the wider change acceptable?
3. **Left unchanged:** the Insights `Pending` bucket (80 rows in the committed
   `insights.json` snapshot, current and unknown together), the "Pending/Unknown" chip and the
   list row's `?`. Should any of them change before P0.3?
4. **Badge style.** Unknown rows keep the gold `badge-pending` class. Its `::before` dot plus
   the `•` glyph render as "• • RESULT UNKNOWN", the same doubling the old "• • PENDING" had.
   Static pages use grey for unknown. Should these rows switch to `badge-neutral` and drop the
   glyph? That is a visual change, so it was not made here.
5. **Pre-existing, not fixed.** For historical CEDA rows, the modal's jurisdiction line and
   the static pages' `jurisdiction_label()` put the raw code in front of the county: the live
   `measures/3154.html` reads "2, San Bernardino County". This could affect up to 9,243 coded
   CEDA rows, so the fix would change thousands of pages. It belongs with P1b, or a separately
   scoped follow-up.
6. **R7 checker:** a resolved row that still carries `election_status` or `official_results`
   is reported as a failure, as stale data. Is that the intended contract?

## Constraints

As before: review only, scratch builds outside the repo, production database read-only
through the SQLite backup API, no live link checks, no push. A fresh worktree lacks the
gitignored finance DBs (`scraper/data/finance/finance_statewide_v2.db`, `_v3.db`); a strict
build needs copies of them.

## Please return

Write `docs/codex/p0_2_review_response.md` with:
- a verdict per item (P0.2, P0.2b, P2.0): **ready**, **ready with changes** or **not ready**,
  with evidence;
- answers to the open questions;
- any new defects, ranked.

Commit only that file. The coordinator updates the checklist.
