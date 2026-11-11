# P0.1 election-status review response

**Verdict: ready with changes.** Reviewed November 7, 2026, on
`phase0-election-status`, HEAD `eff6b1b9`, code diff `c7dc0efa..e090796a`.

The November 7 candidate correctly labels all 63 measures **Results pending**.
The stated page and JSON preservation counts reproduce, as do the targeted tests,
full-suite counts and all six browser scenarios. No fresh-load status consumer for
these 63 retained “Upcoming” or claimed a result. The defects below concern open
tabs, accepted edge-case inputs and release metadata; they are not evidence that
the tested November 7 candidate labels its current records incorrectly.

Address R1–R6 before closing P0.1 and carrying its contracts into P0.3. These are
review findings only; no implementation fixes or publication were performed.
P0.1.15 remains Igor's manual check.

## Demonstrated defects, ranked by severity

### R1 — P2: an already-open explorer keeps yesterday's status

**Location:** `scraper/src/website/generator.py:11208`, `:11233`, `:14895`;
`scraper/src/website/election_status.py:277`.

**Evidence:** In Chromium, loaded the actual November 2 scratch build at
`2026-11-02T23:59:00-08:00`, then changed the clock in the same page to
`2026-11-04T00:01:00-08:00`. In both UTC and Asia/Tokyo browser time zones,
`pacificToday()` returned `2026-11-04` and `getElectionStatus()` returned
`results_pending`, but the rendered statewide cards still said **UPCOMING**.
Opening a modal then showed **RESULTS PENDING**, so surfaces disagreed within one
page. The hero is rendered once; there is no calendar-change refresh. The existing
checker opens a new page for each clock and does not exercise this transition.

**Fix:** Detect a change of California date while the page is visible and on
visibility/focus restoration. Refresh the hero, catalog, section links and any
open modal together, preserving navigation state. Add a same-page midnight test
that inspects rendered DOM badges, including an already-open modal. Comparing
visible text must account for CSS uppercasing.

### R2 — P2: the strict missing-date guard rejects a valid stored-vote row

**Location:** `scraper/src/website/election_status.py:230`.

**Evidence:** A row with `year=2026`, `election_date='2026-11-03'`,
`upcoming_scope='local'`, `passed=None`, and `yes_votes=123` correctly evaluates to
`unknown` under the documented precedence. Passing it to
`attach_election_status(..., as_of=date(2026, 11, 7), strict=True)` raises
`current-cycle measure 1 has no usable election_date`. Its date is valid.
The guard conflates the two reasons for `unknown`: missing date and stored votes
without a normalized outcome. This can block a legitimate release as result data
arrives. None of today's 63 rows triggers it.

**Fix:** Check date validity directly for the intended current-row population.
Keep the stored-vote/unknown branch separate. If such votes require an additional
release policy, implement and describe that policy explicitly rather than
reporting a nonexistent date error. Add strict-mode tests for current rows with
stored votes, including zero.

### R3 — P2: malformed check records can publish an undated results link

**Location:** `scraper/src/website/election_status.py:163`, `:182`, `:186`;
`scraper/src/website/generator.py:14614`.

**Evidence:** Used a scratch manifest with an otherwise valid link and
`last_check={"ok": true, "checked_at": "not a time"}`. `load_official_results()`
accepted it; `results_link_for()` exported it without HTTP or text-match evidence.
The actual browser helper rendered an “Official results” anchor without a check
date. `build_measure_pages.py:141` suppressed that same link, establishing a
browser/static disagreement. The three committed entries themselves are valid;
the two county successes display and the SOS failure is suppressed as intended.

The newest-check comparison also orders raw strings, not instants. A scratch
manual success at `2026-11-07T11:00:00-08:00` was hidden by the older automated
failure at `2026-11-07T18:30:00Z`. Although the manifest note requests UTC, the
loader accepts this offset. Equal instants written as `+00:00` and `Z` also yield
format-dependent decisions.

**Fix:** Validate check objects and timezone-aware timestamps at ingestion;
require automated successes to have status 200 and the expected matched text.
Either enforce one canonical UTC format or normalize before comparing instants.
Define a conservative tie rule. Have both renderers reject an unformattable check
date. Retain the existing fail-closed behavior for valid recorded failures.

### R4 — P2: “any stored vote figure” excludes `percent_no`

**Location:** `scraper/src/website/election_status.py:75`.

**Evidence:** A current row with a valid election date, `passed=None` and only
`percent_no=40.0` evaluates to `results_pending`; a strict attachment succeeds
and exports that status. The helper includes `percent_yes`, the vote counts and
`pass_fail`, but omits the other supported percentage field. The existing tests
do not cover this field. This is a synthetic input reproduction, not a reported
defect in the present 63 records.

