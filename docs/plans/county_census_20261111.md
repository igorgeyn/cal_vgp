# County source census, P1.1 (November 11, 2026)

**Chunk:** P1.1 of the [local-measures plan](local_measures_completion_plan_20261105.md)
(Phase 1, "freeze the sources"). **Data:**
[`scraper/data/census/county_sources_2026.json`](../../scraper/data/census/county_sources_2026.json),
schema version 1. **Scope:** the 10 largest counties not yet covered, plus stub entries for
San Bernardino and San Mateo. All checks were made November 11, 2026, 16:04-16:18 UTC, with the
project User-Agent. Nothing was bypassed, nothing was written to the database, and nothing
was committed.

## Summary

| County | Measures listed | List format | Document host(s) | Results formats | Access |
|---|---|---|---|---|---|
| Los Angeles | **68** (2 county + 66 local) | 14-page text PDF; results page also lists all 68 with questions and thresholds | content.lavote.gov (list only); city clerks for analyses and text (unverified) | HTML text results; 97 MB precinct PDF | ok |
| San Diego | **20** (from results) | No county list; the "measures" PDF is a calendar | sdvote.com per-jurisdiction PDFs (mixed text and scans); city clerks | HTML ENR; CSV summary, contest and precinct (JS buttons, not fetched) | ok |
| Orange | **15** (A-O) | HTML letters page | ocvote.gov, one text PDF per measure | HTML ENR; CSV and PDF reports | ok |
| Riverside | unknown (aggregator: 17) | none read | unknown | unknown; earlier 2026 results were static PDFs | **bot challenge** (Cloudflare) |
| Santa Clara | unknown (aggregator: 19 + RTM) | none read | unknown | unknown | **403 block** (Cloudflare WAF) |
| Alameda | **28** (incl. RTM) | HTML fragment with questions and thresholds | acvote.alamedacountyca.gov, one scanned packet per measure | HTML only; CVR by request | ok |
| Sacramento | **9** (+ F withdrawn) | HTML accordion with questions, analyses, arguments | elections.saccounty.gov (inline HTML) | HTML summary report (SEMI-FINAL); Enhanced Voting app | ok |
| Contra Costa | unknown (aggregator: 12 + RTM) | none read | todb.ca.gov serves at least one county PDF | unknown | **empty 202** (AWS WAF) |
| Fresno | **9** | Letters PDF; election page | fresnocountyca.gov, per-role PDFs, scanned | HTML; dated summary PDF | ok |
| San Francisco | **11** (A-J + RTM) | sf.gov HTML, letters and titles | api.sf.gov, scanned PDFs (119 links) | unknown | **partial**: sf.gov open; sfelections.org and sfelections.gov 403 |
| *San Bernardino* | *20 held* | *covered (stub)* | *uploads.rov.sbcounty.gov* | *HTML, xlsx* | *ok (Nov 7)* |
| *San Mateo* | *29 held* | *covered (stub)* | *smcacre.gov* | *HTML, precinct CSV* | *ok (Nov 7)* |

**Counted from official pages: 160** (LA 68, SD 20, Orange 15, Alameda 28, Sacramento 9,
Fresno 9, SF 11). RTM is in two of these lists (Alameda, SF), so 159 distinct measures.
**Aggregator-only: about 50** (Riverside 17, Santa Clara 20, Contra Costa 13, with RTM in the
last two). Across the 10 counties that is about **207 distinct measures**, with roughly 50 of
them unconfirmed.

## Blocked or list-less counties

- **Riverside:** Cloudflare "Just a moment..." challenge (403) on www.voteinfo.net, as in
  August. A search-indexed June results PDF under `/sites/g/files/aldnop371/files/` answered a
  HEAD with 200, so static files appear unchallenged. I did not guess the November path. One
  WebFetch of the home page also got 403.
- **Santa Clara:** Cloudflare "Attention Required!" 403 on vote.santaclaracounty.gov, as in
  August. No alternate official results host was found. Igor is checking access (Decision 4).
- **Contra Costa:** HTTP 202, empty body, AWS load balancer, as in August. todb.ca.gov served a
  Contra Costa handbook PDF without a challenge; whether it also holds measure documents is
  unknown.
- **San Francisco (new):** sfelections.org and sfelections.gov now return a CloudFront 403
  ("Request blocked") to the project User-Agent, including the November results index
  `results/20261103w/`. The earlier manifest recorded 200 for sfelections.org. The measure list
  and documents now live on sf.gov, which is open, so only results are blocked.
- **List-less:** San Diego publishes no county measure list. The calendar PDF tells readers to
  contact each city clerk. The results page names all 20 contests with thresholds, so it serves
  as the list, but it has no question text.

## Cross-checks

| County | Census | Plan verified | Ballotpedia Oct 21 | Coleman tax rows (heuristic) | Other aggregator |
|---|---|---|---|---|---|
| Los Angeles | 68 | 68 | 68 | 35 | |
| Alameda | 28 | 28 | ("1 to 28" for the rest) | 20 | |
| Orange | 15 | 15 | | 10 | |
| San Francisco | 11 | 11 | **10** ("in the city of San Francisco") | 3 | |
| San Diego | 20 | | | 15 | |
| Sacramento | 9 | | | 4 | |
| Fresno | 9 | | | 8 | |
| Riverside | | | | 11 | NBC LA: 17 |
| Santa Clara | | | | 9 | KQED: 19 + RTM |
| Contra Costa | | | | 9 | KQED: 12 + RTM; CoCoTax: 12 |
| San Mateo | 29 held | | 29 | 16 | |
| San Bernardino | 20 held | | | 15 | |

