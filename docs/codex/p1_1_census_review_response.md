# P1.1 county source census review

**Verdict: ready with changes as a research census; not yet ready as the executable P1.2 input or the final P1.3 schema.** The inventory usefully separates blocked counties and aggregator counts. Before automation, normalize access/provenance fields, establish an explicit capture queue and stop rule, and resolve the Orange slug convention. Keep the substantive source conflicts open rather than choosing a source by convenience.

Reviewed November 12, 2026, on `phase0-election-status` at `28cfbe06`. I read both census files, the Phase 1 and execution plans, relevant registrar infrastructure/legacy guidance, county-content validation and the recent bot-challenge ruling. I ran a read-only Python structural/arithmetic audit. No network requests, database access, downloads or code changes were made. This is an audit of the recorded evidence, not independent verification of the live county pages or the gathering agent's complete request history.

## Findings, ranked by severity

### F1 — P1: capture eligibility and stopping behavior cannot be inferred safely

**Evidence:** `scraper/data/census/county_sources_2026.json:473` labels the Riverside file “ok for a search-indexed file URL (HEAD)” despite the county's recorded block. `:458` records another WebFetch after the challenge. The note generalizes one HEAD result to static files (`docs/plans/county_census_20261111.md:38`). The execution plan says to record a block and move on (`docs/plans/agent_execution_plan_20261111.md:14`).

There is also conflicting inherited guidance: `docs/LESSONS_LEARNED.md:292`, `docs/plans/registrar_manifest.md:107`, and `scraper/src/scrapers/registrar/base.py:12` describe browser execution as the response to Riverside's challenge. Reusing the base class does not itself implement the current stop rule: its requests path accepts a non-error response such as empty HTTP 202, and its response conversion does not reject HTTP 200 challenge bodies (`base.py:461`, `:541`).

**Fix:** mark Riverside static URLs as discovery-only, blocked from automated capture pending the disposition in answer 7. Record the post-challenge attempts explicitly; stop saying their existence proves a general static-file exception. P1.2 must enforce the current block policy before dispatch and at each redirect, reject challenge/empty-block responses as usable source content, and disable challenge-solving fallback. Preserve diagnostic evidence separately from election content. Supersede the conflicting legacy instructions in a later authorized documentation change. These are concrete handoff risks; this review did not execute any challenged request.

### F2 — P1: version 1 is descriptive JSON, not a validated capture contract

**Evidence:** the `schema` at `county_sources_2026.json:8` is prose. Across the 32 list/results URL entries I found ten access values, including absent, `ok (HEAD only)`, `ok (redirect)` and `ok (shell only)`. Nine lack `checked_at`; 30 omit `final_url`. Some missing values are appropriate for unattempted URLs/stubs, but the record does not distinguish them consistently. Only nine of 13 document-host entries provide an example URL; examples are not a document inventory. CSV buttons remain unresolved (`:307`, `:420`). Sacramento's HTTP 200 app shell is explicitly unread (`:811`).

The note's claim that each URL has its own complete access record (`county_census_20261111.md:86`) is therefore too strong. A program cannot treat all `ok*` values as body-verified or enumerate all documents from this file.

**Fix:** define and validate typed source records and a separate approved capture list, as in answer 1. Represent attempted/not-attempted, HEAD/GET, shell/content, access outcome and provenance separately. Preserve unknown metadata as unknown; never copy a county timestamp onto an undocumented request. Deduplicate a URL used for multiple roles while retaining those roles. Resolve report endpoints only through allowed, ordinary source navigation; leave unresolved reports as tasks, not invented URLs.

### F3 — P2: count attribution is mostly sound, but verification and uniqueness are overstated

**Evidence:** all seven non-null counts for newly surveyed counties have an official-page count method and matching designation-array lengths. Riverside, Santa Clara and Contra Costa are null. However, the SB/SMC counts are explicitly held-record counts (`county_sources_2026.json:1167`, `:1230`), not counts newly made from official pages. Source downloads were retained only in the gathering session's scratchpad (`:6`); no artifact/checksum references accompany the count assertions. Thus the stated 159 “distinct” measures (`county_census_20261111.md:29`) relies on the known RTM overlap and an incomplete multi-county inventory, not a completed identity reconciliation.

