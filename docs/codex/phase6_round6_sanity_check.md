# Codex Phase 6 round-6 sanity check

> **For Codex:** Quick sanity check on the round-6 closeout commit.
> You flagged 5 cleanup findings + 5 Phase G false-pass risks in the
> prior pass; this commit addresses each. Just confirm each fix
> matches what you recommended and nothing new is broken.
>
> Live commit: `1c010b6` on `main`. Diff stats:
> ```
> docs/DATA_PIPELINE.md          |   9 ++-
> docs/KNOWN_ISSUES.md           |   3 +-
> docs/WORKING_LIST.md           |   9 +--
> scraper/data/finance/README.md |  13 ++--
> scripts/v3/verify_phase_g.py   | 148 +++++++++++++++++++++++++++++++----------
> ```

## What was fixed

### Cleanup findings (5)

| # | Codex finding | Fix in `1c010b6` |
|---|---|---|
| 1 | `DATA_PIPELINE.md` "181 matched campaigns" should be "measures/propositions" | Now "181 matched measures across 194 campaigns" with parenthetical explaining the year-offset-collision delta |
| 2 | `finance/README.md` self-contradicts on AIMCO (line 211 says covered, line 213 says "NOT merged") | Rewritten: generic suffix merging avoided; specific same-filer cases (AIMCO, Pala) are curated. Both ideas reconciled in one paragraph. |
| 3 | Test count claims off: real is 114 v2 + 60 v3 + 13 crosswalk = 187; docs said 118+60+9. Pytest command (`test_finance_db*.py`) misses crosswalk file. | README + WORKING_LIST corrected to 114+60+13. Pytest command corrected to explicit file list. |
| 4 | WORKING_LIST line 14 says "5 rounds + closeout" (separates), line 82 + CHANGELOG line 57 says "5 (incl closeout)" (combines) | WORKING_LIST line 14 rewritten to single framing: "5 review passes total (including closeout); plus 1 action-plan request" |
| 5 | "Last Updated: February 2026" stale on KNOWN_ISSUES + DATA_PIPELINE despite May 20 edits | Replaced with "Original snapshot: Feb 2026 / Most recently amended: 2026-05-20" with note about scope of amendment |

### Phase G hardening (5)

| # | Codex finding | Fix in `verify_phase_g.py` |
|---|---|---|
| G5 | 30-measure sample; full 181 takes ~1.15s | Now iterates all 181 measures, drops the "would be quadratic" comment |
| G6 | Only checks Uber; misses FanDuel/FBG/Penn/Postmates | Now checks 6 marquee aliases: Uber, Postmates, Instacart, FanDuel, FBG, Penn Interactive. Each: (measure_db_id, stance, expected canonical, substring hint) |
| G7 | Samples one measure (PROP_27_2022); could silently pass if branch isn't exercised | Scans ALL measures, asserts non-empty sample (fails if 0 monetary rows). Live run: 288 monetary rows verified |
| G8 | Source-has-sector → canonical-has-same-sector invariant; misses case where neither side has a sector | Adds explicit expected-sector set for 8 marquee canonicals (Uber/Postmates/Instacart/FanDuel/FBG/Penn/Pala/AIMCO) on top of round-trip |
| G9 | Checks method shape only, not API response shape | Now also asserts `FinanceSideResponse.model_fields` doesn't carry `n_transactions`. Graceful skip if FastAPI not importable in env |

## Live re-run

```
  [PASS] G1: v3 db has all expected tables (4) and views (3)
  [PASS] G2: v3 accepted total = $2,510,050,967.24
  [PASS] G3: combined total across 181 measures = $5,750,344,165.78
  [PASS] G4: combined calendar-year sum reconciles ($5,750,344,165.78)
  [PASS] G5: breakdown sums = summary totals (181/181 measures)
  [PASS] G6: alias merge collapses 6 marquee cross-source variants
  [PASS] G7: combined summary rows with monetary>0 have top5/hhi=None (288 rows verified)
  [PASS] G8: alias canonicals preserve source sectors (18 round-trip + 8 marquee-explicit checks)
  [PASS] G9: n_transactions absent from combined summary (API model check skipped: FastAPI not importable)

=== Phase G: 9/9 PASS ===

real    0m4.293s
```

(G9 API note: my dev shell has FastAPI in a separate env, so the
guard skipped. If your environment has FastAPI, the message should
read `(incl. FinanceSideResponse model)` instead of the skip note.)

## What we want from this sanity check

1. **Each cleanup fix matches the intent of your prior finding?** No
   over-rotation, no missed nuance?
2. **Each Phase G hardening matches what you suggested?** Particularly
   on G7 (the "scan all, assert non-empty" pattern) and G9 (the
   model-fields assertion approach).
3. **Did anything new break in the prose?** The cleanup edits touched
   5 docs; any new inconsistencies introduced?
4. **Anything missed?** If there's any finding from round-6 we didn't
   address, flag it.

This is intended to be a quick read — short bullet feedback is
fine. Calibration: nothing in this commit is risky enough to
warrant pixel-level scrutiny; we want to confirm we landed in the
right place.
