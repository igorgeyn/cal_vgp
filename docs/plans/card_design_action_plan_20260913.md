# CalBallot card design: review and action plan

**Date:** September 13, 2026.  
**Status:** documented for later work; implementation has not started.  
**Scope:** archive, statewide upcoming, and local upcoming measure cards, including the containers and controls that directly determine their usability.

Igor requested a comprehensive aesthetic review and then this durable action
plan. The review inspected the live site at 1440px, 390px, and 320px, read the
card implementation, and consulted civic interfaces and design guidance. It
was an expert review, not a user study or a complete accessibility audit.

This document records recommendations, not approval of every proposed design
detail. It does not authorize immediate implementation, regeneration,
publication, scraping, or database changes. When this work resumes, follow the
then-current task instructions and release process. Creating this plan does
not change the priority of reliable refreshes and election-status correctness.

## 1. Design objective and recommendation

Make each card easy to identify, read, compare, and open. Preserve CalBallot's
warm background, dark text, gold accent, substantive previews, and connection
between current measures and the historical archive.

The largest improvement will come from **hierarchy, typography, and available
width**. Decorative changes alone will not fix repetitive titles, tiny local
metadata, or mobile cards squeezed between arrows and nested padding.

Recommended order:

1. Prototype local cards and their mobile container with real content.
2. Establish shared typography, spacing, color, and interaction rules.
3. Apply those rules to archive and statewide variants, preserving their summaries.
4. Verify difficult content, keyboard use, text enlargement, and responsive behavior.
5. Integrate and release through the current site verification process when scheduled.

The first deliverable is a small comparison sheet, not a site-wide redesign.

## 2. Existing decisions and scope boundaries

Read these alongside this plan:

- [Compact local-card brief](../codex/compact_local_measure_cards.md).
- [Earlier local-widget design and subsequent product decision](local_measures_widget_redesign.md).
- [Accepted September priority plan](forward_plan_20260907.md).
- [Published F1 release and verification record](f1_post_review_release_20260908.md).
- [Results transition contract](results_transition_20260907.md).
- [Lessons learned](../LESSONS_LEARNED.md).

### Preserve

- **The carousel:** Igor previously chose cards and a carousel over a fixed-height list.
  Improve the carousel's mobile geometry; do not quietly replace it with the
  previously rejected list design.
- **Substantive previews:** Igor rejected removing descriptions from ordinary
  cards. Keep useful archive/statewide summaries or source excerpts.
- **Local historical context:** the connection to the archive is intentional.
  Improve its readability and explanation instead of removing it to save space.
- **County-scoped honesty:** selecting a county does not identify a person's
  ballot. Preserve the visible scope qualification.
- **Recorded data semantics:** preserve IDs, thresholds, outcome ownership,
  document grouping, and the exclusion of unresolved outcomes from historical
  comparisons.
- **Existing detail views:** Finance, documents, source links, and other modal
  content must continue to work with the same measure identity.
- **A recognizable brand:** retain the warm palette and restrained gold accent.

### Recommendations that revise earlier design assumptions

- Replace the approximately 120px local-card target with content-driven height.
  A starting prototype around 180–220px is reasonable, not a fixed requirement.
- Replace differently colored approval-threshold pills with clear, neutral labels.
  The previous premise that thresholds need colors to convey increasing difficulty
  is weaker than an explicit statement of the requirement.
- Test four archive columns at 1440px instead of the current five.
- Simplify overlapping upcoming/featured decorations.
- Replace the previously proposed nine-slot document indicator with readable
  document availability text. Empty slots could imply unsupported completeness.

These are conscious proposals, not claims that prior decisions never existed.

### Exclude from this work

- County expansion, address lookup, precinct matching, and new scraping.
- Mass title/summary generation, historical-data cleanup, or new analytics.
- Results ingestion and a new election-status model. Coordinate with that work,
  but do not infer new statuses as part of a cosmetic change.
- New routing, per-card deep links, sharing, saving, or comparison features.
- A framework migration or general site redesign.
- A modal redesign, except for the minimal behavior needed to open the existing
  view and restore focus correctly.
- Stock photos, arbitrary topic illustrations, and additional badge collections.

