# Direction A: post-election design review

**Verdict: ready with changes.** Keep the statewide slate and county directory. The October handoff is not ready to implement verbatim: it assumes explanatory content, pre-election cards and two counties. Revise the content/state contract and acceptance checks below before implementing the affected chunks. This approves the direction, not a release or a claim that results data is ready.

Reviewed November 12, 2026, on `phase0-election-status` at `375a2387`. Scope: the proposal, overview/component mockups and supplied screenshots; completion-plan Phases 3/3b and sections 5/6/8; current generator, county content, historical context, election-status code and related build/navigation paths. The proposal/mockups are pre-existing untracked files in this checkout. No code, data, checklist or published artifact was changed; no database was opened and no live link was checked.

## Evidence and limits

I copied the mockup directory into `C:\Users\igorg\AppData\Local\Temp\calballot-layout-review-zm0kbwr5\mockups` and rendered that copy in Playwright Chromium. Requests were fulfilled from scratch files under a synthetic `layout.test` host; all other requests were aborted, including Google Fonts. These are fallback-font measurements, not exact reproductions of the supplied screenshots. Local screenshots and `review-checks.json` are in that scratch directory and are not committed.

| Re-run | Observed |
|---|---|
| A, Grid and List, at 1440, 390 and 320 CSS px | All six had document scroll width equal to viewport width; the selected San Mateo panel contained 29 visible entries. This checks page overflow, not full accessibility or all future content. |
| San Mateo local-section height at 390 px | Grid: 8,630.7 px; List: 4,526.9 px. At 320 px: 9,969.7 and 5,368.3 px. Results will add content. |
| Find `R` | One of 29 entries, as expected. |
| Synthetic designation `SOS` | Changed one scratch DOM entry's designation to `SOS` and its search text to `city of example bond facilities improvements`. Searching `SOS` returned zero. This demonstrates the search algorithm's three-letter defect, not the presence or identity of a particular live measure. |
| County switch from `?county=San%20Mateo` to San Bernardino | Visible panel changed; URL still named San Mateo. Switching back retained the `R` search and one visible match, while the county announcement said “Showing 29 San Mateo County measures.” |
| Components sheet at 320 px | Rendered without document overflow. Its existing states do not supply the required post-election result designs. |

I also inspected the supplied desktop List, phone Grid and current narrow-card screenshots. I did not re-run the production build, Python suite, non-Chromium browsers, 200% text checks, or a 53-county/68-record fixture. Existing screenshot evidence is useful but does not establish acceptance for the new result anatomy or scale. The roughly 460 records/53 counties/LA 68 figures are the review brief's design targets, not a census independently verified here.

## Severity-ranked findings

### Demonstrated mockup defects

**F1 — P2: designation search stops working beyond two characters.** Evidence: `docs/design/measure-layouts/assets/mockups.js:46` chooses either exact designation matching for length <= 2 or substring matching against `data-search`; the latter omits the designation (`a-slate-directory.html:197`). The synthetic `SOS` reproduction above returned zero. Fix: match the normalized designation at every length, including an optional “Measure ” prefix, and search jurisdiction, official subject/question and type independently. Rank exact designation matches first. Do not reserve every short input exclusively for letters; that prevents short place prefixes from working.

**F2 — P2: county navigation and its announcement disagree with visible state.** Evidence: `assets/mockups.js:23` only changes panels and the total-count announcement. The reproduction retained the old URL and later a hidden filter. This also contradicts the reset rule in `docs/plans/measure_layout_design_proposal.md:437`. Fix: establish one route state for county, search and view; reset local search on county change, serialize county and search, and derive the announcement from the actual filtered count. Implement restoration without adding history entries. These are conceptual-mockup defects, not claims that the mockup script runs on the live site.

### Implementation blockers and design risks confirmed by source inspection

These are gaps in the proposed implementation contract, not newly demonstrated production regressions.

**F3 — P1: post-election results and multi-county scope are missing from the handoff.** Evidence: the proposal removes repeated status/source labels (`measure_layout_design_proposal.md:106`), keeps modal tabs unchanged (`:335`), and proposes regional metadata only for ID 12442 (`:480`). Current `scraper/src/website/election_status.py:96` distinguishes calendar statuses and recorded outcomes; it does not model unofficial/certified observations. `:281` attaches the checked results-link projection only to calendar-status rows. Simply adding a “Passed” badge cannot supply certification or result provenance. Fix: implement the six-state presentation contract in answer 2 from Phase 2 observations, keep status visible, and carry source/as-of/scope through cards, modal and static pages. Generalize multi-county membership and combined-result provenance beyond one ID. A school district can be both a school jurisdiction and multi-county; those are separate dimensions.

