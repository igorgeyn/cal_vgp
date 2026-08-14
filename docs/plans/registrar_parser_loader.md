# Registrar parser and loader

Status: implementation plan, 2026-08-13.

## Goal and boundary

This stage turns one county election's immutable raw registrar snapshots into a
reviewable normalized JSONL file, then reconciles that file into the product
SQLite database. The parser never fetches the county website. The loader is a
dry run unless `--commit` is explicit, and every mutating run backs up the
database first. PDF bytes are checksum-verified but their text is not
extracted.

The first supported scope is San Bernardino (`sb`), election `2026-11-03`.
The implementation is deliberately county-extensible, but it does not pretend
that another county shares SB's field semantics.

## Verified repository and data facts

The following were checked against the repository and the local product
database on 2026-08-13, rather than inferred from the request:

- `extract_measures_page()` is the sole SB HTML extractor and returns the
  documented rows and eight document roles.
- The database contains 12,365 rows, including 344 whose county is exactly
  `SAN BERNARDINO` and 22 whose year is 2026 or later.
- All 22 2026-or-later rows are statewide. No existing row represents a
  November 2026 San Bernardino local measure.
- The 57 rows with neither an outcome nor a yes percentage are rendered by the
  existing static generator as pending/upcoming. It hides their result bar,
  adds an upcoming badge and disclaimer, and exposes `source_url` and
  `pdf_url`.
- The local raw store has two 8/9-row TBD-era observations and a complete
  20-row lettered August 14 observation from the same scrape family as the
  production snapshot. Shared document URLs connect most TBD rows to their
  lettered successors; exact semantics connect the changed Needles URL; unique
  jurisdiction plus threshold connects Beaumont despite `School Bonds`
  changing to `Bond Measure`.

## Snapshot selection and lineage

The product view is generated from **one snapshot: the requested complete
snapshot, or the latest complete snapshot by ascending snapshot ID when none is
requested**. An orphan without `manifest.json` is never eligible. This makes
the normalized file say what the registrar most recently published, rather
than unioning withdrawn and current rows.

The parser still replays every complete snapshot through the selected one.
Replay exists only to establish lineage. For every snapshot it:

1. verifies the manifest scope and cardinalities;
2. reads every artifact through `get_artifact()`, enforcing its recorded
   SHA-256 (PDF bytes are not interpreted);
3. runs `extract_measures_page()` over the stored `page.html`;
4. checks the extractor's documents against `pdf_artifacts` and the artifact
   inventory; and
5. links observations to prior lineages with one-to-one, successively weaker
   deterministic evidence: shared canonical document URL; assigned letter;
   exact jurisdiction/description/threshold; exact jurisdiction/description;
   then a jurisdiction/threshold key that is unique on both unmatched sides.

If a new observation cannot match but shares a jurisdiction with an unmatched
older lineage, parsing fails as ambiguous instead of silently minting a second
identity. Rows with no plausible predecessor begin new lineages. Snapshot row
numbers and storage filenames are never lineage evidence.

Only rows present in the selected snapshot are emitted. The loader reconciles
the whole validated scope, deactivating a previously loaded registrar row that
is absent from a later complete snapshot and reactivating it if its lineage
returns.

### Explicit identity (the fingerprint trap)

Every record supplies `measure_id`; the model is never allowed to regex-guess
it from `title` or `ballot_question`.

The exact format is:

```
REG_{COUNTY}_{YYYYMMDD}_{SHA256}
```

For this election it looks like
`REG_SB_20261103_<64 uppercase hex characters>`. The digest is the full SHA-256
of a canonical JSON array containing county slug, election date, origin-key
kind, and origin-key value. The origin is the earliest observation in the
lineage. Its key is the highest-priority canonical document URL available
(`resolution`, `text`, `analysis`, then the remaining roles); if it has no
document, the key is the normalized jurisdiction, description, and threshold.

This construction is collision-safe across counties and election dates before
the digest is considered, distinguishes multiple measures in one jurisdiction,
survives letter assignment and snapshot-local filename changes, and does not
change when a later snapshot adds documents. The full digest is retained
because truncation buys nothing here. The parser rejects duplicate IDs within
a snapshot. The resulting generated fingerprints are, explicitly:

```
fingerprint         = 2026|{measure_id}|SAN BERNARDINO|SB_County_Registrar
measure_fingerprint = 2026|{measure_id}|SAN BERNARDINO
```

## Normalized JSONL schema (version 1)

There is one object per selected-snapshot row, in table order:

```json
{
  "schema_version": 1,
  "county_slug": "sb",
  "election_date": "2026-11-03",
  "snapshot_id": "20260814T035115Z",
  "snapshot_row_count": 20,
  "table_row": 14,
  "scraped_at": "...",
  "page_sha256": "...",
  "lineage": {
    "origin_snapshot_id": "...",
    "origin_table_row": 7,
    "origin_key_kind": "document_url",
    "origin_key_value": "https://...pdf",
    "origin_key_sha256": "..."
  },
  "measure": { "measure_id": "REG_SB_...", "...": "..." },
  "documents": [
    {
      "role": "text",
      "source_url": "https://...pdf",
      "snapshot_filename": "measure_l_text.pdf",
      "sha256": "...",
      "size_bytes": 123,
      "content_type": "application/pdf"
    }
  ]
}
```

All rows must agree on scope, snapshot, page checksum, and row count. Table row
values must be unique and contiguous. That completeness contract lets the
loader safely reconcile missing registrar rows instead of treating a truncated
JSONL file as authoritative. The loader independently recomputes both the
origin-key checksum and the full identity digest from `origin_key_value`, so a
hand-edited or corrupted identity cannot enter the database merely by matching
the expected prefix and length.

The output path defaults to
`scraper/data/registrar_normalized/{county}_{election_date}.jsonl`. It is
gitignored and replaced atomically. Re-parsing unchanged artifacts produces
byte-identical JSONL.

## Field mapping