The mobile header overflow observed in screenshots is a separate issue. Keep
it distinguishable from overflow introduced or fixed by the card work.

## 3. Evidence from the September 13 review

Measurements describe the site at review time, not permanent invariants.
Recheck them before implementation if the site has changed.

| Observation | Consequence | Proposed action |
|---|---|---|
| Archive titles include `Measure A: ALAMEDA Measure A` | Repeated identifiers consume headline space while substantive information is subordinate | Separate identity, geographic scope, and descriptive heading |
| At 1440px, archive cards form five columns about 261px wide | Headlines and summaries wrap or truncate quickly; the default 12-card page has an incomplete final row | Compare four columns, retaining the existing list view for density |
| At 390px, a local card is about 234px wide, versus about 358px for an archive card | Arrows and container padding spend space the text needs | Move mobile controls below the carousel and widen the card |
| At 320px, the local historical-context line truncates | The observation loses its sample or time qualification | Allow wrapping and remove the side-control bottleneck |
| Local jurisdiction text is 13.76px; other local fields are roughly 10.7–11.2px | Important information is visually fragile | Increase typography and relax height constraints |
| Metadata `#999080` on card background `#F7F5F0` is approximately 2.9:1 | Normal text is below WCAG AA contrast minimum | Use a darker secondary text color |
| Gold identifier `#A8841E` on that background is approximately 3.22:1 | Small bold identifiers also fail the normal-text contrast minimum | Use dark identifiers or a verified darker accent |
| Featured/upcoming treatments combine gold outlines, purple rails, gradients, italic summaries, and badges | Multiple visual systems compete on the same card | Establish one card surface and restrained variant rules |
| Failed archive cards still display a green yes-share bar | The graphic can compete with the red failure label | Use a neutral bar; group it with an explicit yes-share label |
| Local cards do not advertise the newly published document collection | Readers cannot anticipate a major benefit of opening them | Add a readable document count/availability footer |
| Local cards have keyboard-button behavior, while general cards use an onclick div without equivalent semantics | The same apparent component behaves differently by input method | Establish one accessible interaction contract |

### Local evidence bundle

Review screenshots are in the ignored directory
`scraper/data/registrar_recon/card_aesthetic_review_20260913/`.
They may not be present on another machine; the observations above are retained
here so the plan remains useful without them.

- [Desktop archive](../../scraper/data/registrar_recon/card_aesthetic_review_20260913/desktop-archive.png).
- [Desktop local: San Bernardino](../../scraper/data/registrar_recon/card_aesthetic_review_20260913/desktop-local.png).
- [Desktop local: San Mateo](../../scraper/data/registrar_recon/card_aesthetic_review_20260913/desktop-smc.png).
- [Mobile local: San Mateo](../../scraper/data/registrar_recon/card_aesthetic_review_20260913/mobile-local.png).
- [320px local layout](../../scraper/data/registrar_recon/card_aesthetic_review_20260913/narrow-local-detail.png).
- [Mobile archive](../../scraper/data/registrar_recon/card_aesthetic_review_20260913/mobile-archive-detail.png).
- `desktop-statewide-detail.png`, `mobile-statewide-detail.png`, and
  `narrow-statewide-detail.png` cover the statewide variant.
- `metrics.json` contains an initial typography sample, not a full accessibility report.

The saved `reference-calmatters.png` depicts an internal interactives index;
it is **not** the public design precedent. Use `reference-calmatters-public.png`
and the public guide linked in section 11.

## 4. Card anatomy and content rules

Use a shared visual family with variants that reflect different reader tasks.
Do not force every variant to show the same fields or occupy the same height.

| Area | Local upcoming | Statewide upcoming | Historical/archive |
|---|---|---|---|
| Identity | Measure letter; `Local measure` when absent | Verified proposition number or current identifier | Measure identifier and year |
| Primary heading | Jurisdiction | Concise descriptive heading | Concise descriptive heading, when trustworthy |
| Supporting text | Measure type; optional substantive preview if available | Short explanation | Short explanation |
| Decision information | Explicit required approval threshold | Relevant verified requirement, when available | Recorded outcome and yes-share group |
| Context | Existing supported county/type comparison | Preserve existing supported information without conflating different context models | Do not add new analytics |
| Footer | Open details; document availability | Open details; document availability if represented | Open details; quieter source attribution |

