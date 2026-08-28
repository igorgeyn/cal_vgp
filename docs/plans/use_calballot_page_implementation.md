# “Use CalBallot” page implementation plan

> Drafted 2026-08-27. Publication was separately authorized after source and
> scratch review. The root bundle, measure pages, and sitemap were then generated
> through the reviewed publication workflow.
>
> **Implementation status:** source implementation, artifact generation, release
> verification, and GitHub Pages publication are complete.

## 1. Objective

Add a lightweight, shareable page at:

`https://cal-vgp.igorgeyn.com/use-calballot/`

The page should explain how CalBallot serves four repeat-user groups:

1. Local and statewide journalists
2. Academic and policy researchers
3. Civic-information organizations
4. Government, campaign, and public-affairs professionals

The page should help professional users recognize the product's relevance
without turning the voter-facing homepage into an institutional marketing page.
It should preserve the core value proposition:

> CalBallot makes California ballot measures understandable and verifiable by
> connecting official records, voting rules, campaign money, results, and
> historical context in one searchable public resource.

The approved long-form positioning source is
[`docs/AUDIENCE_PITCHES.md`](../AUDIENCE_PITCHES.md). The site page should adapt
that material for web reading rather than dumping four uninterrupted pages of
prose into the interface.

## 2. Product and information-architecture decision

### Chosen structure: a separate generated page

Generate a real static page at `/use-calballot/index.html`, rather than adding a
fifth data-app view or putting the full pitches in the About modal.

Reasons:

- It has a stable, shareable, indexable URL.
- It can be lightweight and avoid fetching the 35 MB measures bundle or loading
  Chart.js, D3, Leaflet, and DuckDB.
- It keeps the homepage focused on voters who came to find a measure.
- It avoids adding more state to the existing grid/list/Insights/Explore view
  router, whose URL contract currently covers pagination and measure modal links
  but not every view.
- It gives the four audiences enough room without making the About modal several
  screens longer.

The page must still be owned by the Python generator. Do not hand-maintain a
second standalone HTML/CSS file: it would drift from the site design and bypass
the root/scraper mirror contract.

### Entry points

Add three restrained links to the existing site:

1. **Welcome panel**, after the methodology link:

   > Using CalBallot for reporting, research, or civic work? See how CalBallot
   > can help →

2. **About modal**, in a short new “Who uses CalBallot?” section. Give the four
   audience names in one sentence and link to the new page. Do not paste the full
   pitches into the modal.

3. **Footer**, beside About:

   > Use CalBallot

Do not add another persistent header button in the first release. The header is
already carrying Grid, List, Insights, Explore, and About, and the new page is a
secondary professional-use destination rather than a primary data-app mode.

## 3. Page content and layout

### Page header

Use the existing CalBallot brand mark as a link back to `/`. Keep the header
minimal:

- CalBallot logo/name
- “Browse measures” primary action linking to `/`
- “About the data” text link back to the homepage's About entry point only if a
  stable link can be provided without fragile inline state; otherwise omit it in
  v1.

Do not reproduce the full data-app search bar or view controls on this page.

### Hero

Suggested hierarchy:

- Eyebrow: **For reporting, research, and civic work**
- H1: **Use CalBallot to investigate California ballot measures**
- Deck: the full “understandable and verifiable” value proposition
- Primary action: **Browse ballot measures** → `/`
- Secondary action: **Choose your use case** → `#audiences`

Add a compact trust strip below the hero. Claims must be generated from current
statistics where possible rather than hard-coded:

- Exact active-record count from `stats['total_measures']`
- Earliest year from `stats['year_min']`
- Exact local archive-record count from `stats['local_count']`
- Source-conscious, endorsement-free presentation

Avoid “every current ballot,” “complete ballot,” and “your ballot.” Historical
county breadth is not address-level current-election coverage.

### Audience index

At `#audiences`, display four keyboard-accessible cards. Each card contains:

- Audience name
- One-sentence benefit
- Two or three example tasks
- Anchor link to the full section

Suggested anchors:

- `#journalists`
- `#researchers`
- `#civic-organizations`
- `#public-affairs`

The cards should use ordinary anchor links, not JavaScript click handlers, so
deep links, keyboard navigation, and browser history work automatically.

