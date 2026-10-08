# Part 1: statewide correction plan and verified candidate

**Historical candidate:** September 13, 2026. The results below describe the
original candidate and are preserved for review history. Its correction batch
is now implemented and verified; use the [October 3 handoff](statewide_corrections_20261003.md)
and [current evidence](statewide_corrections_evidence_20261003.json) for the
accepted input, current behavior, commands, counts, and next steps.
Production remains unchanged; nothing in Part 1 has been committed or published.

This executes Part 1 of the [six-part delivery plan](six_part_delivery_plan_20260913.md).
The source correction has priority because the published statewide list omits
qualified propositions and includes a withdrawn measure. A cosmetic improvement
would not address that failure. County expansion and the card redesign remain deferred.

## Plan of attack and completion

| Step | Work and acceptance condition | Result |
|---|---|---|
| 1. Establish the baseline | Record HEAD; hash production inputs; use SQLite’s backup API from a read-only source connection; keep all later database/build writes in scratch. | Complete. HEAD `ec650a290992da7c7f903800419e59b523de8e9d`; consistent baseline and published HTML/JSON saved. |
| 2. Pin official evidence | Read only the relevant official statewide pages and identity documents. Preserve bytes, dates, URLs, and hashes. Separate the November 2026 section from withdrawal notes and 2028. | Complete. 23 artifacts captured, including all fourteen proposition pages. |
| 3. Reconcile identities | Audit active, inactive, duplicate, and malformed current/future CA_SOS records. Resolve each official proposition and every old row; do not match by a similar title alone. | Complete. All 22 old rows have dispositions; three matches, eleven additions, one withdrawal. |
| 4. Define ownership | Preserve integer IDs, canonical identifiers, fingerprints, editorial content, historical records, registrar scope, and documents. Represent proposition numbers and removal separately. | Complete. A narrow ballot-assignment table carries official presentation and provenance. |
| 5. Implement an offline correction | Require a named scratch database. Default to a read-only check; validate source bytes and database preimages; apply atomically; reject identity collisions and drift. | Complete. `reconcile_statewide.py` has no production override or fetching behavior. |
| 6. Exercise failure and repetition | Test stale evidence, stale records, wrong identity, missing database, wrong destination, production hardlink, mid-transaction failure, and replay. | Complete. Rollback preserves rows/schema; repeat apply makes zero writes and preserves file bytes. |
| 7. Build the real candidate | Use the actual CLI with real finance, Insights, recommendations, cached semantic model, and county context. Redirect both output roots. | Complete. Exit 0; 12,371 exported records; three paired assets byte-identical. |
| 8. Check preservation and readers’ paths | Compare all old records, document groups, enrichment payloads, IDs, and source fields. Exercise desktop/mobile list, modals, search, and links. | Complete. Gate passes; all fourteen modals verified in both viewports; no page errors. |
| 9. Hand off a reviewable result | Save the exact ledger, code, fixtures, commands, hashes, screenshots, and remaining release work. | Complete. See the links and Part 2 checklist below. |

## Result and identity decisions

The candidate contains **fourteen November 3 propositions**: 1–5 and 37–45.
There are 12,425 total database rows and 12,371 active public records.

- Proposition 3 retains integer **10960** and canonical **INIT_1993**.
  The SoS eligible list connects initiative 1993 with AG 25-0016; its formal Act
  and constitutional amendment match the Proposition 3 law text.
- Proposition 4 retains integer **10956**, **SB_42**. The official law identifies
  SB 42, Chapter 245, Statutes of 2025.
- Proposition 5 retains integer **2** and the existing SCA 1 canonical string.
  The official law identifies SCA 1, Resolution Chapter 204, Statutes of 2024.
- Eleven new records receive integers **12467–12477** and `PROP_<number>`
  canonical IDs. The existing SQLite sequence explains this range.
- ACA 13 retains integer **1**, its original identifiers and all content. Its
  `is_active` flag becomes 0, and its ballot assignment records `withdrawn` with
  the official notice and ACA 21 evidence. No later election date is assigned.

The [full reconciliation ledger](statewide_reconciliation_20260913.md) has one
row per proposition and a disposition for every old current/future CA_SOS row.
The machine-readable [review input](../../scraper/tests/fixtures/statewide/20260913/review.json)
is the reproducible input to the correction. The [evidence report](statewide_candidate_evidence_20260913.json)
pins the exact code and candidate hashes and includes the row/field diff.

