# CalBallot remaining review checklist

**Updated:** October 8, 2026.  
**Companion:** [remaining work and review plan](remaining_review_plan_20261008.md).  
**Status:** checklist prepared; remaining implementation and reviews are not complete.

Use this file to track execution; use the plan for rationale, detailed acceptance
criteria and the reusable Claude prompt. R1-R6 are review batches, not the original
delivery-part numbers. Codex owns tasks unless another owner is named. Claude's
findings require an evidence-based Codex disposition; Igor handles concrete product
tradeoffs and the marked walkthroughs.

Check an item only after recording its evidence in the batch handoff. For a
blocked, deferred or inapplicable item, leave it unchecked and append the reason,
owner and next action/date. An accepted fallback can close a readiness gate, but
does not turn an unimplemented feature into a completed task. Apply existing
authorization when executing; these boxes do not create new approval requirements.

## Start here

1. **R1.01-R1.05:** prepare the mixed five-record content pilot and local preview.
2. **R2.01:** check the missed-refresh follow-up while the pilot is being prepared.
3. **R1.06-R1.07:** obtain Claude's pilot critique, assess it, and have Igor read the examples.
4. **R1.08-R1.12:** work through the remaining county records in reviewed waves.
5. Start **R4.01** source inventory early; complete R2-R5's essential readiness
   work before enabling Alameda. R6 remains conditional.

## Batch tracker

Update this table at each handoff. Dates are proposed targets, not evidence of completion.

| Batch | Current state | Target | Handoff / verdict / release evidence |
|---|---|---|---|
| R1 county content | Three SB drafts and 49-record source packet prepared; mixed pilot pending | Pilot Oct 9-10; main content Oct 15 | Pending |
| R2 refresh | Missed-run evidence saved; routine review pending | Oct 14 | Pending |
| R3 status and reader experience | Pending | Oct 18 | Pending |
| R4 results | Design exists; source readiness and implementation review pending | Oct 22 | Pending |
| R5 operations | Earlier release recovery verified; new integrated rehearsal pending | Oct 25 | Pending |
| R6a county expansion | Conditional; current source reassessment pending | After readiness gates | Pending |
| R6b card design | Detailed plan exists; comparison sheet pending | When selected | Pending |

## Already completed baseline

These are historical completions, supported by the [October 8 release receipt](release_progress_20261008.md).
Reopen only for new evidence or relevant changes.

- [x] Correct and publish the statewide slate, retained withdrawal and complete public pages.
- [x] Obtain and assess the original Part 1 review, combined release review and Measure Z follow-up.
- [x] Correct the exact Measure Z PDF's public role while preserving raw source evidence.
- [x] Exercise the accepted release's production preservation, private recovery and served-site checks.

## R1: County content

**Gate:** all 49 records have an explicit content disposition; supported content
is reviewed and published, with honest fallbacks for unresolved sources.

- [ ] **R1.01** Create the 49-row ledger with stable ID, election/jurisdiction, question and explanation sources, page/hash, actual document role, extraction method, review status and fallback.
- [ ] **R1.02** Correct the inventory wording so extractable county-labelled "analysis" is not treated as verified impartial content; retain the Measure Z exception.
- [ ] **R1.03** Select the pilot: SB Y/Z/A (IDs 12418-12420), one difficult SMC scanned/composite source and the SMC regional measure without a letter. Verify the two SMC identities and source pages.
- [ ] **R1.04** Compare all five questions against rendered source pages; verify each explanation's claims, amounts, units, estimates and qualifications. Record normalization and source conflicts; keep advocacy distinct.
- [ ] **R1.05** Prepare the pilot preview in cards, modal and standalone pages, plus the proposed ownership/provenance rules for reviewed content.
- [ ] **R1.06 — Claude + Codex** Obtain the pilot review of format, fidelity, neutrality and provenance; record inspected versus inaccessible sources; assess findings and correct supported defects.
- [ ] **R1.07 — Igor** Read the concrete pilot for usefulness, density and voice; record decisions before repeating the format across all records.
- [ ] **R1.08** Implement and verify content persistence: ordinary registrar refresh preserves reviewed content; changed source bytes flag dependent content for re-review; unrelated enrichment remains intact.
- [ ] **R1.09** Complete SB in waves of roughly 5-10 records, using the per-wave review gate below. Verify every proposed question and explanation against its evidence.
- [ ] **R1.10** Complete SMC in waves grouped by source difficulty. Resolve packet page ownership, visually check OCR/transcription, and record damaged or missing-source exceptions.
- [ ] **R1.11** Perform integration checks for long/missing content, source attribution, shared PDFs, search/previews and all detail surfaces; record second checks for changed amounts/qualifications and difficult transcriptions.
- [ ] **R1.12** Release accepted waves under the applicable authorization, preserve IDs/documents/Finance/history, and record separate totals for verified questions, verified explanations, unresolved sources and published content. Close R1 through the common gate.