### Titles and geographic scope

1. Render the identifier once in a dedicated position.
2. Prefer an existing trustworthy descriptive title over an official long-form
   title when the existing data supports that distinction.
3. Remove obvious presentation duplication without editing canonical source fields.
4. When no useful descriptive heading exists, show a clean identifier/scope and
   let the existing substantive preview carry the explanation.
5. Do not title-case or rewrite jurisdiction names blindly. Preserve proper names,
   acronyms, and official distinctions.
6. Historical county fields do not identify the governing city or district.
   Never relabel all Alameda County records as City of Alameda measures.
7. Do not expose canonical `REG_...` strings as public card titles.
8. Preserve full source titles in the existing detail view.

### Summary previews

- Keep the current summary/source fallback capability; do not turn the redesign
  into a new content-generation pipeline.
- Favor useful substance over repeated `This measure...` boilerplate when an
  existing reviewed short description is available. Do not remove words using
  a heuristic that changes meaning.
- Prefer layout-aware truncation over both a character cut and a CSS clamp.
  Any formatter change must preserve the full underlying text and have focused
  coverage for its meaningful edge cases.
- Do not show metadata, AI refusals, or a duplicated title as a substantive summary.
- If no useful text is available, omit that block or use a concise honest state;
  avoid long generic placeholders and invented descriptions.
- Distinguish observed source debris, such as the reference marker in the
  current Prop 50 preview, from CSS problems. Fixing source extraction broadly
  is a separate task; any bounded display cleanup must be conservative.

### Distinguish the three percentage meanings

| Meaning | Example display | Rules |
|---|---|---|
| Approval requirement | `Requires 55% yes` | Use the existing verified threshold; do not derive it from outcome data |
| Simple majority | `Requires a majority` | Preserve an explanation of the exact requirement in details; do not rewrite it as “at least 50%” |
| Two-thirds | `Requires two-thirds` | Preserve the source value and wording; do not change numeric semantics |
| Missing threshold | `Approval threshold not listed` | Do not infer a requirement or equate missing data with no requirement |
| Actual vote share | `59% voted yes` | Show only when supported; keep zero distinct from missing |
| Historical pass rate | `Historical comparison: 69% passed` | Retain sample size, time scope, and comparison limits |

Keep the vote-share label and bar together near the archive footer. Do not
revive the previously rejected isolated percentage in the card header. A bar
represents yes share, not an outcome prediction or a generic success meter.
Do not add threshold markers to historical bars unless the requirement is
independently trustworthy and that additional scope is explicitly selected.

### Official documents

Use a footer such as `View measure · 5 official documents →`, with correct
singular/plural behavior. The count is the number of displayed, grouped
document links already supplied by the public model, not role rows or a global
deduplication of URLs. Composite/shared packets retain current grouping semantics.

- No supported collection: fall back to `View measure →` or a similarly honest
  action, without suggesting documents were never filed.
- Do not add nine role slots or completeness percentages.
- Do not label capture timestamps as filing dates or promise that a live county
  URL serves the immutable bytes captured previously.
- Default to one primary action opening existing details. A separate direct
  documents action is optional scope and requires valid interaction structure.

### Historical comparison

Keep the existing build-time calculation and minimum-sample rule. This work
changes presentation, not the comparison's population or arithmetic.

Illustrative anatomy using the reviewed Upland record, not a fixed-height mockup:

```text
MEASURE A

Upland Unified School District
Bond measure · Requires 55% yes

Historical comparison
69% passed · 87 outcomes since 1998

View measure & documents →
```

Keep a concise visible section-level explanation, for example:

> Recorded pass/fail outcomes for the same county and measure type. Voting
> rules and purposes vary. Not a prediction.

Put longer methodology and historical-data caveats behind an accessible
disclosure. Do not remove the distinction between county-sourced current
thresholds and derived historical threshold fields. Unsupported comparisons
are omitted naturally, not filled with invented values or conspicuous empty boxes.

## 5. Visual specifications to prototype

These are starting values to evaluate against real content, not CSS requirements
to enforce at the expense of readability.

