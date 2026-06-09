# Local-measure pipeline: Phase 0.5 infrastructure sketch

> **Purpose:** scope the infrastructure scaffolding that the
> registrar-scraping pipeline will sit on, so Phase 1 (first
> live scraper) can drop into a working framework rather than
> standing it up alongside the first county's parser.
>
> **Status:** v2 — Codex-reviewed, infrastructure choices firmed
> up. Cloudflare R2 for object storage, GitHub Actions for
> scheduled runs, counties-only scope at first. Phase 0.5 stays
> thin: framework + one toy/no-op county adapter, not a large
> abstraction suite before any real scraping is done.
>
> **Codex review summary (2026-05-21):** architecture shape
> confirmed correct. One real correction (R2 prefix needs explicit
> snapshot/run id) plus four practical additions (run manifests,
> typed artifact metadata + errors, polite scraping defaults,
> Playwright rendered-content support). All applied below.

## What "the pipeline" actually is

```
┌─ Scrapers (per county) ────────────────┐
│ Fetch HTML/PDF/JSON from registrar     │
│ sites; emit raw artifacts + extraction │
│ metadata.                              │
└────────────────┬───────────────────────┘
                 │
                 ▼
┌─ Raw artifact store (Cloudflare R2) ───┐
│ s3://cal-vgp-registrar-raw/            │
│   {county}/{election_date}/            │
│     index.html                         │
│     measure_A.pdf                      │
│     manifest.json                      │
└────────────────┬───────────────────────┘
                 │
                 ▼
┌─ Parsers (per county) ─────────────────┐
│ Read artifacts, extract structured     │
│ measure records → emit normalized      │
│ JSONL (one row per measure).           │
└────────────────┬───────────────────────┘
                 │
                 ▼
┌─ Normalized intermediate ──────────────┐
│ scraper/data/registrar_normalized/     │
│   {county}_{election_date}.jsonl       │
│ Source of truth for "what did county   │
│ X publish for election Y?"             │
└────────────────┬───────────────────────┘
                 │
                 ▼
┌─ Loader / dedup ───────────────────────┐
│ Merge into ballot_measures.db via      │
│ fingerprint dedupe. Per-source         │
│ priority when conflicts arise (e.g.    │
│ official registrar over Ballotpedia).  │
└────────────────────────────────────────┘
```

Three reasons for the artifact → parser → DB separation (not
scraper-direct-to-DB):

1. **Audit trail.** When a county changes its HTML next March,
   we re-parse old snapshots after fixing the parser. Without the
   raw store we'd re-scrape under uncertainty.
2. **Coverage queries.** "What did LA publish for Nov 2026?" is
   a simple JSONL grep, not a join across the main DB.
3. **One loader, many scrapers.** Counties vary in scraping
   logic but output converges to one shape.

## R2 bucket layout

**Bucket:** `cal-vgp-registrar-raw` (single bucket; private; no
public object URLs)

**Prefix structure:** `raw/{env}/{county}/{election_date}/{snapshot_id}/...`

- `env`: `prod` for cron runs, `dev` for push-trigger / manual
  test runs (Codex round-1: keeps test snapshots from polluting
  the production tree)
- `snapshot_id`: timestamp-based, e.g. `2026-05-21T143211Z`. Makes
  re-scrapes first-class (Codex round-1 architectural correction
  — the previous design conflated "(county, election_date)" with
  "the canonical snapshot," which breaks on re-scrape).

```
cal-vgp-registrar-raw/
├── raw/prod/la_county/
│   ├── 2024-11-05/
│   │   ├── 2024-11-04T100000Z/         # election-night snapshot
│   │   │   ├── index.html
│   │   │   ├── measure_A_text.pdf
│   │   │   ├── rendered.html           # Playwright-rendered DOM
│   │   │   ├── screenshot.png          # rendered page screenshot
│   │   │   ├── results.json            # if API endpoint available
│   │   │   └── manifest.json
│   │   ├── 2024-11-10T090000Z/         # post-election results
│   │   │   ├── results.json
│   │   │   └── manifest.json
│   │   └── ...
│   └── 2026-06-02/
│       └── ...
├── raw/prod/san_diego_county/
│   └── ...
├── runs/prod/
│   ├── 2026-05-21T140000Z/             # cron run-level manifest
│   │   └── run_manifest.json
│   └── ...
└── raw/dev/                            # push-trigger test snapshots
    └── ...
```

**Snapshot `manifest.json`** (one per `{county}/{election}/{snapshot_id}/`):

