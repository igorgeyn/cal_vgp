# Explore E1 fix-pass-2 recheck

**Verdict: ready to release for the current data.** The N1 release blocker is closed.
The N2/N3 fixes and the Other-row guard work on the tested paths. E1 can close its code-review
gate; release still follows Igor's approval and the coordinator's frozen-build process.
The 2026 certification gate remains P2(c), before results enter Explore; this pass does not
implement it or certify future data.

Reviewed `2eeeca57` on `phase0-election-status`, at HEAD `2e6aaf47`, November 13, 2026.
No application code, published artifact or production database was changed. No network or
push. Only this response is committed.

## Findings and dispositions

No new release-blocking defect was demonstrated.

| Finding | Disposition | Evidence |
|---|---|---|
| **N1: county lost on drill** | **Closed** | The original Yuba Bond 2020–24 modal says 1 of 18 and now opens exactly **18 Yuba records**, rather than 714 records from 53 counties. Row-header and Region drills also preserve Yuba. `generator.py:12074` retains the local county; `:11643` clears its model and dropdown together when appropriate. |
| **N2: misleading rate controls/count sorting** | **Closed for the reported metric and sort defects** | County, `levelCounty`, Passed and Failed disable Metric as “Counts only”; Region sort has no rate option. Both column-sort directions order by totals, including cells below five. Removing the active filter chip restores Average yes vote. See `generator.py:11633`, `:11733`, `:11825`, `:11828`. Minor Min n control polish remains below. |
| **N3: conflicting catalog/Explore levels after a switch** | **Closed for explicit level/column changes** | Statewide drill → return → Local changes both level states to Local. Switching columns also reconciles a conflicting catalog level. `generator.py:11651`, `:11962`, `:11985`. Preserved period/geography filters can still yield honest empty views; details below. |
| **Other region broadens a drill** | **Closed for reader-accessible actions** | Synthetic Other row has no button role, tabindex or click handler; clicking it stays in Explore. Its cell opens an explanatory modal with no drill button. `generator.py:11639`, `:11881`, `:12023`. |

Here and below, `generator.py` means `scraper/src/website/generator.py`.

**Nonblocking UI observations, suitable for E2:**

- **P3: initial entry and retained filters can still produce a sparse empty state.** Choose
  Statewide in the catalog, then enter the default Type/Local view: 1,312 statewide catalog
  records remain selected, but zero local Type records are counted. The level chip and coverage
  text expose the scope; choosing Topic/Statewide works and counts 1,279. Likewise, after a
  Greater Bay Area Region drill, switching to Statewide retains that Region chip and yields
  zero records. These are accurate intersections, not silently broadened cohorts. A clearer
  empty-state action or entry policy would help (`generator.py:11615`, `:11651`, `:11788`).
  Extend the County explanation to incompatible Region filters, and consider directing a
  catalog Statewide selection to Topic/Statewide on entry. Preserve filters unless the reader
  explicitly changes or removes them.
- **P4: “Min n for rates” remains enabled in count-only mode** (`generator.py:11829`). It
  cannot expose a rate and does not affect count sorting. Disable it while counts only applies,
  retaining the selected value for later, to avoid a control that has no visible effect.

These do not reopen the wrong-record drill or hidden-rate defects. Do not interpret the
N3 disposition as a claim that every possible filter combination produces records.

## Answers to 1–6

**1. N1: original reproduction, row and Region drills.** I selected Local and Yuba through
the catalog control's change handler, entered Explore, and clicked the actual row/cell
and modal controls. Independent offline Chromium results:

| Drill | Catalog records after drill | Counties in result | Dropdown | Return to Explore |
|---|---:|---|---|---|
| Bond, 2020–24 cell | **18** | Yuba only | Yuba | Counts only |
| 2020–24 row header | **21** | Yuba only | Yuba | Counts only |
| Bond, Region cell | **29** | Yuba only | Yuba | Counts only |
| Region row header | **61** | Yuba only | Yuba | Counts only |

The Region Bond modal says 7 of 29. Every returned view has no percentage or fill and retains
the county caution. Both `levelCounty='Yuba'` and the dropdown value survive the local drills.

An explicit Topic/Statewide change from the Yuba selection clears `levelCounty`, resets the
dropdown to its empty value and removes the County chip; the level chip says Statewide.
It shows 1,279 counted statewide Topic records. The subsequent statewide row drill retains
that synchronized cleared county. Thus the county is already visibly cleared by the explicit
level change before the statewide drill, rather than disappearing unnoticed during it.

**2. N2: controls, sorting and restoration.** Tested separately under `county`, `levelCounty`,
Passed and Failed, with Average yes vote selected beforehand. Metric is disabled and reads
“Counts only”; no rate/average options or “By pass rate” Region option remain. Cells, totals,
titles and accessible labels contain no percentages; backgrounds are transparent; the legend
is absent; cell modals show no average/percentage.

For Year rows, Bond column counts sort monotonically in both directions for all four filters.
For example, Yuba's descending sequence is
`12, 3, 3, 3, 3, 2, 2, 1, 0, 0, 0, 0, 0, 0, 0`; ascending is its reverse. Region row sorting
with a retained rate-sort preference falls back to total count, matching the visible By count
control. Removing only the relevant filter through its chip re-enables Metric and restores
`avgYes` in all four cases. The separate Min n observation above is presentation polish.

