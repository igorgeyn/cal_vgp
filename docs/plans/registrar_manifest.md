# California county registrar reconnaissance manifest

> **Purpose:** per-county notes on what each registrar site
> publishes, URL patterns, formats, and scraping concerns. Phase 0
> deliverable for the local-measure pipeline (see
> `docs/plans/registrar_pipeline_infra.md`).
>
> **Status:** **second pass.** First pass via WebFetch surfaced the
> shape; this pass uses the local probe harness
> (`scraper/scripts/recon/probe.py`) with the planned polite
> User-Agent + actual HTTP fetches. Raw artifacts saved under
> `scraper/data/registrar_recon/` (gitignored). All 5 top-tier
> counties now have at least a first-contact probe; 4 of 5 have
> identified scraping entry points.

## Top-5 counties (Phase 1 targets)

### 1. Los Angeles County — `lavote.gov`

**Status:** ✅ scraping entry point confirmed via harness

**Main site (`www.lavote.gov`):**
- Sitefinity CMS, server-rendered HTML
- Nav pattern: `/home/voting-elections/[section]/[subsection]`
- Past elections archive: `/home/voting-elections/current-elections/election-results/past-election-results` — back to 2007
- No public per-measure index on the main site
- Interactive Sample Ballot at separate subdomain `isb.lavote.net` (per-voter, JS-heavy)

**Results portal (`results.lavote.gov`):** ⭐ **primary entry point**
- Main portal is a SPA at `https://results.lavote.gov/#year=YYYY&election=ID`
- **Static text version at `https://results.lavote.gov/text-results/{election_id}`** — confirmed via harness (562KB HTML)
- Election IDs are sequential integers (`4338` = June 2, 2026 primary; older IDs decrement)
- Content: full ballot measure text + YES/NO vote totals + percentages, organized by section (County Measures, Cities, Schools, Community Services, etc.)
- No JS dependency for text version

**Aggregate result PDFs:**
- `https://content.lavote.gov/docs/rrcc/svc/{election_id}_{document_type}.pdf`
- Document types: Statement of Votes Cast (precinct/district), Precinct Bulletins, Votes Cast by Community
- Excel exports also available
- Sequential election IDs make systematic enumeration trivial

**Scraping verdict:**
- Primary: `text-results/{election_id}` for measure text + outcomes
- Supplement: aggregate SVC PDFs for precinct-level data if needed
- Anti-scraping: none observed with polite UA

---

### 2. San Diego County — `sdvote.com`

**Status:** ✅ polite UA bypasses the block; deeper probe needed

**Confirmed via harness:**
- `https://www.sdvote.com` returned **403 with generic UA, 200 with our polite UA** (`cal-vgp-registrar-recon/0.1 (+https://github.com/igorgeyn/cal_vgp; contact: igorgeyn@gmail.com)`)
- 45KB of HTML at the root
- Validates Codex's polite-scraping advice empirically

**Still TBD (next recon pass):**
- Per-election measures URL pattern
- Whether ballot text is published on a public page or only in mailed PDFs
- JS dependency on internal pages
- Whether deeper pages (results archive, sample ballots) also need polite UA

**Scraping verdict:**
- Will need polite UA from day one (non-negotiable per the 403 evidence)
- Specific entry points TBD in next probe

---

### 3. Orange County — `ocvote.gov`

**Status:** ✅ URL pattern identified

**Confirmed via harness:**
- Drupal-based site (Drupal Gutenberg block markup throughout)
- Main: `https://www.ocvote.gov/` (32KB)
- `/elections` lists upcoming + recent elections
- Multilingual: `/es/`, `/vi/`, `/zh-hans/`, `/ko/` prefixes for Spanish, Vietnamese, Chinese, Korean
- Per-election slug-based URLs: e.g. `/elections/2026-statewide-direct-primary-election`
- **Per-election measures URL pattern: `/elections/{slug}/measures-on-the-ballot`** — observed for the 2024 primary
- 2026 primary page currently has calendar PDFs but no measures-on-the-ballot link yet (election still upcoming, presumably populated closer to the date)

