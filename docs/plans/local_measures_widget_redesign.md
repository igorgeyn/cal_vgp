# Local measures widget: research-led redesign

> **Status:** compact-card variant implemented and scratch-verified
> 2026-08-27. The original research recommendation below preferred a
> fixed-height list; Igor's final product decision kept cards and used a
> carousel. That decision supersedes the rejected-card/carousel bullets in
> this document while retaining the county-control and scope rationale.
>
> **Goal:** a compact county-level widget roughly the height of the
> existing statewide carousel, with county switching, that stays the
> same height whether it holds 20 measures or 2,000.

---

## 1. What the best comparable tools do

| Tool | Approach | Lesson |
|---|---|---|
| **Voter's Edge CA** (MapLight + LWV) — **discontinued** | Address lookup → full personalized ballot; embeddable per-measure widgets | Address lookup is the category's default. Its shutdown left a real gap. |
| **CalMatters 2024 Voter Guide** | Rebuilt local coverage by collecting from **all 58 counties directly**, then address lookup | The closest precedent to this project, and validation of the approach. Their answer to "which measures are yours" is address. |
| **BallotReady** | Address → personal ballot; mobile-first, multilingual, accessibility-led | Compactness and mobile-first are table stakes, not polish. |
| **Ballotpedia** | Encyclopedic index pages plus a sample-ballot lookup | Index pages scale but do not help a voter decide. |
| **USWDS** (US government design system) | ≤15 options → `select` or radio; >15 → combo box, **but** combo boxes have unresolved accessibility problems and `select` is currently recommended regardless | Directly settles the county-picker control. |

**The central tension.** Every serious tool answers *"what is on MY
ballot"* via address. This project cannot: the data is **county- and
jurisdiction-scoped**, not precinct-scoped. A voter in Ontario should
not be shown Needles measures as "theirs."

So the honest framing is **a county browser, not a ballot lookup** —
which the current implementation already states correctly. The design
should make that scope obvious rather than hide it, and should leave a
clean upgrade path to address lookup if district boundary data ever
lands.

## 2. The real problem with the current band

It is not that the cards are too big. It is that **cards are the wrong
form for this task**.

Cards suit browsing a handful of rich, visually distinct items. These
20 measures are the opposite: near-identical in structure, each with
the same four short attributes (letter, jurisdiction, type, threshold),
and the user's task is **scanning to find the one or two that apply to
them**. That is a list task, and a list is roughly four times denser.

A card grid also grows without bound: 20 measures is 7 rows of cards;
Los Angeles alone could be 100+.

## 3. Design principles

1. **Constant height.** The widget occupies a fixed block (~420px)
   regardless of measure count. Overflow scrolls internally. This is
   what makes 58 counties survivable.
2. **Scan, then drill.** The row shows only what distinguishes one
   measure from another. Everything else lives in the existing modal —
   which already exists and should be reused, not rebuilt.
3. **Scope is stated, never implied.** "San Bernardino County · 20
   measures · checked 27 Aug" sits in the header, and the widget never
   says "your ballot."
4. **One control, not a control panel.** A single county `select` per
   USWDS. No combo box, no address field, no filter stack.
5. **Differentiation earns its pixels.** Vote threshold is the most
   decision-relevant attribute the data has and it varies meaningfully
   (50% / 55% / two-thirds) — it stays. Topic does not exist for these
   records and must not be faked.

## 4. Proposed structure

```
┌───────────────────────────────────────────────────────────────┐
│  LOCAL MEASURES        [ San Bernardino County  ▾ ]           │  header
│  20 measures · checked 27 Aug · official county records       │
├───────────────────────────────────────────────────────────────┤
│  A   Upland Unified School District      Bond          55%    │
│  B   Beaumont Unified School District    Bond          55%    │  scroll
│  C   Barstow Community College District  Bond          55%    │  region
│  D   City of Needles          Charter Amendment    majority   │  (fixed
│  E   City of Highland         Sales Tax            majority   │  height)
│  …                                                            │
├───────────────────────────────────────────────────────────────┤
│  Thresholds from the county election office · Source ↗        │  footer
└───────────────────────────────────────────────────────────────┘
```

**Row anatomy** (single line, ~40px):
`letter chip` · `jurisdiction` (primary) · `measure type` (secondary) ·
`threshold` (right-aligned, semantic weight) · optional document
indicator. The whole row is a button opening the existing measure
modal.

**County control.** A native `<select>` listing captured counties, with
uncaptured target counties shown disabled as "not yet captured" — which
is honest about coverage *and* signals the roadmap. At 58 counties the
same control still works; USWDS would only add a combo box above 15,
and currently advises against it.

**Threshold is the one place to spend color.** Two-thirds is
meaningfully harder to pass than a simple majority. A muted amber for
supermajority, neutral for majority, distinct for 55% — semantic, not
decorative, and separate from the site's gold accent.

## 5. The document indicator (phase 2)