- The census matches all four counts the plan verified.
- **SF discrepancy:** the plan says "San Francisco 11 is Ballotpedia's figure", but the
  article, read through WebFetch, says ten measures in the city of San Francisco. That figure
  probably leaves out RTM. The SF list page shows 11 including RTM.
- The Ballotpedia article gives county counts only for LA (68) and San Mateo (29). Its
  `ballotpedia.org` wiki pages came back empty through WebFetch; I did not retry.
- The Coleman column comes from a heuristic parse of the Nov 4 PDF. It covers tax measures
  only and undercounts: on the covered counties it finds 31, where the plan verified 35. Treat
  it as a lower bound.

## Schema rationale

- **One object per county**, keyed by `county_slug`. The slugs reuse the repo's `sb` and `smc`;
  the new ones (`la`, `sd`, `orange`, `riverside`, `scl`, `alameda`, `sac`, `cc`, `fresno`, `sf`)
  are short and stable, so they can become keys in `SOURCE_HOSTS` and `LISTING_URLS` when those
  constants become data (Trap 6).
- **Each URL carries its own access record** (status, final URL, `checked_at`, Last-Modified).
  A county can be partly open: SF's list is open while its results are blocked. The county-level
  `access.state` is a summary only.
- **Results pages used as lists are marked with a `role`.** San Diego's results page is its
  only list; LA's results page and its list PDF are independent and agree.
- **`measure_count` is null unless an official page was counted.** Aggregator numbers stay in
  `cross_checks`, never in the count, per the authority line in Trap 4. Every entry has an
  `unverified` list.
- **Documents record `pdf_text` from a sample** (text, scanned or mixed), because scans decide
  whether Phase 4 needs visual checks: Alameda, Fresno and SF documents are scans; Orange's are
  text; San Diego's are mixed.
- **Results record the status label and timestamp verbatim.** Counties label the same stage
  differently: "UNOFFICIAL", "Preliminary/Unofficial", "SEMI-FINAL", "semifinal official canvass".
  Phase 2's observation store needs the exact text.

## Open questions

1. **Riverside static files.** Fetching unchallenged static PDFs under a challenged domain at a
   *guessed* November path is close to bypassing. This belongs in the bot-challenge decision
   Claude is drafting for Codex.
2. **SF results.** The block on sfelections.org and sfelections.gov is new. It may target the
   User-Agent or be an election-period WAF rule. Ask SF, or check in a normal browser the way
   Igor checked the SOS link.
3. **Santa Clara: San Jose.** Ballotpedia says San Jose has one measure, but KQED's A-S list
   has none. Unresolved until the county is readable.
4. **LA documents.** No county index of impartial analyses or full text was found; city clerk
   sites are the likely hosts. The question and threshold are in the county PDF already, so
   this matters only for documents.
5. **LA jurisdiction for SC.** The list PDF prints SC under an "LAUSD" header; the results call
   it an LA City measure. This needs a review rule.
6. **Fresno J title.** The letter PDF says "Transactions and Use Tax"; the results say
   "Transient Occupancy Tax"; the document folder is `coalinga-sales-tax`.
7. **Download endpoints.** The San Diego and Orange CSV reports and LA's precinct PDF exist but
   were not fetched. P1.2 capture should resolve the San Diego and Orange `DownloadReport()`
   URLs.
8. **Multi-county measures seen:** RTM (5 counties); LA LV (with Ventura); Sacramento E (with
   Placer) and H (Los Rios, with Yolo); Riverside B and Y (with San Bernardino). The list is
   partial.

## What the P1.3 census (remaining ~41 counties) should watch for

- **The "measures" PDF may be a calendar** (San Diego). Check the content, not the filename.
- **Results pages can serve as lists.** Platforms seen: livevoterturnout ENR (San Diego,
  Orange), static ES&S summaries rendered as HTML (Sacramento, Fresno), Enhanced Voting apps
  (Sacramento), county CMS pages. The ENR contest names carry thresholds.
- **Letter-assignment PDFs** (Fresno) give a stated total; record it verbatim.
- **Hosts move.** SF moved to sf.gov, Contra Costa assets appear on todb.ca.gov, and San
  Diego's results redirect to a vendor domain. Record every host, because SOURCE_HOSTS
  validation is per county.
- **Blocks change both ways.** SF is newly blocked; the August blocks persist. Recheck any
  county the manifest calls open.
- **Withdrawn measures** stay listed (Sacramento F). Count them separately.
- **Multi-letter and non-letter designations:** LA HOM, PRK and SOS; Alameda, SF and the
  others' RTM; SF's "Proposition".
- **Scans are common.** Sample one PDF per county and record text, scanned or mixed.
- **Timestamps are perishable.** Store each results label and "as of" text verbatim with
  `checked_at`. Several counties update on Tuesdays and Fridays until about December 1-3.
- **Aggregators are uneven.** Ballotpedia's article has no per-county table for most counties,
  and its wiki pages return empty. KQED covers the Bay Area and NBC LA covers SoCal; Coleman
  covers tax measures only.
