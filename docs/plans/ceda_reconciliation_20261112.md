# CEDA reconciliation report (P1b.1b)

**Date:** November 12, 2026. **By:** Fable. **Revised** the same day after the
[independent review](../codex/p1b_1b_reconciliation_review_response.md), which reproduced
every count and corrected several statements; §7 lists what changed.
**Scope:** read-only. Every stored CEDA row in a year we hold a raw file for (21 files,
8,477 rows) compared field by field with its raw row. Nothing was written to any database.
**Production DB SHA-256, before and after:** `ef1359e482db2c54fe41068771932aaac7c9fc1db372e2e1d8cbbed1f505d9da`.
**Companion:** [P1b.2 design](ceda_backfill_design_20261112.md). Builds on the
[column check](ceda_column_check_20261111.md) and its [review](../codex/p1b_1_ceda_review_response.md).

## 1. Bottom line

1. **The wrong-row defect is from the first CEDA load, not April 12, 2026.** The load ran on
   July 30, 2025 at 5:28 p.m. Pacific (July 31 UTC). A backup taken that evening holds all
   28 wrong rows with the same votes and question they have today.
2. **The first loader keyed rows on year, county and the letters at the start of the
   designation.** A later measure with the same key overwrote the earlier one: 1,077 rows
   were overwritten at load. The `measure_updates` table logged each overwrite.
3. **April 12 repaired most of it.** A refresh from `ceda_parsed.csv` corrected 1,049 of the
   1,077 and restored 1,330 dropped measures.
4. **One rule then dropped 188 rows without a word.** A migration had just changed some
   county spellings, so those CSV rows no longer matched. Their insert then failed on the
   table's `UNIQUE(year, measure_id, data_source)` rule, and the ingest only counted the
   error. That explains three defects at once: the 157 stale rows, the 29 missing 2014
   county shares, and two missing 2002 measures.
5. **Of the 157 stale rows,** 28 hold another measure's content, 55 lack an outcome or a
   date, and 74 differ only in form.
6. **A fourth defect appeared on April 28, 2026, after the repair.** Id 4870 was Santa Cruz
   County's 2016 Measure D. The 2015 file carries a different measure, Measure P, under the
   same ID, and its ingest overwrote D. **Measure D is no longer in the database.**
7. **Otherwise the held years are sound.** 6,169 rows have no field that conflicts with
   raw, and 1,702 differ only in form.
8. **Live cards are affected.** San Bernardino's GO bond pass rate, shown on 7 cards as 69%
   (60 of 87), is 65% (60 of 92) on each county's own result, and **68% (63 of 92) on the
   measures' combined results, which is the figure the site should use** (§5). 23 wrong rows
   also display an AI summary of a different measure.
9. **It can happen again, in three ways** (§4). The unseen 2016-2021 files are the likely
   trigger.

## 2. Reproduction of the earlier figures (acceptance check 1)

All from `scraper/scripts/reconcile_ceda_raw.py`. The review reproduced each one with an
independent loader.

| Figure | Result |
|---|---|
| Row counts, file against DB, 1998-2015 and 2022-2024 | Equal in every year except 2014 (577 file, 548 DB) and 2015 (120 file, 119 DB; the extra row is the 2016 measure stored as id 4870) |
| Rows holding another measure's votes | **28**: 5 in 2000 (San Bernardino), 23 in 2011 (Los Angeles 16, Santa Clara 4, Fresno 2, Marin 1) |
| 2014 keyed on `Multi_MeasID` | 27 rows under their own ID, **521** under another row's, **29** file rows absent (all `Multi_CO=1`) |
| 2002 foreign row | id 9189, `200200001`: Mendocino H content; the raw row is Strathmore A-02 |
| `PASSFAIL` against `passfail_sum` flips | **112** in the 16 newly downloaded years; 145 across all 21 files |
| `passed` NULL | 2000: 6, 2005: 1, 2011: 48, 2018: 1 |
| Multi-county group checks | No violation in any of the 21 files |
| Same ID on two loaded raw rows | None among the 21 files |

## 3. Field-by-field result (acceptance check 2)

