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

---

## Bay Area forward-publication sweep (verified 2026-08-31)

This sweep tested the assumption that San Bernardino might be the only
county publishing measure records before Election Day. It used the exact
production-facing User-Agent below and kept same-host requests at least two
seconds apart:

```text
cal-vgp-registrar-scraper/0.1 (+https://github.com/igorgeyn/cal_vgp; contact: igorgeyn@gmail.com)
```

The HTTP captures were made on August 31 Pacific time (September 1 UTC in
`probe.json`) and are saved under
`scraper/data/registrar_recon/{county}/` (gitignored). Search-engine checks
mentioned below were limited to pages on the counties' official domains.

### Alameda County - `acvote.alamedacountyca.gov`

**Status:** confirmed forward publisher; strong second build candidate

**Upcoming publication (verified):**
- The official November 3, 2026 election page is live at
  `https://acvote.alamedacountyca.gov/election-information/elections?id=260`.
- On August 31, 64 days before Election Day, it linked **28 measures**:
  regional Measure RTM and Measures I through II. This directly answers the
  forward-publication question; the page is not an empty election shell.
- A representative Measure U PDF had an HTTP `Last-Modified` date of July 31,
  95 days before the election. That proves the artifact existed by July 31,
  but not necessarily that the election page linked it continuously from
  that date.

**Measure content and documents (verified):**
- `/rov_app/measures/election/260` returns an HTML fragment with all 28
  measure titles, jurisdiction groupings, full ballot questions, and required
  approval thresholds. Despite the endpoint-like URL, it is HTML, not JSON.
- The election page links one PDF per measure. The representative Measure U
  packet is a 15-page scanned PDF containing the ballot-measure submittal,
  resolution/full text, and tax-rate material. It has no extractable text
  layer and would require OCR.
- The page does not separately label or link impartial analyses, arguments,
  or rebuttals. Those roles were not found in the representative packet.
  Treat the composition of the other 27 PDFs as unverified until a build
  fixture set samples them; do not infer that every packet is identical.

**URL and enumeration (verified):**
- Election details use an opaque numeric query parameter:
  `/election-information/elections?id={election_id}`.
- IDs are not chronological (`262` is August 2026, `260` is November 2026,
  and `259` is June 2026), so do not scan integer ranges.
- The election landing page server-renders the current and previous election
  IDs and dates. Enumerate from that list, then request the selected ID.
- The measure-question application independently server-renders a select list
  and fetches `/rov_app/measures/election/{election_id}`.

**Page structure and access (verified):**
- The selected election's content and 28 PDF links are present in the initial
  HTML. JavaScript only handles selection/accordion behavior; Playwright is
  unnecessary.
- The measure-question detail is a small, server-rendered HTML fragment with
  repeated `.measureDescGroup` blocks, grouped by jurisdiction.
- The polite User-Agent received HTTP 200 from the election page, the measure
  app, the fragment endpoint, and the representative PDF. No anti-bot barrier
  was observed.

**Results and history (verified):**
- The same per-election pages add certified results and Statement of Vote
  downloads after an election; the 2018 general-election page is a confirmed
  example.
- The live election selector covers 2018-present. A separate
  `/election-information/archived-elections` page was verified to carry older
  PDF/XLS result material at least as far back as 2002. Greater depth was not
  established in this sweep.

**Confidence:** high on present forward publication, enumeration, page shape,
and access; medium on full document-role coverage because only one PDF packet
was inspected.

**Estimated build effort:** **5-8 engineering days** for a production county
module, extractor, fixtures, and integration tests. Plain HTML capture is
easy; OCR, packet segmentation, and role assignment are the cost and risk.

Raw evidence:
- `alameda/nov-2026-election/`
- `alameda/nov-2026-measure-questions/`
- `alameda/nov-2026-measures-json/` (the tag predates discovering that the
  response is HTML)
- `alameda/nov-2026-sample-measure-pdf/`

---

### Santa Clara County - `vote.santaclaracounty.gov`

**Status:** forward-publishing pattern confirmed; November 2026 measure page
not yet verified; Cloudflare blocks the polite client

**Upcoming publication (verified versus unresolved):**
- **Verified:** the official November 3, 2026 list-of-offices page and
  election-specific measure argument/rebuttal forms exist.
