# CalBallot: Known Data Quality Issues

> Issues identified but deferred for future investigation or accepted as data limitations.

**Original snapshot:** February 2026
**Most recently amended:** 2026-05-20 (added v3-era issues #9, #10, #11)

---

## 1. Vote Threshold Encoding Errors

**Severity:** Low (5 records)
**Status:** Deferred — requires manual verification against source documents

Five measures are marked as `passed=1` with `vote_threshold='66.67%'` but have `percent_yes` values well below 66.67%. These likely have incorrectly encoded thresholds (should probably be 50%).

| ID | Measure ID | County | Year | Actual % Yes | Expected Threshold |
|----|------------|--------|------|--------------|-------------------|
| 9320 | 200100189 | Humboldt | 2001 | 54.55% | Likely 50% |
| 7513 | 200500247 | Kings | 2005 | 55.61% | Likely 50% |
| 8300 | 200400215 | Santa Clara | 2004 | 56.75% | Likely 50% |
| 8326 | 200400219 | Santa Cruz | 2004 | 62.00% | Likely 50% |
| 7948 | 200400170 | Los Angeles | 2004 | 63.53% | Likely 50% |

**Source:** CEDA data — threshold derived from `pass_fail` code which may have been miscoded.

**To Fix:** Manually verify each measure against county election records and update `vote_threshold` accordingly.

---

## 2. Exactly 50% Ties

**Severity:** Info (2 records)
**Status:** Accepted — behavior is correct

Two measures have exactly 50.0% yes votes and are marked as `passed=0`. In California, ties (exactly 50%) typically fail, so this is correct behavior. Left as-is.

| ID | Measure ID | County | Year | % Yes | Status |
|----|------------|--------|------|-------|--------|
| 1025 | 202200138 | Imperial | 2022 | 50.0% | Failed (correct) |
| 4513 | 201400138 | Siskiyou | 2014 | 50.0% | Failed (correct) |

---

## 3. Content Duplicates (Cross-Source)

**Severity:** Info (257 groups)
**Status:** Accepted — expected behavior

257 groups of measures have identical `content_hash` values, meaning the same text appears in multiple records. This is expected when:
- The same measure is scraped from multiple sources (CEDA + Ballotpedia)
- The measure fingerprint differs (different source attribution)

These are not true duplicates — they represent the same real-world measure tracked from different data sources. The deduplication system correctly identifies them via `measure_fingerprint` for cross-source matching.

**No action needed** — this is by design.

---

## 4. 2025 Coverage Gap

**Severity:** Info
**Status:** Expected — no statewide elections in 2025

The database shows 0 measures for year 2025. This is correct:
- California has no statewide elections in odd years (2025)
- Local/special elections may occur but are not yet in our data sources
- Ballotpedia scraper covers 2020-2026, but 2025 had minimal ballot activity

**No action needed** — gap will naturally fill if local 2025 elections are added.

---

## 5. Missing Optional Fields (CEDA Source)

**Severity:** Info (~10,800 records)
**Status:** Accepted — source limitation

CEDA data (our largest source with ~10,800 records) lacks several optional fields:
- `description` — missing for 11,160 records
- `ballot_question` — missing for 11,156 records
- `source_url` — missing for 10,861 records
- `pdf_url` — missing for 11,282 records
- `election_type` — missing for 11,123 records

**Reason:** CEDA is a structured academic dataset focused on vote outcomes, not full ballot text. These fields are available in other sources (Ballotpedia, UC Law SF) when measures overlap.

**No action needed** — completeness score accounts for field importance tiers.

---

## 6. Non-Standard Measure ID Formats

**Severity:** Info (299 records)
**Status:** Accepted — valid variations

299 measures have `measure_id` values that don't match standard patterns:
- Standard county: `A`, `B`, `AA`, `A1`
- Standard statewide: `PROP 47`, `ACA 13`, `SCA 1`

Non-standard examples include:
- Long numeric CEDA IDs: `202400367`
- Special formats: `I2020`, `FD`, `S1`
- Initiative names: `INIT_CALEXIT`

These are valid measure identifiers from their respective sources — just non-uniform formatting.

**No action needed** — display uses `measure_letter` or parsed ID where possible.

---

## 7. Low Similarity Recommendations

**Severity:** Info (139 recommendations)
**Status:** Accepted — expected for unique measures

139 measure recommendations have similarity scores below 0.5. This occurs for measures with unique topics or unusual ballot text that don't closely match other measures.

**No action needed** — low scores are still the best available matches.

---

## 8. Negative Finance Total (1 record) — RESOLVED 2026-05-04

**Severity:** Low (1 record)
**Status:** Resolved by the v2 finance rebuild.

The v1 finance DB had one measure with a negative `total_receipts`. The
2026-05-04 v2 rebuild (`finance_statewide_v2.db`) introduced a
`non_positive_amount` acceptance gate that quarantines refunds and
zero-amount rows at the source, eliminating the underlying cause. v2's
`finance_summary` has 0 rows with negative `total_receipts`.

```sql
-- v2 (live):
SELECT COUNT(*) FROM finance_summary WHERE total_receipts < 0;  -- 0
```

See `plans/finance-rebuild-verification.md` and
`scraper/data/finance/README.md` for the rebuild details.

---

## 9. v2 monetary donor distribution capped at top-20

**Severity:** Medium (affects concentration metrics on combined view)
**Status:** Accepted; resolution path documented

v2's `finance_top_donors` table is materialized at the top-20 donors
per `(finance_campaign_id, stance)` only. The full per-donor
distribution isn't stored — only summary totals are exact.

In the post-Phase 5 combined view, this means computing HHI /
top5_share against the merged v2+v3 donor list would systematically
underestimate concentration for any measure where v2 monetary is
non-trivial (the missing v2 tail donors don't get counted in the
denominator). `FinanceDatabase.get_combined_summary` therefore
returns `None` for `top5_share` / `hhi` on any row where
`monetary_amount > 0`. v3-only rows pass through v3's exact metrics.

**Resolution path (either of):**
1. v2.1 rebuild that materializes the full monetary donor
   distribution (a few GB; could go in a separate auxiliary table).
2. v3 monetary ingest sub-phase that adds `monetary_contribution`
   rows to `finance_flow_v3`. Then `get_combined_*` collapses into
   v3-only counterparts and concentration metrics become exact for
   all rows.

Tracked in `docs/WORKING_LIST.md` Phase 6 follow-ups.

---

## 10. Cross-source donor canonicalization drift

**Severity:** Low (display-side, doesn't affect totals)
**Status:** Curated alias map covers visible cases; ongoing

v2 (`finance_top_donors`) and v3 (`finance_flow_v3`) canonicalize
donor names independently. The same legal entity sometimes appears
under two slightly different canon strings — typically a comma diff
(`UBER TECHNOLOGIES, INC` vs `UBER TECHNOLOGIES INC`), D/B/A
wrapping (`FanDuel Sportsbook (Betfair Interactive US)` vs
`BETFAIR INTERACTIVE US LLC D/B/A FANDUEL GROUP, INC`), or
`(RESPONSIBLE OFFICER:...)` suffix.

`src/finance/donor_aliases.py` curates ~18 entries covering all
visible splits in marquee fights + top-N donor lists. Aliases apply
only at combined-merge time — underlying v2/v3 storage
canonicalization stays independent so source-table reconciliation
remains exact.

**Known limitations:**
- Aliases are curated, not generic. Future visible splits in
  lower-traffic measures need adding to `donor_aliases.py`.
- Same-org-different-locals stays distinct (SEIU 1000 vs 1021,
  UFCW 770 vs 135) — intentional, not a gap to close.

---

## 11. v3 doesn't ingest monetary contributions

**Severity:** Architectural (workaround in place)
**Status:** Non-blocking follow-up

The v3 finance database (`finance_statewide_v3.db`) currently
ingests only loans (`LOAN_CD`), in-kind contributions
(`RCPT_CD` Schedule C), and independent expenditures
(`EXPN_CD` + `S496_CD`). Monetary contributions (`RCPT_CD`
Schedule A) still live in v2.

The combined read layer (`FinanceDatabase.get_combined_*`) stitches
the two at consumer call time. This works correctly but adds
plumbing: every consumer of v3 reads goes through Python merging.

**Resolution:** add a v3 monetary ingest pass (extends Phase 4)
that puts `receipt_type='monetary_contribution'` rows in
`finance_flow_v3`. Then `get_combined_*` methods can collapse into
their underlying v3 counterparts, and the concentration-None
caveat (issue #9) resolves automatically.

---

## Appendix: Quality Score Breakdown

**Current Overall Score: 86.7% (A-)**

| Dimension | Score | Notes |
|-----------|-------|-------|
| Completeness | 90.9% | Optional fields sparse (by design) |
| Consistency | 83.3% | 18 threshold mismatches remaining |
| Accuracy | 96.4% | Vote math perfect |
| Uniqueness | 80.0% | Content duplicates expected |
| Timeliness | 89.9% | 2025 gap expected |
| Validity | 52.4% | Non-standard IDs accepted |
| Summary Quality | 96.1% | 100% coverage |
| Finance Quality | 90.0% | 75% statewide coverage |
| Recommendations | 95.3% | 95% coverage |

---

## Revision History

| Date | Changes |
|------|---------|
| 2026-02-05 | Initial document created after Codex audit |
| 2026-05-20 | Phase 6 closeout: added v3-era issues #9 (concentration metrics None policy), #10 (donor canonicalization drift), #11 (v3 doesn't ingest monetary yet) |