**Fix:** distinguish `official_list_count`, `held_count` and `cross_check_count`, with source IDs and evidence locators. Link preserved artifacts when recoverable; otherwise identify a count as reported from an earlier observation, pending reproducible capture. Label 160 as county listings and 159 as provisionally distinct after the known duplicate. Keep approximately 207 explicitly mixed official/aggregator evidence. Do not promote the heuristic Coleman count to a guaranteed lower bound merely because it undercounts two known counties; false matches have not been ruled out.

### F4 — P2: slugs are usable, but the host mapping is not directly compatible

**Evidence:** the 12 county slugs are unique. However, existing storage documentation and recon CLI examples use `oc` for Orange (`scraper/src/scrapers/registrar/storage.py:45`; `scraper/scripts/recon/probe.py:116`), while this census uses `orange`. This demonstrates a convention conflict, not proof of existing Orange production snapshots. The document `host` values also include “city clerk sites” and `api.sf.gov / media.api.sf.gov` (`county_sources_2026.json:281`, `:1082`). Current `county_content.py:63` validates one exact hostname per county, not such labels or multiple hosts.

**Fix:** choose a canonical slug registry before capture creates persistent keys. Prefer the existing `oc` convention, with `orange` as an explicit alias, unless a reviewed inventory establishes a reason to choose otherwise. Preserve `sb`/`smc` and existing IDs. Represent each exact host separately with its role and official delegation/redirect evidence; keep unverified city-clerk leads outside the allowlist. Replace single-host assumptions deliberately rather than relaxing validation to arbitrary subdomains or free text.

### F5 — P2: unresolved identity and scope claims need structured dispositions

**Evidence:** LA SC's conflicting jurisdiction is in notes (`county_sources_2026.json:190`), yet not in that county's `unverified` list. Fresno J's conflicting tax title is recorded at `:1026`, while Fresno's `unverified` array is empty. Sacramento's cross-county E/H memberships are attributed to Coleman in a general note (`:833`), then summarized without that qualification in the census note's multi-county list (`county_census_20261111.md:120`). P1.3 only has a north/south split in prose, without an explicit county ownership roster.

**Fix:** add structured issues with affected contest/field, competing source assertions, evidence, owner and resolution status. Label aggregator-derived membership as provisional until officially supported. Do not allow a captured but unresolved measure to enter a jurisdiction/type cohort or receive a combined result. Establish disjoint P1.3 assignments and a shared multi-county reconciliation ledger before two agents extend the schema independently.

## Answers to questions 1–7

### 1. Is the schema sufficient for P1.2 and later manifests?

It is sufficient for **human discovery and choosing initial sources**, not unattended capture or a per-measure manifest. Do not require all eventual contest metadata before capturing allowed sources, but make the capture boundary explicit.

A minimal revised contract should separate:

- **County/election identity:** canonical slug, county name, election date, coverage state and reviewed host relationships.
- **Source identity:** stable source ID, exact URL, role(s), source election date where known, official referring page/discovery method, and whether it is an approved capture target or only a lead. Riverside's June example must not become November evidence merely because the census has a top-level November date.
- **Access observation:** request method, client/UA, actual time, HTTP status, final URL/redirect evidence, normalized access state, body inspected/captured flag and content type. HEAD metadata, HTTP 200 app shells, observed download buttons and downloaded content are different facts. A sampled scan classification describes that sample; it does not establish every county PDF's format.
- **Capture result:** source ID, immutable artifact reference, checksum, byte count, capture time and failure/skipped disposition. Use the existing snapshot storage and manifest-last mechanism; do not declare a planned URL successfully captured because its county summary says `ok`.
- **Claims/issues:** count basis and locator, active versus withdrawn count, completeness unknown/verified, exact source status/as-of text, and unresolved conflicts. Later manifests add contest identity, documents by role and canonical multi-county keys; a letters array alone is not a contest identity map.

