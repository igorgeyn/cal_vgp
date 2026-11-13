# P1b.2 design: repair the CEDA history

**Date:** November 12, 2026. **By:** Fable. **Status:** proposal for Igor. Nothing here has
been run. **Evidence:** [reconciliation report](ceda_reconciliation_20261112.md) and the
[P1b.1 review](../codex/p1b_1_ceda_review_response.md).

## 1. Recommendation: rebuild and diff, not patch

Build the expected value of every CEDA field from the raw files, compare it with the
database, and apply only the differences, in ordered steps on a copy. Reasons:

- The defects have one root, a loader keyed on county and designation, but three shapes:
  28 wrong rows, 55 incomplete rows and 5 misspelled counties. A patch list would miss the
  next shape.
- The comparison already exists. `reconcile_ceda_raw.py` becomes the before-and-after gate:
  after the repair it must report no wrong row, wrong key, incomplete or missing row.
- 6,169 rows already match raw exactly. That gives Layer 1 a strict meaning: those rows'
  existing columns must not change at all.

## 2. Rules for every step

- **Keep every `id`.** No step deletes or reuses one. New measures get new ids.
- **Do not go through `ingest_measures` or `Database.update_measure`.** They recompute keys,
  refuse to overwrite a non-empty field and swallow errors. Use direct SQL keyed on `id`,
  from a reviewed mapping file (`id`, year, `MeasID`, source file, sheet, row).
- **One transaction per step**, with its assertions inside it and its own changed-row list.
- **Record provenance per value:** file, SHA-256, sheet, row.
- **Never join or update on (year, county, designation).**

## 3. Steps, all on a database copy

| # | Step | Rows | Assertion |
|---|---|---|---|
| 0 | Baseline: backup-API copy, per-row hash of every CEDA field, counts per year | 10,997 | Hashes recorded |
| 1 | **Restore the 157 stale rows from raw**, before anything else: question, votes, percent, `pass_fail`, date. `ballot_question` is **replaced**, not filled. Clear `summary_text` and `summary_title` on the 28 wrong rows; they describe another measure. | 157 | Reconcile reports 0 wrong rows; list A (changed outcomes) written |
| 2 | Canonical county on the 5 `SAN BERNADINO` rows; keep the raw spelling in a new `ceda_county_raw`. Remove the special case at `generate_site.py:243-246` in the same change. | 5 | Cohort changes listed for Igor |
| 3 | **2014 rekey, two phases:** set each 2014 row's key to `REMAP:<id>`, then to its `MeasureID`. Recompute `fingerprint` and `measure_fingerprint` in SQL. | 548 (521 change) | Mapping is one-to-one; only three columns change; the unique index holds; the set of ids is identical |
| 4 | 2014 side artifacts in the same commit: rekey `embedding_metadata.json` and its neighbours with the same mapping, and any research data keyed on `measure_id`. Mark `ceda_parsed.csv` superseded. | | No artifact still holds an old 2014 key |
| 5 | 2002: quarantine id 9189 under a provisional key and insert Strathmore A-02 as a new row. | 2 | Igor's decision first (§5) |
| 6 | Insert the 29 missing 2014 county shares as new rows, flagged so they add nothing to statistics. | 29 | Multi-county representation decided first (§5) |
| 7 | Backfill new columns from raw: `place_name`, `jurisdiction_kind`, `multi_measure_id`, combined votes and percent, `ceda_req` (raw), and `ballot_question` (replace) on every held-year row. | 8,506 | **Layer 1, strict:** the 6,169 matching rows keep identical values in every existing column |
| 8 | Outcome rule: `passed` from the combined result for multi-county measures, from the row's own result otherwise. Conflicts are held out (§4). | | List B for Igor |
| 9 | Update `KNOWN_ISSUES` #1 and #5; add the loader defect as a new entry. | | |
| 10 | 2016-2021, when Igor has the files: the same pipeline, plus a cell diff of archive against Esploro. | 2,520 | |

**Verification.** Layer 2: rows per year equal the raw files, plus the 2002 and 2016
exceptions, each named. Layer 3: traces for San Joaquin Delta K, Azusa A and Vernon A,
Rim of the World I, Strathmore A-02 and one 2014 group. Then rerun the reconciliation.

## 4. Thresholds and outcomes

- **`REQ` is unsafe to map straight to `required_vote`.** Store it raw as `ceda_req`.
  Derive `required_vote` only by rule, with a `required_vote_basis` column, and leave it
  NULL where the rule does not apply. Known traps: no `F` code exists before 2002; 2001
  Proposition 39 bonds are coded `M`; some later Proposition 39 bonds are coded `T`.
- **Never compute pass or fail from `REQ`.** Use CEDA's outcome fields.
- **Hold these out of automatic outcome changes** and send them to Igor's P1b.3 list:
  every row where `PASSFAIL` and `passfail_sum` disagree with `Multi_CO=0`; the five
  KNOWN_ISSUES #1 records; and 2014 `201400551`.
- **KNOWN_ISSUES #1, proposed wording:** "For five school bonds, CEDA's per-county and
  combined outcomes conflict. `REQ=T` is probably a miscoding of 55% Proposition 39 bonds,
  which would make the per-county 'Pass' correct. Held out of automatic outcome changes
  until checked against county or Secretary of State records. Keyed by `measure_id`; the
  row ids listed before November 2026 were stale."

## 5. Stopping it recurring (parser, before step 10)

- An explicit header map with exact, case-insensitive names; `HEADER_ALIASES` in the
  reconciliation script is the tested starting point.
- Raise when the ID column is missing. Remove the substring fallback (`ceda.py:268-273`).
- Remove the in-file fingerprint dedup (`ceda.py:374-384`), or make it raise.
- Canonicalize the county before any key is built.
- For CEDA, never derive an identifier from the title.

## 6. Decisions for Igor

1. **Approve rebuild-and-diff** and the step order above?
2. **The 23 wrong summaries are live now.** Hide them ahead of the full repair (a small
   change of its own), or wait for step 1?
3. **Id 9189 (Mendocino H, 2002):** retire it, or keep it as a separate measure if the
   Esploro file or the county confirms it?
4. **Multi-county representation:** county-share rows flagged as duplicates, or one row per
   measure with a group key? This decides steps 6 and 8.
5. **San Bernardino's GO bond rate will read 65%, not 69%**, before combined results are
   applied. Is listing each such change in P1b.3 enough, or do you want to see them first?

## 7. Size

About 2 days of agent work for steps 0-9 on a copy, plus roughly an hour of Igor's time on
lists A and B. Step 10 waits on the downloads.
