# CalBallot: remaining work and review plan

**Prepared:** October 8, 2026.  
**Status:** proposed execution plan; the reviews and implementation below have not been performed by writing this document.  
**Starting revision:** `7b7a4b540648e0e34ce01b327132c8be6e70ba68`.  
**Budget:** approximately 10 Igor-hours/week, with substantially more model execution time. Plan six human hours and reserve four for exceptions.

**Execution checklist:** [track tasks and review gates here](remaining_review_checklist_20261008.md).
Use the checklist for progress; this document supplies the rationale and acceptance criteria.

## Recommendation and relationship to the existing plan

Finish useful content for the current counties, make updates routine, and prove
the election transition before expanding coverage. The remaining work needs
bounded reviews of concrete candidates, followed by evidence that the accepted
changes actually work. Another comprehensive review of the already published
statewide release would add little without a new defect or material change.

The accepted county order remains **San Bernardino/San Mateo content, then
Alameda, then reassess San Francisco/Contra Costa**. My additional recommendation
is that the minimum refresh, status, results fallback and operating checks take
precedence over enabling another county. We have a documented missed refresh,
35 county PDFs without sufficient extracted text, and unfinished election-status
work. More county names would add maintenance before those weaknesses are closed.

The six batches below organize the remaining reviews; they do not renumber the
original [six-part delivery plan](six_part_delivery_plan_20260913.md). Original
Parts 1-2 are complete. Original Parts 3-6 supply most of review batches 2-5.
This document replaces elapsed September review windows with proposed October
targets. Those dates are capacity assumptions, not completion evidence.

This planning pass uses repository records and existing evidence. It does not
refresh official sources, invoke Claude, scrape, load data, or publish anything.
At execution time, use the active user instructions and existing authorization;
the plan itself adds no new approval requirement.

## What is closed, and what is actually open

The [October 8 release receipt](release_progress_20261008.md) and
[machine-readable evidence](statewide_release_evidence_20261008.json) record the
published state. Review narratives written before deployment are historical
observations, not lists of still-open cutover tasks.

| Area | Recorded state | Remaining review obligation |
|---|---|---|
| Statewide reconciliation, original Parts 1-2 | Published: 14 propositions, retained/searchable withdrawn ACA 13, complete pages and source documents | Preserve these properties when later batches change shared code/data; do not repeat the original full review by default |
| Claude Part 1 review | Assessed in the [response](statewide_part1_review_response_20260913.md); bounded corrections implemented and released | Carry explicit deferrals into the register below, rather than treating every original finding as open |
| Combined release review and Measure Z follow-up | Recorded in the [October 8 review](statewide_release_claude_review_20261008.md); release conditions exercised afterward | No outstanding request to obtain these same reviews again |
| Recovery and live publication | Tested recovery, production preservation and served-site checks recorded; 97 focused tests passed for that release | Extend recovery to new inputs and changes; the old test count is not proof of future behavior |
| County content | 20 SB + 29 SMC records and 239 grouped document links live; source inventory and three draft questions/explanations prepared | Review document meaning, complete supported content, verify presentation and persistence |
| Freshness | Latest stored county captures recorded as September 28; October 5 workflow never acquired a runner | Determine current capture/evaluation state and implement a routine path through publication |
| Election status/results | Designs and earlier acceptance criteria exist; original Parts 4-6 remain open | Implement or explicitly select the supported fallback, then exercise it |
| Alameda/SF/Contra Costa | Not enabled by the October 8 release; scouting records are older evidence | Re-establish current source readiness before estimating or enabling coverage |
| Card aesthetics | [Detailed plan](card_design_action_plan_20260913.md) exists; redesign not implemented | Later comparison-sheet review, then implementation and interaction review if selected |

The county content packet lives at
`scraper/data/statewide_recon/20261008_release/county-content/`.
It covers 122 distinct PDFs: 87 with usable extraction, 35 needing visual
inspection/transcription or OCR. Seven files produced extraction warnings.
These are file counts, not counts of publishable or unpublishable measures.
The inventory's `Analysis readable` flag describes extraction from a
county-labelled link; Measure Z proves it does not establish impartial content.