Keep county access as a derived summary. Validate enums, timezone-aware times, duplicate IDs, URL/host relationships and field applicability. An unfinished report endpoint need not block capturing a valid list, but the capture receipt must show the omission. Add byte limits/streaming handling for the known 97 MB LA PDF. Reuse base-class robots/rate-limit behavior with an explicit project UA configuration; the census's “robots not consulted for single fetches” is not a P1.2 exemption. The execution plan's UA decision remains outstanding; do not silently inherit the personal-email default or change identity in response to a block.

### 2. Does every measure count come from an official page?

**For the seven newly counted counties, the recorded attribution says yes. For all 12 entries literally, no: two are held-data stubs.** I found no aggregator-only number copied into a newly surveyed county's `measure_count`.

| County | Count | Recorded official basis |
|---|---:|---|
| Los Angeles | 68 | PDF's 2 county + 66 local; independently reported 68 local results headings |
| San Diego | 20 | County-linked vendor results headings; completeness explicitly unresolved |
| Orange | 15 | Assigned letters A–O, also reported in results |
| Alameda | 28 | Measure headings, PDF links and results names |
| Sacramento | 9 | Active accordion/results entries; F separately withdrawn |
| Fresno | 9 | Letter-assignment PDF total and results letters |
| San Francisco | 11 | Official list A–J plus RTM |

The audit reproduced 160 listings and all seven designation-array lengths. Deduplicating the reported Alameda/SF RTM yields 159 provisionally distinct contests within those seven counties. Adding the three aggregator counts gives 210 listings; deducting three repeated RTM appearances across the resulting four RTM counties gives approximately 207, **assuming no other overlaps**. SB/SMC are outside that ten-county arithmetic; RTM already exists in SMC, so these are not automatically net-new database records.

The null counts for Riverside/Santa Clara/Contra Costa must remain null. Keep their 17/20/13 and other aggregator figures solely as attributed cross-check claims. The prose summary may quote those estimates if it labels them as estimates, as it currently does. Link the SB/SMC held counts to the existing ledger rather than claiming a fresh official count. None of these live counts was independently re-counted in this review.

### 3. Are the access records honest, with nothing bypassed?

They disclose the important limitations, but **“nothing bypassed” cannot be independently certified from this evidence package**. No supplied record demonstrates successful circumvention. That is different from confirming adherence to the stop rule.

- **Riverside static file:** one HEAD reportedly returned 200 and a PDF content type for an earlier-election URL. It proves neither a successful GET nor readable PDF content, access to November files, or general availability of the directory. `www.voteinfo.net` and `voteinfo.net` must not become interchangeable success claims or alternate ways to continue around the block. Record the exact method/URL/time/client and retain the header evidence if available.
- **Riverside follow-up:** the disclosed WebFetch after a challenge was an additional client attempt at the blocked home page. It failed too; it was not a successful bypass. Under the current “record and move on” workflow it should nevertheless be documented as a stopping-rule exception, not repeated as a discovery technique. Its distinct attempt metadata is missing; do not invent it.
- **San Francisco:** preserve the two exact results URLs, November 11 timestamps and 403 observations. Say these endpoints were blocked for the recorded client at that time, not that all SF results are unavailable to everyone. The older manifest's 200 concerned different pages/time and does not authorize continued probes. SF's list/documents remain separately usable; a county-wide blocked flag would incorrectly discard them.

Record project-request observations separately from WebFetch observations; the top-level UA statement cannot establish which headers another tool actually used. Old stubs remain inherited observations, not November 11 checks.

### 4. Are the slugs suitable keys?

Yes in syntax and uniqueness, subject to F4's `oc`/`orange` resolution. `la`, `sd`, `riverside`, `scl`, `alameda`, `sac`, `cc`, `fresno` and `sf` can be stable canonical keys; add a county-name mapping and prohibit future silent renaming. Abbreviations need not match domains or measure letters.

`LISTING_URLS` also needs a reviewed primary-list source selection: San Diego's first listed URL is explicitly a calendar, so “take the first URL” would choose the wrong source. Keep results-as-list roles and multiple supporting sources. Host allowlists should recognize documented official vendor delegation, not assume `.gov` is required or that a shared vendor hostname makes every vendor path authoritative for every county.

### 5. How should the open questions be resolved?

