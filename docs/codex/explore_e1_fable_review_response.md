# Explore E1 "Honest Explore": Fable's independent review

**Date:** November 13, 2026. **Reviewed:** commit `8029d2e9` on `phase0-election-status`.
**Verdict: ready with changes.** E1 does what it set out to do: I found no wrong number, and
no rate or shading below five measures anywhere. Three small things still mislead and
should change before release (F1-F3). The rest can wait for E2.

**What I did.** Read my review, the plan, the handoff and the code. Drove the preview at
`http://127.0.0.1:8917/` in headless Chromium (all other hosts blocked) at 1440, 768, 390
and 320 px. Recomputed the default table from the served `measures-data.json`. I did not
read the other reviewer's response, open a database, run the test suite or rerun the four
existing browser checks; for those I read the evidence in
`scraper/data/exports/explore_e1_20261113/`. Screenshots (27) are in
`scraper/data/exports/explore_e1_fable_review/`.

## Findings, ranked

**F1 (P2): "Difference from column rate" is mislabelled in the totals, and it is the
comparison my review warned against.**
- In the "All" row and the "All" column the baseline is the overall rate, not the column's
  (`generator.py:11665-11671`). "Ordinance, All: −5 pp" means 63% against 68% overall
  (`e1_1440_metric_baseline.png`).
- Under Topic by Region it reads "Statewide, Education: −21 pp" against a column that is
  mostly 2022-2024 local measures (`e1_1440_region_topic_baseline.png`).
- Small differences look exact: "Gann Limit, 1998-99: −15 pp" is 8 of 10.
- The legend runs −100 to +100 pp (`:11728`) while real values sit within ±27, so every
  cell gets nearly the same tint.
- **Fix:** drop the metric in E1.

**F2 (P2): the modal's "Pass rate by decade" bars cannot tell 0% from "too few" from
"none".** For Statewide, Education there are 11 decades and 4 visible bars
(`e1_1440_modal_region_topic.png`). The 1930s is a real 0%; the 1940s is "4 of 4", count
only; both are blank (`:11940-11953`). The values exist only as hover titles.
**Fix:** remove the chart in E1; E2c rebuilds it with numbers.

**F3 (P2): the old decade name survives where the reader looks next.** The row says
"1998-99", but its tooltip and screen-reader label say "1990s, Ordinance: 106 of 183
passed" (`:11759`), the modal title says "1990s — Ordinance" (`:11931`,
`e1_1440_cell_modal.png`) and the filter chip says "Decade: 1990s" (`:10252`).
**Fix:** pass the display label to all three.

**F4 (P3): Topic view gives the count but not the years.** Topic by Region says "Counted
years: 1911-2024". The region rows hold local records from six years only; the Statewide row
holds a century. **Fix:** one sentence, or the answer to handoff question 4 below.

**F5 (P3): on phones the table now starts lower.** At 390 px it begins 979 px down (it was
about 840); at 320 px, 1,056 px. Two of 13 columns show (one at 320). The side-scroll at
320 is fixed. The phone layout is E2c, but E1's three paragraphs made the wait longer.
**Cheap fix:** fold the two notes into a "How this is counted" disclosure on narrow screens.

**F6 (P3): empty cells are the loudest thing on the page.** "0 of 0 / no measures" sits in
a bordered white box (`explore.py:35`, `e1_1440_region_topic.png`), and its label reads
"0 of 0 passed; too few to show a rate". **Fix:** a quiet dash, labelled "no measures".

**F7 (P3): "Reset Explore" clears a search typed in the header box** without saying so
(`:11894-11897`). The chips make the active filters visible, which is the important part.
**Fix:** rename it "Reset view and filters".

**F8 (P3): the shading says little.** 29% and 100% are a faint step apart
(`explore.py:28`; `e1_1440_default_viewport.png`). The numbers do the work. A design point
for E2.

**F9 (P3), leftovers:**
- The active column toggle is white on gold at 2.41:1. It is older than E1 and outside the
  cell check.
- "Decade ↓" shows a descending arrow on an ascending list (`:11780`).
- A stale comment at `:11899`; the header row is still repeated as a footer.
- Year rows have 393 tab stops (E2b).
- Sorting Year rows by Gann Limit puts seven "100%" cells with 5-10 measures on top. The
  rule holds; a floor of 5 is low for sorting.

## 1. Did E1 fix what my review found?