## Review method used for every batch

**Codex owns implementation, investigation and the recommendation. Claude
provides an independent critique. Igor resolves actual product tradeoffs and
reviews concrete reader-facing outcomes.** Neither model's confidence nor a
READY label overrides contradictory source evidence.

1. **Define the batch.** Record the baseline revision, intended behavior,
   affected IDs/fields, source dates, exclusions and acceptance criteria. Separate
   a source-content question from a software defect and a product preference.
2. **Prepare the candidate.** Work on isolated data/output where needed. Produce
   a readable change summary, source evidence and the checks appropriate to the
   change before requesting review. Use new batch names so old drafts cannot be
   confused with accepted candidates.
3. **Codex checks independently.** Inspect sources, exercise meaningful failure
   cases and review rendered behavior. Test the reported risk, not simply the
   implementation's own answer. Preserve stable identities and unrelated data.
4. **Give Claude one bounded review packet.** Include the exact revision/diff,
   evidence inventory, review questions, known limitations and expected output.
   Ask it first whether this is the right work, then whether the candidate is
   correct. Record the reviewer/model/date and which tools it actually used.
5. **Adjudicate findings.** Reproduce or inspect each material claim. Record
   accepted, partly accepted, rejected, already addressed, or deferred, with
   evidence and a next action. A weak proposed remedy does not disprove a finding;
   a plausible finding does not make its proposed remedy correct.
6. **Fix and recheck.** Use a focused follow-up for substantive corrections or an
   unresolved blocker. Do not restart a whole review for wording-only changes.
   Any code/data changes after a review must be identified and checked; a verdict
   applies to the examined candidate, not whatever happens to exist later.
7. **Close the batch.** Record what is reviewed, accepted, published, deferred or
   blocked. For releases, include the accepted artifacts, recovery update,
   deployment receipt and served checks. A local preview closes a design review,
   not a deployment gate. Apply existing publication authorization; involve Igor
   when an unresolved consequential decision actually needs his input.

Use **READY**, **READY WITH CONDITIONS**, or **NOT READY**, plus a recommendation
for the next work. Every condition must identify whether it is a release blocker,
an execution-time check, or a later follow-up. Severity alone is insufficient.

### Review packet and issue register

Create one durable handoff per batch with links to its evidence; keep large
private artifacts in the existing private recovery arrangement. Include enough
source context for the reviewer to inspect claims without relying solely on
Codex's summary. If it cannot see a PDF or run a check, it must say so.

Each packet contains:

- Baseline and candidate revisions/hashes; precise data and output paths.
- Intended changes and preservation rules; source URLs, hashes and page references.
- What was directly checked, test commands/results, screenshots or a local preview.
- Unresolved questions and exceptions, with a visible reader-facing fallback.
- The raw Claude review, Codex disposition, changed-candidate checks and final state.
- Igor/agent effort, current limitations, and the exact next task.

The shared issue register records `ID`, batch, observed failure, evidence,
severity, blocking scope, disposition, owner, target, and closure evidence.
Do not silently delete deferred issues when a release ships.

## Six review batches

| Batch | Main result | Review checkpoint | Dependency / target |
|---|---|---|---|
| R1 | Useful, source-backed content for all 49 existing county records, with explicit exceptions | Small mixed pilot, then bounded county waves and one integration review | Start now; pilot Oct 9-10, main content target Oct 15 |
| R2 | Routine capture evaluation and reviewed refresh through deployment | Changed/unchanged/failure scenario evidence | Begin missed-run triage during R1; finish before expansion, target Oct 14 |
| R3 | Consistent election status and usable reader flows | Date-boundary matrix plus desktop/mobile task review | Use R1 content and R2 freshness contract; target Oct 18 |
| R4 | Honest results fallback and bounded certified import for ready sources | Source/identity review, then results candidate review | Depends on R3 status contract; target Oct 22 |
| R5 | Exercised operation, recovery and release procedure | Integrated rehearsal and final readiness verdict | R1-R4 or their explicit fallbacks; target Oct 25 |
| R6 | Evidence-based expansion decision, then later card design review | Separate Alameda readiness decision and design comparison sheet | Conditional; no deadline that displaces R2-R5 |