| Property | Starting recommendation |
|---|---|
| Card surface | One light surface, distinguishable from the warm page background |
| Border | One subtle neutral border |
| Corner radius | Approximately 8px |
| Internal padding | 16–20px, adjusted for narrow screens |
| Spacing scale | 8, 12, 16, and 24px |
| Primary heading | Local 17–18px; evaluate 17–19px for other variants |
| Identifier | 13–14px, restrained emphasis |
| Supporting body | 14–15px initially; comfortable line height around 1.45–1.55 |
| Type and threshold | 13–14px |
| Context and attribution | At least a readable 13px starting point; satisfy contrast |
| Text palette | Dark primary text and stronger secondary text; verify all combinations |
| Shadow | Restrained; no heavy static elevation across the entire grid |
| Motion | Consistent, subtle, and disabled under reduced-motion preference |
| State styling | Clearly labeled outcomes; neutral threshold and yes-share treatment |

Use relative units and allow enlargement. Small bold text still needs normal-text
contrast. Gold is an accent, not an exemption from contrast requirements.

Remove automatic italic styling from upcoming summaries. Simplify combinations
of purple rails, gold borders, gradients, and repeated upcoming badges. A section
can communicate shared status, but cards reused outside that section must still
have sufficient context. Preserve textual meaning rather than relying on color.

Within a row, use consistent identity and footer alignment. Use flexible content
areas rather than brittle fixed heights. Avoid masonry for these comparable
records. Missing fields should not produce malformed alignment or fake content.

## 6. Responsive layout and carousel behavior

### Local and statewide carousels

- Retain the chosen carousel interaction model.
- Move arrows below local cards on mobile and group them with the position count.
- Recover the width consumed by redundant nested padding. At 390px, prototype
  a local card near the available 350px content width, rather than about 234px.
- A partial next-card preview is optional; do not sacrifice readable width to
  force it at 320px.
- Support touch swiping and snapping while retaining visible previous/next controls.
  Verify that vertical page scrolling still works normally.
- Prefer browser-native scrolling when it materially simplifies touch and focus
  behavior. Do not build a second carousel engine without checking the shared one.
- Keep counters, disabled end controls, viewport resize, county changes, and
  focus behavior synchronized with actual visible cards.
- Do not auto-advance.
- Essential headings, requirements, and comparison qualifications may wrap.
  Do not solve overflow by shrinking text below the chosen readable scale.
- Keep the compact visible scope statement. Reduce explanatory bulk through a
  disclosure, not by removing the coverage qualification.

### Archive grid

- Compare four columns at 1440px to the current five.
- Use two columns where both cards retain a readable width; otherwise use one.
- Keep a single column on narrow phones.
- Preserve the existing list view as the denser alternative.
- Anchor result/footer groups consistently; do not force summaries into an
  unreadably small height simply to equalize cards.
- With the default 12 results, a four-column layout gives three complete rows.
  Treat that as a useful secondary benefit, not the main reason for the change.

## 7. Interaction and accessibility contract

All card variants should behave consistently for pointer, keyboard, and touch.

- Use a native button for a modal action or a real link for navigation. A native
  heading button inside an article is one option; preserve useful heading/list
  structure instead of wrapping arbitrary rich markup in an invalid button.
- Make the main action's clickable region generous and its name specific to the
  measure. Do not rely on an onclick-only div.
- Avoid nested interactive controls. If more than one action is required, use
  an article with separate valid controls and clear focus order.
- Provide visible focus, hover, and pressed states. Focus must not be clipped by
  the carousel viewport or hidden under the sticky header.
- Opening details must select the correct existing record; closing must restore
  focus to its trigger when it remains present, or a logical fallback otherwise.
- Hidden offscreen carousel cards must not create an unexplained keyboard journey.
  Reveal a focused item or manage focusability consistently.
- Preserve keyboard activation and support for assistive technology when changing
  the current local-card implementation.
- Keep text contrast at least 4.5:1 for normal text; verify applicable large-text
  and non-text criteria separately.
- Target roughly 44px mobile navigation controls for comfort. Do not misreport
  current 34px controls as automatically failing WCAG 2.2's 24px minimum criterion.
