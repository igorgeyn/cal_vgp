# Registrar blocker remediation design

> Design date: 2026-08-14  
> Scope: the four registrar data-integrity blockers and the static-site output
> contract. No live database or deployed artifact is changed by this work.

## Safety invariants

1. A registrar load scope is `(data_source, county, election_date)`. Every
   committed scope records the last accepted snapshot ID, page checksum, row
   count, and load time in `registrar_load_scopes`.
2. Ordinary loads are forward-only. An older snapshot is a conflict. A changed
   checksum for the same snapshot ID is always a conflict. A reviewed rollback
   requires an explicit command-line value equal to the incoming snapshot ID;
   a reusable boolean switch is deliberately insufficient.
3. Observation and reconciliation are separate operations. Missing rows never
   deactivate automatically. A row-count decrease or any missing active ID is a
   conflict unless the operator supplies an explicit reconciliation value equal
   to the incoming snapshot ID. This is the initial withdrawal policy because
   neither a magnitude threshold nor two repeated observations proves that a
   source-side truncation is a genuine withdrawal. The exact-snapshot gate makes
   the ambiguous operation human-reviewed and auditable.
4. Parser lineage normally compares weak evidence only with the immediately
   previous snapshot's active set. Historical lineages may reactivate on a
   shared official document URL. A letter alone is never continuity evidence:
   a letter match whose semantic tuple disagrees is a conflict. Exact semantic
   equality may link a re-upload; jurisdiction plus threshold is only a
   conflict/proposed-review signal, never an automatic match.
5. Parsed IDs remain deterministic proposals whose origin digest is independently
   validated. On first database admission, `registrar_identities` assigns the
   canonical ID once and `registrar_identity_aliases` records exact document-URL
   and semantic aliases. Subsequent loads resolve an incoming proposal through
   that registry and retain the canonical ID. The registry row stores the original
   origin key, so its ID can be re-audited cryptographically. This preserves useful
   recomputation from immutable archives while preventing a newly restored earlier
   snapshot from changing an already published database identity.

The registry is database-resident because canonical IDs become public database
state, while parser output remains reproducible from the archive. It can be audited
by recomputing every canonical digest and replaying aliases against immutable
snapshots. It can be rebuilt losslessly only from a database backup or an exported
registry ledger; rebuilding from a changed archive alone may reproduce proposals,
not published canonical assignments. Therefore a registry export belongs beside
every approved database backup before live use.

## Loader schema and transaction

The two registrar tables and alias table are loader-owned additive SQLite schema.
They are created inside the same `BEGIN IMMEDIATE` transaction as the first accepted
load, after the pre-write backup. Dry runs inspect them read-only and never migrate
the target. The locked plan is recomputed after schema creation.

The watermark advances on every accepted newer snapshot, even when all measure
content is unchanged. Repeating the same snapshot/checksum remains a true no-op.
Conflicts produce no backup and no write. Reconciliation and rollback authorizations
are independent; a deliberately older, smaller snapshot needs both exact values.

## Identity evidence policy

No mutable single signal is universally sufficient. A unique shared document URL
is accepted for continuity only when it does not create a many-to-one claim; this is
the strongest available site evidence and enables genuine reactivation. Letter-only
continuity requires exact semantic corroboration. Exact semantics can link re-uploaded
documents when unique. We deliberately fail on description drift without a shared
URL rather than silently use `jurisdiction + threshold`; that case requires a later,
reviewed override mechanism if it occurs in production. The current Beaumont fixture
is a known such review case and will no longer be silently guessed.

The concrete prior failure is: snapshot S1 has A=proposal Alpha and B=proposal Beta,
with URLs U-A/U-B; S2 re-uploads both documents at V-A/V-B and swaps the displayed
letters, B=Alpha and A=Beta. The old matcher consumes the unique letter matches first,
so Alpha receives Beta's origin and vice versa. The fixed matcher raises on each
letter/semantic contradiction before any identity can be emitted.

## Site output contract

`scraper/scripts/generate_site.py` is the canonical production preparation path
because it attaches research briefings, external links, historical context, custom
statistics, and recommendations that do not fit the old `generate()` signature.
The script must not call private rendering methods or write files itself. Instead,
`WebsiteGenerator.generate_prepared()` renders already-prepared data and one shared
bundle writer stages and writes matching `index.html` and `measures-data.json`.

With no explicit `--output`, the deployed root pair is primary and the scraper-local
pair is an identical local-preview mirror, preserving the documented dual-write rule.
With explicit `--output`, only that directory receives a pair; this is the safe
scratch contract and never implicitly touches either tracked location. A
post-generation assertion requires every requested HTML and JSON copy to be
byte-identical, requires the HTML to fetch `measures-data.json`, parses the JSON, and
checks its record count. The two existing deployed HTML formats remain untouched in
this remediation; the next reviewed artifact regeneration will intentionally replace
both with the same split format.

## Test-first evidence plan

- Backward roll: load S2, then assert S1 is rejected with the S2 watermark intact.
- Transient truncation: load two rows, then assert a newer one-row snapshot cannot
  deactivate without exact reconciliation authorization; separately prove reviewed
  reconciliation and reactivation.
- URL re-upload plus letter swap: construct two parsed snapshots and assert the
  second raises instead of exchanging origins.
