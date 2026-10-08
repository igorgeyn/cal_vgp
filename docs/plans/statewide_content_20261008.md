# Statewide reader content — October 8, 2026

Status: reviewed and verified release candidate; publication receipt pending.

## What needed changing

The screenshot shows the earlier four-measure carousel. Direct requests to
https://cal-vgp.igorgeyn.com/ on October 8 matched the published release's HTML
and JSON hashes and already contained the 14 qualified November propositions.
We have not established why the screenshot differs. The real current gap was
substantive: most new measures had only a description and source links, with
Research suppressed and no current campaign finance.

The current SOS list and voter guide were captured again on October 8. The
November slate remains propositions 1–5 and 37–45. ACA 13 remains withdrawn.
The SOS's March and November 2028 assignments are shown separately; they do
not inflate the count of November 2026 measures.

## Reader components

All 14 propositions receive the same source-backed components in the explorer
and their individual pages:

- Clear proposition designation, concise descriptive card title, reviewed topic,
  official description, election date, source and capture date.
- Main: qualification route, YES/NO meanings, official summary, links to the
  analysis, arguments/rebuttals, proposed law and printable guide.
- Research: fiscal estimate and expandable Legislative Analyst background,
  proposal and fiscal effects; equally presented attributed arguments for and
  against; submitted supporter/opponent lists with a non-exhaustiveness note.
- Finance: SOS support/opposition contribution totals and committees through
  October 6; FPPC contributor lists by committee, updated October 6; explicit
  missing-data and reporting-scope explanations.
- Related statewide history: text similarity restricted to historical statewide
  records, linked by integer ID. These are reading suggestions, not a
  representative sample or a forecast. No selected-sample pass-rate is displayed.

Finance timelines, donor concentration and sectors are not calculated from the
snapshot. Historical finance remains a separate receipt-based dataset. We do
not add committee lists or money across propositions; transfers and committees
working on multiple measures would make that misleading. No-committee states
are unknown, not zero. Prop 39's SOS opposition rows differ from its stated total
by $1; the stated total is retained with a note. A malformed FPPC amount
`$2,000,0000` is retained as source evidence and displayed as needing verification.
Normal currency whitespace is accepted without suppressing the amount.

## Evidence and reproducibility

Versioned evidence lives in
`scraper/tests/fixtures/statewide/20261008_content/`: 73 captured HTML responses,
their URLs, timestamps, sizes and SHA-256 hashes, plus the reviewed identity/title
mapping. Source pages comprise the qualified list, four guide pages for each
proposition, the SOS finance index and 14 finance pages, and FPPC contributor lists.
PDF links come from each guide's navigation; this work does not claim to have
downloaded or independently checked every linked PDF.

`scraper/scripts/build_statewide_content.py` reproduces
`scraper/src/website/data/statewide_2026.json` offline. The shared renderer escapes
source text and validates links. Projection requires the exact accepted integer
ID, canonical identity, proposition number and source URL. It does not rewrite
the measure or finance databases or erase legacy editorial fields.

The old embedding cache is keyed by proposition names reused across years.
Current statewide comparisons therefore re-embed a bounded historical statewide
corpus and retain exact integer identities. Local comparisons and historical
finance are left on their established paths.

Scratch evidence: `scraper/data/statewide_recon/20261008_content/`.
Candidate builds use a read-only production database backup, real finance inputs
and the offline embedding model. `build.json` records unchanged input hashes.
The corrected 83-case focused suite passes. All 14 propositions pass Main,
Research, Finance, expanded content, keyboard, carousel and standalone-page
checks at 1440, 390 and 320 pixels. Topic search is exercised too. Full preservation
keeps all 49 county records, withdrawn ACA 13, production databases and 12,358
unrelated measure pages unchanged. Only the known 129 generated legacy export
timestamps differ outside the 14 current content projections.

Claude's initial read-only review was READY WITH CONDITIONS; its focused follow-up
is READY. The [review and Codex dispositions](statewide_content_review_20261008.md)
record donor-name/attribution corrections, separate links for grouped contributors,
stronger cross-source finance wording, topic search, removal of selected-sample
outcome statistics and validation before standalone page writes. All 195 FPPC
donor amounts/ranks/sides remain unchanged. Earlier diagnostic failures remain
separate rather than being relabelled as passing results.

The final bundle is `recovery-build-corrected/site/` in the scratch directory.
Its frozen-input strict rebuild uses the already archived data/model and the new
code/source package. The additive private recovery archive restored successfully:
123 files, 8,202,122 bytes, SHA-256
`f8d55e8da319122cae7226360a771f2058eb328fd1acbfaba7998ef5f0427a1b`.
All 271 composed workspace inputs and 12,382 public files match their manifests.
It depends on the October 3 base and earlier October 8 recovery update; keep all
three archives. Existing archived production databases remain current.

## Maintenance and remaining scope

Refresh this package by capturing a new dated set, reviewing source changes,
rebuilding the package, running source/identity and browser checks, and publishing
the paired site outputs. Captured October 8 is not an automatic daily refresh.
The existing county capture-health, election-status/results transition and
operations reviews remain open. This task changes priority to statewide reader
completeness, as requested; it does not complete those other review batches.