**F4 — P1: copying the content adapter would exclude the new question-only measures.** Evidence: `docs/design/measure-layouts/tools/mockup_data.py:152` selects locals only when `county_guide` exists, then reads its explanation. `scraper/src/website/county_content.py:59` requires a question, explanation and sources; its host/listing maps at `:16` cover SB/SMC. The proposal's fallback at `:419` says “Not reviewed yet” and promises documents. That conflicts with the November 11 decision to defer explanations and does not guarantee a document exists. Fix: select records by election and scope, independently of editorial enrichment. Add a sourced official-question presentation path; retain the existing reviewed explanation package and its validation for records that have it. Do not weaken that validation merely to admit new counties.

**F5 — P1: date selection and carousel removal must preserve the status lifecycle.** Evidence: `generator.py:50` derives upcoming scope from year; `:9996` selects the current slate with `year == 2026`. Meanwhile `refreshCalendarStatuses` (`:11241`) re-renders through `displayHero()` and accesses carousel state. Removing the carousel helpers as proposed in section 7.7 without updating that path would leave stale references. Fix: migrate Python and browser selection to the explicit selected `election_date`, retain completed measures in that election, preserve the strict-build membership checks and Pacific-date refresh behavior, and replace the refresh/render dependencies together. Clock progression must never certify an observation.

**F6 — P2: the proposed county history table is not the requested comparison model.** Evidence: `local_measure_context.py:137` groups by county/category, not required vote and jurisdiction kind; `:157` discards cohorts below five entirely. The proposal's section 7.7 step 4 would promote the existing counts without the Phase 1b repairs. Fix: gate the new table/statistics on repaired data and reviewed cohort definitions; retain small-cohort records separately from statistical eligibility. Do not pin “89 of 102” as a perpetual correctness test. Counts still communicate a rate even without a percent sign.

**F7 — P2: two proposed classification rules would obstruct wider coverage.** Evidence: `mockup_data.py:111` defaults every unrecognized jurisdiction to “special”; proposal `:425` fails the entire build for an unmapped display type. Neither is a safe generalization from 49 records. Fix: use reviewed jurisdiction kinds, allow an explicitly unclassified group, and fall back to the source's verbatim type when only a short display label is missing. Exclude unreviewed types from comparison cohorts and report them for review. Continue failing on actual identity, provenance or result-integrity violations; a missing cosmetic abbreviation should not block a legitimate release.

The remaining choices below—compact phone rows, control placement, tab ordering and finance emphasis—are design recommendations, not demonstrated defects.

## Answers 1–8

### 1. Direction A at the new scale

Yes. The county boundary keeps the directory manageable; it should never render all roughly 460 measures as one undifferentiated list. Four familiar jurisdiction groups still help, with reviewed classification and an unclassified fallback. Multi-county scope is a visible qualifier, not a fifth mutually exclusive jurisdiction type.

The first usability limit is **phone length**, already substantial for 29 entries. At larger county sizes, reliable find-by-place becomes essential. The picker is an easy native-control substitution; grouping becomes a data-quality problem if guessed from names. Neither a missing explanation nor an unrecognized category may hide a measure.

Put county selection, find, filtered/total counts and group jumps immediately before the directory. Keep a direct “Local measures” jump above the statewide slate. Search all loaded entries, including any collapsed entries. Replace the proposal's approximate 40-record trigger with a specified rule: a group with more than 40 entries initially shows 30 in browse mode, with “Showing 30 of N — Show all N”; a search shows all matching entries. A direct target must expand its group. No virtualization is needed at 68 entries. Test mixed groups and one dominant group, not just 68 evenly distributed rows.

### 2. Result anatomy, thresholds and multi-county measures

Use the same result projection everywhere. Card order: **designation and jurisdiction/subject → result state and scope → yes percentage beside the approval rule → concise question/summary → secondary documents or finance**. State must be text, not color alone. Keep the election date in the section context and every standalone page; distinguish dates when records from multiple elections appear together.