- **Verified historical forward behavior:** the official June 2, 2026
  `list-local-measures-3` page published four qualified local measures with
  document links before that election. The Registrar also announced that its
  voter guides began mailing April 23, 40 days before Election Day.
- **Not verified for the current election:** no November 2026 `List of Local
  Measures` page or current voter guide was discoverable on August 31. This is
  not evidence that there are no measures: the filing forms are live, and the
  Cloudflare block prevented direct inspection beyond the targeted page.

**Measure content and documents (verified from official indexed pages):**
- Local-measure pages carry jurisdiction, letter, title, approval threshold,
  full ballot question, and YES/NO choices inline.
- They link primary arguments for and against, rebuttals, and impartial
  analyses, while explicitly marking unsubmitted documents. Older pages also
  link a combined `Measure Information` PDF.
- The Registrar handles county, school, and special-district filings. City
  arguments may remain with each city clerk, so county-hosted document
  completeness varies by jurisdiction.

**URL and enumeration (verified):**
- Modern election resource pages use descriptive slugs, for example
  `/june-2-2026-statewide-direct-primary-election-resources`.
- Recent measure lists use opaque CMS suffixes (`/list-local-measures-0`
  through `-3`) rather than a date-derived route. Older lists use descriptive
  paths under `/candidates-measures/`.
- Enumerate election pages from `/elections`; do not guess the measure-list
  suffix. Resolving the election page to its measure link is a required
  discovery step.

**Page structure and access (verified):**
- Search-engine copies of official pages show server-rendered Drupal-style
  HTML; the content itself does not appear to require JavaScript.
- A direct request to the November list-of-offices page with the required
  polite User-Agent returned HTTP 403 and a Cloudflare hard-block page. The
  exact User-Agent does **not** defeat this barrier. A real browser fetch path
  would need its own robots, redirect, and rate-limit review before use.

**Results and history (verified):**
- `/elections/past-election-information-and-results` enumerates recent
  results with summary, Statement of Vote, precinct, district, and
  consolidation downloads.
- Decade archive pages extend to the 1950s, with PDF and Excel files. A
  separate measure-history page covers state propositions, local measures,
  and recalls from November 1952 onward.

**Confidence:** high on the county's general forward-publication behavior,
document richness, archive depth, and access barrier; medium-low on November
2026 availability because the current measure list could not be verified.

**Estimated build effort:** **6-10 engineering days**, conditional on first
locating the November measure page and approving a compliant browser fetch
path. The extractor is moderate; Cloudflare and unstable CMS slugs dominate
the estimate.

Raw evidence:
- `santa_clara/nov-2026-offices/` (HTTP 403 Cloudflare capture)

---

### San Mateo County - `smcacre.gov`

**Status:** confirmed forward publisher; **recommended next build**

**Upcoming publication (verified):**
- The official November 3, 2026 page is live at
  `https://smcacre.gov/elections/november-3-2026-statewide-general-election`.
- On August 31, 64 days before Election Day, it exposed **29 measures** and
  **135 measure-document links**. This is a fully populated current-election
  source, not merely an election calendar.

**Measure content and documents (verified):**
- The page has one accordion panel per measure, grouped under county,
  regional-transit, school, and city headings. Each panel supplies the
  measure letter/title, jurisdiction, and required approval threshold.
- All 29 measures link an impartial analysis.
- Across the 29 panels, the page links 29 resolution-family records: 24 are
  labeled `Resolution and Full Text`, four also include a tax-rate statement,
  and one is labeled only `Resolution`. It also links 26
  arguments in favor, 18 arguments against, 16 rebuttals to arguments in
  favor, and 17 rebuttals to arguments against. Missing filings are therefore
  represented by absent links rather than placeholder documents.
- The visible labels have minor whitespace/capitalization variants, including
  non-breaking spaces. Normalize labels before assigning document roles.

**URL and enumeration (verified):**
- Election information uses readable slugs:
  `/elections/november-3-2026-statewide-general-election`.
- `/elections/past-elections-results` is the canonical enumerator. It links
  separate election-information and result slugs for each recent election.
- Document links use an `/archival-document?document={encoded_source_url}`
  wrapper. The underlying stable PDF URL is present in the query string and
  can be captured without browser interaction.

**Page structure and access (verified):**
- The complete measure headings, thresholds, and links are present in the
  initial Drupal HTML. Custom `<smc-accordion-panel>` elements are presentation
  components, not a data-loading dependency. Playwright is unnecessary.
