# Codex review request: P1b.1 CEDA downloads and column check

**Type:** review only. Branch `phase0-election-status`.
**Read:** [`docs/plans/ceda_column_check_20261111.md`](../plans/ceda_column_check_20261111.md).

## What was done

- The 1998-2014 files were downloaded from Internet Archive copies of CSU Sacramento's old
  `www.csus.edu/isr/` hosting. There are 18 files in all, including two older copies of
  2011.
- The files are in `scraper/data/raw/ceda_downloads_20261111/`, with a `manifest.json` of
  URL, status, bytes, SHA-256, time and provenance. That folder is gitignored.
- 2016-2021 still need Igor to download them by hand from the CSUS Esploro page, which
  needs JavaScript.

## Questions

1. **Provenance.** Are the archived 1998-2014 files acceptable sources for P1b.2? Or must
   the backfill wait until Igor downloads the current Esploro release and we check the two
   match?
2. **2014 keying.** Is the diagnosis in §6a right? The parser fell back to `Multi_MeasID`
   because the column is named `MeasureID`. As a result 521 of 548 rows carry another
   row's ID, and 29 multi-county rows collapsed away. What is the safe way to remap before
   a backfill keyed on `MeasID`? Remember that `id` must never change.
3. **Wrong votes.** Do these need their own fix, ahead of the backfill?
   - the 28 rows that hold another measure's votes (§6b): 5 in 2000 and 23 in 2011;
   - the 2002 foreign row: database `200200001`, a "Mendocino H" the file doesn't have.
4. **Parser checklist (§8).** Is it complete? Especially:
   - `Multi_MeasID` and `Multi_CO` groups whose values disagree;
   - the `.xls` years, with decimal IDs and Excel serial dates;
   - name variants;
   - zero-width and non-breaking spaces;
   - the misspelled counties.
5. **KNOWN_ISSUES #1.** All five records have `REQ=T`, and `passfail_sum=FailT` agrees with
   the combined percent; the wrong field is the per-row `PASSFAIL`. Should #1 be
   re-framed? Should the plan's claim that `BALQUEST` is empty everywhere be corrected? It
   is filled for 2011 (143 of 172 rows), 2015 and 2022-2024.
6. **Rows with a result but `passed` NULL.** 2000 has 6, 2005 has 1, 2011 has 48 and 2018
   has 1. Are these one fix or several?

## Constraints

- Review only.
- Production database read-only, and only through the SQLite backup API.
- No downloads; no push.

## Please return

Write `docs/codex/p1b_1_ceda_review_response.md` with:
- a verdict;
- findings ranked by severity;
- answers to questions 1–6;
- a recommended P1b.2 order of operations.

Commit only that file.