**Evidence to attach:** ledger, pilot and wave packets, source comparisons,
Claude reviews/dispositions, persistence checks, reader previews and release receipts.

## R2: Refresh and freshness

**Gate:** unchanged, changed, failed and idle runs are distinguishable; a routine
changed release targets at most one measured Igor-hour and preserves accepted content.

- [ ] **R2.01** Inspect current available workflow/capture records, establish whether a later run succeeded, and record the October 5 failure follow-up and retained source vintage. Do not mistake runner acquisition failure for parser failure.
- [ ] **R2.02** Create a versioned accepted-publication manifest separate from evaluation records, with accurate capture, comparison, content-review and deployment times.
- [ ] **R2.03** Produce readable diffs for additions/removals, content and identity changes, document URL/role/hash changes, and provenance-only updates.
- [ ] **R2.04** Implement explicit unchanged/changed/failed-to-evaluate/idle states; ensure capture or parsing alone cannot advance the public baseline.
- [ ] **R2.05** Document and implement the reusable refresh procedure with explicit paths and inputs; preserve the sealed statewide correction's separate contract.
- [ ] **R2.06** Rehearse unchanged, document-only and substantive changes, including changed bytes at the same URL and invalidation of dependent R1 content reviews.
- [ ] **R2.07** Rehearse incomplete/missing captures, ambiguous identity, parse failure and failed scheduled execution; preserve accepted data and issue actionable failure reports.
- [ ] **R2.08** Define and exercise statewide freshness checks separately from county capture health, including their cadence.
- [ ] **R2.09** Verify FTS synchronization on affected insert/update/delete paths; fix demonstrated routine-path failures and separately disposition the fresh-schema gap.
- [ ] **R2.10** Exercise dry-run, backup, safe load, repeated-input no-write behavior, complete build, independent preservation, deployment checks and accepted-manifest advancement.
- [ ] **R2.11** Obtain and assess Claude's failure-focused review, measure routine Igor effort, document actual versus simulated/unattended evidence, and close R2 through the common gate. Update current county/freshness pointers.

**Evidence to attach:** workflow/capture assessment, accepted manifest, change
reports, scenario results, FTS disposition and short refresh runbook.

## R3: Election status and reader experience

**Gate:** all surfaces agree, the local election-date transition invents no
outcome, and the exercised reader tasks work on desktop and mobile.

- [ ] **R3.01** Specify the shared status contract and inventory hero, cards, list/archive, modal, search/filters, individual pages, exports and historical-statistics consumers.
- [ ] **R3.02** Implement consistent status using verified dates and the local calendar; preserve withdrawn records and accepted historical outcomes without inventing missing dates.
- [ ] **R3.03** Exercise the day before, election day, November 3-to-4 Pacific midnight and year boundary, including unknown dates, absent observations, zero counts, unofficial and certified results.
- [ ] **R3.04** Distinguish external official results from imported results and failed checks; display only recorded timestamps and prevent unknown/unofficial observations from contaminating pass-rate projections.
- [ ] **R3.05** Exercise six reader tasks: select county, find measure, understand question/explanation, open correct document, interpret freshness/status, and follow stable page/explorer links. Verify county-scope and historical-comparison qualifications.
- [ ] **R3.06** Check 320px and ordinary mobile/desktop widths, keyboard/focus, zoom, long titles, missing content and PDF links. Measure a specified throttled mobile profile, cold/warm loads, usable cards and optional expensive work separately.
- [ ] **R3.07 — Igor** Walk through the candidate records and identify concrete comprehension or usability problems.
- [ ] **R3.08** Obtain and assess Claude's status/reader review; fix demonstrated blockers, document remaining limits, and close R3 through the common gate. Keep the broader card redesign in R6b.

