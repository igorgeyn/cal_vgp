Written by a Claude reviewer agent in place of Codex on 2026-11-12, at `phase0-election-status` HEAD `3991b587a7dae616ca461d23db43e7dff4aea2e9`.

# P1b.1b CEDA reconciliation report and P1b.2 design: review

**Verdict on the report: ready with changes.** Its central claim holds and I can make it stronger. The wrong rows date from the July 2025 load. The 17:50:43 stamp belongs to the migration. The April 12 refresh repaired most rows and skipped 157. Every headline count reproduces, both with Fable's tool and with my own independent loader.

I also answered the open question (Q2). The 157 rows were discarded by the table-level `UNIQUE(year, measure_id, data_source)` constraint on the insert path, and the error was swallowed. A simulation of that rule reproduces April 12 exactly.

The report misses one live defect. **Id 4870 was overwritten on April 28, 2026, after the "repair", by the third recurrence path.** That path is reuse of a `MeasID` across CEDA releases. Santa Cruz County's 2016 Measure D is now missing from the database. The report files this row as a one-field "differs".

**Verdict on the design: ready with changes.** Rebuild-and-diff is the right approach. Four things must change before anyone runs it:

1. The strict Layer 1 contradicts step 7 on all 6,169 rows it protects.
2. The reconciliation tool, used as the gate, fails a correct 2014 rekey.
3. The UNIQUE constraint that caused the April skips is not in the plan, and it blocks representing 4870 correctly.
4. Step 1 leaves derived fields from the wrong measure in place.

What I did:
- Read the report, design, tool, tests, the prompt, the prior review and CLAUDE.md.
- Made a backup-API copy of the production DB (source opened `mode=ro`) and queried only the copy. Opened every backup DB `mode=ro`.
- Read raw files only through `python -I` scripts in my scratch folder, with data paths passed as arguments.
- Wrote an independent raw loader (`rawload.py`) and reconciliation (`indep.py`) that share no code with Fable's tool.
- Also reran Fable's tool on my copy. Its `summary.json` (apart from the `db` path) and its `ledger.json` are byte-identical to the committed export.
- Ran the 17 tests (`--basetemp=.pytest-tmp/review-recon`): 17 passed.

Nothing written to any database, no network, nothing committed. Production DB SHA-256 before and after: `ef1359e482db2c54fe41068771932aaac7c9fc1db372e2e1d8cbbed1f505d9da`.

## Reproduction status

| Claim | Status |
|---|---|
| Class counts: 6,169 match / 1,702 format / 521 wrong key / 55 incomplete / 28 wrong row / 1 foreign / 1 differs / 29 missing | **Reproduced** by rerun (identical outputs). **Reproduced independently** for wrong row, wrong key, incomplete, foreign and the 2014 split. |
| 28 wrong rows: 5 in 2000 (SB), 23 in 2011 (LA 16, Santa Clara 4, Fresno 2, Marin 1) | **Reproduced independently.** My loader finds 22 unambiguous by votes. The other 6 (Vernon E-J, which share vote totals) resolve uniquely by stored question. That makes 28, the same id set as Fable's ledger. All 28 have a source row with the same county and letter, later in file order. |
| Stored outcome on the 28: 17 agree / 6 contradict / 5 NULL | **Reproduced.** |
| 2014: 27 own / 521 other / 29 missing | **Reproduced.** |
| 2002 foreign row 9189 | **Reproduced.** Already Mendocino H under `200200001` in the July 2025 backup. |
| 112 flips in the 16 new years; 145 in all 21 files | **Reproduced independently.** |
| `passed` NULL 2000:6, 2005:1, 2011:48, 2018:1 | **Reproduced.** |
| July backup: 9,548 CEDA rows, all `year\|MEASURE_x\|county\|CEDA`, 1,077 with `update_count > 0`, row 6138 holding Vernon's 43/9 | **Reproduced**, plus independent proof (F4). |
| 28 wrong rows identical in July 2025 | **Reproduced** for votes and question. Several other fields have changed since (F9). |
| April 12 repaired 1,049 of 1,077, inserted 1,330, skipped 157 | **Reproduced**, with a two-row nuance (F9). |
| 17:50:43 is `migrate_canonicalize.py` | **Confirmed.** The migration sets `updated_at = CURRENT_TIMESTAMP` (UTC) on every row it rewrites (`f075843b:scraper/scripts/migrate_canonicalize.py:289-294`). The 11:00 a.m. PDT backup already holds the stamp, so it is 10:50:43 PDT. |
| §5 cohorts (SB GO 60/87 to 60/92, etc.) | **Reproduced independently** (Q6). |
| 23 wrong rows have `summary_text` | **Reproduced.** I did not re-derive the 20/23 word-overlap heuristic. |
| §6: DB equals CSV for all 2,520 rows in 2016-2021 | **True as computed, but the scope is silently narrowed** (F1). 2016-2021 holds 2,521 rows, and the excluded one, 4870, does not equal the CSV. |

