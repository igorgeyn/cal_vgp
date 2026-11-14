# Prompt: review Codex's "Honest Explore" (E1) against your own Explore review

**For:** Fable, in Claude Code desktop, on branch `phase0-election-status`.
**Type:** review only. No code changes and no commits.

---

You wrote the Explore review (`docs/plans/explore_review_20261112.md`). Codex then built its
first chunk, "Honest Explore" (E1), from the plan in
`docs/plans/explore_renovation_plan_20261112.md`. The coordinator ran the final checks and
committed it as `8029d2e9`. You didn't write this code, so review it as an outsider.

A separate Claude reviewer agent is also reviewing E1, into
`docs/codex/explore_e1_review_response.md`. **Don't read that file before you've finished your
own review**; the point is two independent reads. Don't edit it either.

## Read

1. Your own review, especially §4 (the audit) and §9 (the first chunk and its acceptance
   checks).
2. The plan, §2–§5 (E1).
3. `docs/plans/explore_e1_handoff_20261113.md`. It covers what was built, the evidence, and
   four open questions.
4. The code: `git show 8029d2e9`, especially `scraper/src/website/generator.py` (about
   +107 / −678), the new `scraper/src/website/explore.py`, `scraper/tests/test_explore.py` and
   `scraper/scripts/check_explore_browser.py`.

## Use it

The preview at **http://127.0.0.1:8917/** serves the E1 build; Explore is in the view switcher.
Use it the way your three readers would: a voter, a journalist checking "school bonds almost
always pass", and a researcher defining a sample.
- Change columns, rows, metric and Min n. Sort, open a cell, drill down to Grid and come back,
  and use the filter chips and Reset.
- Do it at 1440, 768, 390 and 320 px.
- Save screenshots in `scraper/data/exports/explore_e1_fable_review/` (gitignored).

Use only `127.0.0.1:8917`; don't start or stop that server.

## Judge

1. **Did E1 fix what your review found?** Take each finding in your §4.1 (statistical honesty),
   §4.3 (layout), §4.4 (interaction), §4.5 (phones) and §4.6 (accessibility). Mark it fixed,
   partly fixed, not fixed, or deferred by the plan to E2/E3. Give evidence for each.
2. **Your §9 acceptance checks 1–8:** pass or fail, with evidence.
3. **New problems** E1 introduced: wrong numbers, misleading labels, broken interactions, or
   regressions in Grid/List or the catalog filters. Look especially at:
   - the remaining metrics ("Average yes vote", "Difference from column rate");
   - the totals row;
   - the cell modal and its decade bars;
   - Region rows mixing statewide and local measures under Topic;
   - whether any rate or shading still appears for n < 5;
   - whether `resetMatrixControls` clearing the catalog filters surprises the reader.
4. **The coverage line.** Is it honest and clear? It reports 12,309, not 12,372. Should it name
   what the default filters leave out?
5. **Design quality.** Is it now good, or only no longer wrong? What is the single most
   valuable change for E2, given what you now see?
6. **The handoff's open questions 1–4:** recommend an answer for each.

## Output

Write `docs/codex/explore_e1_fable_review_response.md` with:
- a verdict: **ready to release**, **ready with changes**, or **not ready**;
- findings ranked by severity, with `file:line` or screenshot evidence;
- the findings table for 1;
- the checks for 2;
- answers to 3–6.

Keep it to about two to three pages.

## Limits

- **Review only.** Edit no code or data; don't commit. The only files you create are the
  response and the screenshots.
- **No network** beyond `127.0.0.1:8917`.
- **Databases read-only** (`mode=ro`) if you query one at all; say so if you do.
- **No builds, pushes or branch changes.**

Reply with a five-line summary, your verdict, and your top three findings, one line each.
