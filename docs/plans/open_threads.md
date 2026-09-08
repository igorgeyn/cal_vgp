# Open threads

> **September 8 release:** Igor approved F1. Production loading and the actual
> paired-build gate passed: 49 measures with 239 official-document links.
> Release `ec89711` is deployed and verified at https://cal-vgp.igorgeyn.com/; see
> [the current release handoff](f1_post_review_release_20260908.md).
> Next is the capture/parse/publication handoff, then election-status rendering.
> Earlier load/publication status below is historical.

> **September 7 priority update:** Igor accepted F1 and reliable updates before
> expansion; two useful counties by October 5, Alameda conditional. Budget:
> 10 Igor-hours/week plus LLM execution. The sequence below is the August 31
> backlog; [forward_plan_20260907.md](forward_plan_20260907.md) supersedes its
> ordering. San Mateo is loaded locally (20 SB + 29 SMC); publication was still
> pending in the review brief. F1 is now implemented and verified on a copy,
> with no production load or publication; see
> [official_documents_20260907.md](official_documents_20260907.md).

> **The "what do I actually do next" checklist**, in one place. For the
> durable backlog read [`../WORKING_LIST.md`](../WORKING_LIST.md); for
> the Bay Area county sequence and its architectural debts read
> [`bay_area_county_workstream.md`](bay_area_county_workstream.md); for
> per-county state read [`county_status.md`](county_status.md).
>
> Undated filename on purpose — updated in place.
> **Last updated: 2026-08-31, ~20:30** (after San Mateo enablement).

**State:** Two counties captured, one published. San Bernardino live
(20 measures / 105 documents). **San Mateo built, reviewed, enabled,
and captured to production** — snapshot `20260901T024142Z`, 29
measures / 135 documents / 167 role records, verified independently
from R2. **Not yet loaded or published.** A5 in flight with Codex.
239 registrar/website tests green; 18 pre-existing legacy failures
(§E1). 1 commit ahead of origin.

---

## A. Track A: San Mateo — publish

- [ ] **A5 · Parse → load → publish.** Prompt at
      [`../codex/san_mateo_publish.md`](../codex/san_mateo_publish.md).
      Three gates: dry-run shows **29 inserts, zero updates, zero
      deactivations**; San Bernardino's 20 measures byte-identical
      after the load; **artifact diff read before committing.** The
      generator swallows a `historical_context` network failure into a
      warning and publishes degraded — if that warning appears, stop
      and re-run (§E5).
      Folds in two fixes: the stale `LOCAL_COUNTY_ROADMAP`, and
      confirming the empty-letter regional measure renders as "Local
      measure" with no raw `REG_SMC_` string anywhere.

**Gate to Track B: one clean unattended cron run with two counties.**
That is **Monday Sept 7**, the first `enabled` run since San Mateo
joined. Do not start a third county before it.

## B. Track B: Alameda

Two things should land *before* the build, not after.

- [ ] **B1 · Rename the table-shaped contract (debt D2).** ~1 day.
      `column` → `group`, `table_row` → `row_index`, `headers` →
      `columns`. Two real page shapes now exist to fit the names to,
      and both implementations annotate them as misnomers. Touches
      `origin_table_row`, persisted in `registrar_identities`, so it
      needs a migration or dual read. **Re-run the SB identity A/B
      after** — the same three fixture scenarios.
- [ ] **F0 should land here too**, since Alameda ships the same
      regional transit measure. See below.
- [ ] **B3 · Build Alameda**, **3–4 days**. Capture packets whole as
      `role="packet"`; take letter, jurisdiction, title, threshold and
      full ballot question from the HTML fragment. Two hosts —
      election page on `acvote.alamedacountyca.gov`, measures on
      `alamedacountyca.gov`. Exclude non-measure PDFs **by path**
      (`/Random Alpha/`), join hosts **on letter** (casing differs),
      and never load the four `N/A` thresholds as values.

## C. Track C: gated counties (parallel, non-blocking)