## Findings, ranked

### F1 (P1): id 4870 is a fourth defect shape, created on April 28, 2026; Santa Cruz County's 2016 Measure D is gone

**Evidence.** I followed id 4870 through the backups:

| Backup | Content of id 4870 |
|---|---|
| July 2025 backup | `201600120`, SANTA CRUZ, **D**, 83,816 to 39,839, Sales Tax, question "In order to: improve children's safety around schools; repair potholes…" |
| `ballot_measures.db.bak.ceda_2015_20260428_142335` | Same. |
| `ballot_measures.db.bak.ceda_2011_20260428_143355` and today | **P**, 8,499 to 2,596, Property Tax, date 2016-11-17. `updated_at` 2026-04-28 14:30:29. Its `last_seen_at` equals the `created_at` of the 119 new 2015 rows. |

- **How it happened.** The April 28 2015 ingest (`ingest_ceda_2015.py` / `ingest_ceda_year.py` → `ingest_measures`) read the 2015 file's 2016 row `201600120`. Its fingerprint, `2016|201600120|SANTA CRUZ|CEDA`, matched exactly, so the update branch overwrote Measure D.
- **Measure D is missing.** `ceda_parsed.csv` line 3878 still has `201600120` as Measure D. No database row now has 83,816/39,839.
- **The row is a hybrid,** like the July rows: `jurisdiction` stayed `1` (D's value), while P's raw `JUR` is 3. That leftover is the only difference the tool reports.
- **The report reads it as trivial.** It calls the row "differs: `jurisdiction` is `1`".
- **§6 drops it from the CSV comparison.** `csv_report` skips rows already reconciled (`reconcile_ceda_raw.py:550`). 2016 shows 871 DB rows against 872 CSV rows, and the 2,520 total omits the one 2016 row that disagrees.

**Impact.**
- **Data.** A real county measure is missing, and a school parcel tax sits under its id.
- **Recurrence.** This is a third way the defect recurs, alongside the report's §4 two, and it has already fired after the April repair. CEDA can reuse a `MeasID` across releases (2002 `200200001` is the other case).
- **Representation.** The table's `UNIQUE(year, measure_id, data_source)` (F3) cannot hold both measures under `201600120`.

**Fix.**
- Add 4870 to the report as its own shape: "overwritten by a cross-release ID collision".
- Widen decision 3 from 9189 alone to the cross-release collisions: 9189 / Strathmore A-02 and Monterey K (2002), and 4870 / Santa Cruz D (2016).
- On id stability: 4870 *was* Measure D for nine months, so restoring D to 4870 and giving P a new row is the id-stable choice. It needs a key scheme that allows two measures with the same `MeasID`.

### F2 (P1, design): strict Layer 1 contradicts step 7 on every protected row

**Evidence.**
- I ran the tool's own `reconcile_year` and counted `match` rows with an empty field. **All 6,169** have `ballot_question` empty, and 6,032 also have `category_topic` empty.
- `classify` (`reconcile_ceda_raw.py:359-365`) only treats empty *core* fields as a problem. An empty question, jurisdiction, topic or title still counts as `match`.
- So §3's "Every compared field equals raw" is not true of any row in the class.
- Design step 7 replaces `ballot_question` on every held-year row and backfills topic. As written, Layer 1 ("the 6,169 matching rows keep identical values in every existing column") fails on all 6,169.

**Fix.**
- Redefine `match` as "no conflicting field; listed fields not loaded".
- Restate Layer 1 as: "on the 6,169 rows, every value that was non-NULL before step 7 is unchanged, except columns on an explicit replace list, which must equal raw byte for byte. NULL to value changes are allowed only in the backfill columns."

### F3 (P1): the skipping branch, and the constraint the design does not mention

The open question is answered in Q2. In short, the 157 were not "missed by matching on spelling". They failed to match on spelling, and the insert that followed then hit `UNIQUE(year, measure_id, data_source)`. The error was swallowed.

The same branch also dropped the 29 2014 members and two 2002 rows (Strathmore A-02 and Monterey K): **188 rows in all**. The report treats those 31 as separate known defects.

**Impact on the design.**
- §2 and step 3 mention "the unique index" (`idx_fingerprint`). The table-level unique key is a second constraint, and the one that actually bit on April 12.
- Step 5 must re-key 9189 *before* inserting Strathmore under `200200001`, or the insert fails.
- 4870 / Santa Cruz D cannot be represented at all under this constraint (F1).
- §5 has no guard against the swallow.

**Fix.** Name both constraints in §2. Order step 5 explicitly. Add the guards in Q7.

### F4 (P2): stronger evidence for the July dating, which the report does not use

- **`measure_updates` is an audit trail of the July load.** It holds 7,929 CEDA field changes on exactly **1,077** distinct row ids, all between 2025-07-31 00:28:28 and 00:28:37 UTC. It is unchanged from the July backup to today.
- **Row 6138 shows the chain step by step.** Azusa (2,250 to 1,059) becomes 1,121 to 4,424, then 675 to 250, then Vernon (43 to 9), with each overwrite's `ballot_question` logged.
- **The fingerprint pins the code.** The July keys come from `f1a6c372`'s regex `Measure\s*([A-Z]+)`, which keeps only the alphabetic prefix of the designation. 249 July rows have a key token that differs from their letter: `R1` and `R3` both key as `R`, `H/J` as `H`. The key was therefore (year, county, *letter prefix*), coarser than "designation". The "never join on (year, county, designation)" rule still holds.
- **Nothing touched CEDA rows between the load and April 12.** `ballot_measures_pre_canonicalize_backup.db` (Apr 7) differs from the July backup only in `topic_primary` (8,327 rows) and new columns.

### F5 (P2): step 1 leaves derived fields from the wrong measure on the restored rows

- **`topic_primary`.** It is set on 153 of the 157 stale rows and on **no other** CEDA row. It was computed from July content, and the April refresh nulled it everywhere it reached. On the wrong rows it describes the sibling. Example: id 6224, a Property Tax measure, has topic "Elections" from a charter question. `generate_site.py` uses `topic_primary` first for `display_topic`.
- **`passed` and `total_votes`.** Step 1 lists "question, votes, percent, `pass_fail`, date" but not `passed`, which waits until step 8. In between, six rows would hold a `passed` that contradicts their own restored `pass_fail`, and the gate would class them "differs". `total_votes` is not named either.
- **Summaries and embeddings.** Step 1 clears `summary_text` and `summary_title` but not `has_summary`. The embedding text and neighbours for the 28 were also built from the wrong content.

**Fix.** Make step 1 set `passed` from the restored `pass_fail` (re-derived in step 8), and restore `total_votes`. Set `topic_primary = NULL` on all 157 and `has_summary = 0` on the 28. Regenerate embeddings for the 28 in step 4.

### F6 (P2, tool as gate): the tool fails a correct 2014 rekey and would hide cross-file ID collisions

- **2014 mode is chosen by header name.** `wrong_key = raws[0]["id_header"].lower() == "measureid"` (`reconcile_ceda_raw.py:398`). In that mode, stored rows are resolved through `Multi_MeasID` groups. I applied the step-3 mapping in memory and reran `reconcile_year`. A **correct** rekey reports `match` 27, `missing_from_raw` **521** and `missing_from_db` **550**. Keyed directly on `MeasureID`, the same rows give `match` 548 and `missing_from_db` 29. The design's gate ("no … wrong key … or missing row") would block a correct repair. Choose the mode from the data (do stored ids match `MeasID` or `Multi_MeasID`?), not the header.
- **Same-ID rows from different files would overwrite each other silently.** `parse_rows` raises on a duplicate `MeasID` within a file. Across files, `reconcile_year` builds `by_id = {raw["id"]: raw …}`, and the last one wins. Step 10 would put a 2016 file's `201600120` next to the 2015 file's (F1). Assert that (YEAR, `MeasID`) is unique across all loaded files.
- **No provenance.** `summary.json` records file names but no SHA-256. For a gate, record each raw file's hash and the tool's own git hash.

### F7 (P2): direct SQL will desynchronise the FTS index

`measure_search` is FTS5 keyed on `fingerprint` with only an `AFTER INSERT` trigger. It has no update trigger. It is in sync today (12,425 of 12,425 fingerprints present). Steps 2 and 3 change fingerprints, and step 7 changes text. `verify_statewide_candidate.py` and `promote_statewide_release.py` compare `measure_search` across releases.

**Fix.** Rebuild or patch `measure_search` rows in the same transaction as each key or text change, and assert that the fingerprint sets agree.

### F8 (P3): the April narrative is incomplete

- **April 12 also moved the question text, not only votes.**
  - **The text was there in 2025.** In the July backup all 9,548 CEDA rows have `ballot_question`.
  - **The 10:53 refresh blanked it.** It used the `f075843b` CSV parser, which reads a `measure_text` column the CSV lacks. That left `ballot_question` NULL on **8,021** rows (title `''`, `category_type` NULL).
  - **The 14:37 run (`cf445606`) wrote the text into `title`.** For 7,068 rows today's `title` equals the July question exactly. The other 952 were overwritten rows, whose `title` now carries the CSV text.
  - **So "fields never loaded" (§3) is wrong.** The text was loaded in 2025 and moved to `title` in 2026. Step 7 should say what happens to `title` once `ballot_question` is restored.
- **April 28 is missing from the timeline.** There are three April 28 events: the 2015 ingest (F1); `patch_ceda_dates.py`, which filled the 143 2011 dates on stale rows, keyed on `measure_id` only (correct values; the vote fields stayed stale); and a `percent_yes` rescale.
- **The CSV ingests did not go through `run_pipeline`.** `scraper_runs` logs only the two 1,478-row runs on the 2022-2024 xlsx files (17:59:55 and 21:51:57 UTC). It has no entry for the 10:53 or 14:37 CSV ingests. The branch is in `ingest_measures` whatever the entry point. "`pipeline.py` ingested" should say "`ingest_measures` was called on".

### F9 (P3): accuracy nits

- **1,049 is right as a count but not as a set.** Rows whose votes changed on April 12 equal the overwritten rows minus the stamped rows, except for two: id 10578, the duplicate 1998 Inglewood D row, which was overwritten but unchanged; and id 8673, which was not overwritten and only rounded 12,065.486.
- **"Exactly as they are today"** holds for votes and question only. County, percent scale, 2011 dates, summaries and `topic_primary` have all changed since.
- **"July 31, 2025" is the UTC date.** In Pacific time the load ran July 30 at 5:28 p.m. The table says so; the bottom line does not.
- **§5 lists San Bernardino Business Tax (11 of 17) "on current cards".** No published card carries an SB Business Tax cohort (checked in the root `measures-data.json`).

## Answers

### 1. Is the July 2025 dating right?

**Yes. Nothing in the backups, git history or timestamps contradicts it, and two sources the report did not use confirm it directly.**

- **Load time.** CEDA `created_at` values span 2025-07-31 00:28:28 to 00:28:37 UTC. The backup is named 18:06 local on July 30, about 38 minutes later.
- **Audit trail.** `measure_updates` logs every July overwrite (F4).
- **Untouched until April.** Votes and questions are unchanged from the July backup to `pre_canonicalize` (Apr 7).
- **Order of events on April 12.**
  - The migration stamp is UTC, 10:50:43 PDT.
  - The CSV inserts are local time, 10:53:36 onward.
  - The 11:00:08 backup holds both.
  - Between April 7 and that backup, the only changes to the 157 stamped rows are `county`, three keys and `updated_at`, which is the migration's footprint.
- **One soft point.** `f1a6c372` (Aug 8) is nine days *after* the load, so the loading code is not in git exactly. The fingerprint shape matches its regex, including the truncation of `R1` to `R`, which makes the attribution sound.

### 2. Which code path skipped the 157 CSV rows?

**The no-match insert branch, failing on the table-level `UNIQUE(year, measure_id, data_source)`. The failure was swallowed as an error count.**

At `f075843b`:
- **Fingerprint.** `check_duplicate` looks up the CSV row's fingerprint, built from the raw county (`2011|201100001|Los Angeles|CEDA`). The stored fingerprint is canonical (`…|LOS ANGELES|…`), so no match.
- **Content hash.** It is the empty-content hash, `7d010443693eec25`: the CSV parser reads a `measure_text` column that does not exist. The check is skipped.
- **Cross-source.** `measure_fingerprint` is also case-sensitive, so no match.
- **Insert.** `ingest_measures` takes `else: db.insert_measure(measure)` (`pipeline.py:344-345`).
- **Failure.** The insert raises `IntegrityError` on `UNIQUE(year, measure_id, data_source)`, which is in the `measures` DDL; `pragma index_info(sqlite_autoindex_measures_1)` gives year, measure_id, data_source. `operations.py:185-188` converts that to `DuplicateError`. The outer `except Exception` at `pipeline.py:348-350` catches it and does only `stats["errors"] += 1` plus a log line.
- **`cf445606` (14:37 run).** Same code path, same 157 rows.
- **Today.** Same structure at `pipeline.py:350` and `:353-354`.

**Verification.** I simulated this rule in memory over all 10,909 CSV rows: canonical stored keys after the migration, raw CSV keys, and in-parser deduplication on fingerprint. The prediction is **9,391 updates (9,391 distinct rows), 1,330 inserts and 188 UNIQUE failures**. That equals the observed 9,391 refreshed, 1,330 inserted (ids 10969-12298) and exactly the 157 unrefreshed rows, plus 31 more:

- the 29 2014 multi-county members, whose CSV ids are the shared `Multi_MeasID`;
- 2002 `200200001` TULARE (Strathmore A-02), blocked by 9189;
- 2002 `200200002` MONTEREY (Monterey K), blocked by Butte B.

So one mechanism accounts for the stale 157, the 29 missing 2014 members and the missing Strathmore A-02. The report should merge them.

### 3. Is the classification sound?

**For the counts, yes. Three definitions need tightening before the tool becomes a gate.**

- **`match` is too lenient in what it implies, not in what it detects** (F2). Every match row has an empty question.
- **"Format only" is acceptable** for county canonicalisation (186 rows), fractional votes (1) and case (1). One part of it hides a display defect: **1,597 rows differ only by the placeholder title** `"<COUNTY> Measure <LTR>"`. They are 2015, 2022-2024 and the 29 inserted 2011 rows, and their cards show the placeholder where the question should be. Keep the class, but list it as a display defect for P1b.2.
- **The 0.01 tolerance is fine.** It is absolute, in percentage points, after scaling raw by 100.
- **`incomplete` is a reasonable home but understates the effect.** 46 of the 55 have a populated `pass_fail` and a NULL `passed`, which is a derivation gap and not missing source data. Those NULLs remove rows from the live cohorts. I would rename it "outcome or date not derived" and count it as user-visible.
- **The real gap is `differs`.** It cannot see content that came from another year's file or another release when the votes still equal the raw row under the same `MeasID`. That is why 4870 (F1) is called a jurisdiction difference. Cross-check every `differs` row against the July backup and the CSV before calling it minor.

### 4. Do the reproduced counts hold?

**Yes, all of them:** 28 wrong rows; 2014's 27/521/29; the 2002 foreign row; 112 flips in the 16 new years (145 in all); 55 `passed` NULLs in 2000/2005/2011 plus 1 in 2018.

Tool rerun: same outputs (Reproduction status). Independent loader: same 28 ids, same 112/145 by year, same NULL counts, and 14 NULL dates (2000: 11, 2005: 2, 2009: 1).

### 5. Is the 2016-2021 evidence (§6) stated at the right strength?

**Mostly. Two qualifications are missing:**

- **It is 2,520 of 2,521 rows.** The excluded row, 4870, disagrees with the CSV and is a known overwrite (F1).
- **DB equals CSV tests ingest fidelity, not source correctness.** The CSV's release lineage differs from the archive in at least two places: 2002 `200200001`/`200200002`, and 2016 `201600120` against the 2015 file.

What the evidence does support:

- **CSV agrees with raw everywhere both exist.** On 7,836 of 7,836 matchable held rows it agrees on votes and `pass_fail`. The 669 unmatched are 2015 (no CSV rows) and the 550 re-keyed 2014 rows.
- **No 2014-style keying in 2016-2021.** Distinct ids equal rows in both the CSV and the DB.
- **No 2016-2021 row was left stale.** By the Q2 mechanism, a stale row would need a (year, id) collision with a different county spelling; none carries the stamp.

Suggested wording: "Good evidence that the 2016-2021 rows equal the CSV and were not left stale. No evidence that the CSV equals the current release. One known overwrite (4870)."

### 6. Live-card effect: San Bernardino GO Bond

**Reproduced exactly from `local_measure_context.py`'s rules.** I reimplemented them: active rows, not `*_County_Registrar`, `passed` in {0, 1}, stored county casefolded, reviewed category, year < 2026. My stored figures match all 12 cohorts on the published root `measures-data.json` (SB GO 60/87 on 7 cards).

Raw scenario: per-row `PASSFAIL` for CEDA rows in held years, 2014 held constant, canonical county.

| Cohort | Stored | Raw per-row | Raw combined (`passfail_sum`) |
|---|---|---|---|
| SB GO Bond | 60/87 (69%) | **60/92 (65%)** | 63/92 (68%) |
| SB Property Tax | 3/15 | 3/17 | 3/17 |
| SB Sales Tax / TOT / Ordinance | 17/30, 12/16, 40/70 | 18/31, 13/17, 40/71 | same |
| San Mateo Property Tax | 76/105 | 81/111 | 81/111 |
| San Mateo GO Bond | 89/102 | 90/105 | 90/105 |

- **What adds the five SB GO rows.** They are ids 10015, 10017, 10018 (`FailT`, `passed` NULL) and 12113, 12114 (`SAN BERNADINO`), as the report says. Raw `RECTYPENAME` equals the stored `category_type` on every CEDA row used.
- **The combined column matters for the final number.** It suggests the completion plan's eventual figure is about 68%, not 71% (2014 still held constant).

### 7. The design

**Rebuild-and-diff is right.** The order is mostly safe. Restoring the 157 before the 2014 rekey is safe: the two sets cover disjoint years, and step 1 changes no key column. Required changes:

1. **Layer 1** (F2): restate as described there.
2. **Step 1** (F5): add `passed`, `total_votes` and `topic_primary = NULL` (all 157), and `has_summary = 0` (the 28). Regenerate the 28 rows' embeddings.
3. **Constraints** (F3): name `UNIQUE(year, measure_id, data_source)` with `idx_fingerprint`.
   - **Step 3:** the two-phase `REMAP:<id>` handles both constraints. Assert both after phase 2.
   - **Step 5:** re-key 9189 first, then insert.
   - **4870:** cannot be fixed without a key-scheme decision (F1).
4. **Step 2** recomputes fingerprints. State it, and update FTS (F7).
5. **Audit:** log every changed value to the existing `measure_updates` table with `update_source = 'P1b.2-step<N>'`. That table is what made the July dating provable. Decide whether to touch `updated_at` at all; the forensics in this report depended on it.
6. **Gate** (F6): fix the 2014 mode and the cross-file ID check before step 3 relies on the tool.
7. **Decision 3:** widen it to Mendocino H, Monterey K and Santa Cruz D/P (F1).
8. **Step 7:** state what `title` becomes once `ballot_question` is restored (F8).

**Missing from the recurrence guards (§5):**

- **Fail closed on errors.** `ingest_measures` must abort and roll back on any exception or `IntegrityError`, and the caller must assert `inserted + updated + duplicate == len(input)`. The swallow at `pipeline.py:353-354` dropped 188 rows silently. That is the root of the "skip".
- **Identity check before an exact-fingerprint update.** Refuse the update when the incoming county, letter or place differs from the stored row's (F1). Cross-release `MeasID` reuse turns an exact match into an overwrite.
- **Retire the side paths.** Retire `ceda_parsed.csv` as an ingest source and remove `run_ceda`'s processed-CSV fallback (`pipeline.py:144-151`). Route or retire `ingest_ceda_year.py`, `ingest_ceda_2015.py` and `patch_ceda_dates.py`; the last keys on `measure_id` without `year`.
- **Assert raw (YEAR, `MeasID`) is unique across all loaded files** before any ingest.
- **Keep the July lesson:** the parser must never build a key from the title. §5 has this.

### 8. Is anything in the tool unsafe to reuse as P1b.2's gate?

Yes, five things, ranked:

1. **The header-selected 2014 mode** fails a correct rekey with 521 + 550 false misses (F6).
2. **Last-wins `by_id`** across files hides collisions of the same `MeasID` (F6).
3. **`match` passes empty non-core fields,** and `csv_report` excludes reconciled ids. Neither should feed a strict invariant without a change (F2, F1).
4. **`differs` cannot see cross-release overwrites** (F1, Q3).
5. **No raw-file hashes or tool version** in `summary.json` (F6).

The read-only contract is sound: every connection is `mode=ro`, the DB hash is checked before and after, and the exit code is 2 on any change. `map_headers` fails loudly on missing headers. The tests cover normalization, sheet choice, the classes and the read-only path. They do not cover a post-rekey 2014, cross-file duplicate IDs, or a stray-year row.

## Not verified

- The 20-of-23 summary heuristic (not re-derived).
- Why `county` on the 29 2011 rows inserted April 12 is upper-case while their fingerprints are not. Something between 10:53 and 11:00 upper-cased the county column without touching the keys. It does not affect Q2.
- Whether Santa Cruz County's 2016 Measure D and Measure P both appear in the current Esploro 2016 release (no network). The CSV and the 2015 file disagree on `201600120`.
- Anything needing the network; 2016-2021 against raw.

My scratch scripts are in `C:\Users\igorg\AppData\Local\Temp\claude\3706ee781272b6b6\d90ea535-f05d-4a6f-929d-dbc27318d103\scratchpad\review-recon\scripts\`:
- `rawload.py`, `indep.py`, `amb.py`: independent reconciliation
- `chain.py`, `diffdb.py`, `repair.py`, `odd.py`, `incr.py`: the backup chain
- `july.py`: July fingerprints
- `simulate_apr12.py`: Q2
- `bqwipe.py`, `bqmove.py`: F8
- `cohort.py`, `cards.py`: Q6
- `gate_after_rekey.py`, `matchempty.py`, `fmt.py`: tool as gate

Outputs are in `..\out\` (`fable_rerun\` holds the tool rerun).
