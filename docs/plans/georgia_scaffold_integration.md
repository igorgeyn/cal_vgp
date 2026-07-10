# Georgia's API scaffold: review + integration roadmap

> Snapshot: **2026-07-09**. Written after a full review of the
> `perfunctory_api_code` commit (preserved verbatim on branch
> [`georgia/api-scaffold`](https://github.com/igorgeyn/cal_vgp/tree/georgia/api-scaffold),
> reverted from `main` in `aa71735`). Audience: Igor and Georgia
> both — this is the constructive version of the review, plus a
> concrete map of what integrates where.

## What the scaffold is

A research-grade relational design for California ballot measures:
a 10-table PostgreSQL schema (measures, county-level outcomes,
campaign finance, endorsements, county demographics, rolling-window
county×domain profiles) with a FastAPI query layer, aimed at an R
prediction model answering *"in county X, how likely is a measure
on topic Z in the next T years — and would it pass?"*

**The strong part is the intellectual scaffolding.** This is a
political scientist's schema: Gerber (1999) outsider-money
variables, Bowler & Donovan roll-off rates as voter-fatigue
proxies, Lupia (1994) elite cues motivating the endorsements table,
Matsusaka (2004) fiscal federalism behind the county profiles,
CPI-adjusted dollars beside nominals, data-confidence and
source-credibility ratings built in, and a seeded table of
structural breaks (1911 direct democracy, 1974 FPPC, Prop 13,
Citizens United) at which any longitudinal model should segment.
That thinking is sound and several pieces of it fill real gaps in
this project.

**The limiting part is that it's a specification wearing the
costume of an application.** It was never executed (committed under
a filename the entry point can't start from), its endpoints read
from tables no code ever populates (there is no ingestion path),
and it assumes a fresh PostgreSQL world parallel to this repo's
actual architecture: SQLite (`ballot_measures.db`, 12,365 measures),
a static site on GitHub Pages, an existing FastAPI server
(`scraper/src/api/server.py`) wired to real data, and a v2/v3
campaign-finance layer with dedup gates and a four-layer
verification stack. Code-level nits for whenever the branch is
iterated on: the `float(x) if x else None` pattern appears ~30
times and silently turns legitimate zeros into nulls (this repo has
been bitten by exactly this bug family before — see
`docs/LESSONS_LEARNED.md` on falsy-vs-null); unused imports;
localhost dev defaults (`0.0.0.0` bind, CORS `*`, password
placeholder edited into the file rather than env-only).

**Verdict:** the schema ideas survive; the code should not merge.
Integrate by harvesting, not by running.

## Integration map

### 1. Adopt CAP as the topic taxonomy ⭐ (the flagship graft)

The project's #1 data gap: ~75% of measures classify as "Other"
because CEDA supplies no topic. The backlog fix ("LLM
classification pass") has always been missing its target taxonomy —
classify into *what?* Georgia's answer is right: the **Comparative
Agendas Project codebook** (comparativeagendas.net). ~23 major
topics, the standard in the field, interoperable with decades of
published research — which strengthens the research-audience story.

Concrete shape:
- Add a `cap_topics` reference table + `cap_primary_code`
  (optionally `cap_secondary_code`) to `ballot_measures.db`.
- Run the LLM classification pass mapping measures → CAP codes
  (closed set = tractable prompt; include CAP minor codes later if
  major-level proves insufficient).
- Unblocks the thematic-policy narrative work parked in IDEATION
  with topic classification as its stated prerequisite, and the
  Topics insights-panel revisit.

### 2. Structural-breaks reference table (cheap rider)

Tiny seeded table: break year, name, description, affected CAP
domains, citation. Makes "post-Prop-13 era" a queryable boundary
for insights panels and briefing prose instead of tribal knowledge.
Land alongside #1; near-zero cost.

### 3. County FIPS codes (cheap rider, with one carve-out)

FIPS codes per county enable unambiguous joins to NHGIS/census
demographics and other federal-keyed datasets. Take them. **Leave
the region groupings** ("Bay Area", "Sierra Nevada", …) — the
project explicitly decided to stay county-level for geography
(WORKING_LIST "Closed by decision"). FIPS = join keys, yes;
regions = UI dimension, no.

### 4. The prediction model → an export view, not a second database
   (the collaboration-shaped piece)

Georgia's real goal is the R model. The integration that respects
both her goal and this architecture: a **materialized export**, not
a parallel Postgres. A script (e.g.
`scraper/scripts/export_analysis_dataset.py`) that computes her
`county_domain_profiles` shape — n_measures / pass rate / median
margin / spending ratios / turnout per (county, CAP domain, rolling
window) — **from** `ballot_measures.db` into CSV/parquet that R
reads directly.

- She gets exactly the analysis dataset her schema specifies,
  populated with 12,365 real measures instead of an empty database.
- The repo gets zero new infrastructure: no PostgreSQL, no second
  API, no parallel truth.
- Naturally Georgia-owned work on her branch (now via PR — `main`
  requires them as of 2026-07-09), off the project's critical path.
- Gets dramatically better after #1 lands: profiles keyed on CAP
  codes need the classification pass first. Do #1 → then this.

### Explicitly not integrating

- **`CampaignFinance` table** — one-row-per-measure side totals are
  structurally naive next to the v2/v3 finance layer (attribution
  resolution, canonicalized dedup gates, Layer 1/2/3 + Phase G
  verification). The finance export for the R model should come
  from `FinanceDatabase` aggregates, not a new table.
- **The FastAPI app** — `src/api/server.py` already exists and
  speaks to real data. New query needs become endpoints there.
- **Endorsements schema** — good idea, no data source behind it.
  That's a new collection pipeline (scope decision), not an
  integration. Parked in IDEATION until someone identifies where
  endorsement data would actually come from.

## Sequencing

Nothing here jumps the queue ahead of the registrar pipeline
(Phase 1 SB scraper is the active arc). Recommended order when
capacity opens:

1. **CAP adoption + LLM classification pass** — strong candidate
   for the arc after the registrar pipeline stabilizes; fixes the
   worst data gap in the project either way.
2. **Structural breaks + FIPS** ride along with #1.
3. **Analysis-dataset export** for the R model — after #1;
   Georgia-led, PR-based, consuming exports rather than forking
   architecture.

## Pointers

- Her work, verbatim: branch `georgia/api-scaffold`.
- Backlog hook: WORKING_LIST → DATA → "Harvest Georgia's
  API-scaffold ideas" (supersede that stub with this doc).
- Repo conventions for contributions: PRs into `main` (branch
  protection, 2026-07-09), `docs/LESSONS_LEARNED.md` before
  substantive work, `pytest` from `scraper/`.