```json
{
  "schema_version": 1,
  "county": "la_county",
  "election_date": "2024-11-05",
  "snapshot_id": "2024-11-04T100000Z",
  "run_id": "2024-11-04T095812Z",
  "scraped_at": "2024-11-04T10:00:00Z",
  "scraper_version": "0.1.0",
  "scraper_git_sha": "a1b2c3d",
  "fetch_mode": "playwright",
  "source_base_url": "https://lavote.gov/...",
  "artifacts": [
    {
      "filename": "index.html",
      "source_url": "https://lavote.gov/elections/2024/general",
      "final_url": "https://lavote.gov/elections/2024/general/",
      "http_status": 200,
      "content_type": "text/html; charset=utf-8",
      "etag": "\"abc-123\"",
      "last_modified": "2024-11-04T08:00:00Z",
      "fetched_at": "2024-11-04T10:00:00Z",
      "sha256": "abc123...",
      "size_bytes": 142839
    }
  ]
}
```

**Run-level `run_manifest.json`** (Codex round-1 addition; one per
cron/manual run, under `runs/{env}/{run_id}/`):

```json
{
  "schema_version": 1,
  "run_id": "2026-05-21T140000Z",
  "started_at": "2026-05-21T14:00:00Z",
  "finished_at": "2026-05-21T14:08:42Z",
  "runner_version": "0.1.0",
  "runner_git_sha": "a1b2c3d",
  "trigger": "schedule",
  "counties": [
    {
      "county": "la_county",
      "status": "success",
      "snapshot_id": "2026-05-21T140014Z",
      "elections_scraped": 1,
      "artifacts_written": 8,
      "duration_seconds": 47
    },
    {
      "county": "san_diego_county",
      "status": "failed",
      "error": "fetch_timeout",
      "duration_seconds": 60
    }
  ],
  "totals": {
    "counties_attempted": 2,
    "counties_succeeded": 1,
    "counties_failed": 1
  }
}
```

**Why this layout:**

- **Snapshot id makes re-scrapes first-class.** Re-scraping the
  same (county, election) creates a new snapshot, not a conflict
  with the previous one. Old snapshots stay intact for audit.
- **Run manifest answers "what happened in this cron run?"**
  without walking the bucket. Per-county status + counts +
  durations.
- **`env` prefix** isolates push-trigger test runs from production
  data.
- **Single bucket** — per-county buckets add admin friction
  without benefit at this scale (Codex round-1 confirmation).
- **`scraper_version` lives in the manifest, not the prefix** —
  version is metadata; snapshot identity is time/run based.

**Immutability:** snapshots are immutable within their
`{snapshot_id}` folder. Object versioning is not used; new
snapshots are cheap and explicit. Re-scrapes of the same election
land in a new dated folder.

**Retention (Codex round-1 addition):** keep all raw snapshots
indefinitely unless manually purged. R2 storage is cheap; the
audit value of historical snapshots is high. Phase 3+ may add a
"cold archive" policy for snapshots older than 5 years, but not
needed now.

**Privacy (Codex round-1 addition):** bucket is private, no
public object URLs, no raw artifact content in logs. Registrar
PDFs can carry candidate statements, signer addresses, precinct
detail — treat as potentially-sensitive even though source is
public records.

## Python `RawArtifactStore` interface

Codex round-1 expanded the protocol — structured `ArtifactRef`
return type (not bare URI string), typed errors, extra methods
for idempotency checks and per-snapshot listing.

