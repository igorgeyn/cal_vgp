Written by a Claude reviewer agent in place of Codex on 2026-11-12, at `phase0-election-status` HEAD `689cd1ddf6ed65b374575d13ffb8762edda7940b`.

# P0.2, P0.2b and P2.0 (R7) review response

Reviewed the code diff `734c47d8..49896ca5 -- scraper/` (six files: checker, generator,
`local_measure_context.py`, three test files). `f122cf05..734c47d8` changes only
`scraper/data/census/county_sources_2026.json`, so the coordinator's `candidate-p0s` build is a
valid baseline for the agent-A candidate.

| Item | Verdict |
|---|---|
| **P0.2** history-list jurisdiction label | **Ready with changes.** The labels are correct and better supported than the prompt claims. The preview line under the same links still shows the county on 171 of 200 links (N1). |
| **P0.2b** "Result unknown" badge | **Ready.** Both badges changed, nothing else did, and the refresh path leaves unknown rows alone. |
| **P2.0** checker R7 | **Ready with changes.** R7 is closed for the per-width checks, which I reproduced on a harsher mixed site. `--transition-to` crashes when no statewide row depends on the date (N2). That is the state result import will produce. |

All builder claims I rechecked reproduce exactly (see the last section). Nothing below is a
production-rendering error in the real 63-row candidate.

## New defects, ranked

### N1 — P3: the preview line under each history link still names the county

**Location:** `scraper/src/website/county_content.py:137-142` (`render_history` prints
`row['title']` under each link); `scraper/src/parsers/ceda.py:334` (the loader writes
`title = f"{county} Measure {measure_letter}"` when CEDA has no ballot question).

**Evidence:** On all 40 changed pages, every one of the 171 "Local measure" links has a preview
that is exactly the title the loader wrote, for example:

```text
2024 · Local measure · Measure U — Failed
SAN BERNARDINO Measure U
```

This shows in the builder's own screenshot,
`agent-a\screenshots\390-county-modal-12437-history-element.png`. I counted these with a regex
over `county_sections` in the candidate JSON: 171 of 171 "Local measure" items match
`(SAN BERNARDINO|SAN MATEO) Measure [A-Z]+`, and 0 of the 29 coded items do. The label now says
only what the code supports. But the line under it puts the county name back, in capitals, as if
it were the measure's name. "SAN MATEO Measure B" also reads as the City of San Mateo. The text is
not a new regression; it was there before. But it undoes the point of P0.2 on 86% of the links,
in the same list item that P0.2 fixed.

**Fix:** In `render_history` (or when building `records`), drop the preview when the title is the
placeholder the loader made: it equals `f"{county} Measure {letter}"`, ignoring case and
whitespace, or it adds nothing beyond the designation. Do it in this change. The same 40 pages
already change, so fixing it now avoids a second update to them. Add a test with a placeholder
title. Do not edit the stored titles; that belongs to P1b, when `PLACE` is restored.

### N2 — P3: `--transition-to` crashes when no statewide row depends on the date

**Location:** `scraper/scripts/check_election_status_browser.py:279-280`.

```python
sample = next((m for m in current if m['upcoming_scope'] == 'statewide' and m.get('official_results')),
              next(m for m in current if m['upcoming_scope'] == 'statewide'))
```

`current` now means the calendar rows only. Python evaluates the inner `next()` eagerly, and it
has no default. So when every statewide row is resolved, the checker raises `StopIteration`
whether or not the outer generator would have found a row.

**Reproduction:** I made a mixed site from the agent-A candidate
(`review-p02\scripts\make_review_mixed.py`). It resolves all 14 statewide rows (5 passed,
5 failed, 4 unknown from `percent_no=0` alone) and all 29 San Mateo rows (10/10/9, the unknowns
from `yes_votes=0`). San Bernardino's 20 rows stay date-dependent. Each current row was passed
back through the real strict `attach_election_status(as_of=2026-11-11)`.

- `--clock 2026-11-11T12:00:00-08:00 --expect-count 63`: exit **0**, **0 failures**. There are
  20 calendar rows and 43 resolved (15 passed, 15 failed, 13 unknown) at 1440, 390 and 320px. The
  San Mateo local section link count is 0 and the statewide section link count is 0, both
  correct.
- Same site, `--clock 2026-11-11T23:59:00-08:00 --transition-to 2026-11-12T00:01:00-08:00`: exit
  **1** with a `StopIteration` traceback at line 280 and no `report.json`.

The crash fails closed, but it is an opaque traceback, not a report. It also blocks the
same-page refresh check, which still matters for local rows and resolved statewide badges.
Result import will likely bring in statewide outcomes before county ones, so this is the next
real dataset shape.

**Fix:** Pick the modal sample from any calendar row, statewide first, with a `None` default. If
there is none, skip the open-modal assertions but still run the hero checks for resolved rows
after the transition. Add a regression test with every statewide row resolved, in transition mode.

