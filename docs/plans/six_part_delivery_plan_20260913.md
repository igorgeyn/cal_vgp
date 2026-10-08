# CalBallot: six-part delivery plan

**Updated:** October 8, 2026.

**Remaining reviews:** the [October 8 review plan](remaining_review_plan_20261008.md)
turns the open work into six review batches, with evidence requirements, Claude
handoffs, finding dispositions and revised October targets. Its batch numbers do
not replace the delivery-part numbers here. It proposes completing essential
refresh/election checks before county expansion; the accepted county sequence is
unchanged. Use it for the next content pilot and current review scheduling.

**Status:** Parts 1-2 are published and verified in release `3911602`, including
the real production cutover, complete public pages, private recovery update and
live desktop/mobile checks. Read the [release receipt](release_progress_20261008.md).
Parts 3-6 remain open.

**Current user-accepted order:** after this release, fill the existing 49 county
records with exact ballot questions and sourced explanations; then Alameda;
then reassess San Francisco/Contra Costa. The first three SB content drafts and
all 49 source-review packets are prepared, not loaded. Keep refresh operations,
election transition and results readiness visible alongside that work. October 5's
scheduled capture failed before execution; latest stored evidence is September 28.

The September target windows below have elapsed. Do not infer completion from
those dates. The October 3 handoff narrows the immediate sequence to the
October 5 reader goal. That deadline is now past; the October 8 receipt records
actual completion of the release gates. Card redesign remains deferred.

This is the current sequence following Claude's September 13 review and
Codex's independent checks. It supersedes the ordering in
[forward_plan_20260907.md](forward_plan_20260907.md). We will tackle the six
parts in order, with a concrete handoff at the end of each. This planning task
does not itself execute loads, scraping, publication, or external storage writes.
When implementation begins, use the active user instructions and existing
authorization; do not repeatedly ask for approval of routine steps.

## Objective, constraints, and evidence

By October 5, readers should find the correct statewide November slate and
useful San Bernardino/San Mateo records on consistent public pages. The project
must have a repeatable refresh procedure and a tested recovery path. Before
November 3, it must handle the election transition honestly and have a bounded
method for importing certified results or directing readers to official results.

- Budget approximately **10 Igor-hours/week**. Plan at most six and reserve four
  for unexpected review, source drift, and maintenance. More agent time does not
  eliminate review or integration costs.
- Keep publication a reviewed operation. Automate detection and verification
  before considering automatic publication.
- Two useful counties remain the commitment. **Alameda is deferred by default**;
  the September 18 checkpoint must not interrupt the core sequence.
- Card redesign is parked in
  [its separate plan](card_design_action_plan_20260913.md). No aesthetic expansion
  is included here beyond fixing task-blocking usability problems.
- Preserve integer IDs, source evidence, document grouping, editorial fields,
  and historical data ownership. Fix the current slate without indiscriminately
  rewriting historical records.

### Verified starting facts