| State | Card | Modal and static page |
|---|---|---|
| Results pending | “Results pending”; source-backed approval rule; no fabricated zero, vote bar or outcome | Explain that a result has not been imported; show a checked official-results link when available. Absence of a link must not hide the record. |
| Unofficial | “Unofficial · as of [source time]”; “52.3% yes · Needs 55%”; “2.7 percentage points below threshold” if supported | Yes/no counts, denominator, exact rule, scope, observation time and source. No Passed/Failed label or outcome-colored badge. |
| Certified passed | “Passed · Certified”; yes percentage and rule; linked result source | Certified observation, counts, margin, certification/report dates when known and source. |
| Certified failed | “Failed · Certified”; same supporting facts | Same detail and provenance as passed; no different evidentiary standard. |
| Withdrawn | “Withdrawn”; identity retained | Sourced withdrawal information. Do not present it as a failed vote or include it in outcome cohorts. |
| Historical result unknown | “Result unknown”; retain known identity/date | State what is unavailable. Preserve independently known counts if present, with scope/provenance; do not turn them into an inferred outcome or a pending current election. |

Existing historical Passed/Failed records do **not** acquire a “Certified” label merely because `passed` is populated. Use “Recorded result” unless certification provenance supports the stronger label. Upcoming/Election day remain supported for future/date-boundary use; the post-election design must not remove P0.1 behavior.

Use “Needs a majority,” “Needs 55%,” or “Needs two-thirds” only from a reviewed source-backed rule. Otherwise use “Approval requirement not listed.” Majority means more than half; two-thirds is not a rounded 66.67% cutoff. Calculate margins from unrounded, compatible data and display rounding consistently; never derive an official Passed/Failed label by comparing two rounded display numbers. Near-boundary values need sufficient precision or an explicit rounding note. Do not infer statewide thresholds from a familiar form of measure.

For multi-county measures, show **“Combined district result” first**, with the district/participating counties stated. Under it, label “San Mateo portion of this district” and the equivalent county rows. A county portion never gets its own measure-wide Passed/Failed badge. If only a portion is available, say “Combined result unavailable” and label the available portion explicitly. Do not average percentages or sum mismatched/incomplete observations. A combined result needs an authoritative consolidated source or a validated aggregation of compatible, complete county observations.

Use a canonical contest key plus county memberships; preserve existing public IDs/permalinks. List the same contest in each applicable county but count it once in statewide/cohort totals. State when a displayed count is county listings versus unique contests. Do not imply that every county resident voted on every listed district measure.

### 3. Cards without explanations

Use the official question, labeled **“Official question”**. Grid can show a word-boundary excerpt with an ellipsis and access to the full verbatim question. The full question belongs near the top of Main and the static page. Do not run the explanation's first-sentence regex over ballot questions: a single long sentence can contain the whole proposition, and an excerpt can omit a condition that changes its meaning.

Prefer a source-provided short subject for compact rows. When none exists, retain a short, visibly excerpted question rather than showing only a generic type and threshold; two measures from the same city must remain distinguishable. If an excerpt misleads by dropping a material condition, show more or use an expandable full question. Do not invent a neutral-sounding summary. Preserve reviewed explanations where already available, with their existing label.

A genuinely unavailable question gets “Official question unavailable” with whatever source access actually exists. Do not say “Not reviewed yet,” promise future explanation work, or claim official documents are in the guide without verifying their presence. Result visibility does not depend on question or explanation availability.

### 4. County picker, URLs and Back

Use a **labeled native select**, alphabetically ordered, with county counts. Fifty-three options are manageable with native keyboard/type-to-select behavior. A custom typeahead adds accessibility and restoration work without demonstrated need; consider it later after testing. Keep the within-county find field separate. Distinguish “not yet loaded” from “no measures”; the brief's 53-county target is not current verified coverage, and uncovered counties must not silently appear to have zero measures.

Make routing required, not optional. For example:

`?election=2026-11-03&local_county=san-mateo&local_q=R&view=list`

Use stable county slugs and namespaced local parameters so they do not collide with full-catalog filters. Preserve unrelated query parameters and existing `#full-catalog`/`#m=<id>` links. County/election changes create history entries and clear dependent local search/expansion state. Typing can replace the current search entry after an initial search-state transition, avoiding a Back entry per keystroke. View changes preserve the chosen county and search. Popstate restores controls, visible rows and announcements without writing history again.

The heading remains a real static-page link. An ordinary unmodified activation opens the modal with `#m=<id>`; modified clicks and new-tab actions follow the actual link. Push an in-app modal-open history entry so Back closes it and restores the directory. Close/Escape restores the opening route and focus; direct-entry modal links need a safe close fallback that does not send the reader off-site. A record outside the selected filter may open directly without silently clearing the filter. If the opener disappeared during a refresh, focus the relevant directory heading. Preserve group anchors and sticky-header offsets.