These are handoff units, not six monolithic releases. Publish accepted useful
county waves when ready. R2 triage and the small results-source inventory need
not wait for every difficult PDF in R1. This describes task scheduling, not a
requirement to run multiple agents or change the current agent permissions.

### R1 — Review and complete the existing county content

**Purpose:** readers should be able to identify the question, understand its
substance, and inspect its source for each supported measure.

**Work before review**

1. Establish a 49-row content ledger: county, stable ID, election/jurisdiction,
   question source/page/hash, explanation sources, verified document role,
   extraction method, review status, confidence issue and visible fallback.
   Keep official question text separate from CalBallot's editorial explanation.
2. Review the existing SB Y/Z/A drafts (IDs 12418-12420). They are three bond
   measures, so they are not a representative pilot by themselves. Add a difficult
   SMC scanned/composite source and the regional measure with no letter; verify
   the identities before selecting those examples.
3. Compare every proposed official question to the rendered source page. Preserve
   wording, amounts and qualifications; document permitted whitespace/layout
   normalization. OCR is a draft extraction aid, never an authoritative source.
4. Check every explanation's substantive claims against official question/text
   or a verified impartial analysis. Distinguish assessed value from market
   value, estimates from guarantees, annual receipts from authorization totals,
   and levy duration from project duration where the source supports them.
   Record conflicts or missing facts instead of resolving them by inference.
5. Classify the document by its actual content. Advocacy can be linked and labelled
   as advocacy, but cannot supply an unqualified neutral explanation. Preserve
   the Measure Z correction and the distinction between its raw county label
   and the public role. Check multi-measure packets at the correct pages.
6. Establish field ownership and provenance for reviewed content. Prove an
   ordinary registrar refresh will preserve it; changed source bytes should
   flag dependent content for re-review. Do not overwrite unrelated enrichment.
7. Complete SB in small waves, then SMC waves selected by source difficulty
   (roughly 5-10 records per packet). Show an explicit disposition for all 49;
   do not hold the supported records indefinitely for a damaged or absent source.
8. Build the relevant cards, modal and standalone pages on a copy. Exercise long
   questions, missing explanations, shared PDFs and source attributions; confirm
   that search and previews use the intended content without stale contradictions.

**Claude's focus:** independently verify question fidelity and claim support,
neutrality, amount/unit mistakes, wrong-measure attachment, and whether the
implementation preserves review provenance. At the pilot, challenge the content
format before it is repeated across 49 records. For subsequent waves, inspect
every newly proposed question/explanation against accessible evidence; report
any source it could not inspect. A partial sample cannot certify the entire wave.

**Igor's input:** one pilot read for usefulness, density and voice, then concrete
exceptions. Do not make Igor transcribe all 49 questions. Codex remains responsible
for source checks; a second model's agreement is additional evidence, not proof.

**Done when:** every record is either source-verified and published or appears in
an explicit exception list with a truthful document-only/partial-content fallback.
Report separate counts for verified question, verified explanation, unresolved
source and published content; a fallback is not a claim of complete content.
All changed amounts/qualifications and difficult transcriptions have a recorded
second check. The released waves preserve IDs, documents, Finance and history.

**Deliverables:** content ledger, pilot preview, wave packets, per-finding
dispositions, reviewed content provenance, persistence checks and release receipt.

### R2 — Review refresh reliability and public freshness

**Purpose:** a successful capture, a successful comparison and a public update
must be distinguishable, and the normal changed week must be manageable.

1. Inspect available run/capture records to determine whether a later scheduled
   run succeeded. The recorded October 5 runner-acquisition failure is not parser
   breakage; do not rewrite an adapter to repair a hosting incident. Record the
   remedy or next-run check and the retained source vintage. New capture work
   follows the active authorization and source-access rules.
2. Create a versioned accepted-publication manifest and a separate evaluation
   record. Track source capture, comparison, content review and public deployment
   times accurately. A capture or parse must not advance the published baseline.