- Earliest-history drift: register a later-only proposal, then load the same current
  observation whose parser proposal changed after an earlier snapshot appeared;
  assert one canonical row remains and the registry still names the first ID.
- Site: generate an isolated pair (and a two-location temporary mirror in a unit
  test), then assert byte equality, fetch reference, valid JSON, and unchanged hashes
  for all three tracked deployed artifacts.

## Sequencing

Before building LA, Orange, San Diego, or Riverside, land the shared county
configuration boundary, corroborated lineage rules, assign-once registry contract,
scope watermark, and explicit reconciliation API. Otherwise each county will encode
different unsafe assumptions and fixtures against an API that immediately changes.
County reconnaissance and immutable raw capture may continue in parallel because it
does not depend on identity or loading and is time-sensitive.

Before any live database load, all four integrity fixes, registry export/backup
procedure, source-provenance handling for cross-source adoption, backup race/create-
only hardening, and a copy-based site generation review must pass. The shared site
writer may land now, but deployed artifact regeneration, pending-measure UX, document
display, historical backfill, and PDF extraction can wait. Building the remaining
capture/extractor layers first is sound; building four production loaders before the
shared integrity layer is not.

## Calibration of the prior review

The prior report overstated three points. First, a checked-in lineage registry is not
the best canonical authority: it would be awkward for recurrent unattended captures
and could diverge from published database IDs; the database registry plus exported
ledger is smaller and stronger. Second, requiring two later snapshots is not evidence
enough to authorize deactivation, so the earlier recommendation gave automation too
much confidence; explicit reconciliation is safer initially. Third, the reported
scratch JSON patch was described as exposing the production fix, but it addressed
only the requested output directory. Because the actual default was scraper-local
and the production script separately wrote root HTML while never invoking the JSON
writer, it would have left the deployed root JSON stale. Conversely, the core four
integrity findings remain blockers, and the static-site defect is worse than the
report's original scope.

## Implementation and verification record

The four adversarial tests were first run against the original implementation. The
focused run produced exactly four failures (11 passes): the smaller snapshot
committed and deactivated, the older snapshot committed and updated, the changed
origin inserted a second identity, and the re-upload/letter-swap case did not raise.
Those are behavioral failures, not tests that merely check for new API names.

Implemented:

- loader-owned `registrar_load_scopes`, `registrar_identities`, and
  `registrar_identity_aliases` tables, created only in a backed-up commit transaction;
- forward-only/checksum-stable loading with exact snapshot-valued rollback and
  reconciliation authorizations;
- assign-once canonical IDs with independent origin-digest audits and exact URL/
  semantic corroboration aliases;
- previous-active lineage matching, letter/semantic contradiction failures, and a
  single reviewed SB override for the otherwise ambiguous Beaumont description
  change; no `jurisdiction + threshold` auto-match remains;
- shared county configuration and date-derived, explicitly imputed election types;
- the corrected `NO-WRITE` commit-mode no-op label;
- one public prepared-site generation path and paired-asset writer; the production
  default is root + scraper mirror, while explicit output is scratch-only; and
- `vote_threshold` and `election_type_imputed` preservation in site preparation.

Verification on 2026-08-14:

- 182 focused tests passed: all 173 pre-existing registrar tests, eight new registrar
  tests, and one site-output contract test (76 warnings).
- The latest real three-snapshot replay produced 20 records. Its JSONL SHA-256 was
  identical before and after replacing the last weak lineage rule with the reviewed
  override (`8AF4C536...DD341D`).
- A live-DB copy loaded 20 inserts, then repeated as `NO-WRITE` with 20 skips. It
  contains one scope watermark, 20 canonical identities, 56 document aliases, 20
  semantic aliases, and passes `PRAGMA integrity_check`.
- Replaying the real oldest eight-row snapshot against that copy now plans zero
  changes and reports both the backward-snapshot and row-decrease conflicts.
- The production CLI generated only the explicit scratch pair: 6,013,708-byte HTML
  and 34,960,992-byte JSON. The JSON parsed as 12,332 records, including 20 registrar
  records, 20 distinct registrar IDs, 20 thresholds, and 20 imputation flags. HTML
  references `fetch('measures-data.json')`.
- The live database remained SHA-256
  `73EEFB23F174C6FA31370CB5384C8C1AB318906BAE6C8E5871E3C1ABC2C860F1`.
- The three tracked deployed artifact hashes remained respectively
  `9683A880...57D01` (root HTML), `3B0D9D41...A0601` (scraper HTML), and
  `1D4053C1...97FEB` (root JSON). No deployed artifact was regenerated.

A repository-wide 410-test run was also attempted. It reached 391 passes and one
skip, but has 17 errors in legacy database/dedup fixtures that pass string paths to a
`Database` implementation requiring `Path`, plus one legacy model expectation that
conflicts with the current `county='Statewide'` default. None is in registrar/site
code changed here; the required registrar suite is fully green.

## Deferred and decisions still required

This remediation does not implement cross-source provenance, create-only/single-
writer backup hardening, pending-measure UX, official-document presentation,
historical backfill, PDF text extraction, artifact regeneration, live loading, or
deployment. Before a live load, Igor still needs to approve the exact snapshot,
registry-export/backup procedure, explicit withdrawal operation, and provenance
model. The first correct tracked site regeneration remains a separately reviewed
large diff because it will deliberately replace the divergent root/scraper formats
and stale root JSON.
