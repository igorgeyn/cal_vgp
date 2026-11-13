Written by a Claude reviewer agent in place of Codex on 2026-11-13, at `phase0-election-status` HEAD `7f2986b03313071afc9983c372d279ad2e9c4b78`.

# Explore E1 "Honest Explore" review response

Reviewed the code commit `8029d2e9` in full: `generator.py`, `explore.py`, `test_explore.py`,
`test_explore_hidden.py` and `check_explore_browser.py`. I checked that the candidate site in
`scratchpad\e1-candidate\site` was built from this code. Its `Explore` script and style are
byte-for-byte the committed `explore.py`. Its Explore JS block matches `generator.py` once the
f-string braces are undoubled; the only differences are the expected backslash unescapes. I then
used Explore in Chromium against the preview server at 1440, 390 and 320 px. I tried every
combination of columns × rows × min n × metric (72), sorted every column both ways, opened cells,
drilled down, came back, and used the chips, Clear and Reset.

## Verdict: **ready with changes**

The nine items and the flag flip are implemented as the plan states them. The core n < 5 rule
holds everywhere I could reach: 0 leaks across all 72 control combinations, in cells, totals,
the modal and the decade bars. The default view (Type by Decade) is honest, and the coverage
arithmetic reconciles. Grid and List are unaffected.

But E1's goal was "Explore stops saying things it can't support", and three remaining paths still
do that. Each is reachable in one or two clicks:

- the **Topic** columns (R1);
- a catalog **County** filter (R2);
- the **"Difference from column rate"** metric (R3).

R1–R3 should change before release. None of them is a regression from the published code. All
three were there before; E1 makes Explore visible again, which is why they matter now.

| Severity | Meaning |
|---|---|
| **P2** | Change before release |
| **P3** | Should fix; can follow in E2 if Igor accepts |
| **P4** | Latent or cosmetic |

## Findings, ranked

### R1 — P2: Topic mode pools statewide and local measures, so the decade trend is really a change of source

**Location:** `generator.py:11579-11582` (`getExploreColValue` for `topic`) and `:11630` (`valid`).
No level is separated anywhere in the matrix build.

**Evidence** (candidate `measures-data.json`, decided rows with a topic):

| Decade row | Statewide | Local |
|---|---|---|
| 1911–19 … 1990–98 | all (92–141 per row) | 0 |
| 2000–09 | 113 | 6 |
| 2010–18 | 94 | 349 |
| 2022–24 | 0 | 1,478 |

Local topics exist only for 2000 (5), 2005 (1), 2011, 2013, 2015, 2016 (1) and 2022–24.

Click **Topic** and the matrix shows, for example:
- Education "1970–79: 63%, 16 measures", which is statewide propositions;
- beside "2022–24: 73%, 588 measures", which is local school measures.

A reader sees a trend; it is a change of source. The "All" row pools the two as well. Of the
Taxes & Finance column (516), 380 are statewide propositions from 1911–2018; of Government &
Elections (928), 316 are.

Under Topic × Region, "Statewide (1279)" sits as a row beside regions whose counts start in 2011.
The coverage note says only "Sources: CEDA local records and the statewide archive."

**Fix (smallest honest one):** in Topic mode, count one level at a time. Use a Local | Statewide
toggle, default Local, and never pool the two in one row, column or total. The coverage line should
then say:
- which level is shown;
- that local topics exist only for 2011, 2013, 2015 and 2022–24;
- how many records of the other level are not counted.

The alternative is to hide Topic until E3/E4. This also answers open question 4 (below).

### R2 — P2: county-level rates are still reachable through the catalog County filter, beside a note saying they are not

