# Independent review: corrected Part 1 candidate, October 3

Review the completed correction batch and recommend whether CalBallot should
proceed to Part 2's release preparation. Treat Codex's claims and Claude's
earlier findings as hypotheses. Give your own assessment of correctness,
remaining risk, and the next work in priority order. Do not invent a findings
quota or recommend broad refactoring without a concrete reader/release need.

Read-only review. Do not modify implementation, tests, fixtures, plans, existing
databases, candidates, or evidence. Do not scrape, publish, commit, push, or
contact anyone. Temporary probes and reports may be written only inside a NEW
reviewer-owned directory under `scraper/data/statewide_recon/`. Never rerun a
command that replaces an existing output directory or targets the production DB.

## Establish scope and evidence

1. Read `CLAUDE.md`, any applicable `AGENTS.md`, `docs/LESSONS_LEARNED.md`, and
   `docs/WORKING_LIST.md`. Record actual HEAD/status. Relevant work is largely
   untracked, so `git diff` alone is insufficient. Preserve unrelated changes.
2. Read:
   - `docs/plans/statewide_corrections_20261003.md`
   - `docs/plans/statewide_corrections_evidence_20261003.json`
   - `docs/plans/statewide_review_approval_20261003.json`
   - `docs/plans/statewide_part1_claude_review_20260913.md`
   - `docs/plans/statewide_part1_review_response_20260913.md`
   - `docs/plans/statewide_reconciliation_20260913.md`
   - `docs/plans/six_part_delivery_plan_20260913.md`
3. Distinguish September's original candidate from the corrected candidate in
   `scraper/data/statewide_recon/20261003_corrections/`. Use its immutable
   `baseline.db`, `published-baseline/`, `candidate/measures.db`,
   `candidate/site/`, build records, preservation report, and browser evidence.
   September source bytes are reused deliberately; an October decision/rebuild
   does not make them October captures.

## Inspect independently

- Review `scraper/src/database/statewide_ballot.py`,
  `scraper/scripts/reconcile_statewide.py`,
  `scraper/src/website/generator.py`, `build_measure_pages.py`,
  the two statewide verification scripts, and `test_statewide_ballot.py`.
  Include the real CLI build's research, recommendations, embedding, and
  external-link consumers when assessing compatibility of year-qualified keys.
- Inspect the pinned review at
  `scraper/tests/fixtures/statewide/20260913/review-corrections.json` and the
  original evidence. Check the 14 propositions, three retained integer/canonical
  identities, eleven new keys, and ACA 13. A PDF can contain neighboring laws;
  an unscoped substring match is not identity verification.
- Compare actual descriptions in cards, all 14 modals, and static pages with
  the official evidence. Are legacy inaccurate explanations still reachable as
  current explanations through another UI path? Are attribution and capture
  dates clear? Distinguish preserved raw editorial fields from reader defaults.
- Open `/measures/1.html`, follow its explorer link, and independently load
  `/#m=1` in a fresh browser document. Search for ACA 13. Check explicit status,
  date, source, list view, status filters, and exclusion from the 14 upcoming
  propositions. A database row's existence is insufficient.
- TYPE `Prop 1`, `Proposition 1`, `Prop 3`, `Proposition 3`, `Prop 4`,
  `Proposition 4`, and year-qualified variants. Check full result identity and
  order, the first visible result, both historical/current records, year-filter
  intersection, and sort behavior. Merely finding the intended row somewhere
  is insufficient. Do not confuse same-document hash changes with initial
  deep-link navigation.
- Challenge the separate review pin and crosswalk with mutated review inputs
  in your own directory. Check swapped old identities, new-key collisions,
  source changes, DB drift, replay, rollback, and protection of baseline files
  even when `--scratch-root` is broad. A copy-ownership marker is an operational
  guard against accidents, not protection against a malicious local user.
- Independently verify preservation: all existing IDs and raw content,
  schema/indexes/triggers, SQLite sequence, unrelated tables, document groups,
  finance/Insights/recommendations, and production hashes. Expected public
  count is 12,372, including the withdrawal; qualified slate count is 14.
- Examine generated detail pages/sitemap and the scope of the browser checks.
  County document files, external links, DuckDB/AI services, deployment, and
  off-machine recovery are not proven by an offline browser run.

## Decision and next steps

Return findings ordered by severity, with precise file/line references,
reproduction evidence, reader/operational impact, and a bounded remedy.
Distinguish actual defects from missing tests, intentional one-shot limitations,
and work already reserved for Part 2 or later. Say explicitly where you disagree
with the prior review or Codex's response.

Recommend one of: **READY FOR PART 2**, **READY WITH SPECIFIC CONDITIONS**, or
**NOT READY**. Separately state publication blockers; this candidate has not
been approved for promotion or publication. It is October 3, the October 5
target is close, and Igor has roughly ten hours/week. Recommend the smallest
credible sequence for correct statewide coverage, useful SB/SMC pages, fresh
enough evidence, safe promotion, and tested recovery. Keep county expansion
and the card redesign deferred unless you can justify displacing those goals.

List checks actually executed and limits of your conclusion. A passing shared
verifier is supporting evidence, not a substitute for your independent review.
