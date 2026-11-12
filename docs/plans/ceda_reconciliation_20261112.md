# CEDA reconciliation report (P1b.1b)

**Date:** November 12, 2026. **By:** Fable. **Branch:** `phase0-election-status` at `3fb00ffa`.
**Scope:** read-only. Every stored CEDA row in a year we hold a raw file for (21 files,
8,477 rows) compared field by field with its raw row. Nothing was written to any database.
**Production DB SHA-256, before and after:** `ef1359e482db2c54fe41068771932aaac7c9fc1db372e2e1d8cbbed1f505d9da`.
**Companion:** [P1b.2 design](ceda_backfill_design_20261112.md). Builds on the
[column check](ceda_column_check_20261111.md) and its [review](../codex/p1b_1_ceda_review_response.md).

## 1. Bottom line

1. **The wrong-row defect is from the first CEDA load on July 31, 2025, not April 12, 2026.**
   A July 2025 backup already holds all 28 wrong rows exactly as they are today.
2. **The first loader keyed rows on year, county and designation.** In that backup all 9,548
   CEDA fingerprints have the form `2011|MEASURE_A|LOS ANGELES|CEDA`. A later measure with
   the same key overwrote the earlier one: 1,077 rows were overwritten at load.
3. **April 12 repaired most of it.** That day's refresh from `ceda_parsed.csv` corrected 1,049
   of the 1,077 and restored 1,330 dropped measures. It missed 157 rows, because a migration
   minutes earlier had changed their county spelling and the refresh matched on spelling.
4. **Those 157 rows have been stale since July 2025.** 28 hold another measure's content,
   55 lack an outcome or a date, and 74 differ only in form.
5. **Otherwise the held years are sound.** 6,169 rows match raw exactly and 1,702 differ
   only in form. The other defects are the known ones: 2014's keys and one foreign 2002 row.
6. **Live cards are affected.** San Bernardino's GO bond pass rate, shown on 7 cards as
   69% (60 of 87), is 65% (60 of 92) once five failed 2000 bonds are counted. 23 wrong rows
   also display an AI summary of a different measure.
7. **It can happen again**, in two ways, and the unseen 2016-2021 files are the likely
   trigger (§4).

## 2. Reproduction of the earlier figures (acceptance check 1)

All from `scraper/scripts/reconcile_ceda_raw.py`; every figure below matches the column
check and its review.

| Figure | Result |
|---|---|
| Row counts, file against DB, 1998-2015 and 2022-2024 | Equal in every year except 2014 (577 file, 548 DB) and 2015 (120 file, 119 DB; the extra row is a 2016 measure, stored as id 4870) |
| Rows holding another measure's votes | **28**: 5 in 2000 (San Bernardino), 23 in 2011 (Los Angeles 16, Santa Clara 4, Fresno 2, Marin 1) |
| 2014 keyed on `Multi_MeasID` | 27 rows under their own ID, **521** under another row's, **29** file rows absent (all `Multi_CO=1`) |
| 2002 foreign row | id 9189, `200200001`: Mendocino H content; the raw row is Strathmore A-02 |
| `PASSFAIL` against `passfail_sum` flips | **112** in the 16 newly downloaded years; 145 across all 21 files |
| `passed` NULL | 2000: 6, 2005: 1, 2011: 48, 2018: 1 |
| Multi-county group checks | No violation in any of the 21 files |

## 3. Field-by-field result (acceptance check 2)

| Class | Rows | Meaning |
|---|---|---|
| match | 6,169 | Every compared field equals raw |
| format only | 1,702 | Differences vanish after normalizing case, spacing, county spelling or a placeholder title |
| wrong key | 521 | 2014: content is right, stored under the group key |
| incomplete | 55 | No conflict, but the outcome or the date is empty |
| wrong row | 28 | Content is another raw row's |
| foreign | 1 | Content is in no raw row (id 9189) |
| differs | 1 | id 4870: `jurisdiction` is `1`; raw `JUR` is 3 |
| missing from DB | 29 | The 2014 multi-county members |