| Review finding | Status | Evidence |
|---|---|---|
| §4.1.1 Coverage hidden | **Fixed** for the default; **partly** for Topic | 10,939 + 1,313 + 57 = 12,309 shown; Topic shows 3,112 and 9,140, not the years (F4) |
| §4.1.2 Threshold mode false | **Fixed** | Mode and "Close calls" removed. A dormant catalog filter still calls the helper (`:10891`) |
| §4.1.3 Cards rank extremes | **Fixed** | Removed |
| §4.1.4 Tiny cells look like results | **Fixed** | 48 combinations of columns, rows, metric and Min n: 0 cells under 5 with a rate or fill; they sort last |
| §4.1.5 Unlike things in one table | **Partly** | Default view is local only. Region by Topic keeps the Statewide row, and F1 compares across it |
| §4.1.6 Known data defects pass through | **Deferred (E3)**, disclosed | Note names repeated county portions and 2016-2021; county rows hidden (D3) |
| §4.1.7 Decade rows mislead | **Partly** | Row labels and order fixed; old name elsewhere (F3) |
| §4.1.8 "Pass" means different things | **Not fixed** | Recall and Advisory share the scale. Not in the plan |
| §4.3 No title or sentence | **Fixed** | Heading and coverage line |
| §4.3 Legend without numbers | **Fixed** | 0% to 100% swatches |
| §4.3 Red-to-green palette | **Fixed** (D2) | One slate hue, dark text |
| §4.3 Low n shown by fading | **Fixed** | "count only", 12 px |
| §4.3 Footer header; nested scroll | **Not fixed** | Not in the plan |
| §4.4 Hidden filters; Reset | **Fixed** | Chips, Clear, and Reset clears them (F7) |
| §4.4 No URL state or history | **Deferred (E2a)** | Reload still returns to Grid |
| §4.4 Modal: bars, "notable" | **Partly** | "Notable" removed; bars now ambiguous (F2) |
| §4.5 Phones | Overflow **fixed**; the rest **deferred (E2c)** | 320 px no longer scrolls sideways; F5 |
| §4.6 Contrast | **Fixed** for cells | Minimum 7.06:1; headers 5.6:1; toggle 2.41:1 (F9) |
| §4.6 Keyboard | **Deferred (E2a, E2b)** | 89 tab stops by default; Space and Escape still do nothing |
| §4.6 Screen readers | **Deferred (E2b)** | A real `h2` now; no caption, scope or `aria-sort` |

## 2. My §9 acceptance checks

| # | Check | Result |
|---|---|---|
| 1 | Default is Type by Decade, in order, labelled by years | **Pass** (1998-99, 2000-09, 2010-19, 2020-24) |
| 2 | Coverage counts reconcile with the catalog | **Pass**, with a note: it reconciles to the filtered catalog, 12,309 (§4) |
| 3 | Under 5: count, no percentage, no color; fixture for 0, 1, 4, 5 | **Pass** (`test_explore.py`; 48 live combinations) |
| 4 | Every cell's text contrast at least 4.5:1 | **Pass** (7.06:1) |
| 5 | Threshold mode, close calls and cards gone, with handlers | **Pass** |
| 6 | Active filter visible and clearable; drill down, return, clear | **Pass** (183 in the cell, 183 in Grid, 12,309 after Clear) |
| 7 | No page overflow at 320 px | **Pass** |
| 8 | Existing browser checks still pass | **Pass per the evidence folder**; not rerun by me |

## 3. New problems

- **Numbers.** None wrong. My recomputation matches every Bond cell (58, 71, 80, 63%), the
  totals (7,463 of 10,939, 68%) and the Bond average yes votes.
- **"Average yes vote".** Arithmetic is right. It is an unweighted average of each
  measure's yes share, which the label could say.
- **"Difference from column rate".** F1.
- **Totals row.** Right for pass rate, count and average; mislabelled under F1.
- **Cell modal and decade bars.** F2 and F3. A small cell's modal shows "2 of 2", no rate.
- **Region rows under Topic.** F4.
- **Rate or shading under five.** None found.
- **Reset clearing filters.** F7.
- **Grid and List.** No regression seen: Grid holds 12,309, List loads, no page errors.

## 4. The coverage line

It is honest, and the arithmetic is right. It should name what the default leaves out:
12,309 is 12,372 minus the 63 measures on the November 3, 2026 ballot. One clause does it:
"The 63 measures on the November 3, 2026 ballot are not included; their results are not
final."

It is also long and partly in house language. "Total for the current catalog filters",
"the statewide archive" and "the history repair" mean little to a reader. Suggested:

> **10,939 local measures, 1998-2024, with a recorded result.** Not counted: 1,313 with no
> measure type (all but two are statewide propositions), 57 with no recorded result, and the
> 63 measures on the November 3, 2026 ballot.

Then one "How this is counted" disclosure for sources, county portions, 2016-2021 and the
note that county breakdowns are hidden while the local history is corrected.

## 5. Design quality

**No longer wrong; not yet good.** The page is trustworthy, which it was not. But the
default is 52 near-identical slate cells under half a screen of text, it answers one
question, and a phone shows two columns after three screens of scrolling.

**Most valuable change for E2: do E2c first**, the list form for one chosen column or row,
with a bar and the count on each line. It fixes phones, restores the visual signal the
neutral palette gave up, and gives the trend with numbers that the modal's bars fail to.

## 6. The handoff's open questions

1. **Coverage total:** yes, name the 63 (§4).
2. **"Difference from column rate":** drop it (F1).
3. **`exploreFilterToCounty`:** leave it for E2a. It duplicates 30 lines of
   `matrixDrillDown` (`:11977-12005`, `:12013-12041`); fold the two together when drill-down
   gains history entries, and rename then.
4. **Region rows mixing statewide and local:** take Statewide out of Region rows and count
   those propositions under "not counted: no region". Topic by Decade and by Year still mix
   the two, so the real fix is a Statewide / Local switch for Topic view in E2. Until then,
   add the sentence in F4.
