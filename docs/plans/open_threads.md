# Open threads

> **The "what do I actually do next" checklist**, in one place. For the
> durable backlog read [`../WORKING_LIST.md`](../WORKING_LIST.md); for
> the Bay Area county sequence and its architectural debts read
> [`bay_area_county_workstream.md`](bay_area_county_workstream.md); for
> per-county state read [`county_status.md`](county_status.md).
>
> Undated filename on purpose — this file is updated in place rather
> than re-created per session. **Last updated: 2026-08-31** (amended after the Alameda/Santa Clara scout).

**State:** San Bernardino live (20 measures / 105 documents, 6 prod
snapshots). Compact local-measure cards published (`dbc7609`). Use
CalBallot page live (`a5518ca`) with the About-modal button
(`164cdc6`). Capture/interpretation decoupling shipped (`edb2978`).
Bay Area recon done (`363f27b`). **San Mateo build in flight with
Codex.** 196 registrar/website tests green; 18 pre-existing legacy
failures (§E1). 4 commits ahead of origin, unpushed.

---

## A. Bay Area workstream — Track A: San Mateo (in flight)

Detail in [`bay_area_county_workstream.md`](bay_area_county_workstream.md) §4.

- [ ] **A1 · Build.** Codex, per
      [`../codex/san_mateo_scraper_build.md`](../codex/san_mateo_scraper_build.md).
      3–5 days.
- [ ] **A2 · Review round.** The one that matters is **D3**: any new
      role name must be added to `_ROLE_PRIORITY` deliberately, or
      every measure re-anchors its identity on `analysis`. Also verify
      the label census (29 impartial analyses, `in Favor`/`In Favor`
      casing, non-measure PDFs excluded).
- [ ] **A3 · Hoist shared contracts to `contracts.py` (debt D1).**
      ~0.5 day. No county module should import another county module.
- [ ] **A4 · Dev smoke, then enable** as a separate reviewed commit.
- [ ] **A5 · Parse → load → publish.** 29 measures onto the
      local-measures band; makes the county toggle load-bearing.

**Gate:** one clean unattended cron run with two counties enabled
before starting a third.

## B. Track B: Alameda

- [ ] **B1 · Rename the table-shaped contract (debt D2).** 1 day,
      after San Mateo, with two real page shapes in hand.
- [x] **B2 · OCR spike — CANCELLED 2026-08-31, answered by scouting.**
      569 pages across 30 PDFs, **11 pages (2%) with extractable
      text**, 22 of 28 packets with none. No partial path exists.
- [ ] **B3 · Build**, **3–4 days** (was 5–8; OCR was the difference).
      Capture packets whole as `role="packet"`; take letter,
      jurisdiction, title, threshold and full ballot question from the
      HTML fragment. **Two hosts** — election page on
      `acvote.alamedacountyca.gov`, measures on `alamedacountyca.gov`.
      Exclude non-measure PDFs **by path** (`/Random Alpha/`), join
      the hosts **on letter** (casing differs), and never load the
      four `N/A` thresholds as values.

## C. Track C: gated counties (parallel, non-blocking)

- [ ] **C1 · Santa Clara — BLOCKED, and not by C3.** Every host
      (`vote.santaclaracounty.gov`, `sccvote.sccgov.org`,
      `www.sccgov.org`, and their `robots.txt`) returns HTTP 403
      "Attention Required!" — a firewall block, not the 503 challenge
      Playwright solves. No open-data alternative
      (`data.sccgov.org` has zero measure datasets). **Next move is an
      email to the Registrar**, not engineering. See G6.
- [ ] **C2 · San Francisco — re-probe weekly** until the voter guide
      leaves maintenance. Do not build against the 503 shell.
- [ ] **C3 · Playwright politeness prerequisite.** ~1–2 days,
      unblocks **two** counties (Contra Costa, Riverside) — Santa
      Clara's 403 is not browser-solvable. Supersedes old F4.
- [ ] **C4 · Contra Costa browser recon.** After C3. Forward
      publication is *unknown*, not absent.

**Decision point ~Sept 20:** anything still gated past that date
cannot land before ballots mail (~Oct 5). Cut for this cycle.

## D. Calendar / passive

- [ ] **D1 · Backfill gate.** Two clean *unattended* cron runs unlock
      the March 2026 backfill. **Status unverified** — see D3.
- [ ] **D2 · November keeps filling.** 8 rows/16 docs (Jul 27) → 20
      rows/105 docs (Aug 31). Rebuttals first appeared Aug 31.
- [ ] **D3 · Confirm the Aug 31 cron actually fired on schedule.**
      Cron is `0 12 * * 1` (Mon 12:00 UTC). The prod snapshot is
      `20260831T185331Z` — **18:53 UTC, not 12:00**, so it was
      probably a dispatch or push run, not the scheduled one. Local
      run manifests only cover dev runs, so this needs a look at
      GitHub Actions. Matters because D1 counts *unattended* runs.

## E. Small loose ends

