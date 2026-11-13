# P1b.2 design: repair the CEDA history

**Date:** November 12, 2026. **By:** Fable. **Revised** the same day for the
[review](../codex/p1b_1b_reconciliation_review_response.md) and Igor's five decisions.
**Status:** ready for a final check; nothing here has been run, and no step writes to the
production database. **Evidence:** [reconciliation report](ceda_reconciliation_20261112.md).

## 1. Decisions (answered November 12)

| # | Decision | Answer | Effect here |
|---|---|---|---|
| 1 | Rebuild-and-diff or patch | **Rebuild and diff** | §3 |
| 2 | The 29 wrong records, live now | A separate small release flags them | Not in this design; step 2 later replaces the flag |
| 3 | Id 9189 (2002) | Leave until the current CEDA release is downloaded | The two 2002 measures stay as they are; the gate waives them (§9) |
| 4 | Multi-county measures | One row per measure, plus a shared group key | §5 |
| 5 | Changed pass rates | A list in P1b.3 is enough | Steps write lists A and B |

New questions these raise are in §12.

## 2. Rules for every step

- **Keep every `id`.** No step deletes or reuses one. New measures get new ids.
- **Do not go through `ingest_measures` or `Database.update_measure`.** They recompute keys,
  refuse to overwrite a non-empty field and swallow errors. Use direct SQL keyed on `id`,
  from a reviewed mapping file (`id`, year, `MeasID`, source file, SHA-256, sheet, row).
- **One transaction per step**, with its assertions inside it and its own changed-row list.
- **Log every changed value** to the existing `measure_updates` table, with
  `update_source = 'P1b.2-step<N>'`. That table is what proved the July dating.
- **Leave `updated_at`, `update_count` and `last_seen_at` alone.** They are evidence.
- **Never join or update on (year, county, designation).**
- **Rebuild the search index at the end of every step** (§7).

## 3. What may change, column by column (Layer 1)

This replaces the earlier "identical values in every existing column", which contradicted
the backfill. It applies to **every CEDA row that is not on a step's named change list**,
including the 6,169 rows with no conflict today.

| Group | Columns | Rule |
|---|---|---|
| **Protected** | `id`, `measure_id`, `year`, `county`, `measure_letter`, `title`, `election_date`, `yes_votes`, `no_votes`, `total_votes`, `percent_yes`, `percent_no`, `pass_fail`, `category_type`, `measure_type`, `election_type`, summaries, `topic_primary`, `fingerprint`, `measure_fingerprint`, timestamps, and every column not named below | Byte-identical before and after |
| **Fill only** | `ballot_question`, `jurisdiction`, `category_topic` | Empty may become the raw value. A value already present must equal raw, and stays |
| **Derived** | `content_hash` | Recomputed with the formula in `models.py:140-147` wherever `ballot_question` was filled |
| **Outcome** | `passed` | Protected through step 7. Step 8 may change it, only on rows in list B |
| **New** | The columns added in §4 and §5 | Set freely |

`title` is protected on purpose. Today it holds the question text on about 7,000 rows and a
placeholder on 1,755. Changing it would change thousands of pages, so it is left for the
page diff in P1b.3 to judge (§12, question 4).

## 4. The unique rule

**Today.** The production table carries `UNIQUE(year, measure_id, data_source)`. It is a
table constraint from an older build: **the current code does not declare it**
(`models.py:258-262` declares `fingerprint TEXT UNIQUE` instead), so a database built from
today's code has a different schema from production. The rule cannot hold two measures
that share a CEDA ID, such as Santa Cruz's Measure D and Measure P under `201600120`.

**Change.**
- Add `source_variant TEXT NOT NULL DEFAULT ''`. It is empty on every existing row. It is
  set only on the second measure to share a source ID, to that measure's designation
  (for example `D`).
- Replace the rule with `UNIQUE(year, measure_id, data_source, source_variant)`.
- The fingerprint's identifier becomes `measure_id`, plus `~<variant>` when the variant is
  not empty. Every existing fingerprint is therefore unchanged. The change is made in
  `BallotMeasure.extract_measure_identifier` (`models.py:150-153`) and its copy in
  `migrate_canonicalize.py:106-109`, so a later `update_measure` recomputes the same value.
