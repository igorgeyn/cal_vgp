# CEDA raw files: download and column check (P1b.1)

Agent C, November 11, 2026. Read-only against the production DB. Nothing committed.

## 1. Bottom line

- **Got 16 of the 22 missing years: 1998-2010 and 2012-2014.** They are Internet Archive
  (Wayback) captures of the files CSU Sacramento ISR used to host on `www.csus.edu/isr/`
  (captured 2012-2015). They are **not** the current official release.
- **2016-2021 (6 years) are not obtained.** The official home is a JavaScript-only Esploro
  record; see §3. Igor needs to download them in a browser.
- **The archived copies are faithful to what we hold.** For 1998-2013, every DB CEDA row
  matches a file row by `MeasID`, and votes are identical apart from the defects in §6. The 2011
  measure sheet is cell-identical across the 2015 archive, the 2017 "revised" archive and our
  on-disk file.
- **Every backfill field exists, fully filled, in all 21 files we now hold:** `PLACE`,
  `BALQUEST`, `REQ`, `Multi_CO`, `Multi_MeasID`, `YES_sum`, `NO_sum`, `Total_sum`,
  `Percent_sum`, `passfail_sum`. The ID column exists too, but in 2014 it is named
  `MeasureID`.
- **New DB defects** (§6). 2014 is keyed on `Multi_MeasID`, so 521 of 548 rows carry another
  row's ID and 29 rows are missing. 28 rows in 2000 and 2011 hold another measure's votes.
- **KNOWN_ISSUES #1 is mis-diagnosed.** All five records have `REQ=T`, and `passfail_sum=FailT`
  agrees with their combined percent. The bad field is the per-row `PASSFAIL`, not the
  threshold (§8).

## 2. Sources

| Source | URL | What it has |
|---|---|---|
| Official, current | https://scholars.csus.edu/esploro/outputs/dataset/California-Elections-Data-Archive-CEDA/99257830890201671 | 121 files. Without JS only 5 are listed: Codebook, 2025 Dataset, three 2025 reports. Everything else sits behind "Show the rest". |
| Official 2025 dataset (seen, not downloaded) | https://scholars.csus.edu/view/fileRedirect?instCode=01CALS_USL&filePid=13306594370001671&download=true | xlsx, 53.54 kB |
| Codebook (seen, not downloaded) | https://scholars.csus.edu/view/pdfCoverPage?instCode=01CALS_USL&filePid=13306594360001671&download=true | pdf |
| SOS | https://www.sos.ca.gov/elections/county-city-school-district-ballot-measure-election-results | PDF reports only (county, city, school) for 1995-2025. No data files. |
| Archived ISR files (used) | `http://www.csus.edu/isr/reports/california_elections/CEDA{YYYY}Data.xls[x]`, via `https://web.archive.org/web/{ts}id_/{url}` | Data files for 1995-2014. Older copies also exist at `/isr/includes/ISR website/CEDA Files/CEDA {YYYY}/` (2006 captures, 1995-2005). |

## 3. Download manifest summary

Full manifest: `scraper/data/raw/ceda_downloads_20261111/manifest.json` (gitignored through
`scraper/.gitignore: data/raw/*`). Fetched one at a time with a 4 s pause and the project UA.
All responses were HTTP 200 with a spreadsheet content type.

