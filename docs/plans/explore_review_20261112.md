# Explore tab: review and proposals

**Date:** November 12, 2026. **By:** Fable. **Branch:** `phase0-election-status` at `640889fc`.
**Method:** I drove Explore in headless Chromium against `http://127.0.0.1:8917/` only (every
other host blocked) at 1440, 768, 390 and 320 px, as a voter, a journalist and a
researcher, and read the code in `scraper/src/website/generator.py`. No code or data
changed. No database was opened; the numbers below come from the preview's own
`measures-data.json`.
**Screenshots:** `scraper/data/exports/explore_review_20261112/` (19 files, gitignored).

## 1. Verdict

Igor's instinct is right, but the layout is the smaller problem. **Explore's main fault is
that it states numbers it cannot support, and does not say what it is counting.**

- **The default view silently drops three quarters of the data.** It shows 3,112 of 12,252
  decided measures. For counties it is really 2022-2024 plus 2011, 2013 and 2015.
- **One of the three column modes is wrong for every row.** "Threshold" puts all 12,252
  measures under "Simple majority".
- **The first thing a reader sees is four "findings"** made by ranking extreme cells. The
  "lowest reliable pass rate" is one 2024 bond package counted as 12 measures.
- **It fails basic accessibility.** No cell reaches 4.5:1 text contrast.
- **On a phone it is not usable**: the matrix starts about three screens down and shows 3 of
  12 columns.

What is good: it is fast (45-70 ms to rebuild), the row and column model is flexible, the
cell detail has useful bones, and **Measure Type by Decade is a sound view** (51 of 52
cells have 10 or more measures; `explore_1440_type_by_decade.png`).

**Recommendation:** fix the honesty problems first (§6, quick wins; §9). Then replace the
matrix as the default with a question-led view (§7, Concept A) and keep a smaller matrix
for desktop.

## 2. How the numbers are made today

| Element | What the code does | Where |
|---|---|---|
| Rows | County (default), region, decade or year. "Statewide" is one row among the counties. | `:11732-11746` |
| Columns | Topic (default), measure type or threshold | `:11726-11730` |
| What is counted | Measures passing the current catalog filters, with `passed` 0 or 1 **and a non-empty column value** | `:11795` |
| Cell value | Passed ÷ total, rounded; the count beneath | `:11984` |
| Color | Red at 0%, amber at 50%, teal at 100%; white text | `:11631-11650`, `:3019-3025` |
| Low n | Under 3: 60% opacity, "anecdotal". Under 10: 82%, "limited". "Min n" defaults to All | `:11782`, `:11993`, `:3003`, `:11689` |
| Sort | Row total by default; a column header sorts by that cell's rate, any n | `:11841-11853` |
| Totals | An "All" column and a dark "All" row, over the same filtered set | `:12048-12053` |
| Summary cards | Highest and lowest rate among cells with n ≥ 10, largest cell, most "traps" | `:11882-11908` |
| Cell click | A modal: rate, average yes, close calls, traps, decade bars, three "notable" measures | `:12424-12525` |
| Row label click | Sets a catalog filter and switches to Grid | `:12577-12608` |
| Filters | Still applied, but the filter panel is hidden in Explore | `:12638` |
| URL | Not recorded. Only `view=list` is ever written | `:10829-10837` |

## 3. Three readers

**A voter curious about San Mateo County.** They find the row and read "Education 95%,
39". Nothing says those 39 come from only six years. They click the county name and
land in Grid with a filter set, with no way back. Returning to Explore shows a matrix of
one cell, and "Reset Explore" does not clear it, because the filter panel is hidden
(`explore_1440_return_after_drilldown.png`). On a phone they never reach the matrix
without three screens of scrolling.

**A journalist checking "school bonds almost always pass".** Measure Type gives "Bond 71%,
3,016". That blends two legal regimes. From the source's own outcome codes, **55% bonds
passed 75% of the time (1,708 of 2,292) and two-thirds bonds 57% (385 of 677)**. Explore
cannot show that: its Threshold mode has one column (`explore_1440_threshold.png`). It
also cannot separate school bonds from city bonds. And there is nothing to cite: no link,
no definition, no download, and a reload returns to Grid.

