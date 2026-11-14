# Codex recheck request: Explore E1 fix pass 2

**Type:** review only. **Branch:** `phase0-election-status`; the commit is in the handoff.
**Read:** your fix-pass review, [`explore_e1_fixpass_review_response.md`](explore_e1_fixpass_review_response.md),
and the "Fix pass 2" section of
[`docs/plans/explore_e1_handoff_20261113.md`](../plans/explore_e1_handoff_20261113.md).

You asked for **N1 to be fixed and independently rechecked before E1 closes**. The coordinator
(Claude) wrote fix pass 2.

## Check

1. **N1.** Rerun your probe: catalog Level = Local, its county dropdown = Yuba, open Explore,
   Bond 2020–24, then **View matching catalog records**, then return. Also do a row-header
   drill and a Region drill.
   - Are the records still Yuba's?
   - Is the dropdown in sync?
   - Is the return counts only?
   - Does a statewide drill clear the county visibly?
2. **N2.** Under County, `levelCounty`, Passed and Failed:
   - Are rate and average controls gone or disabled?
   - Do count sorts order by totals?
   - Is the reader's metric restored when the filter is removed?
3. **N3.** Run the drill / return / level-switch sequence, and a catalog level chosen before
   entering Explore. Is there any remaining empty-intersection trap? Is any county filter
   discarded silently?
4. **Other.** Is there no broadened drill, from either the row header or the modal?
5. **Regressions** in Grid/List, the catalog filters and chips, or the level and county
   controls. Is every changed line Explore-scoped?
6. **Release:** is E1 now ready to release?

Evidence is in `scraper/data/exports/explore_e1_20261113/fixpass2/` (gitignored), including
`e1_fixpass2.py` and `e1_fixpass2_tests.py`.

## Constraints

- Review only.
- No network.
- Production DB read-only.
- No push.

## Please return

Write `docs/codex/explore_e1_fixpass2_recheck_response.md` with:
- a verdict: **ready to release**, **ready with changes** or **not ready**;
- findings with evidence;
- answers to 1–6.

Commit only that file.
