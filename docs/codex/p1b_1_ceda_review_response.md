Written by a Claude reviewer agent in place of Codex on 2026-11-12, at `phase0-election-status` HEAD `689cd1ddf6ed65b374575d13ffb8762edda7940b`.

# P1b.1 CEDA downloads and column check: review

**Verdict: the download and most of the diagnosis are accurate. P1b.2 should not start as currently specified.** I reproduced every headline number I tested. I also found three problems the backfill plan does not cover:

1. The plan's outcome rule would flip probable-correct passes to fails.
2. The wrong-vote rows are wrong across the whole row, not just in their votes, and come from one identifiable write batch. That batch touched 157 rows.
3. Remapping the 2014 keys needs a transactional two-phase update, and its side artifacts must move with it.

The archived files are fine for development on a database copy. They should not be the release provenance until the current Esploro release and the codebook are in hand.

What I did: I read the column check, the prompt, `ceda.py`, `pipeline.py`, `deduplication.py`, `operations.py`, `generate_site.py`, the Phase 1b plan and KNOWN_ISSUES. I copied the production DB to scratch with the SQLite backup API (source opened `mode=ro`) and queried only the copy. I read the 18 downloaded files, the five on-disk raw files and `ceda_parsed.csv` with `python -I` scripts kept in my own scratch folder.

For `.xls` I used the `xlrd 2.0.1` that agent C had installed in its scratch folder. I copied it to my own folder and checked all 16 files against its `RECORD` hashes, which all matched. That shows the copy is internally consistent; it does not prove it matches PyPI. I made no network requests, wrote nothing to the repo except this file, and committed nothing.

## Reproduction status

| Claim (column check) | Status |
|---|---|
| Manifest: 18 files, SHA-256 and byte counts | **Reproduced.** All 18 hashes and sizes match. |
| 2011 measure sheet cell-identical across 2015 archive, 2017 "revised" archive, on-disk file | **Reproduced.** 172 rows, 0 differing cells, same headers. |
| §5 row counts 1998-2015, 2022-2024; matched/file-only/DB-only | **Reproduced** for every year. 2014 is 577 file rows against 548 DB rows; 2015 is 120 against 119 (`201600120` is held under 2016, id 4870). |
| §6a 2014: all 548 `measure_id`s are `Multi_MeasID` values; 27 own / 521 other; 29 missing | **Reproduced.** Each DB row resolves to exactly one file row by (`Multi_MeasID` = old id, county, letter, YES, NO). The 548 resolved `MeasureID`s are distinct. The 29 missing rows are all `Multi_CO=1` members: 23 groups of 2, one of 3 and one of 5. |
| §6b 28 wrong-vote rows (5 in 2000, 23 in 2011) | **Reproduced**, with a different mechanism (F2). |
| §6c 2002 foreign row `200200001` (id 9189, Mendocino H 2116/903) | **Reproduced**, with more context (F4). |
| §6d / Q5 `ballot_question` filled: 2011 143/172, 2015, 2022-2024, 2000 11, 2005 2, 2009 1, 2016 1 | **Reproduced.** 28 of those filled values are another measure's question (F2). |
| `vote_threshold` NULL on all 10,997 CEDA rows | **Reproduced.** |
| §7 `passed` NULL: 2000 6, 2005 1, 2011 48, 2018 1 | **Reproduced.** All 55 in 2000/2005/2011 carry `updated_at` 2026-04-12 17:50:43, not only the 2000/2005 rows. |
| §8 PASSFAIL vs `passfail_sum` flips, 112 in the 16 new years; per-year table | **Reproduced** exactly. |
| §8 KNOWN_ISSUES #1 table (REQ, PASSFAIL, PERCENT, Percent_sum, passfail_sum, Multi_CO) | **Reproduced.** I disagree with the interpretation (F1). |
| §8 text hazards | **Reproduced, with corrections.** The 2024 figures (19/16/15 ZW, 6 NBSP) count characters, not rows; by row they are 12/12/6/4. 2024 `BALQUEST` NBSP (17 rows, 64 chars) and soft hyphens (6) are omitted, as is one other non-ASCII `PLACE`. |
| §8 group anomalies | **Partly.** The pairs and the 2012 4 rows are reproduced. The 2006/2024 "sum equals own votes" rows are benign: only `YES_sum` equals, because the other member had 0 yes votes. |
| §8 "11 fields 100% non-empty" | **True but misleading.** 2012 has a `#NULL!` placeholder in `BALQUEST` and in `RECTYPENAME`. |
| Esploro / 2016-2021 / Wayback CDX observations | **Not verified** (no network). |

