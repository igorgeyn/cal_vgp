# Codex review: local-measure pipeline infrastructure (Phase 0.5)

> **For Codex:** Architecture/design review, not a code review.
> We're scoping the infrastructure scaffolding for a recurring
> pipeline that scrapes California county registrar websites and
> ingests local ballot measures. No code committed yet — this is
> the plan that Phase 1 (first live scraper) will drop into.
>
> Live doc: `docs/plans/registrar_pipeline_infra.md` (345 lines,
> committed at `38ef3c2`). Read that whole file first. This review
> request just frames what to scrutinize.

## Context

- **Current state:** 12,365 local measures in `ballot_measures.db`,
  ~89% from CEDA (1998–2024, vote-outcome-only, no ballot text).
  No local-measure pipeline today — Ballotpedia + CEDA + ICPSR are
  one-shot ingests, not recurring.
- **Goal:** real pipeline that pulls from county registrar
  websites on a schedule, captures raw artifacts (HTML/PDF), parses
  into normalized records, loads to the existing DB. First counties
  are LA, San Diego, Orange, Riverside, San Bernardino (~50% of CA
  population).
- **Already decided** (Igor signoff): Cloudflare R2 for object
  storage, GH Actions cron from day one, counties-only scope at
  first (defer city/special-district clerks).
- **Architecture proposed:**
  ```
  scrapers (per county) → R2 raw artifacts → parsers (per county)
    → normalized JSONL → loader/dedup → ballot_measures.db
  ```

## What we want from you

### A. Architecture sanity check

The artifact-store-as-canonical-truth pattern (scrapers don't write
to DB directly; raw HTML/PDF goes to R2 first, then parsers read
artifacts and emit JSONL, then a loader handles DB merge) is the
core architectural decision. Reasons given:
1. Audit trail when sites change — re-parse old snapshots
2. Coverage queries on the intermediate JSONL without DB joins
3. One shared loader instead of 58

**Is this the right shape, or is there a simpler architecture
that achieves the same goals?** Particularly:
- Is the JSONL intermediate earning its keep, or could we go
  scraper-direct-to-DB and use the R2 artifacts only for
  re-processing-after-the-fact?
- Is the 4-stage pipeline (scrape / store / parse / load) the
  right granularity, or would 3 stages (scrape+parse → store →
  load) be simpler?

### B. R2 bucket layout

Proposed: single bucket `cal-vgp-registrar-raw` with prefix
structure `{county}/{election_date}/{filename}` + per-snapshot
`manifest.json` with SHA256 + source URLs + scraper version +
timestamps. Snapshots are immutable within a folder; re-scrapes
of a different draft produce a new dated folder.

**Specific concerns:**
- Is the immutability rule right, or do we want overwrite-with-
  history (using R2 object versioning) to handle in-cycle ballot
  language updates?
- Is the per-snapshot manifest pulling its weight, or could we
  just rely on filesystem walks of the bucket?
- Single bucket vs per-county buckets — any reason to split?
- Should the prefix include scraper version or just county +
  date?

### C. GH Actions workflow

Single workflow, single job, per-county parallelism via Python
concurrency (not a matrix). Cron on Mondays 4am PT (election
cycle); manual dispatch; push trigger on scraper code changes.
**No DB writes in CI** — CI produces JSONL workflow artifacts;
DB loader runs locally.

**Specific concerns:**
- Single job vs matrix-per-county — we chose single job to keep
  secrets/state management simple. Tradeoff worth re-examining?
- "Push trigger on scraper code changes" — useful early signal
  for code breakage but could be noisy. Worth it?
- The "CI doesn't write to DB" design is conservative for Phase 1
  — saves us from having a CI bot commit to main. Phase 3 might
  reconsider. Sound?
- Failure handling is minimal at first (echo to job output, no
  auto-issue). Worth doing more upfront?

### D. `RawArtifactStore` abstraction

Proposed Python protocol with R2 + local-filesystem impls. Local
fs is the dev default (no cloud creds needed); R2 used when env
vars present. Same interface, swappable via `make_store()`.

**Specific concerns:**
- Is the protocol shape right (`put` / `put_manifest` / `get` /
  `list_snapshots`)? Missing methods?
- Should `put` accept a stream rather than bytes (for very large
  PDFs)?
- Error handling not specified — what should `get` do on missing
  artifact, partial download, etc.?
- Versioning — if we ever do switch to overwrite-with-history,
  does the abstraction handle it cleanly?

### E. Phase 0.5 scope vs Phase 1 deliverables

Phase 0.5 deliverable: framework only. Workflow runs successfully
with `0 scrapers enabled, 0 counties processed`. Phase 1 adds the
first scrapers and they drop into this framework.

**Is the Phase 0.5 / Phase 1 split reasonable, or are we
front-loading too much infrastructure before validating the
scraping side actually works?**

A counter-argument: skip Phase 0.5, build one scraper end-to-end
(scrape → DB), THEN extract the pipeline architecture once we know
what the scraping reality looks like. Specifically: would
discovering that LA's site needs Playwright force a different
artifact-store shape (storing rendered DOM vs raw HTML), and is
the abstraction premature without that knowledge?

### F. Missing concerns

Things I might not have thought of:
- Rate limiting per-county (respectful scraping)
- robots.txt compliance
- User-agent + contact info ("polite scraper" headers)
- Anti-bot measures (CAPTCHA, IP blocking) — what's the fallback?
- Cost monitoring — R2 is cheap but unbounded scraping could grow
- Data retention — do we ever delete old snapshots?
- PII or sensitive data leaking into snapshots (precinct-level
  results sometimes have addresses)
- Legal: are we OK scraping county registrar sites? They're
  public-records sites, but worth thinking about.

**Flag anything you'd add to the Phase 0.5 doc.**

### G. The three open questions in the doc

The infra doc itself ends with three open questions for Igor.
Briefly: (1) Cloudflare account setup walkthrough now or later;
(2) GH Actions cost (public repo so free, confirm); (3) CI write-
back to DB in Phase 1 or stay JSONL-only.

**Any opinions on these worth Igor hearing?**

## Calibration

This is design taste + practical-experience review, not arithmetic
correctness. Earlier rounds on this project caught real SQL and
attribution bugs; this round is about whether the pipeline shape
is right *before* we commit to it. Short bullet feedback fine.

Particularly interested in: anything you've seen in similar
data-pipeline projects that bit you that I should design around.