| Folder | Original file (under `/isr/reports/california_elections/` unless noted) | Capture | Bytes | SHA-256 (first 16) |
|---|---|---|---|---|
| 1998 | CEDA1998Data.xls | 20130602 | 2,915,328 | a36661980f6c7aca |
| 1999 | CEDA1999Data.xls | 20130602 | 1,276,928 | dece0395b050b11c |
| 2000 | CEDA2000Data.xls | 20130602 | 2,746,368 | 8b9c82e62af41263 |
| 2001 | CEDA2001Data.xls | 20130602 | 1,346,560 | f0b1730e9bff1a25 |
| 2002 | CEDA2002Data.xls | 20130603 | 3,247,104 | 5c438ad444086383 |
| 2003 | CEDA2003Data.xls | 20130602 | 1,110,016 | 9f13d4ccf09974a6 |
| 2004 | CEDA2004Data.xls | 20130602 | 2,875,904 | 6264cf9875172531 |
| 2005 | CEDA2005Data.xls | 20130602 | 1,421,824 | 1b580ff2745bd939 |
| 2006 | CEDA2006Data.xls | 20120412 | 2,999,808 | 22ead3543031acd6 |
| 2007 | CEDA2007Data.xls | 20120412 | 1,103,872 | 3851bd6ee24c5561 |
| 2008 | CEDA2008Data.xls | 20120412 | 2,952,192 | ac13dafceb025da6 |
| 2009 | CEDA2009Data.xls | 20150908 | 1,127,424 | 17277a1b2578b897 |
| 2010 | CEDA2010Data.xls | 20150907 | 3,167,232 | 01a4be227ea0d0ff |
| 2012 | CEDA2012Data.xlsx | 20150908 | 1,542,019 | 23130ffb71c5da36 |
| 2013 | CEDA2013Data.xlsx | 20150909 | 493,274 | 0ac62d16e627ace4 |
| 2014 | CEDAData2014.xlsx | 20150908 | 1,441,636 | e1b1a81ac04e5452 |
| 2011_wayback_2015 | CEDA2011Data.xlsx (comparison only) | 20150908 | 461,715 | cb75a15361e8c4ad |
| 2011_wayback_2017_revised | `/isr/projects/ceda reports/revisedreports/ceda2011data.xlsx` (comparison only) | 20170810 | 402,967 | 20933a9fe107bdd6 |

### Blocked or not obtained