- [ ] **C1 · Santa Clara — blocked on a decision, not on engineering.**
      Every host returns HTTP 403 "Attention Required!", a firewall
      block rather than a solvable challenge. See G6.
- [ ] **C2 · San Francisco — re-probe weekly** until the voter guide
      leaves maintenance. Do not build against the 503 shell.
      4–7 days once live.
- [ ] **C3 · Playwright politeness prerequisite.** ~1–2 days, unblocks
      **two** counties (Contra Costa, Riverside).
- [ ] **C4 · Contra Costa browser recon.** After C3. Forward
      publication is *unknown*, not absent.

**Decision point ~Sept 20:** anything still gated then cannot land
before ballots mail (~Oct 5). Cut it to 2028 and stop spending probe
time.

## D. Calendar / passive

- [ ] **D1 · Backfill gate.** Two clean *unattended* cron runs unlock
      the March 2026 backfill. Status unverified — see D3.
- [ ] **D2 · Watch the Sept 7 cron.** First two-county `enabled` run.
      Per-county isolation means a San Mateo failure should not reset
      San Bernardino's streak; confirm that holds in practice.
- [ ] **D3 · Confirm the Aug 31 cron fired on schedule.** Cron is
      `0 12 * * 1`; the prod snapshot is `20260831T185331Z` — 18:53
      UTC, hours off. Needs a look at the Actions history. Matters
      because D1 counts unattended runs.
- [ ] **D4 · November keeps filling.** SB: 16 → 105 documents since
      July. San Mateo appears near-complete (33 rebuttals already
      filed), but expect movement.

## E. Small loose ends

- [ ] **E1 · 18 pre-existing legacy test failures.** `test_database.py`,
      `test_deduplication.py`, `test_models.py`. Fixtures passing
      `str` where `Database.__init__` expects a `Path`, and a stale
      assertion that `measure.county is None`. **~10–30 min.**
- [ ] **E2 · `git gc`.** 1.48 GiB loose objects vs ~92 MiB of real
      history. Needs your go-ahead.
- [ ] **E3 · `weekly-pipeline.yml` stages a gitignored path.**
      `git add scraper/data/ballot_measures.db` would fail if it ran.
      Manual-only today.
- [ ] **E4 · `SAN BERNADINO` misspelling.** 5 records from 2000 appear
      as a 59th county.
- [ ] **E5 · Generator degrades silently on network failure.** The
      `historical_context` step swallows a sentence-transformers fetch
      failure into a warning and publishes anyway. **Live risk during
      A5.** Should fail loudly.
- [ ] **E6 · Two untracked finance drafts** in `docs/plans/`.
- [ ] **E7 · CLAUDE.md names the wrong live domain** —
      `calballot.com` vs the real `cal-vgp.igorgeyn.com`.
- [ ] **E8 · Push.** 1 commit ahead.
- [ ] **E9 · The "Upload normalized JSONL" workflow step does
      nothing.** CI never runs the parser, so
      `scraper/data/registrar_normalized/*.jsonl` is always empty and
      the step uploads no files while reporting success. Either wire
      the parse into CI or drop the step. **Wiring it is the better
      shape** — the parse would run where R2 secrets already live, and
      loading locally from a downloaded JSONL would need no local R2
      credentials at all.
- [ ] **E10 · Fixture size trajectory.** San Mateo's fixtures are
      5.3 MB, 4.9 MB of it two PDFs. Alameda's packets are 5–56 pages
      of scans and will be larger. Decide deliberately — possibly
      first-pages excerpts for scanned counties — rather than
      discovering it at county ten.

## F. Larger parked items

- [ ] **F0 · Regional measures span counties.** One transit measure is
      on five county ballots (Alameda, Contra Costa, San Mateo, Santa
      Clara, SF), published under different names and thresholds —
      Alameda calls it `Measure RTM` at `N/A`, San Mateo `Regional
      Measure` at majority. Per-county identity minting gives
      unrelated records. **Land it with B1, before Alameda.**
      Suggested shape: keep per-county rows, add a shared nullable
      `regional_measure_key`. Would also let the card show "Regional
      Measure" — San Mateo's own published section heading — instead
      of the current honest-but-bland "Local measure".