- Check 200% text enlargement and reflow at an effective 320 CSS px width.
- Under reduced motion, eliminate nonessential transforms/transitions.
- Use labels alongside color for outcomes; never make color the only status signal.
- Explanatory disclosures must work without hover and retain a visible short caveat.

These checks cover the changed components; they are not a claim of whole-site
WCAG conformance.

## 8. Work packages, dependencies, and effort

Estimates are planning ranges, not commitments. Agent hours mean focused work,
debugging, and verification, not guaranteed unattended wall-clock throughput.
Reestimate after the first prototype and check the current election work before
scheduling. The project budget remains about 10 Igor-hours/week; do not consume
it all with this design work.

| Package | Deliverable and exit condition | Agent effort | Igor involvement |
|---|---|---:|---:|
| A. Reorient and establish baseline | Current code/data inspected; six representative records selected; baseline screenshots and field mapping recorded | 1–2 hours | None unless priorities changed |
| B. Comparison sheet | Current/proposed local cards at desktop/mobile widths; shared style direction demonstrated on archive/statewide samples | 3–5 hours | 30–45 minutes to assess real examples |
| C. Implement local variant and container | Readable mobile geometry, threshold/context labels, document footer, and working controls on isolated output | 3–6 hours | 15–30 minutes for a focused check |
| D. Unify archive/statewide variants | Clean title presentation, wider archive grid, aligned result/footer group, restrained variants, preserved previews | 3–6 hours | 20–30 minutes |
| E. Accessibility and integration | Edge-case matrix passed; model/output preservation checked; reviewable release candidate | 2–4 hours | 20–30 minutes |
| F. Release when scheduled | Current release process completed; deployed output verified; handoff updated | 1–2 hours | 10–20 minutes, subject to then-current instructions |

Total planning range: approximately **13–25 agent-hours**, **1.5–2.5 hours of
planned Igor involvement**, plus roughly one hour of human contingency. Do not
add this to an already full operational week without making an explicit tradeoff.

### Checkpoints

- [ ] A: current baseline and content mapping recorded.
- [ ] B: one coherent direction is reviewable with real examples.
- [ ] C: local mobile improvements work without weakening scope/context wording.
- [ ] D: all three variants look related and keep their useful information.
- [ ] E: interaction, responsive, and data-preservation checks pass.
- [ ] F: publication and post-deployment verification completed when scheduled.

Do not treat these review points as repeated permission requests for routine
implementation choices. Follow the active user instructions. Their purpose is
to make design tradeoffs concrete before changes spread across the generator.

### If time becomes constrained

The minimum useful slice is local mobile width, readable typography/contrast,
clear threshold wording, document availability, and accessible interaction.
Keep necessary context and scope qualifications. Archive title normalization,
grid changes, and optional touch refinements can be staged later. Do not ship a
partially converted carousel whose controls and visible state disagree.

## 9. Implementation map and integration safeguards

Start in [scraper/src/website/generator.py](../../scraper/src/website/generator.py):

- Local card CSS under `.upcoming-local-band`, including `.local-measure-card`,
  `.local-card-jurisdiction`, `.local-card-context`, and threshold classes.
- `createLocalMeasureCard`, `getLocalThresholdDisplay`, `getLocalMeasureType`,
  and `handleLocalCardKey`.
- Shared/general `.measure-card`, `.card-title`, `.card-summary`, `.card-meta`,
  `.vote-bar`, and the hero/featured/pending variants.
- `createCard`, `getCleanTitle`, `buildDisplayTitle`, and their existing callers.
- Carousel functions including `getResponsiveCarouselItemsPerView`,
  `setCarouselTrackPosition`, and local/hero update functions.
- Existing `viewMeasure` and modal close/focus behavior.

Also inspect:

- [CLI generation boundary](../../scraper/scripts/generate_site.py).
- [Local historical-context calculation](../../scraper/src/website/local_measure_context.py).
- [Document model and grouping](../../scraper/src/database/measure_documents.py).
- [Upcoming rendering tests](../../scraper/tests/test_website_upcoming.py).
- [Document rendering tests](../../scraper/tests/test_website_documents.py).
- [Paired-output contract tests](../../scraper/tests/test_website_output_contract.py).
- [Local-context tests](../../scraper/tests/test_local_measure_context.py).