### Long-form audience sections

Use four stacked sections rather than accordions. The page is explicitly a
reading page, and all four sections should remain indexable and discoverable with
Find-in-page. Alternate subtle background or column alignment to make the long
page scannable.

Each section should contain:

1. Audience label and pitch headline
2. Approximately 250–350 words adapted from `docs/AUDIENCE_PITCHES.md`
3. A short “CalBallot helps you” list with three concrete tasks
4. One visible scope/limits sentence
5. One or two relevant actions

Recommended action matrix:

| Audience | Stable v1 action |
|---|---|
| Journalists | Browse/search measures at `/` |
| Researchers | Access `/measures-data.json` |
| Civic organizations | Browse official-source records at `/` |
| Public-affairs professionals | Compare measures at `/` |

Do not add `?view=` links or buttons that imply stable Insights/Rules routing.
Main-app URL state is a separate change with a much larger blast radius.

### Closing section

End with the positioning line:

> A public-facing voter resource with an expert-grade research backbone.

Then provide:

- **Browse CalBallot** → `/`
- **Contact Igor** → existing contact address
- A required, data-derived coverage note explaining that the archive contains
  thousands of historical local measures; current-election registrar coverage
  is a narrower county-by-county collection; the current build contains the
  computed number of captured registrar counties and measures; and CalBallot is
  not an address-based ballot finder.

Reuse the existing civic footer links only if they remain visually subordinate to
the page's purpose. At minimum, preserve About/contact and the CalBallot data date.

## 4. Visual and accessibility requirements

Create a small, dedicated stylesheet emitted by the generator and scope every new
rule under `.use-calballot-page`. Do not load the main site's entire stylesheet
unless a measured implementation shows that doing so is materially simpler and
does not pull in irrelevant component behavior.

Design requirements:

- Match the existing cream/gold/charcoal palette, typography, radii, and spacing.
- Use a readable text measure of roughly 65–75 characters for pitch prose.
- Make the four audience cards two columns on desktop and one column on mobile.
- Use a single-column long-form reading layout; avoid a carousel.
- Maintain visible keyboard focus on every link.
- Use one H1, then H2 audience sections, with H3 only inside sections.
- Preserve anchor targets below the sticky header with `scroll-margin-top`.
- Respect `prefers-reduced-motion`; no animation is necessary for v1.
- Do not rely on icons alone to distinguish audiences.
- Test at 375 px, 768 px, 1024 px, and 1440 px widths.

The page must remain useful with JavaScript disabled. No content should depend on
client-side rendering.

## 5. Hard scope boundary: no main-app routing changes

Do not add `?view=` routing in this task. Do not modify `setView()`, `updateURL()`,
`loadPageFromURL()`, browser back/forward behavior, pagination hashes, or measure
modal deep links except where an independently discovered correctness bug makes
the new page impossible to ship.

The secondary page's calls to action will use only stable existing destinations:
`/`, `/measures-data.json`, ordinary in-page anchors, and contact links. Stable
main-app view and Insights-panel URLs deserve their own design, implementation,
and review pass.

## 6. Generator and output-contract implementation

### Generator ownership

Add a focused renderer such as:

```python
WebsiteGenerator._generate_use_calballot_html(stats: Dict) -> str
```

It should return a complete HTML document with:

- `<title>Use CalBallot — Reporting, Research, and Civic Work</title>`
- A concise meta description
- Canonical URL `https://cal-vgp.igorgeyn.com/use-calballot/`
- Open Graph title, description, type, and URL
- Existing favicon/apple-touch-icon assets via absolute paths
- No measure-data fetch and no chart/map/database dependencies

Keep approved page copy near this renderer and add a source comment pointing to
`docs/AUDIENCE_PITCHES.md`. The site copy is an adaptation, so the documentation
does not need to be parsed dynamically at build time.

Before rendering, enrich `stats` from the same database used for the site:

```sql
SELECT COUNT(DISTINCT county), COUNT(*)
FROM active_measures
WHERE CAST(year AS INTEGER) = :current_cycle_year
  AND data_source LIKE '%_County_Registrar'
```

