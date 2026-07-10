# Phase 1: San Bernardino registrar scraper design

> **Status:** proposed implementation design
>
> **Scope:** the first live county adapter for the registrar pipeline:
> `SbScraper(CountyRegistrarScraper)`, which captures San Bernardino
> County's measures pages and linked official PDFs as immutable raw
> artifacts. This document is intentionally an implementation design,
> not the later parser/loader design.

## 1. Scope and boundaries

Phase 1 adds `scraper/src/scrapers/registrar/sb.py` with an
`SbScraper` whose county slug is `sb` and whose fetch mode is
`requests`. It will:

- discover the currently relevant San Bernardino election measures
  pages;
- capture each selected measures page as `page.html`;
- capture every advertised impartial-analysis and argument PDF from
  that page;
- write one completed immutable snapshot per `(sb, election_date)` in
  a run; and
- report the resulting `ScrapeResult` through the existing runner.

It does **not** parse records into normalized JSONL, infer measure
fields, deduplicate records, write the ballot-measures database, or
backfill the County's historical archive. The downstream parser will
read the saved `page.html`, PDFs, and manifest later. The initial live
scope is forward-looking elections only; historical backfill is a
separate manual, date-bounded operation after this scraper is stable.

The canonical SB origin is `https://elections.sbcounty.gov`. Recon
confirmed the direct page pattern:

```
https://elections.sbcounty.gov/elections/{year}/{mmdd}/measures/
```

For example, `2026-03-24` maps to
`/elections/2026/0324/measures/`. The cross-election landing is
`/elections/measures/`.

**Fixture-pinning assumption:** the landing page exposes links to the
canonical per-election measures pages. Recon established the landing
page and direct-page patterns, but not the exact landing-page markup.
The first fixture task must confirm this before implementation begins.
If the landing page is not the election index, this design pauses for a
new recon probe rather than guessing a second discovery endpoint.

The existing base class provides every primitive this design needs:
`fetch()` supplies polite requests, robots checks, retry/backoff, and
per-hop redirect handling; `open_snapshot()` and `SnapshotWriter`
provide manifest-last snapshot publication. No base-class change is
needed for Phase 1.

## 2. Election enumeration

### Static coverage contract

The static anchor list lives in `sb.py`, beside the URL-composition
logic that consumes it. It is a small versioned tuple of date-only
anchors, not a separate runtime configuration file. The list is code
because it is a reviewed coverage contract and has no user-specific or
operational configuration value.

Illustrative shape:

```text
SB_FORWARD_ANCHORS = (
  "YYYY-MM-DD",
  ...,
)
```

Each date is validated as an ISO calendar date and converted only by
the scraper's URL builder:

```text
election_date YYYY-MM-DD -> /elections/YYYY/MMDD/measures/
```

The initial list is a fixture-pinning and rollout gate: add every
current/upcoming election date verified on the live index at that
time. Do not invent dates from a recurrence rule. The recon-verified
2026-03-24 page is a required test fixture, but it is not by itself a
reason to begin a broad historical production scrape.

### Weekly discovery and reconciliation

Every run first fetches the cross-election landing URL
`/elections/measures/` and extracts links whose resolved URL has the
canonical shape:

```text
https://elections.sbcounty.gov/elections/YYYY/MMDD/measures/
```

Discovery accepts a link only when all of the following hold:

1. resolving the link against the landing page produces the canonical
   SB HTTPS origin and exact path shape above;
2. `YYYY` and `MMDD` form a valid ISO calendar date;
3. the date is in the forward collection window selected for this
   initial release; and
4. fetching the candidate page succeeds and the page passes the
   measures-table contract in section 3.

The candidate page fetch used for validation is retained and becomes
that election's `page.html` artifact; it is never fetched a second
time merely because it was discovered.

The discovered-date set must be nonempty and must contain every static
anchor. Either an empty set or a missing anchor is an SB county
failure. This deliberately makes a changed index page visible rather
than silently accepting an incomplete weekly run. Valid discovered
dates are unioned with anchors, deduplicated by ISO date, and processed
in ascending date order. A date discovered and anchored receives
provenance `"anchor_and_discovered"`; otherwise its provenance is
`"discovered"`.

