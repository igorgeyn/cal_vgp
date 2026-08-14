# Codex request: registrar parser + loader (design AND implementation)

> **For Codex:** This is a build request, not a review. You are
> designing and implementing the stage that connects an existing
> raw-artifact archive to the live product database. Deliverables
> are a design doc, working code, tests, and a verification run —
> details in §9.
>
> **Fully self-contained.** Assume no context from prior sessions.
> Everything you need is below or in the files it names. Where this
> doc states an API signature or a fact about the data, it was
> verified against the repo on 2026-08-13, but **verify before
> relying on anything load-bearing** — the repo is the truth.

---

## 1. What you are building, in one paragraph

A weekly cron already scrapes San Bernardino County's registrar
website and stores raw HTML + PDFs in Cloudflare R2 as immutable,
checksummed snapshots. Nothing reads them. You are building the two
stages that turn that archive into rows in the product database:
a **parser** (stored snapshot → normalized JSONL records) and a
**loader** (JSONL → `ballot_measures.db`, with deduplication
against 12,365 existing measures). The immediate output is ~20 real
ballot measures for the November 2026 election appearing on a live
public website.

---

## 2. Project context

**CalBallot** (`https://calballot.com`) is a searchable database of
California ballot measures, 1911–present. Architecture: Python
pipeline → SQLite (`scraper/data/ballot_measures.db`) → static site
generator → GitHub Pages. Zero-cost deployment, no server.

Read `/CLAUDE.md` first — it is the rules-of-engagement file
(hard-won constraints, commit conventions, tooling notes). Then
`docs/WORKING_LIST.md` for current state.

**Current database inventory** (verified 2026-08-13):

| Fact | Value |
|---|---|
| Total measures | 12,365 |
| Existing data sources | `Ballotpedia`, `CA_SOS`, `CEDA`, `ICPSR`, `NCSL`, `UC_Law_SF` |
| Measures with no recorded outcome | 57 (0.5%) |
| Measures with `year >= 2026` | 22 |
| Rows where county matches San Bernardino | 344 |

The 344 SB rows and the 22 2026-era rows are the dedup surface you
must reason about. None came from a county registrar — this
pipeline introduces a new source.

---

## 3. Where the registrar pipeline stands

Package: `scraper/src/scrapers/registrar/`

| File | Role |
|---|---|
| `storage.py` | `RawArtifactStore` protocol + `LocalArtifactStore` + `R2ArtifactStore` + `make_store()` |
| `base.py` | `CountyRegistrarScraper` ABC: polite fetch, `SnapshotWriter` (manifest-last) |
| `sb.py` | San Bernardino scraper + **the pure extractor you will reuse** |
| `runner.py` | Per-county isolation, run manifests, exit codes |
| `noop.py` | Wiring-test scraper |

Design docs: `docs/plans/registrar_pipeline_infra.md` (architecture)
and `docs/plans/registrar_phase1_sb.md` (SB specifics, including a
failure-semantics table and the round-by-round review history).

The pipeline has been through six external review rounds
(`docs/codex/registrar_*.md`). It is live: weekly cron, 161 tests.

**Explicitly NOT built:** any parser, any loader, any consumer of
stored artifacts. `scraper/data/registrar_normalized/` does not
exist. No code outside `scrapers/registrar/` references the
pipeline. You are writing the first consumer.

---

## 4. The APIs you will build on

### 4.1 Artifact store (`scraper/src/scrapers/registrar/storage.py`)

```python
make_store(*, env: Optional[str] = None) -> RawArtifactStore
# env: "prod" | "dev"; selects R2ArtifactStore when all four
# R2_* env vars are set, else LocalArtifactStore. A prod run inside
# GitHub Actions with incomplete R2 config raises
# StoreConfigurationError rather than silently using local disk.

store.list_snapshots(*, county: str, election_date: str) -> list[str]
# Returns COMPLETE snapshots only (manifest present), ascending.
# Orphans from crashed runs are invisible here — by design.

store.get_manifest(*, county, election_date, snapshot_id) -> dict
store.list_artifacts(*, county, election_date, snapshot_id) -> list[ArtifactRef]
store.get_artifact(ref: ArtifactRef) -> bytes   # verifies sha256, raises on mismatch
store.exists(*, county, election_date, snapshot_id, filename=None) -> bool
```