Use the active database's maximum election year as `current_cycle_year`, and
expose the results as named stats such as `current_registrar_counties` and
`current_registrar_measures`. Keep California's fixed 58-county denominator as a
named constant, not an unexplained literal in prose. The renderer must receive
all five public figures—active records, earliest year, local archive records,
current registrar counties, and current registrar measures—through `stats`; it
must not query the database or hardcode a current coverage sentence itself.

### Extend the paired-output writer

The current generator stages and verifies the main HTML and JSON for every output
root. Extend that contract rather than issuing an unrelated write after the main
bundle succeeds.

Recommended shape:

```python
auxiliary_pages = {
    Path("use-calballot/index.html"): use_calballot_html,
}
```

For each main `output_path`:

- Main: `<output_path>`
- Data: `<output_path.parent>/measures-data.json`
- Audience page: `<output_path.parent>/use-calballot/index.html`

Stage all temporary files before replacing any final targets. After publication,
verify that:

- Root and `scraper/` main HTML files are byte-identical.
- Root and `scraper/` JSON files are byte-identical.
- Root and `scraper/` Use CalBallot pages are byte-identical.
- The JSON record-count contract still passes.

An explicit `--output <scratch>/index.html` must generate the auxiliary page only
under `<scratch>/use-calballot/index.html`; it must never fall back to a root
project path.

Do not create a second data file for the audience page.

### Sitemap source

Update `build_measure_pages.py` so the sitemap URL list includes:

`https://cal-vgp.igorgeyn.com/use-calballot/`

Refactor the URL-list construction into a small testable helper if needed. Do not
regenerate `sitemap.xml` during the source implementation pass; that belongs to
the reviewed publication step.

## 7. Testing plan

### Unit and contract tests

Extend `scraper/tests/test_website_output_contract.py` or add
`test_use_calballot_page.py` to verify:

1. Both configured output roots receive byte-identical audience pages.
2. An explicit scratch output keeps every generated file inside the scratch root.
3. The audience page contains all four stable section IDs.
4. The page has one H1 and the expected H2 hierarchy.
5. Canonical and Open Graph URLs use `/use-calballot/`.
6. The page does not contain `fetch('measures-data.json')`, DuckDB, Chart.js, D3,
   Leaflet, or external runtime data calls.
7. Coverage language includes “not an address-based ballot finder” or equivalent.
8. Required copy explicitly distinguishes the historical local archive from the
   narrower current-election registrar collection.
9. Every rendered database-derived number equals the value computed from the
  database used for generation: active measures, earliest year, local archive
  records, current registrar county count, and current registrar measure count.
10. Prohibited claims such as “your complete ballot” do not appear.
11. Every internal anchor resolves to an element ID in the document.
12. Existing HTML/JSON byte-identity and count tests still pass.

### Required regression suite

From `scraper/`:

```powershell
python -m pytest tests/ -q -k "website_output or use_calballot"
```

Also run the registrar/site selection used by the current work arc if the branch
still contains the upcoming-local-measures changes:

```powershell
python -m pytest tests/ -q -k "registrar or website_output"
```

### Scratch generation and browser QA

Generate only to a scratch directory with `--output` and confirm:

- `/use-calballot/` loads without requesting `measures-data.json`.
- All four audience anchors and back-to-top links work.
- Homepage, About, and footer links reach the correct page.
- Logo and Browse actions return to the main app.
- Keyboard tab order is logical.
- No horizontal overflow occurs at mobile widths.
- The long sections remain readable and visually distinct.
- There are no browser console/page errors.

Capture desktop and mobile screenshots as review artifacts under scratch, not as
tracked site files.

## 8. Content and claims review

Before publication, conduct a short factual-copy pass against the current
database and site behavior:

- Render the exact active-record count and earliest year from the current `stats`
  payload; do not maintain those values in prose.
- Compute current registrar coverage from `active_measures` for the current cycle
  with `COUNT(DISTINCT county)` and `COUNT(*)` where
  `data_source LIKE '%_County_Registrar'`; pass those values through `stats`.
- State that campaign-finance coverage is for matched statewide campaigns.
- Describe current registrar work as emerging/county-by-county.
- Include a mandatory sentence stating that thousands of local measures describe
  the historical archive while current-election registrar coverage is narrower.
