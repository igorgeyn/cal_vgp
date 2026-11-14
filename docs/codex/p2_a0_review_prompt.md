# Codex re-review request: P2 chunk (a0), the results contract

**Type:** design re-review only. Change no code and no data. Write one response file.
**Branch:** `phase0-election-status`. The revised design is uncommitted in the main checkout
unless the coordinator has committed it since; review the file as it is on disk and record
its SHA-256 in your response.

## What to review

`docs/plans/results_import_design_20261113.md`, revised after your review
(`docs/codex/p2_results_design_review_response.md`, `3b76947e`). It is now chunk (a0): the
rules-and-evidence contract that (a1), (b), (c-core) and (d) build against. Its "Revision,
November 13" table maps each of your findings to a section.

Igor's answers to the eight questions are in `docs/WORKING_LIST.md`, "Waiting on Igor".

## Questions

1. **Are R1-R8 closed?** For each, say closed, partly closed or open, with the section and
   what is still missing.
   - **R1:** is §4.2's precedence exact and complete? Test it in memory against the cases
     you raised: `passed=0` with `combined_passed=1`; a certified portion with no combined
     result; a grouped row with stored portion votes. Is §4.3's consumer list complete, and
     is §4.4's transport rule (extend `BallotMeasure` and `valid_fields`, keep `id`)
     sufficient?
   - **R2:** does §6 leave any route for a real precinct file into the repository?
   - **R3:** do §2.2 and §2.4 handle a re-download of an old report, a parser or mapping
     fix on unchanged bytes, added certification evidence, a retraction, and equal-order
     conflicts? Is the selection file truly the build input?
   - **R4:** do the canonical bytes, the anchors and the Git prefix check in §2.3 detect
     tail truncation and a changed last line? Is the single-writer append sound on Windows?
   - **R5:** are §3.1's mapping evidence and §3.3's certification binding strict enough?
   - **R6:** is §4.5's derivation rule safe, including the repeated-total check and
     invalidation when an input changes?
   - **R7:** do §3.2 and §5.2 make zero totals, unreviewed rules and percentage units
     executable? Is `certified_no_call` a sound way to show certified counts without a
     result?
   - **R8:** does §1.2 prevent replacement, bind the capture, and exclude the hash output
     from itself? Does the save list now include everything certification will need?
2. **Are the (a1) and (b) interfaces buildable in parallel (§7)?** Could two builders start
   from `contract.py` and the failure matrix without talking to each other? Name anything
   underspecified: a dataclass field, an error code, a file path, who owns a shared file.
3. **Is the chunk order right (§9)?** In particular (c-core) holding the certification
   rehearsals, the optional (c-release), and P2(c) before Explore E2c.
4. **Has the revision introduced any new risk or contradiction?** For example between the
   five status-order rules in §4.2 and the states in §5.1, or between the selection rules
   and a derived total whose inputs change.
5. **The six open questions in §10:** would you answer any of them differently?

## Constraints

- Production database read-only (`mode=ro`, or a backup-API copy). Its SHA-256 is
  `ef1359e482db2c54fe41068771932aaac7c9fc1db372e2e1d8cbbed1f505d9da`; confirm it is
  unchanged when you finish.
- No network. Do not fetch any results page, endpoint or legal text.
- Saved result files under `scraper/data/raw/results/2026-11-03/` are untrusted: run Python
  on them with `-I`, and keep your own scripts outside the data folders.
- No push, no build, no branch change. In-memory probes are welcome; say which you ran.

## Please return

Write `docs/codex/p2_a0_review_response.md` with:
- a verdict: **accepted**, **accepted with changes** or **not accepted**;
- a table for R1-R8: closed, partly closed or open, with evidence;
- answers to questions 2-5;
- any change that must land before (a1) or (b) starts, separated from changes that can wait
  for (c-core).

Commit only that file.