### N3 — P4, latent: the explorer picks the local section results link by a different rule than the statewide one

**Location:** `scraper/src/website/generator.py:11482` uses
`selectedGroup.measures.find(m => m.official_results)`. The statewide note, at `:11287`, uses
`heroMeasures.find(m => officialResultsLinkHtml(m))`.

If the county's first row with a link is not showing one, the local note shows no link even when
another row in the county would. The builder's `mixed-site-dropped` run shows this: deleting
12422's `election_status` removes the San Bernardino link at all three widths. Strict attachment
removes `official_results` from every row without a calendar status, so real builds cannot reach
this state, and the checker correctly fails if one does. Use the statewide predicate in both
places when this code is next touched. This does not block anything.

### N4 — P4, repo hygiene (outside the three items): SMC HTML fixtures lack a `-text` rule

`.gitattributes` marks the statewide and document-role fixture folders `-text`, but not
`scraper/tests/fixtures/registrar/smc/`. With `core.autocrlf=true` (set here), a fresh checkout
turns the two HTML fixtures to CRLF, and `test_fixture_sidecars_match_raw_bytes` fails. In this
main checkout `git ls-files --eol` shows them as `w/lf`, so I did not reproduce the failure
itself. I confirmed the missing rule and the autocrlf setting. Add
`/scraper/tests/fixtures/registrar/smc/*.html -text` (and the SB fixtures if they are in the same
position). Otherwise a fresh Windows clone has a known-red test that hides real ones.

## Answers to the open questions

1. **Labels.** Keep both. I widened the evidence from the 2015 file to every CEDA measures sheet
   on disk that openpyxl can read:

   | Measures sheet | Code 1: rows / CSD-CSA-district names | Code 3: rows / "Community College" names |
   |---|---|---|
   | 2011 | 20 / 10 | 47 / 1 (San Mateo Community College) |
   | 2012 | 76 / 15 | 206 / 19 |
   | 2013 | 12 / 7 | 35 / 0 |
   | 2014 | 84 / 16 | 208 / 23 |
   | 2015 | 34 / 19 | 32 / 0 |
   | 2022 | 93 / 19 | 160 / 11 |
   | 2023 | 7 / 7 | 7 / 0 |
   | 2024 | 107 / 15 | 398 / 24 |

   Code 1 includes special districts every year, so "County or special district measure" is
   correct. The five code-1 records shown today confirm it: two San Bernardino charter measures
   (3145, 3146), a LAFCO order (2768), Caltrain's RR (3222) and the Morongo Valley fire assessment
   (4694). Code 3 includes community college districts in most years, so "School or college
   district measure" is not too cautious: "School district measure" would be false for those
   rows. No code-2 place name contained "District", "CSD", "CSA" or "Authority" in any sheet.
   The only codes present are 1, 2, 3 and blank, in both the raw sheets and the DB (9,243 coded
   and 1,754 NULL CEDA rows). The 1998–2010 `.xls` files were not read because `xlrd` is not
   installed.

   Do not add the county to each label. One correction to the stated reason: the lead sentence
   names San Bernardino only as **"SB"** ("3 of 15 recorded Property Tax measures in SB passed",
   from `COUNTY_CONTEXT_LABELS`). That abbreviation predates this change, but spelling the county
   out there costs nothing and makes the prompt's reason true. Fix N1 first; it matters more than
   either.
2. **Modal badge.** Accept it. Changing the card alone would leave the card saying "Result
   unknown" and the modal "Unknown" for the same row. Both now use the shared `STATUS_LABELS`
   value. Record it in the checklist as part of the approved change, not as a separate decision.
   The open-tab refresh (`generator.py:11222-11226`) returns early for rows that are not pending,
   so it cannot overwrite the unknown badge's text.
3. **Left unchanged.**
   - **List row `?`:** keep it. Add `title`/`aria-label="Result unknown"` when convenient;
     today a bare `?` has no accessible name.
   - **"Pending/Unknown" chip:** keep it. The filter at `generator.py:10987` really does include
     both groups, so the label is accurate.
   - **Insights "Pending" bucket:** relabel it "Pending or unknown" whenever `insights.json` is
     next regenerated; it does not need to block P0.3. The committed snapshot (80 =
     12,332 − 12,252) dates from August 27. In today's DB the active undecided rows are 64 from
     2026 (including the withdrawn statewide row) and 56 historical unknowns. On regeneration,
     almost half the bucket would be rows this change just stopped calling "Pending".
