# Prompt: work the next item on the CalBallot working list

**For:** Fable, in Claude Code desktop, on branch `phase0-election-status`.
**Reusable:** paste the same line each time. Each run does **one chunk** of the
highest-ranked item that suits you, then stops for review.

---

## How to pick the item

1. Read `CLAUDE.md`, then `docs/WORKING_LIST.md`. That's the ranked list of all pending work.
2. Go down **Next** in rank order. Take the first item that is:
   - **not blocked**: check its "Blocked by" column and the "Waiting on Igor" table;
   - **not Igor's own task**, and not a release or publish (the coordinator does those);
   - **not already in progress** elsewhere: see **Now**, and check `docs/codex/PENDING.md`
     for Codex work.
3. If its plan says the first step is a design, do the design, not the build.
4. If nothing qualifies, stop and say why.

**As of November 13, 2026 (evening), this resolves to Next #3, P2, chunk (a0): revise the
design into its rules-and-evidence contract**, after Codex's review. #1 waits on Codex and
Igor; #2 is Igor's task. If the list has changed since then, follow the list, not this line.

## General rules (every run)

- **One chunk, then stop.** Don't start the next item.
- **No commits, pushes, branch changes, publishing or R2 writes.** The coordinator (Claude)
  inspects and commits your files and runs the reviews.
- **Don't edit** `docs/WORKING_LIST.md`, the checklist or `docs/codex/PENDING.md`, since other
  agents edit them concurrently. Put the updates you'd make in your reply instead.
- **No network.**
- **Databases read-only** (`mode=ro`, or a SQLite backup copy in a scratch folder). Record the
  production DB SHA-256 before and after any query.
- **Untrusted files.** Raw or downloaded files are untrusted: run Python on them with `-I`,
  and keep scripts outside the data folders.
- **Explore code.** Another agent may be editing `scraper/src/website/generator.py` and the
  Explore files. Don't touch them unless your item is Explore work.
- **Your limits.** Follow what your own assessment said about them
  (`docs/plans/fable_assessment_20261112.md`): you don't review your own work, and you flag
  editorial or visual calls for Igor.

---

## This run: P2 chunk (a0), rules and evidence (a design revision; no importer code)

Your design (`docs/plans/results_import_design_20261113.md`) was reviewed by Codex in
`docs/codex/p2_results_design_review_response.md`: **ready with changes**. Read the response
in full. Then **revise the design in place**, so it becomes the (a0) contract that later
chunks build against. Add a short "Revision, November 13" changelog at the top that maps each
review finding to the section that answers it.

**Address each of these:**
- **R1, multi-county outcome precedence.** It conflicts with `election_status.py:99` and
  `build_measure_pages.py:117`, which check raw `passed` first. Specify one shared outcome
  function for every surface: cards, modal, static pages, history statistics, Explore and
  exports. Give its exact precedence, including a portion with no combined result.
- **R2, privacy.** No public precinct CSV fixture. Use synthetic or redacted fixtures; full
  files stay private.
- **R3-R5, safe corrections:**
  - selection by the source report's own order, not the capture time;
  - an observation identity that a re-parse, a mapping correction or added certification
    evidence can't collide with;
  - tamper evidence beyond a predecessor hash;
  - mapping and certification evidence tied to the exact report and contest.
- **R6-R7.** Derived combined totals need more than "all counties certified". Write
  executable rules for zero totals, unknown approval rules and percentage units.
- **R8, captures.** One immutable timestamped folder per capture; a manifest binding; a hash
  command that excludes its own output; San Mateo's same-report summary PDF.
- **Codex's question 8 table.** Fold in Igor's answers where they're recorded in
  `docs/WORKING_LIST.md`, "Waiting on Igor". Mark the rest as still open.
- **The revised chunk order:** (a0); then (a1) SOS and (b) counties in parallel; then (c-core)
  with certification rehearsals; then the optional unofficial release; then (d). P2(c)
  precedes Explore E2c.
- **Interfaces for (a1) and (b),** precise enough that two builders can work in parallel:
  file layouts, schemas, the mapping format, and the validator's failure matrix.

Also **update the save list** in §1 to match R8 and §9. Igor is saving files now under a
per-capture timestamped folder, and he adds San Mateo's "Results on PDF".

**Also write** `docs/codex/p2_a0_review_prompt.md`, a Codex re-review prompt. It should ask
whether R1-R8 are closed, whether the (a1)/(b) interfaces are buildable, and whether any new
risk has appeared. It should end with: write `docs/codex/p2_a0_review_response.md` and commit
only that file.

**Reply with:**
- a five-line summary;
- the finding-to-section map;
- the updates you'd make to `WORKING_LIST.md` and the checklist;
- the decisions still needed from Igor;
- the production DB hash before and after, if you queried it.