```python
# scraper/src/scrapers/registrar/storage.py

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Protocol, Iterable


class ArtifactNotFound(Exception):
    """Raised by get / get_manifest when the requested object
    isn't in the store."""


class ArtifactIntegrityError(Exception):
    """Raised when a retrieved artifact's SHA256 doesn't match
    its manifest entry, or when a partial download is detected."""


@dataclass(frozen=True)
class ArtifactMetadata:
    """Caller-provided metadata for a put() call. Captured into
    the snapshot manifest."""
    source_url: str
    content_type: str
    http_status: int
    final_url: Optional[str] = None
    etag: Optional[str] = None
    last_modified: Optional[str] = None


@dataclass(frozen=True)
class ArtifactRef:
    """Returned by put / get-style operations. Structured so
    callers don't parse URI strings."""
    uri: str                      # s3://bucket/key or file:///path
    county: str
    election_date: str
    snapshot_id: str
    filename: str
    sha256: str
    size_bytes: int
    content_type: Optional[str] = None
    etag: Optional[str] = None


class RawArtifactStore(Protocol):
    """Abstract over R2 vs local-filesystem so dev runs don't need
    R2 credentials. CI / production uses R2; local dev defaults to
    filesystem under scraper/data/registrar_raw/."""

    def put(
        self,
        *,
        county: str,
        election_date: str,
        snapshot_id: str,
        filename: str,
        data: bytes,
        metadata: ArtifactMetadata,
    ) -> ArtifactRef:
        """Store an artifact + return its ref. SHA256 computed
        server-side. Raises on write failure; never writes a
        partial object as 'successful'."""

    def put_manifest(
        self,
        *,
        county: str,
        election_date: str,
        snapshot_id: str,
        manifest: dict,
    ) -> ArtifactRef:
        """Store the snapshot manifest.json. Convention: write
        ONLY after all artifacts have been verified — manifest's
        presence signals 'snapshot complete.'"""

    def put_run_manifest(
        self,
        *,
        env: str,
        run_id: str,
        manifest: dict,
    ) -> ArtifactRef:
        """Store the run-level manifest under
        runs/{env}/{run_id}/run_manifest.json."""

    def get(
        self,
        *,
        county: str,
        election_date: str,
        snapshot_id: str,
        filename: str,
        verify_sha256: Optional[str] = None,
    ) -> bytes:
        """Retrieve an artifact. If verify_sha256 given, raises
        ArtifactIntegrityError when checksums don't match.
        Raises ArtifactNotFound if the artifact doesn't exist."""

    def get_manifest(
        self,
        *,
        county: str,
        election_date: str,
        snapshot_id: str,
    ) -> dict:
        """Retrieve a snapshot's manifest.json. Raises
        ArtifactNotFound on missing snapshot."""

    def exists(
        self,
        *,
        county: str,
        election_date: str,
        snapshot_id: str,
        filename: str,
    ) -> bool:
        """Cheap HEAD check for idempotency.
        Returns False rather than raising on missing."""

    def list_snapshots(
        self,
        *,
        county: Optional[str] = None,
        election_date: Optional[str] = None,
    ) -> Iterable[tuple[str, str, str]]:
        """Yield (county, election_date, snapshot_id) tuples for
        re-processing. Filters narrow the scan."""

    def list_artifacts(
        self,
        *,
        county: str,
        election_date: str,
        snapshot_id: str,
    ) -> Iterable[str]:
        """Yield filenames in a snapshot."""


class R2ArtifactStore:
    """Cloudflare R2 implementation via boto3 (S3-compatible).
    Reads credentials from env vars:
        R2_ACCESS_KEY_ID
        R2_SECRET_ACCESS_KEY
        R2_ENDPOINT_URL    (https://<account>.r2.cloudflarestorage.com)
        R2_BUCKET          (default: cal-vgp-registrar-raw)
        R2_ENV             (default: 'prod'; CI sets to 'dev' on
                            push-trigger runs)
    """
    # ... implementation ...


class LocalArtifactStore:
    """Filesystem fallback for local dev. Writes under
    scraper/data/registrar_raw/. Same interface."""
    # ... implementation ...


def make_store() -> RawArtifactStore:
    """Pick R2 if credentials are present in env, else local fs."""
    if os.environ.get("R2_ACCESS_KEY_ID"):
        return R2ArtifactStore()
    return LocalArtifactStore()
```

**Why the interface abstraction:**
- Local dev runs don't need cloud credentials
- Unit tests use the local impl
- CI uses R2 via GH Actions secrets
- Future swap (S3, B2) just adds a new impl

**Error semantics (Codex round-1 addition):**
- `put` failures leave NO manifest entry — atomicity at the
  manifest level. Manifest is written last, after all artifacts
  pass integrity checks.
- `get` with `verify_sha256` is the standard idempotency check
  for re-parsing; integrity error halts processing rather than
  silently re-reading possibly-corrupted bytes.
- `exists` exists (heh) so scrapers can skip re-fetch when an
  artifact at a given URL hasn't changed (using ETag / Last-Modified
  hints) without paying for a full GET.

## GH Actions workflow

`.github/workflows/registrar_pipeline.yml`:

```yaml
name: registrar-pipeline

on:
  schedule:
    # GitHub cron is UTC and doesn't follow DST. '0 12 * * 1' is
    # Monday 4am PST / 5am PDT. Acceptable; documented here.
    - cron: '0 12 * * 1'
  workflow_dispatch:  # manual trigger; defaults to prod env
  push:
    paths:
      - 'scraper/src/scrapers/registrar/**'

# Codex round-1: concurrency group prevents runs that target the
# same R2 prefix from racing. Keyed on env (dev/prod), not event:
# - push (dev) and cron/manual (prod) can run concurrently because
#   they write to different R2 prefixes.
# - But two cron runs, two manual runs, or cron + manual all share
#   the prod prefix and must serialize.
# Self-audit fix to the earlier `github.event_name`-keyed version
# which incorrectly put cron and manual in separate groups even
# though they both target prod.
concurrency:
  group: registrar-pipeline-${{ github.event_name == 'push' && 'dev' || 'prod' }}
  cancel-in-progress: false

jobs:
  scrape:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'
      - name: Install deps
        run: pip install -r scraper/requirements.txt
      - name: Run scrapers
        env:
          R2_ACCESS_KEY_ID: ${{ secrets.R2_ACCESS_KEY_ID }}
          R2_SECRET_ACCESS_KEY: ${{ secrets.R2_SECRET_ACCESS_KEY }}
          R2_ENDPOINT_URL: ${{ secrets.R2_ENDPOINT_URL }}
          R2_BUCKET: cal-vgp-registrar-raw
          # Codex round-1: push-trigger runs write to dev prefix
          # so code-tweak test runs don't pollute production data.
          R2_ENV: ${{ github.event_name == 'push' && 'dev' || 'prod' }}
        run: |
          python scraper/scripts/run_registrar_pipeline.py \
            --counties=enabled \
            --upload-artifacts \
            --emit-normalized
      - name: Upload normalized JSONL as workflow artifact
        uses: actions/upload-artifact@v4
        with:
          name: registrar-normalized
          path: scraper/data/registrar_normalized/*.jsonl
          retention-days: 30
      - name: Upload run manifest as workflow artifact
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: run-manifest
          path: scraper/data/registrar_runs/*.json
          retention-days: 90
```

**Design notes:**