3. Make the normal report distinguish added/removed records, content/identity
   changes, document URL/role/hash changes, and provenance-only changes. Represent
   unchanged, changed, failed-to-evaluate and idle as distinct outcomes.
4. Turn the useful release steps into a repeatable runbook/entry point with explicit
   inputs, without requiring knowledge of a dated scratch directory. Do not reuse
   the sealed statewide one-shot loader as a general update mechanism.
5. Rehearse unchanged, document-only, substantive, changed source behind the same
   URL, missing/incomplete capture, identity ambiguity, parse failure, and a failed
   scheduled job. Include source changes affecting R1 explanations. An unchanged
   week should require no Igor action; failures should produce an actionable report.
6. Include a bounded statewide freshness check and a defined cadence. Healthy
   county automation must not imply the statewide list is current.
7. Verify FTS behavior on affected insert/update/delete paths. The current binary
   database trigger is documented; assess the fresh-schema gap separately. Fix
   demonstrated synchronization failures in the routine path before accepting it.
8. Exercise dry-run diff, safe backup/load, repeated-input no-write behavior,
   complete bundle generation, independent preservation checks, deployment
   verification and accepted-manifest advancement. Keep publication reviewed.

**Claude's focus:** challenge false-green states, stale baselines, failure isolation,
content overwrites, invalid reuse of sealed verifiers, and discrepancies among DB,
generated files and served files. Require failure evidence beyond a happy-path run.

**Done when:** an unchanged run needs no human decision, a normal changed release
is understandable and targets at most one Igor-hour (measured), a failed check
cannot claim freshness, and a new operator can follow the documented routine.
Record simulated and actual runs separately; do not claim unattended success
without an actual unattended run.

**Deliverables:** change report, accepted-source manifest, scenario evidence,
FTS disposition, and short refresh runbook with remaining manual steps.

### R3 — Review election status and the complete reader experience

**Purpose:** the calendar must change the presentation without inventing results,
and readers must be able to use the content we have prepared.

1. Specify one status contract and inventory every consumer: hero, county/statewide
   cards, archive/list, modal, filters/search, individual pages, exports and
   historical statistics. Preserve withdrawn status and historical accepted outcomes.
2. Use verified election dates and the election's local calendar. Exercise the
   day before, election day, November 3-to-4 Pacific midnight and the year boundary.
   Test unknown dates, no observation, zero counts, unofficial observations and
   certified results. Do not assign dates to old records from their year alone.
3. Treat availability of official external results separately from CalBallot's
   imports. Display only real source/check times and preserve the distinction
   between an absent result and a failed attempt to check.
4. Verify unknown/unofficial results stay out of certified/historical pass-rate
   projections, and that the same record says the same thing across surfaces.
5. Review six reader tasks: select the intended county; find a measure; understand
   the question/explanation; open the correct document; interpret freshness/status;
   follow a stable individual-page/explorer link. Retain the county-scope warning.
6. Check 320px and ordinary mobile/desktop widths, keyboard/focus, zoom, long titles,
   missing content and PDF links. Measure one documented throttled mobile profile:
   cold/warm load, time to usable cards and optional expensive work separately.
   Fix demonstrated task blockers; keep the full card redesign in R6.

**Claude's focus:** seek contradictory status consumers, date rollover failures,
misleading empty states, inaccurate comparison claims, and reader-task failures.
Distinguish observed browser behavior from conclusions drawn only from code.

**Igor's input:** a short walkthrough of a small set of actual candidate records;
identify confusing presentation or a meaningful usability tradeoff.

**Done when:** November 4 is exercised without an upcoming label or invented
outcome; supported reader tasks pass across surfaces; measured limitations and
any narrow context exclusions are documented. This is the delayed reader-readiness
check, not a retroactive claim that the October 5 target was met.

**Deliverables:** status matrix, consumer inventory, boundary evidence, desktop/
mobile review packet, performance measurements and concrete fixes or fallbacks.

### R4 — Review results readiness and supported imports

**Purpose:** every published coverage area needs an honest post-election path,
even if numerical ingestion is not yet supported.

1. Inventory official result formats and certification evidence for statewide,
   SB and SMC. Separate historical examples, anticipated endpoints and verified
   current-election sources. Start this small investigation while R1/R2 proceeds
   so source uncertainty is not discovered late.