**A researcher defining a sample.** The sample is defined by filters they cannot see. The
cell says 39 measures; "View all" opens 48, because the catalog includes undecided ones.
There is no export and no statement of sources or exclusions.

## 4. Audit

### 4.1 Statistical honesty (most serious)

1. **Coverage is hidden.** `display_topic` exists for 3,112 decided measures; 9,140 have
   none and are dropped (`:11795`). Local topics exist only for 2011 (92), 2013 (137),
   2015 (119) and 2022-2024 (1,478). The toolbar says "3,112 measures with outcomes" and
   nothing more.
2. **Threshold mode is false.** `getMeasureThreshold` (`:11712-11717`) reads
   `vote_threshold`, which is set on 49 rows. Every other measure defaults to 50. So 2,484
   measures the source codes as two-thirds, and 2,324 it codes as 55%, are labelled
   "Simple majority". "Close calls" inherits the error (`:11770`).
3. **The summary cards rank extremes.** With 684 cells, the top and bottom are mostly noise
   or clustering. "Yuba / Education, 7% passed across 15 measures" is 12 lettered 2024 bond
   measures (A-F, S-X) that failed together, plus three from 2022. The
   [layout review](../codex/layout_direction_a_review_response.md) (answer 5) rules this
   out: no ranks from small cohorts.
4. **Tiny cells look like results.** In the default view 188 of 299 non-empty cells have
   fewer than 5 measures, and 133 of the 142 cells showing 0% or 100% do. Sorting by a
   column puts them on top: Colusa 100% (n=3), Inyo 100% (n=4), Lassen 100% (n=1)
   (`explore_1440_sorted_by_education.png`).
5. **Unlike things share one table.** The Statewide row is 1,279 propositions back to
   1912; the county rows are a few recent years. "All" and "Vs. Baseline" mix them. In
   Measure Type the Statewide row disappears, because propositions have no type.
6. **Known data defects pass straight through.** See the
   [reconciliation report](ceda_reconciliation_20261112.md): 28 rows carry another
   measure's outcome, 55 have no outcome and are dropped, 2016-2021 is unverified, and a
   multi-county measure is counted once per county with that county's share as its result.
   Explore's San Bernardino Bond cell reads 62 of 92 (67%); the county card for the same
   place reads 60 of 87 (69%). One site, two answers.
7. **Decade rows mislead.** "1990s" is 1998-1999 and "2020s" is 2020-2024. The default sort
   is by count, so time runs 2000s, 2010s, 2020s, 1990s.
8. **"Pass" means different things.** A recall "passes" when the official is removed; an
   advisory measure binds nobody. One color scale covers all of them.

### 4.2 Usefulness

It answers one question well: how often a type of local measure passes, by decade. It
cannot answer: by required vote; school versus city; one city or district; a trend with
numbers; how close results were; or anything about the current election.

### 4.3 Layout and visual design

- **No title, no sentence saying what this is.** The page opens on seven controls of three
  different kinds.
- **The legend has no numbers** and is labelled with the metric's name.
- **Red-to-green centred on 50% suits neither the data nor the site.** Local measures pass
  68% of the time, so the page is mostly green and differences vanish. Red and green also
  read as bad and good, on a site that is neutral about outcomes. *The palette is Igor's
  call;* options are in §6.
- **Low n is shown by fading**, which lowers contrast further, plus a word in 8.6 px type.
- The header row is repeated as a footer. The matrix sits in its own scroll box inside the
  page's scroll.

### 4.4 Interaction

- **Hidden filters** (above), and **Reset Explore** resets only the matrix controls.
- **No URL state and no history entry.** Back leaves the site; reload returns to Grid.
- **The cell modal** is the best part, but its decade bars have no numbers, and "notable"
  means closest to 50%, whatever the measure's real threshold.

### 4.5 Phones

At 390 px the toolbar is 274 px tall and the cards 408 px, so the matrix starts near
840 px (`explore_390_viewport.png`, `explore_390_matrix.png`). It then shows 3 columns of
12 and about 12 rows of 57 in a nested scroll box. The "Threshold" button is clipped and
the legend collapses to a red pill. At 320 px the page itself scrolls sideways (350 px
wide; `explore_320_viewport.png`). **A 57 by 12 matrix does not work on a phone.**