**Fix:** Include `percent_no` in the stored-vote predicate, retaining the deliberate
distinction between zero and missing data. Parameterize the test over every
supported vote field and check both Python and exported/browser behavior.

### R5 — P3: Python accepts dates the browser cannot advance

**Location:** `scraper/src/website/election_status.py:64`, `:68`, `:284`.

**Evidence:** Attached statuses in strict mode for a November 2 build, then ran
the actual JavaScript contract in Node with `today='2026-11-07'`:

| Stored election date | Python on November 7 | Browser on November 7 |
|---|---|---|
| `2026-11-03` | `results_pending` | `results_pending` |
| ` 2026-11-03 ` | `results_pending` | `upcoming` |
| `2026-W45-2` | `results_pending` | `upcoming` |

Python strips whitespace and `date.fromisoformat()` accepts the ISO week date;
the original string stays in the exported row. The browser's calendar-date regex
rejects both and retains the build status. All 63 current dates are canonical,
so the real candidate does not encounter this discrepancy.

**Fix:** Define one accepted date representation. Validate calendar dates and
export their canonical `YYYY-MM-DD` value, or reject noncanonical inputs in both
halves. Add these cases to parity tests; do not silently normalize historical
JSON rows as a side effect of this fix.

### R6 — P3: the default release date is not recorded in `build.json`

**Location:** `scraper/scripts/build_release_bundle.py:43`, `:65`, `:82`.

**Evidence:** A scratch fixture exercised the real wrapper with subprocess builds
stubbed. Omitting `--as-of` omitted it from the generator command and wrote
`"as_of": null` in the successful report. Source inspection confirms the child
generator independently resolves today's Pacific date. Thus the machine-readable
receipt does not record the effective date, contrary to P0.1.05. The actual
generator log contains the date, but replaying the original command later can
change statuses. This probe was not a full frozen-workspace release build.

**Fix:** Resolve the date once in the wrapper, always pass it to the generator,
and record that same ISO date. Requiring `--as-of` for release bundles is also a
reasonable simpler policy. Preserve the convenient default for development builds.

## Answers to the seven review questions

1. **Rule correctness:** Withdrawal, recorded outcome, stored votes/unknown, then
   date is a conservative P0.1 ordering. Treat stored zero as present and do not
   infer pass/fail from `pass_fail`. Fix R2 and R4. Phase 2 will need explicit
   unofficial-result states; this temporary unknown state is not that design.
   Freshly rendered current cards, list rows, modals, section links and static
   pages passed. Open tabs are the missed consumer lifecycle (R1). The legacy
   unknown-card fallback still says “• Pending” at `generator.py:14750`; that
   fallback predates this change and is a separate wording follow-up.
2. **Browser clock:** Keep the browser correction: it fixes stale deployments on
   a fresh visit. California conversion and the build-status lower bound work
   for the canonical data, including Pacific midnight and a reader clock behind
   the build. Fix R1 and R5. A clock ahead can still advance an election too early;
   that is a limitation of using the reader's clock, not a timezone conversion
   defect. Static pages remain dependent on a rebuild, as disclosed.
3. **Wording:** “Results pending” is preferable to “Counting votes.” The static
   sentence and post-election modal note explicitly describe what CalBallot has
   recorded and do not claim an outcome, continuing counting or certification.
   On election day, “see the official results” is slightly awkward when no checked
   link is available; qualifying it with “when available” would be clearer.
4. **Link checks:** Status 200 plus election-specific text, known challenge
   rejection and an attributable manual check are adequate for this narrow
   link-only feature once R3 is fixed. They are not verification of vote totals.
   A failed or stale link should not globally block the status correction release;
   suppress failures and report missing/stale coverage in release evidence.
   The SOS omission is already explicit and owned by Igor. No live results URLs
   were fetched during this review and no challenge workaround was attempted.
5. **Build guards:** The current-date guard has the R2 false positive. The other
   guard also rejects a valid future `2028-11-07` row after
   `prepare_upcoming_display_fields()` because it gets no `upcoming_scope` under
   the 2026 selector. I reproduced the rejection. It is broader than an “older
   pending row” guard. Before Phase 3, separate release election membership from
   display-section membership and distinguish unresolved historical dates from
   legitimate future elections. The current 63-row strict build succeeds.
6. **Reproducibility:** An explicit release date is preferable, but requiring the
   flag is not essential if the effective default is resolved, passed and recorded
   once (R6). This flag controls election status; it does not freeze sitemap dates
   or the known regenerated `last_seen_at` values.