- **2016-2021: none.** The Wayback CDX for `csus.edu/isr/*` has no data files after 2014. A
  query of `csus.edu/college/social-sciences-interdisciplinary-studies/*` found none either.
  Queries for `csus.edu/center/*` and the whole domain returned **HTTP 503** ("Temporarily
  Offline"); not retried.
- **Esploro file list:** the record page is an Angular shell (200, 2,328 bytes). A guessed REST
  call (`/esplorows/rest/research/fullAssetPage/assets/99257830890201671?institution=01CALS_USL`)
  returned **HTTP 500**. Further API probing was **refused by the session's permission
  classifier**, so I stopped. The file IDs (`filePid`) can't be guessed.
- **Igor:** in a browser, open the Esploro record, click "Show the rest", and download
  "{year} Dataset" for **2016-2021**. Ideally also get 1998-2014, to confirm the archived copies
  match the current release (2011 already does). Save each file to
  `scraper/data/raw/ceda_downloads_20261111/<year>_esploro/`.

## 4. Per-year column matrix

**Present in all 21 files, same name in each:** `YEAR JUR CNTYNAME DATE PLACE CSD MEASTYPE LTR
BALQUEST RECTYPE RECTYPENAME RECTOPIC YES NO TOTAL PERCENT REQ PASSFAIL Multi_CO Multi_MeasID
YES_sum NO_sum Total_sum Percent_sum Outcome_sum`.

The 11 requested fields are 100% non-empty in every file (each column filled on every row).
Headers are plain ASCII with no padding in all years, so the parser's `' YES '` variants
never occur.

Columns whose name or presence varies:

| Year | Format | Measures sheet | Rows | ID | County no. | Topic name | passfail_sum | Outcome | Code cols | Extra |
|---|---|---|---|---|---|---|---|---|---|---|
| 1998-2010 | xls | `Measures{YYYY}` (2nd sheet) | see §5 | MeasID | CO | RECTOPNAME | passfail_sum | OUTCOME | typerec, topicrec | Orig_TYPE, Orig_TOPIC |
| 2011 | xlsx | `Measures2011` (2nd) | 172 | MeasID | CO | RECTOPNAME | **Passfail_sum** | OUTCOME | typerec, topicrec | Orig_TYPE, Orig_TOPIC, OTH |
| 2012 | xlsx | `Measures2012` (2nd) | 530 | MeasID | CO | RECTOPNAME | **Passfail_sum** | OUTCOME | typerec, topicrec | Orig_TYPE, Orig_TOPIC, OTH |
| 2013 | xlsx | `Measures2013` (2nd) | 137 | MeasID | **CO#** | **RECTOPICNAME** | **Passfail_sum** | OUTCOME | typerec, **topcrec** | OTH |
| 2014 | xlsx | **`measures2014` (1st)** | 577 | **MeasureID** | CO | RECTOPNAME | passfail_sum | OUTCOME | **TYPEREC, TOPICREC** | none |
| 2015 | xlsx | **`measures2015` (1st)** | 120 | MeasID, plus **MeasID_First** as col 1 | CO | RECTOPNAME | passfail_sum | OUTCOME | typerec, topicrec | none |
| 2016-2021 | no file | none | none | unknown | unknown | unknown | unknown | unknown | unknown | unknown |
| 2022 | xlsx | **`Measures 2022`** (2nd) | 580 | MeasID | CO# | RECTOPNAME | passfail_sum | OUTCOME | typerec, topcrec | none |
| 2023 | xlsx | `Measures 2023` (2nd) | 32 | MeasID | CO# | RECTOPICNAME | passfail_sum | OUTCOME | typerec, **toprec** | none |
| 2024 | xlsx | `Measures 2024` (2nd) | 866 | MeasID | CO# | RECTOPICNAME | passfail_sum | **outcome** | typerec, toprec | none |

Every file also has a candidates sheet (`Candidates{YYYY}`, `candidates2014/2015`,
`Candidates 2022`). In 2022-2024, RECTOPIC comes before RECTYPENAME.

Fields the current parser (`ceda.py` `column_mappings`) reads: `MeasID` (falling back to
`MeasID_First`, then `Multi_MeasID`), `BALQUEST LTR MEASTYPE DATE YEAR YES NO TOTAL CNTYNAME
PLACE JUR PASSFAIL PERCENT OUTCOME RECTYPE RECTYPENAME RECTOPIC RECTOPICNAME/RECTOPNAME`. It maps
`PLACE` but never passes it to `BallotMeasure`, and it never reads `REQ` or the `Multi_*`/`*_sum`
fields.

## 5. Row counts: raw file vs DB (`data_source='CEDA'`, by `year`, keyed on `measure_id` = `MeasID`)

| Year | File | DB | Matched | File-only | DB-only | Vote mismatches | Note |
|---|---|---|---|---|---|---|---|
| 1998 | 572 | 572 | 572 | 0 | 0 | 0 | |
| 1999 | 283 | 283 | 283 | 0 | 0 | 0 | |
| 2000 | 559 | 559 | 559 | 0 | 0 | **5** | collisions, §6b |
| 2001 | 233 | 233 | 233 | 0 | 0 | 0 | |
| 2002 | 657 | 657 | 657 | 0 | 0 | **1** | foreign row, §6c |
| 2003 | 178 | 178 | 178 | 0 | 0 | 0 | |
| 2004 | 712 | 712 | 712 | 0 | 0 | 1 | not real: file YES = 12065.486 (fractional), DB 12065 |
| 2005-2010 | 295 / 556 / 179 / 593 / 193 / 482 | same | all | 0 | 0 | 0 | |
| 2011 | 172 | 172 | 172 | 0 | 0 | **23** | collisions, §6b |
| 2012 | 530 | 530 | 530 | 0 | 0 | 0 | |
| 2013 | 137 | 137 | 137 | 0 | 0 | 0 | |
| **2014** | **577** | **548** | 548* | **29** | 0 | **521** | *matched only by accident; DB is keyed on Multi_MeasID, §6a |
| 2015 | 120 | 119 | 119 | 1 | 0 | 0 | the extra row `201600120` has YEAR=2016 (Santa Cruz City Elem. P, DATE 2016-11-17); the DB holds it under 2016. Reconciles. |
| 2016-2021 | none | 872 / 113 / 704 / 68 / 720 / 44 | not checked | | | | no raw file |
| 2022 | 580 | 580 | 580 | 0 | 0 | 0 | |
| 2023 | 32 | 32 | 32 | 0 | 0 | 0 | |
| 2024 | 866 | 866 | 866 | 0 | 0 | 0 | |

## 6. DB defects found (reported, not fixed)

a. **2014 keyed on `Multi_MeasID`.** The 2014 file names its ID column `MeasureID`. The
   parser's `measure_id` aliases (`MeasID`, `MeasID_First`, `Multi_MeasID`) don't match it
   exactly, but `Multi_MeasID` does. So every 2014 row got its group key as `measure_id`:
   - all 548 DB `measure_id`s are `Multi_MeasID` values;
   - 27 rows equal their own row (where `MeasureID == Multi_MeasID`), and 521 carry the votes of
     a row whose `MeasureID` differs;
   - the 29 surplus members of multi-county groups were collapsed away (577 - 548).

   A backfill keyed on `MeasID` would join the wrong 2014 rows. Remap through `Multi_MeasID`
   first.
b. **Same county+letter collisions.** 5 rows in 2000 (all San Bernardino; CEDA spells it
   `SAN BERNADINO`) and 23 in 2011 (Fresno, LA, Marin, Santa Clara) hold the votes of a
   *different* file row. It has the same county and letter but a different `PLACE`: e.g. DB
   `201100001` "Azusa A" holds Vernon A's 43/9. Row 10016 (`200000154`) ends up with
   `pass_fail='FailT'` and `passed=1`. Likely mechanism, not verified: the "exact duplicate →
   update" path in `pipeline.ingest_measures` matching on a content hash of
   `"{COUNTY} Measure {LTR}"` plus an empty question.
c. **2002 foreign row.** DB `200200001` (row 9189) is "MENDOCINO H" with 2116/903, PassF. The
   2002 file has no Mendocino H. Its `200200001` is Tulare A-02 (Strathmore Union High), and
   that measure is absent from the DB.
d. **`ballot_question` is not empty on every CEDA row**, contrary to the plan. It is filled for
   2015, 2022-2024 and 143 of 172 rows in 2011 (rows ingested from the Excel files, which have no
   `jurisdiction`). It is also filled on 11 rows in 2000, 2 in 2005, and 1 each in 2009 and 2016.
   Elsewhere it is empty and `jurisdiction` holds the JUR code. `vote_threshold` is NULL on all
   10,997 CEDA rows.

## 7. `passed` NULL while `pass_fail`/`percent_yes` are set (CEDA, per year)

| Year | Rows with `passed` NULL | ...of which have `percent_yes` + `pass_fail` | pass_fail values |
|---|---|---|---|
| 2000 | 6 | 6 | FailT 5, PassT 1 (all San Bernardino; ids 10013-10015, 10017, 10018, 10020) |
| 2005 | 1 | 1 | PassF 1 (id 8250, Tuolumne M; CEDA spells it `TOULUMNE`) |
| 2011 | 48 | 48 | PassT 23, FailT 18, PassF 5, FailF 2 (2 of them are also §6b collision rows) |
| 2018 | 1 | 0 | `pass_fail` NULL too (id 3736, `201800266` Monterey N, 51.3%); no raw file |
| All other years | 0 | 0 | |

All 2000/2005 cases are in counties CEDA misspells, and every row in this table except 2018
has `updated_at` 2026-04-12 (the 2000 and 2005 rows at 17:50:43). Separately, one row has
`pass_fail='FailT'` with `passed=1` (§6b).

## 8. What the backfill parser must handle

- **ID:** `MeasID`, or `MeasureID` in 2014. Never fall back to `Multi_MeasID`. In xls years
  (1998-2010) IDs are floats (`200000174.0`), so cast them to int. In 2015, ignore
  `MeasID_First` (117 unique values in 120 rows); `MeasID` matches the DB.
- **`Multi_MeasID`** is filled on every row and uses the MeasID number range. For most single
  rows it equals an *unrelated* row's `MeasID` (in 2000, all 540 distinct values do). Use it
  only as a within-year group key, together with `Multi_CO=1`.
- **Group anomalies:**
  - In 1998, 1999, 2002 and 2005, two rows each share a `Multi_MeasID` with `Multi_CO=0`
    and `*_sum` equal to their own votes.
  - 2012 has 4 rows with `Multi_CO=0`, no group, and `YES_sum != YES`.
  - 2006 and 2024 each have one `Multi_CO=1` row whose sum equals its own votes.
- **Case-insensitive names:** `passfail_sum`/`Passfail_sum`, `OUTCOME`/`outcome`, `CO`/`CO#`,
  `RECTOPNAME`/`RECTOPICNAME`, and `typerec`/`TYPEREC` with `topicrec`/`topcrec`/`toprec`/`TOPICREC`.
  Sheet names vary: `Measures{Y}`, `measures{Y}`, `Measures {Y}`. The measures sheet is first in
  2014-2015 and second otherwise.
- **Formats:** `.xls` (BIFF, needs `xlrd`, which is not installed here) for 1998-2010, `.xlsx`
  for the rest. `DATE` is an Excel serial float in xls years and a datetime in xlsx years.
  `PERCENT`/`Percent_sum` are 0-1 fractions in every year (the DB stores 0-100).
- **Codes:** `REQ` is M/T/F (no F before 2002, or in 2023). `PASSFAIL`/`passfail_sum` are
  Pass/Fail for majority, plus T or F suffixes. The suffix matches `REQ` on every row except
  2014 `201400551` (REQ F, PASSFAIL FailT, passfail_sum PassF). `OUTCOME`: 1 = pass,
  2 = fail. `JUR`: 1 county, 2 city, 3 school.
- **Text:**
  - `CNTYNAME` is upper case except 2011 (mixed case).
  - Misspellings: `SAN BERNADINO` (2000: 16 rows, 2009: 1), `TOULUMNE` (2005: 2).
  - 2024 contains U+200B in `PLACE` (19), `LTR` (16) and `BALQUEST` (15), NBSP in `PLACE` (6),
    and 3 padded `PLACE` values.
  - NBSP or soft hyphens appear in `BALQUEST` in 2006, 2008, 2010 and 2022 (NBSP 17), plus one
    padded `LTR` in 2002.
  - `BALQUEST` has curly quotes and newlines throughout.
  - Checked by code point, not console output.
- **Fractional votes:** `YES` = 12065.486 in 2004 `200400671`.
- **Combined vs county outcome:** rows where `PASSFAIL` and `passfail_sum` disagree. Every such
  difference is a real pass/fail flip:

  | Year | 1998 | 1999 | 2000 | 2001 | 2002 | 2003 | 2004 | 2005 | 2006 | 2007 | 2008 | 2009 | 2010 | 2011 | 2012 | 2013 | 2014 | 2015 | 2022 | 2023 | 2024 |
  |---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
  | Flips | 7 | 3 | 5 | 4 | 18 | 2 | 16 | 4 | 22 | 1 | 9 | 1 | 2 | 1 | 5 | 0 | 13 | 2 | 10 | 0 | 20 |

  That is 112 rows in the 16 new years.
- **KNOWN_ISSUES #1 (all five records now in hand):**

  | Record | REQ | PASSFAIL | PERCENT | Percent_sum | passfail_sum | Multi_CO |
  |---|---|---|---|---|---|---|
  | 200100189 Humboldt / Shasta-Tehama-Trinity JCC A | T | PassT | 54.5% | 58.8% | FailT | 1 |
  | 200400170 LA / La Cañada USD B | T | PassT | 63.5% | 63.5% | FailT | 0 |
  | 200400215 Santa Clara / Gavilan CCD E | T | PassT | 56.7% | 56.5% | FailT | 1 |
  | 200400219 Santa Cruz / Cabrillo CCD D | T | PassT | 62.0% | 61.6% | FailT | 1 |
  | 200500247 Kings / Kingsburg JUHS K | T | PassT | 55.6% | 66.0% | FailT | 1 |

  `passfail_sum` is internally consistent and `PASSFAIL` is not. The "likely 50%" guess in
  KNOWN_ISSUES isn't supported by `REQ`. Some of these may really be 55% school bonds coded T, so
  the source check is still needed.

## 9. Scripts

In `C:\Users\igorg\AppData\Local\Temp\claude\3706ee781272b6b6\d90ea535-f05d-4a6f-929d-dbc27318d103\scratchpad\agent-c\scripts\`
(run with `python -I`; `xlrd 2.0.1` is installed in the scratch `libs\` folder):
`download_wayback.py`, `inspect_ceda.py`, `analyze_ceda.py`, `diag_ids.py`, `diag_2014.py`,
`scan_text.py`, `multi_check.py`, `req_check.py`, `diff_versions.py`, `lookup.py`. Their outputs,
`structure.json` and `analysis.json`, are in the `agent-c\` folder.