### 4.6 Accessibility

- **Contrast:** white text on the cell colors measures 1.6 to 3.6 to 1. None of 299 cells
  reaches 4.5:1; 269 are under 3:1. The 9 px counts are worse.
- **Keyboard:** 390 tab stops. Enter opens a cell; Space does not. Focus does not move
  into the modal, and Escape does not close it.
- **Screen readers:** `td role="button"` inside `role="grid"` removes the cell semantics.
  There is no caption, no `scope`, no `aria-sort`, and the modal has no dialog role.
- Meaning is not carried by color alone, since each cell has text. Reliability nearly is.

### 4.7 Performance

Fine. A rebuild takes 45-70 ms and the matrix is 2,390 nodes. The real cost is upstream:
`measures-data.json` is 35 MB and `index.html` 6 MB before Explore can draw. About 257
lines of the old renderer are unreachable after `return renderMatrixV2()` (`:12067-12324`).

## 5. Explore and Insights

They overlap because neither has a stated job. A workable division:

| | **Insights** | **Explore** |
|---|---|---|
| Who chooses the question | CalBallot | The reader |
| Content | A few findings, each reviewed, with prose and a chart | A cohort the reader defines: count, rate, records |
| Numbers | Computed at build time, checked, dated | Computed live from the catalog, with stated limits |
| Rankings, "highest", "lowest" | Only here, and only when reviewed | Never |
| Links | Each finding links to its cohort in Explore | Each cohort links to its records in the catalog |

Under this split the four summary cards belong in Insights or nowhere.

## 6. Suggestions, ranked

### Quick wins (under half a day each)

| # | Change | Why | Depends on | Risk | Verify |
|---|---|---|---|---|---|
| Q1 | **Default to Measure Type by Decade**; decades in time order, labelled with their real years ("1998-99") | The one view the data supports; fits a phone better | None | Low | 51 of 52 cells n ≥ 10; order check |
| Q2 | **Add a title and a coverage line**: "10,939 local measures, 1998-2024, from CEDA. Not included: …" computed from the data | Says what is counted | None | Low | Counts reconcile with the catalog |
| Q3 | **Remove Threshold mode, "Close calls" and the four cards** | Each is wrong or misleading today | None | Low; it removes features | Controls gone; no dead handlers |
| Q4 | **Under 5 measures, show "3 of 4", no percentage and no color.** Default "Min n" to 5; sorting ignores those cells | The layout review's rule | None | Low | Fixture with n = 1, 4, 5 |
| Q5 | **Dark text on light tints**; drop the opacity fade | Contrast | None | Low | Every cell ≥ 4.5:1 |
| Q6 | **Show active filters in Explore, with "Clear"**; make Reset clear them | Ends the one-cell trap | None | Low | Drill down, return, clear |
| Q7 | **Put view and controls in the URL** (`?view=explore&cols=type&rows=decade`), with a history entry on drill-down | Shareable; Back works | None | Medium: touches `updateURL` and `popstate` | Reload, Back and Forward checks; Grid/List links unchanged |
| Q8 | **Modal:** dialog role, focus in and back, Escape, Space on cells | Keyboard use | None | Low | Keyboard script |
| Q9 | Delete the dead renderer | 257 fewer lines to misread | None | Low | Tests pass; matrix renders identically |

### Medium (1-3 days each)

| # | Change | Why | Depends on | Risk | Verify |
|---|---|---|---|---|---|
| M1 | **Phone layout:** below 700 px, replace the matrix with a ranked list for one chosen column or row, each line "Bond · 71% · 3,016" with a bar | A matrix cannot fit | Q1 | Medium | No overflow at 320; all values reachable |
| M2 | **Proper table semantics:** real `th scope`, buttons inside cells, `aria-sort`, arrow-key movement with one tab stop | Screen readers; 390 tab stops become 1 | None | Medium | Axe-style checks; manual pass |
| M3 | **Split bonds and taxes by required vote**, labelled "as coded by the source" | The journalist's question | Safer after P1b; `REQ` is unreliable in places (see the [design](ceda_backfill_design_20261112.md) §4) | **High if shipped before P1b** | Totals equal the unsplit column |
| M4 | **Cohort record list in place** (sortable table under the matrix) with CSV download and a "how this was counted" note | The researcher's need; no trip to Grid | Q7 | Medium | Downloaded rows equal the cell count |
| M5 | **Count a multi-county measure once**, with its combined result | Removes double counting | P1b.2 | Low once data exists | Compare with the reconciliation ledger |
| M6 | **Trend line with numbers** in the cell detail, by election year, n shown | Replaces unlabelled bars | None | Low | Values match the cell |