7. **Tests/checker:** The existing 41 tests and browser scenarios are useful and
   pass, but miss the reproduced cases. Add regressions with each fix. Further
   checker improvements below would make release evidence more independent.

## Suggestions, separate from the defects above

- **Strengthen the checker** (`scraper/scripts/check_election_status_browser.py:54`,
  `:95`, `:136`). Derive expected current IDs independently of the field being
  tested, so losing `election_status` cannot remove a row from coverage. Assert
  the reviewed slate size/IDs. Require the badge label even when the expectation
  is `upcoming`: the current `... or want == 'upcoming'` expression bypasses the
  card assertion in that case. Check rendered DOM as well as generated strings;
  normalize case for the visible-text scan. Resolve/freeze a reader date when
  `--clock` is absent instead of expecting the baked status while the browser
  uses its actual date. Include default-clock and unavailable-Intl cases.
- **Make check freshness visible to release reviewers**, without introducing a
  network-dependent global release gate. Record the checked timestamp, success or
  failure, and omitted scopes. Recheck county links for P0.3; leave P0.1.15 to Igor.
- **Keep preservation checks around these fixes.** Unknown historical labels and
  future-election section selection warrant explicit scope decisions, not
  incidental historical JSON/page churn during this patch.

## Independently rerun claims and observations

All scratch builds and auxiliary probes are outside the repository at
`C:\Users\igorg\AppData\Local\Temp\calballot-p0-1-review-0sab8m7d`.
Pytest basetemps are inside the workspace as requested. Evidence files in that
scratch directory are local working artifacts; the observations here are the
committed review record.

| Claim/check | Observed |
|---|---|
| Exact requested four-file pytest command, from `scraper/`, `--basetemp=.pytest-tmp/codex-p0-1` | **71 passed**, including all **41** election-status tests; 42.06 seconds |
| Full suite, `python -m pytest -q -p no:cacheprovider --basetemp=.pytest-tmp/codex-p0-1-full` | **654 passed, 1 skipped, 1 failed, 17 errors**; 117.81 seconds |
| Baseline `test_models.py`, `test_database.py`, `test_deduplication.py` | Exported unmodified source/tests from `git archive c7dc0efa` into scratch; **7 passed, 1 failed, 17 errors**. Same county-default assertion and `AttributeError: 'str' object has no attribute 'exists'`. The baseline full suite was not rerun. |
| Strict real generator, SQLite backup copy, `--as-of 2026-11-07`, then static builder | Both exited 0; **12,372** pages and **12,374** sitemap URLs |
| Byte comparison with published `measures/` | **63 changed**, all election date `2026-11-03`; **12,309 identical**; no added/deleted pages; no candidate page contains `Upcoming` |
| JSON comparison by ID and field | Same **12,372** IDs. Only differences: `election_status` on **63**, `official_results` on **49**, `last_seen_at` on **129** rows |
| Sitemap comparison | Only the two `lastmod` dates changed, from `2026-10-08` to `2026-11-07`; all other text identical |
| November 7 build / November 7 noon clock | All **63** `results_pending`, checker exit 0 |
| November 2 build / November 2 noon clock | All **63** `upcoming`, checker exit 0 |
| November 2 build / November 3 noon clock | All **63** `election_day`, checker exit 0 |
| November 2 build / November 3 23:59 clock | All **63** `election_day`, checker exit 0 |
| November 2 build / November 4 00:01 clock | All **63** `results_pending`, checker exit 0 |
| November 7 build / November 2 noon clock | All **63** stay `results_pending`, checker exit 0 |

Every browser row above used the supplied checker at **1440, 390 and 320px** with
`-08:00` clock offsets. All reported zero failures and no page errors; the checker
also passed its page and sampled modal overflow assertions. These are fresh-page
checks, distinct from the failing open-tab probe in R1.

The builds used the existing local embedding cache with Hugging Face offline
mode and dotenv loading disabled. The full-suite and baseline runs also disabled
dotenv loading; no test source was changed. Build, full-suite and baseline logs,
page/JSON diff reports, browser reports/screenshots, and edge-case probe outputs
remain in scratch. The results-link checker was inspected but not run against
live sites because it writes its checks in place.

The production DB was opened only read-only for SQLite's backup API; all builders
received the copy. Before/after SHA-256 checks match:

| Protected input | Unchanged SHA-256 |
|---|---|
| `scraper/data/ballot_measures.db` | `ef1359e482db2c54fe41068771932aaac7c9fc1db372e2e1d8cbbed1f505d9da` |
| Root `index.html` | `b0257999de740c6ed15990d0c44915b0e75de5bd1137e7ef6fb34794622c2cc8` |
| Root `measures-data.json` | `1921e5d463a450b5d0d017b673be0a86e47eb8a89fe82864890c2cbc5b3a72d1` |

