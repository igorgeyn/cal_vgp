# Explore E1 "Honest Explore": handoff

**Date:** November 13, 2026. **Branch:** `phase0-election-status`.
**Plan:** [`explore_renovation_plan_20261112.md`](explore_renovation_plan_20261112.md) §5 E1.
**Built by:** Codex. It hit its usage limit before the final regression and preservation
checks, so it made no commits and wrote no handoff.
**Verified, committed and documented by:** the coordinator (Claude), who didn't write the code.
**Status:** built and verified; **independent review pending**; not published.

## What changed

| Plan item | Done | Where |
|---|---|---|
| 1. Default view: Measure Type by Decade, time order, real-year labels ("1998–99", "2020–24") | Yes | `matrixState` defaults; `Explore.decadeLabel` |
| 2. Title and coverage line, computed from the filtered set | Yes | `renderExploreCoverage`; `Explore.coverage` |
| 3. Threshold mode, close calls, trap metric, summary cards removed | Yes | Shared `getMeasureThreshold` kept: the catalog's threshold filter uses it |
| 4. n < 5: "3 of 4", no rate or fill; Min n defaults to 5; such cells sort last | Yes | `Explore.cell`, `Explore.compareCells` |
| 5. One neutral slate hue, dark text, a legend with numbers | Yes (D2) | `Explore.tint`; `explore.py` `STYLE` |
| 6. No county rows; Decade, Year and Region only | Yes (D3) | `groupingOptions`, `setMatrixRowGrouping` |
| 7. Active-filter chips with Clear; Reset also clears filters | Yes | `renderExploreFilters`, `resetMatrixControls` |
| 8. Dead renderer deleted | Yes | About 256 lines after `return renderMatrixV2()` |
| 9. Wording: tooltips and welcome line; "notable" list removed | Yes | "Recorded outcomes by type and period" |
| E0 flag flipped: `SHOW_EXPLORE = True` | Yes | Explore is visible again **in this build only** |

New files:
- `scraper/src/website/explore.py`: pure helpers, as `SCRIPT` and `STYLE`;
- `scraper/tests/test_explore.py`: Node tests for the helpers;
- `scraper/scripts/check_explore_browser.py`: the browser check.

`scraper/tests/test_explore_hidden.py` now pins the flag in both states with E1's wording.

## Evidence

