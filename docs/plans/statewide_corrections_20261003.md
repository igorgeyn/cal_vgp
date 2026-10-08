# Statewide Part 1 corrections — October 3, 2026

**Status:** implemented on an isolated candidate; ready for independent review
before Part 2 release preparation. Production, published files, and all eight
pinned production inputs are unchanged. Nothing committed or published.

This completes the correction batch in the
[independent response to Claude](statewide_part1_review_response_20260913.md).
The three existing identity decisions stand. The original September candidate
and its evidence remain intact; this document describes its replacement.

## Reader behavior

- All 14 propositions use the validated official description in cards, modals,
  and individual pages, with California Secretary of State attribution and the
  actual September source-capture date. Raw legacy summaries remain in storage
  and the export for lineage, but are not the displayed current explanation.
  Unreviewed legacy ballot-question and research-briefing panels are suppressed
  for the reviewed statewide records. Historical comparisons remain separate.
- ACA 13 remains public at `/#m=1` and `/measures/1.html`, is searchable as
  `ACA 13`, and explicitly explains removal from the November ballot on
  June 25 pursuant to ACA 21. It appears as Withdrawn in cards, list rows,
  modals, static pages, and a distinct status filter. It is excluded from the
  14-proposition upcoming band and Pending/Unknown filter/count.
- `is_active` continues to mean curated archive visibility. Eligibility is
  represented by `ballot_status`. ACA 13's raw election date remains null;
  `withdrawn_from_election` records the removed November slate without claiming
  a future election. The browser SQL projection also exposes `ballot_status`.
- Designation-only searches parse an exact proposition number. `Prop 3` and
  `Proposition 3` return the same records and exclude 37/38/39. Optional year
  forms include `Prop 3 2026` and `Proposition 3 (2024)`. Selected years and sort
  still apply. Ordinary text queries continue to use text search.
- Reviewed propositions say “On the November 3, 2026 ballot” rather than
  implying a petition-circulation history. Superseded eligible-initiative links
  are removed; withdrawn records link to their withdrawal evidence.

## Identity, approval, and copy ownership

The eleven unpublished additions now use `PROP_<number>_2026` canonical keys.
Existing integer IDs, canonical keys, fingerprints, and editorial fields are
preserved. Proposition 3 is still integer 10960 / `INIT_1993`, Proposition 4 is
10956 / `SB_42`, and Proposition 5 is integer 2 / its original SCA 1 key. New
integers remain 12467–12477. Public numbers are separate assignment fields.
The [updated ledger](statewide_reconciliation_20260913.md) lists every identity.

The loader accepts
[`review-corrections.json`](../../scraper/tests/fixtures/statewide/20260913/review-corrections.json),
checked against a separate repository-owned
[digest and identity crosswalk](statewide_review_approval_20261003.json).
The canonical review digest is
`96da42cdfea40d9fcf74a15d072d6aafbae25639872464eb42cefc80709da6f6`.
Swapping old identities or editing the reviewed decision invalidates this pin.
The crosswalk records scoped source evidence; PDF keyword matching cannot
replace semantic identity review. This input pin is not publication approval.

The correction entry point creates its own SQLite copy in a new directory.
The source is opened read-only. A marker binds the destination path and file
identity to that owned copy. Direct application to baseline/recovery inputs,
hardlinked copies, replaced working files, and production is refused, including
when the caller supplies a broad scratch root. This protects against operational
mistakes; a local user who forges the marker is outside its threat model.
Strict one-shot drift detection and byte-identical no-write replay remain.

## Evidence and review location

The [versioned evidence report](statewide_corrections_evidence_20261003.json)
pins final candidate bytes, code, review inputs, preservation results, and
browser results. The ignored local working directory is:

`scraper/data/statewide_recon/20261003_corrections/`

| Artifact | Purpose |
|---|---|
| `baseline.db`, `published-baseline/` | Fresh consistent production backup and copies of published root HTML/JSON |
| `production-inputs-sha256.json`, `head.txt` | Unchanged input hashes and actual base commit |
| `candidate/measures.db` | Corrected owned copy; 12,425 total rows, 12,372 public records |
| `candidate/site/index.html`, `measures-data.json` | Real CLI output using existing finance, Insights, recommendations, and offline embedding model |
| `candidate/site/measures/`, `sitemap.xml` | 12,372 individual pages and 12,374 sitemap URLs, including ACA 13 and SMC |
| `candidate/mirror/` | Byte-identical main HTML/JSON/Use CalBallot output pair |
| `candidate/build.json`, `build-process.json`, `build.log` | Build timing, actual process exit, and full log |
| `preservation-report.json` | Independent row/field/schema/sequence/payload checks |
| `replay-report.json` | Same reviewed correction produces zero writes and identical DB bytes |
| `browser/` | Desktop/mobile screenshots and typed-search/route/content evidence |