No code, checked-link manifest, production database, published site artifact,
branch base or remote was changed. Only this response and the two authorized
checklist locations are part of the review commit.

## Re-review

**November 11, 2026 — reviewed `b2ab1fba..f30c2307` on
`phase0-election-status`. Technical verdict: ready for the current P0.1 scope;
R1–R6 are closed.** The requested transition, independent reproductions, tests
and preservation checks pass. One new low-priority checker defect, R7 below,
does not affect the current 63 unresolved measures. Fix it before using this
checker to gate a dataset containing stored votes or recorded outcomes.

**P0.1 closure:** the implementation review is complete. The whole checklist
chunk cannot yet be marked complete because **P0.1.15 remains unchecked**.
Igor must perform that manual check or explicitly defer it with its disposition
recorded. This review does not waive that item or authorize publication.

### Finding dispositions and rerun evidence

| Finding | Verdict | Independent reproduction and result |
|---|---|---|
| **R1** Open-tab refresh | **Closed** | The requested November 2 build, November 3 23:59 to November 4 00:01 transition passed with `--expect-count 63`. All 14 rendered statewide cards changed from Election day to Results pending and the already-open modal updated. The original November 2 23:59 to November 4 00:01 reproduction also passed in UTC and Asia/Tokyo browser zones, using timer, focus and visibility triggers. See the navigation checks below. Fix: `scraper/src/website/generator.py:11222`, `:11241`, `:11256`. |
| **R2** Strict guard conflates unknown with missing date | **Closed** | The original valid-date current row with `passed=None, yes_votes=123` now passes strict attachment, gains no calendar status and evaluates to `unknown` in Python and Node. Repeated with zero votes: same result. The new tests also cover all six vote fields, invalid dates, withdrawal and the valid 2028 future row. Fix: `scraper/src/website/election_status.py:275`, `:283`. |
| **R3** Malformed checks and timestamp ordering | **Closed** | The original `last_check={"ok":true,"checked_at":"not a time"}` manifest now raises a timezone-aware timestamp validation error. A valid timestamp without HTTP/text evidence is also rejected. The manual success at `11:00-08:00` correctly beats the `18:30Z` failure and exports `19:00Z`; the equal-instant `Z`/`+00:00` failure suppresses the link. Injecting the original invalid-date public link into the actual explorer helper now returns an empty string; static rendering likewise omits the link. Fix: `scraper/src/website/election_status.py:146`, `:159`, `:212`; `scraper/src/website/generator.py:14660`. No live links were checked. |
| **R4** Missing `percent_no` | **Closed** | The original `percent_no=40.0`-only row, and a zero-valued variant, both pass strict attachment without a calendar field and return `unknown` in Python and Node. The explicit vote-field coverage and parameterized tests pass. Fix: `scraper/src/website/election_status.py:66`. |
| **R5** Noncanonical date parity | **Closed** | Strict attachment rejects the original whitespace-padded and ISO week dates, plus `20261103`, with `expected YYYY-MM-DD`. Nonstrict attachment leaves them without a calendar status; both Python and Node return `unknown`. Canonical `2026-11-03` still advances from a November 2 build to `results_pending` on November 7. Historical page/JSON preservation is unchanged. Fix: `scraper/src/website/election_status.py:69`. |
| **R6** Unrecorded default release date | **Closed** | Reran the real wrapper against a scratch SQLite fixture with child builds stubbed, as in the original reproduction. At a frozen UTC clock of `2026-11-08T07:30:00Z`, omission passes and records **2026-11-07**, the California date. Explicit `--as-of 2026-11-02` passes and records **2026-11-02**. The repository's wrapper test also passes. Fix: `scraper/scripts/build_release_bundle.py:49`, `:85`. This checks wrapper behavior, not a full recovery-workspace release. |

The independent R1 probe used a real generated explorer with requests routed to
scratch files and all external requests aborted. It selected San Mateo, moved
the statewide carousel to index 4 and the local carousel to index 5, selected
catalog page 2, and opened a local measure before advancing the clock. The
carousel indices and CSS transforms, county, page, view, modal tab, permalink
and open state all remained identical. The Main tab retained its nonzero
`scrollTop=150`; Research and Finance stayed selected in their respective cases.
With the 2026 catalog filter applied, all 12 visible grid badges and all 10
visible list badges advanced from Upcoming to Results pending. The open local
modal gained its checked results link, its note updated, and the local section
link appeared. All 14 hero badges advanced; there were no page errors. Focus
and visibility were dispatched as browser events; the timer case used
Playwright's installed clock and advanced beyond the refresh interval.

