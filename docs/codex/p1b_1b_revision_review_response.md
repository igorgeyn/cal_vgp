Written by a Claude reviewer agent in place of Codex on 2026-11-12, at `phase0-election-status` HEAD `5e79c950ddacaefbea55e67a15e4d35446536099`. The four reviewed files are byte-identical to `e89592c7`; the only later commit touches the checklist.

# P1b.1b revision (e89592c7): re-review

**Verdict: report ready. Tool and design ready with changes; do not run P1b.2 against this gate yet.**

The report now matches the evidence. All nine earlier findings are addressed, most of them fully. The 2014 mode fix works: a correct rekey reports clean, and today's state still reports 27/521/29. Cross-file ID collisions are now reported, never overwritten. Raw-file and tool hashes are recorded.

Two problems remain in the gate:

- **It cannot pass after the designed repair.** Step 8 writes the combined outcome into `passed`, and the tool then classes 140 correct rows as "differs".
- **The §9 waivers are too broad.** They make the gate clean whether or not Measure D is restored, and even if id 4870 is overwritten again.

The schema migration in §4 fails as written, and the search-index checks in §7 cannot detect a stale index. Today's index is already stale. The earlier review's "in sync" claim used the same check that cannot fail, so that claim was wrong.

## Disposition of the earlier findings

| # | Finding | Status | Evidence |
|---|---|---|---|
| F1 | Id 4870 overwritten; Measure D missing | **Resolved**, one wording issue | Report §1.6, §3, §4 and §6 now cover it. The tool classes 4870 as `id_reused` (rerun: `class_before_id_check: differs`, `baseline_identity: SANTA CRUZ D`). Decision 3 is widened. Design step 6 restores D. The 2002 pair is described the wrong way (N9). |
| F2 | Strict Layer 1 contradicted step 7 | **Resolved** | Design §3 sets column classes: protected, fill only, derived, outcome, new. I checked the fill-only columns against raw. Every stored `ballot_question`, `jurisdiction` and `category_topic` equals raw byte for byte, except 28 `ballot_question` values (the wrong rows, step 2) and 1 `jurisdiction` (4870, step 6). So "a value already present must equal raw" holds today. The tool now reports `unloaded_fields` separately. |
| F3 | The unique rule and the swallowed insert | **Resolved** | Report §1.4 and §4 explain all 188 dropped rows with one mechanism. Design §4 changes the rule. Design §11 makes the ingest fail closed and assert the counts. |
| F4 | `measure_updates` / July key evidence | **Resolved** | Report §1.2 and the §4 table: 7,929 changes on 1,077 rows, row 6138's chain, the `Measure\s*([A-Z]+)` prefix and 249 keys. |
| F5 | Step 1 left derived fields stale | **Resolved** | Step 2 now restores `passed` and `total_votes`, clears `topic_primary` on all 157 rows, sets `has_summary = 0` on the 28, sets `election_type` on the 14 rows that gain a date, recomputes `content_hash`, and regenerates embeddings in step 9. On the 28 rows I found no other populated derived column (`generated_title`, research and briefing columns are all empty). |
| F6 | Tool as the gate | **Partly resolved** | The 2014 mode is now chosen from the data (verified, Q2). Repeated IDs are kept as lists and reported (`repeated_ids`, `id_collision`). Raw and tool SHA-256 are recorded. New gate defects: N1, N2, N3, N8. |
| F7 | FTS desync | **Partly resolved** | There is now a rebuild per step and a plan for update and delete triggers, but the planned checks cannot detect staleness (N5). |
| F8 | April narrative | **Resolved** | The 8,021/8,020 blanking, the `title` move (I reproduced 6,992 exact matches against the July question), April 28, and the missing `scraper_runs` entry. |
| F9 | Nits | **Resolved** | The 1,049 edge rows, "exactly as today", Pacific vs UTC time, and the SB Business Tax card claim. |

## New findings, ranked

### N1 (P1): the gate fails a correct step 8, so §9's "must exit 0 after step 9" cannot happen

`compare_row` checks `passed` against the row's own `PASSFAIL` (`reconcile_ceda_raw.py:360-364`). Step 8 sets `passed` from `passfail_sum` on multi-county rows.

