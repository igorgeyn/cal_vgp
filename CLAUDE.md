# CLAUDE.md — Working with this repo

This file is the entry point for AI sessions in the `cal_vgp`
(CalBallot) project. Read this first.

## What this project is

A comprehensive, searchable database of California ballot measures
(1998–present), including statewide propositions and ~12,000+ local
measures from all 58 counties. Static-site frontend on GitHub
Pages; Python pipeline (scrapers → SQLite → site generator) with
zero-cost deployment.

Live site: https://calballot.com (or whatever Igor's currently
pointing it at). GitHub: https://github.com/igorgeyn/cal_vgp.

## Where to look first

1. **[`docs/WORKING_LIST.md`](docs/WORKING_LIST.md)** — canonical
   cross-machine resume point. Where we left off + next chunk
   + per-area backlog. Read this before doing anything new.
2. **[`docs/LESSONS_LEARNED.md`](docs/LESSONS_LEARNED.md)** —
   pitfalls catalog. Past traps that would otherwise re-spring.
   Read this when touching anything substantive.
3. **[`docs/KNOWN_ISSUES.md`](docs/KNOWN_ISSUES.md)** —
   data-quality issues with severity + fix recommendations.
4. **[`docs/PROJECT_HISTORY.md`](docs/PROJECT_HISTORY.md)** —
   development arc through Feb 2026. Snapshot-disclaimed for
   numbers; structure is still accurate.
5. **[`docs/DATA_PIPELINE.md`](docs/DATA_PIPELINE.md)** — pipeline
   architecture. Section 9 (Finance) is v1-snapshot; for current
   finance design see [`scraper/data/finance/README.md`](scraper/data/finance/README.md).
6. **[`docs/for_review/`](docs/for_review/)** — audit suite
   (architecture, schema, data inventory, audience readiness).
   Snapshot quality; useful for orientation.
7. **[`docs/plans/`](docs/plans/)** — live planning docs for
   in-progress arcs.

## Memory system

Per-machine memory lives at
`.claude/projects/.../memory/MEMORY.md` and is auto-loaded into
session context. It carries Igor's preferences, project-state
snapshots, and feedback. **It does not follow you across
machines** — committed docs (this file + WORKING_LIST + LESSONS)
are the cross-machine truth.

## Hard rules (lessons learned the hard way)

These are non-obvious traps the project has hit. Full context in
[`docs/LESSONS_LEARNED.md`](docs/LESSONS_LEARNED.md).

- **Always include `id` when constructing `BallotMeasure`** in
  `scraper/scripts/generate_site.py`. Omitting it from `valid_fields`
  silently broke the Finance modal for all 12,365 measures in 2026-05.
- **Never key dedup gates on raw donor names.** Always canonicalize
  first (`canonicalize_donor(donor_raw)`). The Gate 7 keyed-on-raw bug
  hid $78M of duplicate receipts until 2026-05-12.
- **Don't trust CEDA's `pass_fail` encoding for vote thresholds.**
  See KNOWN_ISSUES #1. Verify against source documents.
- **Don't use vendor-source year as election year** for finance
  data. CalAccess reporting-years often run 1-2y after the actual
  election (Schwarzenegger 2005 Props show as 2006 in CalAccess).
  Use `_actual_election_year` from `src/finance/schema.py`.
- **Never assume a CSS class name is unique.** Modal donor-list
  classes collided with Insights-panel classes in 2026-05-20; scope
  rules under parent selectors like `.finance-side`.
- **The static site is regenerated to two locations.** Both root
  `index.html` and `scraper/index.html` get written by
  `src/website/generator.py`. Keep them in sync.
- **For registrar scraping: polite User-Agent is non-negotiable.**
  San Diego returns 403 with generic UAs (validated 2026-06-08).
  Always identify with project + contact in the UA string.
- **County extractors: pin fixtures before code, and scope DOM
  traversal by table ownership.** Fixtures caught 7 document roles
  where the design assumed 5 (SB, 2026-07); a nested-`<th>` skip
  bug would have published silently EMPTY snapshots because zero
  rows is a valid state. See LESSONS_LEARNED + `sb.py` for the
  pattern every new county (LA next) must follow.