## Field ownership and implementation

`statewide_ballot_entries` stores the integer/canonical pairing, official title,
proposition number, election date, qualified/withdrawn status, official URL,
capture time, identity evidence, and review digest. It has a unique election /
proposition-number constraint. `statewide_ballot_reviews` preserves the review,
all 22 original rows, the resulting row hashes, and assignment rows for replay
and drift checks. These are narrow correction tables, not a replacement ingestion framework.

| Data | Treatment |
|---|---|
| Existing integer IDs, canonical IDs, fingerprints, titles, source/PDF URLs | Preserve in `measures`; do not renumber or regenerate fingerprints. |
| Matched election metadata | Set ISO `2026-11-03`, general election, and non-imputed date/type metadata; update tracking timestamp/count. |
| ACA 13 | Change only active flag and update tracking in its original row; retain all other fields. Store withdrawal evidence separately. |
| Existing summaries, generated titles, briefings, fiscal data, proponents/opponents, research metadata | Preserve. This task does not re-review or replace existing editorial work. |
| New records | Official title, neutral overview, measure type, date and source; no generated summary or fabricated outcome. |
| Public display | Join official assignment fields by both integer and canonical identity. Prefer official title and proposition number. Use the direct voter-guide page and verified legislative session. |
| Historical / registrar rows and documents | Preserve all original fields, identities, scope rows, and document associations. |

The shared projection serves both main generator entry points. Part 2 must use
it in the separate individual-page builder as well. The original statewide
scraper and `pipeline.py check` are not used by this correction.

Two targeted website fixes were necessary: proposition numbers sort numerically
and display consistently in cards/modals; text search includes official titles
and proposition aliases and can return upcoming matches. The default archive
still excludes upcoming records. No card redesign was included.

## Verification evidence

- **54 focused tests passed** across the new statewide module, both website
  generation paths, official documents, output contract, local context, and
  the Use CalBallot page. The eight upcoming UI tests were repeated after the
  final search change and passed.
- A read-only check left the candidate database bytes unchanged. Applying once
  inserted eleven records, matched three and withdrew one. Repeating the apply
  returned `unchanged`, zero writes, and the same SHA-256.
- The real CLI build exited **0** using the local model cache. It included
  semantic context for 15 pending records, reviewed local context for 28,
  and finance for 181. No semantic-context fallback occurred. The existing
  “No AI providers” warning is expected: no new AI titles are requested.
- All **12,414 original database rows** remain. Only the four named statewide
  rows have allowed field changes. All existing search rows remain and the
  eleven new search rows match the inserted official text.
- All fourteen unrelated tables checked by the gate are unchanged, including
  registrar identity/scope/alias tables, historical data, scraper logs, and
  document-role rows. **272 document-role rows still project to 239 links on
  49 county measures.**
- Finance, Insights and recommendation payloads are unchanged. The only topic
  count adjustment is `Governance: Elections` **55 → 54**, explained by ACA 13
  leaving the active cohort. Existing semantic and local context are unchanged.
- The export regenerates `last_seen_at` for **129 records with null stored
  values**, an existing model behavior. Each new timestamp falls inside the
  recorded build window; their database rows remain unchanged.
- Chromium checks passed at **1440×1000** and **390×844**: fourteen numbered
  cards in numeric order, fourteen correct modals per viewport, On Ballot stage,
  direct official links, retained `#m=<id>` routes, proposition search, county
  document groups, and a historical Finance tab. No page errors occurred.
- All eight hashed production inputs remain unchanged. The candidate build
  also leaves its own database unchanged. HTML, JSON and Use CalBallot output
  are byte-identical across the two isolated output roots.

The browser run blocks external requests. It proves the local bundle’s behavior,
not remote PDF/CDN availability. Official source bytes were separately captured
and inspected; election-transition behavior remains Part 4.

## Files and local review

Entry points, run from the repository root:

- [Offline correction](../../scraper/scripts/reconcile_statewide.py)
- [Independent preservation gate](../../scraper/scripts/verify_statewide_candidate.py)
- [Actual-browser check](../../scraper/scripts/check_statewide_browser.py)
- [Loader and shared public projection](../../scraper/src/database/statewide_ballot.py)
- [Source fixtures and reviewed input](../../scraper/tests/fixtures/statewide/20260913/README.md)
- [Desktop slate screenshot](../../scraper/data/statewide_recon/20260913_part1/browser/desktop-slate.png)
- [Mobile Proposition 3 screenshot](../../scraper/data/statewide_recon/20260913_part1/browser/mobile-prop3.png)