- Put the new rule in `models.py` as well, so code and production agree again.

**Migration, on a copy.** SQLite cannot alter a table constraint, so the table is rebuilt:
1. `PRAGMA foreign_keys = OFF`; begin.
2. Create `measures_new` from the stored definition, with the new column and rule.
3. Copy every row with an explicit column list, ids included.
4. Drop `measures`; rename `measures_new` to `measures`.
5. Recreate the nine indexes, the `measure_search_insert` trigger and the views, from their
   stored definitions: first `active_measures`, `decade_summary` and `topic_analysis`, which
   read `measures`, then `measure_stats` and `data_quality`, which read `active_measures`.
6. Rebuild `measure_search` (§7). Commit. `PRAGMA foreign_keys = ON`.

**Assertions.** Row count, the set of ids, `sqlite_sequence` and a per-row hash of every
old column are identical. `PRAGMA integrity_check` and `foreign_key_check` are clean. The
four tables that reference `measures` (`measure_topics`, `measure_updates`,
`measure_documents`, `statewide_ballot_entries`) still resolve.

**What depends on it.**
- **Consumers keyed on `measure_id` alone** would see two rows for `201600120`:
  `generate_site.py:221-222` (research fallback), `:332-341` and
  `scraper/data/embedding_metadata.json` (similar measures), `generator.py:15075-15080`
  (recommendations) and `patch_ceda_dates.py`. Each must key on `id`, or on `measure_id`
  plus `source_variant`, in the same change.
- `operations.py:185-188`, which turns any unique failure into "already exists".
- `verify_statewide_candidate.py` and `promote_statewide_release.py`, which compare schemas
  and the search index between releases; their expected schema changes once.
- Tests that create a database, and the registrar loader's cross-source check.

## 5. Multi-county measures (decision 4)

My reading of "one row per measure, plus a shared group key", to be confirmed (§12,
question 1):

- **Every county's row stays**, with its id and its page. Its vote columns keep that
  county's votes, so they are Protected.
- **New `multi_measure_id`**, `CEDA:<year>:<Multi_MeasID>`, on every member of a
  `Multi_CO=1` group. In the 21 held files that is 606 rows in 265 groups.
- **New `counts_as_measure`**, 1 on exactly one member of each group (the one with the most
  votes; ties go to the lowest id) and on every single-county row. This is the "one row
  per measure": statewide counts use it, so a measure counts once.
- **New combined columns** on every member: `combined_yes_votes`, `combined_no_votes`,
  `combined_total_votes`, `combined_percent_yes`, `combined_pass_fail`.
- **`passed` becomes the measure's outcome** (step 8). A county history counts each member
  in its own county, with the combined outcome. That is the 63 of 92 in the report's §5.

This does not need the unique rule to change: after the 2014 rekey each county share has
its own `MeasureID`. Santa Cruz does need it.

## 6. Steps, all on a database copy

