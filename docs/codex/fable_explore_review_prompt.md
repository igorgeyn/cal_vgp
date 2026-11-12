# Prompt: review the Explore tab and propose improvements

**For:** Fable, in Claude Code desktop, on branch `phase0-election-status`.
**Type:** review and proposals only. No code changes.

---

Igor thinks CalBallot's **Explore** tab is mediocre: poorly designed and laid out, with a lot
of room for improvement. He wants a comprehensive, candid review and a ranked set of
suggestions. Be specific and opinionated. Where a call is really his (taste, editorial voice,
product direction), say so and give options rather than deciding.

## Context

- **Product.** CalBallot is a free, neutral database of California ballot measures, 1998 on:
  about 12,400 records, 14 statewide and 49 local measures on the November 3, 2026 ballot, and
  ~11,000 historical local measures from CEDA. Read `CLAUDE.md` for the hard rules, and the
  "paradigm-as-moat" note: free deterministic facts, with editorial briefings on demand.
- **Explore today.** A topic × jurisdiction matrix of pass rates. It is one of the views next to
  Grid and List (`setView('explore')`).
- **Code.** All of it is in `scraper/src/website/generator.py`, with JavaScript inside a Python
  f-string, so braces are doubled:
  - markup: `id="exploreView"` / `exploreViewCard` (around lines 815 and 934);
  - CSS: under `/* Explore Matrix` (around line 2760);
  - JS: from `// ── Explore Matrix` (around line 11628) through `renderExploreCell` and
    `exploreFilterToCounty` (around 12060 and 12576);
  - visibility: `updateViewVisibility()`.

  Line numbers drift, so search for the names.
- **Insights is hidden** (`SHOW_INSIGHTS = False`). Igor plans to renovate it separately. Explore
  and Insights overlap (pass rates, topics, geography), so say how the two should divide the
  work.
- **Data caveats that bear on any pass-rate display.** Read these before proposing statistics:
  - `docs/KNOWN_ISSUES.md`;
  - `docs/plans/ceda_reconciliation_20261112.md`, your own work: 28 wrong rows, the 2014
    keys, 2016-2021 unchecked;
  - the multi-county question in `docs/plans/ceda_backfill_design_20261112.md`;
  - `docs/codex/layout_direction_a_review_response.md` answer 5, the rules for small cohorts
    and comparisons: n < 5, matched cohorts, no ranks from tiny samples.

  Explore must not present numbers more confidently than the data allows.
- **Live preview.** http://127.0.0.1:8917/ serves the current release candidate. Open it, and
  switch to Explore with the view switcher or `setView('explore')`.

## What to do

1. **Use it.** In a browser, use Explore as three people would:
   - a voter curious about their county;
   - a journalist checking a claim, such as "school bonds almost always pass";
   - a researcher defining a sample.

   You can drive it with Playwright, or a local browser, against `127.0.0.1:8917` only. Take
   screenshots at 1440, 768, 390 and 320 px, and save them in
   `scraper/data/exports/explore_review_20261112/` (gitignored).
2. **Read the code** to learn what each number means: how rows and columns are chosen, the
   denominators, the baseline and color scale, sorting, the totals row, and what a cell click
   does.
3. **Audit:**
   - **Usefulness.** What questions does it answer, and which obvious ones can't it answer?
   - **Layout and visual design:** hierarchy, density, color, legend, labels, empty and
     low-n cells, and what the reader sees first.
   - **Interaction:** controls, discoverability, the cell drill-down into the catalog, URL
     state and Back, and keyboard use.
   - **Phones:** does a matrix even work at 390/320?
   - **Accessibility:** contrast, color-only meaning, screen-reader names, and focus.
   - **Statistical honesty:** small n, duplicates, coding errors, and comparisons the data
     can't support.
   - **Performance** on 12,400 records.
4. **Propose.**
   - Ranked suggestions in three tiers:
     - **quick wins**, under half a day each;
     - **medium**, 1–3 days;
     - **ambitious redesigns**.
   - For each: what changes, why it's better, any data it depends on, effort, risk, and how
     a reviewer would verify it.
   - **Two or three alternative concepts** for what Explore could be. Give each an ASCII
     wireframe for desktop and phone, and say who it serves best. Think beyond a matrix
     where it helps.
   - **What not to do**, and why.
   - **A recommended first chunk:** scope, the files it touches, acceptance checks, and a
     preservation gate: which pages and data must stay byte-identical.

## Output

Write `docs/plans/explore_review_20261112.md`, about 3–5 pages plus wireframes. Cite
`file:line` where it matters, and reference screenshots by filename.

## Limits

- **No code or data changes,** and no commits. The only files you create are the review and the
  screenshots.
- **No network** beyond `127.0.0.1:8917`. Don't start or stop that server.
- **Databases are read-only** (`mode=ro`) if you query one at all. Say so in the review if you
  do.
- **No builds, pushes or branch changes.**

Reply with a five-line summary, your top five suggestions in one line each, and the path to
the file.