I simulated the full design in memory: restore the 157, canonicalise SB, rekey 2014, insert the 29 shares, fix 4870 and insert D, fill step 7.

- **Without step 8:** with the §9 flags and waivers, the gate is clean.
- **With step 8:** it changes `passed` on exactly 140 rows, and the gate reports `blocking: {differs: 140}`, 13 of them in 2014.

**Display problem with the same step.** After step 8 the row keeps the county share's votes as its own votes, while `passed` holds the district result. Today's cards and pages would then show, for example, San Bernardino's 45% share of Kern Community College G next to "Passed", with no label.

The layout review (answer 2) asks for the opposite:
- a "Combined district result" shown first;
- the county row labelled as a portion;
- "a county portion never gets its own measure-wide Passed/Failed badge."

**Fix:** pick one of these.
- **(a)** Keep `passed` as the row's own outcome. Add `combined_passed` (or use `combined_pass_fail`). Point the cohort code and the future result display at it.
- **(b)** If `passed` is overwritten, the tool must apply the same outcome rule. The card and page change must also land in the same commit (the CLAUDE.md atomic-flip rule).

I recommend (a). It keeps the tool's check simple and leaves the UI's combined/portion presentation to P1b.3 and Phase 2.

### N2 (P1): the §9 waivers switch off every check on the IDs the repair is about

A waiver is a (year, `MeasID`) pair. It suppresses every class on every row with that key, plus the matching release conflict and repeated-ID entries (`reconcile_ceda_raw.py:940-948`). Simulated with the exact §9 command (step-0 copy as baseline, CSV, three waivers):

| State after repair | Gate |
|---|---|
| Correct repair | clean |
| **Measure D never inserted** | **clean** |
| **4870 overwritten back to D, so P is lost** | **clean** |
| **Butte B (id 9045, a correct row today) votes changed by 5,000** | **clean** (hidden by `2002:200200002`) |
| Same Butte B and 4870 damage, no waivers | blocks: `differs 1`, `foreign 2`, `missing_from_raw 1`, 2 conflicts |

- **Unused or wrong waivers.** A waiver that matches nothing (`2019:1`) is accepted silently.
- **Formatting slips fail closed,** which is fine. A trailing space means the waiver is not applied.

