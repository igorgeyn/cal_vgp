# Open threads — 2026-08-27

> **Point-in-time checklist**, not a canonical index. For the durable
> backlog read [`docs/WORKING_LIST.md`](../WORKING_LIST.md); for
> county expansion read
> [`registrar_county_expansion_workplan.md`](registrar_county_expansion_workplan.md).
> This file exists to answer "what do I actually do next" in one place.
> Delete or supersede it once its items are done.

**State as of writing:** San Bernardino is live on calballot.com (20
measures, published `2afcba9`). `main` is in sync with origin; the
working tree is clean apart from two untracked finance drafts (§E6).
407 tests pass, 18 fail for pre-existing unrelated reasons (§E1).

---

## A. Ready to hand to Codex — prompts already written

- [ ] **A1 · Compact card variant for the live local-measures band.**
      Prompt: `docs/codex/compact_local_measure_cards.md` (`c946d09`).
      Density variant of the same card component (~230px → ~110px),
      carousel container for statewide parity, county `<select>`, and
      the historical-context line built on the six-entry measure-type
      crosswalk. **This changes a live surface**, so the prompt
      forbids regenerating deployed artifacts — publication is §C1.

- [ ] **A2 · "Use CalBallot" audience page.**
      Codex's own plan: `docs/plans/use_calballot_page_implementation.md`.
      Work appears to have started (`.gitignore` picked up
      `/scraper/use-calballot/`). **Pass along these four amendments
      from the review:**
      1. Cut the `?view=` routing (§5 of that plan) from scope — it
         touches the main app's state machine for a secondary page's
         link targets. Do it later as its own change.
      2. Generate the coverage sentence from data, never hardcode it.
         Local coverage is 1 county of 58 today and changes the moment
         LA lands.
      3. Add a positive test that every number rendered matches a
         computed value.
      4. Make the archive-vs-current-coverage distinction required
         copy, not just a review criterion.

## B. Needs a prompt written first

- [ ] **B1 · §5a capture/interpretation decoupling.**
      From the expansion workplan §5a. Today the scraper must
      recognize a document's *role* to download it, so a new document
      type turns the weekly cron red — and a red cron means that
      week's capture is **lost**, on perishable data. Change: capture
      every link in the measures table with its label and URL,
      unclassified; move role assignment to the offline parser. Both
      real drift events (2026-08-10 tax rate statement, 2026-08-24
      notice of election) become non-events. **Est. 2–3 days.**
      Claude to write the prompt on request.

- [ ] **B2 · Recon sweep of the five unexamined top-10 counties.**
      Alameda, Santa Clara, San Mateo, San Francisco, Contra Costa —
      each out-produces Orange/Riverside/SB and none has ever been
      probed. Uses the existing harness. **Est. half a day**, and it
      converts five unknowns into estimates before any build order is
      locked.

- [ ] **B3 · Los Angeles scraper.** Largest single gain (1,389
      records, 12.6%). Structurally unlike SB — section-organized
      text, and it carries vote totals, so it may deliver *results*.
      Read `docs/setup/registrar_developer_guide.md` first.
      **Est. 3–4 days.**

**Ordering note.** The workplan recommends B1 before county three,
ideally before county two. B1-then-B3 buys sustainability before it's
needed; B3-then-B1 buys visible coverage and defers the refactor one
county. Both defensible. Avoid reaching county four without B1.

## C. Comes back to Claude

- [ ] **C1 · Verify + publish the compact cards.** After A1 returns:
      scratch-render, confirm the statewide carousel is unchanged,
      check the artifact diff, then regenerate and push. Same reviewed
      publication procedure as tonight's release.

- [ ] **C2 · Verify + publish the Use CalBallot page.** After A2.

- [ ] **C3 · Watch Monday's cron** (2026-08-31, 12:00 UTC) — the first
      scheduled run since the notice-role fix. Procedure if it goes
      red: `docs/setup/registrar_drift_runbook.md`.

## D. Calendar / passive

