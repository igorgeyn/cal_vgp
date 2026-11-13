# Codex review request: P0.1 election status and official results links

**Branch:** `phase0-election-status` (local, not pushed). **Base:** `main` at `c7dc0efa`.
**Tracking:** [checklist](../plans/local_measures_checklist_20261107.md), chunk P0.1.
**Plan:** [local measures plan](../plans/local_measures_completion_plan_20261105.md), Phase 0.

## Context

The November 3, 2026 election has passed, but the live site still labels all 63 current
measures "Upcoming". The old rule was year-based (`year >= 2026` in the explorer,
`year >= date.today().year` on static pages), and the site was not rebuilt after October 8.
This chunk replaces it with one date-driven rule and adds checked links to official results.
It is the first of four Phase 0 chunks; the release itself is P0.3/P0.4.

## What to review

| File | Change |
|---|---|
| `scraper/src/website/election_status.py` | New. The rule, link loading and validation, the browser half (`ELECTION_STATUS_SCRIPT`) |
| `scraper/src/website/generator.py` | Attaches statuses at build; routes every explorer consumer through the rule; results link and note; CSS |
| `build_measure_pages.py` | Static page badge, status line and results link |
| `scraper/scripts/generate_site.py`, `build_release_bundle.py` | Explicit `--as-of` |
| `scraper/src/website/data/official_results_links.json` | Three reviewed links and their recorded checks |
| `scraper/scripts/check_official_results_links.py` | Link checker |
| `scraper/scripts/check_election_status_browser.py` | Browser checker used as evidence |
| `scraper/tests/test_election_status.py` | 41 tests, including a Node parity test of the two rule halves |

Evidence is in the checklist (P0.1.10-P0.1.14): test counts, the scratch build's page diff
(63 changed, 12,309 identical) and browser runs at five clock settings and three widths.

## Questions

1. **Rule correctness.** Precedence is withdrawn, then recorded outcome, then stored votes
   (unknown), then date. Is treating any stored vote figure or `pass_fail` as "not pending"
   right? It was added after the first build marked 48 CEDA 2011 rows (votes present,
   `passed` NULL) as pending. Is any surface or consumer missed?
2. **Browser clock.** The explorer re-evaluates the date part with the reader's California
   date, forward only. Is that worth having, given static pages cannot do the same? Any failure
   mode with bad clocks or time zones beyond those tested?
3. **Wording.** "Results pending" replaces the plan's "Counting votes" (see the handoff for
   why). Are the status sentence and modal note accurate and free of outcome or certification
   claims?
4. **Link checks.** A link shows only if its newest check passed: HTTP 200 plus expected page
   text, with bot-challenge pages counted as failures; or a person's `manual_check`. Is that
   enough? Should a failed or stale check block a release rather than silently hide the link?
5. **Build guards.** Strict builds stop when a current-cycle row lacks a date, or when an older
   row would show a pending status. Could either block a legitimate release, for example when
   Phase 3 replaces year-based section selection?
6. **Reproducibility.** `--as-of` defaults to today in California. Should
   `build_release_bundle.py` require it?
7. **Tests and checker.** Gaps in the tests or in `check_election_status_browser.py`?

## Not in scope

The history-label fix (P0.2), the release (P0.3/P0.4), result numbers (Phase 2) and the
layout (Phase 3). The 1 failing and 17 erroring tests also fail on untouched `main`.

## Please return

A verdict (**ready**, **ready with changes** or **not ready**), then findings ranked by
severity, each with file and line, the evidence, and a concrete fix. Separate demonstrated
defects from suggestions.
