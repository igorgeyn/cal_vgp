# Codex: prepare the Upcoming Ballot Measures section for local measures

> **For Codex:** A build task on the live site generator. The
> "Upcoming 2026 Ballot Measures" section currently shows 22
> statewide measures. Twenty **local** San Bernardino measures are
> about to be loaded, and four more counties follow. Restructure the
> section so it absorbs them well — and keeps working when it is
> 150+ measures across five counties.
>
> Self-contained; assume no session memory. Facts below were verified
> against the repo on 2026-08-27, but verify anything load-bearing
> yourself.

---

## 1. Orientation — read these first

**Project.** CalBallot (`https://calballot.com`): a searchable
database of California ballot measures. Python pipeline → SQLite
(`scraper/data/ballot_measures.db`, 12,365 measures) → **static site
generator** → GitHub Pages. No server, no framework, no build step.
Start with `/CLAUDE.md` (rules of engagement, hard-won constraints),
then `docs/WORKING_LIST.md` for current state.

**The generator is one large Python file that emits a complete
HTML+CSS+JS document as an f-string.** `scraper/src/website/generator.py`
is ~14k lines; the browser-side JavaScript lives inside it as
template text, so `{{` and `}}` are escaped braces. Read enough of
the surrounding code to match its conventions before editing —
this file has bitten the project before (see the `valid_fields`
entry in `docs/LESSONS_LEARNED.md`, where an omitted `id` silently
broke the Finance modal for all 12,365 measures).

**The specific code path**, in the order it runs:

| What | Where |
|---|---|
| Section markup | `generator.py` ~line 1211, `<!-- Upcoming 2026 Ballot Measures Section -->` |
| Which measures qualify | `selectHeroMeasures()` ~8572 |
| Carousel render + paging | `displayHero()` ~9756, plus `updateHeroCarousel*` / `heroCarousel*` helpers |
| Card markup | `createCard(measure, featured, featuredReason, isHero)` ~12948 |
| Supporting helpers | `isPendingMeasure()`, `getDisplayMeasureId()`, `buildDisplayTitle()`, `isMetadataSummary()`, `getCleanTitle()` |
| Field prep for the JSON | `_prepare_measures_data()` in the same file |
| CLI entry | `scraper/scripts/generate_site.py` (calls `generate_prepared(...)`) |

Also read `docs/plans/registrar_sb_review_and_integration.md` §B —
the ranked opportunity register for this data, including the design
rule in §4 below.

---

## 2. What was already verified (confirm, don't redo)

- **Ingestion already works.** `selectHeroMeasures()` filters on
  `year === 2026` and nothing else, so local measures appear as soon
  as they exist. `isPendingMeasure()` returns true for year ≥ 2026,
  which yields the "⏳ Upcoming" badge and correctly suppresses the
  vote bar.
- **Titles resolve cleanly.** `getDisplayMeasureId()` prefers
  `measure_letter` for county measures, so a card reads
  "Measure L: City of Needles — Bond Measure" — the 64-character
  identity hash is never displayed.
- **The fields exist in the site JSON.** `jurisdiction`,
  `county`, `measure_letter`, `vote_threshold`, `source_url`,
  `pdf_url`, `description` are all keys in the deployed
  `measures-data.json` (12,312 records). `_prepare_measures_data()`
  title-cases county, so `SAN BERNARDINO` renders "San Bernardino".

## 3. The five problems to solve

1. **Scale.** 22 statewide + 20 local = 42 cards in a carousel that
   shows 3 at a time (~14 pages of dots). Five counties could make
   it 150+. The section was designed for about six.
2. **Redundant summary.** Local measures have no `summary_text` and
   no `ballot_question`, so `createCard` falls through to
   `description` — "Bond Measure" — printed directly beneath a title
   already ending in "— Bond Measure".
3. **Raw system string in the meta row.** It will print
   `SB_County_Registrar` as the source.
4. **No jurisdiction or topic signal.** Local measures carry no
   topic at all, so twenty cards look nearly identical; the
   jurisdiction is buried inside the title.
5. **Undifferentiated cards** generally — nothing conveys that this
   is a *Needles* measure needing a *two-thirds* vote.

## 4. The task