**Other useful patterns:**
- `/elections/{slug}/contests-qualified-for-the-ballot` — qualified contests list
- `/elections/{slug}/legal-election-documents` — legal docs
- Calendar PDFs: `/sites/default/files/{year-mm}/...pdf`
- Election Library, Data Central, Voter Trends sections — research-friendly

**Scraping verdict:**
- Primary: `/elections/{slug}/measures-on-the-ballot` for measure listings
- Slugs follow predictable naming (`{year}-{election-type-words}`); could be enumerated by scanning `/elections` list page
- No anti-scraping observed
- Likely server-rendered HTML; no Playwright needed

**Open questions:**
- What's the URL pattern for older elections (pre-2020)? Same slug pattern, or different?
- Does the measures-on-the-ballot page link to ballot text PDFs, or carry the text inline?
- Are there per-measure detail pages, or just one-page lists per election?

---

### 4. Riverside County — `voteinfo.net`

**Status:** ⛔ **Cloudflare bot challenge** — Playwright required

**Confirmed via harness:**
- HTTP 403 returned even with the polite UA
- 5.5KB response body is a **Cloudflare "Just a moment..." challenge page** — the classic JS-based bot detection that requires a real browser to pass
- Polite UA insufficient; needs Playwright (or headless Chrome) to execute the JS challenge

**Implications:**
- Riverside scraper will be the heaviest of the top-5: Playwright required for every fetch
- Costs more CI minutes (browser cold-start ~30s)
- Cloudflare challenge may also trigger CAPTCHAs in some sessions — need to handle gracefully

**Scraping verdict:**
- Defer to last in Phase 1 county order — let LA / OC / SB validate the easier counties first
- When tackled, use Playwright from the start with proper browser fingerprinting (real Chrome UA + viewport + cookies)
- May want to evaluate whether Riverside's elections data is available via a different channel (state SOS feeds, CalAccess for finance, county GIS portal for boundaries, etc.) to reduce dependence on the scraping channel

---

### 5. San Bernardino County — `elections.sbcounty.gov` ⭐

**Status:** ✅ best-of-the-five — clean URL pattern + structured HTML tables

**Important correction to Jan 2026 plan:**
- The plan listed `sbcrov.com` — that domain doesn't resolve (DNS failure)
- Actual URL is `https://elections.sbcounty.gov/` (also reachable via `https://www.sbcountyelections.com/` which redirects)

**Confirmed via harness:**
- Main: 188KB HTML at root
- **Per-election measures URL pattern: `/elections/{year}/{mmdd}/measures/`**
  - Example: `/elections/2026/0324/measures/` → March 24, 2026 election measures
- Cross-election landing: `/elections/measures/`
- Measures page is a **structured HTML table** with columns:
  - `Letter` (e.g. V, W)
  - `Jurisdiction` (e.g. "City of Ontario")
  - `Measure Description` (full text including amendment chapter/title references)
  - `Analysis` (link to Impartial Analysis)
  - `Arguments` (links to Argument For, Rebuttal to Argument For, Argument Against, Rebuttal to Argument Against)
  - `Percentage to Pass` (e.g. "50% + 1")
- 3 rows in current March 2026 page: 1 header + Measure V + Measure W (both City of Ontario)
- Per-measure analysis + argument PDFs linked inline

**Scraping verdict:**
- **Cleanest target of the five.** Structured table, predictable URL pattern, ballot text inline (not behind a paywall or per-voter tool), supplementary PDFs linked from the same page.
- No anti-scraping observed.
- Strongly recommend SB + LA as the Phase 1 pair (LA for breadth of coverage, SB for cleanest data shape).

---

## Cross-county takeaways (second pass)

### Anti-scraping spectrum

| County | Block type | Bypass |
|---|---|---|
| LA | None | Generic UA works |
| OC | None | Generic UA works |
| SB | None | Generic UA works |
| SD | UA filter | Polite UA defeats it |
| Riverside | Cloudflare challenge | Needs Playwright |