**Location:** the coverage note at `generator.py:11713` ("County breakdowns return after the history
repair."). `applyFilters` (`:10868` ff.) passes `county`/`levelCounty` straight into
`filteredMeasures`, which Explore aggregates.

**Evidence:** with `County: Yuba`, Explore shows **"Bond, 2020–24: 6%, 18 measures"** and "All,
2020–24: 19%". This is exactly Fable's Yuba example (12 bonds in 2024, all failed). D3 hid county
rates because those cohorts carry the CEDA defects, yet these are shown with the note directly
above them saying county breakdowns are not available.

The browser check treats the county-filtered view as the expected behaviour
(`check_explore_browser.py:106`).

**Fix:**
- **Required.** When `currentFilters.county` or `levelCounty` is set, replace the sentence with a
  caution: county figures carry known source errors until the history repair.
- **My recommendation.** Also show counts only for county-filtered cohorts until P1b, using the
  same "3 of 18" rendering, with rate and fill suppressed.

This is a D3 scope question for Igor. The plan only said "hide the county row grouping".

### R3 — P2: drop "Difference from column rate" (open question 2)

**Location:** `generator.py:11665-11671` (the baselines for totals), `:11701` (the label) and
`:11751` (the presentation).

**What's wrong with it:**
1. **Mislabelled in both total lines.** The "All" row (column totals) and the "All" column (row
   totals) are compared with the **grand total**, not "column pass rate". Under Topic × Region the
   "All" row reads "Education +7 pp" and "Taxes & Finance -0 pp". By the metric's own name every one
   of those should be 0.
2. **It pools levels.** Under Topic the baseline is the pooled statewide + local column (R1).
   "Greater Bay Area, Taxes & Finance: +22 pp" is measured against a column that is 74% statewide
   propositions from 1911–2018.
3. **It turns small rated cells into headline numbers.** "Central Coast, Public Safety & Crime:
   −51 pp" is 1 of 5. Under Type × Region: "Central Valley, Initiative +34 pp" (n = 5) and
   "Eastern Sierra, Recall +24 pp" (n = 8). Read across a row, it is a ranking in all but name,
   which the plan rules out.
4. **The shading can't show sign.** A single sequential hue mapped over ±100 pp
   (`tint((d+100)/200)`) puts almost every cell near the middle tone. The legend runs −100 to +100
   while the data spans about ±50.

The pass-rate view with its "All" row already shows everything this metric does, without these
problems. Drop it in E1. If Igor wants to keep it, it needs:
- correct labels on the total lines;
- a floor of n ≥ 20;
- no fill;
- R1 fixed first.

### R4 — P3: the cell modal and accessible names still use calendar decades ("1990s"), not the real years

**Location:** `generator.py:11931` (modal title `${rowKey} — ${colValue}`), `:11759` (cell
`aria-label`/`title` from `rowKey`) and `:11950` (decade bar label `${d}s`).

**Evidence:**
- The default view's first row reads "1998–99", but its cells are announced as "1990s, Ordinance:
  106 of 183 passed…". The modal title is "1990s — Ordinance".
- The decade bars in a Region-row modal are labelled "1910s" to "2010s".

This is the label problem item 1 fixed in the table, still present one click deeper.

**Fix:** pass the display label (`Explore.decadeLabel` of the cell's years) into the aria-label and
the modal title. Use it for the bar labels too.

### R5 — P3: a Status filter turns the matrix into 100% (or 0%) everywhere

**Evidence:** with `Status: Passed`:
- every rated cell reads 100%;
- the coverage line says "0 without an outcome";
- nothing says that the failed measures were filtered out.

The chip is visible, so this isn't hidden, but the rates are tautological. This existed before.

**Fix:** either:
- have Explore ignore `status` passed/failed, and say so in the chip row; or
- when either is active, show counts only with a one-line note.

### R6 — P3: certified 2026 statewide results will enter the Measure Type view as new columns

**Evidence:**
- The 14 statewide 2026 rows carry instrument types in `display_category_type`: Initiative Statute,
  Legislative Constitutional Amendment and the like (ids 12467–12477, 10956, 1, 2).
- Every older statewide row has none.
- Today they are undecided, so they don't count.

Once results are imported, the default view gains six statewide instrument columns, and the note
"Statewide propositions have no measure type" becomes false. Nothing in E1 enforces the plan's "no
2026 results in Explore until certified" (§8).

**Fix:** in Measure Type mode, count local measures only (`county !== 'Statewide'`), and add a test
that pins this. Decide the 2026 rule now, before result import.

### R7 — P3: phones are worse than before E1, and the legend breaks

**Location:** `generator.py:8941` (`.matrix-toolbar span:first-child { flex-basis: 100% }` inside
`@media (max-width: 768px)` at `:8842`).

**Evidence:**
- **The legend breaks.** That old rule now matches the legend's first swatch. At 390 and 320 px the
  "0%" swatch stretches to 202 px on its own line, above 25/50/75/100
  (`review-e1\browser\390-wrapper.png`).
- **The matrix starts lower.** It starts **1,018 px** down at 390 px and **1,108 px** at 320 px
  (Fable measured about 840 before E1). The new heading, coverage line and two notes add about
  450 px.
- **Few columns fit.** 3 of 15 columns are visible at 390 px and 2 at 320 px.

There is no document overflow at either width.

**Fix:**
- **Legend:** scope the old rule to `.matrix-toolbar > span:first-child`, or override it inside
  `.matrix-wrapper .explore-legend-scale`.
- **Space:** put the notes in a `<details>` on narrow screens. The layout itself is E2c.

### R8 — P4: the "shared" threshold filter E1 kept is unreachable

The handoff and the commit say `getMeasureThreshold` was kept because "the catalog's threshold
filter uses it". The filter exists (`generator.py:10891-10895`), but after E1 nothing ever fills
`currentFilters.thresholds`:
- the only writers are `:11969` and `:11974`, which clear it;
- it is not restored from the URL either.

So `getMeasureThreshold`, `getThresholdLabel`, the filter branch and the "Threshold" token in
`getActiveFilterTokens` (`:10257`) are now dead code. They still encode the false
"default = Simple majority" rule.

This is harmless today. Delete them in E2, or leave a comment that they must not be revived before
E3's repaired `required_vote`. Either way, correct the handoff's justification.

### R9 — P4: smaller defects

- **Hidden values can steer the sort.** The `avgYes` sort value uses a literal 5
  (`generator.py:11694`), but the display hides the average below `max(5, minN)` (`:11748`). With
  min n 10 or 20, a cell showing "too few for an average" can still be sorted by its hidden
  average. I found no live cell this affects (`percent_yes` is missing on only 76 decided rows).
  Use `Math.max(5, matrixState.minN)` in both places.
- **"−0 pp".** `toFixed(0)` of a small negative prints "−0 pp" (Taxes & Finance, Topic × Region).
  Moot if R3 drops the metric.
- **A drill-down can show more records than the cell.** It can open more records than the cell
  counted, because the Grid also lists rows without an outcome:
  - 2000s Ordinance 890 → 891;
  - 2000s Bond 1,120 → 1,124;
  - 2010s Bond 933 → 941.

  A decade drill also switches off the default pending exclusion: "2020s" brings in the 63
  current-election rows plus the withdrawn one, so Explore then shows "64 without an outcome". The
  button says "matching catalog records", so this is defensible. Saying "includes records without
  an outcome" would close it.
- **A latent drill-down bug.** Any county not in `CA_REGIONS` would fall into an "Other" region row.
  Drilling on that row sets `levelCounty = 'Other'` (`:12031-12033`, `:11995-11997`) and gives an
  empty Grid. Today there are 0 such rows.
- **Dead code:**
  - the county fall-through in `getExploreRowValue` (`:11597`);
  - `rowLabel`/`colLabel`;
  - the 'Jurisdiction' header branch;
  - an orphan comment "Threshold trap color: purple scale" (`:11899`).
- **A misleading sort arrow.** The row header shows a "↓" `sorted-desc` arrow (`:11780`) while
  decades run oldest-first.

## Answers to 1–7

**1. Plan coverage.**

| Item | Verdict | Notes |
|---|---|---|
| 1. Default view | Done | Measure Type × Decade; time order; labels computed from the data ("1998–99", "2000–09", "2010–19", "2020–24"; under filters "1998", "2000–08"). The modal and aria-labels still say "1990s" (R4) |
| 2. Heading and coverage line | Done | Computed from `filteredMeasures` with the same predicate as the matrix. The year span and sources are present |
| 3. Removals | Done | Threshold mode, close calls, trap, summary cards, their handlers and CSS (`.matrix-insight-*`, the legend bar, the colour functions). `getMeasureThreshold` is kept but now unreachable (R8) |
| 4. Small cells | Done | "3 of 4", no fill, a neutral border, the aria-label "…; too few to show a rate". Min n 5 (options 5/10/20, so you can't go below 5). Unrated cells sort last in both directions (I clicked every column, both ways, at min n 5 and 20 under Decade and Region: 0 violations). The fade and "anecdotal" are gone |
| 5. Palette | Done | One slate hue, dark text, a numbered legend. Lowest cell contrast 7.06:1, which I reproduced. Not centred on 50% |
| 6. County rows | Done | Rows are Decade, Year, Region only; the note is present. But see R2 |
| 7. Filters | Done | Chips with accessible names, "Clear filters", and Reset clears the filters too. Drill, return, chip removal (to 3,028) and Clear (to 12,309) all work |
| 8. Dead renderer | Done | The unreachable block after `return renderMatrixV2()` and its exclusive helpers are deleted; no callers remain (grepped) |
| 9. Words | Done | Tooltip, view card and welcome line updated; "notable" removed; no "topic × jurisdiction" left |
| Flag | Done | `SHOW_EXPLORE = True`; `setView` guard emitted as `!true`; the hidden-state test kept by monkeypatching |

**2. Honesty.**
- **Default view:** sound. 51 cells, none below 5, and the grand total of 10,939 equals "counted".
- **Leak sweep:** across all 72 control combinations, no cell, total or legend shows a % or a fill
  for n below the floor in force.
- **Modal:** shows "3 of 4" and no average below the floor.
- **Decade bars:** for n below the floor, a 4 px transparent bar with a "2 of 3" title.
- **What can still mislead:** Topic pooling (R1), county filters (R2), the baseline metric (R3) and
  status filters (R5).
- **"Average yes vote":** acceptable to keep, with two caveats in its tooltip or note:
  - it is an unweighted mean of each record's yes share, across measures with different required
    votes, so it should not be compared with 55% or ⅔;
  - it includes multi-county portions. 13 decided rows have `percent_yes = 0` with
    `yes_votes = 0`: San Benito portions with 1 total vote, and Monterey 7699 with 0 yes and 0 no.
    These count as 0% yes.
- **Region rows** mix levels only under Topic (R1). Under Measure Type, statewide drops out.

**3. Coverage line.** The arithmetic is right under every filter I tried. Each of the following
reconciles exactly, and the default total equals `#resultsCount` (12,309):
- none;
- County Yuba;
- Year 2026;
- Level Statewide;
- Status Passed;
- Year Range 2000–2010;
- search "school";
- the decade drill.

The default 57 "without an outcome" are the 56 historical unknowns plus the one withdrawn 2026
proposition.

The note's sentence about pending measures matches `applyFilters` (`:11020-11026`). It omits the
"decade" trigger, but "year" covers it loosely.

See question 1 under the open questions for whether to name the 63.

**4. Regressions.**
- **Removed code:** `matrixCellColor`, `matrixYesColor`, `matrixVolumeColor`, `matrixDeltaColor`,
  `trapCellColor` and `renderExploreSummary` have 0 remaining references.
- **Shared code:**
  - `CA_REGIONS` is still defined at `:9686` and used by the catalog region UI and filter;
  - `countyToRegion` is used only by Explore;
  - `matrixDrillDown` and `exploreFilterToCounty` are called only from Explore;
  - `getActiveFilterTokens` and `removeActiveFilterFromButton` are shared with the catalog summary
    and unchanged.
- **Reset:** `resetMatrixControls → clearAllFilters` clears search, every filter and the Grid page
  (page 3 goes back to 1). It stays in Explore and leaves the URL at `/`. That is what "Reset also
  clears filters" asks for. There's no effect beyond the catalog state, which Explore shares by
  design.
- **CSS:** the new rules are all scoped under `.matrix-wrapper` or `.matrix-cell-modal`. The
  regression is the old unscoped mobile rule now matching the legend (R7).
- **Grid and List:** fine after visiting Explore. Grid shows 12 cards at `/`, List is at
  `?view=list`, and there are no page errors.
- **Preservation:** the evidence `compare.json` and `index.diff` are as described: 55 hunks, all
  Explore CSS/JS, the entry points, the cache key and the guard.

**5. Accessibility.**
- **Cells:** names read "1990s, Ordinance: 106 of 183 passed; Pass rate 58%". The facts are right;
  the decade label is wrong (R4).
- **Keyboard:** Enter opens a cell. Space does nothing, Escape doesn't close the modal, focus isn't
  moved into it, and it has no `role="dialog"`. All of this is E2a.
- **Tab stops:** 89 in the default view (Fable counted 390). E2b.
- **Row headers:** each is a `td role="button"` whose name ("1998–99 (855)") doesn't say it leaves
  Explore for the Grid. E2b.
- **Chips:** good names ("Remove County: Yuba"). The container's `aria-label` sits on a role-less
  `div`, where assistive tech ignores it; use `role="group"`. The column toggles lack
  `aria-pressed`. Both are minor.
- **Contrast:**
  - decade-bar labels in the modal are `#888` on white at 0.6 rem, **3.54:1**; this predates E1;
  - the count-only border `#8996a0` is 2.95:1 against `#FDFCFA`, just under 3:1 for non-text;
  - a rated 0% cell's fill is 1.07:1 against the page, so it looks unshaded. The text carries the
    meaning, so none of these fail E1. Fix the bar labels in E2c.

**6. Tests and checks.**
- I reran the targeted tests (`test_explore.py`, `test_explore_hidden.py`, `test_insights_hidden.py`,
  `test_election_status.py`): **103 passed**, with Node v24 present, so the helpers really ran.
- I reran `check_explore_browser.py` on the candidate: **exit 0** at all four widths, minimum
  contrast 7.06:1. I didn't rerun the four older browser checks; I relied on the evidence logs.
- Full suite: 755 passed, at the known baseline (last section).

The tests test what they claim. The browser check is honest but narrow, and it would pass with each
of the following wrong:
- **Fixed floor.** `CELL_CHECK` hardcodes `n<5` (`:35`) and never runs at min n 10 or 20. If
  `Explore.cell` ignored `minN`, it would still pass.
- **Modal.** The synthetic modal uses Year rows (`:140`), so the decade-bar chart is never rendered.
  Bar titles, labels and fills are unchecked, and so are the modal title and the cells' aria-labels
  (R4).
- **Drill path.** "Chip after drill-down" uses the row-header drill (`:124`), not the cell modal's
  "View matching catalog records" (`matrixDrillDown`). My run covered that path (12 cells).
- **Reconciliation.** The coverage check compares with its own reimplementation of the catalog rule
  (`:13`), not with `filteredMeasures.length` or `#resultsCount`. A divergence shared by both would
  go unseen. Assert `total == filteredMeasures.length` too.
- **Nothing checks:**
  - Topic pooling (R1);
  - county-filter rates (R2): the check asserts this path as success;
  - the baseline labels on the total lines (R3);
  - the mobile legend layout (R7).
- **Fixed data.** It hardcodes the dataset (`'1998–99' in labels[0]`). That's fine for a release
  gate, but it will need updating when the data changes.

Suggested additions:
- run `CELL_CHECK` with the floor in force at min n 10 and 20;
- open a Region × Topic cell and assert no "%" in any bar title whose n is below the floor;
- assert the modal title equals the row's display label;
- assert that, with a county filter, no rated cell exists (if R2's stricter fix is taken);
- assert `.explore-legend-scale span` widths are roughly equal at 390 px.

**7. Open questions:** below.

## The handoff's open questions

1. **Coverage total.** Yes: name what the default filters leave out. The page's own FAQ says
   "12,372 measures", and Explore says "Total for the current catalog filters: 12,309", with
   nothing to bridge the two.
   - **What to add:** when the default pending exclusion is active, a clause such as "63
     current-election measures awaiting results are outside the catalog's default view". Compute
     it live as `allMeasures` minus the rule, not hardcoded.
   - **Rename the bucket:** call "without an outcome" "without a recorded outcome (pending,
     unknown or withdrawn)", since it includes the withdrawn 2026 proposition.
   - **Name the scope:** in Topic mode, also say which years have local topics (R1).
2. **"Difference from column rate."** Drop it (R3): it is mislabelled on the total lines, it pools
   levels under Topic, and it turns n = 5 cells into ±50 pp headlines. If it stays:
   - correct the total-line labels;
   - floor n ≥ 20;
   - no fill;
   - only after R1.
3. **`exploreFilterToCounty`.** Agree it's out of E1's scope. Rename it in E2b, when the row header
   becomes a real `<th>` with a button whose name says it opens the Grid. At the same time:
   - fold it and `matrixDrillDown` into one helper (their row branches are duplicated,
     `:11977-12001` and `:12013-12037`);
   - remove the "Other"/county fall-through (R9).
4. **Region rows mixing levels.** It's broader than Region: under Topic, every row and total pools
   statewide 1911–2018 with local 2011–2024 (R1). Recommend Topic counts one level at a time
   (Local | Statewide, default Local), with the coverage line naming the other level's uncounted
   records. Under Measure Type the problem doesn't arise today, but it will after 2026 statewide
   results land (R6). Restrict Measure Type to local measures explicitly.

## Must change before release

1. R1: Topic mode by level, or hide Topic.
2. R2: a county-filter caution at minimum; counts only if Igor agrees under D3.
3. R3: remove the "Difference from column rate" metric, or fix it as listed.
4. Recommended in the same pass, since each is a few lines:
   - R4: decade labels in the modal and aria-labels;
   - R7: the mobile legend rule;
   - R6: Measure Type restricted to local;
   - R5: the status-filter note.

Then rerun `check_explore_browser.py`, extended as in answer 6, and the preservation compare. Only
`index.html` should change further.

## What I verified, and what I did not

Scratch root: `C:\Users\igorg\AppData\Local\Temp\claude\3706ee781272b6b6\d90ea535-f05d-4a6f-929d-dbc27318d103\scratchpad\review-e1\`.

| Check | Observed |
|---|---|
| Candidate = committed code | `explore.py` `SCRIPT`/`STYLE` found verbatim in the candidate `index.html`; the Explore JS block equals the generator source after undoubling, differing only by the expected backslash unescapes (`match_src.py`) |
| Leak sweep (`explore_probe.py`, `browser\probe.json`) | 72 combinations (2 columns × 3 rows × 3 min n × 4 metrics): **0** cells, totals or titles with a % or fill below the floor |
| Sorting | Every column header clicked once and twice, under Decade and Region, at min n 5 and 20: unrated cells always last and rated values monotone; 0 violations |
| Default view | Decades 1998–99 / 2000–09 / 2010–19 / 2020–24; 51 cells, none below 5; 10,939 + 1,313 + 57 = 12,309 = `#resultsCount` |
| Drill-downs | 12 cells: grid count = n, or n plus the rows without an outcome (R9); chips correct; return, chip removal, Clear and Reset all correct |
| Modal | Region × Topic modal: decade bars below the floor are transparent with "n of N" titles; title and bar labels use "1990s"-style keys (R4); Space doesn't open, Escape doesn't close, no dialog role (E2a) |
| Phones, 390 and 320 px | No document overflow, including with the modal open and a chip; the legend's "0%" swatch is 202 px wide (R7); the matrix starts 1,018 / 1,108 px down |
| Filter edges (`edges.py`) | Statewide level, Year 2026, Status Passed, Year Range, County Yuba: arithmetic reconciles; R2 and R5 observed |
| Official check | `check_explore_browser.py` on the candidate: exit 0 at all four widths (`review-e1\official-check\report.json`) |
| Targeted tests | 103 passed, with `--basetemp=.pytest-tmp/review-e1` |
| Full suite (`--basetemp=.pytest-tmp/review-e1-full`) | **755 passed, 1 skipped, 1 failed, 17 errors**, which is exactly the known baseline (`test_models` 1; `test_database`/`test_deduplication` 17). Matches the handoff |
| Data probes | Topic level split by decade; the typed 2026 statewide rows; `percent_yes = 0` rows; no unmapped counties (all read from the candidate JSON) |

**Not done:**
- No fresh scratch build. The candidate's code identity was confirmed instead.
- I didn't rerun the election-status, county-content or navigation browser checks; I relied on the
  evidence logs and reports.
- I didn't rerun the preservation compare; I read `compare.json` and the hunk headers of
  `index.diff`.
- No screen-reader pass.
- No network.

The production DB was not opened. The only repository file written is this response; it is not
staged or committed.
