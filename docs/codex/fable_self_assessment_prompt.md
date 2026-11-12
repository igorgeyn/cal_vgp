# Prompt: pick your own work on CalBallot

**For:** a fresh Claude Code session (Fable) with no prior context.
**Type:** read-only assessment. Write one file; change nothing else.

---

You're joining CalBallot (repo `cal_vgp`), a searchable database of California ballot
measures from 1998 on: a Python pipeline (scrapers → SQLite → static site generator) published
on GitHub Pages. Work is in progress on branch `phase0-election-status`. Igor, the owner,
wants your own judgment on where you'd add the most value, before he assigns you anything.

## Read first, in this order

1. `CLAUDE.md`, especially the hard rules.
2. `docs/WORKING_LIST.md`
3. `docs/plans/local_measures_checklist_20261107.md`, the live tracker for the current arc.
4. `docs/plans/local_measures_completion_plan_20261105.md`
5. `docs/plans/agent_execution_plan_20261111.md`
6. `docs/codex/PENDING.md` and the review responses in `docs/codex/`, especially
   `layout_direction_a_review_response.md`, `p1_1_census_review_response.md` and the ruling
   at the end of `bot_challenge_rule_question.md`.
7. `docs/LESSONS_LEARNED.md` and `docs/KNOWN_ISSUES.md`
8. `docs/plans/local_explanations_parity_plan_20261111.md`, a deferred plan written to be
   handed to a model.

Then go into the code (`scraper/src/website/`, `scraper/scripts/`, `scraper/src/scrapers/`,
`scraper/tests/`) as far as you need to judge how hard each candidate task really is.

## What to produce

Write `docs/plans/fable_assessment_20261112.md` with:

1. **Your read of the project:** where it stands, what blocks the next release, and what you
   think is under- or over-prioritized. Disagree with the plan where you have reason to.
2. **Your strengths and limits, honestly.** Which kinds of work here you expect to do well,
   and which you'd rather leave to another model or to Igor.
3. **The 3–5 tasks you'd take on, ranked.** For each give:
   - scope;
   - why it's high-impact;
   - what it depends on;
   - your estimated size;
   - how a reviewer would verify it, meaning tests, a diff gate or evidence;
   - the main risk.
4. **Tasks you'd decline or defer, and why.**
5. **A first-task proposal:** the exact files you'd touch, the acceptance checks, and what
   you'd hand back for review.

Be specific; cite `file:line` where it matters. Keep it to about two pages.

## Hard limits

- Read-only, except for the one file above. Don't commit; Igor will decide.
- No network requests of any kind: no fetching county or SOS sites, no downloads.
- Don't open `scraper/data/ballot_measures.db` or any finance database for writing. A
  read-only query is fine if it truly helps your judgment; say so in the output if you run one.
- No builds, no `git push`, no branch changes, no edits to `.env`.
- Don't start any of the tasks. This is the assessment only.

When done, reply with a five-line summary and the path to your file.
