# Explore E1 fix-pass review

**Verdict: ready with changes.** Reviewed `a496421c` on `phase0-election-status`, at HEAD
`1979acbd`, November 13, 2026. **Do not close E1 or release this candidate yet.** The major
aggregation fixes work, but a drill-down silently removes a reader's county filter and opens
records from other counties (N1). Fix that and rerun the interaction checks before release.

This reviews the coordinator's fix pass, not a new implementation. No application code,
published files or database was changed. No network requests were allowed. Only this response
is committed.

## Demonstrated findings

Severity follows the original review: P2 changes before release; P3 should fix; P4 latent.
Paths below are relative to the repository; `generator.py` means
`scraper/src/website/generator.py`.

### N1 — P2: a county drill-down silently broadens the cohort

**Location:** `generator.py:12030`, called by both `matrixDrillDown` (`:11998`) and the
row-header drill-down (`:12035`).

**Reproduction:** choose catalog Level = Local and its county dropdown = Yuba; open Explore;
open Bond in 2020–24; click **View matching catalog records**; return to Explore.

- Before the drill, `levelCounty='Yuba'`, `county=null`; the catalog has 61 records.
- The cell/modal correctly says **1 of 18**, counts only.
- The drill sets `levelCounty=null` because `county` is unset. Grid now contains **714 Bond
  records from 53 counties**, all with recorded outcomes. This is not the documented inclusion
  of records without outcomes.
- The county dropdown still displays **Yuba**. Returning to Explore produces four rated cells,
  with the county caution gone.

Evidence: offline Chromium probe, `probe.json` keys `drillModal` and `levelCountyDrill`, plus
`county-drill-return.png` in the evidence directory below. The probe selected the actual dropdown
option and invoked its change handler; it then clicked the modal's drill button.

**Fix:** preserve a valid `levelCounty` when drilling within Local. Clear incompatible county
state only on an explicit change to Statewide, and synchronize the dropdown whenever clearing
it. Test both row and cell drills with `county=null, level='local', levelCounty='Yuba'`:
the returned records must still belong to Yuba, and returning to Explore must remain counts only.

### N2 — P3: count-only views still offer rate controls that do not do what they say

**Location:** `generator.py:11774`, `:11787`, `:11788`; sorting at `:11704` and `:11711`,
with `exploreEffectiveMinN` at `:11628`.

**Evidence:** under each of County, `levelCounty`, Passed and Failed, the toolbar still offers
**Pass rate**, **Average yes vote**, and, for Region rows, **By pass rate**. Switching these
controls leaves counts on screen. The Infinity floor prevents rate sorting, but also causes
column sorting under Number of measures to fall through to row-name order rather than counts.
The browser probes confirmed the visible options for all three metrics; source inspection
confirms the comparator behavior.

There is **no numerical rate leak** here: my checks found no cell/title/accessible-name
percentage, fill, legend or modal average under these filters. This is a misleading control
state, not wrong displayed arithmetic.

**Fix:** render an explicitly count-only metric state and remove/disable rate and average
controls while the caution applies. Allow count sorting by actual totals, independently of
the eligibility rule for rates. Preserve the reader's previous metric for restoration if desired.

### N3 — P3: Explore's level switch conflicts with the level retained by a drill-down

**Location:** `generator.py:11942` and `:11920`, together with `:11615` and `:12029`.

**Evidence:** after a Statewide Topic drill and return, clicking Local changes
`matrixState.level` but leaves `currentFilters.level='statewide'`. The matrix intersects the
two and is empty; switching to Measure Type also remains empty. The probe's Statewide
1990s/Education example retained two statewide catalog records while reporting zero local
records and “switch Level to see them.” Both selectors/chips expose the conflicting state;
the zero is the correct intersection, not evidence of data loss.

The same conflict is possible with a level chosen in the catalog before entering Explore.
It now also arises from Explore's own drill action. Ordinary column switching without a
catalog level filter correctly remembers the Topic level, and Reset correctly clears both.

**Fix:** define one interaction policy: an explicit Explore level change should reconcile the
catalog level, or the incompatible control should explain which catalog filter must be removed.
Do not silently discard county filters while doing this. Add a drill/return/switch test.

### Remaining R9 — P4: “Other” no longer opens an empty list, but opens every region

**Location:** `generator.py:12025`–`:12029`.