## Findings, ranked by severity

### F1 (P1): the plan's outcome rule would flip probable-correct passes, and `REQ` is not a reliable threshold source

**Evidence.**
- The Phase 1b exit is "no stored outcome differs from CEDA's combined outcome" (`docs/plans/local_measures_completion_plan_20261105.md:147`).
- The column check reads the KNOWN_ISSUES #1 records as "`passfail_sum` is internally consistent and `PASSFAIL` is not" (`ceda_column_check_20261111.md:228`).

The files point the other way:

- **The 2004 records carry Proposition 39 wording.** The three 2004 records (`200400170`, `200400215`, `200400219`) are school GO bonds with `REQ=T` whose ballot text has Proposition 39 accountability language ("oversight", "audit", "administrator" salaries). In 2004, 155 school GO bonds are `REQ=F`, and 134 of those have the same markers. Only 17 are `REQ=T`.
- **All five pass at 55% and fail at two-thirds** on combined `Percent_sum`: 58.8, 63.5, 56.5, 61.6 and 66.0.
- **`200400170` (La Cañada B) is a single-county row** (`Multi_CO=0`): `PERCENT` = `Percent_sum` = 63.53%, `PASSFAIL=PassT` and `passfail_sum=FailT`. With the same percent on the same row, the two fields can only disagree if they were computed against different thresholds. `passfail_sum` follows `REQ` mechanically, so it inherits any `REQ` error.
- **Members of one group disagree with each other.** Cabrillo D is PassT in Santa Cruz (62.0%) and FailT in Monterey (49.3%). Gavilan E is PassT in Santa Clara (56.7%) and FailT in San Benito (56.0%). Per-row `PASSFAIL` is not a measure outcome under any single threshold.
- **2001 school bonds are coded majority.** Before 2002 there is no `F` code at all. In 2001, 24 school GO bonds are `REQ=M`, most with Proposition 39 text (for example Mt. San Antonio CCD at 58.5% and Barstow USD at 56.8%). A literal `REQ` → `required_vote` mapping would label them "majority".

**Impact.** Applying the exit rule mechanically would turn five likely-correct passes into fails. It would also write wrong `required_vote` values across 2001 (and any `REQ=T` Proposition 39 bonds after it). The 2014 `201400551` mismatch the check notes (REQ F, PASSFAIL FailT, passfail_sum PassF) is the same class of problem.

**Fix.**
- Treat `REQ` as a CEDA claim, not truth. Store `ceda_req` raw; derive `required_vote` with rules plus flags.
- Flag every GO bond on or after November 2000 with Proposition 39 markers whose `REQ` is not `F`.
- Exclude every row where `PASSFAIL` and `passfail_sum` disagree with no combining reason (`Multi_CO=0`) from the automatic outcome rule. Route those rows to Igor's P1b.3 list instead.
- Rewrite the exit as: "no stored outcome differs from CEDA's combined outcome, except listed, reviewed conflicts."

### F2 (P1): the 28 wrong-vote rows are whole-row corruption from one write batch, which also caused the `passed` NULLs and 14 NULL election dates

