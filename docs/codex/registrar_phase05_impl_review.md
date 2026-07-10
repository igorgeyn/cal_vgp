# Codex review: registrar pipeline Phase 0.5 implementation (round 2)

> **For Codex:** CODE review of the now-implemented Phase 0.5
> infrastructure. Round 1 (2026-05-21,
> `docs/codex/registrar_pipeline_infra_review.md`) reviewed the
> *design*; your corrections were applied to the plan doc before
> any code. This round reviews the code built on that design.
>
> **A previous session on this review hit a session limit — treat
> this as a fresh, fully self-contained request.** Everything you
> need is in this doc + the repo files listed below. Do not assume
> any context from the interrupted session.

## Context (30 seconds)

CalBallot: searchable DB of CA ballot measures (12,365 local +
statewide), static site on GitHub Pages, Python pipeline. This arc
builds a recurring pipeline scraping county registrar sites for
local measures. Shape (round-1 blessed):

```
scrapers (per county) → R2 raw artifacts → parsers (per county)
  → normalized JSONL → loader/dedup → ballot_measures.db
```

Phase 0.5 delivered the framework (no real county scraper yet —
that's Phase 1, San Bernardino first). 72 tests green. Commits
`c40c09c` (storage) then `4b9cb94` → `b14de2f` (everything else).

## Read these, in order

1. `docs/plans/registrar_pipeline_infra.md` — the round-1-reviewed
   design the code implements
2. `scraper/src/scrapers/registrar/storage.py` — store protocol,
   Local + R2 impls, `make_store()` factory
3. `scraper/src/scrapers/registrar/base.py` — `CountyRegistrarScraper`
   ABC: polite fetch + `SnapshotWriter`
4. `scraper/src/scrapers/registrar/noop.py` — wiring-proof scraper
5. `scraper/src/scrapers/registrar/runner.py` — per-county
   isolation, run manifests, exit codes (CLI shim:
   `scraper/scripts/run_registrar_pipeline.py`)
6. `.github/workflows/registrar_pipeline.yml`
7. Tests: `scraper/tests/test_registrar_{storage,base,runner}.py`

## Locked — don't relitigate

- R2 + GH Actions cron + counties-only scope (Igor signoff, round 1)
- Artifact-store-as-canonical-truth, 4-stage pipeline, JSONL
  intermediate (round-1 outcome)
- Immutable snapshots keyed `{env}/{county}/{election_date}/{snapshot_id}/`.
  NOTE: the plan doc showed a `raw/{env}/...` top segment; as-built
  drops `raw/` (run manifests live under `runs/{env}/...`, county
  slugs can never be "runs"). The as-built layout is canonical —
  flag only if you see a concrete hazard.
- Exit nonzero on ANY county failure; concurrency group keyed on
  env not event_name (both were self-audit fixes, already applied)
- Playwright as a full dependency now (Igor's explicit call)
- Polite-UA defaults (empirically required: San Diego 403s generic
  UAs, validated 2026-06-08)

## What to scrutinize

### A. `base.py` — politeness + retry semantics

- Retry matrix: 429/5xx/connection errors retried with 2/4/8s
  backoff; other 4xx raise immediately. `Retry-After` header is
  currently ignored on 429 — worth honoring, or over-engineering
  at this stage?
- Rate limiter is per-domain, per-*instance*, monotonic-clock. The
  robots.txt fetch itself is not rate-limited, and the robots
  check runs before the rate-limit wait. Runner is sequential so
  instances never race today. Structural problems for Phase 1+?
- robots.txt: `RobotFileParser.can_fetch()` receives our full UA
  string; unfetchable robots (4xx/timeout) = allow-all; parser
  cached per origin with no TTL (process-lifetime). Sound?
- Playwright path: single attempt, `networkidle` wait, no
  Cloudflare-challenge detection — deliberately thin until
  Riverside (Phase 1). Anything here that won't extend cleanly?

### B. `SnapshotWriter` — atomicity model

- Manifest written LAST; save-after-finalize raises. A crash
  mid-snapshot leaves orphan artifacts with no manifest —
  invisible to parsers by design, never garbage-collected (R2
  storage cost is trivial). Acceptable, or does the orphan pile
  need a story?
- `snapshot_id` is second-granularity UTC. Collisions are guarded
  by the prod concurrency group + per-(county, election) pathing.
  Enough?

### C. `runner.py`

- Per-county isolation catches bare `Exception` (not
  `BaseException`, so Ctrl-C still kills). Too broad, or right for
  an unattended cron?
- Run manifest: local file (CI artifact) + best-effort mirror into
  the store — mirror failure logs a warning but never reds the
  run. Reasoning: artifact puts would have failed loudly first, so
  the mirror isn't the canary. Agree?
- `--counties=enabled` resolving to an empty set exits 0 with a
  warning (legitimate pre-Phase-1 state). Should it fail instead
  once real counties exist?

### D. `R2ArtifactStore`

- Not-found detection duck-types botocore `ClientError`
  (`.response["Error"]["Code"] in {NoSuchKey, 404, NotFound}`)
  instead of importing botocore — keeps boto3 lazy and tests
  network-free. Robust enough against botocore's actual behavior?
- Whole-body bytes puts, no multipart/streaming. Registrar
  HTML/PDFs are KB-to-low-MB; flag if that assumption is fragile.
- `exists()` via `head_object` (with filename) / `list_objects_v2
  MaxKeys=1` (snapshot-level). boto3 default retry config
  untouched. `region_name="auto"` per R2 convention.

### E. Workflow / CI — our biggest self-flagged concern

**Silent local fallback in prod.** `make_store()` falls back to
`LocalArtifactStore` unless all four `R2_*` env vars are set.
Pre-provisioning this is deliberate (the workflow runs as a wiring
smoke test with no secrets). But post-provisioning, a deleted or
typo'd secret means a prod cron run writes artifacts to ephemeral
CI disk and reports **green** while durably storing nothing.
Options we see:

- (a) fail loudly when `GITHUB_ACTIONS` is set but R2 vars aren't
- (b) a `--require-r2` flag the workflow passes
- (c) `store_backend` field in the run manifest + a workflow step
  that asserts it says `r2`

Which (or what else)? This is the one place we'd most like a
strong opinion.

Also: push-trigger noise (fires on any registrar-path commit),
Playwright chromium install on every run (~30s, accepted), pip
cache keyed on requirements.

### F. Missing concerns

Phase 1 (SB scraper) builds directly on this. What's absent that
will hurt when real HTML starts flowing — encoding handling,
content-type surprises, election-date discovery, manifest schema
versioning discipline, test seams we'll wish we had?

## Calibration

Implementation review: correctness, robustness, API shape. Round-1
level of rigor. Bullet feedback with severity (blocker / should-fix
/ nit) is ideal. 72 tests exist — coverage gaps are fair game.
Don't review the finance code or anything outside the files listed.