- **SF 10 versus 11:** retain the official reported list count of 11 including RTM. Treat Ballotpedia's 10 as a differing-scope cross-check. “Excludes RTM” is plausible, not established merely by subtracting one. Correct the plan's attribution of 11 to Ballotpedia in a later documentation change; preserve both source assertions.
- **LA SC:** keep one provisional contest and both jurisdiction labels. Inspect the enacted measure/resolution and official ballot question, ideally a city-clerk document, to distinguish submitting jurisdiction from the affected education body and a PDF section heading. Ask the county if the primary documents do not resolve it. Do not automatically trust the PDF heading or the results label, duplicate the measure, or assign a school/city cohort yet.
- **Fresno J:** preserve the Transactions and Use Tax versus Transient Occupancy Tax conflict. The `coalinga-sales-tax` folder name is a clue, not controlling evidence. Resolve against the official question, ordinance/resolution and impartial analysis, with a page locator. Keep raw results available for later matching, but withhold normalized tax type/threshold interpretation until identity and content reconcile.
- **Multi-county measures:** open explicit provisional records for RTM, LA LV/Ventura, Sacramento E/Placer, Sacramento H/Yolo, and Riverside B/Y/SB. Treat this as a partial discovery list. Store one canonical contest key, county memberships, each local designation and supporting source, plus whether each result covers the whole district or a county portion. Verify the exact district/subdistrict footprint; an aggregator pairing is not proof of complete membership. Do not sum percentages, merge by letter alone, or treat a county portion as a measure-wide outcome.
- **SF results:** discover an independently accessible official report/link on sf.gov, or request an official file/approved route from the department; Igor can manually supply a browser download. A press release's report number/date is evidence about publication, not the result table itself. Until then leave result formats/counts unavailable. Do not guess files on blocked hosts, switch clients, reuse browser challenge cookies or use an aggregator as the source of record.

### 6. Are the P1.3 notes enough for two agents?

They are a useful checklist, not yet a complete handoff. Before dispatch, freeze the revised schema and provide an exact, disjoint county roster with one owner per county and one output file per agent. “North/south” and “about 41” do not define ownership. Reconcile the roster against all 58 counties, distinguishing the target counties with measures from officially confirmed no-measure counties and unresolved coverage. Do not infer zero from a missing list.

Give both agents the same examples for a results-as-list county, a blocked county, a question-only source, a withdrawn measure and a shared contest. Require per-source evidence, count inclusion rules, issue dispositions, no-block-retry behavior and the UA/download handling already specified by the execution plan. The coordinator should validate unique slugs, expected county coverage, null versus zero, active/withdrawn totals, shared-source roles and the cross-county ledger before merging. Existing blocked counties and SC/J conflicts need named follow-up ownership even though they are outside the remaining-county survey.

### 7. May static files be fetched after HTML on that domain challenges?

**Adopt the proposed conservative rule for this project.** After a recognized challenge, 403 block or empty-202 block, stop automated exploration of that blocked host/service, including HEAD requests, guessed paths, alternate clients and known static URLs, unless the county explicitly confirms an allowed automated route. A person's normal-browser download may be ingested as a manual artifact with its URL, acquisition time, operator and checksum; it is not permission to automate that person's challenge-cleared session.

This is a project operating rule, not a claim that every independently public static file is universally forbidden. A separately published, unblocked official host can be considered with documented provenance and host approval; it must not be an alias/proxy maneuver around the same block. Follow ordinary official links, stop if they redirect to a blocked destination, and record exceptions narrowly. An unrelated county handbook on todb.ca.gov does not prove a measure-document collection exists there.

The earlier bot-challenge ruling concerns whether an already verified **navigation link remains visible**. It does not authorize new captures or turn a challenged HTTP 200 body into source evidence. P1.2's tests should separately pin blocked-host suppression, redirect checks, HEAD-versus-GET evidence, empty 202/HTTP 200 challenge rejection, and continued capture of independently approved open sources.

## Review disposition

Keep the census as the discovery baseline. Before closing P1.1's schema handoff, address F1–F5 or explicitly defer the non-executable leads/conflicts with owners and capture gates. Missing access and unresolved source content need not prevent work on other counties, but they must remain visible in the release/capture evidence. This review authorizes no capture run, R2 write or publication.