**Evidence.**
- **One batch.** Exactly 157 CEDA rows carry `updated_at` 2026-04-12 17:50:43: 11 in 2000, 2 in 2005, 1 in 2009 and 143 in 2011.
- **Last write wins.** All 157 hold exactly the votes and `BALQUEST` of the **last** file row with the same (year, canonical county, letter). For 129 rows that last row is the row itself. For the other 28 it is a different measure: the §6b set exactly. In every case the source row's `MeasID` is later in file order.
- **The whole row came along.** On the 28 rows, `ballot_question`, `pass_fail` and `percent_yes` also belong to the other measure, not just `yes_votes`/`no_votes` (my `fullcmp.py`: 23 `bq` mismatches in 2011, 5 in 2000).
- **At least 7 of the 28 show a flipped outcome**: `200000154`, and 2011 `…082`, `…084`, `…020`, `…024`, `…025`, `…044`.
- **Measures are double-counted.** The source rows (for example Vernon A, `201100094`) also keep their own correct row. Today 28 measures count twice and 28 are missing from every statistic.
- **The `passed` NULLs come from the same batch.** All 55 NULLs outside 2018 are batch rows.
- **The batch also nulled dates and changed counties.** The 14 batch rows in counties CEDA misspells (11 SB in 2000, 2 Tuolumne in 2005, 1 SB in 2009) have `election_date` NULL. That defect is not in the column check. Those rows also had their county canonicalized, while 5 other 2000 `SAN BERNADINO` rows kept the misspelling.
- **The column check's hypothesis does not fit the code.** It proposed content-hash matching (§6b). But in `scraper/scripts/pipeline.py:339-346` a content or cross-source match **inserts and marks a duplicate**, and no CEDA row has `is_duplicate=1`. Only an `exact` fingerprint match updates (`:330-338`). I could not identify the script that wrote the batch. The behaviour, a last-write-wins update keyed on (year, county, letter), is established from the data. That pair is not a unique key in CEDA.

**Fix.**
- Before any backfill, restore all 157 batch rows, every field, from the source row with the same `MeasID`. Keep `id`.
- List each changed outcome for Igor.
- Change the plan's "fill `ballot_question`" (`completion_plan:138-139`) to **replace from source on every CEDA row**. A fill-if-empty pass, and `update_measure`'s protect-non-empty rule (`scraper/src/database/operations.py:199-235`), would keep the 28 wrong questions.
- Add a parser invariant: never join or update on (year, county, letter).

### F3 (P1): the 2014 remap needs a transactional two-phase update, and its side artifacts must be regenerated in the same change

**Evidence.**
- **Remap targets are already in use.** `measures.fingerprint` has a UNIQUE index (`idx_fingerprint`) and embeds `measure_id`. 502 of the 548 target `MeasureID`s are currently held as `measure_id` by a *different* 2014 row.
- **The normal update path would fail.** A per-row remap through `Database.update_measure` recomputes the fingerprint (`operations.py:252-276`) and would hit the unique constraint part-way through. The ingest path swallows such errors into `stats["errors"]` (`pipeline.py:353-355`).
- **Site artifacts are keyed on `measure_id`.** In `generate_site.py`, research data falls back to a `measure_id` key (`:221-222`, `:289`) and the similar-measure embeddings are keyed on `measure_id` (`:332-341`). `scraper/data/embedding_metadata.json` lists 577 2014 entries with only 548 unique keys (25 duplicated) and a `neighbors` dict with 548 2014 keys. Those keys are exactly the DB's current wrong `Multi_MeasID` set, so the precomputed similarity data carries the same keying error.
- **The defect predates the April rebuild.** `scraper/data/processed/ceda_parsed.csv` (Jan 2026) has the same keying: 577 rows, 548 unique 2014 ids.

**Fix.** Answered in Q2.

### F4 (P2): the archive is faithful to what we hold, not demonstrably to the current release; the 2002 foreign row shows another release existed