Fields with real differences, out of 8,477 compared rows: votes and percent 29 each (the 28
wrong rows and 9189); `ballot_question` 28; `pass_fail` 16; `passed` 6. `election_date`,
`county` and designation differ only on 9189. `category_type` never differs.

Fields never loaded for most rows, which is the backfill's subject: `ballot_question`
6,722 rows empty; `jurisdiction` 1,754; `category_topic` 6,742.

**A wrong row is a hybrid, not a whole-row swap.** It keeps its own `measure_id`, county,
designation and `category_type`. Its question, votes, percent, `pass_fail` and AI summary
belong to the sibling. Example: id 6138 is Azusa's Measure A (`201100001`, an ordinance) but
shows Vernon's charter question, 43 to 9, and a summary about Vernon. Vernon's own row
(id 11458, `201100094`) is also stored correctly, so each of the 28 source
measures appears twice and 28 measures do not appear at all.

Stored outcome on the 28: agrees with the row's own raw outcome on 17 (by coincidence),
**contradicts it on 6**, and is NULL on 5.

## 4. Cause, and whether it can recur (acceptance check 3)

| When (Pacific) | What happened | Evidence |
|---|---|---|
| July 30, 2025, 5:28 p.m. | First CEDA load from the Excel files. Rows keyed on the title, `"<COUNTY> Measure <LTR>"`, so same-county, same-designation measures collided and the last one won. | `scraper/data/backups/ballot_measures_backup_20250730_180629.db`: 9,548 rows, all letter-keyed, 1,077 with `update_count > 0`; 2011 has 143 rows for 172 in the file. The code first appears in git at `f1a6c372` (August 8, 2025): `extract_measure_identifier` tried the title pattern before `measure_id`. |
| January 9, 2026 | Identifier changed to prefer `measure_id` (`3bc82b16`). `ceda_parsed.csv` was written the same day with ID keys and all 10,909 rows. The database was not rebuilt. | CSV `created_at` values; `git log -S` on `models.py` |
| April 12, 2026, 10:50 a.m. | `migrate_canonicalize.py` (`f075843b`) rewrote county names and all keys, stamping `updated_at`. **This is the 17:50:43 UTC stamp.** It changed no votes or questions. | `migrate_canonicalize.py:289-294`; 1,473 rows of five sources carry the stamp, not only CEDA's 157 |
| April 12, 10:53 a.m. and 2:37 p.m. | `pipeline.py` ingested `ceda_parsed.csv`: 1,330 dropped measures inserted (ids 10969-12298), and every row it could match refreshed. | `created_at` and `updated_at` values; commit message of `f075843b` |
| Same runs | 157 rows were not matched. The CSV spells their county as raw does (`Los Angeles`, `SAN BERNADINO`, `TOULUMNE`); the migration had just made the stored spelling canonical. | CSV fingerprint `2011|201100001|Los Angeles|CEDA` against stored `…|LOS ANGELES|CEDA` |

So the stamp marks the rows the repair skipped. It does not mark the write that damaged them.

**Not established:** which branch discarded the 157 CSV rows. They were neither updated nor
inserted, so one of the two swallowed-exception branches in `pipeline.py` took them.

**Can it recur? Yes.**
- **Missing ID column.** If a file's ID header is not recognized, `measure_id` is empty and
  the identifier falls back to the title pattern (`src/database/models.py:155-171`). The
  parser then drops same-key rows inside the file (`src/parsers/ceda.py:374-384`) and the
  ingest overwrites on an exact match (`scripts/pipeline.py:330-338`). The 2014 file shows
  how easily a header changes. The 2016-2021 files are unseen.
- **County spelling.** The parser still emits raw county text. Re-ingesting 2011 or 2000
  would again fail to match the 157 rows.

## 5. Effect on the live site

