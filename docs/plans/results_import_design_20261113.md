# P2 design: results for the 63 current measures

**Date:** November 13, 2026. **By:** Fable. **Status:** design for review; nothing is built.
**Goal:** results for the 14 statewide, 20 San Bernardino and 29 San Mateo measures appear on
the site before counties certify on December 3, first as unofficial, then certified, on a
path the county expansion can reuse.
**Builds on:** [results transition](results_transition_20260907.md), the
[layout review](../codex/layout_direction_a_review_response.md) (answer 2), the
[CEDA design](ceda_backfill_design_20261112.md) and its
[revision review](../codex/p1b_1b_revision_review_response.md) (N1).
**Method:** no network. I read the code and docs, and four result files an earlier session
saved on November 5-7 (§1). I queried the production database read-only; its SHA-256 was
`ef1359e482db2c54fe41068771932aaac7c9fc1db372e2e1d8cbbed1f505d9da` before and after.

## 0. The design in six lines

1. Igor saves seven files a week by hand. Each is hashed and registered; nothing is fetched
   by script until the capture tool exists.
2. Importers turn each file into **observations** in an append-only ledger. An observation
   is never edited or deleted.
3. A **reviewed mapping** ties each source contest to our measure `id`. Anything unknown,
   duplicated or missing stops the import.
4. **Unofficial observations never touch the `measures` table.** The site build reads them
   from the ledger. So history statistics, Explore and the status rule cannot pick them up.
5. **Only a certified observation writes `passed`**, in one reviewed transaction.
6. A multi-county measure's outcome comes only from a whole-contest observation. A county's
   portion is shown and labelled as a portion, with no Passed or Failed.

## 1. Sources

What I know comes from the code, the docs and the saved files. Anything marked
**unverified** needs a fixture before an importer is written.