2. Establish the minimum fallback first: accurate awaiting/not-imported wording,
   verified official result links when available, real check times, and no implied
   winner or certification. Do not make automated numerical imports a prerequisite
   for this fallback.
3. Where sources support it, prepare a bounded reviewed-file importer for certified
   observations. Map source contest IDs to existing CalBallot IDs using election,
   jurisdiction and scope evidence. Quarantine letter/title-only ambiguity.
4. Retain immutable observations, source hashes, reporting/capture times when
   known, certification evidence and explicit accepted-observation selection.
   Preserve corrections and reject accidental stale replacement; legitimate
   downward count corrections must be supported.
5. Keep result ownership separate from source documents and reviewed editorial
   content. Verify a normal county refresh after a results import preserves both.
6. Exercise repeat import, revised certification, zero/null, partial counts,
   missing thresholds, rollback, ambiguous match and county/regional scope on
   copies. Do not aggregate regional transit totals across counties by title.
7. Specify post-election capture/retention behavior when sources move or retire,
   using evidence rather than a guessed extension to a discovery date window.

**Claude's focus:** identity and geographic-scope mistakes, unsupported certification,
stale observations, accidental pass-rate contamination, and result loss on refresh.
Challenge whether the importer is worth its maintenance cost for each source.

**Done when:** every live coverage area has a tested presentation fallback and a
documented readiness state. Supported import paths pass the evidence-based cases;
unsupported ones remain explicitly unsupported. Pre-election fixtures prove the
mechanism, not that live November certified results already exist.

**Decision if constrained:** choose official-link fallback and import certified
results later. Bring a proposed new election-night service commitment to Igor;
none is assumed here.

**Deliverables:** source/contest ledger, fallback preview, supported import evidence,
ownership checks and post-election source policy. Extending coverage in R6 must
also extend this ledger; no county ships without a results fallback.

### R5 — Review the integrated operating procedure and final readiness

**Purpose:** confirm that the pieces work together within the human time budget.

1. Rehearse evidence-to-report-to-review-to-load-to-build-to-deployment verification
   using a real changed input when available or a clearly labelled simulation.
   Include the current county content and statewide overlays, not a toy database.
2. Extend recovery for new inputs/code/content. Restore to a fresh directory using
   the documented base archive plus update chain; verify required model/data inputs,
   IDs, documents, Finance, reviewed content and any result observations. Document
   where credentials are obtained separately without putting them in the bundle.
3. Exercise source drift, missing capture, generation failure, deployment failure
   and rollback. Check the accepted-publication manifest stays truthful when the
   database, local output and served release differ.
4. Rehearse the election transition and a later certified correction through the
   actual render/release path. Reuse valid component evidence, but test the
   integration points rather than merely adding up passing test counts.
5. Write one compact operator runbook: cadence, report location, unchanged/changed/
   failed/idle week, source changes invalidating content review, publication,
   recovery, official results, certification and escalation to Igor.
6. Have Claude walk through the handoff as a fresh reviewer. Missing commands,
   undocumented scratch files or inaccessible critical inputs are findings.
   Codex verifies or fixes them and records the final recommendation.
7. Measure Igor involvement. Update the current working list and county/source
   status, then freeze nonessential changes October 26 through election day.

**Claude's focus:** attempt to falsify readiness using a concrete failure sequence.
Check whether recovery restores the accepted system, whether rollback is complete,
and whether the claimed routine fits the recorded human effort.

**Igor's input:** one concrete operator walkthrough and review of any remaining
coverage/service tradeoff. If an extra publication approval is needed under the
then-current instructions, present the completed candidate and limitations first.

**Done when:** there is exercised evidence for the critical scenarios, a usable
runbook, a current recovery set, and an explicit recommendation about operating
through the election. If using a fallback, name it; do not label an unimplemented
importer complete. Later real certification still receives its own source review.

### R6 — Review expansion, then the deferred design work

These are separate decisions. Passing the Alameda gate does not approve a card
redesign, and a successful visual prototype does not establish county readiness.