4. **Badge style.** The doubled mark is not specific to unknown rows: every badge has a
   `::before` dot (`generator.py:4816`), so Passed and Failed render "• ✓ PASSED" and "• ✗ FAILED"
   too (see `review-p02\browser-mixed\390-statewide.png`). The stronger reason to change is color.
   Gold `badge-pending` means "awaiting", which is the claim P0.2b removes, and the static pages
   already use grey. Switching unknown rows to `badge-neutral` (its `::before` has no fill) and
   dropping the `•` glyph is right. It is a visual change, so do it as a small follow-up with
   Igor's sign-off. Update `RESOLVED_CARD_BADGES['unknown']`, the P0.2b test's expected
   `["pending", ...]` card tuples and its `count(...) == 2` assertion in the same commit.
5. **Raw code before the county** (`measures/3154.html`: "2, San Bernardino County"; the
   explorer modal joins with " • "). Confirmed on the candidate page. The DB has exactly 9,243
   coded CEDA rows, so the count is right. Agree to keep it out of P0.2: it would update thousands
   of pages and is better done with P1b's restored `PLACE`. Until then, add it to
   `KNOWN_ISSUES.md`. When it is fixed, reuse `history_jurisdiction_label()` instead of writing
   a second mapping.
6. **Stale fields on resolved rows.** Yes, failing is the right rule, and it is more than tidiness.
   The browser rule (`election_status.py:329-335`) returns a stored calendar status for any row
   whose `passed` is NULL. A stored-votes row with a stale `election_status` would therefore show
   "Results pending" in the browser while Python says unknown. For passed or failed rows a stale
   field changes nothing on screen, because the outcome check comes first and
   `officialResultsLinkHtml` hides the link. It still means attachment did not run, so failing is
   the safe choice for a release gate. Revisit this when Phase 2 decides whether decided rows keep
   an official-results link; that would be a contract change, not a checker bug.

## What I independently verified, and what I did not

Scratch root: `C:\Users\igorg\AppData\Local\Temp\claude\3706ee781272b6b6\d90ea535-f05d-4a6f-929d-dbc27318d103\scratchpad\review-p02\`.

| Claim / check | Observed |
|---|---|
| Targeted pytest, from `scraper/`, `--basetemp=.pytest-tmp/review-p02` | **126 passed** (86 + 23 + 17 collected per file, as claimed), with the Node-backed P0.2b test running, not skipped |
| Files, by my own walker (`scripts\compare.py`, `compare.json`) | 12,376 in each build; none added or removed. Changed: `index.html`, `measures-data.json` and **40** measure pages, the IDs listed in the prompt. **12,332** measure pages identical. `sitemap.xml` and `use-calballot/index.html` identical |
| Page diffs | Every changed line differs only in the `year · label ·` segment. Before: San Bernardino County 100, San Mateo County 100. After: Local 171, City 18, County or special district 10, School or college 1 |
| JSON | Same 12,372 IDs. Changed fields: `county_sections` 40 (0 differences after normalizing labels), `local_historical_context` 40 (only `records[].jurisdiction`, 200), `last_seen_at` 129 (07:49 vs 08:16 build stamps) |
| Distinct records shown | 60: 48 NULL, 6 code 2, 5 code 1, 1 code 3 (checked against the DB, read-only). The 48 NULL rows are 2022/2024 CEDA plus 12314 (2015) and 11021 |
| `index.html` | Cache key, card fallback (comment + line) and modal badge. difflib counts 4 hunks because the comment is a separate one; it is the same 3 changes |
| Remaining legacy strings | No `• Pending` or `• Unknown` in the generator. Related-measure cards show `•` only (`:15075`) |
| 56 unknown rows | 56 rows with no outcome, no calendar status and not withdrawn: 2011 48, 2000 6, 2018 1, 2005 1. All 56 have stored votes |
| Checker on the real candidate, `--clock 2026-11-12T12:00:00-08:00 --expect-count 63` | Exit 0, 0 failures; 63 Results pending at 1440, 390 and 320px |
| Checker on my mixed site, no transition | Exit 0, 0 failures (20 calendar + 43 resolved) |
| Checker on my mixed site, with transition | Exit 1, `StopIteration` (N2) |
| Builder's R7 runs (`agent-a\browser-r7-*.log`) | Logs and reports read; outcomes match the prompt's table. Their old-checker and dropped runs were not re-run |
| Protected hashes before and after | DB `ef1359e4…`, root `index.html` `b0257999…`, root `measures-data.json` `1921e5d4…`, the same full hashes as the P0.1 review. No tracked file changed |

**Not done:**

- No fresh scratch build; nothing in the existing artifacts gave a reason to doubt them.
- No full-suite rerun, so the 709/1/2/17 counts are unverified.
- The SMC CRLF failure was not reproduced (N4).
- The 1998–2010 `.xls` CEDA files were not inspected.
- No live link checks or network requests.

The production DB was opened only with `mode=ro`. The CEDA spreadsheets were read with
`python -I` from the scratch scripts. The only repository file written is this response; it is
not staged or committed.
