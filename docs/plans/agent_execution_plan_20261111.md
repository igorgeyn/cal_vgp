# Agent execution plan — November 11, 2026

How the next stages of the [local-measures plan](local_measures_completion_plan_20261105.md)
are split across parallel agents. Progress stays in the
[checklist](local_measures_checklist_20261107.md). Codex does review only.

## Rules for every agent

- **Ownership:** each agent owns one chunk and its own files. Two agents never edit the same
  file. Code agents work in their own git worktree. Research agents write only new files in
  the main tree and never commit there.
- **Production database:** read-only. Builds use a SQLite backup copy in a scratch folder.
  Nothing writes the production DB until a reviewed backfill chunk and Igor's go.
- **No outward actions:** no push, merge, publish or R2 write. Never bypass a bot challenge,
  403 or empty 202; record it and move on.
- **Downloads:** downloaded files are untrusted. Each goes in its own new directory, and
  Python that reads them runs with `-I`.
- **Identification:** use a polite project User-Agent:
  `cal-vgp-research/0.1 (+https://github.com/igorgeyn/cal_vgp)`. No personal email.
- **Commits:** name files explicitly, never `git add .`. Use the CLAUDE.md trailer.
- **Handoff:** each agent ends with what changed, the evidence, open questions and a draft
  Codex review prompt.
- **Integration:** Claude (the coordinator) checks each handoff, merges the work onto
  `phase0-election-status`, updates the checklist and hands review prompts to Igor for Codex.

## Wave 1 (now)

| Agent | Chunk | Output | Depends on |
|---|---|---|---|
| **A: site fixes** (worktree) | **P0.2** history-list jurisdiction label, **P0.2b** "• Pending" changed to "Result unknown" on historical explorer cards (Igor approved Nov 11), **P2.0** checker fix R7 | Commits in its worktree; scratch build; page diff; browser checks; handoff; review prompt | P0.1 (done) |
| **B: county census** | **P1.1** census schema and the 10 largest counties not yet covered | `scraper/data/census/county_sources_2026.json` and a census note in `docs/plans/` | Decision 1 (all 53) |
| **C: CEDA downloads** | **P1b.1** download the 22 missing CEDA years and check their columns | Downloads in an untracked folder; column report in `docs/plans/` | none |
| **Claude** | Coordinate; write the Codex prompt for the layout review (decision 3) and the bot-challenge question; integrate; keep a local preview | Prompts in `docs/codex/`; checklist | none |

**Codex during wave 1:** the layout proposal review (decision 3). It can run now, because it
touches no code.

## Wave 2 (after Codex reviews wave 1)

| Agent | Chunk | Notes |
|---|---|---|
| Claude | **P0.3** release candidate: frozen workspace, strict build, preservation gate, browser checks, recovery bundle | One owner; it touches the release workspace. Includes the bot-challenge rule if Codex agrees. |
| A | **P1.2** generic capture tool: URL list into immutable R2 snapshots | **Needs Igor:** the User-Agent decision, because the registrar default includes his email |
| B1, B2 | **P1.3** census of the remaining ~41 counties, split north and south | Same schema as B; one file each, merged by Claude |
| C | **P1b.2** backfill on a database copy: combined multi-county results, place names, questions, thresholds, the 48 rows with no outcome | Never touches the production database; produces a changed-outcomes list for Igor (P1b.3) |

**Igor:** the P0.4 go-ahead to publish wave 1's fixes.

## Wave 3 (after wave 2 reviews)

| Agent | Chunk |
|---|---|
| A | **P2** results importers: SOS JSON and San Bernardino xlsx, with the observation store |
| B | **P2** San Mateo CSV importer and the multi-county rule |
| C | **P1b.3/4** verification layers, KNOWN_ISSUES entry, release prep for the repaired history |
| Claude | **P3** layout (Direction A), after Codex's layout review |

Later waves (P3b tab, P4 harvest waves, P6 certification sweep) are planned when wave 3
closes.

## Local preview

Explorer builds can't be opened from `file://`: the page fetches `measures-data.json`, and
browsers block that on `file://`. Serve the newest candidate over http:

```text
python -m http.server 8917 --directory <candidate>\site
```

Then open `http://localhost:8917/`. The coordinator keeps the newest candidate in
`scratchpad\preview\site`. The full path is given in chat.