Each measure has up to **nine official documents**; the current 20 have
88. A compact nine-slot indicator per row shows what a voter can
actually read today — filled versus empty — in about 40px. It is the
single most differentiated thing this data offers, and no comparable
tool has it, because no comparable tool captures the documents.

**Blocked on schema.** Documents are not in the database; only one
`pdf_url` is. This needs the `measure_documents` table already
recommended in the opportunity register. The row design must reserve
the slot; the indicator ships when the table does.

## 6. Scaling path

| Scale | Control | Body |
|---|---|---|
| 1–5 counties (now → LA/OC/SD/Riverside) | `select` | Fixed-height scroll list |
| 6–58 counties | Same `select`, grouped by region | Same, plus a jurisdiction-type filter if rows exceed ~150 |
| District data ever available | Address lookup replaces the county select | Same rows, pre-filtered |

Nothing in the row design changes across these. Only the scope control does.

## 7. Explicitly rejected

- **Address lookup now.** The data cannot support it, and a wrong
  personalized ballot is worse than an honestly scoped county list.
- **Combo box / autocomplete county picker.** USWDS advises against it
  on accessibility grounds, and 5–58 options do not need it.
- **Keeping cards, just smaller.** Shrinking the wrong form yields a
  cramped version of the wrong form.
- **Topic chips.** These records have no topic; inventing one from
  "Bond Measure" produced the Education misclassification already
  documented in KNOWN_ISSUES #14.
- **A second carousel.** Carousels hide content behind interaction and
  are poor for scanning; the statewide one survives because four items
  fit.

## 8. Implementation phases

1. **Replace the band body with the fixed-height list** and add the
   county `select`. Reuses `viewMeasure()` for detail. No schema work.
2. **Threshold semantics** — plain-language labels with a semantic
   weight, plus the existing provenance caveat.
3. **`measure_documents` table** → the nine-slot indicator, and an
   official-documents section in the modal.
4. **Jurisdiction-type filter**, only once row counts justify it.

## 9. Implementation update — compact card variant

The implemented source keeps the card as the cross-context medium, but reduces each
local card from 247px in the live baseline to a fixed 120px. The band uses the
same three/two/one-card responsive breakpoints and track-position helper as the
statewide carousel. It advances by one visible page and reports a compact range
(`1–3 of 20`) instead of rendering a dot for every possible position; this
avoids a 100+ dot control when Los Angeles arrives.

Built in this variant:

- a native county `select`, with Los Angeles, Orange, San Diego, and Riverside
  visible but disabled as “not yet captured”;
- the existing county-scoped/non-address-specific scope sentence unchanged;
- 120px keyboard-operable cards containing measure designation, jurisdiction,
  shortened type, official threshold, and optional historical context;
- distinct non-gold threshold treatments for majority, 55%, and two-thirds;
- source attribution and official links removed from the repeated card surface
  but retained in the existing measure modal;
- a hand-reviewed registrar-description → CEDA-category crosswalk, computed at
  build time within the source-exact county and excluding registrar rows;
- suppression for samples below five and an explicit null mapping for Local
  Transportation Improvement Program.

The copied production database produced historical context on 19 of the 20 San
Bernardino cards. The reviewed cohorts remain 90 GO bonds (60 passed, since
1998), 71 ordinances (40, 1998), 38 charter amendments (28, 1998), 31 sales
taxes (17, 2000), 16 transient-occupancy taxes (12, 2002), and 16 property taxes
(3, 1998). Two CEDA rows spell the county `SAN BERNADINO`; context aggregation
uses the source-exact county key so those rows do not silently change the
reviewed 90-row bond cohort after display-name correction.

Scratch browser comparison measured the full local band at 328px versus 1,346px
for the live accordion baseline. The four statewide cards retained identical
text and 195.39px heights. Desktop and mobile local bands had no horizontal
overflow, card Enter activation opened the existing modal, disabled and empty
county states rendered correctly, and no page errors occurred. External CDN
requests were blocked by the verification sandbox, so DuckDB logged its existing
offline initialization warning; that did not affect static measure loading or
the widget.

The 88-document indicator remains deferred: the documents still are not in the
database, so this implementation does not infer or expose document-role counts.
Verification used a database copy and an explicit scratch output path. No live
database or deployed site artifact was written or regenerated.

## Sources

- [Voter's Edge California / MapLight](https://www.maplight.org/post/voter-s-edge-california-launches-to-guide-voters-and-fight-misinformation)
- [CalMatters 2024 Voter Guide — collecting from all 58 counties](https://calmatters.org/inside-the-newsroom/2024/10/elevating-the-calmatters-2024-voter-guide/)
- [BallotReady Ballot Engine](https://organizations.ballotready.org/ballot-engine)
- [USWDS combo box guidance](https://designsystem.digital.gov/components/combo-box/)
- [Ballotpedia sample ballot lookup](https://ballotpedia.org/Sample_ballot_lookup_tools)