The first live fixture establishes the forward-window rule precisely.
**Fixture-pinning task:** document whether the index exposes only
current/upcoming elections or a longer archive, then encode a
date-based cutoff that excludes unrequested historical backfill while
retaining upcoming elections. The rule must be deterministic for a
given run date and covered by an injected-clock test.

## 3. Per-election scrape flow

The scraper processes each reconciled election independently. A
failure for one election makes the county run fail, but completed
snapshots for earlier elections remain valid immutable observations;
the runner records one failed `sb` county result and retries the whole
selection next week.

1. Construct the canonical direct measures URL from the ISO election
   date. For a discovery candidate, retain its fetched result only if
   its final URL remains the canonical SB page or an expected official
   redirect target established by fixtures.
2. Fetch the page through `CountyRegistrarScraper.fetch()`. This uses
   the project User-Agent, robots policy, retry behavior, and rate
   limiting. The scraper does not use `requests` directly.
3. Open a snapshot and save that fetched response as `page.html`.
   Saving the page before structural validation preserves a useful
   orphan diagnostic if the county changes its HTML; without a final
   manifest it is not a published snapshot.
4. Pass the original response bytes and final page URL to the pure
   SB-table extractor. It locates the one table whose full normalized
   header set is:

   ```text
   Letter | Jurisdiction | Measure Description | Analysis |
   Arguments | Percentage to Pass
   ```

   Header matching normalizes case and whitespace only; it maps columns
   by header name, never by position. Zero data rows are valid once the
   full header contract is present. No matching table, more than one
   matching table, malformed rows, or unrecognized nonblank PDF-link
   labels are schema failures.

   **Fixture-pinning task:** confirm the precise visible header strings
   and the link labels used for the four argument variants. The strings
   above are recon-based assumptions, not a license to make matching
   fuzzy.
5. Convert each nonblank PDF link into an expected document. Resolve
   it against the final measures-page URL. Accept HTTPS only; a
   cross-origin HTTPS URL is allowed only because it appears in the
   fetched official SB table, and its source and final URLs are retained
   by the normal artifact metadata. Reject `javascript:`, `data:`,
   `mailto:`, empty, and malformed URLs before fetching.
6. Derive the deterministic filename described in section 4. Fetch
   each expected PDF through `fetch()`, validate it as a PDF, then save
   it through the same `SnapshotWriter`. A PDF is acceptable when its
   normalized response content type is `application/pdf` **or** its
   bytes begin with `%PDF-`; this permits honest but generic MIME types
   while rejecting a normal HTML error page returned with status 200.
7. When—and only when—all expected documents have been saved, finalize
   the writer with the SB audit extras in section 5. Manifest presence
   publishes the snapshot. The scraper returns the writer summary.

There is intentionally no ETag/Last-Modified skip path. Every weekly
run creates a new snapshot even when all bytes are unchanged. The
artifact manifests already preserve checksums and HTTP validators, so
later tooling can compare observations without weakening the audit
timeline.

## 4. Filename derivation

All filenames are semantic storage keys, never remote URL basenames or
display-link text. The fixed names are:

- measures page: `page.html`
- analysis: `measure_{letter}_analysis.pdf`
- argument for: `measure_{letter}_argument_for.pdf`
- rebuttal to argument for: `measure_{letter}_rebuttal_for.pdf`
- argument against: `measure_{letter}_argument_against.pdf`
- rebuttal to argument against: `measure_{letter}_rebuttal_against.pdf`

`letter` is a lowercase ASCII slug made from the table's Letter cell:
trim, lowercase, retain alphanumeric runs, and join runs with `_`.
An empty resulting slug is a schema failure.

Normally a letter appears once, so Measure V's impartial analysis is
`measure_v_analysis.pdf`. If two or more rows normalize to the same
letter slug, every file for those colliding rows includes its stable
one-based table-data-row suffix:

```text
measure_v_r002_analysis.pdf
measure_v_r004_analysis.pdf
```

The suffix is based on the row's position among data rows, not a URL or
link label. This guarantees unique names even when the County reuses a
letter in a combined page. The scraper computes the entire expected
artifact plan before saving any PDF and rejects any remaining duplicate
filename as an internal schema error.

