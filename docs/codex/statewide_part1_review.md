# Independent review: Part 1 statewide correction

> This is the original September review prompt. For the corrected October 3
> candidate, use [the current review prompt](statewide_corrections_review.md).

Conduct a comprehensive, detailed review of CalBallot's first delivery batch:
the statewide November 2026 reconciliation and isolated correction candidate.
Your recommendation will determine whether we fix this batch before proceeding
or begin Part 2's complete release and recovery work.

This is a review request, not an implementation or publication request. Do not
change the implementation, existing tests, fixtures, plans, databases, or site
artifacts. Do not commit, push, publish, run a scraper, or contact anyone.
You may create temporary probes, database copies, logs, and your review report
inside a NEW reviewer-owned directory under `scraper/data/statewide_recon/`.
Keep the existing candidate and its evidence intact. Return your findings in
the conversation as well as any report you create.

Work independently. Codex's handoff, test counts, hashes, and completion labels
are claims to investigate, not conclusions to adopt. Disagree with the design
or the claimed readiness when the evidence warrants it. Do not invent a quota
of findings or treat style preferences as correctness defects.

## Context and the decision under review

The accepted strategy prioritizes correct statewide coverage and useful,
reliable San Bernardino/San Mateo coverage before county expansion or card
redesign. The working budget is about ten Igor-hours per week, with considerably
more agent execution time available. Human review and maintenance still cost time.

Part 1 should produce a correct, explained, reproducible candidate on an isolated
database. Part 2 will complete individual pages, sitemap, the publication bundle,
off-machine recovery, and publication. Parts 3–6 cover refresh operations,
election status, certified results, and operational rehearsal.

The review decision is **readiness to proceed to Part 2**, not permission to
publish the current main-site candidate by itself. Identify release blockers
even when they belong in Part 2, and distinguish them from defects that invalidate
Part 1's data or verification. Challenge that sequencing if a concrete dependency
makes it unsafe.

## Establish the actual state

The expected repository is:
`C:\Users\igorg\Desktop\personal\projects\cal_vgp`

1. Read `CLAUDE.md`, applicable `AGENTS.md` instructions if present,
   `docs/WORKING_LIST.md`, and relevant `docs/LESSONS_LEARNED.md` entries.
2. Record actual HEAD and working-tree status. The Part 1 recorded base is
   `ec650a290992da7c7f903800419e59b523de8e9d`; do not assume it is still current.
3. Read these planning and evidence files:
   - `docs/plans/six_part_delivery_plan_20260913.md`
   - `docs/plans/statewide_part1_20260913.md`
   - `docs/plans/statewide_reconciliation_20260913.md`
   - `docs/plans/statewide_candidate_evidence_20260913.json`
4. Inspect both tracked diffs and the new untracked files. Part 1 is uncommitted;
   reviewing only `git diff` or the latest commit will miss most of the work.
   There are unrelated pre-existing changes and untracked files; identify the
   relevant scope rather than attributing the whole working tree to this batch.

Primary implementation and test scope:

- `scraper/src/database/statewide_ballot.py`
- `scraper/src/website/generator.py`
- `scraper/scripts/reconcile_statewide.py`
- `scraper/scripts/verify_statewide_candidate.py`
- `scraper/scripts/check_statewide_browser.py`
- `scraper/tests/test_statewide_ballot.py`
- `scraper/tests/fixtures/statewide/20260913/` (including `review.json`,
  `before.json`, README, and all captured HTML/PDFs)
- Relevant `.gitignore` and resume-document changes.

Trace adjacent consumers when needed: database models/operations, the actual
site CLI, external-link generation, finance joins, semantic-context generation,
individual-page generation, and scheduled workflows. This is not a request to
review every unrelated subsystem.

Existing local candidate/evidence root:
`scraper/data/statewide_recon/20260913_part1/`

It contains `baseline.db`, `published-baseline/`, `candidate/measures.db`,
`candidate/site/`, `candidate/mirror/`, `candidate/build.json`, `build.log`,
`load-evidence.json`, `preservation-report.json`, `production-inputs-sha256.json`,
and `browser/`. Inspect actual artifacts where available. If any are missing,
state precisely what you could not verify; do not substitute a documented claim.

## Questions to resolve

### 1. Challenge the design before polishing it

Is the separate ballot-assignment/provenance representation an appropriately
small correction, or does it introduce conflicting sources of truth or brittle
special cases? Is retaining legacy canonical IDs while projecting proposition
numbers sound across the actual consumers? Is making ACA 13 inactive an adequate
way to preserve its history and represent its removal? Consider discoverability,
old routes, stale individual pages, and future refresh behavior.

If you recommend a different approach, name the concrete failure it avoids,
the smallest viable change, and its migration/review cost. Do not recommend a
new general framework merely because a dated correction could be generalized.

### 2. Verify source completeness and identity

Independently reconstruct the captured November slate from the official HTML
and inspect the relevant PDF sections. Do not merely compare one generated
ledger with another. Check election-section ownership, the unusual numbering,
withdrawal notes, other years, title/type agreement, and the neutral-description
boundary. Watch for adjacent propositions sharing pages in a law PDF.

Specifically test the evidence for:

- Existing integer 10960 / `INIT_1993` becoming Proposition 3, including the
  initiative-to-AG crosswalk and its inconsistent stored `INIT_2012` fingerprints.
- Existing integer 10956 / `SB_42` becoming Proposition 4.
- Existing integer 2 / the SCA 1 canonical string becoming Proposition 5,
  including the correct legislative session.
