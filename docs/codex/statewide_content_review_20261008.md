# Independent review: statewide reader content

Review the current working changes against main `7b7a4b5`. Be skeptical of the
implementation and of this description. Identify concrete defects with file/line
evidence, severity, reader impact and an actionable fix. Separate blockers from
follow-ups. Give READY, READY WITH CONDITIONS or NOT READY and say what should
happen next. Do not assume every missing advanced chart should be invented from
incompatible data. Do not treat recorded test results as tests you ran yourself.

Read-only. Do not edit files, run shell commands/tests, browse other projects,
read .env/credentials, access services, publish, or spawn agents. Read/Grep/Glob
only. User already authorized implementation and our review/publication workflow;
your job is to judge the result, not request that authorization again.

Read first: docs/plans/statewide_content_20261008.md and CLAUDE.md.
The user's latest request is to bring the statewide section up to date and make
all its components useful. Screenshot showed four old records. Live HTML/JSON
actually match the October 8 published release and contain 14 current propositions.
The actual missing parts were research, current finance, meaningful links and
reader presentation. A cache cause for the screenshot is not established.

Primary changed code:
- scraper/src/website/statewide_content.py (complete new module)
- scraper/scripts/build_statewide_content.py
- scraper/scripts/generate_site.py (projection and historical comparison section)
- scraper/src/website/generator.py (search statewide_sections/statewide_guide,
  versioned data request, card keyboard activation, future assignment rendering)
- build_measure_pages.py
- scraper/tests/test_statewide_content.py
- scraper/tests/test_statewide_ballot.py (synthetic fixture identity injection)
- scraper/scripts/check_statewide_content_browser.py

Evidence: scraper/tests/fixtures/statewide/20261008_content/{capture,review}.json,
sources/*.html and scraper/src/website/data/statewide_2026.json. Inspect enough
raw source examples to independently challenge attribution, fiscal interpretation,
pro/con ownership, supporter labels and finance table association. Especially
check Props 2/5 absence, 3 heading typo, 39 malformed money and $1 discrepancy,
45 three supporting and three opposing FPPC committees, multiple-measure money.
Check all 14 identities, election scoping, HTML escaping, unsafe links and failure
behavior under source drift. Check that source dates are honestly labelled.

Scratch evidence: scraper/data/statewide_recon/20261008_content/.
- tests-final.xml: 81 focused tests passed before last minor CSS/source-body check.
- candidate-final2/site/: newest isolated bundle (build may be finishing).
- candidate-final2/build.json and build.log: input hashes and strict build.
- preservation.json: full-record and page audit, if already present.
- browser-final/: forthcoming desktop/390/320 checks and screenshots.
Missing in-progress evidence is not evidence of a successful check; list it as a
publication condition, not a code defect. The caller is completing those checks.
Do not try to read the full 35MB measures-data.json: read package entries and
selected individual pages, e.g. measures/10960.html, 12471.html, 12477.html.

Assess: accurate, neutral, accessible, coherent Main/Research/Finance in explorer
and standalone pages; no cross-measure or historical/current finance leakage;
stable ID navigation; record/DB preservation; reproducible offline source package;
mobile/keyboard behavior; stale-data risk. Historical similarity is a selected
reading list, not a voting forecast. No finance timeline/sector/concentration is
claimed from snapshot totals. Election-day status transitions are pre-existing
open work; flag new regressions rather than making that separate project a
surprise prerequisite. Finish with prioritized findings and a concrete verdict.