The scheme contains only lowercase letters, digits, `_`, `-`, and `.`.
It therefore satisfies the artifact store's single-safe-component
validator: no slash, backslash, colon, whitespace padding, `..`,
Windows device name, or reserved `manifest.json` is possible.

## 5. Snapshot manifest extras

The standard `SnapshotWriter` manifest continues to hold the complete
artifact list, source/final URLs, HTTP statuses, content types,
checksums, sizes, fetch modes, and fetch times. SB adds these
non-core top-level fields at finalization:

```json
{
  "source_base_url": "https://elections.sbcounty.gov",
  "election_url": "https://elections.sbcounty.gov/elections/2026/0324/measures/",
  "discovery": {
    "index_url": "https://elections.sbcounty.gov/elections/measures/",
    "provenance": "anchor_and_discovered"
  },
  "table_row_count": 2,
  "table_headers": [
    "letter",
    "jurisdiction",
    "measure description",
    "analysis",
    "arguments",
    "percentage to pass"
  ],
  "pdf_counts": {"expected": 10, "saved": 10},
  "pdf_artifacts": [
    {
      "filename": "measure_v_analysis.pdf",
      "table_row": 1,
      "measure_letter": "V",
      "role": "analysis",
      "source_url": "https://..."
    }
  ]
}
```

`pdf_artifacts` is deliberately an audit map, not normalized ballot
data. It lets the later parser associate a semantic filename with the
row and link that produced it without treating this scraper as the
parser. `saved` equals `expected` in every completed manifest by
construction. Failure paths produce no completed manifest and hence no
misleading partial count.

## 6. Failure semantics

Publication is atomic per election snapshot, not across every election
in an SB county run. Any county failure makes the runner exit nonzero;
already-finalized snapshots from earlier elections remain available.

| Failure class | Snapshot action | Run-manifest result | Next weekly run |
| --- | --- | --- | --- |
| Landing/index request timeout, connection failure, retry exhaustion, or HTTP 4xx/5xx | No SB election snapshot is opened for candidates not reached. | `sb` is `failed` with the typed fetch error. | Fetch the index again; no manual intervention is assumed. |
| Index parses to no canonical candidates, or omits a static anchor | No completed snapshot. | `sb` is `failed` with an enumeration-contract error naming the missing anchor/count. | Retry, but treat a repeat as site drift requiring fixture/recon work. |
| Candidate measures page returns 404 or another terminal fetch error | No manifest for that election; earlier completed elections remain complete. | `sb` is `failed`, including election date and fetch status. | Retry the page next week; do not reinterpret this as a zero-measure election. |
| Measures page is HTTP 200 and has the full expected headers but zero data rows | Save `page.html`, save no PDFs, finalize a zero-measure snapshot with counts `0/0`. | Election contributes a successful snapshot; county may still fail only for another election. | Capture another observation next week because the page may be populated later. |
| Table headers changed, table is ambiguous, a row is malformed, or a nonblank link has an unknown role | `page.html` remains an orphan diagnostic; no manifest is written. | `sb` is `failed` with a schema-contract error. | Retry; after repeat, pin the new fixture and deliberately revise the extractor. |
| Expected PDF fetch is 404, terminally fails, or is robots-disallowed | Page and any already saved PDFs remain orphaned; no manifest. | `sb` is `failed` with election date, role, and source URL/status. | Retry all selected elections next week. |
| Expected PDF returns 200 but fails both PDF checks | Do not save that response under a semantic PDF name; no manifest. | `sb` is `failed` with role, URL, and observed content type. | Retry; a repeat requires fixture inspection rather than accepting HTML as a PDF. |
| Artifact write, manifest create, or storage configuration error | No completed manifest for the affected election (or manifest create reports its collision). | `sb` is `failed`; the runner still writes its local run manifest if possible. | Retry with storage/configuration corrected; never overwrite a completed snapshot. |
| Robots disallows the index or measures page | No completed snapshot for the blocked work. | `sb` is `failed` with `RobotsDisallowedError`. | Retry only after the published policy changes or collection scope is reconsidered. |

