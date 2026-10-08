# Forward plan — September 7, 2026

> **Ordering superseded September 13:** use
> [the six-part delivery plan](six_part_delivery_plan_20260913.md). It adds the
> confirmed statewide correction and complete publication/recovery work before
> routine refreshes. This document preserves the earlier reasoning and F1 contract.

Igor accepted documents and reliable updates before county expansion. Budget:
10 Igor-hours/week for now, with substantially more LLM execution time. Schedule
six hours of Igor involvement and reserve four for review surprises and maintenance.
Two useful counties by October 5 is success; Alameda is conditional.

## Sequence

- September 7–18: F1 official documents end to end for San Bernardino and San
  Mateo; a reviewable capture/parse/publication handoff; correct election-status
  rendering; define the results identity/state contract. Review concrete outputs.
- September 18: Alameda earns a five-day implementation slot only if the core
  works and Igor's review capacity remains. Include HTML ballot questions,
  recognized missing thresholds, packet links and regional cross-links.
- September 21–25: conditional Alameda, otherwise finish the core and advance
  results work. No naming migration or browser-access project.
- September 28–October 2: release acceptance, mobile/keyboard checks, scheduled
  handoff exercise and maintenance instructions. October 5 is readiness day.
- October 5–16: bounded results updates with explicit mappings to existing IDs.
- October 19–23: rehearse incomplete/revised results, idempotency, cross-county
  reporting scope and subsequent document refreshes on isolated copies.
- October 26–November 3: freeze expansion and prepare election operations.

Cut backfill, blocked counties, OCR, finance expansion, generated briefings,
automated drift-fix PRs and general regional aggregation from this commitment.
Keep county-specific records and cross-link verified regional relationships.

## Why this ordering

Capture health is not publication health: scheduled CI currently neither parses
nor publishes. Vocabulary drift preserves the archive but still delays readers.
Measure maintenance in repair hours and public-data delay, not red workflows:
multiple county incidents can occur in one weekly workflow. The three-event
sample and one unchanged weekly interval do not establish steady-state cost.

Historical county-volume percentages do not measure November voter coverage.
The current UI considers every 2026-or-later measure pending regardless of
results. Alameda additionally needs shared parser/loader changes for full ballot
questions, null thresholds and packet links. Those outrank renaming fields.

The election date passing must not imply a result: distinguish awaiting results,
unofficial results and certified results, with provenance and reporting scope.
Keep result updates separate from document-source fields and preserve IDs.

## F1 implementation contract and review

Scope: local implementation and isolated-copy verification. No live scraping,
production database load, root site artifact regeneration or publication in
this implementation step.

Store the latest accepted document-role associations in `measure_documents`,
linked to the existing integer measure ID. The raw immutable snapshots remain
the historical record. One measure may have several roles for the same PDF; a
PDF may belong to several measures. Do not impose global URL/hash uniqueness.

The loader must plan document inserts/updates/removals even for unchanged
measures, show them in dry-run output, and persist them in the same transaction
as measures, identity aliases and scope watermarks. Replaying an already loaded
snapshot must populate the new table; replaying it again must do no writes.
Existing rollback and reconciliation gates still apply. Document disappearance
updates the current association set, not the raw archive or editorial fields.

Both generator entry points must read document metadata through the common
prepared-generation boundary. An unmigrated database retains existing pdf_url
behavior. A migrated record displays grouped, labeled official links and the
capture date; historic/non-registrar records retain their fields and IDs.
Links open the county's current file, not a promised immutable archive copy.
Missing roles do not establish that a document was never filed.

Review gates: composite/shared packets; document-only changes; removal/replay;
canonical identity aliases; cross-county isolation; transaction rollback; unsafe
URLs; unchanged measure/editorial/outcome rows; JSON export and browser rendering.
Verify against stored local artifacts without claiming they are the latest R2
snapshots. Preserve and report any mismatch in snapshot recency.

Design review: the persisted relationship must use canonical database IDs after
identity resolution, not proposed parser IDs. A document-only write needs its
own plan/report signal. Joining metadata at the shared generator boundary avoids
the known dataclass-field filtering loss. Public grouping uses URL and captured
checksum together so different captured bytes are not silently merged.
