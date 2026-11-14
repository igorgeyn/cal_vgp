# CalBallot Working List

**Updated November 13, 2026 (evening).** This is the single ranked index of all pending work. Each item
links to the tracker or plan that holds its detail. **Update it at every chunk boundary:** move
items between sections, re-rank, and change the date. The pre-November log and its full
per-area backlog are in [`WORKING_LIST_HISTORY.md`](WORKING_LIST_HISTORY.md).

**Detail lives in:**
- [`plans/local_measures_checklist_20261107.md`](plans/local_measures_checklist_20261107.md):
  the main tracker. It covers the release phases P0-P6, the CEDA repair P1b and the Explore
  chunks.
- [`codex/PENDING.md`](codex/PENDING.md): the Codex queue, as pasteable prompts.
- The plans linked below.

---

## Where things stand

- **Live** (released November 12, [PR #9](https://github.com/igorgeyn/cal_vgp/pull/9)):
  - the 63 measures on the November 3 ballot read "Results pending", with official-results
    links;
  - history labels are fixed, and past measures with no outcome read "Result unknown";
  - Insights and Explore are hidden.
- **Coverage:** local measures from 2 of 53 counties (San Bernardino and San Mateo, 49
  measures); about 460 statewide.
- **Deadlines:**
  - Counties certify by **December 3**; the Secretary of State by **December 11**.
  - County results pages are overwritten as counts update, and nothing captures them yet.

## Now (in progress)

| # | Item | Status | Detail |
|---|---|---|---|
| 1 | **Explore E1, "Honest Explore"**: Explore comes back without overstating the data | Built, fixed after two reviews (`a496421c`). Codex's fix-pass review (`3c426967`) found a release blocker (a county drill-down dropped the county); **fix pass 2 is being verified**. Then Igor's go-ahead to release. | [handoff](plans/explore_e1_handoff_20261113.md), [plan](plans/explore_renovation_plan_20261112.md) |
| 2 | **Home page review** (Fable, read-only): layout suggestions for the whole page | Running | [prompt](codex/fable_homepage_review_prompt.md); output `plans/homepage_review_20261113.md` |

## Next (ranked)

Ranked by deadlines first (results are perishable, certification is December 3), then wrong
data on the live site, then reader value, then expansion.

| # | Item | Why here | Blocked by | Detail |
|---|---|---|---|---|
| 1 | **Release Explore E1** | Small and fully verified; brings back a feature | Codex review, Igor's go | [handoff](plans/explore_e1_handoff_20261113.md) |
| 2 | **Save the results files by hand** (Igor): today, then Nov 20 and 27, Dec 4 and Dec 12, plus certified files at certification | Results pages are overwritten; the evidence is perishable. Nov 5 and 7 script captures are already filed | Igor (task) | [P2 design §1, "What Igor saves"](plans/results_import_design_20261113.md) |
| 3 | **Results import for the 63 (P2)**: ledger and SOS importer (a), county importers (b), site display (c), certification (d) | The main reader need until certification. Unofficial display only if (c) is ready by **Nov 26** | Design written; **Codex design review**; Igor's 8 answers; first saved county files for (b) | [checklist P2](plans/local_measures_checklist_20261107.md), [results transition](plans/results_transition_20260907.md) |
| 4 | **Flag the 28 wrong CEDA records and id 4870**: hide the summary and add an "under review" note on each page | Wrong data is live: another measure's question, votes and outcome. Decided November 12 | None (small follow-up release) | [CEDA design](plans/ceda_backfill_design_20261112.md), [revision review](codex/p1b_1b_revision_review_response.md) |
| 5 | **Chart the rest of Explore** (Fable), then **E2c**: transpose the table, a phone list, the trend chart with numbers; then E2a and E2b | Explore's phone layout is still poor; E2c fixes most of it | E1 released; **E2c waits for P2(c)**, which also edits `generator.py` and has a deadline | [plan §5 E2](plans/explore_renovation_plan_20261112.md) |
| 6 | **Census fixes and the capture tool (P1.1a, P1.2)** | Gate every county beyond SB/SMC | **The User-Agent decision** (Igor) | [census review](codex/p1_1_census_review_response.md), [checklist P1](plans/local_measures_checklist_20261107.md) |
| 7 | **Home page and layout**: act on Fable's review, then Direction A chunk 1 (the local directory) | The county directory must exist before many counties load | Fable's review (#2 in Now); Igor's calls | [Direction A review](codex/layout_direction_a_review_response.md) |
| 8 | **Counties: prove capture and harvest on the 7 surveyed counties** (LA 68, Alameda 28, Orange, Sacramento, San Diego, Fresno, SF), then survey the other ~41 (P1.3, P4) | Coverage goal: all 53 (decision 1) | #6; a reviewed harvest design | [census](plans/county_census_20261111.md), [checklist P1/P4](plans/local_measures_checklist_20261107.md) |
| 9 | **Results-link checker fix and recheck (P0.3a)**, and a fresh human check of the SOS link | Needed before the certification release | None | [checklist P0.3a](plans/local_measures_checklist_20261107.md) |

## Waiting on Igor

| Decision or task | Recommendation | Blocks |
|---|---|---|
| Approve the **Explore E1 release** after Codex's review | Yes, if the review is clean | Next #1 |
| **Save the results files** weekly until December 3 | Yes: a browser download into a dated folder | Next #2, #3 |
| **User-Agent** for the capture tool | Project name plus the GitHub URL, **no email** (the registrar default in `base.py` includes it) | Next #6, #8 |
| **P2 design §7, eight questions**: ledger as a committed file; a reviewed "majority" rule for the 14 propositions; skip unofficial if not ready by Nov 26; multi-county portion labelled before certification; save other counties' certified results; wording; no precinct data; commit the SMC CSV fixture if under ~5 MB | Agree with all of Fable's recommendations; wording is Igor's call | P2 (a)-(d) |
| **`CLAUDE.md` commit trailer**: it says "Claude Opus 4.7"; the current model is Opus 5.5 | A model-neutral wording, or Opus 5.5 | Nothing (hygiene) |
| **Download the current CEDA release** from CSUS Esploro (2016-2021, ideally all years) | Yes | CEDA repair for those years; the id 9189 decision |
| **San Francisco results route**: its results hosts return 403 to scripts | A manual browser download, or ask the department | SF results |
| **Santa Clara access** (decision 4) | Igor is checking himself | Santa Clara |
| **CEDA design §12**, five questions | Agree on all five. Restore Measure D in the repair, not the follow-up release (the revision review found Measure P's source doubtful) | CEDA repair |
| **Explore audience and name** (D4/D5) | Journalists and researchers; keep "Explore" for now | Explore E4 only |
| Commit `plans/measure_layout_design_proposal.md` and `design/` (both untracked) | Commit them; Direction A is approved | Nothing |

## Paused

- **CEDA history repair (P1b.2-P1b.4).** Paused by Igor on November 12 until the Explore work
  is done.
  - To restart:
    - Fable revises the tool and design for the revision review's N1-N11. Key points: keep
      `passed` per county and add `combined_passed`; narrow the waivers; drop the views before
      the rebuild; make the search-index checks able to fail; add an "unverified" mark; fix
      the code keyed on `measure_id` for the 2014 rekey.
    - Igor answers the design's §12.
  - Detail: [design](plans/ceda_backfill_design_20261112.md),
    [report](plans/ceda_reconciliation_20261112.md),
    [revision review](codex/p1b_1b_revision_review_response.md).
- **Worktree and test hygiene.** Held by Igor on November 12:
  - a `.gitattributes` `-text` rule for the registrar fixtures;
  - the 18 legacy test failures: `Path(db_path)` in `Database.__init__`, and the `test_models`
    county default.

## Later (by area)

**Layout and content**
- Direction A chunks 2-6: statewide slate, result states, results tab, history (after P1b),
  election comparisons ([review](codex/layout_direction_a_review_response.md)).
- Full local explanations for new counties: deferred by decision 2
  ([plan](plans/local_explanations_parity_plan_20261111.md)).
- The card design plan ([September 13](plans/card_design_action_plan_20260913.md)) is largely
  superseded by Direction A and the home page review. Fold it in or close it.

**Explore and Insights**
- Explore E3 (after P1b): count multi-county measures once, the required-vote split, county
  rows back with a parity test, and a cohort list with CSV. Then E4, the concept design.
- **Insights renovation** (hidden). Use the Explore/Insights split in the
  [Explore plan §6](plans/explore_renovation_plan_20261112.md). Older items: Close Calls keep or
  kill, Rules panel follow-ups, Topics and Measure Types revisits (history file, "Insights
  panels").

**Registrar operations**
- R2 routine refresh automation, R2.02-R2.11
  ([October checklist](plans/remaining_review_checklist_20261008.md)).
- R5 integrated operating rehearsal.
- Ongoing drift maintenance ([runbook](setup/registrar_drift_runbook.md)), about one event per
  county every two weeks.
- [County status board](plans/county_status.md) and the
  [expansion workplan](plans/registrar_county_expansion_workplan.md) are both from August 27;
  the census supersedes them.

**Data**
- The topic classification gap: about 75% of records are "Other". Adopt the CAP taxonomy
  ([Georgia scaffold plan](plans/georgia_scaffold_integration.md)).
- Statewide historical coverage; a topic-flag audit; the CEDA 2025 file when it's published.
- The search index (`measure_search`) is stale today (revision review N5).
- The 1,755 placeholder titles ("SAN BERNARDINO Measure U"), after P1b.

**Finance** (detail in the history file, "Finance")
- Crosswalk buckets A-C, the June 2018 propositions, the second PROP_27_2022 committee, a
  per-campaign transaction table, coverage beyond 181 propositions, and where the marquee
  fights go.

**Briefings** (paradigm: free cards, briefings on demand)
- Summary regeneration (about 8,500 missing), the validator harness, a brief bakeoff, curated
  research briefs, and surfacing context layers.

**Docs and hygiene**
- A verification runbook (Phase G and Layers 1-3).
- A methodology and corrections tracker.
- An audit of dead fields in the JSON payload.
- The threshold helpers in `generator.py` are unreachable; delete or revive them in E3.

**Ideation**
- Thematic policy explorations and donor-influence lenses. Both depend on the topic
  classification fix.

## Done since October 8 (most recent first)

- **November 13:** Explore E1 built (Codex), fixed after reviews by a Claude reviewer agent and
  Fable; plan reordered so E2c comes first.
- **November 12:** **P0 release published** ([PR #9](https://github.com/igorgeyn/cal_vgp/pull/9)):
  - election status (P0.1);
  - the history-label fixes (P0.2/P0.2b, N1/N2);
  - Insights and Explore hidden;
  - recovery update `2728598b…` in private R2.
- **November 12:**
  - CEDA reconciliation, its tool and the repair design (Fable), with two reviews;
  - the census review;
  - the bot-challenge ruling;
  - the Direction A layout review;
  - the Explore review and plan.
- **November 11:** P0.1 closed; decisions 1-5; the county census of the 10 largest; the CEDA
  downloads and column check.
- Per-card deep links (`#m=<id>`) and calendar status (October's R3) are both done; removed
  from the backlog.

## Closed by decision (don't re-add)

- Geography regions in Insights: dropped ("keep county-level only").
- Measures-DB ID reconciliation for the 2014/2016 soft duplicates: deferred. **Superseded** by
  the CEDA repair's 2014 rekey.

## External waits

- The CEDA 2025 raw file, when it's published.
- LinkedIn and Twitter write-ups: drafts are ready; post when ready (Igor).