## 7. Fixtures and test plan

Fixtures precede scraper code. Store them under a focused test-fixture
directory such as `scraper/tests/fixtures/registrar/sb/`, with raw
response bytes preserved unchanged and small sidecar metadata files for
source URL, final URL, status, and headers.

Required pinned live fixtures:

1. the cross-election landing page used for discovery;
2. the recon-confirmed 2026-03-24 measures page, including its full
   header row and both known measure rows;
3. one impartial-analysis PDF; and
4. one example of each nonblank argument-link role present on that
   page, or a documented fixture task for any role not present.

The fixture capture must record the exact table headers, canonical and
final URLs, relative-versus-absolute link forms, actual response
content types, and whether any PDF link is off-origin. Those facts are
currently recon assumptions and must become explicit fixture facts.

The pure extraction boundary takes raw page bytes plus the final page
URL and returns a page contract: normalized header mapping, ordered
rows, and resolved expected-document descriptors. It performs no
network, storage, clock, or runner work. Its contract is:

- one and only one full-header table is accepted;
- column order is irrelevant;
- valid zero-row tables are returned as zero rows;
- nonblank document links have one recognized semantic role; and
- every returned descriptor has a resolved HTTPS URL and a deterministic
  safe filename.

Test coverage must include:

- static-anchor URL construction, discovery reconciliation, no
  discovery candidates, and a missing known anchor;
- the pinned landing and measures fixtures, including byte-preserving
  encoding behavior;
- headers reordered, changed, duplicated, absent, and two matching
  tables;
- relative and absolute links, a permitted linked off-origin HTTPS
  PDF, and rejected non-HTTP(S) links;
- duplicate letters and filename collision suffixes;
- each argument-role label, blank cells, unknown nonblank labels, and
  a table with zero measures;
- correct-PDF MIME, `%PDF-` fallback, HTML masquerading as a PDF, and
  malformed/truncated PDF bytes;
- measures-page 404 versus a valid late-populated zero-row page;
- a missing expected PDF after earlier PDFs have been saved, asserting
  no manifest exists; and
- an end-to-end fixture-session test using `LocalArtifactStore`,
  asserting `page.html`, every expected semantic filename, the audit
  extras, and a `ScrapeResult` count.

All unit and integration tests use injected sessions, clocks, sleeps,
and local storage. No test depends on a live SB site.

## 8. Rollout checklist

1. Capture and commit the required fixtures and their sidecar metadata.
   Confirm the landing-page discovery assumption, exact headers, link
   labels, and initial forward anchor dates.
2. Add the pure discovery and table-extraction tests. Implement the
   pure functions only after those fixtures define their contract.
3. Implement `SbScraper` using only `fetch()`, `open_snapshot()`, and
   `SnapshotWriter`; add its fixture-session integration tests.
4. Register `"sb"` in `runner.REGISTRY` and add `"sb"` to
   `ENABLED_COUNTIES`. Keep `noop` explicit-only.
5. Update `.github/workflows/registrar_pipeline.yml` from
   `--counties=noop` to `--counties=enabled`. Run the registrar test
   suite and a local explicit `--counties=sb --env=dev` fixture smoke
   before merging.
6. Merge only after the production R2 configuration is confirmed. The
   production workflow's existing guard must select R2, never local
   fallback.
7. Trigger the first production run manually and verify:

   - the GitHub Actions job is green and reports `1/1 counties
     succeeded`;
   - the local workflow-artifact run manifest says
     `env: prod`, `store_backend: r2`, and one successful `sb` report;
   - R2 contains `prod/sb/{election_date}/{snapshot_id}/page.html`,
     its semantic PDFs, and `manifest.json` for every selected
     election;
   - every completed manifest has matching expected/saved PDF counts,
     valid source/final URLs, SHA-256 values, and the SB audit extras;
   - R2 contains `runs/prod/{run_id}/run_manifest.json` with the same
     run identifier; and
   - a sampled artifact can be read through the store with checksum
     verification, while push-trigger data remains under `dev/`.