- [ ] **F1 · `measure_documents` table.** SB captures 105 documents,
      San Mateo 167 role records; the DB stores **one `pdf_url` per
      measure**. Largest piece of captured-but-unused value in the
      project, and it grows with every county. Discipline:
      **presence is not content** — never fill `pro_arguments` with
      URLs.
- [ ] **F2 · CAP taxonomy adoption.** The flagship fix for the
      ~75%-"Other" topic classification gap.
- [ ] **F3 · Post-election results ingestion. The one with a real
      deadline.** On November 4 every measure flips from pending to
      decided, and **no design exists** for that transition while
      preserving identity — which is the entire point of the registrar
      identity system. Nine weeks out. Design it well before it is
      needed.
- [ ] **F5 · Finance backlog** — v3 monetary ingest, Schedule E
      sub-phase, donor alias coverage. Dormant since May.
- [ ] **F6 · Automated drift triage.** ~3 days, after Alameda. The
      failure already names the row, cell and rule; it could open a PR
      with the proposed role addition and a pinned fixture.
- [ ] **F7 · Generalize `verify_registrar_identity.py`.** Hardcodes
      `COUNTY = "sb"` and `REQUIRED_SNAPSHOT_COUNT = 5`. San Mateo has
      one production snapshot, so its identity-history gate cannot
      exist yet. Revisit at ~5 snapshots (early October).

## G. Decisions only you can make

- [ ] **G1 · Target coverage.** Six counties (24.6%), ten (50%),
      twenty (73%), or all 58?
- [ ] **G2 · Acceptable red-cron rate.** Post-decoupling the estimate
      is ~0.8/week at five counties, down from ~2.5. This sets the
      county ceiling more than engineering effort does.
- [ ] **G3 · Backfill vs forward-only.** Backfill multiplies both
      value and the never-exercised cross-source reconciliation
      problem (KNOWN_ISSUES #12).
- [ ] **G6 · Santa Clara: email the Registrar?** The honest path to a
      403-blocked county is to ask for an allowlist entry or a feed.
      One email, plausible yes. Alternative is deferring to 2028.
      Spoofing a browser UA stays off the table.
- [ ] **G7 · Regional measure modeling.** See F0 — five near-duplicate
      cards, or one cross-linked measure?

---

## Done

**2026-08-31 (evening) — San Mateo, county #2**

- [x] **A1 · Build** — `395d763`. 29 measures; composite documents
      modeled as one PDF expanded per role; the `/archival-document`
      redirector unwrapped and its target validated.
- [x] **A2 · Review** — three findings, all closed in round two. The
      critical gate (San Bernardino's IDs unchanged under the shared
      `_origin_key` edit) verified by A/B rather than assertion.
- [x] **A3 · `contracts.py` hoist** — `57c516d`. Six dataclasses plus
      `RegistrarInterpretationError`; SB and SMC errors are now
      siblings, not parent/child. No county module imports another.
      Landed inside round two rather than as its own arc.
- [x] **A4 · Enable + first production capture** — `04db0dc`.
      Identity gate passed on the push run; dispatch `33463432886`
      captured `20260901T024142Z`.
- [x] **G4 · R2 token rotation** — open since 2026-07-09. New scoped
      token; `.env` at the repo root (gitignored) as the durable local
      copy; GitHub secrets updated; credentials verified reading prod
      R2. **Two dead tokens still to delete in Cloudflare.**
- [x] **G5 · Alameda OCR fallback** — resolved by measurement, not
      judgment: 569 pages, 11 with extractable text (2%).
- [x] **B2 · Alameda OCR spike** — cancelled; the scout answered it.

**Earlier**

- [x] Compact local-measure cards (`9b78e9d` / `dbc7609`); Use
      CalBallot page (`a5518ca`) and its About-modal promotion
      (`164cdc6`); capture/interpretation decoupling (`edb2978`); Bay
      Area recon sweep (`363f27b`); Los Angeles reprioritized to
      archive-only after recon disqualified it for November.
