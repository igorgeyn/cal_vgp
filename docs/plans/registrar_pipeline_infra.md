# Local-measure pipeline: Phase 0.5 infrastructure sketch

> **Purpose:** scope the infrastructure scaffolding that the
> registrar-scraping pipeline will sit on, so Phase 1 (first
> live scraper) can drop into a working framework rather than
> standing it up alongside the first county's parser.
>
> **Status:** draft for Igor's signoff. Infrastructure choices
> already made: Cloudflare R2 for object storage, GitHub Actions
> for scheduled runs, counties-only scope at first.

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

**Bucket:** `cal-vgp-registrar-raw` (single bucket; per-county
prefix separation)

```
cal-vgp-registrar-raw/
├── la_county/
│   ├── 2024-11-05/
│   │   ├── index.html                  # main elections page
│   │   ├── measure_A_text.pdf          # ballot language PDFs
│   │   ├── measure_B_text.pdf
│   │   ├── results.json                # if API endpoint available
│   │   └── manifest.json               # what we fetched + when + sha256
│   ├── 2026-06-02/
│   │   └── ...
│   └── ...
├── san_diego_county/
│   └── ...
└── ...
```

`manifest.json` per (county, election_date) snapshot:

```json
{
  "county": "la_county",
  "election_date": "2024-11-05",
  "scraper_version": "0.1.0",
  "scraped_at": "2026-05-21T14:32:11Z",
  "source_base_url": "https://lavote.gov/...",
  "artifacts": [
    {
      "filename": "index.html",
      "source_url": "https://lavote.gov/elections/...",
      "fetched_at": "2026-05-21T14:32:11Z",
      "sha256": "abc123...",
      "size_bytes": 142839
    },
    ...
  ]
}
```

**Why this layout:**
- One folder per (county, election) means re-scraping is
  isolated; we don't blow away historical snapshots
- Manifest gives parsers what they need without reading bytes
- SHA256 in manifest lets us detect when a re-scrape produced
  the same artifact (skip re-parsing)

**Versioning vs immutability:** we'll treat artifacts as
**immutable** within a (county, election_date) folder. If a
county updates ballot language between draft and final, the
scraper produces a new dated snapshot folder (e.g.
`2024-11-05_2024-09-15/` if needed). Avoids "did this artifact
change?" ambiguity at parse time.

## Python `RawArtifactStore` interface

```python
# scraper/src/scrapers/registrar/storage.py

from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Optional, Protocol

class RawArtifactStore(Protocol):
    """Abstract over R2 vs local-filesystem so dev runs don't need
    R2 credentials. CI / production uses R2; local dev defaults to
    filesystem under scraper/data/registrar_raw/."""

    def put(
        self,
        *,
        county: str,
        election_date: str,
        filename: str,
        data: bytes,
        source_url: str,
    ) -> str:
        """Store an artifact. Returns the URI (s3:// or file://)."""

    def put_manifest(
        self,
        *,
        county: str,
        election_date: str,
        manifest: dict,
    ) -> str:
        """Store the manifest.json for a snapshot."""

    def get(
        self,
        *,
        county: str,
        election_date: str,
        filename: str,
    ) -> bytes:
        """Retrieve an artifact."""

    def list_snapshots(
        self,
        *,
        county: Optional[str] = None,
    ) -> list[tuple[str, str]]:
        """Return [(county, election_date), ...] for re-processing."""


class R2ArtifactStore:
    """Cloudflare R2 implementation via boto3 (S3-compatible).
    Reads credentials from env vars:
        R2_ACCESS_KEY_ID
        R2_SECRET_ACCESS_KEY
        R2_ENDPOINT_URL    (https://<account>.r2.cloudflarestorage.com)
        R2_BUCKET          (default: cal-vgp-registrar-raw)
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

## GH Actions workflow

`.github/workflows/registrar_pipeline.yml`:

```yaml
name: registrar-pipeline

on:
  schedule:
    # Every Monday 4am PT during 2026 election cycles
    - cron: '0 12 * * 1'
  workflow_dispatch:  # manual trigger
  push:
    paths:
      - 'scraper/src/scrapers/registrar/**'
      # rerun if scraper code changes (catches breakage early)

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
      - name: Report failures
        if: failure()
        run: |
          # Post a summary to job output; future: open an issue
          echo "registrar pipeline failed; check logs"
```

**Design notes:**
- **Single workflow, parallel within** — one job that iterates
  counties. Per-county parallelism via Python concurrency, not
  matrix jobs (keeps secret/state management simple).
- **No DB writes in CI.** CI produces normalized JSONL artifacts.
  Loading into `ballot_measures.db` happens locally where the DB
  lives. Avoids merging a write-back commit on every cron run.
  (Reconsider in Phase 3 when we want continuous deployment.)
- **Manual dispatch** for ad-hoc runs.
- **Push trigger on scraper code changes** catches "we broke the
  scraper" quickly.
- **Failure handling minimal at first.** Phase 3 will add
  per-county "needs fixing" tracking + auto-issue creation.

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
- `playwright` — for JS-heavy sites (LA's voter page uses Vue or
  similar). Heavier dep (~50MB browser), but reconnaissance will
  tell us if we need it for the top-5

Should be able to stick to `requests + beautifulsoup4 + lxml`
(already in repo deps) for most counties. Playwright is the
fallback when reconnaissance shows a county can't be scraped
statically.

## What Phase 0.5 actually delivers

End of Phase 0.5, before any scraper code:

- `scraper/src/scrapers/registrar/` package with:
  - `storage.py`: `RawArtifactStore` interface + R2 impl + local
    fs impl
  - `base.py`: `CountyRegistrarScraper` abstract base class
  - `__init__.py`
- `scraper/scripts/run_registrar_pipeline.py`: skeleton runner
  with `--counties` arg, currently a no-op (no scrapers yet)
- `.github/workflows/registrar_pipeline.yml`: GH Actions workflow
  with R2 secrets wired in, currently runs the no-op runner
  successfully
- `docs/setup/registrar_r2_setup.md`: walkthrough for Igor's R2
  account setup
- `docs/plans/registrar_pipeline_infra.md`: this doc, committed
  as the reference

**Verification:** I can manually trigger the GH Actions workflow,
it completes successfully, R2 bucket gets a test artifact, and
the runner reports `0 scrapers enabled, 0 counties processed`.

That's the platform. Then Phase 1 implements the first
scraper(s), drops them into this framework, and we have data
flowing.

## Estimated time

- **Phase 0** (reconnaissance): 3-5 days, mostly research
- **Phase 0.5** (this infra): 1-2 days, mostly mechanical
- They can run in parallel — recon doesn't need infra, infra
  doesn't need recon results

## Open questions for Igor

1. **Cloudflare account setup**: do you have one? Want me to walk
   you through bucket creation when Phase 0.5 code lands, or are
   you set up already?
2. **GH Actions cost**: this repo's public, so Actions minutes are
   free. Confirmed?
3. **DB write-back from CI in Phase 1**: my Phase 0.5 design has
   CI producing JSONL only; local runs the loader. OK for first
   pass, or do you want CI to push DB updates too (more complex
   but more "automatic")?