### Ambitious

| # | Change | Why | Depends on | Risk |
|---|---|---|---|---|
| A1 | **Concept A below as the default Explore** | Serves the journalist and researcher directly, and works on phones | Q-tier; M3 and jurisdiction kind need P1b | Largest; a new surface in a 16,000-line file |
| A2 | **County page** (Concept B), linked from every local measure | Serves the voter; gives county pass rates one home, shared with the county cards | P1b for names; shared cohort code with `local_measure_context.py` | Medium |
| A3 | **Precomputed Explore data** (a small aggregates file) so Explore loads without the 35 MB catalog | Speed on phones | A build step | Medium |

## 7. Three concepts

Figures inside the wireframes are illustrative, except Concept C's, which are today's.

### Concept A: "Ask the record" (recommended; journalist and researcher)

The reader builds one sentence; the page answers it with a count, a rate, the spread and
the records. No grid of 700 numbers.

```text
DESKTOP
+----------------------------------------------------------------------------+
| How often do  [ school bonds v ]  needing  [ 55% v ]  pass in              |
| [ all counties v ]  from [ 2001 ] to [ 2024 ] ?                            |
+----------------------------------------------------------------------------+
|  1,708 of 2,292 passed (75%)        Source: CEDA. Counted once per measure.|
|  Not counted: 31 with no recorded outcome.   [Copy link] [Download CSV]    |
+--------------------------------------+-------------------------------------+
| By election year                     | Yes vote against the 55% line       |
| 100|            .  .                 |        fail | pass                  |
|  75|  . .  . .. . .. .  .            |   . ..:::|::::::::... .             |
|  50| .                               |  40   50   55   60   70   80        |
|    +--2002----2010----2018----2024   |  212 failed within 5 points         |
|     (n under each point)             |                                     |
+--------------------------------------+-------------------------------------+
| Compare:  two-thirds bonds 57% (385 of 677)   parcel taxes ...   [+ add]   |
+----------------------------------------------------------------------------+
| Records (2,292)   Year v | Place | Measure | Yes % | Result                |
| 2024  Saugus Union SD     Measure N   48.8%   Failed                       |
+----------------------------------------------------------------------------+

PHONE
+------------------------------+
| How often do                 |
| [ school bonds          v ]  |
| needing [ 55%           v ]  |
| pass in [ all counties  v ]  |
| [ 2001 ] to [ 2024 ]         |
+------------------------------+
| 75% passed                   |
| 1,708 of 2,292               |
| [Copy link]  [CSV]           |
+------------------------------+
| By year      (tap for n)     |
|  . .. . .. . . .             |
+------------------------------+
| Compare                      |
| Two-thirds bonds  57%  677   |
+------------------------------+
| Records (2,292)           >  |
+------------------------------+
```

### Concept B: County page (voter)

```text
DESKTOP                                            PHONE
+-----------------------------------------------+  +---------------------------+
| San Mateo County        [ change county v ]   |  | San Mateo County       v  |
| 1,0xx local measures, 1998-2024               |  | 1,0xx measures, 1998-2024 |
+-----------------------------------------------+  +---------------------------+
| On the November 3, 2026 ballot: 29 measures > |  | Nov 3, 2026: 29 measures >|
+----------------------+------------------------+  +---------------------------+
| Kind of measure      | Passed        State    |  | School bonds              |
| School bonds (55%)   | 90 of 105 ##########   |  | 90 of 105  ##########     |
| Parcel taxes (2/3)   | 81 of 111 #######      |  | Parcel taxes              |
| Sales taxes          | 18 of 26  #######      |  | 81 of 111  #######        |
| Charter amendments   | 3 of 4 (too few for %) |  | Charter amendments        |
+----------------------+------------------------+  | 3 of 4                    |
| Recent results       2024  2022  2020  ...    |  +---------------------------+
| Measure A  Millbrae  Sales tax  61%  Passed   |  | Recent results         >  |
+-----------------------------------------------+  +---------------------------+
```