Serve `candidate/site/` locally for interactive review; opening HTML directly
with `file://` will not reliably load its JSON. Review `Prop 3`, `Prop 4`,
`Prop 5`, and `ACA 13`, then test the historical year variants. The
[Claude review prompt](../codex/statewide_corrections_review.md) specifies the
independent acceptance questions and safe probe boundaries.

Verification completed:

- **61 focused tests pass** across the statewide, upcoming UI, output contract,
  documents, local context, and Use CalBallot suites. Regression coverage includes
  swapped identities, review changes, cross-year keys, baseline protection,
  file replacement/hardlinks, rollback, drift, replay, and both generator paths.
- The actual paired CLI build exits zero. Its default root destinations were
  redirected to scratch; the offline embedding model completed successfully.
- Preservation checks cover every existing database row, all original schema
  definitions/indexes/triggers, sequence allocation, all 12,414 original search
  rows, all unrelated tables, and all original public records. Only the reviewed
  metadata/projection changes and 11 insertions are accepted. The pre-existing
  129 null `last_seen_at` values are regenerated only in model exports and checked
  against the build's time window; raw DB values remain unchanged.
- Finance, Insights, recommendations, and topic counts match the published
  baseline. All **49 county document groups / 239 links** are preserved.
- Chromium at 1440×1000 and 390×844 clicks all 14 cards, checks exact official
  modal descriptions/attribution, types designation queries, checks first
  results and exclusions, exercises year-filter intersection and sort, follows
  the withdrawn static-page link, loads its direct deep link, and verifies
  withdrawal status/filter/list behavior. County links and a known 2022 Finance
  record are checked. No page errors; external requests are blocked.
- Static page IDs and sitemap membership match the complete export. All 15
  reviewed statewide static pages are checked for their authoritative content,
  source, and stable explorer link. Mobile screenshots were visually inspected.

The first test pass found a SQLite connection left open by the new copy helper
on Windows; explicit connection closure fixed it. Browser-harness corrections
addressed the results-container selector, CSS-uppercase badge text, and modal
visibility. These are recorded to distinguish test-harness changes from product
changes. The final checks use the final generated bytes.

## Source dates and remaining limits

The 23 captured official artifacts remain the September 13 versions. An
October 3 read of the
[official qualified list](https://www.sos.ca.gov/elections/ballot-measures/qualified-ballot-measures)
still showed the same 14 November propositions and ACA 13 removal notice; it
also showed a new March 2028 section. That read does not recapture the 14 detail
pages or make the older descriptions current as of October 3. No scraper or
county capture ran in this correction batch. Source freshness remains an
explicit release check. The `reviewed_at` value is a controlled batch stamp;
capture and build times are recorded separately.

The scratch site is not yet a deployable release package: local document assets,
other static assets, and deployment inputs still need a complete inventory and
link check. The static-page builder still does not display the county document
collection. External services, live links, browser DuckDB execution, and AI chat
were not exercised by the offline browser run. Eleven new measures still lack
topic classification. Existing historical canonical-key ambiguity remains;
this batch avoids new collisions without migrating old identities or enrichment
consumers. Full election/result transitions and routine refresh/supersession are
still later work. No off-machine backup or promotion/recovery rehearsal was done.

## Next: Part 2, narrowed to the October 5 objective

The September target windows have elapsed. Do not treat their planned dates
as completed work or compress unverified gates into a completion claim.

1. Independently review this corrected candidate and resolve concrete blockers.
2. Check source freshness and decide the accepted statewide/county vintage.
   If changes require a new reviewed input, explicitly revise the pin and stage
   them from a fresh baseline. Do not edit the sealed candidate in place or
   relax replay checks. County updates are conditional on reviewed evidence.
3. Finish the complete site bundle: county document sections on static pages,
   local document/static assets, sitemap, and internal link validation.
4. Prepare and test recovery from the exact DB/source/build-input bundle,
   including an off-machine copy. Stage any combined changes on copies.
5. Review the final release. Promotion must exclude concurrent writers, check
   production still matches the accepted baseline, handle actual SQLite
   sidecars/journal state, and retain a tested rollback package. A preflight
   hash alone does not prevent a concurrent write after the check.
6. Publish only after the concrete release is approved; verify served artifacts
   and reader paths. Then resume the refresh and election-status work.

Keep county expansion and the card redesign deferred. Two useful counties and
an accurate statewide slate remain the reader goal; Part 1 completion is not
evidence that the complete October 5 operational goal has been met.
