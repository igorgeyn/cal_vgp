# Finishing the local measures section

**Date:** November 5, 2026 (E+2). **Revised:** November 7, adding the history repair
(Phase 1b) and the results and comparisons tab (Phase 3b, §6). **Status:** proposed, awaiting
Igor's direction check. **Execution is tracked in the
[checklist](local_measures_checklist_20261107.md)**; Igor said to proceed on November 7.

**Scope as read:** every California local measure on the November 3, 2026 ballot that
CalBallot does not yet carry, about **413 measures in 51 counties**. If only the Bay Area
roadmap was meant (Alameda, San Francisco, Contra Costa), Phases 0-4 still apply and Phase 5
shrinks to those counties.

## 1. Bottom line

Four things shape the job, the first three because the election has happened.

1. **The live site is wrong today.** Every current measure still says "Upcoming", because
   the October status and results work (R2-R5) never ran. `main` has not moved since
   October 8. Fix this first; it is small.
2. **The maintenance wall is gone for this election.** Per-county weekly adapters were
   needed because filings kept changing. The list is now final, so each county needs one
   capture, not a maintained scraper. The earlier verdict that 48 tail counties were
   uneconomic no longer applies to a closed election.
3. **The sources are perishable.** County election pages are still up now but will roll
   over at some unknown point. Capture before anything else that takes time.
4. **The history behind today's cards has errors.** The county pass rates on 40 cards come
   from CEDA rows that store a multi-county measure's county share as its full result and
   that dropped the jurisdiction's name. The raw CEDA files carry both, so a backfill fixes
   this and becomes the base for the comparisons tab.

**Recommended order:** fix the status; freeze the sources and repair the history in
parallel; import results for the 63 measures we already hold; ship the new layout; add the
results and comparisons tab; then load counties in waves. Certified results arrive by
December 3 and close the loop.

## 2. Where things stand (checked today)

| Item | State |
|---|---|
| Git | `main` at `c7dc0efa`, even with origin. Last commit October 8. |
| Live site | Byte-identical to that commit. Footer says "Data last updated October 08, 2026". |
| Status label | "Upcoming" on cards and modals, and baked into static pages (12450, 12473, 12442 checked). |
| Registrar cron | Green October 12, 19, 26 and November 2. SB 106 and SMC 136 artifacts on Nov 2. Not loaded or published. |
| Tests | 180 focused registrar/website tests pass today. |
| Local coverage | 49 measures (SB 20, SMC 29). No other 2025 or 2026 local rows exist; CEDA stops at 2024. |
| Results | No results path exists. Every 2026 row has `passed` null; the loader correctly rejects outcome fields. |
| County history | 40 of 49 cards show a same-type county pass rate (cohorts of 15-105 past measures). Built on CEDA rows with known defects; see Phase 1b. |
| Layout proposal | `docs/plans/measure_layout_design_proposal.md` and `docs/design/` are uncommitted. Its four decisions are unanswered and no Codex review is recorded. |

## 3. How big "remaining" is

