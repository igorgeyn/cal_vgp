# Release and county-content work — October 8, 2026

Status: **published and verified** at https://cal-vgp.igorgeyn.com/.
Content release: `39116027510773e988b33b307bf9a44dde599654`.
GitHub Pages run [37844458073](https://github.com/igorgeyn/cal_vgp/actions/runs/37844458073)
deployed successfully on October 8 at 14:07:36 Pacific (21:07:36 UTC).
All 22 checked served artifacts match the reviewed bytes, and live desktop/mobile
checks pass for the 14 statewide cards, withdrawn ACA 13 route, Measure Z
correction, and representative Finance. No registrar capture was triggered.
The October 3 candidate is superseded by the corrected candidate described here.
The user's October 8 instruction authorized proceeding with review/publication.
Both requested Claude reviews completed through the installed CLI with only
Read, Grep and Glob tools. Codex assessed the findings and performed the checks.

## Reader-facing issue found during source inspection

San Bernardino City Unified School District, Measure Z (ID 12419), has the same
PDF linked as both **Impartial** and **Argument For** on the county's measure page.
The one-page PDF is headed **Argument in Favor of Measure Z** and advocates a
yes vote. This is a county source-label problem, faithfully captured by the
parser, not evidence that the PDF contains an impartial analysis.

- [County listing](https://elections.sbcounty.gov/elections/2026/1103/measures/)
- [Actual argument PDF](https://uploads.rov.sbcounty.gov/ROV/Elections/2026/1103/Measures/SBCityUSD/AIF_SBCUSD.pdf)
- SHA-256: `297f20d5de893e76970be47c8f25f4cd66a69757ee5cea4fe762e8afa854631e`
- The full live PDF was retrieved October 8 and matches the archived bytes.
- Independent-review fixture: `scraper/tests/fixtures/document_roles/`.

The correction preserves both raw source-role associations in SQLite. The
public projection labels these exact bytes **Argument in favor** and states
that the county also calls it an impartial analysis, but a separate analysis
has not been verified. `source_roles` preserves the original attribution in
the public data. Modal and standalone page both display the correction.
A changed PDF at that URL, still labelled as analysis, stops the build for
reinspection. Legitimate combined packets elsewhere retain all their roles.
No guessed replacement URL, newly invented analysis or new summary is inserted.

The correction changes one public document group, not its URL/hash or the
272 raw stored roles. There are still 49 county records and 239 grouped links.
Public role associations fall from 272 to 271. The preservation checker allows
only this exact correction and checks every other document against its baseline.
Capture wording now means retrieval, not a claim that every PDF was read.

## Cutover implementation

`scraper/scripts/promote_statewide_release.py` is separate from the scratch-only
reconciler; the latter's production guard remains intact. The cutover:

1. Verifies pinned baseline and candidate files, distinct paths, no symlinks or
   hard links, and the actual SQLite sidecar/journal state.
2. Takes `BEGIN EXCLUSIVE` with no wait. Existing readers/writers cause refusal.
3. Rechecks the complete target against the baseline while holding that lock.
4. Writes and flushes a fresh exact-byte backup before any database mutation.
5. Changes only four existing rows, inserts eleven and adds the two review tables.
6. Checks integrity, foreign keys, all rows/schema/sequences and the complete
   search-index token/document/column/offset set before committing.

The real 20 MB production copy passed this cutover rehearsal and the independent
whole-database/public-projection preservation gate. The first rehearsal rejected
different FTS binary segment packing and rolled back. The corrected comparison
uses the actual indexed vocabulary, as documented by
[SQLite's FTS5 vocabulary interface](https://www.sqlite.org/fts5.html#the_fts5vocab_virtual_table_module),
and preserves FTS document sizes/configuration. It does not equate external-content
`SELECT *` with an index check. Focused tests exercise lock contention, baseline
drift, indexed-token drift, sidecar refusal and rollback after inserted rows.

This is database writer exclusion. The site is static on GitHub Pages: publish
the matching complete artifact set as one Git revision after local verification.
Do not claim a single transaction across SQLite and Git. If local site staging
fails, do not push; retain the backup and restore the matching local state.

## Freshness and operations

Local HEAD and remote main were both
`ec650a290992da7c7f903800419e59b523de8e9d` at the October 8 preflight.
The production DB/site and all eight pinned build inputs are unchanged.
The known running Python services belong to other projects; none were stopped.
Production uses DELETE journal mode and had no WAL, SHM or journal sidecars.

The October 5 scheduled registrar run
[37368780103](https://github.com/igorgeyn/cal_vgp/actions/runs/37368780103)
failed before any job step: GitHub could not acquire a hosted runner. This was
not a parser failure and produced no capture. R2 still contains ten SB and five
SMC snapshots, latest September 28. Their previously checked contents match the
accepted September 7 loaded vintage. Do not relabel these as October captures.
The missed refresh remains an operational follow-up; no scraper was started.

The official statewide list was reread October 8: the same 14 propositions and
ACA 13 withdrawal remain. Per-proposition descriptions were last checked October 3.

## Exact review locations

Scratch root: `scraper/data/statewide_recon/20261008_release/`.

- `candidate-final/site/`: corrected complete public bundle.
- `workspace-final/`: frozen build inputs with the local model; no credentials.
- `candidate-final/build.json` and `build.log`: actual strict build.
- `rehearsal-promotion.json`, `rehearsal-preservation.json`: successful full-DB cutover.
- `z-live-pdf-check.json`: full live PDF checksum, not a header-only probe.
- `tests-final.xml`: final focused suite; earlier failed fixture attempts remain
  separate. A test SQL placeholder count was corrected before this final run.
- `claude-request.md`, `claude-result.json`: independent review request/result.
- `production-promotion.json`, `production-preservation.json`, `public-promotion.json`:
  actual successful cutover and checks of the production paths.
- `staged-verification.json`: the committed public inventory and 28 machine-read
  fixtures match their reviewed bytes. `.gitattributes` prevents Git newline
  conversion from invalidating source evidence or changing served artifacts.
- `deployment-verification.json`, `live/`: 22 actual served hashes and both
  browser viewports. External browser requests were blocked; the live official
  Measure Z PDF was verified separately.

The normal release push was accepted using the account's existing administrator
exception to the pull-request rule; no repository protection setting was changed.
The release-receipt documentation update uses a pull request. The rule requires
zero approving reviews and does not enforce protection for administrators.

The original private R2 recovery archive remains immutable and valid for the
October 3 baseline/candidate. The October 8 update is separately sealed, restored,
rebuilt and read back from the private bucket. It contains 97 files and is
7,784,704 bytes; SHA-256
`a9c0d56163c0d195c4eee14cb2414e8e7fa8919a197ace89fb9605e9e90c3607`.
R2 prefix: `recovery/20261008-release/` followed by that hash. Keep both archives:
the update depends on the base archive's model, data, baseline and county sources.
All 190 composed workspace inputs and 12,382 public files were verified. The
restored-input strict rebuild preserved all 12,372 records, except the known 129
generated export timestamps, and 12,380 public files matched byte for byte.
The exact promoted production database is also stored and read-back verified
under this recovery prefix. No bucket-access settings changed.

Both Claude reviews and the Codex disposition are now recorded in the
[review record](statewide_release_claude_review_20261008.md) and
[release evidence](statewide_release_evidence_20261008.json). The combined review
was READY WITH CONDITIONS; the bounded Measure Z follow-up was READY. Claude's
claim about a missing prior review was its own still-empty output file, not an
additional missing review. Its FTS documentation finding was valid and is now
addressed in `docs/DATA_PIPELINE.md`; schema/index-maintenance changes remain
outside this release. Current-source/hash checks and the real production
preservation gate passed. **97 focused tests** and desktop/mobile browser checks
pass, including the Measure Z note in both readers.

## County content prepared next

`county-content/index.json`, `inventory.md` and `text/` contain a private review
packet for all 49 records, with source URLs, SHA-256 hashes, page counts and
extraction warnings. It uses only the already archived PDFs: 122 distinct files,
87 with text extraction and 35 without enough extracted text. Seven PDFs emit
extraction warnings, including five with damaged compressed streams. Extracted
text is not automatically approved content.

All 20 SB records have extractable county-labelled analysis links; one is the
mislabelled Measure Z argument above. SMC has extractable analysis-labelled files
for only 9 of 29 records, and extractable text/resolutions for 14. Some shared
packets cover several measures; identity and page location must be verified.

Next content sequence: SB official ballot questions and short sourced explanations,
then SMC with visual transcription/OCR where required. Verify the question against
the rendered source page, and source each explanation to official text or a
verified impartial analysis. Keep advocacy separate. No content has been loaded
or published from this preparation packet, and no additional county is enabled.
`county-content/first-three-drafts.md` and its source-pinned JSON companion contain
the first drafts for SB Measures Y, Z and A. Questions were checked against the
rendered source pages; explanations remain drafts for the next content batch.

Igor accepted the October 8 order: this release, richer content for the existing
49 county records, Alameda, then a fresh SF/Contra Costa source assessment.
Keep the missed refresh visible and continue the remaining operations/election/
results work; neither more county names nor a release receipt completes it.