`ArtifactRef` fields: `county, election_date, snapshot_id, filename,
sha256, size_bytes, content_type, storage_uri`.

**Snapshot manifest shape** (what `get_manifest` returns):

```json
{
  "schema_version": 1,
  "county": "sb",
  "election_date": "2026-11-03",
  "snapshot_id": "20260814T035115Z",
  "run_id": "...", "scraped_at": "...", "scraper_version": "0.1.0",
  "fetch_mode": "requests",
  "source_base_url": "https://elections.sbcounty.gov",
  "election_url": "https://elections.sbcounty.gov/elections/2026/1103/measures/",
  "discovery": {"index_url": "...", "provenance": "anchor_and_discovered"},
  "table_row_count": 20,
  "table_headers": ["letter", "jurisdiction", "..."],
  "pdf_counts": {"expected": 56, "saved": 56},
  "pdf_artifacts": [
    {"filename": "measure_l_analysis.pdf", "table_row": 14,
     "measure_letter": "L", "role": "analysis", "source_url": "https://..."}
  ],
  "artifacts": [
    {"filename": "page.html", "source_url": "...", "final_url": "...",
     "http_status": 200, "content_type": "text/html", "etag": null,
     "last_modified": null, "fetch_mode": "requests", "fetched_at": "...",
     "sha256": "...", "size_bytes": 183842}
  ]
}
```

### 4.2 The extractor you should reuse (`sb.py`)

**Do not write new HTML parsing.** This pure function is already
fixture-tested and hardened through two review rounds:

```python
extract_measures_page(body: bytes, page_url: str) -> MeasuresPage

@dataclass(frozen=True)
class MeasuresPage:
    headers: tuple[str, ...]
    rows: tuple[MeasureRow, ...]
    expected_documents: tuple[ExpectedDocument, ...]

@dataclass(frozen=True)
class MeasureRow:
    table_row: int          # 1-based index among data rows
    letter: str             # "L", or "TBD" before letters are assigned
    jurisdiction: str       # "City of Needles"
    description: str        # "Bond Measure" / "Transactions and Use Tax Measure"
    percentage_to_pass: str # "50% + 1", "66.67%"
    documents: tuple[ExpectedDocument, ...]

@dataclass(frozen=True)
class ExpectedDocument:
    filename: str      # snapshot-local storage key, e.g. "measure_l_analysis.pdf"
    url: str           # absolute HTTPS source URL
    role: str          # see below
    measure_letter: str
    table_row: int
```

**The eight document roles:** `resolution`, `text` (the full measure
text / ordinance), `analysis` (impartial analysis),
`tax_rate_statement`, `argument_for`, `rebuttal_for`,
`argument_against`, `rebuttal_against`.

Run the extractor over a stored `page.html`, not over the network.

### 4.3 Database (`scraper/src/database/`)

```python
from src.database.operations import Database
from src.database.models import BallotMeasure
from src.config import DB_PATH

db = Database(DB_PATH)           # note: expects a Path
db.insert_measure(m: BallotMeasure) -> int
db.find_by_fingerprint(fp: str) -> Optional[BallotMeasure]
db.find_by_content_hash(h: str) -> List[BallotMeasure]
db.update_measure(measure_id: int, updates: Dict) -> bool
db.get_statistics() -> Dict
db.backup(backup_path: Path = None) -> Path
```

`BallotMeasure` is a dataclass; fields relevant to you:

```
identity:    id, fingerprint, measure_fingerprint, content_hash
basics:      measure_id, measure_letter, year, state, county, jurisdiction
content:     title, description, ballot_question
results:     yes_votes, no_votes, total_votes, percent_yes, percent_no,
             passed, pass_fail, vote_threshold
class:       measure_type, topic_primary, topic_secondary,
             category_type, category_topic
source:      data_source, source_url, pdf_url
summary:     has_summary, summary_title, summary_text
meta:        election_type, election_type_imputed, election_date,
             decade, century
tracking:    created_at, updated_at, last_seen_at, update_count
dedup:       is_active, is_duplicate, duplicate_type, master_id, merged_from
```

### 4.4 ⚠️ The fingerprint trap — read this twice

`BallotMeasure.__post_init__` auto-generates fingerprints when none
are supplied:

```python
self.fingerprint         = f"{year}|{measure_id}|{county}|{data_source}"
self.measure_fingerprint = f"{year}|{measure_id}|{county}"
```

where `measure_id` comes from `extract_measure_identifier()`, which:
1. uses `self.measure_id` if set, else
2. **regex-guesses from `title`/`ballot_question`** (patterns for
   `Proposition N`, `ACA/SCA N`, `AB/SB N`, `Measure X`), else
3. falls back to `measure_letter`, else `"UNKNOWN"`.

If you let step 2 run on SB data, a measure whose description is
`"Bond Measure"` or `"Transactions and Use Tax Measure"` will
produce a garbage or colliding identifier — and identity collisions
are the single most expensive class of bug this project has hit
(the entire finance v1→v2 rebuild happened because a keying scheme
let different election cycles contaminate each other; see
`docs/LESSONS_LEARNED.md`). **Set `measure_id` explicitly and
deliberately. Decide its exact format in the design doc and defend
it.** Note that letters repeat across elections and jurisdictions
(three separate "City of Needles" measures exist in one election;
letters A–R, Y, Z all appear on the November 2026 page), so
`year|LETTER|county` alone is NOT unique.

---

## 5. What is actually in the store right now

Bucket `cal-vgp-registrar-raw`, prefix `prod/`. County slug `sb`.

| Election | Snapshot | Rows | PDFs | Notes |
|---|---|---|---|---|
| 2026-11-03 | `20260727T171800Z` | 8 | 16 | letters all "TBD" |
| 2026-11-03 | `20260803T144106Z` | 9 | 18 | letters all "TBD" |
| 2026-11-03 | `20260814T035115Z` | 20 | 56 | **letters assigned A–R, Y, Z** |

Three snapshots of the *same* election, showing the county
progressively publishing. This is deliberate: snapshots are
independent observations, never overwritten.

**This raises your first real design question: snapshot selection.**
Which snapshot represents "what SB published for November 2026"?
Latest complete? Do you re-parse all of them? What happens next
Monday when a fourth appears with more arguments filed? Your answer
must make re-running the parser and loader **idempotent** — running
twice must not create duplicate rows or churn `update_count`.

Also note: `measure_letter` changed from `"TBD"` to real letters
between snapshots, and snapshot-local PDF filenames changed with it
(`measure_tbd_r014_analysis.pdf` → `measure_l_analysis.pdf`).
Filenames are snapshot-local storage keys, NOT stable identifiers.
`source_url` is a continuity hint; `sha256` identifies exact bytes.
Cross-snapshot lineage is explicitly the parser's problem to solve —
that was the conclusion of an earlier review round.

---

## 6. Binding constraints

1. **Raw artifacts are immutable and authoritative.** The parser
   reads from the store; it never re-fetches from the county site.
   A parse is reproducible from stored bytes forever.
2. **Reuse `extract_measures_page`.** If it needs a change to serve
   the parser, say so explicitly and justify it — do not fork it.
3. **The loader writes to the live product database.** Back it up
   before writing (`db.backup()`), and make the write reviewable and
   reversible. Prefer a `--dry-run` default or an explicit
   `--commit` flag; a script that silently mutates 12,365-row
   production data on invocation is not acceptable.
4. **Never `git add .`** — the repo has many gitignored data
   artifacts. Name files explicitly.
5. **`pytest` runs from `scraper/`**; imports use `from src.xxx`.
6. **Windows + PowerShell** is the primary environment; Bash is
   available. Write cross-platform code (`pathlib`, no shell-isms).
7. **Do not touch the finance subsystem**, the site generator's
   existing behavior, or the scraper's live cron path.

---

## 7. Decisions the design doc must make

### 7.1 Field mapping
For each `BallotMeasure` field, state where the value comes from or
why it stays null. At minimum resolve:
- `title` vs `description` vs `ballot_question` — SB gives a short
  type label ("Bond Measure") and a jurisdiction; neither is a
  natural title. What makes a good card headline?
- `county` — the exact string convention. Existing rows use some
  form of San Bernardino; **verify against the DB** rather than
  guessing, or the new rows will not group with the existing 344.
- `jurisdiction` — SB supplies "City of Needles", "Upland Unified
  School District". How does this relate to existing conventions?
