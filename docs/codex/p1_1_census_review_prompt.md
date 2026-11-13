# Codex review request: P1.1 county source census

**Type:** review only. Branch `phase0-election-status`.

The work is in
[`scraper/data/census/county_sources_2026.json`](../../scraper/data/census/county_sources_2026.json)
and [`docs/plans/county_census_20261111.md`](../plans/county_census_20261111.md). They cover
the 10 largest counties we don't cover yet, plus stubs for San Bernardino and San Mateo. An
agent gathered it on November 11, 2026, between 16:04 and 16:18 UTC.

## Check

1. Is the schema enough to drive a generic tool that captures a list of URLs (P1.2), and
   later each county's manifest?
2. Does every `measure_count` come from an official page? Figures from aggregators (KQED,
   NBC LA, Coleman, Ballotpedia) must appear only in `cross_checks`.
3. Are the access records honest, with nothing bypassed? In particular:
   - the note about Riverside's static files: one header request to a June PDF returned
     200 while the domain shows a challenge;
   - the follow-up fetch of Riverside's home page after its challenge;
   - the new San Francisco 403 on sfelections.org and sfelections.gov.
4. Do the slugs (`la`, `sd`, `orange`, `riverside`, `scl`, `alameda`, `sac`, `cc`,
   `fresno`, `sf`) suit becoming keys for `SOURCE_HOSTS` and `LISTING_URLS`?
5. The open questions:
   - SF: Ballotpedia counts 10, SF's own list counts 11 including RTM;
   - LA's SC: the jurisdiction differs between the list PDF and the results page;
   - Fresno J: the title conflicts between sources;
   - the multi-county measures found so far;
   - getting SF results without the blocked hosts.
6. Are the notes for P1.3 enough for two agents to split the other ~41 counties?
7. Policy: may we fetch static files on a domain whose HTML pages show a challenge? We
   propose no, unless the county confirms it or a person downloads them in a browser.

## Constraints

Review only; no live fetches against blocked hosts; no push.

## Please return

Write `docs/codex/p1_1_census_review_response.md` with:
- a verdict;
- findings ranked by severity;
- answers to questions 1–7.

Commit only that file.
