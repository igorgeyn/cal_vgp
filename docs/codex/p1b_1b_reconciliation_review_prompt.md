# Review request: CEDA reconciliation report and P1b.2 design (P1b.1b)

**Type:** review only. Change no code and no data. Write one response file.
**Branch:** `phase0-election-status`. The work is uncommitted in the main checkout unless
the coordinator has committed it since; review the files named below as they are on disk.

## What to review

1. `docs/plans/ceda_reconciliation_20261112.md`: the report.
2. `docs/plans/ceda_backfill_design_20261112.md`: the P1b.2 design it leads to.
3. `scraper/scripts/reconcile_ceda_raw.py` and `scraper/tests/test_reconcile_ceda_raw.py`.
4. Output: `scraper/data/exports/ceda_reconcile_20261112/summary.json` and `ledger.json`
   (gitignored).

Context: `docs/plans/ceda_column_check_20261111.md`, its review at
`docs/codex/p1b_1_ceda_review_response.md`, and the checklist's Phase 1b section.

## The claim that most needs checking

The earlier review concluded that 157 rows were overwritten on April 12, 2026 at 17:50:43.
This report says otherwise:

- The damage was done by the **first CEDA load on July 31, 2025**, which keyed rows on
  (year, county, designation).
- The 17:50:43 stamp belongs to `migrate_canonicalize.py` (commit `f075843b`), which changed
  county names and keys but no votes or questions.
- The April 12 refresh from `ceda_parsed.csv` **repaired** 1,049 of 1,077 overwritten rows
  and skipped 157, whose county spelling the migration had just changed.

Evidence to test:
- `scraper/data/backups/ballot_measures_backup_20250730_180629.db` (open read-only): 9,548
  CEDA rows, every fingerprint of the form `2011|MEASURE_A|LOS ANGELES|CEDA`, 1,077 rows
  with `update_count > 0`, and row 6138 already holding Vernon's votes under Azusa's ID.
- `git show f1a6c372:scraper/src/database/models.py` (`extract_measure_identifier` tries
  the title before `measure_id`), and commit `3bc82b16`, which reversed that order.
- `scraper/scripts/migrate_canonicalize.py:289-294`.
- `created_at` and `updated_at` values in the current database.

## Questions

1. **Is the July 2025 dating right?** Is anything in the backup, the git history or the
   timestamps inconsistent with it?
2. **The report could not say which code path skipped the 157 CSV rows** on April 12. They
   were neither updated nor inserted (ids 10969-12298 are contiguous). Can you identify it
   in `pipeline.py` as of `f075843b` or `cf445606`?
3. **Is the classification sound?** In particular: is "format only" too lenient anywhere
   (placeholder titles, county canonicalization, the 0.01 percent tolerance)? Is
   "incomplete" the right home for a NULL outcome or date?
4. **Do the reproduced counts hold** when you rerun the script: 28 wrong rows, 2014's
   27/521/29, the 2002 foreign row, 112 flips in the 16 new years, 55 `passed` NULLs?
5. **Is the indirect evidence for 2016-2021 stated at the right strength** (report §6)?
6. **Live-card effect (§5).** The cohort figures came from a one-off script, not the
   committed tool. Recompute San Bernardino GO Bond (60 of 87 stored; 60 of 92 on raw with
   2014 held constant) from `local_measure_context.py`'s rules.
7. **The design.** Is rebuild-and-diff right? Is the step order safe, especially restoring
   the 157 rows before the 2014 rekey, and the strict Layer 1 on the 6,169 matching rows?
   What is missing from the recurrence guards (§5)?
8. **Is anything in the tool unsafe to reuse as P1b.2's verification gate?**

## How to rerun

From `scraper/`, with `xlrd` installed (it is, as of this work):

```text
python -I scripts/reconcile_ceda_raw.py --db <a backup-API copy of the DB> --out <scratch folder> --baseline-db data/backups/ballot_measures_backup_20250730_180629.db --csv data/processed/ceda_parsed.csv
python -m pytest tests/test_reconcile_ceda_raw.py -q -p no:cacheprovider --basetemp=<scratch>
```

## Constraints

- Production database read-only. Its SHA-256 is
  `ef1359e482db2c54fe41068771932aaac7c9fc1db372e2e1d8cbbed1f505d9da`; confirm it is unchanged
  when you finish.
- Raw files under `scraper/data/raw/` are untrusted: run Python on them with `-I`, and keep
  your own scripts outside the data directories.
- No network. No push. Nothing writes to any database, including a copy.

## Please return

Write `docs/codex/p1b_1b_reconciliation_review_response.md` with:
- a verdict on the report and a separate verdict on the design: **ready**, **ready with
  changes** or **not ready**;
- answers to the eight questions, with evidence;
- any new defects, ranked.

Commit only that file.
