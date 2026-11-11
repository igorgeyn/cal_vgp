# Codex review request: layout proposal (Direction A), post-election

**Type:** design review only. Change no code and no data.
**Branch:** `phase0-election-status`, local, at or after `f122cf05`.
**Why now:** Igor approved Direction A on November 11, 2026, on the condition that you
review it first (decision 3 in the
[completion plan](../plans/local_measures_completion_plan_20261105.md#8-decisions-for-igor)).
This is the review the proposal's §7 was written for.

## Read

1. [`docs/plans/measure_layout_design_proposal.md`](../plans/measure_layout_design_proposal.md),
   in full. §7 is the implementation handoff written for you, and §8 lists the open design
   decisions.
2. The mockups: [`docs/design/measure-layouts/index.html`](../design/measure-layouts/index.html),
   `a-slate-directory.html`, `a-components.html` and `screens/`.
3. Completion plan §5 (what each new card gets), §6 (results and comparisons tab) and
   Phase 3/3b.
4. The current explorer, for feasibility: `scraper/src/website/generator.py`,
   `county_content.py`, `local_measure_context.py` and `election_status.py`.

## What changed since the proposal (October 8)

- **The election is over.** The proposal assumed upcoming measures. Every card now needs a
  result state:
  - Results pending, then unofficial, then certified.
  - Yes % against the threshold, for example "Needs 55%" beside "52.3% yes".
  - Passed or failed, with a source link.
- **Scale.** The proposal designed for 14 props, 20 San Bernardino measures and 29 San
  Mateo measures. Coverage is now going to all 53 counties with measures, about 460 local
  measures.
  - Los Angeles alone has 68.
  - The county picker has to handle 53 counties; the proposal's two-option segmented
    control won't.
- **Same-year selection.** `election_date` replaces `year == 2026`.
- **A new results and comparisons tab** (plan §6), as both a modal tab and a section on the
  static pages.
- **Explanations.** New local cards ship with the official question and results only (Igor's
  decision 2). The directory cannot assume a "first sentence of the CalBallot explanation"
  for most cards.

## Questions

1. **Validity at the new scale.** Is Direction A still right for ~460 measures in 53
   counties with results? What breaks first: the phone length, the county picker,
   find-by-place, or the grouping into four categories?
2. **Result state.** Propose the card anatomy and the modal/page anatomy for each state:
   results pending, unofficial, certified passed or failed, withdrawn, result unknown
   (historical). How should the threshold read, and how should a multi-county measure show
   its combined result first and its county share as a share?
3. **Cards without explanations.** What goes in the slot the explanation used to fill: the
   official question truncated, type and threshold only, or something else? Keep it true
   and not misleading.
4. **County picker for 53.** Select, typeahead or a grouped list? URL state, and how
   permalinks and the back button behave. The proposal's select/radio cutoff now applies.
5. **Results tab.** Is §6's content order right for a modal tab and for a static-page
   section? What must stay visible on a phone? What is the failure mode when cohorts are
   tiny (n < 5)?
6. **Proposal §8 decisions 1–4.** Do you agree with each recommendation, now that the
   election has passed? Decision 4 is money on statewide cards.
7. **Implementation slicing.** Break Phase 3 into reviewable chunks that each ship
   something true. Name the first chunk and its acceptance checks, including preservation
   gates for historical and statewide pages.
8. **Anything in §7's handoff** that is wrong given the current code.

## Constraints

- Review only.
- If you need to render something, use a scratch folder outside the repo.
- Production database read-only, and only through the SQLite backup API.
- No live network checks; no push.

## Please return

Write `docs/codex/layout_direction_a_review_response.md`:
- a verdict (ready / ready with changes / rethink);
- answers to questions 1–8;
- a severity-ranked list of findings;
- your proposed Phase 3 chunk list.

Commit only that file.
