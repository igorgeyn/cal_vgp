# Official documents — implementation and review, September 7, 2026

> **Review follow-up complete:** see
> [independent disposition and evidence](official_documents_review_response_20260907.md).
> Latest validation: 261 registrar/site tests passed. Document changes and
> provenance refreshes are reported separately; the UI says Last captured;
> missing/mismatched IDs fail before output. Snapshot storage IDs/filenames
> remain in SQLite rather than public JSON. The original preview below is
> historical; current evidence and previews are in
> `scraper/data/registrar_recon/documents_review_response_20260907_final/`.

F1 is implemented locally and verified on an isolated database copy. No live
scraping, production database loading, root site regeneration, commit, push or
publication was performed. The production database and root HTML/JSON hashes
were unchanged by the verification command.

## Behavior

- `measure_documents` stores the latest accepted document-role associations,
  preserving the existing integer measure ID, source URL, raw snapshot filename,
  checksum, byte length, content type, snapshot ID, capture time and listing URL.
- The loader plans and reports document changes separately from measure changes.
  A replay can populate documents for already-loaded measures without updating
  those measure rows. Repeating the replay does no writes.
- Document changes, identity registrations, measure updates and scope watermarks
  share a transaction and the existing backup/reconciliation/rollback gates.
- The common site-generation boundary attaches document metadata, preserving
  both CLI and model-based generation. Existing databases without the new table
  retain their old behavior until an accepted snapshot is loaded.
- The modal groups composite PDFs by source URL and captured checksum, lists all
  their roles, and shows the capture date. Shared packets can appear under each
  relevant measure. A text PDF in the panel is not duplicated in generic Links.
- Links open current county files. The UI does not claim they are immutable
  archive links or that a missing link proves a document was never filed.

## Verification

**252 registrar/site tests passed**, including actual headless Chromium
rendering. New cases cover migration replay, document-only additions/replacements/
removals, unsafe metadata, transaction rollback, shared and composite packets,
packet-only links, canonical ID reuse and both generator entry points. The SMC
fixture also traverses mocked capture, parse and load: 29 measures, 167 role
associations, 135 per-measure grouped links. No live requests are made.

The real-data copy check lives at
`scraper/data/registrar_recon/documents_review_20260907_final/verification.json`.
It verifies all 12,361 measure rows and preserves every supplied prepared JSON
field; finance, insights and recommendation payloads are reused from the existing
site. That original check did not exercise the CLI's model-field filter. The
review follow-up adds that separate check without claiming to verify semantic
enrichment regeneration.

| County | Local accepted snapshot | Roles inserted | Distinct URLs |
|---|---|---:|---:|
| San Bernardino | 20260828T004155Z | 88 | 87 |
| San Mateo | 20260901T024142Z | 167 | 132 |

The resulting preview has 49 measures with documents and 222 per-measure grouped
links. These numbers deliberately reflect the local accepted snapshots. The
September 7 brief reports newer captures, including 105 SB documents; those
captures were not fetched or loaded here. F1's production release must use a
reviewed intended snapshot rather than presenting this preview as latest data.

Preview: `scraper/data/registrar_recon/documents_review_20260907_final/site/index.html`.
It needs an HTTP server, like the existing site, to fetch `measures-data.json`.
Screenshots in that review directory show the SMC Measure R document section at
desktop and mobile widths. The panel contains six links including a combined
full-text/tax-rate/resolution packet; generic Links has no duplicate text link.

The full-page mobile check also found 15px of horizontal overflow in existing
view/pagination controls. The unchanged root site reproduces the same 405px
page width at a 390px viewport. The new document panel fits within the viewport;
this unrelated layout issue is recorded rather than included in F1.

## Reproduce without touching production

Run from the repository root, choosing a **new** output directory:

```powershell
python scraper/scripts/verify_registrar_documents.py --db scraper/data/ballot_measures.db --site index.html --jsonl scraper/data/registrar_normalized/sb_2026-11-03.jsonl --jsonl scraper/data/registrar_normalized/smc_2026-11-03.jsonl --output-dir scraper/data/registrar_recon/documents_review_new
```

The script opens the source SQLite database in read-only mode, takes a SQLite
backup into the new directory, and requires document-only loader plans. It
checks same-snapshot replay idempotency, exact measure-row equality, prepared
input fields and source-file hashes. It also generates `cli-site/` through the
real CLI database/model/export path and verifies active IDs and documents.
Enrichment inputs are controlled and the embedding step is not exercised; the
report explicitly states that this is not a full production rebuild. Network
connections are forbidden while rendering. It does not load production or publish.

## Next steps in the accepted plan

Review this local feature; select the intended snapshots and release it through
the normal reviewed publication path. Then wire offline parsing and a reviewable
publication handoff into the scheduled workflow, expose freshness separately
from build time, and fix election-status selection. The drafted results contract
is in [results_transition_20260907.md](results_transition_20260907.md).
