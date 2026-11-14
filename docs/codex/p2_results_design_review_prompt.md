# Codex review request: P2 results import design

**Type:** design review only. Change no code and no data. Write one response file.
**Branch:** `phase0-election-status`. The design is uncommitted in the main checkout unless
the coordinator has committed it since; review the file as it is on disk.

## What to review

`docs/plans/results_import_design_20261113.md`: the design for showing results for the 63
measures on the November 3, 2026 ballot, first as unofficial, then certified.

Context to read first:
- `docs/plans/results_transition_20260907.md` (the earlier design and its rehearsal list);
- `docs/codex/layout_direction_a_review_response.md`, answer 2 (the six result states);
- `docs/codex/p1b_1b_revision_review_response.md`, finding N1 (`passed` per row, plus
  `combined_passed`);
- `scraper/src/website/election_status.py` and
  `scraper/src/website/data/official_results_links.json`;
- `scraper/src/scrapers/registrar/loader.py` (`_OUTCOME_FIELDS`) and `storage.py`;
- the checklist's Phase 2 outline in `docs/plans/local_measures_checklist_20261107.md`.

Sample files the design relies on, saved by script on November 5-7 (untrusted; read with
`python -I`): in
`C:\Users\igorg\AppData\Local\Temp\claude\3706ee781272b6b6\d90ea535-f05d-4a6f-929d-dbc27318d103\scratchpad\`,
`sos_returns.json`, `dl_results_links\7aef5a2d.bin` (a second SOS file), `sb_results.html`
and `dl_results_links\7b7d6674.bin` (the San Mateo page). If Igor's hand-saved files exist
under `scraper/data/raw/results/2026-11-03/`, use those too.

## Questions

1. **The ledger (§2).** Is a committed, hash-chained JSONL file a sound store, or should it
   be database tables as the transition design implied? Consider review, recovery,
   idempotent re-import, corrections, and the county expansion (about 460 measures).
2. **Keeping unofficial counts out of `measures`.** Does anything on the site, in Explore,
   in the county history code or in the release gates still pick up unofficial numbers by
   another route? Check `has_recorded_votes` and every reader of `passed`.
3. **The mapping (§3).** Does it fail closed in every case that matters? Check the
   statewide route through `statewide_ballot_entries.proposition_number` against the
   database (read-only), and the claim that the San Bernardino page lists exactly our 20
   measures. Is the identity check enough to stop a repeat of the Santa Cruz overwrite?
4. **Multi-county model.** Is it truly one model with the CEDA design: `multi_measure_id`,
   `passed` as the row's own result, `combined_passed` for the measure? Is "the state comes
   only from a whole-contest observation" right, and is the derived-sum rule safe? Are
   12418, 12421 and 12442 the only current multi-county measures?
5. **Outcome and display rules (§4).** Are the three integer rules right for California
   (strict majority; at least 55%; at least two-thirds; yes plus no as the denominator)?
   Is the true-side rounding rule sufficient? Should the 14 propositions carry a reviewed
   "majority" rule, and on what citation?
6. **The status contract change.** Is adding `unofficial` to `election_status()` consistent
   with the P0.1 rules (precedence, forward-only browser clock, strict build guards)? What
   would break in `check_election_status_browser.py`?
7. **Verification (§5).** Is anything missing from the importer tests, the rehearsal list
   or the preservation gate? Is the certification evidence rule strict enough?
8. **Chunks and timing (§6, §7).** Is the split buildable in parallel? Is the November 26
   cut-off for the unofficial display sensible? Which of the eight questions for Igor would
   you answer differently?
9. **The hand-save list (§1).** Is any file missing that the importers or the certification
   sweep will need? Is the folder and hashing convention adequate as evidence?

## Constraints

- Production database read-only (`mode=ro`, or a backup-API copy). Its SHA-256 is
  `ef1359e482db2c54fe41068771932aaac7c9fc1db372e2e1d8cbbed1f505d9da`; confirm it is
  unchanged when you finish.
- No network: do not fetch any results page or endpoint.
- Raw and saved files are untrusted: run Python on them with `-I`, and keep your own
  scripts outside the data folders.
- No push, no build, no branch change.

## Please return

Write `docs/codex/p2_results_design_review_response.md` with:
- a verdict: **ready**, **ready with changes** or **not ready**;
- findings ranked by severity, each with evidence (`file:line`, a query result, or a line
  from a sample file);
- answers to the nine questions;
- any change you would make to the chunk order.

Commit only that file.