| Class | Rows | Meaning |
|---|---|---|
| match | 6,169 | No compared field conflicts with raw. **Every one of these rows also has an empty `ballot_question`**; see below |
| format only | 1,702 | Differences vanish after normalizing case, spacing or county spelling, or the title is a placeholder |
| wrong key | 521 | 2014: content is right, stored under the group key |
| incomplete | 55 | No conflict, but the outcome or the date was never derived. 46 have a `pass_fail` code and a NULL `passed`, so they drop out of the site's statistics |
| wrong row | 28 | Content is another raw row's |
| ID reused | 1 | id 4870: overwritten through an ID that two CEDA releases give to different measures |
| foreign | 1 | Content is in no raw row (id 9189) |
| missing from DB | 29 | The 2014 multi-county members |

Fields with real differences, out of 8,477 compared rows: votes and percent 29 each (the 28
wrong rows and 9189); `ballot_question` 28; `pass_fail` 16; `passed` 6. `election_date`,
`county` and designation differ only on 9189. `jurisdiction` differs only on 4870.
`category_type` never differs.

**Empty fields.** `ballot_question` is empty on 6,722 compared rows, `category_topic` on
6,742 and `jurisdiction` on 1,754. The question text was not "never loaded": all 9,548 rows
had it in July 2025. The April 12 refresh blanked it (8,021 rows at the time; 8,020 are
still empty) and a later run that day wrote the text into `title` instead. Today `title`
equals the July question on 6,992 of those rows.

**Placeholder titles.** 1,597 "format only" rows differ from raw only because their `title`
is `"<COUNTY> Measure <LTR>"` (2015, 2022-2024 and 29 rows of 2011). Their cards show the
placeholder where the question should be. This is a display defect, listed for P1b.2.

**A wrong row is a hybrid, not a whole-row swap.** It keeps its own `measure_id`, county,
designation and `category_type`. Its question, votes, percent, `pass_fail`, AI summary and
`topic_primary` belong to the sibling. Example: id 6138 is Azusa's Measure A (`201100001`,
an ordinance) but shows Vernon's charter question, 43 to 9, and a summary about Vernon.
Vernon's own row (id 11458, `201100094`) is also stored correctly, so each of the 28 source
measures appears twice and 28 measures do not appear at all.

Stored outcome on the 28: agrees with the row's own raw outcome on 17 (by coincidence),
**contradicts it on 6**, and is NULL on 5.

## 4. Cause, and whether it can recur (acceptance check 3)

Times are Pacific.

| When | What happened | Evidence |
|---|---|---|
| July 30, 2025, 5:28 p.m. | First CEDA load from the Excel files. The key came from the title, `"<COUNTY> Measure <LTR>"`, through the pattern `Measure\s*([A-Z]+)`. That keeps only the leading letters, so `R1` and `R3` both keyed as `R`. Measures sharing a key collided and the last one won. | July backup: 9,548 rows, all keyed `year\|MEASURE_x\|county\|CEDA`; 249 keys differ from the row's designation; 2011 has 143 rows for 172 in the file. `measure_updates`: 7,929 field changes on exactly 1,077 rows, all within those nine seconds; row 6138 goes Azusa, two others, then Vernon. The code first appears in git at `f1a6c372` (August 8, 2025). |
| January 9, 2026 | Identifier changed to prefer `measure_id` (`3bc82b16`). `ceda_parsed.csv` was written the same day with ID keys and all 10,909 rows. The database was not rebuilt. | CSV `created_at` values |
| April 12, 2026, 10:50 a.m. | `migrate_canonicalize.py` (`f075843b`) rewrote county names and all keys, stamping `updated_at`. **This is the 17:50:43 UTC stamp.** It changed no votes or questions. | `migrate_canonicalize.py:289-294`; 1,473 rows of five sources carry the stamp |
| April 12, 10:53 a.m. | `ingest_measures` was called on `ceda_parsed.csv` (not through `run_pipeline`; `scraper_runs` has no entry). It refreshed 9,391 rows, inserted 1,330 (ids 10969-12298) and **blanked `ballot_question`** on the refreshed rows, because that parser read a column the CSV lacks. | `created_at` and `updated_at` values; the review's simulation predicts exactly 9,391, 1,330 and 188 |
| Same run | **188 rows were dropped.** Their CSV county spelling (`Los Angeles`, `SAN BERNADINO`, `TOULUMNE`) no longer matched the stored, canonical one, so no existing row was found. The insert then broke `UNIQUE(year, measure_id, data_source)`, and `ingest_measures` caught the error and only added one to a counter. | `pipeline.py:344-350` at `f075843b`; the same structure is at `pipeline.py:350-355` today |
| April 12, 2:37 p.m. | A second run (`cf445606`) wrote the question text into `title` and filled `category_type`. Same 188 rows dropped. | Row timestamps |
| April 28, 2:30 p.m. | The 2015 file was ingested. Its one 2016 row, `201600120`, is Santa Cruz City Elementary's Measure P. The stored `201600120` was Santa Cruz County's Measure D. The keys matched exactly, so **P overwrote D** in id 4870. | July backup and the 2:23 p.m. backup hold D (83,816 to 39,839); the 2:33 p.m. backup and today hold P (8,499 to 2,596). `jurisdiction` kept D's value. |
| April 28 | `patch_ceda_dates.py` filled dates on the 143 stale 2011 rows, keyed on `measure_id` alone. A `percent_yes` rescale also ran. | Per the review; not re-derived here |

