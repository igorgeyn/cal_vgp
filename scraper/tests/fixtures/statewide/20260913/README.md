# November 2026 statewide correction evidence

Captured September 13, 2026 from California Secretary of State, its official
voter-guide/CDN hosts, and the California Attorney General. `review.json`
contains source URLs, final URLs, capture times, byte counts, and SHA-256 hashes
for the 23 unmodified artifacts in `sources/`.

`before.json` contains the 22 existing CA_SOS current/future records, including
inactive records and duplicates. It is a regression fixture, not a complete
application database. Its full-row hashes are pinned by `review.json`.

The normalized review is a deliberate, bounded input. The loader does not
discover identities or fetch pages. Source hashes, election sections, titles,
numbers, descriptions, and database preimages are checked before mutation.
The identity decisions require review of the cited official documents.

`review-corrections.json` is the October 3 revision of those decisions using
the same September 13 source bytes. It adds explicit withdrawal presentation
and year-qualified keys for new records. The loader now accepts only this
revision, checked against the separate repository-owned digest and identity
crosswalk in `docs/plans/statewide_review_approval_20261003.json`. The original
`review.json` remains historical evidence, not a currently accepted load input.
Neither this pin nor a successful load authorizes publication. Source capture
dates are unchanged; this revision does not imply an October source recapture.

See [the ledger](../../../../../docs/plans/statewide_reconciliation_20260913.md)
and [Part 1 handoff](../../../../../docs/plans/statewide_part1_20260913.md).
Raw captures are government publications; retained legacy database summaries
are existing application content, not newly supplied official summaries.
