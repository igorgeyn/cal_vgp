# Results transition — bounded design, September 7, 2026

Status: design for October implementation. No results ingestion is enabled.
Start with the counties actually published, not a statewide scraper framework.

## Reader contract

Election timing and result status are separate. Before the election, show
Upcoming. Once that date passes without a result observation, show Awaiting
results. An official preliminary observation is Unofficial results; certification
requires an explicitly sourced certified observation. Never infer an outcome,
certification, or a completed count from the calendar, turnout, or a threshold.

For registrar records, project a result into the existing `passed` field only
from a supported certified observation. Keep unofficial counts and any reported
preliminary outcome in the result observation, displayed with explicit status.
They must not silently enter historical pass-rate aggregates. Existing historical
records retain their accepted outcome semantics. Verify every outcome consumer
against this boundary before activation.

All presentation surfaces must use the same status rule: hero selection, cards,
lists, modal, filters and results display. The current `year >= 2026` pending
predicate and year-only hero selection cannot survive results ingestion.

## Identity and observation contract

- Match each external result contest through a reviewed mapping to the existing
  integer `measures.id` and canonical registrar `measure_id`. Include source,
  election date, jurisdiction and reporting scope in the mapping evidence.
- Preserve official contest identifiers as aliases, not replacement identities.
  A letter or similar title alone is insufficient. Ambiguous/unmatched contests
  remain quarantined with source links and an operator report.
- Retain immutable result observations: source URL/artifact checksum, capture
  time, source's reporting time if available, status, yes/no totals, reported
  outcome if any, and geographic scope. Reimports are idempotent. Corrections
  supersede observations rather than destroying them.
- A reviewed current-observation pointer selects the displayed result. Reject
  accidental stale rollback. An explicit correction can revise counts downward;
  counts are not a monotonic watermark.
- Regional county observations may be county portions or repeated region-wide
  totals. Do not sum or collapse them automatically. An RTM cross-link establishes
  a relationship, not vote aggregation semantics.

## Ownership and scope

Keep results ingestion separate from the existing registrar JSONL loader, which
correctly rejects outcome fields. The results path owns observations and the
reviewed outcome projection; document refreshes own source/document fields.
The same transaction updates the selected result and any projected fields.
Retain `measure_documents`, document snapshots, editorial enrichment and IDs.

The first implementation may ingest a reviewed local results file rather than
an automatic scraper. Exact source formats and certification signals for the
supported counties still need verification against official artifacts before
that implementation is accepted. This design does not claim source readiness.

## Acceptance before November 3

Rehearse on database copies: awaiting results, unofficial counts without a call,
certification, revised counts, zero and null values, unknown thresholds, stale
observation rejection, ambiguous matches, regional reporting scope, repeated
imports, transaction rollback, and a subsequent ordinary registrar refresh.
Existing IDs, document history and unrelated rows remain identical. Historical
analytics and all UI surfaces must agree on how unofficial outcomes are handled.

If results are unavailable, display Awaiting results with the official source
link and source-check time. November 4 is not an automatic result deadline.