**R6a: Alameda, then reassess San Francisco/Contra Costa**

1. Recheck readiness against current official source evidence. August counts,
   access failures, HTML shapes and estimates are starting hypotheses only.
2. Evaluate Alameda first. Inventory source coverage, packet/page associations,
   questions, thresholds, stable identities, regional scope and results fallback.
   Treat the older dual-host/letter join design as something to verify, not assume.
3. Confirm the existing counties are useful, R2's routine works, R3's transition
   is safe, and R4/R5's minimum fallback/rehearsal obligations can be met without
   displacement. An unavailable source in R1 with an explicit honest fallback
   need not block all expansion forever; account for the unresolved reader cost.
4. Estimate maintenance and Igor review effort as well as implementation. If this
   fits before the freeze, prepare fixtures, isolated parse/load, full content and
   UI review, preservation evidence, recovery and served checks for Alameda.
   Otherwise defer enablement and record the reason and next reassessment date.
5. Independently review Alameda before enabling it. Then reassess SF/Contra Costa
   on present evidence and capacity; do not revive obsolete automatic 2028 cutoffs
   or assume a blocked source has become available.

**Claude's focus:** whether expansion is the right next investment, source
completeness, identity/packet attachment, regional ambiguity, maintenance cost,
and whether existing county behavior survives the new adapter.

**R6b: Card design, when selected**

Use the existing [card action plan](card_design_action_plan_20260913.md). Begin
with six real examples at desktop/mobile widths, including standard, long/no-letter
and missing-context local cards, a statewide card, and passed/failed archive cards.
Compare current/proposed designs in page context with real reviewed R1 content.
Preserve the user's carousel, summaries, historical comparisons and brand choices.

Igor reviews the concrete comparison sheet for density and readability. Claude
reviews hierarchy, source/status clarity, keyboard/zoom behavior, overflow and
consistency. After selecting a direction, implement on isolated output and perform
the relevant data/render/release checks. Do not reopen basic preferences without
a new substantive reason or let cosmetic work displace election correctness.

## Carry-forward findings: initial disposition register

| Item | Disposition now | Next owner / review |
|---|---|---|
| Part 1 F1-F3: inaccurate descriptions, hidden withdrawal, proposition search | Corrected and released | Codex: targeted regressions when shared content/status/search changes in R1/R3 |
| F4: independently bound identity review | Reviewed-input pin/crosswalk implemented; semantic judgment still required | Codex + Claude: new sources/identity changes in R2/R4/R6 |
| F5/F8: safe promotion and destination ownership | Corrected for the reviewed release | Codex: preserve guarantees in reusable R2 path; do not generalize the one-shot loader blindly |
| F6: ambiguous historical canonical keys | New 2026 keys qualified; legacy collisions remain deferred | R4 checks actual mappings; fix an affected collision if needed, not a broad migration by default |
| F7: strict replay rejects later edits | Correct behavior for the sealed correction | R2 defines a separate supersession/refresh contract |
| F9: independence of verifier evidence | Targeted checks added; some shared primitives remain | R2 strengthens meaningful independent checks where a shared error could escape |
| F10: topics/timeline/context gaps | Corrected status/source wording; broader topic coverage still a follow-up | R1/R3 verify current presentation; omit unsupported classifications and avoid general taxonomy work |
| Measure Z purported analysis | Exact PDF public role corrected; raw evidence retained | R1 actual-content review; R2 changed-byte reinspection |
| October 5 missed run | Failure evidence saved; current operating follow-up remains | R2 |
| FTS schema/index lifecycle | Actual production insert trigger documented; fresh-schema/update-delete work not completed by that note | R2 investigates real affected paths; R5 states supported restore method |
| Claude's missing workflow evidence observation | Evidence subsequently recorded | Closed unless the evidence itself proves insufficient |
| Claude's empty prior-review output observation | It observed its own unfinished output; not a missing separate review | Closed; label running/completed reviews clearly |
| Stale August county board / historical "next" instructions | Later release notes supersede them, but navigation is confusing | Update current-state pointers now; refresh detailed county/source board during R2/R6 |