This is deliberate work beyond the current implementation: `generator.py:14917`/`:15356` use a stored return URL and `replaceState`, while the `popstate` handler at `:10842` restores view/page. The mockup's redundant whole-card `.click()` must not swallow modifier keys, text selection or a separate source link. Keep one primary heading link, but allow an independently accessible official-result source link.

### 5. Results and comparisons tab

Keep a compact result summary **above the modal tabs**, so phone users see the state, combined-versus-portion scope, yes percentage/rule, source and as-of information without discovering a new tab. Add “Results & comparisons” after Main, before Research and Finance. Four tabs must wrap or otherwise remain fully accessible at 320 px; do not hide the fourth tab offscreen. Static pages get the same result summary and a linked section, not simulated tab-only content.

Within that tab/section, use this order:

1. Result and its provenance, with multi-county combined/portion breakdown immediately adjacent. For propositions, county-versus-state figures also belong near this result context.
2. Ballots cast and roll-off, only where a compatible contest-level denominator exists. Countywide ballots cast are not automatically the denominator for a district contest; missing counts are not zero or historical turnout.
3. Same-place history, using reviewed identities rather than a loose string match across renamed or redistricted jurisdictions.
4. Similar historical measures: reviewed type, jurisdiction kind and required vote; explicit geography and years.
5. Same-election comparisons within supported coverage. Statewide same-year comparisons remain withheld under November 11 decision 5. A 2024 comparison must be explicitly labeled as a different election, not a substitute in the “same election” slot.

The original order puts multi-county scope too late: readers need it before interpreting counts or denominators. On phones, show the result summary in full and make secondary comparison sections collapsible; explanatory provenance can expand, but the source link and observation status cannot disappear.

For **n < 5**, list the eligible records and explain the small sample. Do not show pass rates, median margins, percentiles or ranks that imply stable comparisons. At n = 0, explain the eligibility/coverage limit rather than suggesting no earlier measures existed. Every displayed statistic needs n, definition, years and links to its underlying records. Exclude the subject itself, unofficial outcomes and duplicate county portions. Never silently relax matching criteria to reach five.

### 6. Proposal section 8 decisions

1. **Replace both carousels: agree.** The slate and directory improve direct access and browser find. Retire each carousel's event/state dependencies with its replacement.
2. **Accept long phone Grid as-is: revise.** Prefer option (b): compact local rows on phones, retaining identity, a meaningful subject/question excerpt and result facts. Grid may remain richer on wider screens; preserve the explicit shared Grid/List choice and keep their phone differences modest. Do not silently change a saved preference. Statewide keeps its slate. Find/group jumps and explicit expansion still matter; compact rows alone do not solve 68 entries.
3. **County history table: agree conditionally.** It is secondary context below the directory, preferably collapsed on phones. Ship only after Phase 1b and the new cohort contract; no broad category aggregate presented as a matched comparison. When constituent measures require different thresholds/kinds, they do not share one comparable row merely because the category label matches.
4. **Statewide money: agree, subordinate to results.** Keep support/opposition contributions as secondary facts, with their reporting date and non-additivity warning. Do not let money displace the outcome or masquerade as votes. “No committee identified” is clearer than “None reported” for that specific status; distinguish it from zero, missing data and unimported data. Use per-side/per-record as-of information where dates differ, not a hardcoded October 6 legend. Preserve existing finance totals and access to exact values; no new aggregation is needed for this layout change.

### 7. Reviewable implementation chunks

**First chunk: date-aware local directory for currently loaded measures.** Ship a true improvement for the existing coverage before claiming all 53 counties. Include the native picker, deterministic grouping/fallback, find, compact phone rows, real links, URL/focus behavior, sourced question fallback and the existing result-status contract. Add no new inferred results or history statistics. Introduce the date-selection change consistently across Python/browser consumers; unchanged current statewide membership is a preservation requirement. Namespace new CSS as the handoff recommends.

Acceptance for that first chunk:

- Reconcile the selected election against its loaded-record manifest: every eligible local ID appears once per county membership, independent of `county_guide`; the current fixture has all 49 locals. No same-year/different-election leakage, and recorded outcomes do not disappear from the selected election. Withdrawn records remain findable and labeled.
- Use fixtures for 53 county options, 68 local entries, a dominant group > 40, a question-only record, an unmapped type, a three-letter designation, repeated letters across jurisdictions and multi-county membership. These are scale tests, not coverage claims. Search includes hidden entries and full question text; direct targets expand as needed.
- Verify deep links, reload, Back/Forward, direct `#m=<id>`, modified clicks, keyboard selection, Escape and focus return. Preserve full-catalog navigation and finance/document access. Calendar transitions refresh an open modal and directory without losing county, search or focus; retain the P0.1 cross-midnight/browser-clock checks.
- Render 1440/1024/768/390/320 px in both views, enlarged text, long official questions and long result/source labels. No page overflow, clipped essential facts or obscured focus. Check actual contrast and accessible names. Test a non-Chromium engine or explicitly record the gap before release.
- On a scratch build using a SQLite-backup copy if needed, compare against the branch baseline captured before the chunk. **All historical and all statewide static pages remain byte-identical for this local-layout chunk.** Statewide JSON values, guide content, finance/research payloads, IDs and the current 14-member slate remain unchanged. Compare JSON by ID/field as well as artifact bytes; no historical row changes. If genuinely necessary new current-local fields are introduced, enumerate them in a narrow reviewed diff manifest. Account separately for established volatile `last_seen_at` regeneration; do not make it a blanket exemption.
- Run relevant generator/document/navigation/status tests and the browser checks against the scratch build; save the artifact diff manifest with the review. Do not require unrelated known baseline failures to be fixed as part of a layout-only change, but demonstrate any claimed baseline failure rather than assuming it.

Subsequent chunks:

| Chunk | Shippable scope and gate |
|---|---|
| 2. Statewide slate | Replace the 14-proposition carousel with number index and Grid/List; retain all content and finance semantics. Update calendar refresh dependencies atomically. Static pages stay unchanged. Verify every ID/link and finance absence state. |
| 3. Observation-based result presentation | After Phase 2's data contract is ready, add all six states consistently to cards, modal and static pages; include combined/portion provenance, thresholds and as-of/source facts. Fixture-test each state and missing-data case. Keep historical certification claims unchanged. Explicitly enumerate current pages/JSON fields allowed to change. |
| 4. Results details | Add the accessible tab/static section and compatible-denominator roll-off. Shared projection and parity checks prevent modal/static disagreement. Missing optional counts must not block a valid result release. |
| 5. Phase 3b history | After Phase 1b, add same-place records, matched cohorts, small-sample record lists and the revised county table. Audit cohort membership, deduplication, exclusions and source links; do not mix historical repairs into a layout preservation diff. |
| 6. Phase 3b election comparisons | Add covered county comparisons and sourced proposition county/state context. Keep statewide same-year aggregates disabled until decision 5's coverage condition is met. |

Chunks 3/4 can be developed against fixtures, but production results must wait for their evidence. Every chunk needs its own artifact preservation gate. Later chunks may intentionally change the relevant current static pages; use an explicit ID/field allowlist, not “all intentional HTML changes.” Recompute baseline counts as coverage expands rather than treating 12,309 historical pages or 63 current pages as permanent constants.

### 8. Corrections to the section 7 handoff

In addition to F1–F7 and the revised slice order:

- **7.3:** replace the universal explanation-first-sentence rule, hard failure on display labels, and fixed-date finance copy. Keep verbatim source wording and reviewed thresholds. A reviewed short-label/form mapping is presentation metadata, not a result rule.
- **7.4:** select is now the initial county control; serialized election/county/search state is required. Specify search, group-expansion and navigation restoration together. Existing mockups do not implement the proposed search reset.
- **7.5:** preserve the real heading link, namespaced CSS and focus requirements. Amend “one link per card” to permit a separate result-source link. Whole-card activation must respect mouse modifiers and interactive children.
- **7.6:** the new data is not just three small display additions. Results need observation status, source/time, counts/denominators and scope; county membership is distinct from jurisdiction kind. Add stable contest identity and question provenance independently of `county_guide`. Thread required fields through the model/build/export path—`scraper/scripts/generate_site.py:128` explicitly whitelists fields—and preserve `id`. Do not blindly transfer `mockup_data.load()`'s editorial-content selectors or fixed 14/49 assertions into production.
- **7.7:** modal/page content changes are now required, not optional header polish. `build_measure_pages.py` and shared renderers belong in the result work. Remove carousel dependencies without breaking status refresh. Defer the history table until the data and cohort prerequisites hold.
- **7.8:** JSON cannot be universally byte-identical while intentionally adding new presentation fields; define exactly which current fields may change. Conversely, “except intentional HTML changes” is too broad to protect history. Use the per-chunk preservation rules above. Replace fixed first-screen card counts with findability, readable results, keyboard access and no clipping; adding honest result information should not fail a 13-of-14 density target.

**Decision:** proceed with Direction A using these revisions. The first local-directory chunk can ship useful, truthful browsing independently of the deferred comparisons. Neither the October mockups nor this review establishes readiness to publish unofficial/certified results without the Phase 2 evidence.