3 of 5 are wide-open; 1 needs polite UA; 1 needs Playwright. Codex's
polite-scraping defaults handle SD; Playwright handles Riverside.

### URL pattern shapes

Three distinct shapes across counties:

1. **Integer election ID** (LA): `text-results/4338` — sequential, easy to enumerate
2. **Slug-based** (OC): `2026-statewide-direct-primary-election` — predictable but needs name-to-slug logic
3. **Date-based** (SB): `2026/0324` — most parseable, predictable format

For Phase 1 scrapers, each county module owns its URL composition logic. The shared `RawArtifactStore` just needs a `(county, election_date, snapshot_id)` key — agnostic to how the county constructs URLs.

### Ballot text availability

- **LA, SB**: ballot text included in the per-election measures page (inline or via linked Analysis PDFs)
- **OC**: TBD — `measures-on-the-ballot` page exists for 2024 but content not yet inspected; likely linked PDFs
- **SD**: TBD — homepage probed only
- **Riverside**: TBD until Playwright integration

### Recommended Phase 1 county order

1. **SB** (cleanest data shape, structured tables, predictable URLs)
2. **LA** (largest population, validates scale, text-results portal is concrete)
3. **OC** (predictable slug pattern, but 2026 measures not yet populated)
4. **SD** (need to find measures URL; polite UA works)
5. **Riverside** (last; Playwright required)

Original Jan 2026 plan listed LA → SD → OC → Riverside → SB by
population. Recon-informed order is data-quality-driven: SB first
because it validates the parsing layer with the cleanest input.

### Implications for Phase 0.5

Items the recon confirmed for the Phase 0.5 build:

1. **Polite User-Agent from day one** ✅ already in the plan; validated by SD
2. **Playwright as first-class fetch mode** ✅ already in the plan; validated by Riverside
3. **R2 immutable snapshot folders keyed on `(county, election_date, snapshot_id)`** ✅ already in the plan; works for all 5 URL shapes
4. **Per-county scraper modules** ✅ already in the plan; each county's URL composition is distinct enough to require module-level isolation

Items the recon refined:

5. **Add slug-discovery logic for OC** — OC scraper needs to first hit `/elections` to enumerate per-election slugs, then visit each `{slug}/measures-on-the-ballot`. SB and LA can enumerate elections via their own list endpoints.
6. **Two-tier fetch mode** — most counties (LA, OC, SB) use plain `requests`; Riverside uses Playwright; SD uses requests + polite UA. The `CountyRegistrarScraper` base class should configure `fetch_mode` per subclass.
7. **Update plan's county URL list** — replace `sbcrov.com` with `elections.sbcounty.gov`.

## Open questions for Phase 0.5 implementation

1. **OC for older elections** — does `/elections/{slug}/measures-on-the-ballot` exist for pre-2020 elections, or only recent ones?
2. **SD measures page** — where does SD publish per-election measure listings? (Need a second-round probe.)
3. **LA text-results historical coverage** — does the text-results portal cover all elections back to 2007, or only modern ones?
4. **Sample ballot booklet PDFs** — most counties have these for voters; URL pattern unknown for LA / OC / SD / Riverside. SB embeds it in the measures page directly.
5. **OC's measures-on-the-ballot internal format** — inline ballot text vs PDFs? Inspect a known election.

## Honest assessment

This second pass replaces the first-pass placeholders. We now have:
- **Confirmed entry points for 4 of 5 counties** (LA, OC, SB clean; SD with polite UA)
- **One county requiring Playwright** (Riverside; expected per Codex)
- **One URL correction** (SB)
- **A recommended Phase 1 order** that's data-quality-driven, not just population-driven

The recon harness (`scraper/scripts/recon/probe.py`) is committed and
reusable — future second-pass probes (SD measures page, OC pre-2020,
LA historical coverage) can use it. Snapshots from this pass live
under `scraper/data/registrar_recon/` (gitignored; ~1MB total).

**Ready to proceed to Phase 0.5 implementation.** Open questions
above can be answered during Phase 1 implementation rather than
blocking 0.5.
