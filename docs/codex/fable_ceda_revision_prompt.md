# Prompt: revise the CEDA tool and P1b.2 design after review

**For:** Fable, in Claude Code desktop, on branch `phase0-election-status`. Run this after the
Explore review, or in a separate session.
**Type:** code and docs revision. **No database writes of any kind, including to copies.**

---

Your CEDA reconciliation (commit `3991b587`) was reviewed by an independent Claude agent, standing
in for Codex. Read `docs/codex/p1b_1b_reconciliation_review_response.md` in full. Its verdict:
the report and the design are both **ready with changes**. Every headline number reproduced
with an independent loader.

Igor has also answered your five design decisions. They are in the checklist
(`docs/plans/local_measures_checklist_20261107.md`), under "CEDA repair (P1b.2) decisions":
1. Rebuild and diff.
2. A separate small follow-up release flags the 29 wrong records. That release is not your task.
3. Leave 9189 until the current Esploro release is downloaded.
4. One row per measure, plus a shared group key.
5. A list in P1b.3 is enough.

## Revise

**Tool** (`scraper/scripts/reconcile_ceda_raw.py` plus tests). It must become the P1b.2 gate:
- **2014 mode.** Don't choose it from the header name alone. After a correct 2014 rekey, the
  tool must report a clean match, not 521 rows missing from raw and 550 missing from the DB.
  Add a test for the rekeyed state.
- **Repeated IDs.** Detect and report the same CEDA ID across files and releases, such as id
  4870: Santa Cruz 2016 Measure D was overwritten by Measure P, which has the same ID
  `201600120`. Today a later row silently replaces an earlier one; make that a reported
  collision instead.
- **Raw-file evidence.** Record each raw file's SHA-256 in `summary.json`.
- **Cohort figures.** Recompute the cohorts in your report §4 with the committed tool, not the
  one-off script. The review got San Bernardino GO bond at 60 of 92 from stored per-row
  outcomes, and 63 of 92 from CEDA's combined results. Report both, and say which one the site
  should use and why.

**Report** (`docs/plans/ceda_reconciliation_20261112.md`): correct it according to the review's
findings, especially:
- id 4870, the third way the damage can recur;
- the 157 skipped rows were dropped by the `UNIQUE(year, measure_id, data_source)` rule;
- April 12 blanked `ballot_question` on 8,021 rows, so "never loaded" is wrong;
- the April 28 events;
- the `measure_updates` evidence;
- the July key was the letter prefix.

**Design** (`docs/plans/ceda_backfill_design_20261112.md`): fold in Igor's answers, and fix:
- **The Layer 1 vs step 7 conflict.** Name exactly which fields are protected and which are
  allowed to be filled.
- **The `UNIQUE(year, measure_id, data_source)` rule.** It has to change, both for decision 4
  and to store both Santa Cruz measures. Specify the schema change, the migration on a copy,
  and what depends on it.
- **Restoring id 4870 and the missing Measure D.** Keep every existing public `id`.
- **Derived fields in step 1:** `topic_primary`, `passed`, `total_votes`, `has_summary`, and
  any others you find.
- **`measure_search` FTS sync.** It has only an insert trigger; plan a rebuild and its check.
- **The ingest bug.** A failed insert is counted, not surfaced (`pipeline.py`, review finding 2).
  Add that to §5's recurrence fixes.
- **Collision handling** for the unseen 2016-2021 files.

Remove §6, "Decisions for Igor", or mark it answered. List any new questions it raises.

## Limits

- No database writes, not even to a copy. Read only (`mode=ro`, or a backup-API copy for
  reading). Record the production DB SHA-256 before and after. It is currently
  `ef1359e482db2c54fe41068771932aaac7c9fc1db372e2e1d8cbbed1f505d9da`.
- Raw files are untrusted. Run Python on them with `-I`.
- No network. Don't commit; the coordinator commits after a review.
- Run the tool's tests and the full suite. The baseline is 728 passed, plus the known 1
  failure and 17 errors.

Reply with: what changed in each of the three files, the new test count, the before and after
DB hashes, and any new question for Igor.