It reuses the county-history rules in `local_measure_context.py`, so a county has one
pass rate per kind of measure across the whole site.

### Concept C: Matrix, done properly (desktop analyst)

```text
DESKTOP                                                   PHONE (no matrix)
+------------------------------------------------------+  +-----------------------+
| Local measures by type and decade   10,939 measures  |  | Show [ Bonds      v ] |
| Shade = share passing. Under 5: count only, no shade.|  +-----------------------+
+-------------+--------+--------+--------+-------+-----+  | 1998-99   58%    249  |
|             |1998-99 |2000-09 |2010-19 |2020-24| All |  | 2000-09   71%  1,120  |
| Bonds       |58% 249 |71% 1120|80% 933 |63% 714| 71% |  | 2010-19   80%    933  |
| Property tax|61%  98 |53% 532 |66% 432 |66% 238| 60% |  | 2020-24   63%    714  |
| Gann limit  |80%  10 |96%  55 |94%  17 |100% 16| 95% |  +-----------------------+
+-------------+--------+--------+--------+-------+-----+  | [ By county > ]       |
| Rows: [type v]  Columns: [decade v]  [counties >]    |  +-----------------------+
+------------------------------------------------------+
```

One sequential hue, dark text, real year labels, counties as a drill-in rather than the
default.

**Who each serves:** A the journalist and researcher; B the voter; C the analyst who
already likes tables. A and B together cover more readers than any matrix. C is the
cheapest, since Q1-Q5 nearly produce it.

## 8. What not to do

- **Don't polish the current default.** A better-looking Topic by County matrix is still a
  quarter of the data.
- **Don't add significance tests, rankings or "top counties".** The cells are too small
  and the measures are not independent.
- **Don't ship a threshold split before P1b** without the "as coded by the source" label.
- **Don't include 2026 results** until they are certified.
- **Don't build a map.** It answers the same question as the county column, less precisely.
- **Don't generate prose about cells** with a model. Fixed templates only, per the
  deterministic-cards rule.
- **Don't solve phones by shrinking the matrix.**

## 9. Recommended first chunk: "Honest Explore"

**Scope:** Q1 to Q6 and Q9. No new features; Explore stops saying things it cannot
support. About 1.5 days.

**Files:** `scraper/src/website/generator.py` only: the Explore CSS (near `:2762`), the
Explore JavaScript (`:11629-12608`), `updateViewVisibility` (`:12627`) and the two view
buttons' tooltips. New: `scraper/scripts/check_explore_browser.py`, and tests beside the
existing Node tests in `scraper/tests/`.

**Acceptance checks:**
1. Default view is Measure Type by Decade, decades in order and labelled by their years.
2. The coverage line's counts equal the catalog's: counted + not counted = all measures.
3. Every cell with fewer than 5 measures shows a count, no percentage and no color; a
   fixture covers n = 0, 1, 4, 5.
4. Every cell's text contrast is at least 4.5:1, measured in the browser.
5. Threshold mode, "Close calls" and the summary cards are gone, with their handlers.
6. An active filter is visible in Explore and can be cleared there; drill down, return and
   clear restores the full count.
7. No page overflow at 320 px.
8. Existing status, navigation and county-content browser checks still pass.

**Preservation gate:**
- All 12,372 measure pages byte-identical.
- `measures-data.json` byte-identical apart from the known `last_seen_at` regeneration.
- `sitemap.xml` and `use-calballot/index.html` byte-identical.
- `index.html` differs only inside the Explore blocks named above, plus the data cache key.
- Grid and List render the same DOM for the same URL before and after.

**Decisions that are Igor's:**
1. **Who Explore is for.** If voters, build Concept B next; if journalists and researchers,
   Concept A.
2. **Palette:** one neutral hue (my preference), or keep red-to-green.
3. **Whether county-level rates appear at all before P1b lands,** given the known errors.
4. **The name.** "Explore" promises more than a pass-rate table delivers; "Pass rates" or
   "Patterns" would be plainer.
