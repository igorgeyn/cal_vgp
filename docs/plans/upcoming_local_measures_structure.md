# Upcoming local measures: split-band structure

> Decision record, 2026-08-27. This describes the presentation-layer change in
> `scraper/src/website/generator.py`; it does not activate registrar data or
> publish generated site artifacts.

## Structure chosen

The “Upcoming 2026 Ballot Measures” section is split into two bands:

1. **Statewide measures** keep the existing carousel and existing `createCard()`
   rendering.
2. **Local measures** are grouped into native `<details>` county accordions. A
   single captured county opens automatically. When multiple counties are
   present, every county starts as a compact name-and-count row. An opened county
   shows a responsive card grid, initially limited to 12 cards, with an explicit
   show-all/show-first-12 control.

This avoids turning 150 measures into a 50-page carousel. At five counties the
collapsed view is five rows; within a county, the preview prevents a large county
from immediately creating a very long page. The markup remains useful without
JavaScript animation and uses native disclosure semantics.

Local cards deliberately use registrar fields rather than the statewide card’s
summary/topic shape: measure letter, jurisdiction, source description as the
measure type when no reviewed classification exists, authoritative vote
threshold, human-readable registrar label, and the official county page. The
generic description is not repeated under a title that already contains it.
Registrar rows are also excluded from the pending-measure semantic-history loop:
generic labels such as “Bond Measure” do not support defensible similarity results.
That context can be reconsidered after official text is persisted and emitted.

Coverage language names only the counties currently captured and explicitly says
the section is not a complete address-specific ballot. With no local records, the
band remains visible with an honest county-by-county coverage empty state.

## Scaling and a future geography filter

The renderer already has one stable group key per local record
(`upcoming_county`) and one disclosure element per key. A future lightweight
geography control needs only to select one or more of those keys, rerender the
same groups, and optionally open the selected county. It does not require changing
card markup or replacing the statewide carousel. An address-based ballot finder
would require precinct/district boundary data and is intentionally not implied by
this structure.

## Threshold provenance

Thresholds on these pending local cards are labeled “Official vote threshold” and
come from the named county election office. The link to the historical Rules
insight carries a visible caveat that the broader historical corpus also contains
derived threshold fields with known cases under review. Registrar facts are not
used to imply that every historical threshold is equally authoritative.

## Official-documents scope decision

This change ships **without document counts or schema work**. The current 88
official document observations are not in `ballot_measures.db`; only the single
full-text-role `pdf_url` is available to the site generator. Showing counts would
therefore require a new persistence and publication contract, not a presentation
change.

The local card has a dedicated action row containing the official county-page
link. A future “Official documents” action can occupy the same row after a
`measure_documents` table (measure identity, role, source/archive URL, checksum,
size, snapshot, observation dates, active/superseded state) is designed and
emitted. Document URLs must not be placed in prose fields such as
`pro_arguments`; presence is not content.

## Verification snapshot

Using a copy of `scraper/data/ballot_measures.db`, the existing normalized San
Bernardino batch inserted 20 records with no updates, deactivations, or conflicts.
The copy moved from 12,365 to 12,385 total records and from 12,312 to 12,332 active
records. Scratch generation produced 4 active statewide 2026 cards and 20 local
cards. Although the database has 22 total statewide 2026 records, 18 are inactive;
the active view and deployed JSON contain 4. The implementation preserves that
actual active statewide set and its existing card/carousel renderer.

The checked-in normalized batch represents the 20-row, 56-document Aug. 14
snapshot. Neither configured artifact-store environment exposed a complete
snapshot in this workspace, so the later 88-document snapshot could not be
reparsed locally. That does not affect this presentation verification because no
document observations or counts are consumed by the generator.

A browser smoke test confirmed the 12-card preview, expansion to all 20, honest
zero-local empty state, human source label, official link, and threshold display.
A synthetic 150-record distribution across Los Angeles, Orange, Riverside, San
Bernardino, and San Diego rendered as five collapsed 30-measure county groups.
