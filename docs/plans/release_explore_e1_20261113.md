# Release: Explore E1 "Honest Explore", November 13, 2026

**Code:** `2a06d4ba` (identical code at `78d8df0d`, which includes `main`). Published from
branch `release/explore-e1-20261113`. **Approved by Igor** on November 13, 2026.

## What changes for readers

Explore is back (`SHOW_EXPLORE = True`), rebuilt so it doesn't state numbers the data can't
support:
- **Default view:** measure type by decade, with real-year labels ("1998–99" … "2020–24").
- **Coverage line:** says what is counted and what isn't, including the 63 current-election
  measures awaiting results.
- **No pooling:** Measure Type counts local measures only; Topic shows Local or Statewide, never
  both pooled.
- **Small groups:** groups under 5 show counts only. County and Passed/Failed filters also give
  counts only, with a caution.
- **Removed:** threshold mode, close calls, the trap metric, the summary cards, "Difference from
  column rate", and the modal's decade bars.
- **Design:** one neutral color with dark text (minimum contrast 7.06:1).
- **Filters:** visible inside Explore, with Clear; drill-downs keep the county and level.

Insights stays hidden.

## Evidence

Private, gitignored: `scraper/data/county_content/20261113_e1/`.

- **Build:** a fresh frozen workspace (the November 12 workspace plus current code; 287 inputs)
  ran a strict build as of 2026-11-13.
- **Compared with the published root:** **0 of 12,372 measure pages change.**
  `measures-data.json` differs only in the known `last_seen_at` regeneration (129). The
  finance, insights, topics, recommendations and quiz payloads are unchanged. `sitemap.xml`
  changes only its two build dates. `index.html` has 64 hunks, all Explore.
- **Browser checks, all 0 failures:** Explore at 1440/768/390/320, including a real county
  drill-down; status at the real clock and across Pacific midnight; county content; Grid/List
  navigation.
- **Reviews:**
  - E1 by an independent Claude reviewer and by Fable;
  - fix pass by Codex (`3c426967`, which found the county drill-down blocker);
  - fix pass 2 rechecked by Codex (`2a06d4ba`, **ready to release**).

  The Grid/List DOM is identical to the pre-E1 baseline. Full suite: 760 passed, baseline only.
- **Recovery:** update `62fe3f538c6528e19980ca5e3accd5ea3bf7a6f1f6b88047aea908fc079f961f`. It
  chains onto the November 12 update and is restore-verified (287 inputs, 12,382 public files).
  It is stored in private R2 at `recovery/20261113-explore-e1/` with a read-back of every object.

## Follow-ups, not in this release

- E2c (transpose, phone list, trend chart): after P2(c).
- Minor: a sparse empty view with carried-over filters; "Min n" stays enabled under count-only.
- Before results import: gate 2026 outcomes out of Explore until certified (P2(c)).