- [ ] **D1 · Backfill gate.** Two clean *unattended* cron runs unlock
      the March 2026 backfill batch. The gate has reset twice
      (Aug 10, Aug 24); current streak is one (Aug 17).
- [ ] **D2 · The November election keeps filling.** 8 rows/16 docs in
      July → 20 rows/88 docs now, arguments still being filed. Expect
      the count to keep climbing.

## E. Small loose ends

- [ ] **E1 · 18 pre-existing legacy test failures.** 1 failure + 17
      errors in `test_database.py`, `test_deduplication.py`,
      `test_models.py`. Two causes: fixtures passing `str` where
      `Database.__init__` expects a `Path` (fix: coerce with
      `Path(db_path)`), and a stale assertion that `measure.county is
      None` when the model now defaults to `'Statewide'`. Logged
      2026-07-06. **~10–30 min.**
- [ ] **E2 · `git gc`.** 1.48 GiB of loose objects versus 92 MiB of
      actual committed history — local-only, from an untracked
      CalAccess ZIP hashed into the object store. `git gc --prune=now`
      should reclaim most of it. Needs your go-ahead.
- [ ] **E3 · `weekly-pipeline.yml` stages a gitignored path.** It runs
      `git add scraper/data/ballot_measures.db`, but that file is
      ignored by `scraper/.gitignore`, so the step would fail if the
      workflow ever ran. It is manual-only today.
- [ ] **E4 · `SAN BERNADINO` misspelling.** 5 records from 2000 sit
      under a misspelled county, appearing as a 59th county in
      groupings.
- [ ] **E5 · Generator silently degrades on network failure.** The
      `historical_context` step fetches a sentence-transformers model
      from the HF Hub; when that fails the exception is swallowed into
      a warning and generation continues with a degraded artifact.
      Caught during tonight's publication only because the diff was
      reviewed. Same class as the storage fallback closed in
      `5f1cd26`. Should fail loudly.
- [ ] **E6 · Two untracked finance drafts** —
      `docs/plans/finance-v3-sprint-summary.md` and its `.pdf`. They
      sit in a normally-committed directory. Commit or move; left
      alone pending your call.

## F. Larger parked items

- [ ] **F1 · `measure_documents` table.** Blocks the nine-slot
      document indicator on cards and an official-documents section in
      the modal — the top-ranked opportunity and the thing no
      comparable tool has. Discipline to preserve: **presence is not
      content**; never fill `pro_arguments` or similar prose fields
      with URLs.
- [ ] **F2 · CAP taxonomy adoption** (from Georgia's scaffold review,
      `georgia_scaffold_integration.md`). The flagship fix for the
      ~75%-"Other" topic classification gap.
- [ ] **F3 · Post-election results ingestion.** No design exists for
      turning a pending measure into a decided one while preserving
      identity. Becomes urgent right after November 3.
- [ ] **F4 · Riverside Playwright prerequisite.** The Playwright fetch
      path delegates redirects to the browser, so per-hop robots and
      rate-limit guarantees do not apply. Resolve before enabling
      Riverside.
- [ ] **F5 · Finance backlog** — v3 monetary ingest, Schedule E
      sub-phase, donor alias coverage. Dormant since May; non-blocking.

## G. Decisions only you can make

- [ ] **G1 · Target coverage.** 50% of local measures (10 counties),
      73% (20), or all 58? This decides whether B1 is a nice-to-have
      or a precondition.
- [ ] **G2 · Acceptable red-cron rate.** At ~1 drift event per county
      per two weeks, this number sets the ceiling on county count more
      than engineering effort does.
- [ ] **G3 · Backfill vs forward-only.** Everything so far is
      forward-only. Historical backfill multiplies both value and the
      cross-source reconciliation problem (KNOWN_ISSUES #12), which
      has never run against overlapping data.
- [ ] **G4 · R2 token rotation.** Credentials passed through chat on
      2026-07-09. Two minutes to rotate; never required, still offered.