| # | Step | Rows | Assertions |
|---|---|---|---|
| 0 | Baseline: backup-API copy; per-row hash of every column; counts per year | 10,997 | Hashes recorded |
| 1 | **Schema** (§4, §5): rebuild the table with the new rule; add the new columns | All | §4's list |
| 2 | **Restore the 157 stale rows from raw.** Set question (replace, not fill), `yes_votes`, `no_votes`, `total_votes`, `percent_yes`, `pass_fail`, `election_date`, and `passed` from the restored `pass_fail`. Clear `topic_primary` on all 157: it was computed from 2025 content and exists on no other CEDA row. On the 28 wrong rows also clear `summary_text` and `summary_title` and set `has_summary = 0`. Set `election_type` by the existing date rule on the 14 rows that gain a date. Recompute `content_hash`. | 157 | Tool reports 0 wrong rows and 0 incomplete in 2000, 2005, 2009, 2011; list A written |
| 3 | Canonical county on the 5 `SAN BERNADINO` rows, raw spelling kept in `ceda_county_raw`; recompute their two fingerprints. Remove the special case at `generate_site.py:243-246` in the same change. | 5 | Both unique rules hold |
| 4 | **2014 rekey, two phases:** key each 2014 row as `REMAP:<id>`, then as its `MeasureID`. Recompute `fingerprint` and `measure_fingerprint`. | 548 (521 change) | Mapping one-to-one; only three columns change; both unique rules hold; ids identical; tool reports `key_mode: own`, 548 rows clean and the 29 shares still missing |
| 5 | Insert the 29 missing 2014 county shares as new rows, `counts_as_measure = 0`. Set `multi_measure_id`, `counts_as_measure` and the combined columns on all 606 member rows. | 29 new, 606 set | One counting row per group; combined values equal the file's `*_sum` fields; statewide count of 2014 measures unchanged |
| 6 | **Santa Cruz 2016** (§12, questions 2 and 3): correct id 4870's leftover `jurisdiction`; insert Measure D as a new row with `source_variant = 'D'`, from `ceda_parsed.csv`, marked unverified. | 1 changed, 1 new | Both measures stored; release conflict for `201600120` gone |
| 7 | **Backfill**: fill `ballot_question`, `jurisdiction`, `category_topic`; set `place_name`, `jurisdiction_kind`, `ceda_req`, `required_vote`, `required_vote_basis`; write provenance | 8,506 | **Layer 1 (§3) on every row not listed in steps 2-6** |
| 8 | **Outcome rule** (§8): `passed` from the combined result on multi-county rows | Up to 140 | List B written; the 5 single-county conflicts untouched |
| 9 | Regenerate embeddings and neighbours for the 28 restored rows, 4870, the new rows and all of 2014; rekey `embedding_metadata.json`. Mark `ceda_parsed.csv` superseded. Update `KNOWN_ISSUES` #1 and #5 and add the loader defect. | | No artifact holds an old 2014 key |
| 10 | 2016-2021, when Igor has the files: §10, then the same steps, plus a cell diff of archive against Esploro | 2,521 | |

**Verification.** Layer 2: rows per year equal the raw files, plus the named exceptions.
Layer 3: traces for San Joaquin Delta K, Azusa A and Vernon A, Rim of the World I, Kern
Community College G, Santa Cruz D and P, and one 2014 group. Then the gate (§9).

## 7. The search index

`measure_search` is an FTS5 table over `measures` with only an insert trigger. Direct
updates leave it stale, and it indexes `ballot_question`, `title`, summaries and county.

- **At the end of every step's transaction:**
  `INSERT INTO measure_search(measure_search) VALUES('rebuild')`.