- The polite User-Agent received HTTP 200 from both the current election page
  and the 316 KB past-election index. No anti-bot barrier was observed.

**Results and history (verified):**
- Recent elections have separate slug-based result pages, commonly
  `/elections/{date}-election-results`, with the links enumerated beside each
  election-information page.
- The past-election index carries online results/election-information links
  through the modern period, PDF results for older elections, and decade
  groupings back to the 1950s.

**Confidence:** high on all six reconnaissance questions. The only material
build-time unknown is the text/scanning quality distribution across the 135
PDFs, which fixture selection should sample.

**Estimated build effort:** **3-5 engineering days** for capture, extraction,
fixtures, tests, and pipeline integration. The data is server-rendered,
roles are explicitly labeled, and enumeration is direct.

Raw evidence:
- `san_mateo/nov-2026-election/`
- `san_mateo/past-elections-results/`

---

### San Francisco - `sfelections.org` and `voterguide.sfelections.org`

**Status:** upcoming election confirmed; November measure publication not yet
live on the voter-guide host

**Upcoming publication (verified):**
- The Department's November 3, 2026 calendar is live at
  `https://sfelections.org/tools/cscal_nov26/`, 64 days before Election Day.
- It verifies that ballot questions, digests, and Controller financial
  analyses were due August 10; arguments August 13; rebuttals August 17; and
  the final public-examination period ended August 28.
- The separate voter-guide host returned HTTP 503 with a server-rendered
  `Site under maintenance` page naming November 3 as the next election. No
  November measure list or packet was publicly retrievable there on August
  31. Therefore San Francisco does **not** count as a verified current
  forward-measure source on the recon date, even though its production
  calendar shows the source material has been collected.

**Measure content and documents (verified from the official calendar;
publication inferred):**
- The scheduled voter-guide record includes Ballot Simplification Committee
  digests, City Attorney ballot questions, Controller financial analyses,
  official proponent/opponent arguments, rebuttals, paid arguments, and
  regional impartial analyses; district tax-rate statements are due with
  bond/tax submissions.
- **Inferred:** those items should populate the online Voter Information
  Pamphlet before ballots mail, but the November viewer was not available and
  its exact grouping/link format remains unverified.

**URL and enumeration (verified):**
- Election calendars use compact cycle-specific paths such as
  `/tools/cscal_nov26/`.
- The voter guide is a separate Drupal site with generic routes rather than a
  verified date-bearing per-election URL; it appears to be republished for
  the next election and was in maintenance mode during recon.
- Results use a stable date pattern, `/results/{YYYYMMDD}w/` (with a parallel
  `/results/{YYYYMMDD}/` form for some pages), and expose HTML plus downloadable
  PDF, Excel, XML, and JSON reports.

**Page structure and access (verified):**
- The calendar is a server-rendered HTML table and returned HTTP 200 with the
  polite User-Agent.
- The voter-guide maintenance response was server-rendered Drupal HTML and
  HTTP 503. This is a publication-state barrier, not a bot challenge; changing
  the User-Agent would not reveal content that is offline.

**Results and history (verified):**
- Per-election result pages include summary/detail HTML, Statement of Vote,
  district/neighborhood reports, and machine-readable downloads.
- The date-shaped results archive was verified back to March 1996 in this
  sweep. Greater depth was not established.

**Confidence:** high on the present publication state, calendar, access, and
results shape; medium on the future voter-guide structure until maintenance
ends.

**Estimated build effort:** **4-7 engineering days after the November guide
goes live**. Do not begin the county module before a fresh probe confirms the
measure-page structure; building against the maintenance shell would be
speculative.

Raw evidence:
- `san_francisco/nov-2026-calendar/`
- `san_francisco/voter-guide-home/`

---

### Contra Costa County - `contracostavote.gov`

**Status:** current-election source unresolved behind AWS WAF; rich archive
confirmed on a separate host

**Upcoming publication (unresolved):**
- The real elections domain is `https://www.contracostavote.gov/`.
- A request to the root with the required polite User-Agent returned HTTP 202,
  an empty body, and `x-amzn-waf-action: challenge`. The polite User-Agent does
  **not** defeat the AWS WAF challenge.
- No official November 2026 measure page was discoverable through targeted
  official-domain search. Because the live site could not be inspected, this
  is an unknown, not a finding that Contra Costa publishes only after an
  election.

