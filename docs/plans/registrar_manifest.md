# California county registrar reconnaissance manifest

> **Purpose:** per-county notes on what each registrar site
> publishes, URL patterns, formats, and scraping concerns. Phase 0
> deliverable for the local-measure pipeline (see
> `docs/plans/registrar_pipeline_infra.md`).
>
> **Status:** **First-pass reconnaissance only.** Initial probing
> was done via WebFetch (returns markdown summaries, no JS rendering,
> generic User-Agent). Several sites either blocked or returned
> limited content; full reconnaissance for those will need real
> browser fetches (Playwright) or curl with a polite-scraping
> User-Agent. This doc captures what's confirmed; gaps are flagged.

## Top-5 counties (Phase 1 targets)

### 1. Los Angeles County — `lavote.gov`

**Status:** ✅ scraping entry point identified

**Main site (`www.lavote.gov`):**
- Built on Sitefinity CMS, primarily server-rendered HTML
- Navigation pattern: `/home/voting-elections/[section]/[subsection]`
- Past elections archive: `/home/voting-elections/current-elections/election-results/past-election-results` — lists elections back to 2007
- Scheduled elections list: `/home/voting-elections/current-elections/election-results/past-scheduled-elections` — covers 2001 through 2025
- **No public per-measure index page** — main site lists elections by date, not measures by letter/number
- Interactive Sample Ballot at separate subdomain `isb.lavote.net` (per-voter, requires input, JS-heavy)

**Results portal (`results.lavote.gov`):**
- SPA at root path with anchor routing: `https://results.lavote.gov/#year=2026&election=4338`
- **Static text version at `https://results.lavote.gov/text-results/{election_id}`** — this is the scraping entry point
- Sample observed: `text-results/4338` = June 2, 2026 Statewide Direct Primary
- Election ID is the path param; election list at `/election-list/text`
- Content shape: county measures, board of supervisors, sheriff, judges, cities, schools, community services — each section lists contests with full measure text + vote totals
- "COUNTY MEASURE ER" type entries with full ballot text + YES/NO counts + percentages
- Static HTML, no JS dependency, scraper-friendly

**Aggregate result PDFs:**
- URL pattern: `https://content.lavote.gov/docs/rrcc/svc/{election_id}_{document_type}.pdf`
  (e.g. `4324_final_svc_precinct_public_v2.pdf`, `4324_final_svc_district_v3.pdf`)
- Document types: Statement of Votes Cast (by precinct/district), Precinct Bulletins, Votes Cast by Community
- Excel format datasets also available alongside the PDFs
- Election IDs appear sequential (4338, 4337, 4331…)

**Ballot language sources:**
- Not visible as a public per-measure list on the main site
- Likely lives in mailed Sample Ballot Booklets (PDFs); URL pattern not yet identified
- Interactive Sample Ballot at `isb.lavote.net` carries it but per-voter access

**Scraping verdict for Phase 1:**
- **Use the text-results portal** as primary source — gives measure text + vote totals in one page per election
- Enumerate by election ID (sequential integers from past scheduled-elections list, or query `/election-list/text`)
- Save raw HTML to R2; parse per-section (County Measures, Cities, Schools, Community Services)
- No Playwright needed for the text-results URL
- Anti-scraping: no visible blocks during reconnaissance (WebFetch with generic UA worked)

**Open questions:**
- What's the earliest `election_id` the text-results portal covers? (Older results may only be in PDFs.)
- For pre-election captures (before vote counts exist), does the same URL show measure text only?
- Are draft / preliminary ballot measures listed somewhere before the official Statement of Vote?

---

### 2. San Diego County — `sdvote.com`

**Status:** ⚠️ blocked — generic User-Agent returned 403 Forbidden

**Confirmed finding:**
- `https://www.sdvote.com` blocks generic User-Agents (HTTP 403)
- Will require a real polite-scraping User-Agent for any access
- This validates Codex's polite-scraping concern; the planned default UA
  (`cal-vgp-registrar-scraper/0.1 (+https://github.com/igorgeyn/cal_vgp; contact: igorgeyn@gmail.com)`) is the right shape — clearly identifies us with a working contact

**Not yet probed:**
- Site structure, URL patterns, JS dependency, measure text availability — all pending real-browser fetch
- Whether 403 is purely UA-based or also IP / rate-limited

**Next step for SD recon:** retry with a real User-Agent (curl `--user-agent` or Playwright with the polite-scraping default). If still blocked, may need to test from a different IP or check if registrar offers a public records request channel.

---

### 3. Orange County — `ocvote.gov`

**Status:** ⚠️ partial — landing pages reachable but content thin

**Confirmed:**
- Main site at `www.ocvote.gov` returns content via WebFetch (no UA block)
- Top-level nav: `/elections`, `/candidates`, `/results`, `/data`, `/voting`
- Past results archive lives at `/data/election-results-archives`
- "Previous Results" link visible from data section
- Site appears server-rendered, not a JS-heavy SPA