**Fix:**
- A waiver should name the year, the `MeasID`, the class and the stored `id` (or the raw identity for `missing_from_db`).
- `summary.json` should list each suppressed entry.
- The gate should fail on a waiver that matches nothing.
- For 2016 the waiver should cover only "D has no raw row" (`missing_from_raw` on D's new `id`). The gate must still require that P matches raw and that both identities are stored.

### N3 (P2): the gate's strength depends on optional flags

`--gate` does not require `--csv` or `--baseline-db`. Without them, `release_conflicts` and `id_reused` are never computed. In that case, with D never restored, the gate is clean with the waivers. Without waivers it blocks only on 9189.

§9 does pass both flags, but nothing enforces it. **Fix:** `--gate` should refuse to run without both flags, and should record the CSV's and the baseline's SHA-256.

### N4 (P2): the §4 table rebuild fails as written

I replayed §4 on an in-memory backup-API copy of production (SQLite 3.45.3, `legacy_alter_table = 0`):

1. Created `measures_new`, copied the rows, and dropped `measures`.
2. `ALTER TABLE measures_new RENAME TO measures` then fails: **`error in view decade_summary: no such table: main.measures`**. Dropping `measures` leaves its five views dangling, and RENAME re-parses them.
3. After `DROP VIEW` on all five, the rename succeeds.
4. Everything else in §4 then held:
   - the nine indexes and the trigger were recreated;
   - `sqlite_sequence` stayed 12477, because max(id) equals seq;
   - `foreign_key_check` and `integrity_check` were clean;
   - the new autoindex is (year, measure_id, data_source, source_variant).

The step runs in one transaction, so the failure rolls back safely, but the procedure needs this step: **drop the five views before the DROP TABLE.** Also:
- The new update and delete triggers must name `rowid = old.id / new.id` explicitly. The existing insert trigger omits the rowid and is aligned with `id` only by luck. My test insert got FTS rowid 12478 = id 12478.
- They must be created only after the rebuild. Feeding `'delete'` with values the index does not hold corrupts an external-content index.

### N5 (P2): §7's search-index checks cannot fail; today's index is already stale

`measure_search` is `content='measures', content_rowid='id'`, so a SELECT on it reads `measures`. Results on the in-memory copy:

| Check | Result |
|---|---|
| Row count equals `measures` | 12,425 = 12,425 (always true) |
| Fingerprint sets equal | True (always true) |
| `VALUES('integrity-check')` | OK |
| **`(measure_search, rank) VALUES('integrity-check', 1)`** | **`database disk image is malformed`**: the index does not match its content table today |
| After `'rebuild'` | the rank-1 check passes |

The first review's "in sync today (12,425 of 12,425)" used the first, always-true check and was wrong. `promote_statewide_release.py:36-38` already documents this trap.

The "Vernon's phrase no longer returns 6138" check is also already true today: the stored-question phrase returns nothing. Only the positive phrase check can tell a stale index from a fresh one.

**Fix:**
- Use `integrity-check` with rank 1.
- Compare `fts5vocab` term counts against a fresh rebuild.
- Keep only positive phrase checks.

### N6 (P2): "marked unverified" has no mechanism

Decision 3 (9189) and step 6 (Measure D) both rely on an "unverified" mark. No column, value or display rule for it appears in §3-§5, and nothing in `scraper/` implements one. Specify it before step 6, for example a `verification_status` column with a fixed vocabulary that cards and pages render. Without that, D appears as an ordinary row.

### N7 (P2): measure_id-keyed artifacts after the 2014 rekey; the consumer list is incomplete

- **Old keys become new keys.** 502 of the 521 changed 2014 keys become *another row's* new `MeasureID`.
- **The embeddings are affected.** `embedding_metadata.json` holds 577 2014 keys (548 distinct). 529 of them are still valid keys after the rekey, but they point at different measures.
- **The step 9 check cannot work.** "No artifact holds an old 2014 key" cannot be checked by key value.
- **The file already has duplicate keys.** It holds 57 duplicate `measure_id`s (for example `200200001`, `200200002` and 2014 group keys).

**Fix:**
- Key embeddings and neighbours by `id`.
- Regenerate them rather than rekeying in place.
- Check that every embedding key is a live `id` and the keys are unique.

**Consumers keyed on `measure_id` that §4 misses:**
- `generate_embeddings.py:118-145`, the producer of the file;
- `generate_insights.py:1563-1568`, where the first row wins;
- `generator.py`'s JS `allMeasures.find(m => m.measure_id === rec.measure_id)`, next to the cited `recommendations[measure.measure_id]`;
- the BallotMeasure dataclass and `generate_site.py`'s `valid_fields`, if `source_variant` is to reach `measures-data.json` (CLAUDE.md hard rule).

### N8 (P3): the gate passes a measure stored twice under one ID when the copy carries a variant

Once two stored rows share an ID, each is matched by county and designation only (`reconcile_ceda_raw.py:465-487`). A synthetic test with the same measure stored twice (the second with `source_variant`) gives `{'match': 3}` and no defect.

The new UNIQUE rule and `idx_fingerprint` block same-variant duplicates, and Layer 2's row counts would catch the rest. Still, the gate should assert that each raw row is represented at most once.

### N9 (P3): the 2002 pair is a duplicate ID inside one release, not reuse between releases

What the data shows:
- **Raw archive (`CEDA2002Data.xls`, 657 rows, contiguous IDs):** `200200001` is Tulare A-02 (Strathmore) and `200200002` is Butte B.
- **`ceda_parsed.csv` (659 2002 rows):** it holds **both** identities under each ID: Mendocino H and Tulare A-02 under `…001`, Butte B and Monterey K under `…002`. The two extra rows carry Sunday dates (2002-03-03 and 2002-11-03).
- **July 2025 backup:** the same lineage. 9189 is Mendocino H under `200200001`. The 2,210-to-1,212 "Monterey K" sits inside the July hybrid id 9209, which carries King City's ID, `200200376`.

So the CSV's release reused two IDs within itself. Two consequences:
- **The report's wording.** §4 ("the 2002 pair shows it is not a one-off") and §6 ("different release … in at least three places") should say this instead.
- **"Monterey K" is ambiguous.** In design §9 and decision 3 it means the missing 2,210-to-1,212 bond (Hartnell-type vocational text). It does not mean the archive's Monterey K (King City, `200200376`, id 9209), which is present and correct.

The tool's `load_csv` does not check for duplicate (year, `measure_id`) pairs inside the CSV. The CSV has 27 such pairs: 25 in 2014 (the group keys) and the 2 in 2002.

### N10 (P3): the San Bernardino GO bond figure moves again in step 5

The 63/92 figure holds 2014 constant. Step 5 inserts two San Bernardino GO bond shares:
- Palo Verde Community College P (`201400525`): own FailF, combined PassF;
- Snowline Joint Unified L (`201400548`): FailF both ways.

Under §5's rule, the post-P1b.2 cohort is **64 of 94 (68%) combined, or 60 of 94 (64%) per row**. Design §5 calls the result "the 63 of 92 in the report's §5". List A/B and P1b.3 should quote the end-state figure.

### N11 (P3): Measure P's provenance is weaker than the report implies

The only source for P is row 121 of `ceda_data_2015.xlsx`, a 2016 row appended to the 2015 file. Its date is 2016-11-17, which is not an election day. Its `Multi_MeasID` is `201600117`, which the CSV's 2016 release gives to Santa Clara AA (the SF Bay parcel tax). P is absent from the CSV's 2016 release. D, by contrast, sits under its home year's ID with a real election date (2016-11-08). This affects Q5.

## Answers

### 2. The tool as the P1b.2 gate

**Fail closed?** Only for defects outside waived keys, and only when both optional flags are passed (N2, N3). It also cannot go green after the designed step 8 (N1). Exit codes behave as stated: 2 if the DB hash changes, 1 on an unclean gate, 0 otherwise. Bad waiver syntax fails closed.

**Waivers narrow and visible?** Visible: they are echoed in `summary.json`. Not narrow: a waiver covers every class on every row under the key (N2).

**2014 mode from the data:**

| State | Mode | Result |
|---|---|---|
| Today | `group` | 27 match / 521 `wrong_key` / 29 `missing_from_db` (reproduced) |
| Correct rekey, applied in memory to the real 548 rows | `own` | **548 match**, 29 `missing_from_db` |
| Half-done rekey | `group` | 258 `missing_from_raw`, 263 `wrong_key`, 287 `missing_from_db` (fails closed) |

The new tests cover all three on synthetic data.

**Repeated IDs never overwritten?** Yes. `candidates` keeps lists, and two raw rows under one ID become `repeated_ids` plus `id_collision`, or `missing_from_db` with `id_collision: true`. The 21 held files contain none, and in-file duplicates still raise. One gap: duplicates on the stored side (N8).

**The "ID reused" class against the sources.**
- **4870: confirmed.**
  - July backup: D, 83,816 to 39,839, key `MEASURE_D`.
  - Today: P, 8,499 to 2,596.
  - Raw 2015 file row 121: P.
  - CSV line 3843: D.
  - `measure_updates` has no rows for 4870, consistent with the April 28 path (`ingest_measures`), which does not log.
- **2002: these are release conflicts, not `id_reused`.** The tool itself does not class the 2002 IDs as `id_reused`: the stored identity has not changed since July. It lists them as release conflicts whose second identity is not stored, which is correct. The report's description of them as "reuse between releases" is not (N9).

**Rerun against the export.** I ran the committed tool on a backup-API copy with the report's flags.
- `ledger.json` is **byte-identical** to `scraper/data/exports/ceda_reconcile_20261112/ledger.json`.
- `summary.json` differs only in `db` and `db_sha256_*`, because a backup copy has different bytes.
- Totals: 6,169 / 1,702 / 521 / 55 / 28 / 1 / 1 / 29.
- Gate: not clean, with 3 release conflicts.
- `tool_sha256`: `f9588a8e…354b`.
- Tests: 27 passed.

### 3. Design safety

**Unique rule only in production?** Confirmed. `git grep` finds no `UNIQUE(year, measure_id, …)` in any tracked `.py` or `.sql` file. `models.py:258` declares `fingerprint TEXT UNIQUE` plus a non-unique `idx_fingerprint`. Production has `UNIQUE INDEX idx_fingerprint` plus the table constraint.

Production also differs from code in other ways: `idx_decade` in production against `idx_measure_fingerprint` and `idx_is_duplicate` in code; a `master_id` foreign key in code; column order. So "code and production agree again" (§4) needs more than adding the new rule. §11 acknowledges this.

**Dependent code list:** incomplete (N7). The four referencing tables and the nine indexes are correct.

**Every public `id` preserved?** Yes, in the procedure: explicit column copy, and the sequence is preserved (verified in memory). New rows (29 shares and D) get new ids. Step 6 keeps 4870.

**Column classes.** Correct, and Layer 1 no longer contradicts the fill step (F2 above). Two additions:
- Say whether "raw value" means raw bytes or `clean_text`. Raw text from 2006 on carries zero-width characters and NBSPs.
- `passed` belongs in the outcome class only if N1 option (b) is chosen.

**Search index:** the rebuild is right; the checks are not (N5).

**Embeddings and research:** research and summary checkpoints key on `id` (fine). Embeddings: N7.

**Fail-closed ingest:** right, and placed correctly in §11. The identity check before an exact-key update is the guard that would have saved D.

**2016-2021 collisions (§10):** the procedure is sound: run the tool first, keep both measures, never replace one with the other. It depends on N2/N3 being fixed, because a waived key hides exactly these cases. Add one rule: the variant goes on the row that is foreign to the ID's home release (Q5).

### 4. Cohort figures

I recomputed independently with the earlier reviewer's loader (`rawload.py` / `cohort.py`, which shares no code with the tool), against today's copy:

| Cohort | Stored | Raw per row | Raw combined |
|---|---|---|---|
| SB GO bond | 60/87 | 60/92 | 63/92 |

All 13 San Bernardino and San Mateo cohorts equal the tool's `summary.json`.

The +3 comes from five multi-county rows where own and combined differ:

| Year | Measure | Own | Combined |
|---|---|---|---|
| 2002 | Kern CC G | 0 | 1 |
| 2004 | Beaumont AA | 1 | 0 |
| 2006 | Sierra Sands A | 0 | 1 |
| 2022 | Muroc B | 0 | 1 |
| 2024 | Sierra Sands AA | 0 | 1 |

All five are `Multi_CO=1` with `REQ=F`.

**Is "combined" consistent with the layout review's answer 2? Yes in substance, with conditions:**
- **Consistent.** Answer 2 forbids measure-wide Pass/Fail for a county portion. Counting the 60/92 figure would give each portion its own outcome. "Count once in … cohort totals" is met: each district contest appears once in each county's cohort.
- **Labelling.** Answer 2 also requires saying "when a displayed count is county listings versus unique contests" and not implying that county residents decided the measure. A San Bernardino GO bond rate that includes Kern Community College G must be labelled as measures on San Bernardino ballots.
- **Source.** The combined result needs "an authoritative consolidated source or a validated aggregation". `passfail_sum` is CEDA's consolidated field. `group_violations` validates `YES_sum` but not `NO_sum`; add it.
- **Storage.** It is not consistent to store the combined result in `passed` while the row shows portion votes (N1).
- **End-state figure.** It is 64/94 (N10).

### 5. Fable's five questions (design §12)

1. **Decision 4 reading.** Agree. The layout review's model ("canonical contest key plus county memberships; preserve existing public IDs; count once") is exactly Fable's reading. Merging pages would retire ids, which that review rules out. Fable is also right that the multi-county change does not need the unique rule changed (after the rekey every share has its own `MeasureID`); Igor's note that the rule "must change" is driven by Santa Cruz. Ask Igor to confirm, and fix N1 first.

2. **Which measure keeps 4870.** I agree with leaving 4870 with Measure P.
   - **Verified:** `measures/4870.html` was first published on 2026-07-02 (`542e2bae`) and shows P in both of its versions. No published file ever paired id 4870 with D. Before July, site data carried `measure_id 201600120` = D (`cd7654de:index.html`), but not ids.
   - **Two conditions:**
     - **(a)** Put `source_variant` on **P**, not D. The ID's home release (2016) gives `201600120` to D, and P is the stray row from the 2015 file (N11). A future 2016 file should then match D on the plain key, instead of reaching P through the very path that destroyed D. This changes 4870's (non-public) fingerprint once. It breaks §4's claim that every fingerprint is unchanged, but only for that one named row.
     - **(b)** Record in `measure_updates` that 4870's `created_at` (2025-07-31) belongs to D's load.
   - **If Igor prefers the review's earlier "return 4870 to D":** that is defensible on database history, but it changes what a published permalink shows. I would not.

3. **Restore D now, marked unverified?** Safe only with conditions; without them, wait.
   - **The evidence is good.** D has two consistent sources of the same lineage (the CSV and the July backup), a real election date, and its home-year ID.
   - **The unverified mark must exist** (N6).
   - **The `measure_id` consumers must be fixed first** (§4 plus N7). Otherwise D and P share research, recommendations and embedding neighbours.
   - **The gate must not blanket-waive `2016:201600120`** (N2).

   With those in place, restoring D is less risky than leaving a real county measure missing until the Esploro file arrives.

4. **`title`.** Agree: leave it untouched in P1b.2. The 28 wrong rows' titles are placeholders (all 28 checked), so no wrong content stays in `title`.

   Note that step 7 alone changes thousands of pages. On about 6,990 rows `title` already equals the question, and filling `ballot_question` makes the modal's ballot-question section appear with the same text again. P1b.3's page diff must expect this and decide whether to suppress the duplicate.

5. **Qualified `measure_id` fallback (`201600120~D`).** Keep it as the fallback. It avoids the rebuild and N4, but it puts a non-CEDA key into `measure_id`, which is the column every N7 consumer reads. The rebuild with `source_variant` is the better design once N4's view step is added. The consumer work in N7 is needed either way, because 2014 already breaks `measure_id`-keyed artifacts.

## What I did, and what I did not reproduce

**Did:**
- Read CLAUDE.md, the earlier review, the revision prompt, Igor's decisions, the four revised files and `git diff 3991b587 e89592c7`.
- Made a backup-API copy of production (source opened `mode=ro`) in my scratch folder. Opened the July 2025 backup `mode=ro` only.
- Read raw files only through `python -I` scripts in my scratch folder (a copy of the tool, byte-identical, plus my scripts), with data paths passed as arguments.
- Reran the tool and compared it with the export. Ran 27 tool tests (`--basetemp=.pytest-tmp/review-recon2`, all passed).
- Simulated repair states in memory by wrapping the tool's `ceda_rows`; no database was written.
- Replayed §4's migration and the FTS checks on an in-memory copy.
- Recomputed:
  - the cohorts, independently;
  - 606 member rows in 265 groups;
  - the 140/5 flips;
  - the 8,020 / 6,992 `title` figures;
  - the 4870 publication history;
  - the overlap of 2014 keys.

**Did not:**
- Run the full test suite: Codex is editing `generator.py` in this checkout.
- Anything needing the network: the Esploro release, or whether Measure P is real and correctly dated.
- Re-derive the 20/23 summary heuristic.
- Test the effect of a rebuilt FTS index on `promote_statewide_release.py` and `verify_statewide_candidate.py` against a real release pair.

**Production DB SHA-256:** before `ef1359e482db2c54fe41068771932aaac7c9fc1db372e2e1d8cbbed1f505d9da`, after `ef1359e482db2c54fe41068771932aaac7c9fc1db372e2e1d8cbbed1f505d9da`.

**Scratch files:** scripts in `C:\Users\igorg\AppData\Local\Temp\claude\3706ee781272b6b6\d90ea535-f05d-4a6f-929d-dbc27318d103\scratchpad\review-recon2\scripts\`:
- `simulate.py`, `simulate2.py`: gate scenarios;
- `ftsmig.py`: §4 and §7;
- `dupcheck.py`: N8;
- `csvlook.py`, `look2.py`, `look3.py`, `july.py`: 2002 and 2016;
- `sb2014.py`, `groups.py`, `rekeyoverlap.py`;
- `indep\cohort.py`.

The tool rerun is in `C:\Users\igorg\AppData\Local\Temp\claude\3706ee781272b6b6\d90ea535-f05d-4a6f-929d-dbc27318d103\scratchpad\review-recon2\out\rerun\`.