**Evidence to attach:** consumer inventory, status/date matrix, browser results,
screenshots, measured performance, reviewer dispositions and release receipt.

## R4: Results readiness

**Gate:** every published coverage area has a tested honest fallback. Numerical
imports are accepted only for supported sources with verified identity and certification evidence.

- [ ] **R4.01** Inventory official result formats and certification signals for statewide, SB and SMC; distinguish historical examples, anticipated endpoints and verified current-election sources.
- [ ] **R4.02** Implement and review the minimum awaiting/not-imported fallback with verified official links when available, real check times and no implied result or certification.
- [ ] **R4.03** Record source-by-source importer-versus-fallback decisions and the maintenance rationale. Keep unsupported imports explicitly deferred with a revisit trigger.
- [ ] **R4.04 — For supported imports** Build the contest-to-existing-ID ledger using election, jurisdiction, source and reporting scope; quarantine ambiguous matches and identify relevant legacy canonical-key collisions.
- [ ] **R4.05 — For supported imports** Implement bounded reviewed-file ingestion with immutable source-backed observations, explicit accepted selection, certification evidence and retained correction history.
- [ ] **R4.06 — For supported imports** Exercise repeat/stale import, revised certification, downward correction, zero/null, partial counts, missing thresholds, ambiguous identity and transaction rollback.
- [ ] **R4.07 — For supported imports** Verify county versus regional scope, no unsupported cross-county aggregation, and preservation of results/editorial content/documents through an ordinary registrar refresh.
- [ ] **R4.08** Define post-election capture and retention behavior for moved or retired sources without guessed discovery-window extensions.
- [ ] **R4.09** Obtain and assess Claude's identity/certification/fallback review, preview result-bearing or fallback pages, and close R4 through the common gate. Distinguish pre-election fixture evidence from real certification.

**Evidence to attach:** source-readiness/contest ledger, fallback preview,
supported-import checks, ownership evidence and post-election source policy.

If only the fallback is selected, R4.04-R4.07 stay unchecked and explicitly deferred;
R4 readiness may close with that limitation recorded. No election-night service
commitment is assumed.

## R5: Operating rehearsal and readiness

**Gate:** the documented procedure works with the accepted system, exercised
failure paths and current recovery inputs, within the human time budget.

- [ ] **R5.01** Rehearse a complete evidence-to-report-to-review-to-load-to-build-to-deployment-verification cycle; label any simulated changes.
- [ ] **R5.02** Extend the recovery inventory for new code, content, inputs and any results; document the base/update chain and credential access separately.
- [ ] **R5.03** Restore into a fresh directory and rebuild; verify IDs, documents, Finance, reviewed content, statewide overlays and supported results using the required real model/data inputs.
- [ ] **R5.04** Exercise structural source drift and missing capture, preserving the last accepted data with accurate vintage and source links.
- [ ] **R5.05** Exercise generation failure, deployment failure and complete rollback; verify the public manifest remains truthful when DB, local output and served release differ.
- [ ] **R5.06** Exercise the election transition and a later certified correction, where supported, through actual rendering/release integration; use explicit fixtures before real evidence exists.
- [ ] **R5.07** Write the compact operator runbook covering cadence, report locations, unchanged/changed/failed/idle runs, invalidated content review, publication, recovery, results and escalation.
- [ ] **R5.08 — Claude + Codex** Review the handoff as a fresh operator; resolve undocumented commands, scratch dependencies or inaccessible critical inputs; record the readiness verdict and limitations.
- [ ] **R5.09 — Igor** Perform a concrete operator walkthrough; record actual human effort and resolve any remaining coverage/service tradeoff.
- [ ] **R5.10** Update the working list, county/source status, deferred issues and exact resume task; close R5 through the common gate and establish the October 26-through-election nonessential-change freeze.

**Evidence to attach:** integrated rehearsal report, recovery inventory/restore
results, failure/rollback evidence, operator runbook and final readiness disposition.

## R6a: County expansion, conditional

**Gate:** existing-county usefulness and essential R2-R5 readiness are protected;
new coverage has justified review/maintenance costs and its own results fallback.