On September 13, the [Secretary of State's qualified list](https://www.sos.ca.gov/elections/ballot-measures/qualified-ballot-measures)
listed **14 November 3 propositions** and stated that **ACA 13 was removed from
that ballot on June 25**. CalBallot's database/export contained four active
CA_SOS 2026 records, including ACA 13, with pre-proposition identifiers. Three
had null election dates and one a non-ISO date. This confirms the priority of
statewide correction; it is no longer a hypothetical investigation.

Other independently checked findings:

- The qualified-page parser accepts PDF links; the current official list links
  to HTML proposition pages.
- `pipeline.py check` logs a database run and has no `--db` argument. A copied
  database is not isolation unless the executed code actually uses it.
- The existing state scraper traverses multiple endpoints. Running it is not
  equivalent to a single read of the qualified page.
- San Mateo's 29 published records have no individual pages or sitemap entries.
- The individual-page builder is separate from the main generator, does not
  render the new document collection, and has its own status logic.
- The scheduled registrar workflow captures; it does not complete publication.
- HTML generation can warn and continue after a semantic-context failure.
- General UI pending logic is year-based; individual-page status also needs work.
- A documented, tested off-machine recovery path is absent. This is not proof
  that Igor has no external backup.

Recheck dated source facts and HEAD when starting. The expected current count
is 14, not a permanent hard-coded assertion for future elections.

## Sequence and milestones

| Part | Outcome | Target window | Dependency |
|---|---|---|---|
| 1 | Correct statewide data and a reviewed isolated candidate | September 14–16 | Current source evidence |
| 2 | Corrected public site, complete page bundle, tested recovery | September 16–18 | Part 1 |
| 3 | Repeatable change detection and short refresh procedure | September 18–25 | Part 2's published baseline |
| 4 | Consistent election status and October 5 reader-readiness check | September 25–October 2 | Parts 1–3 |
| 5 | Bounded results support with verified identities and sources | October 5–16 | Part 4's status contract |
| 6 | Recovery, drift, and election-operation rehearsal plus handoff | October 19–23 | Parts 1–5 |

These are planning targets, not evidence of completion. Aim to freeze expansion
and nonessential changes October 26. If a part slips, reduce scope using the
fallbacks below; do not mark a gate complete merely to fit the calendar.

## Part 1 — Reconcile and correct the statewide November slate

**Outcome:** a fully explained correction, exercised on an isolated database,
ready for the production release in Part 2. Nothing remains ambiguous about
which records belong on the November ballot.

### Work

1. Record the current code revision and back up SQLite using a consistent backup
   method. Hash production inputs and use a new scratch location for all writes.
   Do not initialize the production application database to perform a read-only audit.
2. Preserve dated official source evidence for the qualified November list,
   relevant proposition pages, and withdrawal notice. Bound network work to
   those sources; do not start an all-source scraper or county capture.
3. Build a reconciliation ledger with one row per official proposition: number,
   title, election date, source URL, existing integer/canonical ID if matched,
   proposed action, and identity evidence. Add separate rows for current
   CalBallot entries that no longer belong on the November slate.
4. Distinguish the same measure receiving a proposition number from a genuinely
   new measure. Preserve existing stable IDs for matches. Quarantine ambiguous
   matches; a similar title alone is not sufficient.
5. Define a narrow representation for removal/withdrawal from the upcoming
   election. Preserve the ACA 13 record and evidence; do not silently delete
   history or assign a guessed later election date.
6. Implement either a bounded parser repair or a reviewed normalized input path.
   Handle HTML proposition links, election-section boundaries, numbering,
   source URLs, dates, and exclusion of withdrawal notes and other election years.
7. Make the database destination explicit and prove it points to scratch before
   any check/load. Do not assume changing `DATABASE_URL`, creating a copy, or
   changing the working directory redirects `Database()`.
8. Exercise the correction on the copy. Review exact changes and repeat the
   operation to demonstrate no duplicate records or unnecessary writes.
9. Generate an isolated main-site candidate from the corrected copy. Show the
   complete upcoming list, corrected labels, and removal from upcoming of ACA 13.
   Produce focused regression evidence for identity and source ownership.

### Deliverables

- Versioned reconciliation ledger and a short explanation of source/field ownership.
- Reusable isolated correction entry point or bounded parser repair with fixtures.
- Candidate database/build evidence, exact row/field diff, and next-step instructions.

### Done when

- Every currently qualified November proposition has exactly one intended record
  with a verified number, November 3 ISO date, and source link.
- Every old statewide upcoming record has a documented disposition.
- The withdrawn measure is absent from upcoming presentation but retained with evidence.
- Existing matched IDs, historical rows, registrar rows/documents, and unrelated
  editorial/enrichment fields are preserved.
- Repetition creates no duplicates; production inputs remain unchanged.

**Scope limit:** do not rebuild the entire statewide ingestion framework. After
roughly four agent-hours of unsuccessful parser repair, assess a reviewed input
file as the smaller path. An ambiguous match requires evidence, not a timer-based guess.
Do not wait for the next scheduled county capture to begin this part.

## Part 2 — Publish a complete, recoverable baseline

**Outcome:** the corrected data is public across the explorer and individual
pages; the release can be reproduced or restored without relying on undocumented
state on the current laptop.

### Work

1. Inventory everything the real build needs: measures database, identity/scope
   state, document associations, finance inputs, semantic model/embedding inputs,
   other enrichment files, code revision, and configuration. Identify what is
   reproducible and what requires custody. Keep credential recovery separate
   from publishing application data.
2. Establish a private off-machine recovery location using the user's selected
   storage arrangement. Preserve a pre-change backup and a manifest. Test restore
   into a distinct directory, including integrity, IDs, representative joins,
   and availability of required build inputs. A row count alone is insufficient.
3. Fix the page bundle contract: main HTML/JSON, individual measure pages,
   sitemap, and any other generated public assets must derive from the same
   accepted dataset. Include San Mateo and update San Bernardino pages.
4. Add grouped official documents and accurate capture wording to individual
   pages using the existing public document model. Preserve URL safety and
   composite packet semantics. Link back to the existing `#m=<id>` explorer route.
5. Give the individual-page builder a safe candidate-output path. Do not run its
   current delete/recreate operation against the working public directory during
   rehearsal. Check exact expected IDs/paths, not a target such as `12,361+ pages`.
6. Make missing required enrichment a release failure. Distinguish legitimate
   no-context records from failure of the enrichment process. Exercise the full
   production build with real inputs; do not substitute empty providers to get green output.
7. Inspect the next available SB/SMC production capture without triggering an
   extra one. Parse and compare it against the published snapshots. Include
   changes only after an explicit reviewed plan; an unresolved county change
   must not hold the statewide correction indefinitely. Report the retained county vintage.
8. Perform a bounded link-health check under the permitted source-access rules.
   Deduplicate URLs for requests, preserve per-measure reporting, and follow
   project redirect/robots/rate-limit rules. Treat HEAD failures and redirects as
   diagnostic results; use an allowed minimal GET where needed. A 200 response
   alone does not prove a usable document. Record unresolved exceptions.
9. Review the candidate bundle, apply the approved production load, generate the
   real artifacts, and verify actual outputs. Stage only intended code/docs/public
   assets and publish under the current authorization. Avoid accidental scraper
   workflow execution.
10. Check the served main pair, representative individual pages and document links,
    sitemap membership, and explorer deep links. Save an accepted-state recovery
    bundle and versioned release checklist; record published source IDs/hashes.

### Deliverables

- Complete public page bundle with statewide corrections and county document pages.
- Versioned publish checklist/entry point and actual deployment evidence.
- Recovery manifest, restore report, and off-machine accepted-state backup.
- Explicit published-source record, including any county data intentionally retained.

### Done when

- Public statewide membership matches the Part 1 ledger.
- Each intended public measure has its expected page and sitemap entry; documents
  and status do not contradict the explorer.
- Served artifacts match the accepted build/commit, accounting explicitly for
  any Git line-ending normalization.
- Recovery is demonstrated from the saved package, not merely asserted.
- No unintended historical, registrar, identity, or enrichment changes occurred.

**Scope limit:** do not turn this into general SEO, historical-date cleanup, or
an accessibility redesign. Missing individual pages weaken discoverability;
their creation does not prove search-engine indexing. If an unexpected large
page-builder problem appears, split out the verified statewide correction
release and retain a clearly documented remaining page-bundle task.

## Part 3 — Make a normal refresh routine

**Outcome:** capture health, parsed content, and public freshness are separately
visible. An unchanged week requires no Igor action; a changed week has a short,
reviewable path to publication.

### Work

1. Define the published-source manifest as an accepted-release record. A capture
   workflow must not advance it merely because capture or parsing succeeded.
2. Version the reusable parts of the release orchestration. Replace dependencies
   on dated ignored helper scripts with explicit inputs, outputs, and failures.
3. Extend the scheduled registrar path to parse accepted complete captures and
   compare them with the published baseline. Report added/removed measures,
   changed source fields, identity issues, role/URL/checksum changes, and
   provenance-only refreshes separately.
4. Distinguish `unchanged`, `changed`, `failed to evaluate`, and `idle/no scheduled
   election`. Missing snapshots, parse failures, and incomplete captures are not
   evidence that the public site is current.
5. Make the report discoverable through the existing workflow interface and
   record an operator follow-up path. Do not introduce outbound messaging or a
   new notification account without a concrete need and applicable authorization.
6. Implement the shortest safe changed-release procedure: explicit input scope,
   dry-run diff, consistent backup, atomic load, same-input no-write replay,
   complete build, preservation checks, artifact review, deployment verification,
   and accepted-manifest update.
7. Keep invariant checks for IDs, field ownership, document attachment, and required
   enrichments. Reserve expensive reference rehearsals for code/contract changes;
   do not throw away safeguards to achieve a shorter checklist.
8. Cover statewide freshness too: support a bounded qualified-list comparison
   through the repaired Part 1 path, or document a scheduled manual check against
   the published ledger. Registrar green must never imply statewide current.
9. Rehearse unchanged, document-only, substantive, and failed-parse scenarios.
   Use stored/synthetic cases when the next real capture is unchanged and label
   simulation honestly. Exercise a real routine run when evidence becomes available.

### Deliverables

- Versioned change report and published-source manifest.
- Short refresh runbook that reaches public deployment, not just R2 capture.
- Evidence of unchanged and changed paths plus failure handling.

### Done when

- An unchanged source can be evaluated without loading or regenerating production.
- A changed snapshot yields an intelligible field/document diff and actionable
  status; a parse failure cannot be mistaken for freshness.
- Accepted releases advance the public baseline only after verification.
- A normal changed release targets **at most one Igor-hour**, measured during
  rehearsal rather than assumed. Structural drift can take longer and is reported separately.
- The procedure works without knowing the September 8 scratch-directory layout.

**Scope limit:** no automated publishing, generalized drift-repair agent, new
county adapter, or overhaul of the F1 verifier. Its sealed HTML/unchanged-ID
assumptions cannot verify a new statewide insertion release unchanged; use
appropriate current invariants and evidence rather than weakening the old gate.

## Part 4 — Make election status honest on every surface

**Outcome:** the election date passing changes presentation correctly without
inventing a result. Current and historical records retain appropriate semantics.
Complete this before the October 5 reader-readiness milestone.

### Work

1. Inventory all outcome/date consumers: hero selection, local/statewide carousels,
   grid/list cards, modal, filters, individual pages, exports, and historical statistics.
2. Specify the shared status contract from verified election date, scope, and
   evidence: upcoming, awaiting a result observation, official results available
   externally when verified, unofficial observation when supported, and certified
   observation. Unknown dates/results need explicit neutral handling.
3. Normalize dates only where source evidence supports them. The Part 1 November
   records and current registrar election scopes provide known dates; do not
   assign an assumed November date to every historical record in a given year.
4. Remove year-based pending and hard-coded hero-election assumptions consistently.
   Preserve accepted historical outcomes even when historical dates are missing.
5. Use the election's local calendar consistently. Rehearse the day before,
   election day, November 4, and the year boundary. Avoid a UTC rollover falsely
   declaring the local election over.
6. Keep unknown results out of pass/fail aggregates. The date passing does not
   imply failure, a completed count, certification, or a particular yes share.
7. Show official result/source links. If verified unofficial results exist but
   CalBallot has not imported them, say so rather than implying the county has
   not released results. Show only genuinely recorded check/publication times.
8. Reconcile the regional-context qualification with the existing reviewed broad
   county/type comparison. Inspect San Mateo mappings; do not assert the cohort
   is city-only. If a comparison is unsupported or misleading, omit it with a
   narrow documented rule rather than inventing a regional statistic.
9. Run an October 5 reader-readiness check: find a measure, open its source documents,
   interpret its status, and reach its individual page on desktop and mobile.
   Measure one specified throttled mobile profile, including cold/warm loads,
   JSON parsing, first usable county cards, and optional DuckDB work separately.
10. Fix only demonstrated task-blocking performance problems, such as unnecessary
    eager optional work. Record remaining limitations. A small voluntary reader
    check can reveal confusion; analytics installation is not a prerequisite.

### Deliverables

- Shared status specification and consistent implementations/tests.
- Before/after evidence for clock boundaries and missing-data cases.
- Reader-readiness report with measured performance and outstanding limitations.

### Done when

- All public surfaces agree about the same measure's status.
- November 4 never leaves the finished election labeled upcoming and never
  fabricates pass/fail results.
- Missing dates, zero votes, unofficial observations, and certified outcomes
  remain distinct, with historical analytics protected.
- Supported statewide/county records and documents can be reached and understood
  in the exercised mobile flow; any blocking load problem has been addressed.

**Scope limit:** no general historical election-date correction, full mobile
redesign, new analytics service, or results scraper in this part.

## Part 5 — Add bounded, source-backed results support

**Outcome:** CalBallot can safely apply reviewed certified results to existing
measure identities, without assuming election-night staffing or new regional
aggregation capability.

### Work

1. Inspect official result formats and certification signals for the Secretary
   of State, San Bernardino, and San Mateo. Distinguish archives/examples from
   verified current-election endpoints; record source readiness and open questions.
2. Build reviewed mappings from official contest IDs to existing integer and
   canonical IDs. Include election, jurisdiction, source, and reporting scope.
   Resolve proposition/letter aliases explicitly; quarantine ambiguous matches.
3. Use a reviewed local input file as the initial ingestion interface if that
   is simpler than an automatic scraper. Default to **certified numerical imports**.
   Unofficial external results can be acknowledged and linked using Part 4.
4. Retain immutable observations with source URL/artifact checksum, capture and
   reporting times when known, certification evidence, totals, and scope. Select
   a current accepted observation; keep correction history.
5. Keep result ownership separate from document/source refresh ownership.
   Atomically update the accepted observation and supported outcome projection.
   A later registrar refresh must not erase results or alter document identity.
6. Reject stale/unmatched imports. Permit explicitly supported downward count
   corrections; a monotonically increasing count is not a valid freshness rule.
7. Treat county portions and region-wide totals distinctly. Do not sum or merge
   the transit measure across counties merely because the titles correspond.
8. Rehearse on copies: repeated input, revised certification, incomplete counts,
   zero/null distinctions, missing thresholds, ambiguous identity, regional scope,
   transaction failure, and an ordinary document refresh after a result import.
9. Define post-election capture retention explicitly. Election-page retirement
   and discovery requirements must not conflict when counties move pages into
   an archive. Do not simply extend an anchor by a guessed number of days.
10. Generate and review result-bearing candidate pages, preserving all other
    fields and unrelated enrichments. Document exactly which sources are ready.

### Deliverables

- Source/contest mapping ledger and readiness notes.
- Bounded results observation/import path with copy-based verification evidence.
- Documented presentation fallback and post-election capture policy.

### Done when

- A supported certified observation updates the intended existing measure,
  preserves history/documents, and survives a subsequent ordinary refresh.
- Unknown, unofficial, and certified information cannot silently contaminate
  one another or historical outcome statistics.
- Every published coverage area has an explicit results plan, including statewide.
  Do not recreate the statewide blind spot by designing only for county records.
- Unsupported source formats remain an honest official-link fallback, with no
  claim that ingestion or certification verification is ready.

**Scope limit:** no election-night service commitment, automatic winner calls,
regional total aggregation, or general results framework. If necessary, implement
the best-supported sources first and state the remaining coverage clearly.

## Part 6 — Rehearse operations and finish the handoff

**Outcome:** a short operational playbook and exercised failure paths make the
project maintainable through election day and certification.

### Work

1. Run a complete routine cycle from accepted source evidence through change
   report, review, load, full public bundle, and deployment verification. Use a
   real changed capture if available; otherwise identify the simulation clearly.
2. Restore an accepted recovery package in a fresh location. Demonstrate that
   the current full site can be built using the documented inputs and that IDs,
   Finance, documents, and selected results remain attached correctly.
3. Rehearse structural drift or missing capture: report evaluation failure,
   preserve the last accepted county data, and show its actual vintage/source
   links. Do not publish an incomplete snapshot as a successful refresh.
4. Rehearse failed generation, failed deployment, and a needed rollback. Keep the
   accepted public-source manifest accurate when database or deployment state
   differs. Define recovery of code, data, and generated artifacts together.
5. Exercise the November 3→4 transition and a later certified update through the
   real status and publication path. Verify the individual pages as well as the SPA.
6. Confirm the post-election capture policy with moved/retired page scenarios and
   no-results cases. A green idle run must not be reported as a new source check.
7. Write a compact operator runbook: cadence, where to see reports, unchanged
   week, changed week, failed evaluation, publication, recovery, official results,
   certification/correction review, and escalation to Igor.
8. Measure Igor involvement and separate routine review from drift repair. Record
   what remains manual and when an agent can decide without new product input.
9. Update the working list, source readiness, unresolved issues, and exact resume
   command/task. Freeze nonessential changes for October 26–November 3.

### Deliverables

- Rehearsal report, restore evidence, and concise operator runbook.
- Explicit outstanding limits, source coverage, and fallback states.
- A current resume point and post-election maintenance checklist.

### Done when

- The critical scenarios have actual evidence, not only instructions for a future test.
- A fresh agent can follow the runbook without relying on this conversation or
  ignored September release helpers.
- Routine review fits the intended time budget; exceptional drift is visible.
- The site can remain honest and useful if a county source or results importer fails.
- No live certification import is claimed before the official evidence exists.

## Effort, fallback, and deferred work

| Part | Agent effort estimate | Planned Igor involvement |
|---|---:|---:|
| 1 | 4–8 hours | 45–90 minutes |
| 2 | 6–12 hours | 1–2 hours |
| 3 | 6–12 hours | 1–2 hours |
| 4 | 5–10 hours | 45–90 minutes |
| 5 | 12–25 hours | 2–4 hours spread over October |
| 6 | 5–10 hours | 1–2 hours |

These are uncertain agent-effort ranges, not guaranteed unattended runtimes.
Reestimate after each part. Keep the weekly human contingency intact.

If capacity drops to five Igor-hours/week or drift becomes substantial:

- Protect statewide correctness, consistent public output, recovery, and truthful
  status. Simplify routine operation before attempting additional automation.
- Keep last accepted county data with explicit vintage and official links when
  a refresh cannot be validated. Do not present failure to check as no change.
- Reduce results implementation to reviewed imports for ready sources or official
  links until certification can be handled safely; importing later is acceptable.
- Defer cosmetic work, county expansion, analytics setup, broader performance
  tuning, and new discovery features.

At the September 18 Alameda checkpoint, retain the default deferment unless the
corrected statewide release is public, county freshness has been evaluated,
recovery is tested, the refresh path is bounded, and spare review capacity exists
without displacing Parts 3–6. Use material voter/operational blockers as the gate,
not every historical issue labeled above Low. Do not reopen expansion automatically.

Other deferred work: OCR, backfill, blocked counties, naming migrations,
automated drift-fix PRs, finance expansion, generated briefings, and regional
vote aggregation. The documented card plan remains available for later selection.

## Handoff format after every part

Record:

1. Outcome: what is implemented, rehearsed, or actually published.
2. Evidence: code revision, source snapshots, candidate/report locations, and checks.
3. Exact data/artifact changes and preservation results.
4. Unresolved issues and the selected fallback, if any.
5. Actual Igor/agent effort versus estimate.
6. The next part's concrete starting task.

Do not claim a deployment from a local build, recovery from a backup file alone,
freshness from a green capture, or results readiness from a design document.

### Restart prompt for Part 2

> Begin Part 2 of docs/plans/six_part_delivery_plan_20260913.md. Read
> docs/plans/statewide_part1_review_response_20260913.md and complete its pending
> correction batch before page generation. Then read the original Part 1 handoff
> and its ledger/evidence. Recheck HEAD,
> production hashes and the official slate before using the isolated candidate.
> Complete the main/individual-page/sitemap bundle with the same statewide
> assignments and grouped county documents. Establish the private off-machine
> recovery bundle and prove restore before publication. Preserve stable routes,
> identity, finance and historical data; explicitly handle the withdrawn record.
> Prepare the complete reviewable release, then publish under the active user
> authorization and verify the served artifacts. Finish with the Part 3 handoff.

## Progress

- [x] Part 1 — Statewide reconciliation and isolated correction; production unchanged.
- [ ] Part 2 — Complete public release and recovery baseline.
- [ ] Part 3 — Routine change detection and publication.
- [ ] Part 4 — Election status and reader readiness.
- [ ] Part 5 — Bounded results support.
- [ ] Part 6 — Operations rehearsal and handoff.