- `vote_threshold` — SB gives `"50% + 1"`, `"66.67%"`. The DB
  convention appears to be `"50%"`, `"55%"`, `"66.67%"`. Normalize,
  and note `docs/KNOWN_ISSUES.md` #1 on threshold data quality.
- `measure_type`, `election_type`, `year`, `election_date`,
  `data_source`, `source_url`, `pdf_url`, `passed`/`pass_fail`.
- Results fields: this election has not happened. Be explicit.

### 7.2 Identity and dedup
- The exact `measure_id` format and why it is collision-safe across
  jurisdictions, letters, elections, and counties.
- Dedup strategy against the existing 344 SB rows and 22 2026 rows.
  Verify empirically whether any existing row refers to the same
  real-world measure as a November 2026 SB local measure. If yes,
  what wins? (Registrar is the official primary source; other
  sources are aggregators.)
- Re-run behavior: same snapshot twice, and a NEW snapshot of the
  same election with more documents. Which fields update, which are
  immutable, and how `update_count` / `last_seen_at` behave.

### 7.3 Pending-measure semantics
These measures have no outcome. `context/vgp-pending-measures-prompt.md`
is an existing spec for improving pending-measure UX — **read it for
intent, but note it assumes a React stack this project does not use
(the site is a Python static generator, `src/website/generator.py`)
and its stated measure counts are stale.** Decide minimally: what
does a pending registrar measure look like in the DB such that the
existing generator renders it sensibly rather than as a broken
historical record? Confirm by inspecting how the 57 existing
no-outcome measures are handled.

---

## 8. Explicitly out of scope

- **PDF text extraction.** The full measure text lives in the
  `text`-role PDFs. Extracting it is a separate project (new
  dependency, layout-dependent quality). Store the URLs; do not
  parse PDF contents. If you believe a minimal version is trivially
  safe, argue it in the design doc and implement it only if
  approved — do not assume.
- LLM summarization, topic classification, other counties, historical
  backfill, CI integration of the loader, site-generator redesign.

---

## 9. Deliverables

1. **`docs/plans/registrar_parser_loader.md`** — the design doc:
   every decision from §7 with rationale, the snapshot-selection and
   idempotency model, a failure-semantics table (missing snapshot,
   integrity error, unparseable page, dedup conflict, partial load),
   and open questions for Igor kept short and genuinely his call.
2. **Parser** — likely `scraper/src/scrapers/registrar/parser.py`
   plus a CLI entry point matching existing conventions (see
   `scraper/scripts/run_registrar_pipeline.py` — thin shim over an
   importable, testable module). Output: normalized JSONL at
   `scraper/data/registrar_normalized/{county}_{election_date}.jsonl`
   (gitignored). One JSON object per measure; document the record
   schema in the design doc.
3. **Loader** — JSONL → `ballot_measures.db` with dedup, dry-run
   default, backup-before-write, and a clear summary report
   (inserted / updated / skipped / conflicts).
4. **Tests** — `scraper/tests/test_registrar_parser.py` (+ loader
   tests). Use the pinned fixtures in
   `scraper/tests/fixtures/registrar/sb/` (notably
   `measures_2026_1103_lettered.html`, the 20-row page with both
   analysis types) and a temp SQLite DB. No test may touch the live
   database or the network. The existing 161 registrar tests must
   still pass.
5. **A verification run** — parse the real stored snapshot, load
   into a COPY of the database, and report: rows inserted, a sample
   record rendered field-by-field, dedup outcomes, and idempotency
   proof (second run changes nothing). Do not write to the live DB
   without Igor's explicit approval.

---

## 10. Calibration

Design first, then implement — but this is one task, and the design
doc should be a real artifact, not a preamble. Be opinionated: give
one recommended answer per decision rather than an option menu, and
say plainly when you are guessing versus when you verified against
the repo.

Prior rounds on this pipeline caught: a fallback that would have
silently written to ephemeral storage, a nested-`<th>` case that
would have published silently empty snapshots, and a
cardinality rule that turned out to prevent silent document
misattribution. The bar is that class of thinking — the failure
modes that report success. Identity/dedup is where that risk lives
in this stage.

State clearly at the end: what you verified, what you assumed, what
you deliberately deferred, and what needs Igor's decision.