- **Single job, per-county concurrency in Python.** One workflow
  job iterates over counties using Python concurrency (e.g.
  `concurrent.futures`). Per-county failures are isolated: the
  runner catches each scraper's exception, records `status:
  failed` in the run manifest, and continues to the next county
  (no early exit). After all counties have been attempted, the
  process exits nonzero if **any** county failed (or the runner
  itself crashed). This gives CI visibility into partial failures
  — the run manifest carries per-county detail; CI red/green
  signals "something needs attention." Self-audit refinement of
  Codex round-1: earlier wording exited nonzero only when ALL
  failed (fail-open), which would hide a 4-of-5 partial outage.
- **Concurrency group** prevents cron + manual + push runs from
  racing. `cancel-in-progress: false` because we'd rather queue
  than abort a partially-complete scrape.
- **Push trigger writes to `dev` prefix** so code tweaks don't
  create noisy production snapshots. Production env only on
  scheduled cron + manual workflow_dispatch.
- **No DB writes in CI** in Phase 1. CI produces normalized JSONL
  + run manifest as workflow artifacts; DB loader runs locally.
  Phase 3+ may switch to "CI opens a PR with generated artifacts"
  rather than direct write-back to main.
- **Run manifest uploaded as `always()`** so failure runs still
  produce diagnostic info.
- **Failure handling minimal at first.** Phase 3 adds per-county
  "needs fixing" auto-issue creation and slack/email pings.
- **Cron schedule:** weekly Mondays during 2026 election cycles
  (Jun primary + Nov general). Reduce to monthly off-cycle.

## Secrets / credentials

Required GH Actions repo secrets:
- `R2_ACCESS_KEY_ID`
- `R2_SECRET_ACCESS_KEY`
- `R2_ENDPOINT_URL` (account-specific R2 endpoint)

Setup steps for Igor:
1. Create Cloudflare account (free tier covers our use)
2. Create an R2 bucket named `cal-vgp-registrar-raw`
3. Create an R2 API token with read+write to that bucket only
4. Copy access key + secret + endpoint URL into GH repo settings
   → Secrets → Actions

I'll write a `docs/setup/registrar_r2_setup.md` walking through
this when we're ready to wire it up.

## Python deps

New deps for `scraper/requirements.txt`:
- `boto3` — R2/S3 client (already widely used; ~3MB)
- `playwright` — for JS-heavy sites. Reconnaissance will tell us
  which top-5 counties need it. Playwright runs produce additional
  artifact types per snapshot: `rendered.html` (post-JS DOM) and
  `screenshot.png` (full-page screenshot). The artifact-store
  schema already supports these as just-more-filenames.

Should be able to stick to `requests + beautifulsoup4 + lxml`
(already in repo deps) for most counties. Playwright is the
fallback when reconnaissance shows a county can't be scraped
statically. Codex round-1 nudge: when Playwright IS used, record
the rendered DOM as a first-class artifact — raw HTTP HTML may be
useless for those pages.

## Polite scraping defaults (Codex round-1 addition)

Every county scraper inherits these defaults from
`CountyRegistrarScraper`:

- **User-Agent:** `cal-vgp-registrar-scraper/0.1 (+https://github.com/igorgeyn/cal_vgp; contact: igorgeyn@gmail.com)` — identifies us, links to the
  repo, gives a contact for site admins
- **Per-county rate limit:** default 1 request / 2 seconds. Tunable
  per-county if a registrar's robots.txt or terms request slower.
- **Timeout:** 30s default, configurable per scraper
- **Retry policy:** 3 attempts with exponential backoff for 5xx
  + connection errors; never retry 4xx (those are programmatic
  errors, not transient)
- **robots.txt stance:** check + respect on first request per
  domain. If `Disallow: /elections/` covers a path, log and skip
  rather than scrape. (California registrar sites publish public
  records, but respecting robots.txt is professional courtesy.)
- **No log dumps of raw HTML/PDF content.** Snapshots go to R2;
  logs get URLs + sizes + checksums + status codes only.

## What Phase 0.5 actually delivers

Codex round-1: **keep this thin** — framework + one no-op
adapter to prove the wiring, not a large abstraction suite
before any real scraper exists. The real shape gets validated
when Phase 1 implements LA + SD.

End of Phase 0.5:

- **Cloudflare R2 account + bucket + API token configured.**
  Walkthrough at `docs/setup/registrar_r2_setup.md`. Secrets
  added to GH repo settings.
- `scraper/src/scrapers/registrar/` package with:
  - `storage.py`: `RawArtifactStore` protocol + `ArtifactRef`
    + `ArtifactMetadata` + `ArtifactNotFound` /
    `ArtifactIntegrityError` exceptions + `R2ArtifactStore`
    + `LocalArtifactStore` + `make_store()` factory.
  - `base.py`: `CountyRegistrarScraper` abstract base class
    with built-in polite-scraping defaults (User-Agent, rate
    limit, retries, robots.txt check).
  - `noop.py`: one `NoOpCountyScraper` for "wire the workflow,
    prove the pipeline shape." Pretends to scrape a fake county,
    writes one HTML and one PDF artifact + a manifest, returns
    a success status. Used only by tests + the first CI run.
  - `__init__.py`
- `scraper/scripts/run_registrar_pipeline.py`: runner with
  `--counties` arg + run-manifest emission + per-county
  failure isolation.
- `.github/workflows/registrar_pipeline.yml`: GH Actions workflow
  with R2 secrets wired in, concurrency group set, env split
  between push (`dev`) and cron/manual (`prod`).
- `scraper/tests/test_registrar_storage.py`: unit tests against
  `LocalArtifactStore` covering put/get/manifest/integrity-error
  paths.
- `docs/setup/registrar_r2_setup.md`: walkthrough for Igor's R2
  account setup (linked above).
- `docs/plans/registrar_pipeline_infra.md`: this doc.

**Verification:** I can manually trigger the GH Actions workflow,
it runs the `NoOpCountyScraper` against the `dev` R2 prefix, R2
bucket gets the test artifacts, run manifest reports success,
JSONL workflow artifact is downloadable. End state: pipeline
shape proven, ready for Phase 1 to implement the first real
county scrapers.

That's the platform. Then Phase 1 implements LA + SD scrapers,
drops them into this framework, and we have real data flowing.

## Estimated time

- **Phase 0** (reconnaissance): 3-5 days, mostly research
- **Phase 0.5** (this infra): 1-2 days, mostly mechanical
- They can run in parallel — recon doesn't need infra, infra
  doesn't need recon results

## Open questions for Igor (Codex round-1 resolutions noted)

1. **Cloudflare account setup**: Codex says do it DURING Phase 0.5,
   not later — the first live scraper shouldn't also debug
   credentials. **Plan: bake account setup into Phase 0.5 as a
   prerequisite step.** If Igor doesn't have a Cloudflare account,
   creating one + the bucket + the API token is ~15 minutes.
2. **GH Actions cost**: this repo is public, so Actions minutes
   are free at the relevant scale. Playwright browser downloads
   add ~30s per run but still well within free tier. ✓
3. **DB write-back from CI in Phase 1**: stay JSONL-only.
   Revisit in Phase 3 once the loader and dedup behavior are
   boring. If we add CI write-back later, do it via PR (CI
   commits to a branch + opens a PR) rather than direct push to
   main. ✓