**Evidence:** a browser-only synthetic local Bond with county `UNMAPPED` creates an Other
row with one record. Drilling its cell returns **3,029 Bonds across all regions**, including
the injected record. No production records currently have an unmapped county. The guard
removed the bogus county string but did not preserve the row's cohort.

**Fix:** either disable that drill with an explanation until supported, or filter for the
actual unmapped-county cohort. A “matching records” action must not silently drop its row
condition. This is a partial fix of the old latent finding, not a newly reachable data defect.

## Dispositions of the original findings

| Finding | Disposition | Evidence / qualification |
|---|---|---|
| Claude R1 — pooled Topic levels | **Closed** | `generator.py:11611`–`:11617`, `:11658`: the selected level feeds cells, all totals and modal. Independent checks of all nine column/level × row-grouping combinations found no mixed cohort. N3 concerns navigation state, not pooling. |
| Claude R2 — county rates through catalog filters | **Partly closed** | Both county fields suppress rates, shading, legend and modal averages, with a visible caution (`:11621`, `:11757`, `:11974`). N1 loses one of those filters on drill-down. |
| Claude R3 — difference metric | **Closed** | Removed from options, accepted metrics, presentation and aggregation; browser checker rejects the old option. No baseline fields remain in the matrix cells. |
| Claude R4 — old decade labels in cells/modal | **Closed** | `:11715`, `:11807`, `:11967`; checker verifies 1998–99 in accessible name and modal title. The ambiguous decade chart is removed. |
| Claude R5 — tautological Status rates | **Closed** | Passed and Failed both produce counts only in cells, totals and modal. N2 is the remaining control-label issue. |
| Claude R6 — statewide instrument types / 2026 | **Partly closed** | Type is explicitly Local, including a browser-only injection of decided 2026 statewide records: zero entered Type. There is still no certification check for Topic; see below. |
| Claude R7 — phone legend and added prose | **Closed for the fix-pass scope** | `explore.py:91` fixes the swatch; checker passes at 768/390/320. Notes are collapsed. Table/list phone redesign remains the explicitly deferred E2c work. |
| Claude R8 — unreachable threshold helpers | **Closed** | `generator.py:11567` documents the false fallback and prohibits revival before E3; handoff corrects the original justification. Removal was optional. |
| Claude R9 — smaller defects | **Partly closed** | Average sort floor fixed: synthetic min n 20 puts the cell with only five vote shares last in both directions. Difference metric/negative zero removed; modal discloses unknown-outcome records; dead branches/comment removed; time rows lose the descending arrow. Other drill is still overbroad, and new shared drill logic causes N1. |
| Fable F1 — difference metric | **Closed** | Same removal as R3. |
| Fable F2 — ambiguous modal bars | **Closed** | Chart removed; modal now shows numerical metrics only (`generator.py:11970`). |
| Fable F3 — decade wording | **Partly closed; remaining wording acceptable** | Cell and modal fixed. Catalog chip intentionally remains “Decade: 1990s,” accurately naming its whole-decade filter; it does not claim that every year has data. No release change needed for that chip. |
| Fable §4 — coverage / current-election exclusion | **Closed** | Computed 63 and renamed missing-outcome bucket; arithmetic below. The exclusion count is global, not county-specific. |
| Fable handoff question 4 — Region mixing / Topic level | **Closed** | No Statewide row under Local; Statewide Topic is a separate cohort. Actual topic years are listed. This also addresses F4's missing-years concern. |

**R6's remaining certification requirement:** `buildExploreMatrixData` accepts any selected
record with `passed` equal to 0 or 1 and a column value (`generator.py:11658`); the catalog's
default exclusion also stops excluding such rows (`:11013`). In a browser-only simulation,
setting `passed=1` on the 63 pending 2026 records admitted **14 statewide Topic records**,
without any certification evidence. The actual JSON has **zero decided 2026 records**, so
this is not a present-data release blocker. Keep the plan's certification requirement open
and enforce it before a results import can populate `passed`; do not describe R6 as wholly
closed by the level split.

## Answers to checks 2–8