- [ ] **R6a.01** Reassess Alameda with current official evidence; verify completeness, packets/pages, questions, thresholds, identities, regional scope and results fallback. Recheck the older dual-host/letter-join assumptions.
- [ ] **R6a.02** Estimate implementation, human review and continuing maintenance; document whether expansion fits the readiness gates and freeze. Bring Igor only a consequential scope/timing tradeoff requiring his decision.
- [ ] **R6a.03 — If proceeding** Prepare fixtures, isolated parse/load and complete content/UI candidate; verify existing counties and unrelated data remain intact.
- [ ] **R6a.04 — If proceeding** Obtain and assess Claude's Alameda review; satisfy the common release gate, recovery and served checks before marking the county live. Extend the results/source ledger.
- [ ] **R6a.05** Reassess SF/Contra Costa afterward using current access/source evidence and capacity; record proceed/defer decisions and revisit triggers. Update the county board.

If Alameda is deferred, leave its implementation boxes open with the recorded
reason and next reassessment date. Do not count a scouting review as enablement.

## R6b: Card design, when selected

**Gate:** a real-content comparison is accepted before wider implementation;
reader behavior, data semantics and earlier user preferences remain intact.

- [ ] **R6b.01** Prepare the [card plan's](card_design_action_plan_20260913.md) six-example current/proposed comparison sheet: standard, long/no-letter and missing-context local; statewide; passed and failed archive. Show desktop/mobile page context and the 320px edge case.
- [ ] **R6b.02 — Igor** Review concrete density/readability choices while preserving the carousel, useful summaries, historical context and recognizable brand.
- [ ] **R6b.03 — Claude + Codex** Review hierarchy, source/status clarity, keyboard/zoom behavior, overflow and consistency; disposition findings and select a direction.
- [ ] **R6b.04 — If selected for implementation** Implement on isolated output, verify interaction and data/render preservation, then complete the common release gate. Keep this separate from county-enablement approval.

## Common review and release gate

Copy this short checklist into each batch or content-wave handoff. These boxes
are a reusable template, not a single review that can close all batches.

- [ ] **G1** Record baseline/candidate revision or hashes, affected IDs/fields, source dates, scope, exclusions and acceptance criteria.
- [ ] **G2** Prepare source/page/hash evidence, intended changes, preservation results, meaningful checks, preview and known limitations.
- [ ] **G3** Complete Codex's direct source/behavior checks before asking for external review.
- [ ] **G4** Obtain Claude's bounded review using the plan's prompt; record reviewer/date, actual inspected evidence, tool limits and verdict for the exact candidate.
- [ ] **G5** Disposition every material finding with evidence: accepted, partly accepted, rejected, already addressed or deferred; distinguish blockers, execution checks and follow-ups.
- [ ] **G6** Fix supported defects, recheck changed behavior, and obtain a focused follow-up when substantive corrections or unresolved blockers warrant it.
- [ ] **G7** Record any necessary Igor decision against concrete examples; otherwise use existing choices and authorization.
- [ ] **G8 — For a release** Verify accepted artifacts, preservation and recovery; perform the authorized publication and check served behavior/artifacts. Advance the accepted-publication manifest only after verification.
- [ ] **G9** Record final state, closure evidence, actual effort, remaining limitations and exact next task; update this checklist and the issue register.

For a design-only handoff, mark G8 inapplicable with the reason. For release work,
"reviewed", "accepted", "published" and "verified live" remain separate claims.

## Ongoing and post-election follow-up

- [ ] **O1** Maintain the shared issue register with ID, batch, failure, evidence, severity, blocking scope, disposition, owner, target and closure evidence; carry forward the plan's deferred findings.
- [ ] **O2** At each weekly handoff, plan at most six Igor-hours, reserve four, record actual effort, and reestimate slipped work instead of stacking missed commitments.
- [ ] **O3** During the freeze, perform the agreed source/health checks and address material failures; keep expansion and cosmetic work deferred unless a new decision changes scope.
- [ ] **O4** Verify the real election-date transition on the served site when it occurs; distinguish that observation from the earlier simulated boundary checks.
- [ ] **O5** As real official results/certification become available, review evidence and mappings, use supported imports or the chosen fallback, verify publication and retain correction history.
- [ ] **O6** Reassess deferred imports, county expansion and card work using observed source readiness, maintenance effort and available human time.

## Completion record

Append evidence links here or in the relevant batch handoff as work closes.

| Date | Task / wave | Outcome or deferral | Evidence / next action |
|---|---|---|---|
| 2026-10-08 | Checklist preparation | Created from the remaining review plan; no remaining review marked complete | This checklist and linked plan |
