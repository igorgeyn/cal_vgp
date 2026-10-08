# County content integration review — October 8

Read-only: Read/Grep/Glob only. Do not execute commands, edit files, access
credentials/environment files, contact external services, or publish.

Review the county reader update against baseline main `7a4bccb9`. Question its
readiness and priorities; do not repeat completed source transcription reviews
unless you find contrary evidence. Statewide card redesign is deferred.

The frozen reader candidate is
`scraper/data/county_content/20261008/candidate-02/site/`. The 49-entry package
is `scraper/src/website/data/county_2026.json`. Both are stable for this review.
All 20 San Bernardino and 29 San Mateo questions/explanations were visually
checked by Codex. Separate read-only Claude reviews inspected all cited images:
five-record pilot READY WITH CONDITIONS; remaining 17 SB READY; remaining 27 SMC
READY. Raw outputs and readable copies are under the private task directory.
No question/explanation source remains unresolved. Treat these as recorded
reviews, not a substitute for investigating a contradiction.

Read:
- `scraper/src/website/county_content.py` and `local_measure_context.py`.
- Relevant county changes in `scraper/src/website/generator.py` and
  `build_measure_pages.py` (search county_guide/county_sections/county_finance).
- `scraper/tests/test_county_content.py`, `test_local_measure_context.py` and
  `scraper/scripts/check_county_content_browser.py`.
- `scraper/data/county_content/20261008/preservation.json`,
  `refresh-rehearsal.json`, `fresh-comparison.json`, `tests-final.xml`,
  `browser-final/report.json`, `statewide-final/report.json` and
  `navigation-final/report.json` if the last has finished.
- Representative actual HTML pages 12419 (known advocacy mislabel), 12442
  (five-county transit), 12443 (bond repayment), 12450 (square-foot tax), 12460
  (rent regulation), plus 320/390/1440 screenshots in `browser-final/`.

Check fail-closed identity/source binding, preservation of imported/raw fields,
thresholds, capture-vs-review dates, attribution and source access, regional
scope, honest finance fallback, historical comparison labels/links/statistics,
desktop/mobile density and interactions, and no stale county content when
opening historical or statewide records. Assess whether tests exercise actual
failure modes. Generation after a fresh ordinary registrar load retained all
49 reviews and every measure row; repeated identical input made no writes.

The pilot conditions were resolved: numeric CEDA jurisdiction labels use a
county fallback; approval requirements are visible; October 8 source rechecks
are distinguished from retained document capture timestamps; the county modal
does not use a fabricated Filed status rail. County explanations now display
in full. Existing 239 official-document groups and all raw rows remain intact.
Local campaign finance is explicitly not imported; county resources are only
lookup starting points, with city/regional filing limits explained.

Known boundaries: all county source files were recaptured October 8 and matched
September 28 on URL/role/SHA, but the production document rows still retain
their earlier capture provenance. We did not reload identical bytes merely to
change those timestamps. Forty same-county/broad-type historical cohorts link
to real older records; they are not matched on purpose or legal voting rules.
Full refresh automation, election-day status/results and Alameda remain later
batches. No production DB or live site changes have been made for this update.
Private recovery preparation is in progress; do not certify a completed upload.

Return READY / READY WITH CONDITIONS / NOT READY for this candidate, with
prioritized reproducible findings. Separate release blockers, checks still
required before release and later improvements. Identify exactly which files,
pages and screenshots you inspected; do not claim to execute tests or inspect
surfaces you did not open. Codex will adjudicate findings against evidence.