**Evidence.**
- **What the 2011 check proves.** The archive matches our on-disk file. No repo doc records the on-disk file as an Esploro download.
- **Revisions happened.** The 2017 "revisedreports" path shows CSUS revised its releases.
- **`ceda_parsed.csv` reflects a different 2002 release.** Its 2002 has **659** rows against 657 in the 2013 archive. The two extras collide on ids: `200200001` Mendocino H (2116/903, dated 2002-03-03) and `200200002` Monterey K (2210/1212, dated 2002-11-03). The DB kept Mendocino H in place of Strathmore A-02, and kept Butte B, dropping Monterey K (no DB row has 2210/1212). The Mendocino H question text is in no held file.
- **The codebook has not been read.** The `REQ`, `JUR`, `OUTCOME` and `Multi_CO` semantics in §8 are inferred.

**Fix.** Answered in Q1.

### F5 (P2): KNOWN_ISSUES #1 is stale beyond its diagnosis

**Evidence.**
- **The ids point at other measures.** `docs/KNOWN_ISSUES.md:23-29` lists ids 9320, 7513, 8300, 8326 and 7948. In the current DB those are other measures (`200200171`, `200700171`, `200400393`, `200400408`, `200600178`). The five records are now ids 9589, 8065, 8724, 8742 and 8442.
- **The field it describes is empty.** The entry describes `vote_threshold='66.67%'`, but `vote_threshold` is NULL on every CEDA row. Only 9 registrar rows hold `66.67%`.

**Fix.** Rewrite #1: keyed by `measure_id`, with current ids noted as of a date. See Q5 for the framing. The stale ids also show that `id` stability is a rule for the future and was not true historically. Never join to doc-recorded ids.

### F6 (P3): accuracy nits in the column check

- §7 understates the batch: all 55 rows are at 17:50:43, not only 2000/2005.
- §8 text counts are characters, not rows. 2024 `BALQUEST` NBSP/SHY is missing.
- `#NULL!` occurs in 2012.
- The identical-vote pairs are probably source errors, not groups:
  - 1998 Inglewood D appears **twice** with the same letter, place and votes;
  - 1999 Los Altos G/H, 2002 Kashia 1/2 and 2005 Nashville Trail I2/I3 are distinct letters with identical votes.
- The 2006/2024 "sum equals own" rows are benign.

## Answers

### 1. Are the archived 1998-2014 files acceptable for P1b.2?

**Yes for building and testing P1b.2 on a copy. No as the release's source of record.** Record per-value provenance from the start (manifest path, SHA-256, Wayback URL, sheet, row, `MeasID`) so swapping sources later is a diff, not a rebuild.

Gate P1b.4 on:

- Igor downloading the Esploro release for 2016-2021, and at least every year with a P1b.3 outcome change. Ideally all of 1998-2014.
- Downloading the codebook.
- A per-year cell diff, archive against Esploro. Any difference becomes a reviewed item.
- Searching the new files for the 2002 Mendocino H / Monterey K rows (F4).

Do not wait on Esploro to *start* P1b.2.

### 2. Is the 2014 diagnosis right? How should the remap be done?

**Yes, the diagnosis is right.** The root cause is `ceda.py:35`'s exact-alias pass picking `Multi_MeasID` when `MeasID` is absent. I reproduced the 27/521/29 split, and every row maps uniquely.

Safe remap, on a copy, in one transaction:

1. **Build the mapping.** Map `id → new MeasureID` by unique match on (old `measure_id` = `Multi_MeasID`, canonical county, stripped letter, YES, NO). Assert 548 rows, a bijection, 27 self-maps, and no unmatched rows.
2. **Apply it in two phases.** Set every 2014 CEDA row to a non-colliding temporary key (for example `'REMAP:'||id`), then set the final `measure_id`. Recompute `fingerprint` and `measure_fingerprint` in SQL from the same formula as `models.py:131-147`. Assert the unique index holds and nothing besides those three columns changed. Each row's content already belongs to its new key, so cards for each `id` keep their content.
3. **Insert the 29 missing members** as **new** rows, which never reuse an existing `id`. Follow the multi-county representation decision (county-portion rows or a group key), so they don't add 29 measures to statistics.
4. **Then run the `MeasID`-keyed backfill.**
5. **Handle side artifacts in the same commit** (atomic flip): regenerate embeddings/neighbors for 2014, or remap their keys with the mapping. Do the same for any research data keyed by `measure_id`. Re-key the derived `ceda_parsed.csv`, or mark it superseded, so a pipeline rerun cannot reintroduce the bad keys.

Parser change: build an explicit per-year column map with case-insensitive exact names. Drop the substring fallback in `_find_column` (`ceda.py:268-273`) and fail loudly on a missing ID column.

### 3. Do the wrong-vote rows need their own fix ahead of the backfill?

**Yes, both.**

- **The 28 rows.** Fix them as part of restoring all 157 batch rows (F2), before the backfill. If they wait for the backfill, Layer 1 ("single-county rows keep identical figures") stops being a strict invariant: these rows and the 521 remapped 2014 rows legitimately change. Do the repair as a separately verified step with its own changed-outcome list, so the backfill's Layer 1 can stay exact.
- **The 2002 row.** Do not overwrite id 9189 with Strathmore: that silently changes what an existing card shows. Instead:
  - quarantine 9189: flag it, take it out of statistics, and give it a non-colliding provisional `measure_id`, recording the old one;
  - insert Strathmore A-02 as a new row under `200200001`;
  - resolve Mendocino H against the Esploro files or Mendocino County records.

  Igor decides whether 9189 is retired or kept as a separate, verified measure. Log Monterey K (2002) as a lead.

### 4. Is the parser checklist (§8) complete?

It is mostly complete. Add or correct:

- **`Multi_*` groups.** In all 21 held files, no multi-row group disagrees on `YES_sum`/`NO_sum`/`Total_sum`/`passfail_sum`/`REQ`/`DATE`/`Multi_CO`. Every `Multi_CO=1` group's `YES_sum` equals the sum of member `YES`. **Assert these per year** rather than assume them; 2016-2021 are unseen. Per-member `PASSFAIL` differs within groups, so use it only as a county-portion value.
- **Identical-vote pairs.** Flag the four `Multi_CO=0` pairs as probable source errors; the 1998 Inglewood D row is a duplicate. Do not treat them as groups.
- **`.xls` years.** I found no non-integral IDs. All float IDs are integral, so assert that and cast them. Convert dates with the workbook's `datemode`, not an assumed epoch. With the 1900 system, dates match the DB on every row except the known defects. Fractional votes (2004): set a rounding policy and record it.
- **Names.** Use explicit per-year maps (Q2). Pick the sheet by normalized name, not position. `Outcome_sum` currently wins the `outcome` alias in every year but 2024.
- **Invisible characters.** Normalize U+200B, NBSP, U+00AD and padding in `PLACE`/`LTR`/`CNTYNAME` for **matching**, using row counts from F6. Keep raw `BALQUEST` and store a cleaned copy. `LTR` carries ZW on 12 rows in 2024, so any letter match must strip first.
- **Misspelled counties.** Canonicalize for matching but keep the raw value. The DB is mixed today: 5 SB rows in 2000 still misspelled, 14 canonicalized. `generate_site.py:243-246` relies on the raw spelling for the reviewed San Bernardino GO-bond cohort, so recanonicalizing changes that cohort. Put the change in the P1b.3 list.
- **Placeholders.** Treat `#NULL!` (and any `#…!`) as missing.
- **Keys.** Assert `MeasID` is unique per file. Never join on (year, county, letter) (F2). Key on `MeasID` and the row's `YEAR` (the 2015 file holds a 2016 row).
- **`REQ`.** Raw only, plus flags (F1). There is no `F` before 2002; 2001 Proposition 39 bonds are coded `M`.