The 188 dropped rows are the 157 stale ones, the 29 members of 2014 groups (whose CSV IDs
are the shared `Multi_MeasID`), and two 2002 rows: Strathmore A-02, blocked by id 9189, and
Monterey K, blocked by Butte B.

So the stamp marks rows the repair skipped. It does not mark the write that damaged them.

**Can it recur? Yes, in three ways, and one fault lets each of them pass unnoticed.**
- **Missing ID column.** If a file's ID header is not recognized, `measure_id` is empty and
  the identifier falls back to the title pattern (`src/database/models.py:155-171`). The
  parser then drops same-key rows inside the file (`src/parsers/ceda.py:374-384`) and the
  ingest overwrites on an exact match (`scripts/pipeline.py:330-338`).
- **County spelling.** The parser still emits raw county text, so a re-ingest of 2011 or
  2000 would again fail to match those rows.
- **An ID reused between releases.** An exact key match is treated as "same measure" with
  no check of county, designation or place. This is how id 4870 was overwritten, after the
  April repair. The 2002 pair shows it is not a one-off.
- **The fault that hides them:** a failed insert is counted, not raised
  (`pipeline.py:353-355`).

## 5. Effect on the live site

County pass rates as the site computes them, from the committed tool (`summary.json`,
`cohorts`). Three columns: what is stored; raw, using each county's own result; and raw,
using each measure's combined result. 2014 keeps its stored rows in all three, so its 29
missing county shares are a separate change.

| Cohort | Stored | Raw, county's own result | Raw, combined result |
|---|---|---|---|
| San Bernardino GO Bond (on 7 cards) | 60 of 87, 69% | 60 of 92, 65% | **63 of 92, 68%** |
| San Bernardino Property Tax | 3 of 15 | 3 of 17 | 3 of 17 |
| San Bernardino Business Tax | 11 of 17 | 11 of 18 | 11 of 18 |
| San Bernardino Sales Tax | 17 of 30 | 18 of 31 | 18 of 31 |
| San Bernardino Transient Occupancy Tax | 12 of 16 | 13 of 17 | 13 of 17 |
| San Bernardino Ordinance | 40 of 70 | 40 of 71 | 40 of 71 |
| San Mateo Property Tax | 76 of 105, 72% | 81 of 111, 73% | 81 of 111 |
| San Mateo GO Bond | 89 of 102, 87% | 90 of 105, 86% | 90 of 105 |

Charter Amendment in both counties, and San Mateo's other four cohorts, do not change. Not
every cohort appears on a published card; the GO Bond one is on seven.

**What adds five San Bernardino bonds.** Three failed 2000 bonds have no stored outcome
(ids 10015, 10017, 10018) and two sit under `SAN BERNADINO` (12113, 12114), which
`generate_site.py:243-246` keeps out on purpose.

**Which figure the site should use: the combined one, 63 of 92.** Five San Bernardino bond
rows are county shares of districts that cross the county line: Kern Community College G
(2002), Beaumont Unified AA (2004), Sierra Sands Unified A (2006), Muroc Joint Unified B
(2022) and Sierra Sands Unified AA (2024). A bond passes or fails on the whole district's
vote. Four of these passed although San Bernardino's share voted below 55%, and one failed
although its share voted above. Calling Kern's Measure G a failure because of one county's
precincts is false. All five are coded `Multi_CO=1` with a 55% requirement, so none is one
of the doubtful single-county conflicts the first review warned about.

