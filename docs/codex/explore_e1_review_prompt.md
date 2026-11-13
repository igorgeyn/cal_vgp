# Review request: Explore E1 "Honest Explore"

**Type:** review only. **Branch:** `phase0-election-status`, code commit `8029d2e9`.
**Read:**
- [`docs/plans/explore_renovation_plan_20261112.md`](../plans/explore_renovation_plan_20261112.md)
  §3–§5 (E1), especially the acceptance checks and the preservation gate;
- [`docs/plans/explore_e1_handoff_20261113.md`](../plans/explore_e1_handoff_20261113.md);
- [`docs/plans/explore_review_20261112.md`](../plans/explore_review_20261112.md), the problems
  E1 is meant to fix.

Codex wrote the code. The coordinator ran the final checks and committed it. You wrote neither.

## Check

1. **Plan coverage.** Does each of E1's nine items, plus the flag flip, do what the plan asks?
   Review `git show 8029d2e9 -- scraper/src/website/generator.py` in full. It's large: about
   +107 / −678.
2. **Honesty.** Can Explore still show a number the data can't support?
   - Look at each remaining metric, especially "Difference from column rate" and "Average
     yes vote".
   - Look at Region rows, which mix statewide and local measures under Topic.
   - Look at the totals row, the cell modal and the decade bars.
   - Does any rate or shading appear for n < 5 anywhere: cells, totals, the modal, the legend?
3. **Coverage line.** Is the arithmetic right under filters? Does it reconcile with the
   catalog, and should it name what the default filters exclude? The handoff's question 1
   covers this.
4. **Regressions.**
   - Removed code: did anything outside Explore call it? Check `getMeasureThreshold`,
     `CA_REGIONS`/`countyToRegion`, `matrixDrillDown`, `exploreFilterToCounty`, the filter-token
     helpers and `clearAllFilters`.
   - Does `resetMatrixControls` → `clearAllFilters` now have side effects outside Explore?
   - Are the new CSS rules scoped (`.matrix-wrapper`, `.matrix-cell-modal`)?
5. **Accessibility.** Look at the cells' accessible names, keyboard (Enter/Space), focus, the
   chips' labels, and contrast. Keyboard and modal semantics are E2a, so note gaps there; don't
   fail E1 for them.
6. **Tests and checks.** Do `tests/test_explore.py` and `scripts/check_explore_browser.py`
   test what they claim? Could the browser check pass while the page is wrong?
7. **The handoff's open questions 1–4:** give a recommendation for each.

## How to verify

Use the plan's §4 toolkit, or reuse the evidence in `scraper/data/exports/explore_e1_20261113/`
(gitignored), including `compare.json`, `index.diff` and the browser reports. If you rebuild,
use a SQLite backup copy of the production DB and `--as-of 2026-11-12`.

## Constraints

- Review only. Write no code; no commits beyond the response file; no push.
- No network.
- Production DB read-only (`mode=ro` or a backup copy).

## Please return

Write `docs/codex/explore_e1_review_response.md` with:
- a verdict: **ready**, **ready with changes** or **not ready**;
- findings ranked by severity, with `file:line` evidence;
- answers to 1–7;
- anything that must change before release.

Commit only that file.