## Timing, human effort and scope cuts

Use these as working targets and reestimate after the pilot; do not make the
review thoroughness depend on an optimistic model-runtime estimate.

| Window | Intended outcomes | Planned Igor time |
|---|---|---:|
| Oct 8-14 | R1 mixed pilot and first waves; R2 missed-run triage and routine candidate; small R4 source inventory | R1 1.5-2h + R2 1-1.5h; up to 2.5h for integration, at most 6h total |
| Oct 15-21 | Resolve R1 difficult cases; R3 reader/status review; R4 fallback and supported importer review | R1 exceptions 0.5-1h + R3 1-1.5h + R4 1-1.5h; at most 6h total |
| Oct 22-25 | R4 closure and R5 integrated rehearsal; explicit R6 scope decision | R4 up to 1h + R5 1-1.5h + R6 decision up to 0.5h; retain contingency |
| Oct 26-Nov 3 | Freeze nonessential changes; perform source/health checks and address material failures | Use the reserved capacity; no assumed election-night staffing |
| After election / as official evidence becomes available | Review actual results/certification and corrections; reassess deferred expansion/design | Budget and cadence follow observed sources and user availability |

Do not stack a delayed week on top of the next week's full plan. If the work
does not fit: protect truthful status, source access, recoverability and freshness;
publish supported county content with explicit exceptions; use official-link
results fallback; defer expansion and aesthetics. If source access or extraction
blocks a record, investigate and record a fallback rather than spending unlimited
time or inventing content. Surface actual effort before committing to another county.

## Exact next task

Prepare **R1's mixed content pilot** from the three existing SB drafts plus the
two SMC edge cases. Produce the source/page comparisons, neutral explanations,
ownership/provenance proposal and a small local reader preview. Correct the
inventory's misleading implication that every extractable analysis-labelled PDF
is an impartial analysis. Independently verify the claims, then issue Claude one
focused review packet and assess its findings before scaling to the remaining waves.

Alongside that bounded preparation, determine the current scheduled-capture state
from available run records and record R2's next action. Do not wait for all 49
content rows to be finished to notice another missed refresh.

No new product answer from Igor is needed to prepare this pilot. Bring him the
actual examples and only those exceptions for which his preference changes the
outcome. The proposed expansion timing can be revisited at R6's concrete decision.

## Reusable Claude prompt skeleton

Fill the placeholders with the finished batch packet; do not send a promise of
future evidence as though it were a reviewable implementation.

```text
Review CalBallot batch <R# / name> independently and read-only.

Read docs/plans/remaining_review_plan_20261008.md, then <batch handoff>,
<baseline/candidate revision and diff>, <source/evidence index>, and the
relevant implementation and rendered examples. The packet must specify whether
you can inspect PDFs and execute isolated checks. Do not modify production,
publish, scrape, start workflows, contact anyone, or write to external storage.
If an input or capability is unavailable, identify it and limit your claims.

First challenge the premise and timing: is this the right work given the current
reader need, 10 human hours/week, source readiness and unfinished election work?
Then evaluate the candidate against this batch's actual acceptance criteria.
Do not assume Codex's report is correct, and do not search for disagreement merely
to produce findings. Prefer primary source evidence and concrete failure cases.

Focus on: <the batch-specific review questions above>.
Preserve: <IDs, field ownership, content/source semantics and relevant invariants>.
Known limits and deliberate deferrals: <explicit list>.

Return:
1. Recommendation on scope/priority, including a better sequence if justified.
2. Findings ordered by impact, each with file/line or source/page evidence,
   a failure example, affected scope, suggested remedy, and blocking status.
3. What you inspected or ran directly versus accepted from recorded evidence.
4. Acceptance criteria that pass, fail or remain unverified.
5. READY / READY WITH CONDITIONS / NOT READY for this exact candidate and scope.
   Distinguish release blockers, execution checks and deferred follow-ups.
6. The next concrete work, in order, and any real decision needed from Igor.

Do not reopen a closed finding without new evidence. Do not report a past,
pre-deployment condition as still open without checking the later release receipt.
Explicitly state when a result is based on a sample rather than complete coverage.
```