Use scoped selectors and a small shared set of card tokens. CSS-name collisions
have broken other panels before. Do not undertake a generator refactor merely
because it contains duplicated historical styling.

Preserve integer `id` through the CLI field whitelist and model boundary. Card
actions must use the existing identity mechanism; a count of rendered cards
cannot prove correct attachment to Finance or documents.

Use isolated output for implementation review. The root `index.html` and
`measures-data.json` are the published pair; the `scraper/` mirror is ignored.
Do not edit generated root HTML as the implementation or stage that mirror.

For a later full build, preserve the real enrichment inputs. A successful
generator exit alone does not prove semantic context, Finance, recommendations,
or Insights survived. Compare the candidate to the current baseline and inspect
warnings for degraded generation.

The F1 release verifier compares HTML to a sealed reviewed reference. A deliberate
card redesign will not match the September 8 HTML reference. **Do not weaken
that verifier or reuse its old approval evidence to make the redesign pass.**
Use a fresh candidate and an appropriate current comparison. This UI task should
not require rerunning registrar loads or changing production database contents.

At publication time, check active workflow triggers and current user scope.
The F1 release used `[skip ci]` because ordinary pushes could start scraping.
Do not assume a future UI publication is permission for an unrelated capture.
Compare committed and served bytes with any Git line-ending normalization
explicitly accounted for, following the current release procedure.

## 10. Verification matrix and acceptance criteria

### Representative content

Use current real records, recording stable identities in the comparison sheet.
The following are useful starting examples rather than permanent fixtures:

| Case | What it exercises |
|---|---|
| SB Measure A, Upland Unified School District | Standard local bond, 55% requirement, historical comparison |
| SMC regional transit measure without a letter | Honest fallback identifier, long jurisdiction, majority requirement, shared documents |
| SMC Measure AA | Long type label and a card without supported historical context in the reviewed build |
| A statewide measure with a long official title | Identifier/title separation, wrapping, summary preservation |
| Alameda historical Measure A, 2024 | Repetitive display title, substantive summary, recorded passing result |
| Alameda historical Measure CC, 2024 | Failed outcome with a nonzero yes share |
| Prop 50, 2025 | Long title and imperfect source-preview content |
| Prop 27, 2022 | Correct identity and Finance detail integration |

Add controlled edge cases only where real records do not cover them. Mark
synthetic content as synthetic. Include missing/zero vote share, unknown
threshold, missing summary, absent documents, one document, composite packets,
long names, and absent comparison data.

### Visual and interaction matrix

- Desktop 1440px; intermediate 1024px and 768px; mobile 390px and 320px.
- Default, hover, focus, pressed, disabled navigation, and open/closed details.
- First, middle, and last carousel positions; county switch; viewport resize.
- Long content and missing fields; 200% text enlargement; effective 320px reflow.
- Keyboard-only use, touch/vertical scrolling, and reduced-motion preference.
- At least Chromium plus one available independent browser engine before release;
  record an unavailable browser as an untested limit rather than implying coverage.

### Must pass

- [ ] Identify a measure and its jurisdiction/scope without opening it.
- [ ] Essential local names, threshold labels, and comparison qualifications are
      readable at narrow widths; no new horizontal page overflow.
- [ ] No arbitrary hard height clips content under enlargement.
- [ ] Text colors meet the relevant contrast criteria in actual backgrounds/states.
- [ ] No duplicate identity text in normalized headings; valid proper names survive.
- [ ] Summaries remain available and existing source/full-text fields are unchanged.
- [ ] Requirement, actual yes share, and historical pass rate have distinct labels.
- [ ] Document counts equal the displayed grouped links for the selected measure.
- [ ] Null context/threshold/result states remain honest; zero is not treated as null.
- [ ] Card activation opens the correct record; Finance and document panels work.
- [ ] Focus is visible and restored sensibly; no inaccessible click-only variant remains.
- [ ] Carousel controls, counter, focus, and displayed cards agree after every state change.
- [ ] No new JavaScript page errors during the exercised flows.
- [ ] Unrelated public fields and enrichment payloads are preserved; intentional
      presentation differences are documented.
