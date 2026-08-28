# How to add a county registrar scraper

> **Audience:** whoever builds the next county. Los Angeles is next,
> then Orange, San Diego, Riverside.
>
> **What you are building:** a scraper and a pure extractor for one
> county. Everything downstream — the artifact store, snapshot
> integrity, identity, parsing to JSONL, loading to the database — is
> shared and already built. You are writing roughly two files and
> their tests.
>
> This guide encodes the pattern San Bernardino arrived at through
> six external review rounds and three production drift events.
> Following it is considerably cheaper than rediscovering it.

---

## 1. Before any code: reconnaissance

Confirm the county's URL patterns and page shape, and record them in
`docs/plans/registrar_manifest.md`. That file already carries a
first pass for all five target counties — **verify it before
trusting it**, since it dates from 2026-06 and vendor URLs go stale
(the January plan listed `sbcrov.com`, which by June no longer
resolved).

You need to know:
- How elections are enumerated (LA uses sequential integer election
  IDs; Orange uses slugs; San Bernardino uses `{year}/{mmdd}` dates)
- Where measures live for one election
- Whether the page is server-rendered (Riverside needs Playwright
  for a Cloudflare challenge; the rest do not)
- Whether a polite User-Agent is required (San Diego 403s without one)

## 2. Pin fixtures before writing the extractor

**This is the single highest-value rule in the guide.** Capture real
pages as raw bytes with a `.meta.json` sidecar into
`scraper/tests/fixtures/registrar/<county>/`, and write the
extractor against those bytes.

San Bernardino's fixtures immediately overturned the design: the
plan assumed five document roles per measure, and the first real
page had **seven** — the Jurisdiction cell links a resolution and
the Description cell links the full measure text, both of which the
design would have rejected as schema violations. Recon tells you the
shape; only fixtures tell you the contract.

Capture at least: the election index/landing page, one measures page
in a **published** state, and — if you can find one — a page in an
**announced** state, where rows exist but no documents have been
filed yet. That second state is real and must not be treated as an
error.

## 3. Write the extractor as a pure function

Signature to match:

```python
extract_measures_page(body: bytes, page_url: str) -> MeasuresPage
```

No network, no storage, no clock. It takes bytes and returns typed
rows plus `ExpectedDocument` descriptors. This separation is why the
parser can replay years of stored snapshots without re-fetching
anything, and why the whole contract is testable against fixtures.

Four rules, each of which was learned the hard way:

**Scope every DOM scan by table ownership.** Only consider rows,
cells, and links whose *nearest ancestor table* is the measures
table. `sb.py` provides `_owned_rows`, `_direct_cells`, and
`_owned_links` for this. Without it, a nested table — or a future
`<th scope="row">` accessibility change — silently drops measure
rows. And because **zero rows is a valid state** (announced
elections), the failure mode is a silently empty published snapshot
that reports success.

**Identify the table by its full header set, never by position.**
Normalize whitespace when matching; San Bernardino's "Percentage to
Pass" header contains a `<br/>`. Require exactly one match: zero or
two are schema failures.

**Assign document roles by label or by column, deliberately.** Use
**label** when one cell carries several document types distinguished
by link text; use **column** when the label carries no role
information (a jurisdiction name, or just the measure letter).
Never key roles on URL filename prefixes — see §7.

**Fail loudly; never guess.** Single-role cells accept zero or one
link, and a second link raises rather than being dropped. Unknown or
duplicated labels raise. Links in cells with no defined role raise.
This is what makes drift *visible* instead of silently corrupting
data, and it is the reason all three production drift events were
caught before any bad record was stored.

## 4. Write the scraper class

Subclass `CountyRegistrarScraper` (`base.py`). Set `county`,
`fetch_mode` (`"requests"` or `"playwright"`), and `version`, then
implement `scrape()`.

The base class already provides, and you should not reimplement:

- **Polite fetching** — identifying User-Agent, per-domain rate
  limiting, retries with exponential backoff on 429/5xx (honoring
  `Retry-After`), never retrying other 4xx, robots.txt checked per
  domain, and manual redirect following so every hop gets its own
  robots check and rate limit.
- **`open_snapshot(election_date)` → `SnapshotWriter`** — manifest
  written last, duplicate filenames rejected, completed snapshots
  immutable. A crashed run leaves orphans that no parser can see.

Use `fetch()` for every request. Do not touch `requests` directly.