**Not yet confirmed (WebFetch returned thin content on archive + results pages):**
- Whether there's a per-election landing page with measure-level data
- URL patterns for individual election result pages
- Format of measure text (HTML, PDF, embedded)
- Whether there's a structured data export (CSV / JSON)

**Likely shape (inferred, needs verification):**
- "View" buttons on results landing page → per-election detail pages
- May have downloadable result files in some structured format
- Per-election URLs likely include election date or ID

**Next step for OC recon:** click through the "View" links from `/results` to see what per-election pages contain. Probable that the results pages need actual interaction (clicks/JS) rather than direct URL fetches; may need Playwright.

---

### 4. Riverside County — `voteinfo.net`

**Status:** ⛔ not probed in this pass

The Jan 2026 plan noted `voteinfo.net` as the Riverside registrar
URL. Not investigated in this reconnaissance pass. To probe:
- Verify URL still active
- Check if blocks generic User-Agents
- Probe results / past elections / sample ballot pages
- Identify if dedicated subdomain for results (like LA's
  `results.lavote.gov`)

---

### 5. San Bernardino County — `sbcrov.com`

**Status:** ⛔ not probed in this pass

Same as Riverside — not investigated. Plan doc lists `sbcrov.com`
but reconnaissance pending.

---

## Cross-county takeaways (first-pass observations)

### What's the same across counties

- **No standardized format.** Every county has its own URL structure and content patterns. The pipeline architecture's per-county scraper module pattern is justified.
- **Static text endpoints exist for at least some counties** — LA has the text-results portal; OC presumably has analogous per-election result pages. These are the scraper-friendly entry points.
- **Aggregate result PDFs exist everywhere.** Statement of Votes Cast (SOVC) is a state-mandated document; every registrar publishes it. These are good for vote totals but not ballot language.

### What varies

- **Anti-scraping posture.** SD blocks generic UAs (403); LA + OC allowed WebFetch's default UA. We need to assume each county requires polite identification.
- **Ballot language availability.** LA buries it in per-voter Interactive Sample Ballot tools or mailed PDFs. OC, Riverside, SB unknown.
- **JS dependency.** LA's main results portal is SPA (anchor routing); LA's text portal is static. OC's pages need deeper inspection.

### Implications for the Phase 0.5 + Phase 1 plans

1. **Playwright is going to be needed sooner than "optional fallback."** OC's per-election pages, SD's anti-scraping defenses, and LA's main results portal all hint at JS-rendered or auth-required content. Plan should treat Playwright as a first-class fetch mode from Phase 1.

2. **Polite User-Agent is non-negotiable from day one.** SD's 403 confirms Codex's polite-scraping advice. Build the UA + contact info into the base scraper from the first commit.

3. **Election-ID-based enumeration is realistic for LA.** Sequential integers (4338, 4337, …) mean we can systematically walk LA's history once we identify the lowest valid ID.

4. **"Ballot language" might require a different sourcing strategy than "results."** Results pages (LA text-results, OC View pages) carry measure titles + vote totals but may not carry full ballot text. Sample ballot booklets (PDFs mailed to voters) carry the language but aren't necessarily public-listed. We may need to source ballot text from:
   - The voter information guide PDFs (when registrar publishes them publicly)
   - Each county's "argument & rebuttal" archive (LA links to these in measure information pages)
   - Cal SOS or Ballotpedia as supplements

5. **Phase 0 reconnaissance is incomplete.** Three of five counties not yet probed; the two that were probed need deeper inspection. **Recommend:** finish reconnaissance with curl/Playwright (not WebFetch) before Phase 0.5 implementation locks in any concrete scraper interfaces.

## Recommended next steps for Phase 0

1. **Set up a reconnaissance harness** (local Python script with polite-scraping UA + Playwright + ability to save artifacts to local FS). ~half-day.
2. **Probe SD with polite UA** — does the 403 go away with a real UA, or is it more aggressive?
3. **Probe OC's per-election View pages** with the harness — confirm structure + format.
4. **Probe Riverside + San Bernardino** from scratch — same set of questions as the LA probe.
5. **Probe LA's text-results portal for a few historical election IDs** — confirm the URL pattern works back to 2007 or only for recent elections.
6. **Find a sample ballot booklet for each county** — chase down URL patterns for the PDFs containing ballot language.

After that pass, the manifest gets a "Phase 1 county priority order" recommendation and Phase 0.5 implementation can start with realistic constraints baked in.

## Honest assessment

This first pass surfaced enough to confirm the pipeline architecture
is on the right track, identify one concrete scraping entry point
(LA's text-results portal), validate Codex's polite-scraping concerns
(SD 403), and flag that Playwright is going to be needed more than
the plan anticipated. But it's not enough to start building scrapers
against. The reconnaissance harness step above is the right next
move before any code commits.