Implement the **split-band** approach: keep the statewide carousel
essentially as it is, and add a local-measures band beneath it,
grouped by county, with cards that carry the fields local measures
actually have.

Requirements:

- **Works at 20 and at 150+.** Grouping by county must not become
  another unnavigable carousel when Los Angeles lands. Choose the
  pattern (grouped sections, per-county collapse, a lightweight
  filter) and justify it; a full geography picker is out of scope
  but the structure should not preclude one.
- **Statewide behavior must not regress.** The existing 22 measures
  keep their current presentation.
- **Local card content** should use what exists: measure letter,
  jurisdiction, measure type, **vote threshold** (authoritative from
  the county — 50%+1, 55% for Prop-39 school bonds, two-thirds),
  and a link to the official county page. Suppress the description
  when it merely repeats the title. Show a human source label, not
  `SB_County_Registrar`.
- **Empty-state honesty.** Before the load, there are zero local
  measures. The band must render sensibly with none, and must not
  claim coverage it does not have — this is San Bernardino only, not
  "your ballot."
- **The vote threshold is worth surfacing** and connects to the
  site's existing Rules insight panel. Note `docs/KNOWN_ISSUES.md`
  #1: CEDA-derived thresholds elsewhere in the corpus are
  unreliable, but registrar thresholds are authoritative — do not
  blur that distinction if you display it anywhere else.

**Scoping decision to make and state explicitly:** each local
measure has up to **nine official documents** (notice, resolution,
full text, impartial analysis, tax rate statement, arguments and
rebuttals both ways) — 88 for the current 20 measures. **Those
documents are NOT in the database.** Only a single `pdf_url` (the
full-text role) is. A `measure_documents` table is the recommended
home for them (see the opportunity register: *presence is not
content* — never stuff document URLs into `pro_arguments` or other
prose fields). Decide whether this task should (a) ship without
document counts and leave a clean slot in the card for them, or
(b) include the schema work. **Recommendation is (a)** — keep this
change to the presentation layer. If you disagree, argue it.

## 5. How to verify without touching production

The SB measures are **not** in the live database. To see real cards:

```
python scraper/scripts/parse_registrar_snapshots.py \
    --county sb --election-date 2026-11-03 --env dev
python scraper/scripts/load_registrar_measures.py \
    scraper/data/registrar_normalized/sb_2026-11-03.jsonl \
    --db <A COPY of ballot_measures.db> --commit
```

Then generate the site against that copy into a scratch directory
and inspect the result. `scraper/src/scrapers/registrar/{parser,loader}.py`
document their own CLIs; the loader is dry-run by default and backs
up before writing.

**Never** write to `scraper/data/ballot_measures.db`, and **never**
regenerate or commit `index.html`, `measures-data.json`, or
`scraper/index.html` — deployed artifact regeneration is a separate
reviewed step (`docs/plans/site_artifact_publication_decision.md`).

## 6. Constraints

- Static output only: generated HTML/CSS/JS, no framework, no
  backend, no external requests at runtime.
- The generator dual-writes a root pair and a gitignored local
  mirror; publishing goes through `generate_prepared(...,
  output_paths=[...])` and `scraper/tests/test_website_output_contract.py`
  asserts the copies are byte-identical. Keep that contract.
- CSS lives in the same generated stylesheet as every other panel.
  **Scope new rules under a parent selector** — class collisions
  between panels have broken this site before (LESSONS_LEARNED,
  2026-05-20 Finance modal vs Insights).
- Existing tests must pass: `python -m pytest tests/ -q -k "registrar
  or website_output"` from `scraper/` (185 green as of `ae4a79b`).
  The wider legacy suite has 18 known pre-existing failures (string
  DB paths, Statewide county default) — not yours.
- Never `git add .`; Windows-compatible code; `pytest` runs from
  `scraper/` with `from src.xxx` imports.

## 7. Deliverables

1. The generator changes.
2. A short note in `docs/plans/` recording the structure you chose,
   why, how it scales to five counties, and what a future geography
   filter would need.
3. Tests where the logic is testable (selection/grouping/labeling is
   Python-side or extractable; the carousel is not).
4. A verification report: cards rendered against a loaded database
   copy, what a local card shows, confirmation that the statewide
   band is unchanged, and the record counts before and after.

State at the end what you verified, what you assumed, and anything
that needs Igor's decision.