**Summaries.** 23 of the 28 wrong rows have `summary_text`. A word-overlap test flags 20 as
describing the sibling. It flags none of the 192 other rows that were overwritten in 2025
and later repaired.

## 6. Years with no raw file (2016-2021, 2,521 rows)

- **2,520 rows equal `ceda_parsed.csv`** on votes, `pass_fail`, date and title. **One does
  not: id 4870** (§4).
- The CSV equals raw on votes and `pass_fail` for all 7,836 rows where both exist.
- None of these rows carries the stale stamp, and each year has as many distinct IDs as
  rows, so there is no 2014-style collapse.

Stated at its real strength: good evidence that these rows equal the CSV and were not left
stale; **no evidence that the CSV equals CEDA's current release.** The CSV came from a
different release than the archive files in at least three places (two IDs in 2002, one in
2016). Id 3736 (2018, no outcome) is still open.

## 7. What the review corrected in this report

- **Id 4870** was listed as a one-field difference. It is an overwritten measure, and
  Measure D is missing. The tool now reports it as "ID reused".
- **"Missed 157 rows because the refresh matched on spelling"** was half the mechanism. The
  failed match led to an insert that broke the unique rule, and the error was swallowed.
  The same rule accounts for the 29 missing 2014 members and the two 2002 rows, which this
  report had treated as separate defects.
- **"Fields never loaded"** was wrong for `ballot_question` (§3).
- **"Match: every compared field equals raw"** overstated it. All 6,169 have an empty
  question.
- **The July key** was coarser than "designation": the leading letters only.
- **April 28** was missing from the timeline.
- **§6** said 2,520 rows and dropped the one row that disagreed.
- **"Exactly as they are today"** holds for votes and question only. County, the percent
  scale, 2011 dates, summaries and `topic_primary` have changed since.
- **1,049 repaired** is right as a count. As a set it has two edge rows: id 10578 (a
  duplicate 1998 row, overwritten but unchanged) and id 8673 (only a vote rounded).
- **The cohort table** came from a one-off script and listed a cohort as "on current
  cards" that no card carries. It now comes from the tool.

Earlier corrections still stand: the first review dated the damage to April 12; my
assessment guessed a join on county and letter that day; and the completion plan's "69% to
71%" counted only the multi-county change.

## 8. Not verified

- 2016-2021 against raw; the Esploro release; anything needing the network.
- Taken from the review without re-deriving: the simulation that predicts 9,391 / 1,330 /
  188; the `scraper_runs` contents; the April 7 backup comparison; the April 28 date patch
  and percent rescale.
- Whether CEDA's current 2016 file holds both Measure D and Measure P.
- Real-world outcomes. "Raw" means CEDA's codes, and the first review shows `REQ` is
  miscoded in places.
- The summary test is a heuristic; it missed 3 of 23 known cases.

## 9. Files, and how to rerun

- `scraper/scripts/reconcile_ceda_raw.py` and `scraper/tests/test_reconcile_ceda_raw.py`
  (27 tests). Full suite: 740 passed, 1 skipped, with the known 1 failure and 17 errors.
  That is the 728 baseline, plus 10 new tests here and 2 from the Insights commits.
- Output: `scraper/data/exports/ceda_reconcile_20261112/summary.json` and `ledger.json`
  (gitignored). `summary.json` records each raw file's SHA-256, the tool's own, the cohort
  table, repeated IDs, release conflicts and a `gate` section.
- `xlrd 2.0.2` was installed with `pip install "xlrd>=2.0.0" --no-deps`; nothing else changed.

```text
cd scraper
python -I scripts/reconcile_ceda_raw.py --db data/ballot_measures.db ^
  --out data/exports/ceda_reconcile_20261112 ^
  --baseline-db data/backups/ballot_measures_backup_20250730_180629.db ^
  --csv data/processed/ceda_parsed.csv
```

The script opens every database `mode=ro`, hashes the target before and after, and exits 2
if the hash changed. With `--gate` it also exits 1 unless the result is clean; `--waive
YEAR:ID,...` names defects a recorded decision defers, and echoes them in the output.