| `BallotMeasure` field | Value and rationale |
|---|---|
| `measure_id` | Explicit lineage ID above. Never inferred. |
| `measure_letter` | Registrar letter, including `TBD` if that is still the latest publication. It is display data, not identity. |
| `year` | Year parsed from ISO `election_date` (`2026`). |
| `state` | `CA`. |
| `county` | `SAN BERNARDINO`, verified as the existing 344-row convention. |
| `jurisdiction` | Registrar text unchanged apart from extractor whitespace normalization, e.g. `City of Needles`. Existing SB rows mostly leave this null, so no invented translation is applied. |
| `title` | `{jurisdiction} — {description}`. The generator separately prefixes `Measure {letter}`, producing a useful card headline such as `Measure L: City of Needles — Bond Measure` without embedding identity in prose. |
| `description` | Registrar's short measure-description/type label. |
| `ballot_question` | Null. It is not present in the table, and PDF extraction is deferred. |
| result fields | `yes_votes`, `no_votes`, `total_votes`, `percent_yes`, `percent_no`, `passed`, and `pass_fail` are null before the election. Null is the existing pending convention. |
| `vote_threshold` | Strict mapping: `50% + 1` to `50%`; `55%` to `55%`; `2/3` or `66.67%` to `66.67%`. Unknown values fail instead of being guessed. This field is useful despite the current database having it null everywhere; CEDA `pass_fail` suffixes are not trusted (KNOWN_ISSUES #1). |
| `measure_type` | `Measure`, matching an existing local-measure convention and avoiding unsupported topic inference. |
| topic/category fields | Null; classification is out of scope. |
| `data_source` | `SB_County_Registrar`, a stable machine label for the official primary source. |
| `source_url` | The selected snapshot manifest's official election page URL. |
| `pdf_url` | The `text`-role source URL only. It remains null when no full-text link is published; a resolution is not mislabeled as full ballot text. Every document URL remains in JSONL. |
| summary fields | `has_summary=false`; summary title/text null. The short registrar label is not promoted to an invented summary. |
| `election_type` | `general` for the November 3, 2026 general election. |
| `election_type_imputed` | `0`; this is a county-specific explicit mapping, not the database's month heuristic. |
| `election_date` | ISO `2026-11-03`. SQLite accepts it and the generator already handles ISO dates. |
| decade/century | Derived by `BallotMeasure`. |
| tracking fields | Created on insert. `updated_at`, `last_seen_at`, and `update_count` change only with a substantive accepted update or activation change, never for a no-op rerun. |
| active/duplicate fields | New rows are active and non-duplicate. Scope reconciliation may set `is_active=0`; it does not label an official withdrawal as a duplicate. |

## Deduplication and loading

The loader does not use generic content-hash deduplication: many legitimate
rows share short content such as `Transactions and Use Tax Measure`, so that
would recreate the identity bug in another form.

For each record it applies these gates in order:

1. exact registrar fingerprint: update that row only if mapped values changed;
2. same explicit `measure_id`: a mismatched scope/fingerprint is an identity
   conflict and aborts the load;
3. strict cross-source real-world match: normalized county, full election date,
   assigned measure letter, and compatible jurisdiction when both sides provide
   one; and
4. otherwise insert.

A single strict cross-source match is adopted in place: its database `id` and
any richer non-null results, ballot question, summary, or classification are
preserved, while official registrar identity/source and non-null registrar
fields become authoritative. Multiple candidates are a conflict. The current
database has zero such candidates: every existing 2026 row is statewide.

Before commit, the loader validates the entire file and plans all actions. Any
schema, identity, or dedup conflict prevents all writes. A commit with changes
creates a timestamped backup via `Database.backup()`, starts one SQLite
transaction, recomputes the plan, and applies inserts, updates, and scope
deactivations atomically. An exception rolls back the whole load. The report
separates inserted, updated, deactivated, skipped, and conflicts and includes
the backup path. Dry-run is the default and opens the database read-only.

### Idempotency

- Same snapshot twice: identical fingerprints and mapped values; every row is
  skipped, with no timestamp or `update_count` churn.
- New snapshot with only more document roles: JSONL changes, but if
  `source_url`, text-role `pdf_url`, and database fields do not, the row is
  skipped.
- New snapshot with a real mapped change: the stable lineage ID selects one
  row, changed fields update once, and `update_count` increments once.
- Newly published measure: one new lineage and one insert.
- Withdrawn measure: one deactivation; repeated loads skip it. A later
  reappearance reactivates the same lineage row.

## Pending-measure behavior

No generator changes are needed. These rows have year 2026 and null outcome
fields, which the existing Python-generated JavaScript treats as upcoming. The
card shows its measure letter, jurisdiction/type headline, official source, and
short description; the modal hides results and shows the pending disclaimer.
This is the minimal coherent representation until ballot-question PDF parsing
or post-election results ingestion is separately designed.

## Failure semantics

| Failure | Behavior | Writes? |
|---|---|---|
| No complete snapshot / requested ID absent | Parser fails with scope and available IDs. | No JSONL replacement; no DB write. |
| Artifact missing or SHA-256 mismatch | Store exception propagates; snapshot is not normalized. | None. |
| Manifest scope/cardinality/audit mismatch | Parser fails loudly, including extractor-versus-manifest document disagreement. | None. |
| Unparseable or schema-drifted page | Existing `SbSchemaError` propagates. | None. |
| Ambiguous cross-snapshot lineage | Parser fails rather than minting a likely duplicate identity. | None. |
| Malformed/truncated/mixed-scope JSONL | Loader validation fails before planning. | None. |
| Identity or multi-candidate dedup conflict | Report conflict; commit is refused. | None. |
| Backup failure | Commit aborts before transaction writes. | None. |
| Insert/update/deactivation failure | Roll back the one transaction; backup remains for review/recovery. | No partial load. |

## Verification plan

Tests use pinned SB HTML, synthetic checksum-valid artifacts, and temporary
SQLite databases only. The final manual verification parses the real local
20-row stored snapshot, copies `scraper/data/ballot_measures.db` to a temporary
path, loads that copy, inspects a field-by-field sample and dedup report, then
loads it again and proves row count, values, timestamps, and `update_count` are
unchanged. The live database is never opened writable.

## Deliberately deferred / open question

PDF text extraction, topics, summaries, results ingestion, other counties, and
site redesign are deferred as requested. No decision from Igor is required to
ship this bounded stage. Before enabling a live database commit in automation,
Igor should separately decide the review/approval mechanism; this deliverable
only supplies an explicit local `--commit` switch.

## Verification results (2026-08-13)

The completed implementation was verified without opening the live database
writable.

- Parsed the real stored dev snapshot `20260814T034259Z`, replaying all three
  complete local observations. The selected snapshot yielded 20 rows and 56
  checksum-verified documents. Its page SHA-256 is
  `8a7cd487edb2ec8adea9b1385fce2cc84740f7c700a8bbb7884ebdeb8f4da354`;
  the deterministic JSONL SHA-256 is
  `1b98522bdff8fd01c66ca1233b118898c5e026b7c0c33dec3829db7746ab1c7c`.
  Eighteen identities are rooted in an earliest document URL and two in a
  semantic origin where the earliest row had no document.
- Dry-run against the product DB reported `inserted=20, updated=0,
  deactivated=0, skipped=0, conflicts=0`.
- Copied the 12,365-row product DB, loaded only that copy, and obtained
  `inserted=20, updated=0, deactivated=0, skipped=0, conflicts=0`. The copy
  then had 12,385 rows, 20 active registrar rows, 20 distinct registrar
  `measure_id` values, and 20 distinct registrar fingerprints. All 22
  pre-existing 2026 rows remained present.
- The repeated-label cohorts remained distinct: seven `Bond Measure` rows,
  six `Transactions and Use Tax Measure` rows, and three `Municipal Code
  Amendment` rows each had one identity per real measure.
- A second committed invocation made no write:
  `inserted=0, updated=0, deactivated=0, skipped=20, conflicts=0`. The copied
  DB SHA-256 remained
  `C7BC439418381A2A87339950F77318D2C05A095EB1B2A5F0B20CC83447D04650`,
  the selected registrar-field state hash remained
  `9d019199ef7a695473d2cd703f6f2ad1b33b1522234c8c70146a6831776e7bc6`,
  and every registrar `update_count` remained zero.
- The live database SHA-256 was
  `73EEFB23F174C6FA31370CB5384C8C1AB318906BAE6C8E5871E3C1ABC2C860F1`
  before and after verification. The disposable copy and its backup were then
  removed.
- All 173 registrar tests pass (the prior 161 plus 12 new tests). The full
  repository run reported 382 passed and one skipped before the final
  identity-tamper regression was added; that additional test passes in the
  registrar run. The full run's remaining 17 setup
  errors and one assertion are unrelated existing contract mismatches in old
  database/model tests (`Database` is passed a string despite its documented
  `Path` API, and one test expects a null county despite the model's
  `Statewide` default).

Sample copied-database record, shown field-by-field:

| Field | Measure L value |
|---|---|
| `measure_id` | `REG_SB_20261103_973A2809DB723F30E501E63BF54BA0509D16621BE09359AF490A514284B55F63` |
| `measure_letter` | `L` |
| `year` / `election_date` / `election_type` | `2026` / `2026-11-03` / `general` |
| `state` / `county` | `CA` / `SAN BERNARDINO` |
| `jurisdiction` | `City of Needles` |
| `title` | `City of Needles — Bond Measure` |
| `description` | `Bond Measure` |
| `vote_threshold` | `66.67%` |
| `measure_type` / `data_source` | `Measure` / `SB_County_Registrar` |
| `source_url` | `https://elections.sbcounty.gov/elections/2026/1103/measures/` |
| `pdf_url` | official `/CityofNeedles/30/FT_CityofNeedles.pdf` URL |
| question, vote, outcome, and summary fields | null (with `has_summary=0`) |
| active / duplicate / update count | `1` / `0` / `0` |

Production R2 credentials were not present in this environment, so the
production ID `20260814T035115Z` was not downloaded. Verification used the real
complete local dev snapshot from the same August 14 collection, not a test
fixture; no network access was needed.