- [ ] Source implementation and generated candidate agree; required paired-output
      behavior remains intact.

Use browser measurements and screenshots for layout, and focused tests for
meaningful behavioral changes such as title normalization, document counts,
null handling, and keyboard activation. Do not write tests that merely assert
chosen pixel values or duplicate the CSS implementation. Run the relevant
existing tests once changes are complete; expand testing when failures or new
coupling justify it.

For a brief human check, ask whether a reader can find the applicable
jurisdiction, identify what a percentage means, and discover official documents.
If readers interpret the historical rate as a forecast or the county selection
as a personalized ballot, revise the wording/hierarchy before adding polish.
Do not report a small informal check as statistically validated usability evidence.

## 11. External references and what to borrow

Sources were inspected during the September 13 review. The proposed sizes,
colors, and column counts are design judgments, not specifications mandated
by these references.

- [CalMatters 2024 proposition guide](https://calmatters.org/california-voter-guide-2024/propositions/):
  separates proposition identifiers, explanatory headings, brief descriptions,
  and an explicit action. Borrow the hierarchy rather than its brand treatments.
- [California Secretary of State proposition index](https://voterguide.sos.ca.gov/propositions/):
  keeps identification consistently positioned beside official titles. Use as
  an identification reference, not a contemporary visual template or proof of
  CalBallot's current source completeness.
- [BallotReady](https://www.ballotready.org/): address-based personalization
  makes geographic relevance explicit. CalBallot should clearly communicate its
  county scope without adopting a personalization claim its data cannot support.
- [USWDS card component](https://designsystem.digital.gov/components/card/):
  recommends actionable cards, nonredundant content, restrained styling, and
  meaningful heading/list structure.
- [NN/G: Cards, UI-component definition](https://www.nngroup.com/articles/cards-component/):
  explains cards as summaries leading to detail and the importance of predictable
  layouts when comparing repeated attributes.
- [W3C: Contrast minimum](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html):
  normal text generally requires 4.5:1; large text has a separate threshold.
- [W3C: Target size minimum](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html):
  WCAG 2.2 specifies a 24 CSS px minimum criterion with exceptions. A 44px
  comfort target here is a design recommendation, not that criterion's wording.

## 12. Decisions and exact restart task

### Reasonable defaults for the implementation agent

Use the shared visual family, wider mobile cards, neutral approval labels,
stronger contrast, document availability, retained summaries/context, and
accessible actions described above. Resolve routine spacing and markup choices
against the examples and acceptance criteria.

### Bring to Igor only when the concrete examples reveal a meaningful tradeoff

- Does the increase from roughly 120px to a readable content-driven local card
  occupy too much vertical space in the actual page context?
- Is the four-column archive preferable to five when comparing the same records?
- Is one card action sufficient, or does direct access to the document panel
  merit a second control and its additional interaction complexity?
- Should a larger source/content-quality problem be scheduled separately rather
  than worked around in the card renderer?

Do not reopen whether to keep summaries, the carousel, or historical comparisons
without a new substantive reason. The user has already expressed those preferences.

### First task when this work is selected

> Read this plan and the current working list. Check what changed since the
> September 13 review. Prepare a standalone comparison sheet using six real
> records: three local cases (standard, long/no letter, and missing context),
> one statewide case, and two historical cases (passed and failed). Record
> their stable identities. Show the current and proposed cards at desktop and
> mobile sizes, including the carousel controls and enough surrounding page
> context to judge density. Implement only an isolated prototype at this stage.
> Preserve real wording/data and mark any proposed editorial text explicitly.
> Include typography/contrast measurements, the 320px edge case, and the proposed
> one-action interaction model. Recommend one direction and explain the remaining
> tradeoffs. Do not alter production data, generated root artifacts, or deployment.

### Resume record

| Item | Current state |
|---|---|
| Aesthetic review | Complete, September 13, 2026 |
| Durable action plan | Complete, this document |
| Prototype | Not started |
| Implementation | Not started |
| Browser acceptance of redesigned cards | Not started |
| Publication | Not started |
| Next bounded action | Package A/B: baseline and comparison sheet, when scheduled |