**Measure content and documents (verified only for the archive):**
- `https://pastresults.contracostavote.gov/` is an official ElectionStats
  database containing ballot questions, choices, approval thresholds, vote
  totals, source documents, and CSV downloads.
- Archived measure detail pages carry the ballot question and link back to
  official source-report pages. This sweep did not verify upcoming impartial
  analyses, arguments, rebuttals, full text, or tax-rate statements on the
  WAF-protected live site.

**URL and enumeration (verified only for the archive):**
- The archive is a Next.js application with opaque numeric detail routes such
  as `/contest/{id}`; legacy indexed URLs also appear under
  `/eng/ballot_questions/view/{id}`.
- Its search page enumerates elections, contests, ballot questions, and
  documents and supports CSV export. IDs should be discovered from search/API
  responses rather than scanned.
- The current-election URL pattern remains unverified.

**Page structure and access (verified):**
- The live registrar host is blocked by an AWS WAF JavaScript challenge.
- The separate archive host returned HTTP 200 with the polite User-Agent. Its
  initial HTML is server-rendered Next.js metadata plus loading skeletons;
  inventory and search results are client/API populated. This is a different
  integration from any eventual current-election scraper.

**Results and history (verified):**
- Archive metadata states coverage from 1997 through 2025. It includes
  candidates, contests, ballot questions, voter statistics, official source
  documents, and downloadable result CSVs.

**Confidence:** high on the two access behaviors and archive shape; low on all
current-election questions.

**Estimated build effort:** **7-12 engineering days, low confidence**, after a
separate browser recon resolves the live site's forward-publication and URL
shape. Do not treat the archive application as evidence that a forward source
exists.

Raw evidence:
- `contra_costa/home/`
- `contra_costa/past-results-home/`

---

## Bay Area sweep recommendation

### Strategic answer

**San Bernardino is not unusual in publishing measures before an election.**
It is unusual mainly in how early and cleanly it does so. Two of the five new
counties - Alameda and San Mateo - already expose substantive November 2026
measure records 64 days before Election Day. Santa Clara also demonstrably
published its June 2026 measure record before that election, although its
November page is not yet verified. San Francisco's calendar is live but its
November guide is still offline, and Contra Costa remains unknown behind WAF.

The roadmap therefore should **not** collapse into an archive-only effort for
2026. Current-election expansion is reachable this cycle. San Bernardino's
roughly four-month lead remains better than the lead directly verified here,
so the product should expect counties to come online at different points in
the filing/voter-guide calendar rather than on one statewide date.

### Recommended next build: San Mateo

San Mateo wins on the required ordering:

1. **Forward publication:** 29 November measures are live now.
2. **Document richness:** 135 explicitly labeled links; every measure has an
   impartial analysis, and filed arguments/rebuttals are separate documents.
3. **Structural simplicity:** one server-rendered election page, readable
   slugs, a server-rendered archive enumerator, and no anti-bot barrier.

Alameda should follow San Mateo. It is equally decisive evidence for current
coverage and its inline ballot questions are excellent, but its scanned,
combined PDF packets introduce OCR and document-segmentation work that San
Mateo avoids. Santa Clara becomes attractive after the November page is found
and a compliant Cloudflare fetch path is approved. San Francisco should be
re-probed when its voter-guide maintenance page comes down. Contra Costa
needs a browser reconnaissance task before any build commitment.

### Effort summary

| County | Enumeration | Production build estimate | Primary risk/gate |
|---|---|---:|---|
| **San Mateo** | Slugged election pages enumerated from `/elections/past-elections-results` | **3-5 days** | PDF text/scanning variance |
| **Alameda** | Opaque IDs enumerated from the election page; HTML fragment at `/rov_app/measures/election/{id}` | **5-8 days** | Scanned combined packets; OCR and role segmentation |
| **Santa Clara** | Election index plus unstable CMS measure-list links | **6-10 days** | Cloudflare; November measure page not yet verified |
| **San Francisco** | Calendar cycle path; date-shaped results; voter guide republished separately | **4-7 days after guide launch** | Current guide offline; exact structure not yet verifiable |
| **Contra Costa** | Current unknown; archive uses search-discovered numeric IDs | **7-12 days, low confidence** | AWS WAF and unresolved forward source |
