# Release: election status and history fixes (P0.4), November 12, 2026

**Code:** `f2cc8a1d` on `phase0-election-status`; published from branch
`release/p0-status-20261112`. **Approved by Igor** on November 12, 2026.

## What changes for readers

- **Status.** The 63 measures on the November 3, 2026 ballot no longer read "Upcoming". Status
  follows the reader's California date: "Results pending", with an official-results link where
  one has been checked (P0.1).
- **History lists.** On the 40 county measures with a history list, each past record is labeled
  by what CEDA's code supports ("City measure", "County or special district measure", "School
  or college district measure", "Local measure"), not with the county's name. The loader's
  "<COUNTY> Measure <X>" placeholder titles are no longer shown under the links (P0.2, review
  N1).
- **"Result unknown".** Past measures with no recorded outcome say so on cards and in the
  detail window, not "Pending" (P0.2b).
- **Hidden for renovation:** Insights (`SHOW_INSIGHTS = False`) and Explore
  (`SHOW_EXPLORE = False`). Explore returns via "Honest Explore"
  ([plan](explore_renovation_plan_20261112.md)).

## Evidence

Private, gitignored: `scraper/data/county_content/20261112_p0/`.

- **Build.** A fresh frozen workspace (the October 8 recovery workspace plus current code; 284
  inputs) ran a strict build as of 2026-11-12. The production DB and finance DB copies are
  logically identical to production. The build did not change its DB copy.
- **Compared with the published root:** 12,372 IDs unchanged. **Exactly 63 measure pages
  change**, the current-election measures; 12,309 are byte-identical; no historical row
  changes. JSON changes only `election_status` (63), `official_results` (63),
  `county_sections` (40) and `local_historical_context` (40), plus the known `last_seen_at`
  regeneration (129). The finance, insights, topics, recommendations and quiz payloads are
  unchanged. `sitemap.xml` changes only its two build dates.
- **Browser checks, all 0 failures:**
  - status at the real clock (63 rows, 1440/390/320 px);
  - status across Pacific midnight, Nov 12 to 13;
  - county content (49 measures × 3 widths);
  - Grid/List navigation, including the hidden Insights and Explore paths.
- **Tests at `f2cc8a1d`:** 730 passed, 1 skipped. Known baseline failures: `test_models` (1),
  and `test_database` / `test_deduplication` (17 errors). Two worktree-only artifacts pass in
  the main tree: SMC fixture CRLF, and a parser test exceeding the Windows path length.
- **Reviews:** P0.1 by Codex (`b2ab1fba`, `4fcf12b6`). P0.2/P0.2b/R7 by an independent Claude
  agent standing in for Codex (`482c8f15`); its findings N1 and N2 were fixed in `c1683de5`.
- **Recovery:** update `2728598b60034b7cf2ff48d13f02b658c8a86b2157b16bb52de1e90d2217ec80`, which
  chains onto the October 8 county-content update. Restore-verified (284 inputs, 12,382 public
  files) and stored in private R2 with a read-back of every object.
- **Not in this release:** the results-link recheck and the P0.3a checker change (decision a),
  the CEDA repair (P1b) and the follow-up flag on the 29 wrong historical records.
