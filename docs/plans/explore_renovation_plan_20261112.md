# Explore renovation plan

**Date:** November 12, 2026. **Branch:** `phase0-election-status`.
**Executor:** Codex, one chunk at a time. **Coordinator:** Claude. **Approver:** Igor.
**Source:** [Fable's Explore review](explore_review_20261112.md), which has the evidence,
screenshots and wireframes. The coordinator checked its most serious finding (threshold
mode) against the code and the data. Read the review before starting; this plan doesn't
repeat its evidence.

---

## 0. How to run this plan

1. Read `CLAUDE.md`, [`docs/LESSONS_LEARNED.md`](../LESSONS_LEARNED.md), the review above, and
   this plan in full.
2. Check §2. **Don't start a chunk whose blocking decisions are unanswered.** Stop and ask.
3. Do **one chunk**, then stop. Each chunk ends with:
   - commits, with files named explicitly;
   - an evidence folder;
   - a short handoff note: what changed, the evidence, and open questions;
   - a review prompt in `docs/codex/` for the reviewer.

   The reviewer is never the author of the chunk. Add the review prompt to
   `docs/codex/PENDING.md`.
4. **Never publish.** No push, no merge, no change to the root `index.html` /
   `measures-data.json` or the root `measures/` pages, and no R2 writes. A release happens
   only after review and Igor's go-ahead, through the coordinator's release workspace (§7).
5. Update [`local_measures_checklist_20261107.md`](local_measures_checklist_20261107.md) only in
   the "Explore" section this plan adds (§9). Leave other sections to the coordinator.

## 1. The problem, in short

Explore is a pass-rate matrix (`setView('explore')`). Fable found that, today:

- **It hides what it drops.** The default view (Topic by County) counts 3,112 of 12,252
  decided measures: local topics exist only for 2011, 2013, 2015 and 2022-2024.
- **Threshold mode is false.** `getMeasureThreshold` reads `vote_threshold`, which is set on
  49 rows; every other measure defaults to "Simple majority", including about 2,484 the source
  codes two-thirds and about 2,324 it codes 55%. "Close calls" inherits the error.
  **Confirmed by the coordinator.**
- **The summary cards rank noise.** For example, Yuba / Education at 7% is mostly 12 bonds
  that failed together in 2024.
- **Small cells look like results.** 188 of 299 cells have fewer than 5 measures, and sorting
  puts them first.
- **Decade rows mislead.** "1990s" is only 1998-99, and they sort by count, not by time.
- **Accessibility fails.** No cell reaches 4.5:1 contrast, there are 390 tab stops, the modal
  has no dialog semantics, and Escape doesn't close it.
- **Phones fail.** The matrix starts about 840 px down and shows 3 of 12 columns. At 320 px
  the page scrolls sideways.
- **It has no URL state.** Back leaves the site, and reload returns to Grid.
- **Known data defects pass straight through:** the CEDA wrong rows, multi-county shares and
  2016-2021 unverified. Explore and a county card can give two answers for the same cohort.

One view holds up: **Measure Type by Decade** (51 of 52 cells with n ≥ 10).

## 2. Decisions

| # | Decision | Recommendation | Status | Blocks |
|---|---|---|---|---|
| D1 | Hide Explore in the release now being prepared (P0.4)? | **Yes**, by a flag, as with Insights | **Pending Igor** | E0 |
| D2 | Palette | **One neutral hue**, dark text on light tints. Red-to-green reads as good/bad on a neutral site and fails for color-blind readers | **Pending Igor** | E1 |
| D3 | County-level rates before the CEDA repair (P1b) lands | **Hide the county row grouping until P1b**; keep Region, Decade and Year | **Pending Igor** | E1 |
| D4 | Who Explore is for | Journalists and researchers (Concept A); voters through the county page in the layout work | Pending Igor | E4 only |
| D5 | The name | Keep "Explore" for now; revisit at E4 | Pending Igor | E4 only |

If Igor approves a recommendation, the coordinator marks it here. Don't infer approval.

## 3. Hard rules for every chunk

- **The template.** `scraper/src/website/generator.py` is one f-string, so every JS/CSS brace is
  doubled. Run `python -c "import ast; ast.parse(open(...).read())"` after each edit, and check
  the generated HTML, not only the source.
- **Scope CSS** under the Explore container (`.matrix-wrapper` or a new `.explore-*`
  namespace). Never assume a class name is unique (`CLAUDE.md`).
- **Shared helpers.** Before deleting a function, `grep` every caller. In particular:
  - `getMeasureThreshold` / `getThresholdLabel` may serve other surfaces;
  - `CA_REGIONS` / `countyToRegion` are shared.
- **Keep `id`** on every `BallotMeasure` (`generate_site.py` `valid_fields`). Explore doesn't
  need new JSON fields; if a chunk seems to need one, stop and ask.
- **Pure logic goes in a module.** New pure logic (cell display rule, decade labels, coverage
  counts) goes in a small module, e.g. `scraper/src/website/explore.py`. It exports `STYLE` /
  `SCRIPT` constants like `browse_navigation.py`, so Node can test it like
  `ELECTION_STATUS_SCRIPT` in `tests/test_election_status.py`. Don't move the whole Explore
  block in E1; that would bloat the diff.
- **No model-generated prose** about cells. Use fixed templates only (the deterministic-cards
  rule).
- **No rankings, "top/bottom" lists or significance tests** in Explore (review §5 and §8).
- **Production DB is read-only.** Builds use a SQLite **backup-API** copy (§4). No network.
- **Commits.** Detailed messages with the trailer
  `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>` per `CLAUDE.md`, or
  your own attribution if Igor prefers. Never `git add .`.

## 4. Build and verify toolkit

**Baseline first.** Before a chunk's first edit, build a scratch site from the current HEAD,
and keep it as that chunk's baseline. Every comparison in that chunk is against **this
baseline**, not the live site.

**Scratch build** (outside the repo, e.g. `%TEMP%\explore-<chunk>\<label>\`):

1. Copy `scraper/data/ballot_measures.db` with the SQLite backup API, from a `?mode=ro` URI
   source into the scratch folder.
2. Build the environment with `clean_environment()` from
   `scraper/scripts/build_release_bundle.py`. The repo has no `model/` folder, so set
   `CALBALLOT_EMBEDDING_MODEL=all-MiniLM-L6-v2`, with the HF cache offline.
3. Run `scraper/scripts/generate_site.py --db <copy> --output <site>/index.html --force
   --strict --as-of 2026-11-12`. A strict build needs the gitignored
   `scraper/data/finance/finance_statewide_v2.db` and `_v3.db`; use the main checkout, or copy
   them into a worktree.
4. Run `build_measure_pages.py --site-dir <site>`.

Use the same `--as-of` for the baseline and the candidate.

**Comparison script.** Write it once, in the chunk's evidence folder. It reports:
- file counts, and files added or removed;
- every changed file;
- for `measures-data.json`, changed fields per ID. `last_seen_at` regenerates on 129 rows,
  so report it separately and don't use it as a blanket exemption;
- for `index.html`, a unified diff restricted to lines. Each changed line must sit inside the
  Explore blocks, the view buttons/tooltips, the welcome line, or the `measures-data.json?v=`
  cache key.

**Browser checks.** Run from `scraper/` against the scratch site. Each must exit 0:
- `scripts/check_election_status_browser.py --site-dir <site> --output-dir <out> --expect-count 63`
- the same, with `--clock 2026-11-12T23:59:00-08:00 --transition-to 2026-11-13T00:01:00-08:00`
- `scripts/check_county_content_browser.py --site-dir <site> --output-dir <out>`
- `scripts/check_browse_navigation_browser.py --site-dir <site> --output-dir <out>`
- from E1 on, the new `scripts/check_explore_browser.py` (§5, E1)

**Tests.** Run from `scraper/`, with
`python -m pytest -q -p no:cacheprovider --basetemp=.pytest-tmp/<chunk>`.
- Known baseline: 1 failure in `test_models`, plus 17 errors in `test_database` /
  `test_deduplication`.
- In a fresh worktree, `test_registrar_smc::test_fixture_sidecars_match_raw_bytes` can also
  fail from CRLF checkout. That's a known artifact; prove it passes in the main tree.

## 5. Chunks

### E0: Hide Explore in the current release (only if D1 = yes)

The coordinator may do this itself as part of the P0.4 release. **Check `git log` for
`SHOW_EXPLORE` before starting.** If it's there, skip E0.

- **Flag.** Mirror the Insights pattern exactly (commits `41502ab6`, `0f96c0dc`): a module flag
  `SHOW_EXPLORE = False`, plus constants holding the removed markup.
- **Entry points to gate.** Find them with `grep -n "setView('explore')\|exploreView"`:
  - the header button `#exploreView`;
  - the view card `#exploreViewCard`;
  - the welcome-intro line "Explore — pass rates by topic and jurisdiction";
  - any other `setView('explore')` caller outside the Explore block.
- **`setView`.** `setView('explore')` falls back to `'grid'` when the flag is off, alongside
  the existing Insights guard.
- **Tests.**
  - Extend `scraper/tests/test_insights_hidden.py`, or add `test_explore_hidden.py`, with
    both flag states.
  - `check_browse_navigation_browser.py` clicks `#exploreView`: make it exercise the hidden
    path when the button is absent, as was done for Insights.
- **Acceptance:**
  - no entry point in the generated HTML;
  - `setView('explore')` leaves the view on Grid;
  - Grid and List are unchanged;
  - all browser checks pass.
- **Preservation:** every measure page and `measures-data.json` are byte-identical to the
  baseline, apart from `last_seen_at`. `index.html` changes only at the gated entry points,
  the `setView` guard and the cache key.

### E1: "Honest Explore" (Fable's Q1-Q6 and Q9; about 1.5 days). Needs D2 and D3.

Goal: Explore stops saying things it can't support. No new features. If E0 shipped, E1 ends by
setting `SHOW_EXPLORE = True`.

1. **Default view: Measure Type by Decade.** Set `matrixState` defaults to
   `colField: 'measureType'` and `rowGrouping: 'decade'`.
   - Decade rows sort by time, not count.
   - Labels use the real years present, e.g. "1998-99", "2000-09", "2020-24", computed from
     the data, not hardcoded.
   - Statewide propositions have no measure type, so they drop out of this view. Say so in
     the coverage line.
2. **A title and a coverage line**, computed from the same filtered set the matrix uses:
   - a short heading saying what the table is;
   - one line: *N measures with a recorded outcome are counted. Not counted: M without a
     [column field], K without an outcome.* Plus the year span and the source (CEDA for local
     measures, and the statewide record).
   - **Counted plus not counted must equal the catalog total for the current filters.**
3. **Remove Threshold mode, "Close calls", the trap metric and the four summary cards**
   (`renderExploreSummary`, metric options `close` / `trap`, `colField: 'threshold'`). Remove
   their handlers and CSS. Keep any helper another surface uses (§3).
4. **Small cells.**
   - When n < 5, show "3 of 4": no percentage and no fill color, a neutral border, and an
     accessible label such as "3 of 4 passed; too few to show a rate".
   - Set the "Min n" default to 5.
   - Sorting ignores n < 5 cells; place them after the rated cells.
   - Drop the opacity fade, and the "anecdotal"/"limited" words in 8.6 px type.
5. **Palette (per D2).**
   - With the neutral hue: a sequential light-to-mid tint of one hue, with **dark text on
     every cell**.
   - Add a legend with numbers, e.g. "0%  25%  50%  75%  100%".
   - **Every cell must reach at least 4.5:1 text contrast**, measured in the browser.
   - Don't center the scale on 50%.
6. **County grouping (per D3).** If hidden: remove the "County" row option until P1b, make the
   default row grouping Decade, and have the coverage line say county breakdowns return after
   the history repair. Keep Region, Decade and Year.
7. **Filters.**
   - When catalog filters are active, show them inside Explore as removable chips, plus a
     "Clear filters" button.
   - "Reset Explore" resets both the matrix controls and the filters.
   - After a drill-down to Grid and a return, the Explore count reflects the filters, and
     Clear restores the full count.
8. **Dead code.** Delete the unreachable old renderer after `return renderMatrixV2()` in
   `renderMatrix()` (about 257 lines; confirm unreachable first), and any helpers only it used.
9. **Words.**
   - Update the view button tooltips ("topic × jurisdiction matrix") and the welcome line, so
     they describe what Explore now shows.
   - Cell-modal "notable" measures currently mean closest to 50%, which is wrong for 55% and
     two-thirds measures. Rename them to "closest to an even split", or remove that list. Don't
     claim a threshold.

**New browser check: `scraper/scripts/check_explore_browser.py`.** Playwright, no network,
run against a scratch site, at 1440, 768, 390 and 320 px. It asserts:
- the default is Type by Decade, with decades in time order;
- the coverage line's arithmetic reconciles with `measures-data.json` under no filters, and
  under one county filter and one year filter;
- no cell with n < 5 shows a percentage or a fill;
- every cell's computed text contrast is at least 4.5:1;
- no threshold, close-call, trap or summary-card controls exist;
- a filter chip appears after a drill-down, and Clear restores the count;
- no document overflow at 320 px;
- no page errors.

It saves screenshots and a `report.json`.

**Node tests** (the `tests/test_election_status.py` pattern) for the pure helpers in the new
module: the decade label from a year set, the n < 5 display rule (n = 0, 1, 4, 5), and the
coverage arithmetic.

**Acceptance (all must hold):**
1. Fable's §9 checks 1-8.
2. The new browser check exits 0 at all four widths.
3. All four existing browser checks exit 0.
4. The full test suite is at baseline, plus the new tests.

**Preservation gate, against the chunk's baseline:**
- All 12,372 measure pages are byte-identical.
- `measures-data.json` is byte-identical apart from `last_seen_at`.
- `sitemap.xml` (except build dates) and `use-calballot/index.html` are byte-identical.
- `index.html` differs only inside the Explore CSS/JS/markup, the view buttons and tooltips,
  the welcome line and the cache key. Provide the line-classified diff.
- Grid and List render the same DOM for the same URL before and after. Capture `outerHTML`
  of `#resultsContainer` for 3 URLs and compare.

**Hand back:** the commits, `docs/plans/explore_e1_handoff_<date>.md`, the evidence folder
path, and `docs/codex/explore_e1_review_prompt.md`.

### E2: Polish (about 3-4 days, in three reviewable sub-chunks, each with its own gate)

- **E2a: URL state and keyboard.** Fable's Q7 and Q8.
  - **URL.** Serialize `view=explore&cols=…&rows=…&minn=…&metric=…` into the URL, using
    namespaced parameters that don't collide with catalog filters.
    - Add a history entry on view change and on drill-down; replace the entry on control
      tweaks.
    - `popstate` restores the controls without writing history.
    - Existing `?view=list`, `#full-catalog` and `#m=<id>` links keep working.
  - **Cell modal.** Give it `role="dialog"` and `aria-modal`.
    - Move focus into it, trap focus, close on Escape, and return focus to the cell.
    - Space and Enter open a cell.
  - Extend the Explore check with reload, Back and Forward, and a keyboard script.
- **E2b: Table semantics.** Fable's M2.
  - A real `<table>` with a `<caption>`, `th scope`, and `aria-sort` on sortable headers.
  - A cell's content is a `<button>`. Use a roving tabindex with arrow-key movement, so the
    matrix is **one tab stop**.
  - Use the checks the project can run offline: a manual screen-reader pass described in the
    handoff, plus DOM assertions.
- **E2c: Phones and trend.** Fable's M1 and M6.
  - Below 700 px, replace the matrix with a list for one chosen column or row ("Bond · 71% ·
    3,016" with a bar, applying the same n < 5 rule), with a selector to switch.
  - In the cell detail, label the decade bars with numbers and n.
  - No horizontal scroll at 390 or 320 px, and every value reachable.

### E3: After the CEDA repair (P1b.2-P1b.4) lands. Don't start before Igor releases P1b.

- **M5:** count a multi-county measure once, using its combined result and the group key
  decided in P1b (decision 4).
- **M3:** split bonds and taxes by required vote, labelled "as coded by the source". Totals
  must equal the unsplit column. Use the repaired `required_vote`, not `vote_threshold` or raw
  `REQ`.
- **County rows return** (if D3 hid them). Use the same cohort rules as
  `local_measure_context.py`, so Explore and the county cards give one answer. Add a parity
  test: for every county × category shown on a county card, Explore's cell under the same
  filters equals the card's figures.
- **M4:** a cohort record list under the matrix, with a CSV download (tested in Chromium) and
  a "how this was counted" note.

### E4: Concept choice (needs D4 and D5). Design first; build later.

- Write a design doc for Concept A ("Ask the record") or Concept B (county page), per D4, from
  the review's §7 wireframes. Get a review before any build.
- **Concept B overlaps the local-measures layout work**
  ([layout review](../codex/layout_direction_a_review_response.md), chunks 1 and 5). Plan them
  together, and don't build a second county surface.
- **Precomputed Explore aggregates** (A3) are part of this design: a small build-time file, so
  Explore needn't load the 35 MB catalog.

## 6. Explore and Insights: the contract

Adopt this for both renovations (review §5):

| | Insights | Explore |
|---|---|---|
| Who chooses the question | CalBallot | The reader |
| Content | A few reviewed findings, prose plus a chart | A cohort the reader defines: count, rate, records |
| Numbers | Computed at build, checked, dated | Computed live from the catalog, limits stated |
| Rankings, "highest/lowest" | Only here, only when reviewed | Never |
| Links | Each finding links to its cohort in Explore | Each cohort links to its records in the catalog |

## 7. Release path, for every chunk

The executor ends at a reviewed scratch candidate. Then:
1. A review by someone other than the author: Codex, or a Claude reviewer agent if Codex is
   unavailable.
2. Fixes for the review, then a re-check.
3. **Igor's go-ahead.**
4. The coordinator builds the release in a fresh frozen workspace. The pattern is in
   `scraper/data/county_content/20261112_p0/prepare_and_build.py` (gitignored), from the
   previous recovery workspace plus the current code. The coordinator then:
   - verifies against the live root files;
   - updates the private recovery bundle, with an R2 read-back;
   - opens a PR into `main`.
5. After the merge: the served files' hashes must match the tested build, then live checks
   on desktop and phone.

Explore chunks are separate releases from the CEDA repair. **Never mix a data repair and a
layout change in one preservation diff.**

## 8. What not to do (from review §8)

- Don't polish the current default (Topic by County): it covers a quarter of the data.
- No significance tests, rankings or "top counties".
- No threshold split before P1b, and none without the "as coded by the source" label.
- No 2026 results in Explore until they're certified.
- No map.
- No model-generated prose about cells.
- Don't solve phones by shrinking the matrix.

## 9. Tracker

Add this section to the checklist when E0 or E1 starts, and keep it current:

```
## Explore renovation (plan: explore_renovation_plan_20261112.md)
| Chunk | Scope | Status | Review | Evidence |
| E0 | Hide Explore (flag) | | | |
| E1 | Honest Explore | | | |
| E2a | URL state + keyboard | | | |
| E2b | Table semantics | | | |
| E2c | Phones + trend | | | |
| E3 | After P1b: multi-county, required vote, county rows, cohort list | | | |
| E4 | Concept design (D4/D5) | | | |
```

## 10. Kickoff prompt (paste into Codex)

> Read `docs/plans/explore_renovation_plan_20261112.md` on branch `phase0-election-status` and
> follow it. Do the next chunk whose blocking decisions in §2 are marked answered, and only
> that chunk. If none is unblocked, stop and say which decisions are pending. Never push,
> publish or write to R2.