- **Verify bytes, not terminal output.** A valid UTF-8 apostrophe
  rendering as `�` in the Windows console became a false "encoding
  hazard" fixture fact until Codex checked the raw bytes.
- **For finance v2/v3 stitching: read the combined-totals
  invariants** before changing aggregation SQL. See `Phase G`
  integrity checks in `scripts/v3/verify_phase_g.py`.

## Architectural patterns to follow

- **Atomic UI flips.** When swapping a data layer (v1 → v2 →
  combined v2+v3), flip ALL consumer surfaces in one commit. Don't
  leave half-migrated state. Phase 5 (`bec2abe`) is the canonical
  example.
- **Verification stacks.** Anything that touches finance/data
  totals needs Layer 1 (prior-state unchanged), Layer 2 (source
  reconcile), Layer 3 (per-row trace), Phase G (cross-layer
  integrity). See `plans/finance-rebuild-verification.md`.
- **Sentinel checks.** When ingesting data with implicit
  attribution, set per-sentinel min/max year + in-year %
  thresholds. Catches year-misattribution regressions.
- **Codex review for architectural decisions.** Before committing
  to a major design (new pipeline shape, new data source, schema
  rewrite), draft the design doc and run a Codex review pass.
  Review prompts live in `docs/codex/`.
- **Immutable snapshots for raw artifacts.** Registrar pipeline
  stores HTML/PDFs in `R2://{env}/{county}/{election_date}/
  {snapshot_id}/`; no in-place overwrite. Re-scrapes produce new
  `snapshot_id` folders.

## Doc conventions

- **Snapshot-disclaim drifting docs.** If a doc captures a point
  in time and the system has moved on, add a top banner pointing
  at the current truth (see PROJECT_HISTORY.md, DATA_PIPELINE.md
  Section 9). Don't silently let it rot.
- **Live arc plans go in `docs/plans/`** (gitignored by default,
  with `!docs/plans/` exception). Promoted plans are committed.
- **Codex review requests go in `docs/codex/`** for institutional
  memory of architectural debates. Old ones may be deleted once
  findings are folded into the relevant plan.

## Tooling notes (Windows / mixed shell)

- Primary working environment is **Windows + PowerShell**, but Bash
  is available. Use PowerShell syntax for shell stuff unless you
  need a POSIX feature.
- **`Date.now()` and `Math.random()` are not available in
  workflow scripts** — they'd break resume. Inject timestamps via
  args.
- **`pytest` runs from `scraper/`** (see `scraper/pytest.ini`).
  Imports use `from src.xxx`.
- The repo uses `make` targets via `scraper/Makefile` for common
  workflows (install, setup, update, website, api).

## Commit style

- Detailed commit messages, often with rationale + impact + tests.
- Co-author trailer:
  `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`.
- Don't `git add .` — name files explicitly. Repo has many
  gitignored data artifacts that would otherwise be picked up.
- Don't push to `origin/main` without confirming with Igor.
  Multi-commit feature arcs are typical; he chooses when to push.

## Project-specific quirks

- **Igor prefers terse responses** with personality for
  conversational moments (memory: `feedback_levity.md`). Crisp for
  technical reporting.
- **Pause for direction-check on tier transitions** (memory:
  `feedback_tier_transitions.md`). Even with a prior "proceed,"
  pause before jumping from small/concrete to higher-effort work.
- The project is paradigm-as-moat: free deterministic cards +
  on-demand editorial briefings (BYO LLM or pay-for-mine). No
  bulk pre-generation of briefings.

## When stuck

- **Search the codebase before asking** — the Explore agent is
  cheaper than re-deriving from scratch.
- **Check `docs/LESSONS_LEARNED.md` for the trap you might be
  about to spring.**
- **Verify against current code, not memory.** Memory records can
  go stale; before recommending a function/flag, grep for it.