- **Check:** `measure_search` row count equals `measures`; the two fingerprint sets are
  equal; `VALUES('integrity-check')` passes; a search for a phrase from one restored
  question (Azusa's ordinance) returns id 6138, and Vernon's charter phrase no longer does.
- Add update and delete triggers in the same change, so the next direct update cannot
  leave it stale.

## 8. Thresholds and outcomes

- **`REQ` is unsafe to map straight to `required_vote`.** Store it raw as `ceda_req`.
  Derive `required_vote` only by rule, with a `required_vote_basis`, and leave it NULL
  where no rule applies. Known traps: no `F` code exists before 2002; 2001 Proposition 39
  bonds are coded `M`; some later ones are coded `T`.
- **Never compute pass or fail from `REQ`.** Use CEDA's outcome fields.
- **Outcome rule.** On a `Multi_CO=1` row, `passed` is the combined result
  (`passfail_sum`). On any other row it is the row's own `PASSFAIL`. In the held files the
  two differ on 145 rows: 140 are multi-county and change; **5 are single-county and are
  held out** for Igor, with the KNOWN_ISSUES #1 records and 2014 `201400551`.
- **KNOWN_ISSUES #1, proposed wording:** "For five school bonds, CEDA's per-county and
  combined outcomes conflict. `REQ=T` is probably a miscoding of 55% Proposition 39 bonds,
  which would make the per-county 'Pass' correct. Held out of automatic outcome changes
  until checked against county or Secretary of State records. Keyed by `measure_id`; the
  row ids listed before November 2026 were stale."

## 9. The gate

`reconcile_ceda_raw.py --gate` must exit 0 after step 9, run as:

```text
python -I scripts/reconcile_ceda_raw.py --db <copy> --out <folder> --gate ^
  --csv data/processed/ceda_parsed.csv --baseline-db <step 0 copy> ^
  --waive 2002:200200001,2002:200200002,2016:201600120
```

- The two 2002 waivers are decision 3. They cover id 9189, Strathmore A-02 and Monterey K.
- The 2016 waiver covers Measure D only until the 2016 file is in hand: until then D has
  no raw row to be checked against.
- `summary.json` records each raw file's SHA-256 and the tool's own, and echoes the
  waivers. The tool now picks 2014's mode from the data, so a correct rekey reports clean.

## 10. New files: collisions before any load

For the 2016-2021 files, and any re-download:

1. **Run the tool first, with the new files beside the held ones.** `repeated_ids` (one ID
   on two raw rows) and `release_conflicts` (one ID naming different measures in the files
   and in what we store) must each be empty, or each entry resolved by a recorded decision.
2. **Resolve a collision by keeping both measures**: the one already stored keeps its row;
   the other is inserted with `source_variant` set. Never by letting one replace the other.
3. **Check the ID column.** The loader raises if it is missing (§11).
4. Only then load, through the P1b.2 loader, not `ingest_measures`.

## 11. Stopping it recurring

**Parser**
- An explicit header map with exact, case-insensitive names; `HEADER_ALIASES` in the tool
  is the tested starting point. Raise when the ID column is missing.
- Remove the substring fallback (`ceda.py:268-273`) and the in-file dedup (`:374-384`).
- Canonicalize the county before any key is built. Never derive a CEDA key from the title.

**Ingest** (`pipeline.py`)
- **Fail closed.** `ingest_measures` catches every exception and only counts it
  (`pipeline.py:353-355`); that dropped 188 rows unseen. It must roll back and raise, and
  the caller must assert `inserted + updated + duplicate == len(input)`.
- **Check identity before an exact-key update.** Refuse it when the incoming county,
  designation or place differs from the stored row's. This is the check that would have
  saved Measure D.
- **Assert (YEAR, `MeasID`) is unique** across all files loaded together.

**Side paths**
- Retire `ceda_parsed.csv` as a source, and `run_ceda`'s fallback to it (`pipeline.py:144-151`).
- Retire or reroute `ingest_ceda_year.py`, `ingest_ceda_2015.py` and `patch_ceda_dates.py`;
  the last keys on `measure_id` without the year.

**Schema**
- One definition of the `measures` table, in code, equal to production (§4).

## 12. New questions for Igor

1. **Is my reading of decision 4 right** (§5)? County rows stay as pages, one of them
   counts, and all carry the combined result. The alternative is to merge a multi-county
   measure into a single page, which retires ids.
2. **Which measure keeps id 4870?** The review suggests returning it to Measure D, which
   held it in the database until April. I recommend leaving it with Measure P:
   `measures/4870.html` was first published on July 2, 2026 and has only ever shown P, so
   no public address changes meaning. D then returns as a new row.
3. **Restore Measure D now or with the Esploro file?** D's only sources today are
   `ceda_parsed.csv` and the July 2025 backup. Decision 3 waits for Esploro in the similar
   2002 case. I recommend restoring D now, marked unverified, because a real county measure
   is missing from the site; say if you would rather wait.
4. **`title`.** Leave it untouched and let P1b.3's page diff show the effect (my
   recommendation), or decide now what the 1,755 placeholder titles should become?
5. **A cheaper form of the key change, if you prefer it.** Instead of rebuilding the table,
   give the second measure a qualified `measure_id` (`201600120~D`), as the 2026
   propositions already use year-qualified keys. It avoids the rebuild and every consumer
   change in §4, at the cost of a `measure_id` that is no longer CEDA's own. I have
   specified the rebuild, as decided; this is the fallback if it proves too invasive.

## 13. Size

About 3 days of agent work for steps 0-9 on a copy (the schema change adds one), plus
roughly an hour of Igor's time on lists A and B. Step 10 waits on the downloads.
