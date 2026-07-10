# Codex review: SB fixture findings + design refinements (round 5)

> **For Codex:** Small, focused review round. In round 4 you drafted
> the Phase 1 SB scraper design; live fixtures were then captured
> (rollout step 1) and four fixture-driven refinements were appended
> to your design by Claude. You are reviewing the REFINEMENTS and
> the proposed rollout parameters — the round-4 design body is
> already settled, as are rounds 1–3.
>
> Self-contained; assume no prior-session context.

## Read, in order

1. `docs/plans/registrar_phase1_sb.md` — your round-4 design +
   Claude's red-team note + the "Fixture findings (2026-07-09)"
   section. The findings section is the review subject.
2. `scraper/tests/fixtures/registrar/sb/README.md` — the pinned
   fixture facts (supersede recon assumptions).
3. The fixtures themselves (same directory): `landing_measures.html`,
   `measures_2026_0324.html` (published state),
   `measures_2026_1103.html` (announced state), seven `pdf_*_v.pdf`
   files with `.meta.json` sidecars. Verify claimed facts against
   the actual bytes — don't take the README's word for it.

## What changed since your draft (the four refinements)

1. **Seven roles, not five** — Jurisdiction cell links a resolution
   PDF, Description cell links the ordinance (full measure text).
   Role assigned by COLUMN for those two, by LABEL within the
   Arguments list. New filenames `measure_{letter}_resolution.pdf`
   and `measure_{letter}_text.pdf`.
2. **"Announced" state is first-class** — rows with TBD letters and
   zero links are valid observations; expected documents are defined
   as link-bearing cells; such snapshots finalize with
   `pdf_counts {expected: 0, saved: 0}`.
3. **Off-origin PDFs are the norm** (`uploads.rov.sbcounty.gov`).
4. **Header contains `<br/>`; announced page has a Windows-1252
   byte inside declared UTF-8** — tolerant decode, pristine bytes.

## What to scrutinize

1. **Does refinement 2 weaken your fail-on-missing-PDF guarantee?**
   Adversarial case: a page that HAD links last week loses them
   (county pulls a document); the row now looks "announced" and the
   snapshot finalizes as a valid 0-expected observation instead of
   failing. Snapshots are observations and cross-snapshot comparison
   is the parser's job — is that framing sound, or does the scraper
   need a regression tripwire (e.g., compare expected-doc count to
   the previous snapshot's manifest)?
2. **Mixed-state pages.** As filing deadlines pass, one row may have
   links while another doesn't. Confirm "expected = link-bearing
   cells" handles mixed states with no additional rule.
3. **Role-by-column soundness.** Jurisdiction/description links get
   roles from their column regardless of label. Failure mode: the
   county adds a second link in one of those cells (e.g., an amended
   ordinance). Current design would — what, exactly? Define the
   rule: first link? schema failure? Recommend one.
4. **Anchor lifecycle — our own flagged worry, please pressure-test.**
   Proposed §9 answers: anchor list `("2026-11-03",)`,
   forward-window cutoff = run date, discovery must contain every
   static anchor. Contradiction risk: after election day the index
   may drop the 2026-11-03 link → "missing anchor" → county failure
   forever, even though nothing is wrong. The anchor list needs a
   graduation/pruning rule (e.g., anchors older than run date are
   exempt from the discovery-must-contain check, or get pruned in a
   reviewed commit). Recommend the exact rule — this decides whether
   the first cron after Nov 3 goes red.
5. **Filename additions** — `measure_{letter}_text.pdf` for the
   ordinance: clear enough, or should it be
   `measure_{letter}_ordinance.pdf` (SB's own RES_/ORD_ vocabulary)?
   One-word verdict is fine.
6. **Anything the fixtures show that both the design and the
   refinements still miss.** You have the actual bytes — look for
   surprises we didn't list (link attributes, tbody quirks, the
   second table on the landing page, meta.json gaps).

## Calibration

Verdicts per item with severity (blocker / should-fix / nit /
agree). Short round — the goal is a green light (or precise red
flags) for starting the pure extractor + SbScraper implementation
against these fixtures.