- Do not imply all 58 counties have complete current-election coverage merely
  because the historical archive contains records from all counties.
- Do not call CalBallot a personalized ballot finder.
- Do not promise every measure has a summary, official document set, finance
  record, or defensible semantic comparison.
- Keep endorsements and voting recommendations explicitly out of scope.

The About modal currently contains broader feature language. Review only the
sentences directly adjacent to the new audience link during this task; a full
About rewrite should be a separate content pass unless a statement directly
contradicts the new page.

## 9. Delivery phases and review gates

### Phase A — content wireframe

Deliver:

- Plain HTML structure or static screenshot in scratch
- Final hero/value-proposition copy
- Four condensed web sections and action labels
- Coverage disclaimer

Gate: confirm tone, length, and audience hierarchy before touching output
contracts.

### Phase B — generator and tests

Deliver:

- Audience-page renderer
- Scoped CSS
- Homepage/About/footer entry links
- Extended auxiliary-page mirror contract
- Focused tests

Gate: source diff and tests only. Do not regenerate tracked artifacts.

### Phase C — scratch verification

Deliver:

- Scratch root and scraper-mirror generation
- Byte-identity report
- Desktop/mobile screenshots
- Browser request/error report
- Accessibility checklist

Gate: Igor reviews the rendered page and copy.

### Phase D — publication, separately authorized and completed

After approval:

1. Regenerate the tracked root bundle and ignored local mirror through the normal
   generator entry point.
2. Regenerate measure pages/sitemap through the reviewed publication workflow.
3. Confirm the only new public route is `/use-calballot/` and the expected
   sitemap addition.
4. Review the large artifact diff separately from source changes.
5. Verify the deployed URL, canonical tag, links, mobile rendering, and absence of
   console errors.

## 10. Definition of done

The work is complete when:

- `/use-calballot/` is a lightweight, static, directly shareable page.
- Each of the four audiences can identify its use case within one screen and
  navigate to a substantive pitch.
- The homepage remains voter-first and receives only a quiet professional-use
  link.
- About and footer provide secondary entry points.
- Claims accurately distinguish historical breadth, statewide finance coverage,
  and county-by-county current-election ingestion.
- The archive-versus-current distinction is explicit, and current registrar
  county/measure figures are generated from the active database.
- Positive tests prove every rendered database-derived figure matches the input
  database used for generation.
- The page works without JavaScript and at mobile widths.
- It does not load the measures bundle or analytical libraries.
- Root and local-mirror audience pages are byte-identical.
- Existing site output and registrar tests pass.
- Tracked deployed artifacts are regenerated only in the separately reviewed
  publication phase.

## 11. Estimated effort

- Content adaptation and wireframe: 2–3 hours
- Generator/output-contract implementation: 3–5 hours
- Tests and responsive/accessibility QA: 2–3 hours
- Publication review: separate short session because of tracked artifact scope

## 12. Implementation verification

Scratch generation against the isolated San Bernardino-loaded database produced:

- 12,332 active measure records
- 11,017 local records in the archive
- statewide history beginning in 1911
- current registrar coverage of 1 of 58 counties and 20 measures for 2026

The page is 33 KB, contains no JavaScript, and made no requests for the measures
bundle, Chart.js, D3, Leaflet, or DuckDB. Headless Chromium checks at desktop and
mobile widths found no horizontal overflow, console/page errors, or broken
audience anchors; keyboard focus begins with the skip link and proceeds through
the header, hero actions, and audience cards.

Tests completed:

- `website_output or use_calballot`: 7 passed
- `registrar or website_output or use_calballot`: 193 passed
- The focused database-backed page tests verify every rendered figure against
  the database used for generation.

The legacy `tests/test_database.py` file still has its documented pre-existing
string-path fixture failures; all ten tests fail before reaching the statistics
logic because `Database` expects a `Path`. This task does not alter that known
legacy issue.

Publication generated the tracked root bundle, `/use-calballot/index.html`, 20
San Bernardino measure pages, and a 12,334-URL sitemap. The page canonical and
Open Graph URL match the repository's live `CNAME`,
`https://cal-vgp.igorgeyn.com`.
