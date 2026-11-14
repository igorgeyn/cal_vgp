# Prompt: work the next item on the CalBallot working list

**For:** Fable, in Claude Code desktop, on branch `phase0-election-status`.
**Reusable:** paste the same line each time. Each run does **one chunk** of the
highest-ranked item that suits you, then stops for review.

---

## How to pick the item

1. Read `CLAUDE.md`, then `docs/WORKING_LIST.md`. That's the ranked list of all pending work.
2. Go down **Next** in rank order. Take the first item that is:
   - **not blocked**: check its "Blocked by" column and the "Waiting on Igor" table;
   - **not Igor's own task**, and not a release or publish (the coordinator does those);
   - **not already in progress** elsewhere: see **Now**, and check `docs/codex/PENDING.md`
     for Codex work.
3. If its plan says the first step is a design, do the design, not the build.
4. If nothing qualifies, stop and say why.

**As of November 13, 2026, this resolves to Next #3, the results import for the 63 current
measures (P2), design chunk.** #1 waits on Codex and Igor; #2 is Igor's task. If the list has
changed since then, follow the list, not this line.

## General rules (every run)

- **One chunk, then stop.** Don't start the next item.
- **No commits, pushes, branch changes, publishing or R2 writes.** The coordinator (Claude)
  inspects and commits your files and runs the reviews.
- **Don't edit** `docs/WORKING_LIST.md`, the checklist or `docs/codex/PENDING.md`, since other
  agents edit them concurrently. Put the updates you'd make in your reply instead.
- **No network.**
- **Databases read-only** (`mode=ro`, or a SQLite backup copy in a scratch folder). Record the
  production DB SHA-256 before and after any query.
- **Untrusted files.** Raw or downloaded files are untrusted: run Python on them with `-I`,
  and keep scripts outside the data folders.
- **Explore code.** Another agent may be editing `scraper/src/website/generator.py` and the
  Explore files. Don't touch them unless your item is Explore work.
- **Your limits.** Follow what your own assessment said about them
  (`docs/plans/fable_assessment_20261112.md`): you don't review your own work, and you flag
  editorial or visual calls for Igor.

---

## This run: P2 results import, design chunk

**Goal:** a design that lets results for the 63 current measures (14 statewide, 20 San
Bernardino, 29 San Mateo) appear on the site **before counties certify on December 3**. First
as unofficial, labeled and sourced, then certified. It must be built so the county expansion
can reuse it.

### Read

- `docs/plans/results_transition_20260907.md`: the earlier results design and its rehearsal
  list.
- The checklist's Phase 2 outline and P2.0. That covers precinct masking (10 voters or fewer),
  the multi-county rule, unofficial display, and the observation store.
- `scraper/src/website/election_status.py`: the current status contract (calendar statuses;
  passed, failed and unknown; `official_results` links; the stored-votes rule).
- `scraper/src/website/data/official_results_links.json`: the official results URLs and
  check records.
- `docs/codex/layout_direction_a_review_response.md`, answer 2: the six-state result contract
  (results pending, unofficial, certified passed, certified failed, withdrawn, historical result
  unknown). It also covers threshold wording, rounding, and the multi-county combined result
  versus a county's portion.
- `docs/plans/ceda_backfill_design_20261112.md` and
  `docs/codex/p1b_1b_revision_review_response.md` (N1): the historical multi-county model,
  with a group key and `combined_passed` kept separate from per-county `passed`. Current and
  historical measures should use **one** model.
- The registrar code (`scraper/src/scrapers/registrar/`: `sb.py`, `smc.py`, the loader,
  `storage.py`) and `docs/setup/registrar_developer_guide.md`: how captures, immutable R2
  snapshots and loads work today. Results pages are not captured: `smc.py` skips them and
  `sb.py` never requests them.
- `docs/LESSONS_LEARNED.md` and `docs/KNOWN_ISSUES.md` #1, on vote thresholds.
- `CLAUDE.md` hard rules: always keep `id` in `BallotMeasure`'s `valid_fields`; flip consumer
  surfaces atomically; use verification stacks.

### Produce

Write `docs/plans/results_import_design_20261113.md`, about 4–6 pages, covering:

1. **Sources.** For each source (SOS statewide, San Bernardino, San Mateo): the official URL
   (from `official_results_links.json`), the expected format, and what identifies a contest.
   Say what you know from the code and docs and what's unverified; you can't fetch anything.
   Then give **an exact list of files for Igor to save by hand** each week until certification:
   URL, what to click, file naming, and a dated folder convention under a gitignored path, with
   a SHA-256 manifest. This list also serves working-list item #2.
2. **Data model.** An append-only observation store: measure `id`, source, as-of text and
   time, unofficial or certified, yes/no/total counts and denominator, scope (the whole
   contest, or one county's portion), the source file's hash or snapshot, and the importer
   version. Explain how it relates to the existing `measures` columns. Never overwrite history,
   and keep every public `id`.
3. **Mapping.** A reviewed manifest from each source's contest to our measure `id`. It must
   fail closed on unknown, duplicate or missing contests. Then the multi-county rule for current
   measures: RTM/SMC and any others, using one model with the CEDA design.
4. **Projection to the site.** How observations become the six result states, and which fields
   reach `measures-data.json`, the cards, the modal and the static pages.
   - Unofficial results never get a Passed/Failed label.
   - Thresholds come only from reviewed sources; otherwise "Approval requirement not listed".
   - Rounding never decides an outcome.
   - Precinct-level data is masked at 10 voters or fewer, if precinct data is used at all.
   - How the P0.1 status contract changes.
5. **Verification.** Fixtures-first importer tests for each source; the rehearsal list from the
   results transition doc; a preservation gate (which pages and fields may change); browser
   checks; a certification sweep.
6. **Chunks.** For example: (a) the store and SOS importer; (b) the SB and SMC importers; (c)
   site projection and display; (d) the certification sweep. For each: size, dependencies,
   acceptance checks, and who should build it (you, Codex or a Claude agent).
7. **Risks and open questions** for Igor, each with a recommendation.

Also write `docs/codex/p2_results_design_review_prompt.md`, a review prompt for Codex in the
style of the other `*_review_prompt.md` files. It should end with: write
`docs/codex/p2_results_design_review_response.md` and commit only that file.

### Reply with

- a five-line summary;
- the list of files Igor should save, short form;
- the decisions you need from Igor;
- the updates you'd make to `WORKING_LIST.md` and the checklist;
- the paths of the files you created;
- the production DB hash before and after, if you queried it.
