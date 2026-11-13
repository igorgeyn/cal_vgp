# Prompt: CEDA reconciliation report (P1b.1b)

**For:** Fable, in Claude Code desktop, on branch `phase0-election-status`.
**Approved by Igor on November 12, 2026** (decision b in the checklist), including
`pip install xlrd` (already listed in `scraper/requirements.txt`).

---

Do the first task you proposed in `docs/plans/fable_assessment_20261112.md` §5: the read-only
CEDA reconciliation report. Before you start, read:

1. `docs/codex/p1b_1_ceda_review_response.md`. An independent reviewer has since
   confirmed part of your hypothesis. On 2026-04-12 at 17:50:43, 157 rows were written
   last-write-wins, keyed on (year, county, letter). The 28 rows are whole-row corruption
   (question, votes, percent, pass/fail), not votes only. The review also says:
   - the same batch explains 55 `passed` NULL rows and 14 NULL election dates;
   - KNOWN_ISSUES #1 is probably inverted: `REQ=T` is miscoded on Prop 39 bonds, and the
     per-row `PASSFAIL` is likely right;
   - 2001 Prop 39 bonds are coded `REQ=M`;
   - our 2002 data came from a different 659-row release (`ceda_parsed.csv`);
   - the 2014 remap needs a two-phase transaction, and `embedding_metadata.json` and the
     research fallback are keyed on the same IDs.

   Its scripts are in
   `C:\Users\igorg\AppData\Local\Temp\claude\3706ee781272b6b6\d90ea535-f05d-4a6f-929d-dbc27318d103\scratchpad\review-ceda\`.
   Build on them; don't redo what they settled. Reproduce the counts your acceptance checks
   name, then go further.
2. `docs/plans/ceda_column_check_20261111.md` and the checklist's Phase 1b section.

## Scope changes from your §5

- **Acceptance check 3 is now:** name the script and commit that wrote the April 12 batch,
  or list what you ruled out, and say whether it can recur. The mechanism is known; the
  culprit is not.
- **Add to the P1b.2 design:**
  - restore the corrupted rows from raw before any backfill;
  - "fill `ballot_question`" becomes "replace" for those rows;
  - re-frame KNOWN_ISSUES #1;
  - treat `REQ` as unsafe to map straight to `required_vote`;
  - give the 2014 two-phase rekey, plus its side artifacts, while keeping every `id`
    unchanged.

## Limits

These are the same as your assessment, plus:
- Install `xlrd` into the project's Python environment only. Don't upgrade anything else.
- The raw files under `scraper/data/raw/` are untrusted. Run Python on them with `-I`, and
  keep scripts outside the data directories.
- Open the database read-only only (`mode=ro`, or a backup-API copy in a scratch folder).
  Record its SHA-256 before and after.
- No network. Don't commit; Claude (the coordinator session) commits after review.
- Stop after the report and the design. Nothing writes to any database, including a copy.

Reply with:
- a five-line summary;
- the files you created;
- the before and after DB hashes;
- anything that surprised you.