Gitignored: `scraper/data/exports/explore_e1_20261113/`. Scratch builds were made with
`--as-of 2026-11-12` from a SQLite backup copy:
- the **baseline** from a clean worktree at `65ad0215`, which is the published code (PR #9);
- the **candidate** from the working tree with Codex's changes.

**Preservation gate** (`compare.json`, `index.diff`):
- No files added or removed. **All 12,372 measure pages are byte-identical.**
- `measures-data.json`: same IDs; the only changed field is `last_seen_at` (129, known).
- `sitemap.xml` and `use-calballot/index.html` are byte-identical.
- `index.html`: 55 hunks, all in Explore CSS/JS, the Explore view button/card, the welcome
  line, the `setView` Explore guard and the data cache key.
- **Grid and List DOM** (`#resultsContainer` outerHTML, fixed clock): identical for `/`,
  `?view=list` and `?view=list#page=3`.

**Browser checks, all exit 0:**
- `check_explore_browser.py` at 1440, 768, 390 and 320 px:
  - coverage 10,939 counted + 1,313 without a type + 57 without an outcome = 12,309, the
    catalog under default filters;
  - decades 1998–99, 2000–09, 2010–19 and 2020–24;
  - minimum cell contrast 7.06:1 (synthetic small cells 8.18:1);
  - no page errors.
- Election status at the real clock (63 rows) and across Pacific midnight; county content
  (49 × 3 widths); Grid/List navigation.

**Tests:** 176 targeted tests pass. Full suite: 755 passed, 1 skipped; known baseline only
(`test_models` 1, database/dedup 17).

## Open questions for the reviewer and Igor

1. **The coverage total** (12,309) is the catalog under default filters, not all 12,372
   records. Should the line say which records the default filters leave out (likely the 63
   current-election measures)?
2. **"Difference from column rate" metric.** It's kept, and it isn't a ranking, but it
   invites comparing cells. Keep it or drop it?
3. **`exploreFilterToCounty`** now handles decade, year and region rows. The name is stale, but
   renaming it is out of E1's scope.
4. **Region rows mix statewide and local measures.** Fable's review flagged unlike things in
   one table. Statewide drops out under Measure Type (no type), but not under Topic.

## Fix pass, November 13, 2026 (after both reviews)

Two independent reviews both said **ready with changes**: the Claude reviewer
([response](../codex/explore_e1_review_response.md)) and Fable
([response](../codex/explore_e1_fable_review_response.md)). Igor approved the merged fix list.
The coordinator made the fixes. **Codex reviews this pass.**

| Fix | Source | Change |
|---|---|---|
| Statewide and local pooled | Claude R1, Fable Q4 | Measure Type counts **local measures only**. Topic shows one level at a time, with a **Local / Statewide** toggle defaulting to Local, so no row, column or total pools the two. Region rows lose Statewide under Local. Also covers R6: 2026 statewide instrument types can't become Measure Type columns. |
| County rates via the catalog filter | Claude R2 | With a County filter: **counts only**, no rate, shading or legend, plus a visible caution. D3. |
| Status filter turns rates into 100% or 0% | Claude R5 | A Passed/Failed Status filter also gives counts only, with a caution. |
| "Difference from column rate" | Both | Removed: the metric, its legend, sort and presentation, and the baseline fields. |
| Modal decade bars | Fable | Removed until E2c rebuilds them with numbers. |
| Leftover "1990s" | Both | Cell `aria-label`/`title` and the modal title use the row's real-year label. The catalog's own "Decade: 1990s" chip is unchanged: it is a calendar-decade filter, which is correct there. |
| Coverage line | Both | Now names the level, the other level not shown, and **the 63 current-election measures** outside the catalog view. "Without a recorded outcome (pending, unknown or withdrawn)". Counted years are listed as ranges ("2011, 2013, 2015, 2022–24"). Notes moved into a collapsed "About these figures". |
| Phone legend | Claude R7 | The first swatch no longer stretches to a full line. The table still starts low on phones; that's E2c's job. |
| Small fixes | Claude R9 | The average-yes sort uses `max(5, minN)`. Drill-downs carry Explore's level into the catalog, and the modal notes the list includes records without an outcome. "Other" region rows no longer set a bogus county. Row-header and cell drill-downs share `applyExploreRowFilter`. Dead code is gone (county fall-through, `rowLabel`/`colLabel`, the "Jurisdiction" header, an orphan comment). The row header no longer shows a misleading "↓" for time order. |
| Threshold helpers | Claude R8 | Kept, but now commented as unreachable and not to be revived before E3. **Correction:** E1's handoff said the catalog filter uses them; nothing can set that filter any more. |

**New tests.**
- Node tests for `Explore.yearRanges` and the count-only reason.
- `check_explore_browser.py` now also checks:
  - level separation (Statewide rows only under Statewide, none under Local);
  - counts only under County and Status filters;
  - no `baseline` option;
  - real-year `aria-label` and modal title, and no decade chart;
  - the current-election count;
  - the phone legend swatch width;
  - that a drill-down sets the level.

**Evidence** (`scraper/data/exports/explore_e1_20261113/fixpass/`), against the same published
baseline:
- All 12,372 measure pages are byte-identical. JSON changes only `last_seen_at` (129). Sitemap
  and use-calballot are unchanged. Grid/List DOM is identical for 3 URLs. All 64 `index.html`
  hunks are Explore-scoped.
- **Explore check** at 1440/768/390/320 passes. Default coverage: 10,939 counted, 2 without a
  type and 56 without a recorded outcome, out of 10,997 local measures. 1,312 statewide
  propositions are not shown, and 63 current-election measures are outside the view
  (10,997 + 1,312 = 12,309). The minimum contrast is 7.06:1.
- **Other checks:** the status check (now and across midnight), county content and navigation
  all pass.
- **Tests:** full suite 760 passed, baseline only.

**Deferred to E2c** (plan reordered: E2c first):
- transposing the table when it fits;
- the phone list form;
- rebuilding the decade chart with numbers.
