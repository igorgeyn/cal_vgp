# Independent county-content pilot review

Read-only. Use only Read/Grep/Glob. Do not execute commands, edit files, access
credentials or environment files, contact external services, or publish.

We are prioritizing useful content for the existing 20 San Bernardino + 29 San
Mateo records before expanding counties. Challenge that priority if evidence
warrants it. Then examine this five-record pilot before the format is repeated.

Baseline main: 7a4bccb9ebd7273c78942f8d47e993cf47a309dd. Pilot is a local preview,
not published. Fresh county capture is in progress separately; the source PDFs
here are the September 28 archived bytes. Do not certify October freshness.

Frozen pilot content:
`scraper/data/county_content/20261008/pilot/content.json`.
Frozen site: same directory, `site/`; browser evidence: `browser/` and report.json.
There are 5 reviewed questions/explanations. Other 44 records remain document-only
in this pilot. Statewide design is out of scope. The implementation may continue
evolving while you review; bind your content verdict to this frozen packet.

Read every cited question page image in
`scraper/data/county_content/20261008/images/`:

- 12418-text-1.png (SB Y)
- 12419-resolution-4.png (SB Z)
- 12420-text-1.png and 12420-text-2.png (SB A)
- 12442-text-8.png, 12442-analysis-1.png, 12442-analysis-2.png (regional transit)
- 12443-text-11.png, 12443-text-12.png, 12443-analysis-1.png,
  12443-analysis-2.png (Burlingame R, scanned packet)

`ledger.json` at the parent directory identifies full private PDF paths/hashes.
Question layout and whitespace may be normalized; wording/amounts/qualifications
must match. Check assessed vs market value, authorization vs repayment, annual vs
total receipts, districtwide vs county revenue, uncertainty, duration, neutrality,
actual impartial vs advocacy roles, and multi-page/multi-measure attachment.
SB Z's purported impartial PDF is actually an argument in favor; the explanation
therefore cites the resolution. Check that the public distinction is sufficient.

Review the rendered modal/card screenshots for usefulness, density, source
visibility, and mobile behavior. Critique whether these facts are the right
reader information. A browser report is evidence of executed checks, not your
own execution. Full question and explanation should also appear on each of the
five `site/measures/<id>.html` pages.

Implementation context (may evolve):
- scraper/src/website/county_content.py
- scraper/src/website/local_measure_context.py
- scraper/tests/test_county_content.py
- scraper/scripts/check_county_content_browser.py

27 focused tests and all 5 records at 1440/390/320px passed before this request.
Source-byte changes must require re-review; identical bytes in a newer capture
must preserve review. Database fields are retained; the versioned content package
owns separate display fields. Historical links are same county/broad type, not
predictions or equivalent legal thresholds. Campaign-finance ingestion is not
part of this pilot.

Return READY / READY WITH CONDITIONS / NOT READY for repeating this format,
then prioritized, reproducible findings. Separate content blockers from later
improvements. State precisely which source images and reader surfaces you could
inspect. Do not certify unreviewed records or claim checks you did not perform.