County pass rates on current cards, stored against raw per-county outcomes. 2014 is held
constant, so this isolates the stale rows. Combined multi-county results and the 29 missing
2014 county shares are separate changes.

| Cohort | Stored | Raw | Why |
|---|---|---|---|
| San Bernardino GO Bond | 60 of 87, 69% | 60 of 92, **65%** | Five failed 2000 bonds are missing: three have no outcome (ids 10015, 10017, 10018) and two sit under `SAN BERNADINO` (12113, 12114) |
| San Bernardino Property Tax | 3 of 15, 20% | 3 of 17, 18% | |
| San Bernardino Business Tax | 11 of 17, 65% | 11 of 18, 61% | |
| San Bernardino Sales Tax, TOT, Ordinance | one row each | | 57→58%, 75→76%, 57→56% |
| San Mateo Property Tax | 76 of 105, 72% | 81 of 111, 73% | Six 2011 rows with no outcome |
| San Mateo GO Bond | 89 of 102, 87% | 90 of 105, 86% | Three 2011 rows with no outcome |

Five rows are still stored under `SAN BERNADINO` (ids 12110-12114), so they are left out of
every San Bernardino statistic. `generate_site.py:243-246` keeps them out on purpose.

**Summaries.** 23 of the 28 wrong rows have `summary_text`. A word-overlap test flags 20 as
describing the sibling. It flags none of the 192 other rows that were overwritten in 2025
and later repaired.

## 6. Years with no raw file (2016-2021, 2,520 rows)

- The database equals `ceda_parsed.csv` on votes, `pass_fail`, date and title for all 2,520.
- The CSV equals raw on votes and `pass_fail` for all 7,836 rows where both exist.
- None of these rows carries the stale stamp, and each year has as many distinct IDs as rows,
  so there is no 2014-style collapse.
- 218 of them were overwritten in the 2025 load and refreshed on April 12.

This is good indirect evidence, not a raw check. Id 3736 (2018, no outcome) is still open.

## 7. Corrections to earlier statements

- **Review F2, "157 rows were written last-write-wins at 17:50:43".** The mechanism is
  right; the date and the write are not. The damage was done in July 2025. The stamp is the
  migration's.
- **Review, "the batch caused the `passed` NULLs and 14 NULL dates".** They are stale 2025
  values the April repair never reached. Same fix, different cause.
- **"Whole-row corruption".** The key fields and category are the row's own (§3).
- **My assessment** guessed "a join on county and letter" on April 12. Right key, wrong date.
- **Completion plan**, "San Bernardino GO bond rate moves from 69% to 71%": that counted
  only the multi-county change. The stale rows move it down to 65% first.

## 8. Not verified

- 2016-2021 against raw; the Esploro release; anything needing the network.
- The exact branch that skipped the 157 rows.
- Real-world outcomes. "Raw" here means CEDA's per-county `PASSFAIL`, which the review shows
  is itself doubtful where `REQ` is miscoded.
- The summary test is a heuristic; it missed 3 of 23 known cases.

## 9. Files, and how to rerun

- `scraper/scripts/reconcile_ceda_raw.py` and `scraper/tests/test_reconcile_ceda_raw.py`
  (17 tests). Full suite: 728 passed, 1 skipped, with the known 1 failure and 17 errors.
- Output: `scraper/data/exports/ceda_reconcile_20261112/summary.json` and `ledger.json`
  (gitignored; one ledger entry per row that is not an exact match).
- `xlrd 2.0.2` was installed with `pip install "xlrd>=2.0.0" --no-deps`; nothing else changed.

```text
cd scraper
python -I scripts/reconcile_ceda_raw.py --db data/ballot_measures.db ^
  --out data/exports/ceda_reconcile_20261112 ^
  --baseline-db data/backups/ballot_measures_backup_20250730_180629.db ^
  --csv data/processed/ceda_parsed.csv
```

The script opens every database `mode=ro`, hashes the target before and after, and exits 2
if the hash changed.