| Source | Count | Use |
|---|---|---|
| [Ballotpedia, Oct 21](https://news.ballotpedia.org/2026/10/21/california-voters-will-decide-on-462-local-ballot-measures-in-november-the-second-lowest-number-since-2018/) | 462 measures in 53 counties; none in Alpine, Del Norte, Plumas, San Benito, Sierra | Completeness check, read by a person |
| [Coleman, Nov 4 preliminary](https://californiacityfinance.com/Votes2611prelim.pdf) | "Over 470" measures, 331 tax-related, with county, letter and YES% | Cross-check for tax measures |

The two differ slightly (multi-county counting is the likely cause, unverified), so treat
the target as about 415-425 records until the census settles it.

Verified county counts: Los Angeles 68, Alameda 28, Orange 15. San Francisco 11 is
Ballotpedia's figure. The other 47 counties are unknown until Phase 1. They average about
6 measures each.

Coleman is a usable check: all 35 tax-type measures among our 49 appear in it. Neither
source is a source of record, and neither gets republished.

### Source reconnaissance (small sample)

| County | Finding |
|---|---|
| Los Angeles | 14-page text PDF with all 68 measures, thresholds and full questions, revised Aug 14. **`county_status.md` is wrong** to say LA publishes nothing ahead. November results are `text-results/4348`, with a 9,805-page precinct PDF already posted. |
| Alameda | Clean HTML fragment still live with 28 measures and questions. Thresholds appear present now (four read N/A in August). Packets are scanned. |
| Orange | 15 measures A-O, one PDF each. Contents unverified. |
| San Diego | The "measures" PDF is a calendar and says cities are handled by each city clerk. **A county list may not exist**, so the census must check city sites. |
| San Bernardino results | `results.rov.sbcounty.gov/Results/20261103/` offers `ElectionSummaryReportRPT.xlsx`. |
| San Mateo results | Precinct CSV with vote-method split, all 29 measures, already posted. See the [data assessment](election_data_granularity_assessment_20261105.md). |
| Statewide results | `api.sos.ca.gov/returns/ballot-measures` returns clean JSON. Still unofficial; it reads 100% of precincts while millions of ballots remain. |
| Blocked in August | Santa Clara (403), Contra Costa and Riverside (challenges). Ballotpedia returns an empty 202 to scripts. |

## 4. Phases

Estimates are rough and should be redone after Wave 1. Assumes the earlier 10 Igor-hours
per week; correct me if that has changed.

### Phase 0: make the site true (1 day; Igor 30 min)

- Replace the year-based `isPendingMeasure` with one status rule driven by `election_date`:
  Upcoming, Election day, then **Results pending** after election day. No outcome implied.
  ("Counting votes" was the first idea; it would turn false at certification while the label
  stays until CalBallot imports results.)
- Add official results links: SOS for statewide, each county's page for local.
- Update cards, list rows, modal and the static pages. Those pages bake the label in, so
  this needs a real build and release.
- Stop the county history list naming the county as every record's jurisdiction. Of the 48
  records shown on cards that could be checked against raw CEDA files, 43 are city or school
  measures; Alta Loma, Colton and Fontana school bonds appear as "San Bernardino County". Use
  a neutral label until Phase 1b restores the real names.
- **Exit:** no "Upcoming" on any November 3 measure; preservation gate passes; served
  bytes verified.

### Phase 1: freeze the sources (start now, 2-3 days; Igor 30 min)

- Build a versioned **county source census**, one row per county: listing, results and
  document URLs, access state, format, measure count.
- Build one generic capture tool, not per-county scrapers. It reuses `base.py` politeness
  and the immutable R2 store, and takes a URL list.
- Capture measure lists, documents and results pages. Largest counties first.
- Watch the **November 9 cron**: `smc.py` reads a "past elections" index, so the rollover
  could turn it red.
- **Exit:** the board shows each county's count against the two checklists, plus every
  blocked or list-less county by name.

### Phase 1b: repair the CEDA history (parallel with Phase 1; 2-3 days; Igor 1 hour)

Checked November 7 against the five raw CEDA files on disk (2011, 2015, 2022-2024; 1,770
rows). The parser read each county's share of the vote, not the combined figure, and
skipped the other fields below:

| Defect | Evidence | Raw field that fixes it |
|---|---|---|
| Multi-county measures stored as one county's share | 110 share rows for 51 measures; **30 show the wrong outcome**, 20 of them in 2024. San Joaquin Delta College K passed with 59.2% combined; our Alameda row says it failed at 48.1%. | `Multi_CO`, `Multi_MeasID`, `YES_sum`, `NO_sum`, `Total_sum`, `Percent_sum`, `passfail_sum` |
| No jurisdiction name | `jurisdiction` holds CEDA's code (1 county, 2 city, 3 school) or nothing; titles read "ALAMEDA Measure M" | `PLACE` |
| No ballot question | Empty on every CEDA row. KNOWN_ISSUES #5 calls this a source limitation; the raw files contradict that | `BALQUEST` |
| Threshold only implied | Read from the `pass_fail` suffix | `REQ` (M, F, T) |

Effect on live cards, checkable years only: the San Bernardino GO bond rate moves from 69%
to 71% on 7 cards. Only 15 of that cohort's 87 rows fall in years we hold, so the full effect
is unknown until the other years are checked.

- Re-download the 22 missing CEDA years (1998-2010, 2012-2014, 2016-2021) and check each has
  the same columns.
- Backfill keyed on CEDA `MeasID` (our `measure_id`). Never change `id`: record links, static
  pages and finance joins depend on it.
- Measure-level vote fields carry the combined result; the county share moves to its own
  columns. Each multi-county measure counts once in every statistic. Whether share rows
  become `duplicate_type='county_portion'` or stay visible with a group key is a code-level
  choice, made against the dedup logic.
- Add `place_name`, `jurisdiction_kind`, `required_vote` and `multi_measure_id`; fill
  `ballot_question`. Strip zero-width spaces: 2024 names contain U+200B.
- Normalize `passed` for the 48 CEDA 2011 rows that carry `percent_yes` and `pass_fail` but a
  NULL `passed` (found in P0.1), and check other years for the same gap.
- Check `REQ` against the five KNOWN_ISSUES #1 records.
- Verification: single-county rows keep identical figures (Layer 1); row counts per year
  match the raw files (Layer 2); every changed outcome is listed with both figures and
  reviewed by Igor (Layer 3); San Joaquin Delta K is a sentinel.
- Log the defect as a new KNOWN_ISSUES entry and correct #5.
- **Exit:** no stored outcome differs from CEDA's combined outcome; history rows show real
  jurisdictions; a before/after list of every card statistic that changed.

### Phase 2: results for the 63 we hold (3-4 days; Igor 1-2 hours)

- Implement [results_transition_20260907.md](results_transition_20260907.md): immutable
  observations, reviewed ID mapping, Unofficial and Certified states.
- Importers: SOS JSON, SB xlsx, SMC precinct CSV. Keep precinct and vote-method detail, and
  mask precincts of ten or fewer voters before anything is published.
- Only certified observations project into `passed`, so unofficial counts stay out of
  historical pass rates.
- Store what the tab (§6) needs: votes, threshold, ballots cast per contest where published
  (for roll-off), and the as-of time. For props, keep the SOS county breakdown.
- Solve the multi-county rule here, on real cases (Trap 1).
- **Exit:** the rehearsal list in that design doc passes on a database copy, and the 63
  show unofficial results with an as-of time.

### Phase 3: layout (3-5 days; Igor 2 hours)

- Direction A has to land before LA: 68 measures behind a carousel means 67 taps on a phone.
- Add a **result state** to the design, which assumed upcoming measures. "Needs 55%" beside
  "52.3% yes" now does real work.
- Replace `year == 2026` selection with `election_date`, and handle a 53-county picker.
- Design the results and comparisons tab (§6) as a modal tab and a static-page section.
- Run the Codex review the proposal was written for, then Igor's decisions (§8).

### Phase 3b: results and comparisons tab for the 63 (3-4 days; Igor 2 hours)

- Needs Phases 1b, 2 and 3. Spec in §6.
- Extend `local_measure_context.py` rather than starting over. It already applies the
  reviewed type crosswalk, keeps the current measure out of its own cohort and links every
  cohort record for audit.
- Hand-tag topics for the roughly 40 props from 2018-2024; tags in `ca_historical_measures`
  stop at 2018.
- Tests: cohort rules, multi-county measures counted once, unofficial numbers never in a
  statistic, minimum sample, template wording.
- Launch around certification, so most numbers can show as certified.
- **Exit:** tab live on the 63; every statistic shows its n, cohort definition and records.

### Phase 4: harvest adapter and Wave 1 (3-4 days; Igor 2 hours)

- **One adapter, many counties.** A reviewed per-county JSON manifest, bound to captured
  bytes by SHA-256, feeds the existing `extractor`/`interpreter` contract. It inherits
  identity minting, scope watermarks and loader gates without 51 code modules.
- LLM-assisted extraction, then deterministic checks: question text found in source bytes,
  letters unique, threshold in the allowed set, counts match the census. Scanned sources
  get visual checks.
- Add `regional_measure_key` and `jurisdiction_kind` before Alameda (Trap 2), matching the
  Phase 1b history fields.
- Extend the type crosswalk to each county's vocabulary; new cards then get the tab.
- **Wave 1: Los Angeles 68 + Alameda 28 = 96 measures.** Two hard shapes and the
  five-county transit measure. Re-estimate everything afterward.

### Phase 5: remaining waves (1-2 weeks; Igor about 1 hour per wave)

- **Wave 2:** Orange, San Francisco, then the next-largest counties by census count.
- **Wave 3:** the rest, batched by source format rather than geography.
- Each wave: manifest, checks, crosswalk review, independent review of a sample, load on a
  copy, preservation gate, release, served check, recovery update.
- Statewide same-year comparisons switch on per Decision 5.

### Phase 6: certification sweep (Dec 3 onward; 2 days; Igor 1 hour)

- Counties must certify by **December 3**; the state is reported to certify on December 11.
- Import certified observations, project `passed`, rebuild statistics, compare with
  Coleman's final report, and capture the final pages.
- 2026 results join the history cohorts only once certified.

Dates assume a go-ahead by November 9 and slip day for day after that. The tab adds about a
week before Wave 1.

| Date | Milestone |
|---|---|
| Nov 9-10 | Phase 0 live; Phases 1 and 1b running |
| Nov 9 | Watch cron |
| Nov 10 | Last day for postmarked ballots to arrive |
| ~Nov 13 | Sources frozen |
| ~Nov 16 | History repaired |
| ~Nov 20 | Unofficial results on the 63 |
| ~Nov 27 | New layout ready |
| Dec 3-11 | Certification sweep |
| ~Dec 4 | Results and comparisons tab live on the 63 |
| ~Dec 11 | Wave 1 live |
| ~Dec 23 | Waves 2-3 complete |

## 5. What each new card gets

| Layer | Coverage |
|---|---|
| County, jurisdiction, letter, type | All |
| Approval rule | County-published only; otherwise "not listed", never inferred |
| Official question, verbatim | All with a usable source |
| Result, unofficial then certified | All |
| Official documents | Where the county exposes them |
| County record table (history) | Needs the type crosswalk extended per county |
| Results and comparisons tab | Results for all; history where a reviewed type exists; same-year per Decision 5 |
| CalBallot explanation | Decision 2 |
| Local campaign finance | Out of scope; the honest "not imported" stays |

## 6. Results and comparisons tab

The ask, per card: (1) the result as currently known, and (2) how it compares with similar
measures, past and present. Data checked November 7.

### What it shows

| Part | Content | Data | Ready |
|---|---|---|---|
| Result | Yes %, votes, threshold and the margin against it; Unofficial with an as-of time, or Certified; source link | County files and SOS JSON | After Phase 2 |
| Turnout and roll-off | Share of ballots cast that skipped the measure | Ballots cast per contest: San Mateo, San Bernardino, LA so far | 2026 only. CEDA has no registration or ballots cast, so there is no historical turnout to compare against |
| Multi-county | Combined result first; each county's share labelled as a share | Summed county files; CEDA combined fields for history | After Phase 1b |
| Same place before | Earlier measures by the same city, district or county, any type | `PLACE` names | After Phase 1b |
| Similar in history | Same reviewed type, jurisdiction kind and required vote; county first, then statewide. n, pass rate, median yes %, median margin, and where this measure falls | 10,997 CEDA rows, 1998-2024; about 1,200 props since 1912 | Local after 1b; props after tagging |
| Same election | Other November 2026 measures of the same type | 49 rows in two counties today; statewide needs Phases 4-5 | Within the county now; statewide per Decision 5 |
| County versus state (props only) | The county's yes % beside the statewide figure | SOS county JSON | After Phase 2 |

Until statewide same-year data exists, November 2024 (708 local measures) can stand in as
the last comparable election.

Later, optionally: match on bond size or tax rate parsed from the ballot question. That needs
`BALQUEST` from Phase 1b plus reviewed parsing, so it stays out of v1.

### Rules

- History describes; it never predicts. No "likely to pass".
- The measure is never in its own cohort, and unofficial 2026 figures never enter a
  statistic.
- Lead with the margin against the threshold, not the pass rate alone. A 55% bond at 54% is a
  different story from one at 40%.
- Every statistic shows its n, cohort definition and years, and links to its records.
- Multi-county measures count once, with the combined result.
- No pass or fail label before certification (Trap 3). Unofficial results say which side of
  the threshold they are on.
- Wording comes from fixed templates, not generated text, per the free deterministic cards.
- Ballotpedia and Coleman are checks only, never displayed.
- The minimum cohort stays at 5 (`MIN_HISTORICAL_CONTEXT_SAMPLE`). Below that, list the
  records without a rate.

### Coverage at launch

- Results: all 63.
- History: the 40 local cards with a reviewed type, plus the 14 props once tagged. The other
  9 local cards (rent control, a fireworks ban and similar) get results and same-place
  history only.
- Each later wave inherits the tab once its descriptions are in the crosswalk.

## 7. Traps

1. **Multi-county measures pass or fail on the combined vote.** A county's number can be
   only its portion. At least 11 are in Coleman's tables, three already on our site:
   Beaumont B, San Bernardino CCD Y and the transit measure. Importing one county's figure
   could show the wrong outcome. Our CEDA history already does this (Phase 1b).
2. **One measure, several county lists.** RTM alone is on five. Without a shared key we mint
   five unrelated records. Decide before Alameda loads.
3. **Unofficial numbers move.** Coleman reports over 20 school bonds too close to call, and
   late ballots tend to shift results. No pass or fail label before certification.
4. **Aggregators are checklists.** Keep the registrar-versus-aggregator authority line
   (KNOWN_ISSUES #12). A future CEDA 2026 release will need reconciling against these rows.
5. **No bypassing blocks.** Blocked counties stay honestly uncovered unless access is
   granted. Santa Clara's results may be hosted elsewhere; check, don't assume.
6. **County-specific constants need to become data:** `ENABLED_COUNTIES`,
   `LOCAL_COUNTY_ROADMAP`, `SOURCE_HOSTS`, `LISTING_URLS`, `FINANCE_URLS`, and tests that
   assume 49 records.
7. **Display assumes "Measure X".** San Francisco uses "Proposition"; LA has letters like
   SOS and HT.
8. **`county_status.md` is stale.** Correct the LA row and refresh the board in Phase 1.
9. **Comparisons can read as forecasts.** "Similar bonds passed N% of the time" beside a
   live count invites a prediction. Keep to the §6 wording rules.

## 8. Decisions for Igor

1. **Coverage target.** All 53 counties (recommended; one-shot capture makes it affordable),
   or stop at the largest ten?
2. **Explanations for the 413.** Recommended: ship official questions and results first,
   then decide on explanations separately. This matches "free deterministic cards, no bulk
   pre-generation", and their value has dropped now that voting is over. The alternative is
   parity with the 49, at much higher review cost.
3. **Layout.** Approve Direction A with a result state and the §6 tab? This replaces the
   proposal's four open questions; the carousel question is now forced by LA's 68 measures.
4. **Santa Clara.** Email the Registrar for access (one email, plausible yes), or leave the
   county uncovered?
5. **Statewide same-year comparisons before every county loads.** Show them over partial
   coverage, labelled "among the N measures loaded so far", or wait? Recommended: wait, and
   use the same county plus November 2024 meanwhile. A partial statewide figure leans toward
   whichever counties loaded first.

Publishing needs your go-ahead at each release, per CLAUDE.md.

## 9. Not in this plan

Local campaign finance; June 2026 local measures (Coleman counts over 110); the 2025 gap;
historical county backfill; address lookup; forecasting. The first two are the natural next
candidates.

## 10. Not verified

- Per-county counts and source formats for the 47 unexamined counties.
- Whether the 22 missing CEDA years can still be downloaded and carry the same columns.
- The pass-rate effect in CEDA years without raw files on disk.
- What a blank CEDA `JUR` means (1,754 rows, 2000-2024); special districts is a guess.
- Whether a place's name is spelled the same across CEDA years, which "same place before"
  depends on.
- Whether blocked counties are still blocked.
- How each multi-county measure's combined result is published. Summing certified county
  precinct files should rebuild it.
- How long any county keeps its pages up. "Perishable" is a judgment, not a measurement.