### 5. Should KNOWN_ISSUES #1 be re-framed, and the BALQUEST claim corrected?

**Re-frame #1, but not as "`PASSFAIL` is wrong".** The evidence (F1) better supports "`REQ=T` on probable Proposition 39 55% bonds". If so, `PASSFAIL=PassT` is right and the combined `passfail_sum=FailT` inherits the `REQ` error.

New framing: "CEDA's per-row and combined outcomes conflict; `REQ` probably miscoded; held out of automatic outcome changes until checked against county or SOS records." Also fix the stale ids and the `vote_threshold` premise (F5).

**Yes, correct the BALQUEST claim** at `local_measures_completion_plan_20261105.md:123`. Say that 28 filled values are wrong (F2), and that KNOWN_ISSUES #5's "source limitation" is false for `ballot_question`.

### 6. Are the `passed`-NULL rows one fix or several?

**Two.**

- **The 55 rows in 2000, 2005 and 2011.** One cause: the 17:50:43 batch. Fix them by the F2 restore. Then derive `passed` from the post-backfill outcome rule (combined for multi-county, reviewed conflicts excluded), not by a `pass_fail` prefix patch. Row 10016 (`FailT`, `passed=1`) is in the same batch.
- **2018 id 3736** (`201800266` Monterey N, 51.3%). This row has `pass_fail` NULL too and a different write time (14:37:07). It is a separate source or ingest gap and waits for the 2018 file.

## Recommended P1b.2 order of operations (all on a DB copy)

1. **Parser.** Explicit per-year column maps; the invariant asserts from Q4; per-value provenance.
2. **Snapshot and baseline.** Before/after per-year counts and a per-row hash of every CEDA field.
3. **Restore the 157 batch rows** from source by `MeasID` (F2). Output: changed-outcome list A.
4. **Remap 2014** with the two-phase transaction (Q2). Assert only key columns changed.
5. **2002:** quarantine 9189 and insert Strathmore (Q3, decision for Igor).
6. **Insert the 29 missing 2014 members** as new rows, using the chosen multi-county representation.
7. **Backfill** `place_name`, `jurisdiction_kind`, raw `ceda_req` with a derived `required_vote` and flags, `multi_measure_id`, and `ballot_question` (replace, not fill). Then the combined results. Layer 1 strict on single-county rows from here on.
8. **Normalize `passed`** from the outcome rule. Keep conflicts (F1, 2014 `201400551`) out of automatic changes. Output: list B for Igor.
9. **Regenerate** embeddings/neighbors and any `measure_id`-keyed artifacts in the same change. Update KNOWN_ISSUES #1/#5.
10. **2016-2021** after Igor's download: same pipeline, plus a cell diff of archive against Esploro before P1b.4.

## Not verified

- The Esploro release, Wayback CDX results, or anything requiring the network.
- 2016-2021, for which there are no files.
- Real-world thresholds or outcomes of the KNOWN_ISSUES #1 measures. The Proposition 39 reading rests on ballot-text markers and CEDA's own coding pattern.
- Which script wrote the 17:50:43 batch (only its behaviour), and how 29 multi-county 2014 members were collapsed in the earlier ingest.
- The origin of the Mendocino H and Monterey K rows in `ceda_parsed.csv`.
- My scratch scripts are in `C:\Users\igorg\AppData\Local\Temp\claude\3706ee781272b6b6\d90ea535-f05d-4a6f-929d-dbc27318d103\scratchpad\review-ceda\scripts\` (`repro.py`, `fullcmp.py`, `drill.py`, `batch.py`, `k2014.py`, `ki1.py`, `req_scan.py`, `checklist.py`, `groups*.py`, `text.py`, `emb.py`), with outputs in `..\out\`.