**3. N3: level switching and preselected catalog filters.** The two level variables no longer
contradict one another after an explicit Explore level/column change. The tested statewide
drill selected the 1910s; after switching to Local, both levels correctly become Local,
but the 1910s chip remains. Zero records is then legitimate. Removing that decade chip and
switching to Type yields the expected **10,939** counted local records. No unrelated period
filter was silently removed to manufacture a nonempty result.

Catalog Statewide before entry is usable through Topic/Statewide, with the initial-entry
caveat described above. The other County filter (`currentFilters.county`) is deliberately
preserved under Statewide and produces the visible instruction “remove the County filter to
see them.” Local drills and local column changes do not clear the catalog's sub-county.
Explicit changes to Statewide reconcile that sub-county and its dropdown together. Column
changes apply the effective level of the selected column mode, as documented in the handoff;
Topic retains its previous level choice.

**4. Other.** The synthetic unmapped-county record remains inspectable, but neither its row
header nor its modal provides a broadened drill. The modal explains that there is no matching
catalog filter. The helper functions themselves are not guarded against arbitrary console
calls with `Other`; that is not a reader-accessible action or a release blocker.

**5. Regressions and scope.** The actual production-code diff in `2eeeca57` is confined to
the Explore JS block in `generator.py`; the other executable change extends its checker.
No shared catalog function or CSS rule was rewritten. The new Explore helpers invoke the
existing catalog update/filter functions, so their effects were tested across Grid/Explore
transitions rather than assumed safe from location alone.

County/level dropdowns and chips agree on the tested drills and level changes. Removing
count-only filter chips restores the metric; Clear/Reset restores 10,939 counted local
records, no catalog level/county filter, and the default Type/Decade configuration. The
four-width checker also exercises Clear and Reset. Hidden Insights and Explore flag tests pass.

Independently compared `#resultsContainer.outerHTML` with the retained pre-E1 scratch baseline
at a fixed clock: identical for `/`, `?view=list` and `?view=list#page=3`. The coordinator's
full preservation and navigation reports were read, not independently regenerated here.

**6. Release.** **Yes, E1 is ready for the current-data release.** N1's independent recheck
passes, as do the metric/sort and Other protections. The remaining empty-state/control polish
can follow in E2. Keep the separate P2(c) gate before any 2026 result import; E1's release
does not authorize uncertified records to enter statistics. The coordinator still needs the
normal frozen release build, preservation checks and Igor's approval.

## Verification receipt and limits

Local evidence: `scraper/data/exports/explore_e1_fixpass2_codex_recheck/` (gitignored):
`scratch.json`, `probe.py`, `probe.json`, `compare_dom.py`, `dom.json`, and the four-width
checker report/screenshots. All browser requests were fulfilled from local scratch files or
aborted; no external request was permitted.

As in the first re-review, I used an **offline replay**, not a fresh strict database build.
I applied the supplied `fixpass2/index.diff` to the retained pre-E1 scratch HTML at
`%TEMP%/calballot-explore-e1-agk12tbt/baseline`, with its scratch JSON. Every removed hunk
matched except the known data cache key; the saved diff supplied the replacement. The replay
is `%TEMP%/calballot-e1-recheck2-ttk5lf7r/site`. The whole Explore renderer matches the current
generator after f-string unescaping; `explore.py` SCRIPT and STYLE match exactly. There are
no generator/checker changes between `2eeeca57` and reviewed HEAD. No production DB was opened.

| Check | Observed |
|---|---|
| `python -m pytest tests/test_explore.py tests/test_explore_hidden.py tests/test_insights_hidden.py tests/test_election_status.py -q -p no:cacheprovider --basetemp=.pytest-tmp/codex-e1-fixpass2`, from `scraper/` | **108 passed**; Node helper tests ran |
| `check_explore_browser.py --site-dir <replay>/site --output-dir <evidence>/checker` | **Exit 0**, 1440/768/390/320 px; no page errors; minimum cell contrast **7.06459:1** |
| Additional independent probe | Four Yuba drill paths; all four count-only filters, both count-sort directions, Region fallback sort, modal suppression, metric restoration via chips, level reconciliation, Other guard and Reset pass; zero page errors |
| Default coverage | 10,939 counted + 2 missing type + 56 missing outcome = 10,997 Local; 1,312 other-level records and 63 default-excluded current-election records |
| Grid/List DOM | All three URLs identical to retained pre-E1 baseline |
| Coordinator preservation evidence | Read `fixpass2/compare.json` and source/diff evidence: reports 12,372 unchanged measure pages, only 129 `last_seen_at` JSON differences, no added/removed files, unchanged use-calballot, sitemap equal apart from dates. **Not independently rebuilt/rehashed here.** |
| Coordinator full suite | Log reports **760 passed, 1 skipped, 1 failed, 17 errors**, identified as the known baseline. **Not rerun or independently reconfirmed here.** |
| Status, county-content and full navigation browser checks | Coordinator reports read; not rerun in this bounded recheck |

No screen-reader pass or new phone-layout review was performed; those remain the planned
E2 work. No checklist or queue edit is part of this response-only commit.