8. Watch the next scheduled run. Any SB failure is operationally
   meaningful; do not weaken the county-failure policy to keep cron
   green. Schedule historical collection only as a separately reviewed
   bounded backfill after two clean forward runs.

## 9. Open questions for Igor

1. After fixture capture, approve the exact initial forward anchor list
   and forward-window cutoff for the first production release. This is
   the only coverage-policy value not knowable from the present recon.
2. Confirm whether the first manual production run should collect only
   the approved forward anchors or also the recon page as a one-time
   diagnostic snapshot. The design recommends anchors only; the
   recon page remains the pinned test fixture unless explicitly
   approved as a bounded backfill.

---

## Red-team review note (2026-07-09, Claude)

Verified against the as-built base class and storage layer: all
primitives are used as they actually exist; manifest extras don't
collide with protected core fields; the filename scheme passes the
storage validator in all cases including collision suffixes and
Windows reserved-name edges. No blockers. Three watch-items for the
fixture phase:

1. **Future-election 404s.** Discovery criterion 4 (candidate page
   must fetch and validate) + failure-table row 3 (candidate 404 =
   county failure) means an SB index that links elections before
   publishing their pages would turn weekly cron red through no code
   fault. Fixture capture must determine whether SB does this; if
   yes, refine to "linked-but-unpublished, election date > run date
   = pending, not failure."
2. **Orphan accumulation.** A persistent schema failure leaves one
   orphan `page.html` per weekly run (invisible to parsers, by
   design). Acceptable; just expected noise when browsing the bucket
   during an extractor-drift incident.
3. Rollout step 5's local `--counties=sb --env=dev` check is a live
   smoke against the county site, not a fixture run — fine, just
   naming.

---

## Fixture findings (2026-07-09) — design refinements

Rollout step 1 executed same day; fixtures + facts at
`scraper/tests/fixtures/registrar/sb/` (see its README). Four
refinements to the design above, all fixture-driven:

1. **Seven roles, not five.** Published rows link from every cell:
   Jurisdiction → resolution (`RES_*`), Measure Description →
   ordinance/full measure text (`ORD_*`), plus the five planned
   (analysis + four argument variants). Filename scheme extends:
   `measure_{letter}_resolution.pdf`, `measure_{letter}_text.pdf`.
   Role assignment is by COLUMN for jurisdiction/description (their
   link labels are variable text — jurisdiction name / measure
   title), by LABEL within the Arguments list. The Analysis link
   label is exactly "Impartial".
2. **"Announced" state is a first-class page state** (Nov 2026
   fixture): rows exist with Letter "TBD" and ZERO links — Analysis
   cell is plain text, Arguments cell is clerk-contact prose.
   Expected documents = cells that CONTAIN links; link-free rows are
   announced-not-published, a valid observation, not a schema
   failure. Such a snapshot finalizes with
   `pdf_counts {expected: 0, saved: 0}` and a nonzero
   `table_row_count`. §3 step 4's "unrecognized nonblank PDF-link
   labels" rule applies to LINKS in the Arguments list only.
3. **Off-origin PDFs are the norm**: every document lives on
   `uploads.rov.sbcounty.gov`. The design's off-domain-HTTPS
   allowance is the main path, not the exception. (Separate domain =
   separate rate-limit bucket + its own robots check, both already
   base-class behavior.)
4. **Encoding + header quirks**: header "Percentage to Pass"
   contains an internal `<br/>`; the announced-state page declares
   UTF-8 but carries at least one Windows-1252 byte. The extractor
   decodes tolerantly; raw bytes stay pristine in the artifact.

Red-team watch-item #1 is resolved for the observed case: SB links
measures pages months early, but the page exists in announced state
(200) rather than 404. The strict discovery rule found exactly one
canonical candidate today (2026-11-03); past elections (2026-03-24,
2026-06-02) are linked without the `/measures/` suffix and enter via
anchors/backfill, as designed.

**Proposed answers to §9** (for Igor's sign-off): initial anchor
list `("2026-11-03",)` — the sole forward election, self-confirming
via discovery; forward-window cutoff = run date (past elections
excluded until a reviewed backfill batch); first production run
collects anchors only, with 2026-03-24 entering as the first
bounded backfill batch once two forward runs are clean.
