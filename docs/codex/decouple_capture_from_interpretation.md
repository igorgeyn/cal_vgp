# Codex: decouple capture from interpretation in the registrar scraper

> **For Codex:** A refactor of the live registrar pipeline. It adds no
> features and no counties. It changes the economics of every county
> added after it, and it is recommended before county three.
>
> **Sequencing:** start from a clean tree *after* the compact-card
> publication lands (`docs/codex/publish_compact_cards_and_about.md`).
> Do not begin while that work is uncommitted.
>
> Self-contained; assume no session memory. Facts verified 2026-08-27.

---

## 1. The problem

The San Bernardino scraper is live and runs weekly. It has produced
**three drift events in five weeks**, roughly one per county per two
weeks:

| Date | Cause | Failure |
|---|---|---|
| 2026-08-10 | Analysis cell began carrying a second document type (Tax Rate Statement) | `'analysis' cell has 2 links (row 14)` |
| 2026-08-24 | Letter cell began carrying the Notice of Election | `unexpected link in 'letter' cell (row 1)` |

Both were the pipeline correctly refusing to guess, and that
strictness has real value — it caught five tax rate statements about
to be filed as impartial analyses. **Do not weaken it.**

The problem is *where* the strictness sits. Today the scraper must
recognize a document's **role** before it can download it, so an
unrecognized document type aborts the whole county run before any
manifest is written. **A red cron means that week's capture is lost**,
on data that is perishable — county sites publish, revise, and
eventually remove these documents.

At one county that is a minor annoyance. At ten counties it is roughly
five red crons a week, each losing a week of capture for that county.
This is the binding constraint on county expansion — see
`docs/plans/registrar_county_expansion_workplan.md` §5.

## 2. The change

**Capture everything; interpret later.**

The scraper should download **every link in the identified measures
table**, recording each one's row, column, label, and URL — without
deciding what any of them are. Role assignment moves to the **parser**,
which runs offline against immutable stored snapshots.

After this, a new document type is captured on schedule and produces a
**parse** failure — fixable whenever, from bytes already safely
stored, with nothing lost. Both events in §1 become non-events.

## 3. Required work

### 3.1 Split the extractor (`scraper/src/scrapers/registrar/sb.py`)

`extract_measures_page()` currently finds the table, parses rows,
assigns roles, and builds semantic filenames in one pass. Split it:

- **Capture layer** — emits every link in the table with `table_row`,
  `column`, `label`, `url`, and a neutral filename. No roles. No
  cardinality rules. No unknown-label rejection.
- **Interpretation layer** — a separate function applying
  `COLUMN_ROLES` and `LABEL_ROLE_COLUMNS`, enforcing per-cell
  cardinality and unknown-label failures. This is what the parser
  calls.

Keep both in the county module or split into a sibling — your call,
but the capture layer must not import role knowledge.

### 3.2 Neutral filenames

`measure_l_analysis.pdf` cannot be produced without knowing the role.
Use something column-derived and stable within a snapshot, e.g.
`row014_analysis-cell_01.pdf` — the *column* is known at capture time
even when the role is not. This is safe: filenames are snapshot-local
storage keys, never stable identifiers (established in an earlier
review round). They must still satisfy the storage validator: single
safe path components, no separators, no Windows reserved names.

### 3.3 Manifest schema v2

`pdf_artifacts` entries currently carry `role`. In v2 they carry
`column` and `label` instead. Bump `schema_version`.

### 3.4 Backward compatibility — the expensive part

**Five production snapshots already exist with v1 manifests**
(2026-07-27, 08-03, 08-14, 08-17, 08-28), and **snapshots are
immutable**, so that shape persists permanently. The parser replays
*every* snapshot to establish lineage, so it must read both formats
forever. `_audit_documents()` in `parser.py` also cross-checks
extractor output against the manifest on a tuple that includes
`role` — that comparison needs a version-aware path.

### 3.5 Ordering subtlety — get this right or identities shift

Measure identity digests the **highest-priority canonical document
URL**, where priority is `resolution > text > analysis > rest`. That
priority is **role-based**. So in the parser, roles must be assigned
**before** identity is computed. Getting this backwards silently
changes `measure_id` for existing measures, which would make the
loader treat all 20 live San Bernardino rows as new inserts.

## 4. What must still fail loudly

The scraper keeps failing the county on: measures table not found or
ambiguous, malformed rows, fetch failures and retry exhaustion,
non-PDF content where a PDF was advertised, and off-origin redirects.
Structural drift still stops capture — only **new document types**
stop stopping it.

The parser gains the failures the scraper loses: unknown labels,
duplicate labels, and per-cell cardinality violations. These must be
just as loud, and must still name the cell, row, and rule so the drift
runbook stays usable (`docs/setup/registrar_drift_runbook.md`).

## 5. Acceptance criteria

**The critical one:** parse all five production snapshots before and
after the refactor and assert the resulting **20 `measure_id` values
are identical**. Identity drift here would duplicate every live San
Bernardino row on the next load. Treat this as the gate.

Also verify:

- Both real drift cases now capture cleanly. Replay the 2026-08-24
  fixture (`measures_2026_1103_notice.html`) through the capture layer
  with the `notice` role **removed** from the role maps: the scraper
  must succeed, and the parser must fail loudly with a message naming
  the unrecognized label.
- v1 and v2 manifests both parse; a mixed-version replay works.
- Roles produced from v2 snapshots match those recorded in v1
  manifests for the same documents.
- The existing test suite passes:
  `python -m pytest tests/ -q -k "registrar or website"` from
  `scraper/`. The wider legacy suite has 18 known pre-existing
  failures — not yours.
- Test migration: SB fixture assertions currently checking roles as
  output of `extract_measures_page` move to the interpretation layer.

## 6. Constraints

- **Never write to `scraper/data/ballot_measures.db`.** Verify against
  copies. The 20 live measures are already loaded.
- Do not regenerate or commit deployed site artifacts — this change
  produces no site diff and should produce no artifact commit.
- Do not weaken any strictness rule; relocate it.
- The live cron runs Mondays 12:00 UTC. If your change lands mid-week,
  it takes effect on the next scheduled run — so the capture path must
  be correct before merge, not after.
- Never `git add .`; `pytest` runs from `scraper/`; Windows-compatible.

## 7. Report

State: the before/after `measure_id` comparison across all five
snapshots, which failures moved from scraper to parser, how v1
manifests are handled, the new filename scheme, and anything you
assumed or deferred.