- [ ] **E1 · 18 pre-existing legacy test failures.** `test_database.py`,
      `test_deduplication.py`, `test_models.py`. Two causes: fixtures
      passing `str` where `Database.__init__` expects a `Path`, and a
      stale assertion that `measure.county is None` when the model now
      defaults to `'Statewide'`. **~10–30 min.**
- [ ] **E2 · `git gc`.** 1.48 GiB loose objects vs 92 MiB of real
      history, from an untracked CalAccess ZIP. Needs your go-ahead.
- [ ] **E3 · `weekly-pipeline.yml` stages a gitignored path.**
      `git add scraper/data/ballot_measures.db` would fail if the
      workflow ever ran. Manual-only today.
- [ ] **E4 · `SAN BERNADINO` misspelling.** 5 records from 2000
      appear as a 59th county in groupings.
- [ ] **E5 · Generator silently degrades on network failure.** The
      `historical_context` step swallows a sentence-transformers fetch
      failure into a warning and publishes a degraded artifact. Should
      fail loudly. Same class as the storage fallback closed in
      `5f1cd26`.
- [ ] **E6 · Two untracked finance drafts** —
      `finance-v3-sprint-summary.md` and its `.pdf`, sitting in a
      normally-committed directory. Commit or move.
- [ ] **E7 · CLAUDE.md names the wrong live domain.** Says
      `calballot.com`; `CNAME` and every canonical URL use
      `cal-vgp.igorgeyn.com`. One line, and it has already misled a
      plan.
- [ ] **E8 · Push.** 4 commits ahead of origin.

## F. Larger parked items

- [ ] **F0 · Regional measures span counties.** "Measure RTM" is one
      measure on five county ballots (Alameda, Contra Costa, San
      Mateo, Santa Clara, SF), published under different names and
      thresholds. Per-county identity minting gives five unrelated
      records. **Decide before San Mateo lands** — suggested shape is
      a shared nullable `regional_measure_key` over per-county rows.
- [ ] **F1 · `measure_documents` table.** SB captures 105 documents;
      the DB stores **one `pdf_url` per measure**. San Mateo adds ~135
      more. Largest piece of captured-but-unused value in the project.
      Discipline: **presence is not content** — never fill
      `pro_arguments` with URLs.
- [ ] **F2 · CAP taxonomy adoption.** The flagship fix for the
      ~75%-"Other" topic classification gap.
- [ ] **F3 · Post-election results ingestion.** No design exists for
      turning a pending measure into a decided one while preserving
      identity. **Urgent right after November 3.**
- [ ] **F5 · Finance backlog** — v3 monetary ingest, Schedule E
      sub-phase, donor alias coverage. Dormant since May.
- [ ] **F6 · Automated drift triage.** ~3 days, worth doing after
      Alameda. The failure already names the row, cell and rule; it
      could open a PR with the proposed role addition and a pinned
      fixture. Reduces cost per event once event count is what scales.

*(F4 — Riverside Playwright prerequisite — is now C3, since it gates
Contra Costa as well as Riverside.)*

## G. Decisions only you can make

- [ ] **G1 · Target coverage.** Six counties (24.6%), ten (50%),
      twenty (73%), or all 58?
- [ ] **G2 · Acceptable red-cron rate.** Post-decoupling the estimate
      is ~0.8/week at five counties, down from ~2.5. This number sets
      the county ceiling more than engineering effort does.
- [ ] **G3 · Backfill vs forward-only.** Backfill multiplies both
      value and the never-exercised cross-source reconciliation
      problem (KNOWN_ISSUES #12).
- [ ] **G4 · R2 token rotation.** Credentials passed through chat
      2026-07-09. Two minutes; never required, still offered.
- [x] **G5 · Alameda OCR fallback — RESOLVED by measurement.** Role
      segmentation is not merely unreliable, it is impossible without
      OCRing 569 scanned pages. Whole-packet it is.
- [ ] **G6 · Santa Clara: email the Registrar?** The honest path to a
      403-blocked county is to ask for an allowlist entry or a feed.
      Costs one email; plausibly works. The alternative is deferring
      the county to 2028. Spoofing a browser UA should stay off the
      table.
- [ ] **G7 · Regional measure modeling.** See F0 — five near-duplicate
      cards, or one cross-linked measure?

---

## Done since 2026-08-27

- [x] **Compact local-measure cards** — built `9b78e9d`, published
      `dbc7609`.
- [x] **Use CalBallot prominence** — promoted to a button in second
      position in the About modal (`164cdc6`), per your call to keep
      it in About rather than the header, without disturbing the
      existing text flow.
- [x] **Capture/interpretation decoupling** (old B1) — `edb2978`. A
      new document label now reds an offline parse, not the weekly
      cron.
- [x] **Bay Area recon sweep** (old B2) — `363f27b`. Answered the
      strategic question: San Bernardino is *not* unusual in
      publishing ahead.
- [x] **Use CalBallot page** — `a5518ca`, reviewed 2026-08-27.
- [x] **Los Angeles reprioritized** (old B3) — recon disqualified it
      for November; it publishes at/after Election Day. Now a
      standalone archive project, workstream Track D.