**Election enumeration** should follow the hybrid pattern: a
versioned static anchor list as the coverage contract, plus weekly
discovery from the county's index, with discovered candidates
accepted only after strict validation. Anchors are **active** while
`election_date >= as_of_date` in `America/Los_Angeles` and retire
automatically once past; discovery must contain every active anchor,
and empty discovery is a failure only while an active anchor exists.
No active anchors and nothing discovered is a **successful idle
run**, not an error. Getting this wrong makes the cron go
permanently red the week after an election.

## 5. Register the county

Add an entry to `COUNTY_CONFIGS` in `county_config.py`:

```python
"la": RegistrarCountyConfig(
    slug="la",
    county_name="LOS ANGELES",       # must match the existing DB convention
    data_source="LA_County_Registrar",
    extractor=extract_la_measures_page,
),
```

`county_name` must match how the county already appears in
`ballot_measures.db` (upper case, e.g. `LOS ANGELES`), or new rows
will not group with existing historical ones. **Check the database,
do not guess.** Election type is derived from the date and marked
imputed, so adding an election requires no code change.

Then register the scraper in `runner.py`'s `REGISTRY` and add the
slug to `ENABLED_COUNTIES` when it is ready for the weekly cron.

## 6. Test

Mirror `scraper/tests/test_registrar_sb.py`:

- **Fixture contracts** — exact row counts, role census, and the
  per-role URL-prefix distribution (§7 explains why).
- **A synthetic schema-failure matrix** — wrong/missing/duplicate
  headers, two matching tables, malformed rows, cardinality
  violations, unknown labels, non-HTTPS links, nested tables,
  duplicate letters.
- **Clock-controlled anchor tests** — an active anchor missing from
  discovery is red; a retired one missing is a green idle run; a
  newly discovered future election is collected.
- **Integration against `LocalArtifactStore`** with injected
  session, clock, and sleep. No test may touch the network or the
  live database.

```bash
cd scraper && python -m pytest tests/ -q -k "registrar or website_output"
```

## 7. Roles come from labels, not filenames

Counties name their PDF files by convention, and conventions have
exceptions. San Bernardino's URL prefixes are consistent — `RES_`,
`FT_`, `IA_`, `TR_`, `Notice_` — except that San Bernardino City
USD's *"Impartial"* link points at `AIF_SBCUSD.pdf`, an
argument-in-favor filename. Because roles derive from the link
label, it is correctly recorded as an analysis. Had roles been keyed
on the URL, it would have been silently misfiled.

Assert the prefix distribution in tests anyway. It is how that
anomaly was found, and it documents the county's conventions without
depending on them.

## 8. Rollout

1. Fixtures committed, extractor tests green.
2. Scraper implemented, integration tests green.
3. Live smoke: `python scraper/scripts/run_registrar_pipeline.py
   --counties=<slug> --env=dev` — exercises the real site.
4. Register in `REGISTRY`, add to `ENABLED_COUNTIES`.
5. Push (this triggers a dev CI run on registrar paths), then a
   manual `workflow_dispatch` to verify the prod path.
6. Verify the prod snapshot in R2: list snapshots, read the
   manifest, sha-verify one artifact.
7. Watch the next scheduled run.

Then expect drift. Budget roughly one session per two weeks per
county; `docs/setup/registrar_drift_runbook.md` is the procedure.

## 9. County-specific notes

| County | Enumeration | Notes |
|---|---|---|
| **LA** | Sequential integer election IDs, `results.lavote.gov/text-results/{id}` | Largest by far. The text-results portal is server-rendered and carries measure text **and vote totals** — so LA may deliver results data, unlike SB's pending-only measures. Section-organized text rather than a table; the extractor will differ substantially. |
| **Orange** | Slug-based, `/elections/{slug}/measures-on-the-ballot` | Enumerate slugs from the `/elections` index. Unknown whether pre-2020 elections use the same pattern. |
| **San Diego** | TBD | Polite UA is mandatory (403 without). The per-election measures page still needs a recon pass. |
| **Riverside** | TBD | Cloudflare challenge; needs `fetch_mode = "playwright"`. **Prerequisite:** the Playwright path delegates redirects to the browser, so the per-hop robots/rate-limit guarantees do not yet apply to it. Resolve that before enabling. |

## Further reading

- `docs/plans/registrar_pipeline_infra.md` — architecture and rationale
- `docs/plans/registrar_phase1_sb.md` — the SB design, with its
  failure-semantics table and review history
- `docs/LESSONS_LEARNED.md` — the traps, with the incidents that
  produced them
- `docs/setup/registrar_drift_runbook.md` — when the cron goes red
