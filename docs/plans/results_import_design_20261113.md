# P2 design: results for the 63 current measures

**Date:** November 13, 2026. **By:** Fable. **Status:** chunk (a0), the rules-and-evidence
contract that chunks (a1), (b), (c) and (d) build against. Nothing is built.
**Goal:** results for the 14 statewide, 20 San Bernardino and 29 San Mateo measures appear on
the site, first as unofficial (optional), then certified, on a path the county expansion can
reuse.
**Builds on:** [results transition](results_transition_20260907.md), the
[layout review](../codex/layout_direction_a_review_response.md) (answer 2), the
[CEDA design](ceda_backfill_design_20261112.md) and its
[revision review](../codex/p1b_1b_revision_review_response.md) (N1).
**Method:** no network. I read the code, the docs and the four result files saved on
November 5-7. The production database was read only; its SHA-256 was
`ef1359e482db2c54fe41068771932aaac7c9fc1db372e2e1d8cbbed1f505d9da` before and after.

## Revision, November 13

Codex reviewed the first version: **ready with changes**
([response](../codex/p2_results_design_review_response.md)). This version answers it.

| Finding | Answered in |
|---|---|
| **R1** Multi-county outcome conflicts with the status precedence; new columns never reach the site | §4.2 (one outcome function, exact precedence), §4.3 (consumers), §4.4 (transport) |
| **R2** A real precinct CSV as a public fixture | §6 |
| **R3** Selection by capture time; observation identity collides on corrections | §2.2 (identity), §2.4 (selection by the source's own order) |
| **R4** A predecessor hash misses tail edits and truncation | §2.3 |
| **R5** Mapping and certification not tied to the exact report and contest | §3.1, §3.3 |
| **R6** "All counties certified" is not enough for a derived total | §4.5 |
| **R7** Zero totals, unknown rules, percentage units | §3.2, §5.2 |
| **R8** Captures can be replaced; no independent San Mateo total | §1.2 |
| Question 8 table, Igor's answers | §10 |
| Revised chunk order; P2(c) before Explore E2c | §9 |
| Interfaces for (a1) and (b) | §7 |

## 0. The design in seven lines

1. Igor saves eight files per capture by hand, into a folder that is never changed again.
2. Importers are pure parsers. A shared step turns a parsed report plus the reviewed
   mapping into **observations** in an append-only ledger.
3. An observation is never edited. A correction is a new observation that names the one it
   replaces, and why.
4. A **reviewed selection file** says which observation the site shows for each measure. It
   is the build's actual input, and it pins the ledger's length and final hash.
5. **Unofficial observations never touch the `measures` table.**
6. **Only a certified observation writes an outcome**, in one reviewed transaction.
7. Every surface asks **one function** for a measure's outcome. For a multi-county measure
   it answers only from the whole contest, never from a county's portion.

## 1. Sources and captures

### 1.1 Sources

| | Secretary of State (`sos_api`) | San Bernardino (`sb_summary`) | San Mateo (`smc_csv`) |
|---|---|---|---|
| Reader link | `electionresults.sos.ca.gov/returns/ballot-measures` | `results.rov.sbcounty.gov/Results/20261103/` | `smcacre.gov/elections/november-3-2026-election-results` |
| Data file | JSON at `api.sos.ca.gov/returns/ballot-measures` | "Excel Version (XLSX)": `ElectionSummaryReportRPT.xlsx` | "Results on CSV": `/media/<id>/download?attachment` |
| Seen in a saved file | `ReportingTime`, `Reporting`, 14 entries with `Number`, `Name`, `yesVotes`, `noVotes`, `yesPercent`, `noPercent`, all strings | The saved **page**: per contest a title, "Precincts Reported", "Times Cast a / b", YES and NO with percents, "Total Votes". **No xlsx is held yet** | **No CSV is held yet.** The November 5 assessment describes precinct by vote method rows |
| Contest identity | `Number` **and** `Name` together | The title, e.g. "City of Needles MEASURE D (Vote for 1)" | Unverified |
| The report's own order | `ReportingTime` | "Summary Report #5" | Unverified; the summary PDF's file name carries a date |
| Election identity inside the file | None. Checked through the 14 numbers and names (§3.1) | "11/03/2026 - Statewide General Election" | Unverified |
| Status wording | None | "Final Unofficial Election Night Results" | Unverified |

Still true from the first version: the SOS reader page is bot-challenged; San Bernardino's
page lists exactly our 20 measures (A-R, Y, Z) plus 14 county portions of the propositions;
titles do not match our jurisdiction names; "100% of precincts" proves nothing about
status; and San Mateo's CSV holds a two-voter precinct split.

### 1.2 Captures (R8)

**One folder per capture, never changed afterwards:**
`scraper/data/raw/results/2026-11-03/<capture_id>/`, where `<capture_id>` is the local save
time with its offset, for example `20261113T1730-0800`. The path is gitignored.

- A second save on the same day is a new folder. Nothing is added to, or replaced in, an
  existing one. A wrongly saved file means a new capture.
- The two script captures already filed (`2026-11-05/`, `2026-11-07/`) keep their names.
  They are registered with `acquisition: "script"` and their original times, not the day
  they were copied.

**Files in each capture:**

| # | Save as | Open | Do |
|---|---|---|---|
| 1 | `sos_ballot_measures.json` | `https://api.sos.ca.gov/returns/ballot-measures` | Save the page as a file |
| 2 | `sos_returns_page.pdf` | `https://electionresults.sos.ca.gov/returns/ballot-measures` | Print to PDF. Context and a human link check only; it certifies nothing |
| 3 | `sb_summary.xlsx` | The San Bernardino results page | Downloads, "Excel Version (XLSX)" |
| 4 | `sb_summary.pdf` | same | Downloads, "Print Friendly Version (PDF)" |
| 5 | `sb_results_page.html` | same | Save as "Webpage, HTML only" |
| 6 | `smc_results.csv` | The San Mateo results page | "Results on CSV" |
| 7 | `smc_summary.pdf` | same | **"Results on PDF"**. This is the independent total the CSV is reconciled against |
| 8 | `smc_results_page.html` | same | Save as "Webpage, HTML only" |

**Then, in the folder** (the command leaves its own output out of the list):

```text
Get-ChildItem -File | Where-Object { $_.Name -notin 'SHA256SUMS.txt','capture.json','NOTES.txt' } | Get-FileHash -Algorithm SHA256 | ForEach-Object { "$($_.Hash.ToLower()) *$(Split-Path $_.Path -Leaf)" } | Set-Content -Encoding ascii SHA256SUMS.txt
```

Add a `NOTES.txt`: who saved, the time with its offset, and anything odd.

**`capture.json`** is written last, by the registration script built in (a1). It binds the
capture together and is never rewritten:

```text
{ "schema": "calballot-results-capture/1", "capture_id": "20261113T1730-0800",
  "election_date": "2026-11-03", "saved_at": "2026-11-13T17:30:00-08:00",
  "saved_by": "Igor", "acquisition": "manual_browser",
  "artifacts": [ { "file": "sb_summary.xlsx", "source": "sb_summary", "sha256": "…",
      "bytes": 0, "source_url": "…", "final_url": null,
      "report": { "seq": 7, "as_of_text": "…", "status_text": "…", "election_text": "…" } } ],
  "artifacts_sha256": "<hash of the canonical artifacts list>" }
```

The script refuses a folder that already has `capture.json`; a file missing from
`SHA256SUMS.txt`; a hash that does not match; and an unlisted file name. It creates
`capture.json` with exclusive create, so it cannot overwrite. `report` holds what the file
says about itself. It is filled by the parser, never from the folder name.

**When:** now, then November 20 and 27, December 4 and December 12. These are planning
days, not status switches: certified material is saved whenever a source publishes it.

**At certification, also save:**
- each county's **actual** official results and Statement of Vote documents, and its
  **certification statement**, not only an index page;
- the state's Statement of Vote spreadsheet and certification;
- for each multi-county measure (§4.1): each other county's exact contest page or table,
  its certification statement, and the document that shows which counties the district
  covers.

**Once, before the propositions can carry an approval rule:** the authority packet (§3.2).

**Recovery** needs all of: the raw captures and their manifests, the ledger, the mapping,
the rules, the certifications, the selection, and the code. The coordinator adds the raw
folder to the private recovery bundle.

## 2. The ledger

### 2.1 Files

All under `scraper/src/website/data/results/2026-11-03/`, committed, with a `-text` rule in
`.gitattributes` for the whole folder so Windows never converts their line endings:

| File | Holds | Changes by |
|---|---|---|
| `sources.json` | Source keys, publishers, URLs, the status wording each source uses, and its reviewed time zone | Review |
| `rules.json` | Approval rules and their authorities (§3.2) | Review |
| `mapping.json` | Contest-to-measure entries and multi-county groups (§3.1, §4.5) | Review |
| `observations.jsonl` | Observations | Append only |
| `certifications.jsonl` | Certification annotations (§3.3) | Append only |
| `selection.json` | What the site shows, and the ledger anchors (§2.4) | Review, each release |

### 2.2 Identity (R3)

Two identities, kept apart:

- **`source_record_id`**: SHA-256 over the election date, source, artifact SHA-256 and the
  contest's raw key. It names one contest in one saved file.
- **`observation_id`**: SHA-256 over the canonical normalized observation: election date,
  source, `source_record_id`, measure `id` and canonical key, scope, scope county, group,
  every count, status, `certification_id`, the report's own order and as-of text, the
  mapping entry's hash, the importer name and its `interpretation_rev`.

Consequences:
- Running the same importer on the same file again yields the same `observation_id`, and
  appends nothing.
- A parser fix, a mapping correction or added certification evidence yields a **different**
  `observation_id` for the same `source_record_id`. It must carry `supersedes` (the earlier
  observation) and a `reason`: `parser_fix`, `mapping_fix`, `certification_added`,
  `source_correction` or `retraction`.
- The validator requires that the superseded observation exists earlier in the file, is
  for the same measure, scope and county, has no other direct successor, and that the
  relation has no cycle.
- A **retraction** is a line with `kind: "retraction"`, `supersedes` and a reason, and no
  counts. The retracted observation can no longer be selected. This is how an erroneous
  certified selection is withdrawn without deleting history.

### 2.3 Bytes, anchors and appends (R4)

- **Canonical line:** one JSON object; UTF-8 without a byte-order mark; keys sorted;
  separators `,` and `:`; non-ASCII characters written as themselves, in NFC form; counts
  as JSON integers; **no floating-point number anywhere** (percentages are text); one LF
  after each line, including the last.
- **Chain:** each line has `seq` (from 1) and `prev`, the SHA-256 of the previous line's
  bytes without its LF. The first line's `prev` is the SHA-256 of the text
  `calballot-results/1/2026-11-03`.
- **Anchor:** `selection.json` records the ledger's line count and the SHA-256 of its last
  line. A build that finds a different count or hash stops. This catches a deleted or
  edited last line, which the chain alone does not.
- **Append-only against Git:** a check compares the working file with the same file at a
  named base commit: the base's bytes must be an exact prefix. The release gate runs it
  against the last released commit.
- **One writer.** Importers never write the ledger. They emit a candidate batch (§7.3). One
  append command validates the whole batch against the existing ledger, writes the new
  file beside the old one, and replaces it in a single step. A batch with one bad contest
  appends nothing. The append command alone assigns `seq`.

### 2.4 Selection (R3)

`selection.json` is the **build input**, not a receipt:

```text
{ "schema": "calballot-results-selection/1", "election_date": "2026-11-03",
  "anchors": { "observations": { "lines": 126, "last_sha256": "…" },
               "certifications": { "lines": 0, "last_sha256": "…" },
               "mapping_sha256": "…", "rules_sha256": "…", "sources_sha256": "…" },
  "measures": [ { "measure_id": 12424, "contest": "<observation_id or null>",
                  "portion": null, "override": null } ],
  "reviewed_by": "Igor", "reviewed_at": "…" }
```

- **A proposal tool** picks, for each measure and scope, the observation that is not
  superseded or retracted and stands latest **in the source's own order**: the report
  sequence where the source has one, otherwise the report's as-of time. Capture time is
  provenance only: an old report downloaded today stays old.
- **It refuses to choose** when the order is missing, when two reports share an order but
  differ in counts, or when two sources supply the same scope. It lists those for review
  and exits non-zero.
- **No stale rollback.** Against the last released selection, each measure's chosen
  observation must be the same or later in source order, unless the entry carries an
  `override` with a reason.
- **A strict build stops** when a current measure is missing from the selection, a chosen
  observation is absent, superseded or retracted, or any anchor differs.

## 3. Mapping, rules and certification

### 3.1 Mapping (R5)

One entry per source contest:

```text
{ "source": "sb_summary", "election_date": "2026-11-03",
  "contest": { "key": "City of Needles MEASURE D", "aliases": [] },
  "measure": { "id": 12424, "canonical_measure_id": "REG_SB_20261103_4F39…",
               "county": "SAN BERNARDINO", "jurisdiction": "City of Needles",
               "designation": "D" },
  "identity_evidence": { "document_sha256": "…", "role": "measure_text", "note": "…" },
  "scope": "contest", "scope_county": null,
  "scope_evidence": { "basis": "…", "document_sha256": "…" },
  "group": null, "rule": "majority",
  "reviewed_by": "…", "reviewed_at": "…" }
```

- **Identity is pinned from evidence, not copied from the row.** `identity_evidence` names
  the captured ballot question or measure document that shows this contest is this
  measure. An entry that merely repeats the target row's own fields proves nothing.
- **Every one of the 49 local entries needs `scope_evidence`.** "Whole contest" is a claim
  to be shown, not a default.
- **The file's own election identity is checked**, never the folder name. For the SOS JSON,
  which carries no date, the entry pins `Number` and `Name` together, and the set of
  numbers must be exactly 1-5 and 37-45.
- **Statewide numbers** resolve through `statewide_ballot_entries.proposition_number` for
  the election date, with exactly one qualified entry each. Propositions 3, 4 and 5 are ids
  10960, 10956 and 2. The withdrawn ACA 13 (id 1) is listed as "no contest expected".
- **Contests that are not ours.** Each source has a reviewed pattern for what a measure
  title looks like. Every measure-like contest must be mapped, or ignored with a reason
  (San Bernardino's 14 "PROPOSITION n" rows are county portions of statewide measures).
  A YES/NO contest that is not measure-like must match a reviewed non-measure pattern, such
  as judicial retention. Anything else stops the import.

### 3.2 Approval rules (R5, R7)

`rules.json` defines each rule once, as an exact comparison on whole numbers, where
N = yes + no:

| Rule | Passes when | Fewest yes votes that pass |
|---|---|---|
| `majority` | yes > no | floor(N / 2) + 1 |
| `pct55` | 100 × yes ≥ 55 × N | ceiling(55 × N / 100) |
| `two_thirds` | 3 × yes ≥ 2 × N | ceiling(2 × N / 3) |
| `unreviewed` | never computed | none |

- **The denominator is yes plus no.** Ballots cast, registration and "Times Cast" are kept
  as separate facts and never substituted.
- **A measure gets a rule only from a reviewed authority,** recorded with the document, its
  hash, the page and the wording. The stored `vote_threshold` text ("50%", "55%",
  "66.67%") is a pointer to look up, not the authority; the 49 local rules are confirmed
  against the registrar's own "percentage to pass" text in the captured snapshots.
- **The 14 propositions stay `unreviewed`** until the authority packet is saved and
  reviewed: California Constitution Article II §10(a), Article XVIII §4 and Article XVI §1,
  plus each proposition's own enabling or referral text. Until then they read "Approval
  requirement not listed".
- **Counts must be whole numbers, zero or more.** Booleans, negatives, fractions and blank
  cells are rejected. Null and zero are different things.
- **No outcome is computed** when N is zero or the rule is `unreviewed`. The counts are
  shown and the result is marked as not determined (§5.1).
- "Two-thirds" is displayed as words, never as a 66.67% cut-off.

### 3.3 Certification (R5)

A certification is its own immutable line in `certifications.jsonl`:

```text
{ "certification_id": "<hash>", "election_date": "2026-11-03",
  "authority": "San Bernardino County Registrar of Voters", "county": "SAN BERNARDINO",
  "document": { "capture_id": "…", "file": "…", "sha256": "…", "url": "…" },
  "statement": { "page": 1, "quote": "…" }, "certified_on": "2026-12-01",
  "covers": { "source": "sb_summary", "artifact_sha256": ["…"], "report_seq": 12 },
  "reviewed_by": "…", "reviewed_at": "…" }
```

- An observation becomes certified only through a **new** observation (reason
  `certification_added`) that names a `certification_id`.
- The certification must name the same authority, county and election, and its `covers`
  must name that observation's artifact or report. A general certification PDF does not
  certify an earlier, different report.
- These never count as certification: "Final unofficial", 100% of precincts, a date, or a
  link's label. San Mateo's "Statement of the Vote" link points at a placeholder today.

## 4. Multi-county measures and the one outcome function

### 4.1 The known cases

| id | Measure | We hold | Other counties |
|---|---|---|---|
| 12418 | San Bernardino Community College District Y | San Bernardino's portion | Riverside |
| 12421 | Beaumont Unified School District B | San Bernardino's portion | Riverside |
| 12442 | Public transit revenue measure | San Mateo's portion | Alameda, Contra Costa, San Francisco, Santa Clara |

**This list is not proven complete.** The scope review of all 49 entries (§3.1) settles it.

### 4.2 Columns and the outcome function (R1)

Columns added to `measures` (plain `ADD COLUMN`; the migration must be safe to run twice,
on today's schema and on the future CEDA one):

| Column | Meaning |
|---|---|
| `multi_measure_id` | Group key, e.g. `REG:2026-11-03:SBCCD-Y`; CEDA will use `CEDA:<year>:<Multi_MeasID>`. NULL for a single-county measure |
| `passed` (existing) | **The row's own result only**: for a grouped row, the county portion against the rule. A source fact, never a badge |
| `combined_yes_votes`, `combined_no_votes`, `combined_passed` | The whole contest's result |
| `result_observation_id` | The observation behind the row's own votes |
| `combined_observation_id` | The observation behind the combined result. Two ids, because the two have different sources |

**`effective_outcome(measure)`** is the only way any surface learns an outcome:

| Order | Condition | Outcome | Basis |
|---|---|---|---|
| 1 | `ballot_status` is withdrawn | none | withdrawn |
| 2 | `multi_measure_id` is set and `combined_passed` is 0 or 1 | failed or passed | combined; "certified" if `combined_observation_id` is set, else "recorded" (historical) |
| 3 | `multi_measure_id` is set, no combined result | **none**, reason `combined_unavailable` | The row's `passed` and vote fields are ignored here, and do not trigger "Result unknown" |
| 4 | Not grouped, `passed` is 0 or 1 | failed or passed | row; "certified" if `result_observation_id` is set, else "recorded" |
| 5 | Otherwise | none | reason `stored_votes_without_outcome` if any vote field is set, else none |

**Status then follows, in this order:** withdrawn; a passed or failed outcome; a selected
unofficial whole-contest observation (`unofficial`); a selected certified observation with
no computed call (`certified_no_call`, §5.1); for a grouped row with only a portion,
`results_pending` with the portion attached; "Result unknown" for an ungrouped historical
row with stored votes; then the calendar statuses.

A grouped row with `passed = 0` and `combined_passed = 1` is therefore **Passed**. With no
combined result it is **pending**, never Failed. Tests pin both, and the opposite pair.

Historical outcomes stay "recorded". Nothing becomes "Certified" by having `passed` filled.

### 4.3 Every consumer (R1)

The function ships in one module in three forms: Python, the JavaScript for the explorer,
and a SQL expression, `CASE WHEN multi_measure_id IS NOT NULL THEN combined_passed ELSE
passed END`. Python and JavaScript are tested against each other in Node.

| Consumer (lines as cited by the review) | Change |
|---|---|
| `election_status.py:96-112`; `build_measure_pages.py:113-122`, `:245` | Call the function before any raw `passed` check |
| Explorer cards, list, modal, filters, sort, statistics (`generator.py:10899`, `:10938`, `:11013`, `:11037`, `:14184`, `:14292`, `:14384`, `:14439`) | Use the JavaScript form; define how filters treat `unofficial` |
| Explore (`generator.py:11689`, `:11998`) | Leave grouped rows without a combined result out of rates; count a group once in cross-county cohorts |
| County history (`local_measure_context.py:121-161`; `county_content.py:154`) | Use the function, so CEDA groups read the same once populated |
| Build statistics and recommendations (`database/operations.py:481`; `generator.py:461`, `:480`; `generate_site.py:348`, `:435`) | Use the SQL or Python form |
| Insights, exports, research (`generate_insights.py:263`, `:315`; `generator.py:9857`; `database/operations.py:360`; `research/sources/historical.py:257`, `:366`) | Raw row fields stay as scoped facts; any claim about a whole measure uses the function |
| `check_export_contract.py:11` | Either leave the raw exports unchanged and document their scope, or version the contract |

All of these change in one commit, before any county `passed` is projected.

### 4.4 Getting new fields to the site (R1)

`generate_site.py:128` filters rows into `BallotMeasure`, and `:235` rebuilds the site's
dictionaries from those models, so a new database column disappears unless the model
carries it. Contract: the six columns above are added to `BallotMeasure` and to
`valid_fields`, **keeping `id`**, with a test that a row holding them reaches
`measures-data.json`. The nested `result` object (§5.3) is attached afterwards, by integer
`id`, the way `attach_election_status` works today.

### 4.5 Combined results (R6)

`mapping.json` has a `groups` list:

```text
{ "multi_measure_id": "REG:2026-11-03:SBCCD-Y", "rule": "pct55",
  "members": [ { "county": "SAN BERNARDINO", "source": "sb_summary", "measure_id": 12418 },
               { "county": "RIVERSIDE", "source": "manual", "measure_id": null } ],
  "membership_evidence": { "document_sha256": "…", "note": "district boundary" },
  "consolidated_source": null, "aggregation": "sum_disjoint_county_portions/1",
  "reviewed_by": "…", "reviewed_at": "…" }
```

A whole-contest observation comes from one of two places:

1. **An authoritative consolidated result**, when a source publishes one. It is preferred.
   If such a source publishes an unofficial consolidated total, it may be shown as
   unofficial.
2. **A derived total**, the sum of county portions, allowed only when **all** of these hold:
   - the group's membership and rule are reviewed, with evidence;
   - every member has **exactly one** selected observation, with scope `county_portion`,
     certified under §3.3, for the same election and group;
   - a member with no voters is an explicit observation with zeros and evidence, never an
     omission;
   - no input is a consolidated total posing as a portion. The check: no member's counts
     equal another member's, or the sum of the others; a match goes to review;
   - the inputs share one rule.

A derived observation records every input `observation_id`, the mapping hash and the
aggregation version. Its status is `derived_from_certified`, and the site labels it
**"CalBallot total from certified county results"**. No authority certified the sum itself.

**If any input is superseded or retracted,** the derived observation is no longer valid:
the selection validator rejects it until a new one is derived, and the new selection and
projection ship in one reviewed release.

**CalBallot never adds unofficial portions together**, and never averages percentages.

Other counties' certified portions enter through the manual form (§7.4), with the same
gates as an importer. No new `measures` rows are needed for them.

## 5. Projection to the site

### 5.1 States

| State | When | Card | Detail |
|---|---|---|---|
| Results pending | No selected observation | As today | As today |
| **Unofficial** | A selected unofficial whole-contest observation | "Unofficial · as of [source time]" · "52.3% yes · Needs 55%" | Counts, rule, margin, source, as-of. **No Passed or Failed, no outcome color** |
| **Certified passed / failed** | The outcome function answers from a certified observation | "Passed · Certified" / "Failed · Certified" | Counts, margin, certification authority and date |
| **Certified, no result determined** | Certified counts, but zero votes or an unreviewed rule | "Certified count" · counts | Says why no result is stated |
| Withdrawn; Result unknown | As today ("Result unknown" stays for historical rows) | As today | As today |

**Grouped rows** add a scope line, and keep two things apart, as Igor asked:

| Situation | Reads |
|---|---|
| County portion available, combined not | "Combined result not available yet" + "San Bernardino County portion · Unofficial as of …" (or "· Certified") with its counts |
| Neither available | "Results pending" |
| Combined available | The combined result leads; the portion follows, labelled as a portion |
| Combined is a derived total | Labelled "CalBallot total from certified county results" |

A certified portion is shown as certified. It is never relabelled unofficial, and never
gets a Passed or Failed of its own.

"Unofficial" and "Certified" appear as words on cards and in the detail (Igor, question 6).
Exact placement is settled in (c-core) and is Igor's call.

### 5.2 Numbers (R7)

- **Every new percentage is text made from whole counts**, in a field whose name ends in
  `_text`. The `result` object has no numeric percentage.
- **Units.** `generate_site.py:264-267` multiplies any stored percent of 1 or less by 100,
  so a certified 0.5% would display as 50%. (c-core) limits that rule to the legacy sources
  that store fractions, and never applies it to a row with `result_observation_id`. Tests
  cover 0.5%, 1% and 99.5%.
- **The displayed percent sits on the true side of the rule**, above and below, including a
  tie under `majority` and a repeating two-thirds. Start at one decimal and add up to three.
  If that still misleads, show "just under 55%" or "just over" with the exact counts.
- **Margins** are computed from counts first and formatted afterwards.
- The source's printed percent is kept as text and compared with the counts, within the
  source's printed precision (0.05 points for the SOS file's one decimal).

### 5.3 What reaches the site

Each current measure gains a `result` object in `measures-data.json`:

```text
{ "state": "unofficial", "basis": "contest",
  "yes_votes": 0, "no_votes": 0, "yes_percent_text": "52.3",
  "rule": { "id": "pct55", "label": "Needs 55%" }, "margin_text": "2.7 points below",
  "status_label": "Unofficial", "as_of_text": "…", "source": { "publisher": "…", "url": "…" },
  "portion": null, "combined_note": null, "observation_id": "…" }
```

- **Unofficial:** nothing in `measures` changes; top-level `passed`, vote and percent
  fields stay as they are. No convenience copy of nested votes upward, ever: the status
  rule reads any top-level vote without an outcome as "Result unknown".
- **Certified:** one transaction writes the row's own votes and `passed`, the combined
  columns where they apply, and both observation ids. A strict build stops if those ids
  and the selection disagree.
- **`official_results`** stays attached for unofficial and certified current rows, by an
  explicit rule; today it is attached only to calendar statuses (`election_status.py:281`).
- The weekly registrar load must leave every new field alone; a test pins it, and another
  pins that outcomes cannot be injected through document loading.

### 5.4 The P0.1 status contract

- `unofficial` and `certified_no_call` are **observation-driven**, outside
  `DATE_DRIVEN_STATUSES`. The reader's clock still only advances calendar statuses; it never
  turns unofficial into certified, and an as-of time is always the source's.
- `attach_election_status` attaches these states and the `result` object, and keeps the
  strict guards for current rows' dates and for unexplained historical "pending" rows.
  New strict checks: anchors, selection, mapping and rule hashes, scope and evidence.
- The JavaScript `getElectionStatus`, the labels, the static `outcome()`,
  `isPendingMeasure`, section notes, filters and local cards all take the new projection.
- `check_election_status_browser.py` must classify rows from observation fixtures, not from
  the status under test. Per the review it currently treats an unofficial row as
  calendar-dependent (`:58`), rejects `unofficial` (`:73`), forbids any link on resolved
  rows (`:80`) and has fixed badge maps (`:44-47`).

## 6. Fixtures and privacy (R2)

- **No real San Mateo CSV in the repository, whatever its size.** The same holds for any
  file with precinct rows.
- **Public fixtures are synthetic or reviewed.** For the CSV: a generated file with the real
  header and row structure and invented precincts and counts, including a small cell, a
  subtotal row and a vote-method split. Its README records the private file's hash and how
  the fixture was derived. Trimming a real file is not enough.
- **The two SOS files** hold statewide totals only and may be committed as they are.
- **San Bernardino's summary** may be committed only after a review confirms it holds
  contest totals and no precinct rows (§10, open question 5).
- **Tests on the real private files** run locally, are skipped when the files are absent,
  and report their counts and hashes in the chunk's handoff.
- The public ledger holds contest totals only. No public precinct results in this version.

## 7. Interfaces for (a1) and (b)

### 7.1 Code layout

```text
scraper/src/results/
  contract.py     dataclasses, canonical bytes, ids, rule arithmetic, error codes   (a1)
  capture.py      read and write capture.json                                       (a1)
  ledger.py       read, verify chain and anchors, append one batch                   (a1)
  mapping.py      load and validate mapping.json, rules.json, sources.json           (a1)
  candidates.py   SourceReport + mapping -> candidate batch                          (a1)
  importers/sos_api.py                                                               (a1)
  importers/sb_summary.py, importers/smc_csv.py, importers/manual.py                 (b)
scraper/scripts/
  register_results_capture.py, import_results.py, append_results.py,
  check_results_ledger.py                                                           (a1)
scraper/tests/fixtures/results/…  (with a -text rule)
```

(a1) lands `contract.py` and the error codes first, as its own small commit. (b) starts
from that commit.

### 7.2 The importer interface

An importer is a pure function. It reads no database, no mapping and no ledger:

```text
parse(data: bytes, artifact: ArtifactInfo) -> SourceReport

SourceReport:  source, election_text, report: {seq, as_of_text, as_of_local, status_text},
               contests: [SourceContest]
SourceContest: key_raw, choices {label: votes}, total_votes_printed,
               percent_yes_printed_text, ballots_cast, registered,
               precincts_reported, precincts_total, locator (sheet/row or line)
```

- `as_of_local` is the parsed time with no zone. The zone comes from `sources.json` once
  reviewed; until then it stays unknown and only `as_of_text` is displayed.
- A parser that sums precinct rows (San Mateo) must also reconcile each contest with the
  same report's summary PDF figures, supplied as reviewed expected totals.

### 7.3 Candidate batch

`candidates.py` joins a `SourceReport` to the mapping and writes one file per artifact, in
the capture's folder (private): `candidates.<source>.json`, a list of normalized
observations without `seq` or `prev`, plus the capture id, artifact hash, mapping hash and
importer revision. Either every mapped contest is present and valid, or no file is written.

### 7.4 Manual form

For a result that exists only in a document: `manual.<county>.json` in the capture folder,
one entry per contest, with the document's file and hash, page, the counts as printed, the
transcriber and a second checker. It passes through the same mapping, scope, rule and
certification gates and produces a candidate batch like any importer.

### 7.5 Failure matrix

Every failure stops the step and writes nothing. Each has a stable code, which tests assert:

| Code | Raised when |
|---|---|
| `CAPTURE_EXISTS` | The folder already has `capture.json` |
| `CAPTURE_HASH_MISMATCH` | A file's hash differs from `SHA256SUMS.txt`, or a file is unlisted |
| `ELECTION_MISMATCH` | The file's own election identity is absent or wrong |
| `REPORT_ORDER_MISSING` | The report has neither a sequence nor an as-of time |
| `STATUS_TEXT_UNKNOWN` | The source's status wording is not in `sources.json` |
| `CONTEST_UNMAPPED` | A measure-like contest has no mapping entry |
| `CONTEST_MISSING` | A mapped contest is absent from the file |
| `CONTEST_DUPLICATE` | A contest key, or a measure and scope, appears twice |
| `CONTEST_KIND_UNKNOWN` | A YES/NO contest matches neither the measure pattern nor a reviewed non-measure pattern |
| `IDENTITY_DRIFT` | The measure row's election, canonical key, county, jurisdiction or designation differs from the entry |
| `EVIDENCE_MISSING` | An entry lacks identity, scope or rule evidence |
| `COUNT_INVALID` | A count is not a whole number of zero or more, or is a boolean, blank or formula-like |
| `TOTAL_MISMATCH` | Yes plus no differs from the printed total, or from the summary PDF |
| `PERCENT_MISMATCH` | The printed percent disagrees with the counts beyond the source's precision |
| `SUPERSEDE_INVALID` | A correction without a reason, across contests or scopes, or forming a cycle |
| `CHAIN_BROKEN`, `ANCHOR_MISMATCH`, `NOT_APPEND_ONLY` | The ledger fails §2.3 |
| `SELECTION_INVALID` | A selection fails §2.4 |
| `CERTIFICATION_INVALID` | A certification fails §3.3 |
| `DERIVATION_INVALID` | A derived total fails §4.5 |

Exit codes: 0 done; 1 a contract failure, with the code and the contest named; 2 a usage
or file error.

## 8. Verification

- **Fixtures first** (§6), then an exact-contract test per importer and the failure matrix
  above.
- **Ledger and selection:** the same bytes with a corrected parser, a corrected mapping,
  and added certification; an old report captured later; equal-order conflicts; a
  retraction; a selection naming a missing or superseded observation; a truncated last
  line; a failed batch; two appends at once.
- **Mapping:** an older election reusing a letter or number; a wrong but existing target
  id; a judicial YES/NO contest.
- **Groups:** an omitted portion, a repeated portion, a consolidated total posing as a
  portion, a corrected membership, a corrected input invalidating a derived total.
- **CSV:** precinct, method and subtotal double counting; repeated headers; a missing
  choice; zero against blank; reconciliation with the same report's PDF.
- **Outcome arithmetic,** Python against JavaScript: zero, one vote, a tie, exactly 55%,
  exactly two-thirds and the neighbours of each.
- **Every state** in §5.1 plus the future calendar states, at 1440, 390 and 320 px, with a
  long as-of label and an open modal held across midnight.
- **The rehearsal list** of the transition design, on database copies, including the
  certification transaction and its rollback, in (c-core), not for the first time on
  December 4.
- **Migration:** safe to run twice, on today's schema and on the future CEDA schema.
- **Preservation gate, unofficial release,** against a **frozen baseline build**: only
  `index.html`, up to 63 measure pages, and the `election_status` and `result` fields on up
  to 63 rows may change. Top-level votes and outcomes, and every history cohort's
  membership and figures, are identical. The known `last_seen_at` regeneration is frozen
  or excepted by exact id.
- **Preservation gate, certified release:** a separate allowlist: the projected row,
  combined and provenance fields on named ids, and the expected changes to aggregates.

## 9. Chunks

| Chunk | Scope | Size | Depends on | Acceptance | Builder |
|---|---|---|---|---|---|
| **(a0)** | This contract | Done | | Codex re-review closes R1-R8 | Fable |
| **(a1) Ledger and SOS** | `contract.py` first; capture registration; ledger, anchors, append; mapping and rule validators; SOS parser; the 14 statewide entries with rule `unreviewed` | 2 days | (a0) accepted | Both saved SOS files register and import to 28 observations; a re-run appends nothing; a re-parse with a bumped revision supersedes; the failure matrix passes | **Fable**; reviewed by Codex or a Claude agent |
| **(b) Counties** | San Bernardino and San Mateo parsers; the 49 entries with identity, scope and rule evidence; the three groups; the manual form; the synthetic CSV fixture | 2-3 days | `contract.py`; Igor's first xlsx, CSV and summary PDF | 49 measures observed from real private files; CSV totals equal the summary PDF's; every `scope` has evidence | **A Claude agent**, in parallel with (a1) |
| **(c-core) Projection** | The outcome module in three forms; every consumer in §4.3; field transport; `result` rendering on cards, modal and static pages; the selection tools; the certification transaction and its rehearsals on copies | 3-4 days | (a1), (b). **Runs before Explore E2c**; the two must not edit `generator.py` at once | §8's state, arithmetic and rehearsal tests; all consumers flip in one commit | **Codex** for `generator.py` and the pages; **Fable** for the outcome module, selection and transaction. Each reviews the other |
| **(c-release) Unofficial release** | Optional. A reviewed selection of unofficial observations, the unofficial gate, the release | 0.5 day | (c-core) reviewed; Igor's go; ready by **November 26** | The unofficial preservation gate | The coordinator |
| **(d) Certification** | Certified captures and certifications; scope and membership evidence; derived totals; projection on a copy, then production; the link recheck (P0.3a) | 1.5 days, from December 4 | (c-core); certified material | Layers 1-3; all 63 outcomes traced to certified files; incomplete groups stay "not available" | **Fable** prepares; the coordinator promotes |

If (c-core) is late, the **unofficial release** is skipped. The shared projection code and
the certification rehearsals are built either way.

## 10. Decisions

**Answered by Igor on November 13** (recorded in `docs/WORKING_LIST.md`):

| # | Question | Answer | Where it lands |
|---|---|---|---|
| 1 | File or database | A committed file | §2 |
| 2 | Majority for the 14 propositions | Yes, after a source and rule review; no guessed default | §3.2 |
| 3 | November 26 cut-off | For the optional unofficial release only | §9 |
| 4 | Multi-county before certification | Show the county portion, clearly scoped; keep "combined not available" apart from "county counts not available" | §5.1 |
| 5 | Other counties' certified results | Igor saves them, with certification statements, after the membership and scope review | §1.2, §4.5 |
| 6 | Wording | "Unofficial" and "Certified" as words on cards and in the detail | §5.1 |
| 7 | Precinct results | Not public in this version; private ingestion allowed | §6 |
| 8 | San Mateo CSV as a fixture | **No**, whatever its size | §6 |

**Still open:**

1. **The SOS file's time zone.** `ReportingTime` names none. *Recommend recording
   Pacific time in `sources.json` after a reviewer confirms it;* until then the site shows
   the source's own wording.
2. **The authority packet for the propositions.** Someone must save the constitutional
   sections and each proposition's enabling text. *Recommend Igor saves them with the next
   capture;* the rule review follows in (b).
3. **Who reviews identity and scope evidence for the 49 local entries?** *Recommend the (b)
   builder assembles it and a second agent checks it,* with Igor deciding any doubtful
   scope.
4. **The label for certified counts with no result,** and final wording and placement of
   every result line. These are Igor's; (c-core) brings options.
5. **San Bernardino's summary file as a public fixture.** *Recommend yes, after a check
   that it holds contest totals only.*
6. **An official unofficial consolidated total, if one is found for a multi-county
   measure.** *Recommend showing it as unofficial, scoped and sourced.*

## 11. Not verified

- The layout of San Bernardino's xlsx and San Mateo's CSV, and San Mateo's status wording
  and report order.
- Whether the three multi-county measures are the only ones, and each district's
  membership.
- The legal text behind any approval rule.
- How each source will mark certification, and the 2026 Statement of Vote file names.
- The line numbers cited from the review in §4.3 and §5.4; I checked only
  `election_status.py`, `build_measure_pages.py:113-122` and `generate_site.py:128`,
  `:235` and `:264-267`.
- Nothing was fetched for this design.
