# Codex request: draft the Phase 1 San Bernardino scraper design (round 4)

> **For Codex:** This round you DRAFT, not review. Produce a
> complete design document for `SbScraper` — the first real county
> scraper — as a markdown doc we can commit to
> `docs/plans/registrar_phase1_sb.md` after Igor's direction-check.
> Design only: illustrative signatures and data shapes are welcome;
> full implementation code is not.
>
> **Self-contained request; assume no context from prior sessions.**
> Rounds 1–3 live in `docs/codex/` if you want history, but
> everything binding is below.

## Read first, in order

1. `docs/plans/registrar_manifest.md` — Phase 0 recon; the San
   Bernardino section is your source of truth for URL patterns and
   page shape. (If you have network access, verifying live against
   `elections.sbcounty.gov` is welcome — note discrepancies. If
   not, treat recon as ground truth and mark assumptions.)
2. `scraper/src/scrapers/registrar/base.py` — the base class your
   design must build on: `fetch()` (polite, per-hop robots + rate
   limit, Retry-After, manual redirects), `open_snapshot()` →
   `SnapshotWriter` (manifest-last, duplicate filenames rejected,
   completed snapshots immutable).
3. `scraper/src/scrapers/registrar/storage.py` — storage contract:
   filenames are single safe path components (no separators, no
   `..`, no Windows reserved names), `manifest.json` reserved,
   manifests are create-only.
4. `scraper/src/scrapers/registrar/noop.py` + `runner.py` — the
   wiring `SbScraper` drops into (`ScrapeResult`, `ENABLED_COUNTIES`,
   per-county failure isolation, run manifests).
5. `docs/WORKING_LIST.md` "Next chunk" — the six locked design
   decisions (also restated below).

## Binding constraints (locked in rounds 1–3; do not redesign)

1. **Hybrid election enumeration.** Versioned static anchor list =
   coverage contract; weekly discovery from the SB index page adds
   candidates only after strict validation (ISO-convertible date,
   expected measures-table headers, same-origin URL). Discovery
   yielding nothing, or losing a known anchor, fails loudly.
2. **Forward-only first**, then bounded manual backfill in explicit
   date-bounded batches.
3. **Always snapshot** — no skip-if-unchanged logic in Phase 1;
   checksums/ETags land in manifests for later comparison.
4. **Semantic deterministic PDF filenames** (e.g.
   `measure_v_analysis.pdf`, `measure_v_argument_for.pdf`, stable
   row suffix if letters collide) — never URL basenames or link
   text. Resolve relative links; off-domain HTTPS only when linked
   from the official page; reject non-HTTP(S) schemes; require PDF
   content-type or `%PDF-` signature before saving.
5. **Fail the county on a missing expected PDF.** Advertised-but-
   unfetchable documents = incomplete raw truth: leave orphan
   artifacts, write NO manifest, record county failure, retry next
   week. Blank table cells = "not expected", not failures.
6. **Fixtures before code.** Live HTML/PDF fixtures pinned first;
   table extraction is a pure function identified by the full
   header set (not column position); preserve response bytes for
   encoding decisions; distinguish zero-measure elections from
   unpublished/404 pages.

Architecture invariants: raw-artifact capture only (parsing to
normalized JSONL is a separate later deliverable); one snapshot per
(county, election_date) per run; snapshot immutability; scraper
uses ONLY base-class primitives — if the base class is missing a
primitive the design needs, say so explicitly rather than designing
around it.

## What the design doc must cover

1. **Scope statement** — what Phase 1 SB does and explicitly does
   not do (no parser, no DB writes, forward-only initially).
2. **Election enumeration module** — static anchor list format +
   where it lives (code vs config), index-page discovery flow,
   validation rules, failure modes. How `/elections/measures/`
   (cross-election landing) vs `/elections/{year}/{mmdd}/measures/`
   are used.
3. **Per-election scrape flow** — fetch page → extract rows →
   derive expected artifact list → fetch PDFs → save via
   SnapshotWriter → finalize. Where each locked constraint bites.
4. **Filename derivation spec** — exact scheme incl. collision
   suffix rule, and how it satisfies the storage validator.
5. **Manifest extras** — `election_url`, discovery provenance
   (anchor vs discovered), expected-vs-saved PDF counts, table row
   count, anything else audit needs.
6. **Failure semantics table** — for each failure class (index page
   down, measures page 404 vs zero-measure, PDF 404, PDF wrong
   content-type, robots disallow, table headers changed): what
   happens, what the run manifest records, what retries next week.
7. **Fixture + test plan** — which live pages/PDFs to pin, the pure
   parse function's contract, the test matrix (incl. relative/
   absolute links, duplicate letters, malformed PDFs, late-populated
   election pages, encoding).
8. **Rollout steps** — implementation order, adding `"sb"` to
   `ENABLED_COUNTIES`, flipping the workflow from `--counties=noop`
   to `--counties=enabled`, first-production-run verification
   checklist (mirroring the R2 setup doc §6 pattern).
9. **Open questions for Igor** — anything genuinely his call, kept
   short.

## Calibration

Concrete and opinionated: one recommended design, not option menus
(binding constraints already settled the big forks). Where the
recon manifest is ambiguous (e.g. exact table header strings,
argument-link variants), state the assumption and mark it as a
fixture-pinning task. Target length: the doc a careful implementer
could build from without asking questions — roughly the shape of
`docs/plans/registrar_pipeline_infra.md`.