Local evidence lives under `scraper/data/statewide_recon/20260913_part1/`, which
is ignored by Git. The review, raw source fixtures, source code, ledger, and
condensed evidence report are source-controlled candidates, currently uncommitted.
The complete database/site copies will need custody in Part 2’s recovery bundle.

The scratch directory contains `baseline.db`, `published-baseline/`,
`candidate/measures.db`, `candidate/site/`, `candidate/mirror/`, `load-evidence.json`,
`preservation-report.json`, `candidate/build.json`, `build.log`, and `browser/`.

For interactive local review:

```powershell
python -m http.server 8765 --bind 127.0.0.1 --directory scraper/data/statewide_recon/20260913_part1/candidate/site
```

Open `http://127.0.0.1:8765/`. This command starts a local preview only. Opening
`index.html` directly as a file may prevent its JSON fetch.

To check or replay the existing candidate without touching production:

```powershell
python scraper/scripts/reconcile_statewide.py --review scraper/tests/fixtures/statewide/20260913/review.json --db scraper/data/statewide_recon/20260913_part1/candidate/measures.db --scratch-root scraper/data/statewide_recon/20260913_part1/candidate
```

Adding `--apply` on this already-corrected copy returns `unchanged`. A fresh copy
must be made with a consistent SQLite backup and pass the pinned preimage gate.
If production changes, re-audit and prepare a new review; do not force this one.

To repeat the independent gate:

```powershell
python scraper/scripts/verify_statewide_candidate.py --baseline-db scraper/data/statewide_recon/20260913_part1/baseline.db --baseline-site scraper/data/statewide_recon/20260913_part1/published-baseline/index.html --candidate-db scraper/data/statewide_recon/20260913_part1/candidate/measures.db --candidate-site scraper/data/statewide_recon/20260913_part1/candidate/site/index.html --review-path scraper/tests/fixtures/statewide/20260913/review.json --build-metadata scraper/data/statewide_recon/20260913_part1/candidate/build.json --production-hashes scraper/data/statewide_recon/20260913_part1/production-inputs-sha256.json --output scraper/data/statewide_recon/20260913_part1/preservation-report.json
```

The checked-in evidence records the candidate hashes. A rebuild changes build
timestamps, so record a new build window, rerun the gate/browser check, and
update evidence before promoting different bytes. The sealed F1 release
verifier rejects this insertion candidate by design; do not weaken that gate.

## Part 2 handoff and remaining release work

Effort: this was one agent implementation session, with no additional user
decision needed. Actual Igor review time and model execution hours were not
instrumented; no precise hours-versus-estimate claim is made. The chosen
reviewed-input path avoided rebuilding the all-source scraper.

1. Recheck HEAD, production input hashes and official slate against this review.
   Do not replace a newer production database with this copy. If another source
   changes first, rebase the correction onto a new consistent backup.
2. Inventory and preserve the complete build-input bundle; establish the private
   off-machine recovery location and prove a restore into a separate directory.
   A local SQLite copy is not completion of the recovery requirement.
3. Make the individual-page builder consume these same assignment fields and
   grouped county documents. Generate San Mateo’s missing 29 pages, update San
   Bernardino pages, and reconcile all current statewide pages and sitemap.
   Preserve old public routes where appropriate and explicitly handle the old
   withdrawn ACA 13 page. Do not publish contradictory main and detail pages.
4. Review source/status wording throughout the release bundle, including the
   hero’s old “details will be available” sentence. Existing editorial summaries
   were preserved; they should not be mistaken for newly validated official text.
5. Validate the entire release candidate and recovery manifest. Keep the old
   multi-endpoint statewide scraper from overwriting this accepted correction;
   a future refresh must reconcile against these identities and evidence.
6. Commit and publish the accepted complete bundle under the active publication
   authorization, then verify served artifacts. Part 1 itself performs neither.

Parts 3–6 remain as written in the six-part plan. The ten Igor-hours/week budget
still applies; the next human review should focus on the identity ledger,
current slate, and Part 2’s concrete release/recovery result.
