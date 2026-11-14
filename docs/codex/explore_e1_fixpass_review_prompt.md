# Codex review request: Explore E1 fix pass

**Type:** review only. **Branch:** `phase0-election-status`, fix-pass commit `a496421c`. It
sits on top of E1, commit `8029d2e9`.

## Background

- **E1** ("Honest Explore") was built by Codex. The coordinator verified and committed it.
- **Two independent reviews** both returned **ready with changes**:
  - the Claude reviewer, [`explore_e1_review_response.md`](explore_e1_review_response.md),
    findings R1–R9;
  - Fable, [`explore_e1_fable_review_response.md`](explore_e1_fable_review_response.md).
- **Igor approved the merged fix list.** The coordinator (Claude) wrote the fix pass, so you're
  reviewing the coordinator's code. Its handoff is the "Fix pass" section of
  [`docs/plans/explore_e1_handoff_20261113.md`](../plans/explore_e1_handoff_20261113.md).

The plan is [`docs/plans/explore_renovation_plan_20261112.md`](../plans/explore_renovation_plan_20261112.md).
E2c has been reordered ahead of E2a and E2b.

## Check

1. **Is each review finding actually closed?** Give a disposition table: closed, partly closed
   or open, with evidence. Cover Claude R1–R9 and Fable's three top findings plus its
   question 4.
2. **Level separation.**
   - Does anything still pool statewide and local measures: cells, row/column/grand totals,
     the modal, the coverage line, sorting, drill-downs?
   - Is "Measure Type = local only" right?
   - Does the Local/Statewide toggle reset or keep state sensibly with Reset, column switches and
     drill-down/return?
3. **Counts-only filters.**
   - Under a County filter (`county` or `levelCounty`) or a Passed/Failed Status filter, can a
     rate, shading, legend, average-yes or sort-by-rate still appear anywhere?
   - Is the caution clear?
   - Are other filters correctly *not* forced to counts only, and is that the right call?
4. **Coverage line.**
   - Check the arithmetic under the default view, a county filter, a year filter, a search, and
     Topic in each level.
   - Is the "63 current-election measures" count computed by the same rule as
     `applyFilters`' default exclusion, and is it 0 whenever that exclusion is off?
   - Does `Explore.yearRanges` read honestly?
5. **Drill-downs.**
   - `applyExploreRowFilter` now sets `currentFilters.level`. Does that interact badly with a
     level the reader had chosen in the catalog, or with `levelCounty`?
   - The "Other" region guard.
6. **Regressions outside Explore.** Grid/List, the catalog filters and chips, `clearAllFilters`,
   and the hidden Insights.
7. **Tests and checks.**
   - Do the new Node tests and the extended `check_explore_browser.py` pin these behaviours,
     or could they pass while the page is wrong?
   - The checker's `expected_coverage` has an independent `current_excluded`. Is it truly
     independent of the page's logic?
8. **Release readiness.** Is E1 plus this fix pass ready to release, given Igor's rule that
   Explore must not state numbers the data can't support?

## How to verify

- Use the plan's §4 toolkit, or the evidence in
  `scraper/data/exports/explore_e1_20261113/fixpass/` (gitignored): `compare.json`,
  `index.diff`, the browser reports, and the edit scripts `e1_fixpass.py` and
  `e1_fixpass_tests.py`.
- The published-code baseline and the candidate are scratch builds made with
  `--as-of 2026-11-12`. If you rebuild, use a SQLite backup copy of the production DB.

## Constraints

- Review only.
- No network.
- Production DB read-only (`mode=ro` or a backup copy).
- No push.

## Please return

Write `docs/codex/explore_e1_fixpass_review_response.md` with:
- a verdict: **ready to release**, **ready with changes** or **not ready**;
- the disposition table;
- new findings ranked by severity, with `file:line` evidence;
- answers to 2–8.

Commit only that file.