| | Secretary of State | San Bernardino | San Mateo |
|---|---|---|---|
| Reader link (`official_results_links.json`) | `electionresults.sos.ca.gov/returns/ballot-measures` | `results.rov.sbcounty.gov/Results/20261103/` | `smcacre.gov/elections/november-3-2026-election-results` |
| Data file | JSON at `api.sos.ca.gov/returns/ballot-measures` | "Excel Version (XLSX)" on that page: `ElectionSummaryReportRPT.xlsx` | "Results on CSV": `/media/<id>/download?attachment` |
| Format, as seen | `ReportingTime`, `Reporting`, and 14 entries with `Number`, `Name`, `yesVotes`, `noVotes`, `yesPercent`, `noPercent` (all strings) | The page lists each contest: title, "Precincts Reported", "Times Cast a / b", YES and NO votes with percents, "Total Votes". **The xlsx layout is unverified** | Per the November 5 assessment: 34,045 rows, precinct by vote method, with registered, voters, votes, undervotes and overvotes. **Column names are unverified** |
| What identifies a contest | `Number` ("01"-"05", "37"-"45") | The title, e.g. "City of Needles MEASURE D (Vote for 1)" | The contest name in the CSV (unverified) |
| As-of text | `ReportingTime`, e.g. "November 6, 2026, 11:00 p.m." | "Summary Report #5"; "Next Update: …" | The page; the media id changes per report (9149, then 9153) |
| Status wording | None in the JSON | Page heading, e.g. "Final Unofficial Election Night Results" | Unverified |
| Certified source | Statement of Vote, after December 11 (2024 used `csv-ballot-measures.xlsx`; unverified for 2026) | A final official report and a Statement of Votes (June's came 24 days after the election) | "Statement of the Vote PDF" (a placeholder today) |

**Facts that shape the design:**
- **The SOS page that readers get is bot-challenged; the JSON endpoint answered scripts on
  November 5-7.** Whether it still does is unverified.
- **San Bernardino's page lists exactly our 20 measures** (A-R, Y, Z), plus the 14
  propositions as "San Bernardino County PROPOSITION n", which are county portions.
- **Titles do not match our jurisdictions.** Measure I is "San Bernardino County MEASURE I"
  there and "San Bernardino County Transportation Authority" in our record. The mapping must
  be reviewed, not matched on strings.
- **"100% of precincts" does not mean counting is finished.** No status may be inferred from
  it, or from the date.
- **San Mateo's CSV has a 2-voter precinct split, unmasked.** The raw file stays private.

**Files already in hand** (saved by script on November 5-7, in the planning session's
scratch folder `…\d90ea535-…\scratchpad\`): two SOS JSON files (`sos_returns.json`, SHA-256
`3d4b05aff814…`; `dl_results_links\7aef5a2d.bin`, `647fb5d31206…`), the San Bernardino page
(`sb_results.html`, `355379126d6a…`) and the San Mateo page (`…\7b7d6674.bin`). The
coordinator should copy them into the folder below as the first two captures before that
scratch folder is cleared.

### What Igor saves, and where

**Folder:** `scraper/data/raw/results/2026-11-03/<YYYY-MM-DD>/` (already gitignored by
`scraper/.gitignore`). One folder per save day.

| # | Save as | Open | Do |
|---|---|---|---|
| 1 | `sos_ballot_measures.json` | `https://api.sos.ca.gov/returns/ballot-measures` | Save the page as a file |
| 2 | `sos_returns_page.pdf` | `https://electionresults.sos.ca.gov/returns/ballot-measures` | Print to PDF. It also serves as the fresh human check of the SOS link (P0.3a) |
| 3 | `sb_summary.xlsx` | `https://results.rov.sbcounty.gov/Results/20261103/` | Downloads, "Excel Version (XLSX)" |
| 4 | `sb_summary.pdf` | same page | Downloads, "Print Friendly Version (PDF)" |
| 5 | `sb_results_page.html` | same page | Save as "Webpage, HTML only". It holds the report number and status heading |
| 6 | `smc_results.csv` | `https://smcacre.gov/elections/november-3-2026-election-results` | "Results on CSV" |
| 7 | `smc_results_page.html` | same page | Save as "Webpage, HTML only" |

Then, in that folder, in PowerShell:

```text
Get-ChildItem -File | Get-FileHash -Algorithm SHA256 | ForEach-Object { "$($_.Hash.ToLower())  $(Split-Path $_.Path -Leaf)" } | Set-Content -Encoding ascii SHA256SUMS.txt
```

and a `NOTES.txt` with the time saved (Pacific) and anything odd. Chunk (a) replaces this
with a small registration script that checks the folder and writes `manifest.json`.

**When:** today, then each Friday (November 20 and 27), then **December 4** (after county
certification) and **December 12** (after the state's).

**At certification only,** also save:
- San Mateo's "Statement of the Vote PDF" and San Bernardino's final official report and
  Statement of Votes index page;
- the state's Statement of Vote spreadsheet;
- for the three multi-county measures (§3), the certified result from each other county:
  Riverside (two measures), and Alameda, Contra Costa, San Francisco and Santa Clara (one).

## 2. Data model

### The ledger

**One append-only file per election, committed to the repo:**
`scraper/src/website/data/results/2026-11-03.observations.jsonl`, one observation per line.
It sits beside `official_results_links.json` and `county_2026.json`, and is reviewed the
same way: a diff in a pull request.

Each observation records:

| Field | Meaning |
|---|---|
| `seq`, `prev_sha256` | Position, and the hash of the previous line. Any edit or deletion breaks the chain, and a test checks it |
| `observation_id` | SHA-256 of the capture hash, contest key and scope. Importing the same file twice adds nothing |
| `measure_id`, `canonical_measure_id` | Our integer `id`, and the row's `measure_id` string as a cross-check |
| `source`, `contest_key` | For example `sb_summary`, and the source's own contest title, verbatim |
| `capture` | File name, SHA-256, bytes, URL, saved at, saved by, and how it was obtained (`manual_browser`, `script`, `capture_tool`) |
| `scope`, `scope_county`, `group` | `contest` (the whole measure) or `county_portion`; the county; the multi-county group key |
| `status`, `status_evidence` | `unofficial` or `certified`. Certified needs named evidence (§5) |
| `yes_votes`, `no_votes`, `total_votes` | Integers. `total_votes` is the source's yes plus no |
| `ballots_cast`, `registered`, `precincts_reported`, `precincts_total` | Where the source prints them; else null, never zero |
| `source_percent_yes` | The source's printed percent, as text, for cross-checking only |
| `as_of_text`, `as_of_at` | The source's own wording, and a parsed Pacific time when it parses |
| `importer`, `importer_version`, `mapping_sha256` | What produced the line |
| `supersedes` | Set only on an explicit correction |

**Why a file and not database tables.** The store is small (63 measures, about six captures:
under 400 lines), it must be reviewable line by line, and it lets the whole unofficial phase
run **without one write to the production database**. A database table would also work; I
recommend the file (§7, question 1).

### Which observation is shown

For each measure and scope, the current observation is the one from the latest capture, with
certified ranking above unofficial. Importing an older file later adds history but never
becomes current. Counts may go down: a correction is a new line with `supersedes`, never an
edit. Each release's evidence lists the current observation for all 63 measures, and Igor
signs that list. That list is the "reviewed pointer" of the transition design.

### How this relates to `measures`

| Phase | `measures` columns | Where the site gets results |
|---|---|---|
| Unofficial | **Unchanged.** `passed`, `yes_votes` and the rest stay NULL | The ledger, at build time |
| Certified | `passed`, `yes_votes`, `no_votes`, `total_votes`, `percent_yes`, `percent_no` written from the selected certified observation, with a new `result_observation_id` naming it | Those columns, plus the ledger for the source and date |

Keeping unofficial counts out of `measures` matters for a second reason: the status rule
reads any stored vote without an outcome as "Result unknown"
(`election_status.py:83-108`).

No `id` changes. No row is added to `measures`. The weekly registrar load already refuses
outcome fields (`loader.py`, `_OUTCOME_FIELDS`), so it cannot erase a projected result; a
test pins that.

## 3. Mapping

**File:** `scraper/src/website/data/results/2026-11-03.mapping.json`, reviewed and
committed. One entry per source contest:

```text
{ "source": "sb_summary", "contest_key": "City of Needles MEASURE D",
  "measure_id": 12424, "identity": { "county": "SAN BERNARDINO", "letter": "D",
  "jurisdiction": "City of Needles" }, "scope": "contest",
  "rule": { "id": "majority", "source": "measures.vote_threshold = 50%" } }
```

**It fails closed.** An import stops, writing nothing, when:
- a contest in the file that looks like a measure is not in the mapping (it must be mapped,
  or listed as ignored with a reason);
- a mapped contest is missing from the file, or appears twice;
- the measure `id` is not a current measure, or its county, designation or jurisdiction no
  longer match the entry's `identity`. This is the check that would have saved the Santa
  Cruz measure in the CEDA history;
- any count is not a whole number, yes plus no differs from the printed total, or the
  printed percent differs from the counts by more than 0.05 points.

**The 63.**
- **Statewide (14):** `Number` maps through `statewide_ballot_entries.proposition_number`,
  not through the `measure_id` text. Propositions 3, 4 and 5 are ids 10960, 10956 and 2.
  The withdrawn ACA 13 (id 1) is mapped as "no contest expected".
- **San Bernardino (20) and San Mateo (29):** by reviewed contest title.

### Multi-county measures: one model with the CEDA history

Three current measures cross a county line, per the plan (to be confirmed when the mapping
is reviewed):

| id | Measure | We hold | Other counties |
|---|---|---|---|
| 12418 | San Bernardino Community College District Y | San Bernardino's portion | Riverside |
| 12421 | Beaumont Unified School District B | San Bernardino's portion | Riverside |
| 12442 | Public transit revenue measure | San Mateo's portion | Alameda, Contra Costa, San Francisco, Santa Clara |

The model is the one the CEDA revision review asked for (N1), so current and historical
rows read the same way:

- **`multi_measure_id`** on the row: the group key, for example `REG:2026-11-03:SBCCD-Y`.
  CEDA rows will use `CEDA:<year>:<Multi_MeasID>`.
- **`passed`** stays the row's own result: here, the county portion against the rule.
- **`combined_passed`**, with `combined_yes_votes` and `combined_no_votes`: the measure's
  result. It is set only from a `contest`-scope observation.
- Badges and statistics use `combined_passed` when `multi_measure_id` is set, and never fall
  back to `passed` for such a row.

P2 adds these columns (plain `ALTER TABLE ADD COLUMN`; no rebuild) because it needs them
first. The CEDA repair then fills the same columns for history.

**Where a whole-contest observation comes from:**
1. an official consolidated result, if one exists (unverified for all three); or
2. a **derived** observation: the sum of certified county portions, allowed only when every
   member county listed in the mapping has a certified observation. It records its inputs.
   Percentages are never averaged.

Before certification there is no combined figure: unofficial portions from different days
are not added together. The other counties' certified figures enter through a **manual
observation file**: a reviewed transcription with the document's URL, hash and page. That
avoids five more importers for three measures.

## 4. Projection to the site

### States

The six states of the layout review, with one rule added: **the state comes only from a
whole-contest observation.**

| State | When | Card | Modal and static page |
|---|---|---|---|
| Results pending | No observation | As today | As today, with the official link |
| Unofficial | Current observation is unofficial, scope `contest` | "Unofficial · as of [source time]" · "52.3% yes · Needs 55%" | Counts, total, rule, margin, source, as-of time. **No Passed or Failed, no outcome color** |
| Certified passed / failed | `passed` is 1 or 0 from a certified observation | "Passed · Certified" or "Failed · Certified" | Counts, margin, certification source and date |
| Withdrawn | As today | As today | As today |
| Result unknown | Historical rows only | As today | As today |

**A multi-county row** with only a portion stays **Results pending** ("Combined result not
available yet") and shows the portion beneath, labelled "San Bernardino County portion,
unofficial as of …". After certification, the combined result leads and the portion follows.

### Rules

- **Thresholds come only from reviewed sources.** The 49 local rows carry the registrar's
  `vote_threshold` (50%, 55% or 66.67%). The 14 statewide rows carry none, so they read
  "Approval requirement not listed" unless §7, question 2 is answered.
- **Rounding never decides an outcome.** Outcomes and margins are computed from whole counts:
  majority is yes > no; 55% is 100·yes ≥ 55·(yes + no); two-thirds is 3·yes ≥ 2·(yes + no).
  The denominator is yes plus no.
- **The displayed percent must sit on the true side of the threshold.** Use one decimal; if
  that would show "55.0%" for a result below 55%, add decimals until it does not.
- **If a certified source prints its own outcome,** it must agree with the computed one, or
  the measure is held for review.
- **Precinct data is not published in this version.** Only contest totals leave the raw
  file, so the masking rule (10 voters or fewer) has nothing to act on yet. It applies in
  full when precinct results are added.
- Wording comes from fixed templates.

### What changes in the P0.1 status contract

- `election_status()` gains **`unofficial`**, ranked after a recorded outcome and before
  the date-driven statuses. It is not date-driven: the reader's clock never changes it.
- Each current row gains a **`result`** object in `measures-data.json`: state, scope, counts,
  display percent, rule and its source, margin text, as-of text, status label, source link,
  and `portion` / `combined` blocks for multi-county rows.
- `official_results` stays as it is.
- Consumers are the ones P0.1 inventoried, plus local cards, which show no status today.
  **All of them change in one commit.**
- New rendering goes in a small module (`results_display.py`) that exports both the Python
  for static pages and the JavaScript for the explorer, tested against each other in Node,
  like `election_status.py`.

Unofficial results stay out of everything that reads `passed`: county history cohorts,
Explore and Insights.

## 5. Verification

- **Fixtures first.** Igor's first saved files are pinned as fixtures, with a `-text` rule
  in `.gitattributes` for the new fixture folder from day one. The two saved SOS files and
  the saved San Bernardino page are available now.
- **Importer tests,** per source: an exact-contract test on the fixture, and a failure
  matrix (missing field, extra contest, duplicate, non-numeric count, totals that do not
  add up, unknown status wording, a mapping entry whose identity has drifted).
- **Ledger tests:** the hash chain; re-import adds nothing; an older capture never becomes
  current; a correction supersedes without editing.
- **Cross-check:** San Bernardino's xlsx against the same report's saved page.
- **The rehearsal list** from the transition design, on database copies: awaiting results;
  unofficial counts without a call; certification; revised counts; zero and null values;
  unknown thresholds; stale-observation rejection; ambiguous matches; regional scope;
  repeated imports; transaction rollback; and an ordinary registrar refresh afterwards.
- **Preservation gate, unofficial release:** only `index.html`, up to 63 measure pages, and
  the `election_status` and `result` fields on up to 63 rows may change. Every other page
  and field is byte-identical. The production database is untouched.
- **Browser checks:** extend `check_election_status_browser.py` (its R7 fix already accepts
  non-calendar rows) to every state at 1440, 390 and 320 px, including a long as-of label,
  a multi-county row and a near-threshold percent.
- **Certification sweep:** a status is `certified` only with named evidence in the capture's
  manifest (the certification statement or Statement of Vote, with its hash). Then project
  on a copy; run Layer 1 (no other row changes), Layer 2 (the 63 against the certified
  files) and Layer 3 (traces, including the three multi-county measures); Igor reviews the
  list of 63 outcomes; the coordinator promotes.

## 6. Chunks

| Chunk | Scope | Size | Depends on | Acceptance | Builder |
|---|---|---|---|---|---|
| **(a) Ledger and SOS** | Capture registration script, the ledger and its tests, the mapping format and validator, the SOS importer, the 14 statewide mappings | 1.5 days | The two saved SOS files (in hand); question 1 | Importing both saved files yields 28 observations; a re-run adds none; the failure matrix passes; no database is opened for writing | **Fable**, reviewed by Codex or a Claude agent |
| **(b) County importers** | San Bernardino xlsx and San Mateo CSV importers, 49 mappings, the three multi-county marks, the manual observation file | 2 days | Igor's first saved xlsx and CSV; chunk (a)'s interfaces | 49 measures observed from real files; contest totals equal the summed precinct rows; unknown contests stop the run | **A Claude agent or Codex**, in parallel with (a) once the formats are pinned |
| **(c) Site projection** | The status contract change, `results_display.py`, the generator and static-page hooks, the browser check, the unofficial release candidate | 2-3 days | (a) and (b); `generator.py` free of Explore edits | §5's preservation gate and browser checks; all surfaces flip in one commit | **Codex**, which already works in `generator.py`; I review |
| **(d) Certification** | Certified captures, the projection into `measures` on a copy, combined results for the three multi-county measures, the link recheck (P0.3a), the release | 1.5 days, December 4-12 | (c); certified files; Igor's review of 63 outcomes | The rehearsal list; Layers 1-3; every outcome traced to a certified file | **Fable** builds the projection; the coordinator releases |

**Timing.** With (a) and (b) done by about November 18 and (c) by about November 24, readers
get nine or ten days of unofficial results before December 3.

## 7. Risks and questions for Igor

1. **File or database for the ledger?** *Recommend the committed file* (§2). It keeps the
   production database untouched until certification and makes every observation
   reviewable.
2. **The approval rule for the 14 propositions.** We store none. *Recommend adding
   "majority" as a reviewed rule,* citing the state constitution for initiatives,
   amendments and bonds, after Codex checks the citations. Otherwise they read "Approval
   requirement not listed" beside their percentages.
3. **A cut-off for the unofficial display.** If chunk (c) is not ready by **November 26**,
   *recommend skipping the unofficial state* and shipping certified results only. Chunks (a),
   (b) and (d) are needed either way.
4. **Multi-county measures before certification.** *Recommend showing the county's portion,
   labelled, with "Combined result not available yet".* The alternative is to show nothing
   for those three.
5. **Multi-county measures after certification.** Will you save the other counties'
   certified results (Riverside; and Alameda, Contra Costa, San Francisco, Santa Clara)?
   *Recommend yes.* Without them those three stay "Combined result unavailable".
6. **Wording and placement** are yours: "Unofficial · as of …", where the result line sits
   on a local card, and whether "Certified" appears as a word or only in the detail.
7. **Precinct results.** *Recommend not in this version.*
8. **Committing fixtures.** San Mateo's CSV is several megabytes. *Recommend committing it
   whole* if it is under about 5 MB, otherwise a trimmed copy with the full file's hash.

**Risks**
- **Formats are unverified** for the two county files. Mitigation: no importer before its
  fixture.
- **The county pages may change shape or wording** between saves. Mitigation: unknown
  wording stops the import.
- **Counts move.** More than 20 school bonds were too close to call on November 4.
  Mitigation: no outcome label before certification, and the true-side display rule.
- **`generator.py` is shared** with the Explore work. Mitigation: chunk (c) runs after
  Explore E2c, or the two are sequenced by the coordinator.
- **The saved samples sit in a session scratch folder.** Copy them now.

## 8. Not verified

- The layout of San Bernardino's xlsx and San Mateo's CSV, and San Mateo's status wording.
- Whether the state's JSON endpoint still answers, and what time zone `ReportingTime` uses.
- How each source will mark certification, and the 2026 Statement of Vote file names.
- Whether any consolidated result exists for the three multi-county measures, and whether
  those three are the only ones.
- Nothing was fetched for this design.