**2. Level separation.** Correct for aggregation. Type always counts Local; Topic counts the
chosen level. Cells, row/column/grand totals and modal use that same cohort. Independent
matrix checks found totals of **10,939 Type Local**, **1,833 Topic Local**, and **1,279 Topic
Statewide**, identical under Decade, Year and Region. Sorting does not reintroduce excluded
records. Reset returns to Local/Type and clears catalog filters; Topic → Type → Topic retains
the previous Topic level. Drill-down preserves the chosen level, with N1/N3 interaction defects.

**3. Counts-only filters.** Correct numerical suppression under `county`, `levelCounty`,
Passed and Failed, across Pass rate, Number of measures and Average yes vote. Cells/totals
have transparent backgrounds and no percentages; legends and modal averages disappear.
The caution is visible outside the disclosure. Rate values cannot steer sorting because
the comparison floor is Infinity, but N2 describes the resulting misleading controls.

Other filters appropriately retain rates when they define a cohort without selecting its
outcome: year, search, topic, type, region, level and feature filters. Their source limitations
remain disclosed. Pending/withdrawn-only cohorts have no eligible outcomes anyway. Selecting
both Passed and Failed also conservatively invokes counts only; relaxing that is optional.

**4. Coverage.** Independently partitioned the selected catalog IDs in Python from JSON,
without using `Explore.coverage`; every displayed bucket and counted total matched:

| View | Selected level total | Counted | Missing column | Missing outcome | Other level | Current excluded |
|---|---:|---:|---:|---:|---:|---:|
| Default Type/Local | 10,997 | 10,939 | 2 | 56 | 1,312 | 63 |
| San Mateo Type | 458 | 449 | 0 | 9 | 0 | 63 |
| Selected year 2024, Type | 866 | 865 | 1 | 0 | 11 | 0 |
| Search “school,” Type | 3,639 | 3,593 | 0 | 46 | 99 | 0 |
| Topic/Local | 10,997 | 1,833 | 9,108 | 56 | 1,312 | 63 |
| Topic/Statewide | 1,312 | 1,279 | 32 | 1 | 10,997 | 63 |
| Pending status, Type | 105 | 0 | 0 | 105 | 14 | 0 |
| Selected decade 2020s, Type | 2,291 | 2,241 | 1 | 49 | 47 | 0 |
| Sidebar year range 2000–2010, Type | 4,637 | 4,630 | 0 | 7 | 127 | 63 |

Counted + missing column + missing outcome equals selected-level total. Adding other level
equals the filtered catalog. The 63 is computed over **all records**, not the filtered cohort;
do not add it to an arbitrary county/year-range subset as a reconstruction of that subset.
At default scope, 10,997 + 1,312 + 63 = 12,372.

The exclusion activation and predicate at `generator.py:11747`–`:11750` match
`applyFilters` at `:11011`–`:11013`: search, Pending, selected years and selected decades
disable it. Each was observed with zero excluded. The sidebar's continuous year range does
not disable it, consistently with the catalog. This is the existing catalog rule, not an
election-certification rule.

`Explore.yearRanges` is honest: it deduplicates and sorts integer years and merges only
consecutive runs. Actual local Topic coverage is **2000, 2005, 2011, 2013, 2015–16, 2022–24**,
including the sparse exceptions missed by the earlier simplified description. Statewide's
long year list is accurate; compacting its presentation belongs in E2c.

**5. Drill-downs.** Level is carried into Grid correctly, avoiding pooled results. Existing
catalog constraints still intersect the matrix before drilling. The county deletion in N1
violates that preservation; N3 explains conflicting level selections after returning. Other
has a partial guard only. A modal's disclosure about unknown outcomes does not justify
discarding geography.

**6. Outside Explore.** Grid/List navigation checker passes at 1440, 768, 640, 390 and 320,
including filters, county controls, pagination/history/reload and modal links. Results-container
DOM matches the retained pre-E1 scratch baseline at `/`, `?view=list` and `?view=list#page=3`
under a fixed clock. Explore's chips, Clear and Reset pass their checker; Reset clears search
and both level states. Hidden Insights tests pass. The fix-pass source changes are confined
to Explore; N1 is nevertheless a real catalog regression reached through Explore.

**7. Tests.** The Node tests execute the actual exported helper script and pin year ranges,
small-cell presentation, higher floors and reason-driven count suppression. They cannot test
catalog/drill integration. The extended browser checker is useful but passed despite N1–N3:

- It tests `county='San Mateo'`, not the catalog's `levelCounty` drill sequence.
- Its status case is Passed only; my extra probes covered Failed too.
- `NO_RATES` checks text/rated flags, caution and legend, not backgrounds, modal averages or
  available controls. My additional checks covered those surfaces.
- `CELL_CHECK` still hardcodes n < 5 (`check_explore_browser.py:47`), rather than checking
  active min n 10/20. My synthetic average-sort case covered the specific R9 regression.
- It never changes level after returning from a drill and has no unmapped-region fixture.
- Its current-data fixture cannot pin R6 against newly decided statewide instrument types.

`current_excluded` (`check_explore_browser.py:17`) is independent **of the running page**:
it calculates from JSON in Python rather than reading page state or calling its helper.
It is not an independent specification of eligibility: it duplicates the same hardcoded
2026/null-outcome/withdrawn rule. `expected_coverage` only models county/year and the level
split; it does not model search, status, decades, ranges or certification. Thus it can catch
implementation divergence for its scenarios while agreeing with an incorrect shared policy.
Add fixtures for the interaction failures above, not just assertions that the current helper
returns its own expected value.

**8. Release readiness.** The numerical level split, removal of difference/bar comparisons,
and count suppression materially resolve the original release findings. **N1 must be fixed
and independently rechecked before E1 closes.** N2/N3 should be addressed in the same bounded
interaction pass; the Other guard and certification gate remain explicitly open with the
limitations above. E2c layout work and E3 data repair remain separate chunks.

## Verification receipt and limits

New local evidence: `scraper/data/exports/explore_e1_fixpass_codex_review/` (gitignored),
including `probe.py`, `probe.json`, `extra.py`, `extra.json`, checker/navigation reports and
screenshots. Browser routes fulfilled local files only and aborted every other request.

The coordinator's original `scratchpad/e1-candidate/site` was not present here. Instead of
opening the production DB or claiming a fresh strict build, I reconstructed the saved
fix-pass candidate HTML from `fixpass/index.diff` and the retained pre-E1 scratch baseline
at `%TEMP%/calballot-explore-e1-agk12tbt/baseline`. Every removed hunk matched except the
expected JSON cache key; the replacement key came from the saved diff. The resulting site
is `%TEMP%/calballot-e1-fixreview-rspflbx1/site`, with the retained scratch JSON. I confirmed
the entire Explore renderer block matches current `generator.py` after f-string unescaping,
and `explore.py`'s SCRIPT and STYLE match byte for byte. Those source files have no changes
between `a496421c` and reviewed HEAD. This is an offline frontend replay, not a new release
build or a rerun of the strict-build preservation gate.

| Check | Observed |
|---|---|
| `python -m pytest tests/test_explore.py tests/test_explore_hidden.py tests/test_insights_hidden.py tests/test_election_status.py -q -p no:cacheprovider --basetemp=.pytest-tmp/codex-e1-fixreview` from `scraper/` | **108 passed**, Node tests executed |
| `check_explore_browser.py --site-dir <replay>/site --output-dir <evidence>/checker` | **Exit 0**, all four widths; minimum cell contrast **7.06459:1**, no page errors |
| `check_browse_navigation_browser.py --site-dir <replay>/site --output-dir <evidence>/navigation` | **Exit 0**, all five widths, no page errors |
| Additional browser/Python probes | Coverage table, 12 count-only filter/metric combinations and modal checks pass; nine matrix level/total invariants pass; N1/N3 and Other reproduced; average sort floor passes both directions; 2026 simulation confirms remaining certification gap |
| Grid/List DOM comparison | Equal for all three URLs against retained pre-E1 scratch baseline |
| Coordinator's `fixpass/compare.json`, `index.diff`, browser reports | Read; report claims 12,372 unchanged pages, JSON only 129 `last_seen_at` values, sitemap unchanged except permitted dates, unchanged use-calballot page. **Not independently rebuilt/rehashed in this review.** |
| Full suite claim, 760 passed plus known baseline failures | **Not rerun**; no claim here to reconfirm baseline failures |
| Election-status midnight and county-content browser checks | Coordinator's evidence read; not rerun. Targeted election-status unit tests did run |

Initial custom-probe attempts stopped on the hidden county selector and then an uppercase
option value; neither was counted as a product failure. The completed probe selects the
actual `Yuba` option and records zero page errors. No screen-reader pass was performed.