- ACA 13 / integer 1 being withdrawn without deletion or a guessed future date.
- Eleven genuinely new records, after accounting for all 22 old current/future
  CA_SOS rows, including inactive duplicates, AB 440, and malformed initiatives.

Separate a verified identity from a plausible policy/title resemblance. Inspect
whether the reviewed input, source manifest, and loader meaningfully bind the
decisions to evidence, and identify what still depends on human review.
Use the pinned sources for as-captured findings; no new scraping is authorized.
If current source verification is necessary, identify the exact unresolved
question and official URL without presenting the captured state as current.

### 3. Test database isolation, atomicity, and repeatability

Examine the default check mode, explicit destination/scratch-root requirements,
path resolution and file-alias handling, missing-file behavior, transaction
boundaries, preimage checks, collisions, full-cohort checks, rollback, and replay.
Can check mode initialize or write a database? Can apply reach production through
an overlooked path? Can concurrent changes be lost? Can a malformed, partial,
duplicated, or differently ordered review yield an accepted wrong slate?

Check schema constraints and state transitions as well as happy-path Python
validation. Determine what happens with partial prior application, assignment
drift, a different review, and later source refreshes. Examine whether the
scratch-only loader provides a practical, safe Part 2 promotion path.

### 4. Trace preservation across real consumers

Verify integer/canonical keys, source ownership, all old rows, editorial fields,
registrar identities/scopes/aliases, document associations, search indexes, and
unrelated tables. Check that allowed-change lists are narrow enough to detect
the regressions they claim to exclude.

Trace whether new `PROP_<number>` IDs can collide with historical IDs reused in
other years in recommendations, embedding lookup, finance, generated links,
SQL exploration, or detail-page naming. Verify the shared presentation boundary
and both main generator entry points, not only raw database contents.

Preserving old AI summaries is not proof that they remain accurate or are
presented honestly next to new official titles. Check for contradictions,
stale amounts, misleading source attribution, and whether a correction is
needed before release. Keep any broader editorial rewrite recommendation bounded.

### 5. Review the candidate as a reader

Inspect actual HTML/JSON and desktop/mobile behavior where tools permit. Check
numeric ordering, card/modal labels, all fourteen assignments, withdrawal,
retained `#m=<id>` routes, official source links, timeline/status, and proposition
search. Exercise ordinary UI interactions where useful; calling a rendering
function directly is not the same as proving a reader can reach it.

Check that the search change does not cause a surprising filter regression,
and that the default archive, county document groups, and historical Finance
remain usable. Identify incomplete or misleading wording. Card redesign is
deferred; focus on task completion, factual clarity, and actual usability defects.

### 6. Audit the verification itself

Check the asserted counts: fourteen propositions, three preserved matches,
eleven insertions, one withdrawal, 12,425 total rows, 12,371 active records,
272 county document roles, 239 displayed links on 49 measures, and 54 focused
tests. Confirm what was actually executed on the final source/candidate bytes.

Examine whether checks are independent of the implementation or merely repeat
its assumptions. Look for broad exclusions, unverified schema/sequence changes,
ignored missing values, weak hash coverage, swallowed build failures, skipped
tests, or assertions that accept unintended changes. Assess the explanations
for 129 regenerated null timestamps and the one topic-count decrement.

Do finance, Insights, recommendations, semantic context, and local context
survive the actual build? Do the reports cover the same candidate and code?
Do paired-output and production-unchanged claims cover the relevant artifacts?
Distinguish offline browser checks from live dependency/source verification.

## Verification boundaries

- Read authoritative databases through SQLite URI `mode=ro`, without application
  database initialization. Do not run `pipeline.py check`, all-source ingestion,
  the old release/publish helpers, or `generate_site.py --deploy`.
- Inspect commands before executing them. The handoff's verifier/browser commands
  write reports: redirect outputs to your NEW review directory, never over the
  original evidence. Run mutation probes only on copies you created there.
- Run relevant existing tests from `scraper/`, using a fresh reviewer-owned
  `--basetemp`. Add exploratory tests only in your scratch directory. Do not
  install dependencies or update snapshots just to obtain a passing result.
- If rebuilding is necessary, use your own database copy and explicit scratch
  output, set `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, and
  `HF_HUB_DISABLE_TELEMETRY=1`, and verify the real input/output paths first.
  Do not trigger model downloads, paid API calls, or root/mirror overwrites.
- State which tests, probes, artifact comparisons, and browser interactions you
  performed, their outcomes, and what you could not check. A test count alone is
  not evidence that the right properties were tested.

## Deliver the review

Lead with your recommendation: **READY FOR PART 2**, **READY FOR PART 2 WITH
CONDITIONS**, or **FIX PART 1 FIRST**, with a short explanation and confidence.
These labels do not authorize publication.

Then provide:

1. Findings ordered by severity. For each: a precise title, file/line or artifact
   reference, concrete trigger or reproduction, expected versus actual behavior,
   impact, smallest reasonable remedy, and when it must be fixed. Clearly label
   confirmed defects, plausible risks, and unanswered questions.
2. Your assessment of the identity decisions and design, including any premise
   you reject and the evidence for doing so.
3. Verification performed: commands/probes, results, exact artifacts reviewed,
   and limitations. Reconcile discrepancies with Codex's completion claims.
4. What is sound and should be retained, with supporting evidence. Do not force
   criticism of a defensible choice just to balance the report.
5. A short ordered action list: fixes needed before Part 2; issues to resolve
   during Part 2 before publication; and optional later improvements. Explain
   dependencies and identify only decisions that truly require Igor's input.

Be thorough in the reasoning that matters. Make the final recommendation useful
even if there are no blocking findings, and candid if the evidence cannot support
a confident verdict. Do not implement fixes during this review.
