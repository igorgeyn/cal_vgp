# Local measures checklist

**Updated:** November 11, 2026.
**Companion:** [plan](local_measures_completion_plan_20261105.md) (rationale, phases, decisions) and
[data assessment](election_data_granularity_assessment_20261105.md).
**Status:** chunk **P0.1** (status rule and official results links) is **complete** on branch
`phase0-election-status`. Codex closed R1-R6 on re-review, and Igor confirmed the Secretary of
State link, so it now shows on the 14 propositions. Next: P0.2. Nothing is published; `main`
and the live site are unchanged.

## How this works

- Work goes in **chunks**: small, reviewable units, each ending in a handoff with what changed,
  evidence and open questions. Codex reviews each chunk before the next starts.
- Check a box only with evidence recorded here or in the linked handoff. A blocked, deferred or
  inapplicable item stays unchecked, with the reason, owner and next step appended.
- Igor approves every push, merge and release. Items marked **Igor** need him.
- Later phases are outlined, not detailed. Each gets its full item list when its first chunk
  starts, after the previous chunk's review.

## Chunk tracker

| Chunk | Scope | State | Review | Evidence |
|---|---|---|---|---|
| **P0.1** | One status rule on every surface; official results links | **Complete** | Codex: [R1–R6 closed; ready for current scope](../codex/p0_1_status_review_response.md#re-review); Igor P0.1.15 done Nov 11; R7 deferred to P2.0 | [P0.1 handoff](#p01-handoff), [dispositions](#p01-review-dispositions) |
| P0.2 | History list: stop naming the county as every record's jurisdiction; with P0.2b (Igor approved Nov 11) and P2.0 (R7) | **Built** (agent A; merged as `6fe4f565`..`e0db6d60`): only the 40 history pages change, and only in their 200 history labels; card and modal read "Result unknown"; checker fixed for R7. 155 targeted tests pass; browser checks 0 failures | Codex: [prompt](../codex/p0_2_review_prompt.md) pending | prompt has the full evidence and 6 open questions |
| P0.3 | Release candidate: strict build, page diff, browser checks, recovery bundle | Not started | | |
| P0.4 | **Igor** go; publish; served-byte and live checks; receipt | Not started | | |
| P1.1 | County source census: schema and the 10 largest counties | **Built** (agent B): 159 distinct measures confirmed from official pages in 7 counties; Riverside, Santa Clara and Contra Costa still blocked; **SF newly 403** on its results hosts | Codex: [prompt](../codex/p1_1_census_review_prompt.md) pending | [census note](county_census_20261111.md), `scraper/data/census/county_sources_2026.json` |
| P1.2 | Generic capture tool (URL list into immutable R2 snapshots) | Not started | | |
| P1.3 | Census and capture for the remaining counties | Not started | | |
| P1.4 | Watch the November 9 registrar cron (SMC rollover risk) | **Done**: run succeeded | | P1.4 below |
| P1b.1 | Download the 22 missing CEDA years; column check | **Built** (agent C): 16 of 22 years downloaded (1998-2014, via Internet Archive copies of csus.edu/isr); every backfill field exists in all 21 files held. **2016-2021: Igor to download by hand** from the CSUS Esploro page. New defects: 2014 keyed on the wrong ID; 28 rows with another measure's votes; one foreign 2002 row | Codex: [prompt](../codex/p1b_1_ceda_review_prompt.md) pending | [column check](ceda_column_check_20261111.md) |
| P1b.2 | Backfill on a database copy (combined results, names, questions, thresholds) | Not started | | |
| P1b.3 | Verification layers; changed-outcome list for **Igor** | Not started | | |
| P1b.4 | Release of the repaired history | Not started | | |
| P2.x | Results for the 63 (importers, observations, multi-county rule) | Outline below | | |
| P3.x | Layout (Direction A, result state, tab design) | Outline below | | |
| P3b.x | Results and comparisons tab | Outline below | | |
| P4-P6 | Harvest waves, certification sweep | Outline below | | |

## Decisions (plan §8)

Igor answered on November 11, 2026. Parallel execution follows [`agent_execution_plan_20261111.md`](agent_execution_plan_20261111.md). Codex prompts are ready: [layout review](../codex/layout_direction_a_review_prompt.md) (decision 3) and the [bot-challenge rule](../codex/bot_challenge_rule_question.md) (P0.3).

| # | Decision | Answer | Blocks |
|---|---|---|---|
| 1 | Coverage: all 53 counties or the largest ten | **All 53** | P1.3 scope |
| 2 | Explanations for the ~413 new measures | **Questions and results first.** The full alternative is written up, deferred, in [`local_explanations_parity_plan_20261111.md`](local_explanations_parity_plan_20261111.md) | P4 content |
| 3 | Approve Direction A with a result state and the results tab | **Approved**, subject to Codex reviewing the layout proposal first | P3 |
| 4 | Email the Santa Clara Registrar for access | **Igor is checking Santa Clara's access himself**; outcome pending | Santa Clara in P1.3 |
| 5 | Statewide same-year comparisons before every county loads | **Wait** for full coverage; meanwhile compare within the same county and against November 2024 | P3b same-year section |

## Phase 0: make the site true

### P0.1 Status rule and official results links

Maps to the October plan's R3.01-R3.04 and R4.02.

- [x] **P0.1.01** Inventory every status consumer. Explorer: statewide cards, list rows,
  modal badge, modal note, modal links, card meta, section notes. Static pages:
  `build_measure_pages.py` `outcome()`. Data: `measures-data.json`. Local cards show no status
  (unchanged). The "Pending/Unknown" filter chip counts outcomes, not dates (unchanged).
- [x] **P0.1.02** One rule in `scraper/src/website/election_status.py`: Upcoming before election
  day, Election day on it, **Results pending** after it, all by California date. Recorded
  outcomes and withdrawal take precedence. No date means unknown, never inferred from the year.
- [x] **P0.1.03** Stored votes without a normalized outcome read as unknown, not pending. Found
  in the first build: 48 CEDA 2011 rows have `percent_yes` and `pass_fail` but `passed` NULL,
  plus one 2018 Monterey row. Logged for Phase 1b.
- [x] **P0.1.04** Release builds stop if a current-cycle row lacks a usable date, or if an older
  row would show a pending status.
- [x] **P0.1.05** Build date is explicit: `generate_site.py --as-of`, passed through and recorded
  by `build_release_bundle.py`; default is today in California.
- [x] **P0.1.06** The explorer re-applies the date rule with the reader's clock, forward only,
  so an un-rebuilt site still stops saying "Upcoming". Python and browser rules are tested
  against each other in Node.
- [x] **P0.1.07** Results link data in `scraper/src/website/data/official_results_links.json`,
  validated at build: https only, one per election and county, `expect_text` required.
- [x] **P0.1.08** `check_official_results_links.py` records each check in place. A check passes
  only on 200 with the expected text; bot-challenge pages count as failures and are not
  worked around. A link shows only if its newest check (automated or a person's) passed, with
  the real check date.
- [x] **P0.1.09** Links render from election day on: modal Links section, statewide and local
  section notes, static pages.
- [x] **P0.1.10** Tests: `scraper/tests/test_election_status.py`, 41 pass at first review, 81 after the review fixes (boundaries, Pacific
  midnight, year rollover, precedence, unusable dates, strict guards, link validation and
  newest-check rule, Node parity, static pages, no year rule left in the explorer).
- [x] **P0.1.11** Full suite: 654 pass, 1 skipped. The 1 failure and 17 errors also occur on an untouched
  `main` worktree (`test_models` county default; `test_database`/`test_deduplication` pass a
  `str` path). Not caused by this chunk; not fixed here.
- [x] **P0.1.12** Scratch strict build (`--as-of 2026-11-07`, database copy): exactly **63**
  measure pages change, all current measures; **12,309** are byte-identical. JSON gains
  `election_status` on 63 rows and `official_results` on 49. 129 `last_seen_at` values
  regenerate (known since October). Sitemap dates move. No static page says "Upcoming".
- [x] **P0.1.13** Browser checks (`check_election_status_browser.py`, 1440/390/320px, all 63
  measures on every surface, no page errors, no horizontal overflow): pass for a November 7
  build at a November 7 clock; a November 2 build at November 2 noon (Upcoming), November 3
  noon and 11:59 p.m. (Election day) and November 4 12:01 a.m. (Results pending); and a
  November 7 build at a November 2 clock (stays Results pending).
- [x] **P0.1.14** Production database hash unchanged; root `index.html` and
  `measures-data.json` untouched.
- [x] **P0.1.15 — Igor** Open the Secretary of State link
  (https://electionresults.sos.ca.gov/returns/ballot-measures) in a normal browser. If it shows
  November 3, 2026 results, it gets a `manual_check` entry and the statewide link appears.
  Scripts get a bot challenge there (HTTP 200 with an Incapsula page).
  **Done November 11:** Igor opened the page in a browser. It shows the returns table for
  Props 1-5 and 37-45, the same 14 measures we have. The `manual_check` is recorded at
  2026-11-11T15:38:00Z. Strict scratch build `--as-of 2026-11-11` compared with the
  November 7 candidate:
  - `official_results` changes on exactly 14 rows, so 63 rows now carry a link.
  - Withdrawn ACA 13 correctly gets none.
  - Exactly those 14 measure pages change; no pages are added or removed.
  - The browser checker, with `--expect-count 63` at the real clock, reports 0 failures.
  - 81 election-status tests pass.

  The rule for how a later bot challenge counts is a P0.3 question.
- [x] **P0.1.16 — Codex** Review complete: **ready with changes**; see the
  [response](../codex/p0_1_status_review_response.md) to the
  [review prompt](../codex/p0_1_status_review_prompt.md). Independent tests, build,
  preservation counts and six browser scenarios reproduce. R1–R6 remain open for
  the builder: open-tab refresh, strict date guard, check-record validation,
  `percent_no` precedence, date-format parity and effective release-date recording.
  Re-review the fixes before closing P0.1; P0.1.15 remains Igor's manual check.
- [x] **P0.1.17** Fix R1-R6 and take up the checker suggestions; see
  [dispositions](#p01-review-dispositions).
- [x] **P0.1.18 — Codex** Re-review complete November 11: **R1–R6 closed; ready for
  the current P0.1 scope**. See the [re-review](../codex/p0_1_status_review_response.md#re-review)
  and [prompt](../codex/p0_1_fixes_rereview_prompt.md). Original reproductions,
  requested midnight transition, 111 targeted tests and preservation checks pass;
  full suite matches the claimed 694 passes and baseline failures. New P3 finding
  R7 is a nonblocking checker follow-up before result imports. P0.1 is not fully
  complete until Igor performs P0.1.15 or explicitly records its deferral.

#### P0.1 review dispositions

| Finding | Disposition | Evidence |
|---|---|---|
| **R1** Open tab keeps yesterday's status | **Fixed.** `refreshCalendarStatuses()` runs every minute, when the tab becomes visible and on focus. When the California date changes it re-renders the hero, both section notes, the local section and grid/list results, keeping carousel and page positions. It updates an open modal's badge, results link and note in place, so the tab and scroll stay where they were. | Checker `--transition-to`: Nov 2 build loaded at Nov 2 23:59 with a modal open, then Nov 3 00:01: 14 cards go Upcoming to Election day and the open modal updates. Same for Nov 3 23:59 to Nov 4 00:01 (Results pending). The identical check fails 16 ways on the pre-fix build. |
| **R2** Strict guard rejects a valid stored-vote row | **Fixed.** Date validity is checked directly, for current-cycle rows that are not withdrawn. Stored votes stay "unknown" and do not stop a build. The second guard now fires only for `results_pending` outside the cycle, so a future election (e.g. 2028) may read Upcoming. | Tests: every vote field (zero included) on a current row passes strict; a 2028 row attaches as upcoming; noncanonical dates raise "expected YYYY-MM-DD". |
| **R3** Malformed check records can publish an undated link | **Fixed.** Checks are validated at load: timezone-aware `checked_at`, boolean `ok`, automated success needs status 200 and the expected `matched_text`, manual checks need ok, by and observed. Times compare as instants; a failure at the same instant wins; the exported time is canonical UTC. The explorer also refuses a link whose date it cannot format. | 13 new tests (7 malformed automated, 3 malformed manual, offsets, ties, valid failure). |
| **R4** `percent_no` missing from stored votes | **Fixed.** `VOTE_FIELDS` lists all six; tests are parameterized over it, and Python and Node agree. | Tests. |
| **R5** Python accepts dates the browser cannot advance | **Fixed.** Both halves accept exactly `YYYY-MM-DD`; nothing is trimmed or reinterpreted, and historical JSON is not normalized. | Node parity test over ` 2026-11-03 `, `2026-W45-2`, `20261103`. |
| **R6** Default release date not recorded | **Fixed.** `build_release_bundle.py` resolves the date once (California today if omitted), always passes `--as-of` and records the same value. | Test runs the real wrapper with stubbed subprocesses, with and without `--as-of`. |
| Q3 wording on election day | **Changed** to "official results are linked when available". | Browser checks. |
| Checker suggestions | **Adopted:** current rows chosen by `upcoming_scope` with `--expect-count`; rendered hero badges checked; card label required for every status; case-insensitive visible-text scan; clock frozen to now when `--clock` is absent; same-page transition check. A no-`Intl` case is in the Node tests. | Six runs, all 0 failures, `--expect-count 63`. |
| Legacy "• Pending" on historical unknown cards (Q1) | **Deferred** to P0.2b, per the review: a scope decision, not part of this fix. | |
| Separate release-election membership from display sections (Q5) | **Deferred** to Phase 3, where `election_date` replaces the year selector. | |
| Record link-check freshness in release evidence | **Planned** for P0.3: recheck county links and list the omitted scopes. | |
| **R7** (re-review, P3) Browser checker requires a calendar status on every current row, so it rejects the supported stored-votes "unknown" state | **Deferred**, nonblocking: all 63 current rows depend on the date. Fix before P2 imports results; see P2.0. | Codex's reproduction on row 12420 with `yes_votes=123`. |

Post-fix evidence: 81 election-status tests pass; full suite **694 passed**, 1 skipped,
with the same 1 failure and 17 errors as `main`. A fresh strict build at November 7 again
changes exactly 63 pages (12,309 identical to live). All 12,372 static pages are
byte-identical to the first candidate's, so the fixes changed only the explorer script and
the data checks. JSON differs from live only in `election_status` (63), `official_results` (49)
and `last_seen_at` (129). Protected hashes are unchanged: database `ef1359e4…`, root
`index.html` `b0257999…`, `measures-data.json` `1921e5d4…`.

#### P0.1 handoff

**What changed:** the status rule, the results links and their checker, every explorer
consumer, the static page builder, the build scripts' `--as-of`, a browser checker and tests.
Branch `phase0-election-status`; no generated site files are committed.

**Wording choice to review:** the plan said "Counting votes"; the build says **Results
pending**. Counting finishes at certification (December 3), but the label stays until
CalBallot imports results, so "Counting votes" would become false. "Results pending" is true
for the whole interval.

**Known limits:**
- Static pages only change when rebuilt. The explorer corrects itself; static pages do not.
- The results link sits in the modal's Links section, below the documents. A more prominent spot
  belongs to the Phase 3 result state.
- The statewide link waits on P0.1.15.
- `UPCOMING_ELECTION_YEAR` still chooses which measures appear in the current-election
  section. Replacing it with `election_date` is Phase 3 work.

### P0.2b Legacy "• Pending" wording (from review Q1)

- [ ] Historical rows with no normalized outcome show "• Pending" on explorer cards, e.g. the
  48 CEDA 2011 rows. "Result unknown" would match the static pages. Explorer-only change;
  needs a scope call because it alters historical presentation. Can ride with P0.2.

### P0.2 History list label

- [ ] **P0.2.01** County history records show the county as jurisdiction for every CEDA row
  (`local_measure_context.py`, modal and `county_content.py` renderers). 43 of the 48 checkable
  shown records are city or school measures.
- [ ] **P0.2.02** Neutral label until Phase 1b restores names; tests; page diff limited to the
  40 cards with history.

### P0.3 Release candidate

- [ ] Fresh frozen workspace and strict build via `build_release_bundle.py --as-of`.
- [ ] Preservation gate: only the expected pages, JSON fields and sitemap dates change.
- [ ] Browser checks for status, the history label and existing county-content checks.
- [ ] Private recovery bundle update and R2 read-back.
- [ ] Recheck the county results links; record each link's check date and any scope left
  without a link.
- [ ] **Codex question** on how a bot challenge counts. The SOS link gets a bot challenge
  from scripts every time. Under the current rule, the newest check decides whether the link
  shows, so rerunning the checker hides the link Igor confirmed by hand. Proposal: treat a
  `bot_challenge` result as inconclusive, not as a failure, so it cannot override a newer
  or older manual success. Real failures (bad status, missing text) still hide the link.
  This changes the R3 rule, so it needs Codex's agreement before code changes.

### P0.4 Publish

- [ ] **Igor** go-ahead.
- [ ] Merge and publish the root pair and pages as one revision.
- [ ] Served-byte hashes match the tested build; live desktop and mobile checks; receipt.

## Phase 1: freeze the sources (outline)

- [ ] P1.1 Census schema (county, listing/results/document URLs, access state, format, count,
  checked time) and the 10 largest counties.
- [ ] P1.2 Generic capture tool reusing `base.py` politeness and immutable R2 snapshots.
  Decide the User-Agent with Igor: the registrar default includes his email.
- [ ] P1.3 Remaining counties, by decision 1; blocked and list-less counties named.
- [x] P1.4 November 9 cron result recorded: scheduled `registrar-pipeline` run on `main`,
  2026-11-09 21:59Z, **success**. No rollover action needed.

## Phase 1b: repair the CEDA history (outline)

- [ ] P1b.1 Download the missing years; column check per year.
- [ ] P1b.2 Backfill on a copy: combined multi-county results, `place_name`,
  `jurisdiction_kind`, `required_vote`, `multi_measure_id`, `ballot_question`.
  Also normalize `passed` for the 48 CEDA 2011 rows found in P0.1.03.
- [ ] P1b.3 Layers 1-3 and the San Joaquin Delta K sentinel; Igor reviews changed outcomes.
- [ ] P1b.4 KNOWN_ISSUES entry, #5 corrected, release.

## Later phases (outline)

- **P2.0** Fix review finding R7 in `check_election_status_browser.py` before any results
  import: require a calendar status only for rows that depend on the date, check the
  displayed unknown, passed or failed state for the rest, and add a regression with mixed
  states.
- **P2** Results for the 63: observation store, SOS JSON, SB xlsx and SMC CSV importers,
  precinct masking (10 voters or fewer), multi-county rule, unofficial display.
- **P3** Codex review of the layout proposal; result state; tab design; `election_date`
  replaces the year in section selection.
- **P3b** Results and comparisons tab per plan §6.
- **P4-P6** Harvest adapter and waves; certification sweep from December 3.
