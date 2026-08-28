# Codex: compact card variant for the local measures band

> **For Codex:** A focused change to a **live** site surface. The
> local-measures band you built in `d9390d6` is correct but too tall;
> Igor wants it roughly the height of the statewide carousel. Keep the
> card as the medium — this is a density variant, not a new component.
>
> Self-contained; assume no session memory. Facts verified against the
> repo 2026-08-27.

---

## 1. Where things stand

The registrar pipeline is **live in production** as of `2afcba9`:
20 San Bernardino County measures for the November 3, 2026 election
are on calballot.com, in the "Upcoming 2026 Ballot Measures" section,
below the statewide carousel.

The band renders per-county accordions of full-size cards. Each card
carries measure letter, an UPCOMING badge, jurisdiction, a measure-type
chip, "Official vote threshold" with a plain-language value, the source
line "San Bernardino County Registrar of Voters", and an "Official
county page" link. Roughly 230px tall, twelve shown, "Show all 20".

**The problem:** it dwarfs the statewide carousel above it, and Los
Angeles could bring 100+ measures.

Design rationale and the rejected alternatives are in
[`docs/plans/local_measures_widget_redesign.md`](../plans/local_measures_widget_redesign.md).
Read it — particularly why a plain `<select>` beats a combo box
(USWDS), and why address lookup is out of scope (the data is
county-scoped, not precinct-scoped, so the page must never imply
"your ballot").

## 2. What to build

**A compact card variant of the same component**, in a container that
matches the statewide band.

### Card anatomy (target ~105–120px, down from ~230px)

```
┌────────────────────────────────────┐
│ MEASURE A              55%         │  letter (small caps) + threshold
│ Upland Unified School District     │  jurisdiction — primary, bold
│ [ Bond ]                           │  short type chip
│ 90 in SB since 1998 · 67% passed   │  historical context (see §3)
└────────────────────────────────────┘
```

Keep: measure letter, jurisdiction, measure type, vote threshold.
**Remove from the card** (move to the modal, which already opens on
click): the "San Bernardino County Registrar of Voters" source line and
the "Official county page" link. They repeat on every card and cost two
lines each.

The UPCOMING badge is redundant inside a section already titled
"Upcoming" — drop it from the compact card unless you disagree.

**Threshold gets the one spot of semantic color**, because it is the
most decision-relevant attribute and it genuinely varies: two-thirds
should read as harder than a simple majority. Keep the existing
plain-language phrasing ("Simple majority (50% + 1)", "55%",
"Two-thirds (66.67%)") but consider shortening for the tighter card.
Semantic color must be distinct from the site's gold accent.

Shorten type labels for the narrower card: "Transactions and Use Tax
Measure" → "Sales tax", "Municipal Code Amendment" → "Municipal code",
"Local Transportation Improvement Program" → "Transportation".

### Container

Use a **carousel matching the statewide band**, for visual parity.
Igor's call, and at N=20 it is defensible. Reuse the existing hero
carousel machinery rather than writing a second implementation.

Add a **county `<select>`** in the band header. Counties with no
captured data appear as **disabled** options reading "not yet
captured" — honest about coverage and it signals the roadmap. Today
only San Bernardino has data; the other four recon'd counties (Los
Angeles, Orange, San Diego, Riverside) should appear disabled.

Keep the existing scope line verbatim — it is doing real work:

> Currently captured: San Bernardino County. These are county-scoped
> official records, not a complete address-specific ballot.

Keep the existing threshold-provenance footnote (the KNOWN_ISSUES #1
caveat about derived historical thresholds).

**Do not change the statewide carousel.** It currently shows 4 active
measures and must render identically after this change.

## 3. The historical-context line

This is the piece Igor specifically wants: cards as a **cross-context
medium** connecting current measures to the archive.

Jurisdiction-name linking does **not** work — historical CEDA rows
store `jurisdiction` as numeric type codes ("1", "2", "3"), and the
city name is buried in `ballot_question` prose.

**Measure type does work.** A reviewed crosswalk maps registrar
vocabulary to CEDA's `category_type`. Verified counts, San Bernardino,
excluding registrar rows:

| Registrar `description` | CEDA `category_type` | n | passed | since |
|---|---|---:|---:|---:|
| Bond Measure | GO Bond | 90 | 60 | 1998 |
| Municipal Code Amendment | Ordinance | 71 | 40 | 1998 |
| Charter Amendment | Charter Amendment | 38 | 28 | 1998 |
| Transactions and Use Tax Measure | Sales Tax | 31 | 17 | 2000 |
| Transient Occupancy Tax | *(exact match)* | 16 | 12 | 2002 |
| Special Parcel Tax | Property Tax | 16 | 3 | 1998 |
| Local Transportation Improvement Program | **unmapped** | — | — | — |

That covers **19 of 20** measures. Leave the last one unmapped rather
than guessing; a null context line is correct and the card should
simply omit it.

Implementation notes:

- Put the crosswalk in a small named module or constant with a comment
  explaining it is hand-curated and reviewed, following the precedent
  of `src/finance/donor_aliases.py` and `donor_sectors.py`.
- Compute at **build time** in `generate_site.py`, attached to the
  measure dict, following the existing `historical_context` pattern —
  not client-side over 12k records.
- Scope counts to the **same county** and exclude registrar rows, so a
  measure is never counted as its own precedent.
- Suppress the line when n < 5. Small-n percentages mislead.
- Phrase it as observation, not prediction: "90 in SB since 1998 · 67%
  passed". Never "likely to pass".
- This is deterministic, unlike the embedding-based
  `historical_context`, which stays suppressed for registrar rows
  (KNOWN_ISSUES #14 — it classified a Needles "Bond Measure" as
  Education with unrelated 2002 analogs).

## 4. Constraints

- **Static output only.** Generated HTML/CSS/JS, no framework, no
  backend, no runtime external requests.
- Publishing goes through `generate_prepared(..., output_paths=[...])`;
  `scraper/tests/test_website_output_contract.py` asserts the root and
  mirror copies are byte-identical. Keep that contract.
- **Scope new CSS under a parent selector.** Panel class collisions
  have broken this site before (`docs/LESSONS_LEARNED.md`, the 2026-05
  Finance modal vs Insights collision).
- Existing tests must pass, including `test_website_upcoming.py`, which
  you wrote for the current band and will need updating rather than
  deleting.
- Cards must remain keyboard-accessible with visible focus, and the
  carousel must not trap focus.
- Mobile: the compact card must not become unreadable; drop the
  context line before the type chip if space forces a choice.
- Never `git add .`; `pytest` runs from `scraper/`; Windows-compatible.

## 5. Verification

The SB data is now in the live database, so cards render without a
special setup — but **do not write to `scraper/data/ballot_measures.db`
and do not regenerate or commit `index.html`, `measures-data.json`, or
`scraper/index.html`.** Generate to a scratch path with `--output` and
inspect there. Regenerating the deployed artifacts is a separate
reviewed publication step, as it was for the current release.

Report: the rendered compact card height vs the current ~230px, that
the statewide carousel is unchanged, that 19 of 20 cards carry a
context line, the empty/disabled-county state, and a headless run with
no page errors.

## 6. Deliverables

1. Generator changes (compact card variant, carousel container, county
   select, crosswalk + build-time context).
2. Updated `test_website_upcoming.py` plus new tests for the crosswalk
   (including the unmapped type and the n<5 suppression).
3. A short update to
   `docs/plans/local_measures_widget_redesign.md` recording what was
   built and any deviation from the plan.
4. Scratch-rendered verification as described in §5.

State what you verified, what you assumed, and anything needing Igor's
decision.
