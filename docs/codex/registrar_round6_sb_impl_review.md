# Codex review: SB scraper implementation (round 6)

> **For Codex:** Code review of the shipped Phase 1 San Bernardino
> scraper — the implementation of the design you drafted in round 4
> and amended in round 5. It is LIVE: commit `1e73f70`, weekly prod
> cron enabled, first production snapshot verified in R2
> (2026-11-03 election, 8 rows, 16/16 PDFs). Review accordingly:
> findings will be applied to running production code.
>
> Self-contained; assume no prior-session context.

## Read, in order

1. `scraper/src/scrapers/registrar/sb.py` — the review subject:
   pure extraction (`extract_measures_page`,
   `extract_discovery_candidates`) + `SbScraper`.
2. `scraper/tests/test_registrar_sb.py` — 35 tests
   (fixture-pinned, synthetic schema matrix, clock-controlled
   anchor lifecycle, integration).
3. `docs/plans/registrar_phase1_sb.md` — the binding design
   (round-4 body + round-5 amendments). The implementation claims
   full fidelity to it; verify that claim.
4. `scraper/src/scrapers/registrar/base.py` + `storage.py` — the
   primitives sb.py builds on (politeness, SnapshotWriter,
   validation). Context, not review targets.
5. `scraper/src/scrapers/registrar/runner.py` (sb registration,
   `ENABLED_COUNTIES`) + `.github/workflows/registrar_pipeline.yml`
   (`--counties=enabled` flip).
6. Fixtures: `scraper/tests/fixtures/registrar/sb/` + its README.

## Important context: the site drifted between fixtures and go-live

Fixtures were pinned 2026-07-09 (announced state: TBD rows, zero
links). By go-live 2026-07-27 the same page had evolved: 8 rows / 6
jurisdictions, letters STILL "TBD", mixed per-row publication
(some rows resolution-only; one already has an argument), and URL
prefixes the fixtures never showed (`FT_`, `AIF_` alongside `RES_`,
`IA_`). The live run succeeded because roles derive from labels and
columns, not URLs — but it means the pinned fixtures no longer
cover the richest observed state. The live bytes are stored (dev
and prod buckets, `sb/2026-11-03/`), so pinning a mixed-state
fixture is cheap if you think it's warranted (see item 7).

## What to scrutinize

1. **Extraction robustness against real-world HTML drift.** Header
   detection uses first-`<tr>`-with-`<th>` + full set equality;
   cells via `find_all("td", recursive=False)`; links via
   `find_all("a", href=True)` at any depth within a cell. Probe:
   `<thead>` appearing later, nested tables inside a cell (would
   its `td`/`a` elements leak into the outer row's cells?), header
   cells containing links, rows split across `<tbody>` elements.
2. **The TBD-letters filename consequence.** All 8 current rows
   slug to `tbd`, so every filename carries an `r{NNN}` suffix; when
   the county assigns real letters, the SAME documents get different
   filenames in later snapshots. Snapshots are independent
   observations, and `pdf_artifacts` preserves row/role mapping —
   is that sufficient for the future parser to track identity
   across snapshots, or should the audit map carry more (e.g., the
   source URL is already there — is that the stable key)?
3. **Anchor lifecycle implementation vs your round-5 spec.**
   `_as_of_date` (naive-clock UTC fallback, `astimezone(LA_TZ)`),
   active filtering, missing-anchor error, idle path, provenance
   assignment. Also: `SB_FORWARD_ANCHORS` parses via
   `date.fromisoformat` at scrape time — a typo'd anchor becomes a
   runtime county failure rather than an import-time error. OK or
   should-fix?
4. **PDF fetch policy.** Document URLs must be absolute HTTPS at
   extraction, but redirects during the PDF fetch may land anywhere
   HTTPS (per-hop robots + rate limit apply; final origin is NOT
   re-validated for PDFs, unlike the measures page). Acceptable
   under the design's "official page advertised it" rationale?
5. **Discovery strictness.** Path regex is case-insensitive with
   optional trailing slash, same-origin, valid-date. Landing-page
   fetch failure fails the county (no idle path without discovery)
   — confirm that's the right precedence vs the idle rule.
6. **Test coverage gaps.** E.g.: multi-election runs (ordering,
   one snapshot per election), landing-page redirect, header cells
   wrapped in links, `<thead>` variants, anchor-typo behavior,
   PDF-fetch redirect. Which missing tests matter enough to add?
7. **Fixture refresh policy.** Should the 2026-07-27 mixed-state
   page (bytes available in the bucket) be pinned as a third page
   fixture now, or wait until letters are assigned? Short answer
   fine.
8. **Runner/workflow flip** — registration, `ENABLED_COUNTIES`,
   the `--counties=enabled` flip, and the updated runner tests.
   Anything the flip broke or left stale (docs, comments, noop
   paths)?

## Calibration

Implementation review of production code: correctness first, then
robustness-to-drift, then test coverage. Verdicts with severity
(blocker / should-fix / nit / agree). The registrar suite is
144/144 green; coverage gaps are fair game. Don't review finance
code or anything outside the listed files.