### New defect: R7 — P3, checker rejects a supported unknown state

**Location:** `scraper/scripts/check_election_status_browser.py:114`.

The revised checker correctly discovers rows independently of `election_status`,
but then requires every non-withdrawn current-cycle row to have one of the three
calendar statuses. That is incompatible with the stored-vote/unknown contract
verified in R2 and R4, and with recorded outcomes, which intentionally gain no
calendar field.

**Reproduction:** In a separate scratch copy of the November 7 site JSON, set
current local measure **12420** to `yes_votes=123, passed=None`, removing its
calendar status and results link as attachment would. The real strict
`attach_election_status()` accepts that complete row and returns zero attached;
`election_status()` returns `unknown`. Running the checker with
`--clock 2026-11-07T12:00:00-08:00 --expect-count 63` nevertheless exits **1**:

```text
12420: current row has no calendar status (None)
```

That is its only failure. It reports 63 current rows but tests 62 calendar rows
at each width, with no page errors. This is a checker false positive on a
synthetic supported row, not a failure of the real 63-row candidate or a reason
to reopen R2.

**Fix:** Determine which rows require calendar fields from their withdrawal,
outcome and stored-vote evidence. Require the field only for date-dependent
rows; verify the appropriate unknown/passed/failed display for the others.
Retain independent ID/count coverage and the failure for an accidentally missing
calendar field. Add a mixed-state checker regression before the result-import
phase. This is nonblocking for P0.1's current dataset, where all 63 rows are
date-dependent; it remains an open follow-up.

### Checker suggestions and validation receipt

The requested improvements otherwise landed: independent scope selection,
`--expect-count`, rendered hero checks, unconditional label assertions,
case-insensitive visible-text scanning, a frozen default clock, and same-page
transition coverage. The no-Intl Node test passes. The supplied transition check
is desktop-only and does not itself assert preserved navigation state or exercise
the appearance of a local results link; the independent probes above cover
those gaps. No new production-rendering defect was demonstrated.

Scratch root for this re-review:
`C:\Users\igorg\AppData\Local\Temp\calballot-p0-1-rereview-dv3tyhhe`.
Both strict builds used the SQLite backup copy, offline model loading and
`--force --strict`, with `--as-of 2026-11-02` and `2026-11-07` respectively.
The requested browser invocation was:

```text
python scraper/scripts/check_election_status_browser.py --site-dir <scratch>/site-before --output-dir <scratch>/browser-transition --clock 2026-11-03T23:59:00-08:00 --transition-to 2026-11-04T00:01:00-08:00 --expect-count 63
```

| Rerun | Observed |
|---|---|
| Four targeted files from the original review, `--basetemp=.pytest-tmp/codex-p0-1-rereview`, cache provider disabled | **111 passed**, including **81** election-status tests; 50.74 seconds |
| Full suite, `--basetemp=.pytest-tmp/codex-p0-1-rereview-full`, cache provider disabled | **694 passed, 1 skipped, 1 failed, 17 errors**; 133.12 seconds. Same model county-default failure and string-path database/deduplication errors independently confirmed on the base during the first review. The baseline was not rerun again. |
| Requested browser transition | Exit **0**, zero failures; all **63** Election day at 1440/390/320px; desktop transition updates **14** hero cards and the open modal to Results pending |
| November 7 build, checker with `--expect-count 63` and no `--clock` | Exit **0**, zero failures; default frozen reader date **2026-11-11**, all **63** Results pending at all three widths |
| Static build and comparison with published pages | **12,372** pages; **63 changed**, **12,309 identical**, no added/deleted files, no `Upcoming` in candidate pages |
| Comparison with the first review's retained scratch candidate | All **12,372 static pages byte-identical** |
| JSON comparison with published data | Same **12,372 IDs**; only `election_status` (**63**), `official_results` (**49**) and `last_seen_at` (**129**) differ |
| Protected inputs | Production DB, root `index.html` and root `measures-data.json` hashes unchanged and equal to the full hashes recorded above |

Logs, browser reports/screenshots and independent reproduction outputs remain
under that scratch root, including `original-reproductions.json`,
`browser-independent-filtered-probes.json`, `preservation-counts.json` and
`protected-hashes.json`. This pass reran the requested transition, the original
finding reproductions and the default-clock case; it did not repeat all six
fresh-load scenarios from the first review. The production database was opened
read-only solely for SQLite backup. No live checks, code edits, generated-file
commits, pushes, merges or publication occurred.
