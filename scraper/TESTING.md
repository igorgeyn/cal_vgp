# Testing & Validation Guide

This document defines the testing and validation practices for Cal VGP.
**All contributors (human and AI) must follow these practices when making changes.**

---

## Principles

1. **Fix data bugs, don't threshold around them.** If a check reveals corrupted data, fix it. Do not set thresholds to the current broken count and call it passing.
2. **Validation runs after every change.** Before committing, run `make validate`. If it fails, fix the issue.
3. **Reuse existing tools.** Do not rewrite validation logic that already exists in `check_export_contract.py` or `inspect_summaries.py`. Call them.
4. **Validation code is read-only.** Validation must never mutate the database. Use raw `sqlite3.connect()` with read-only mode, not the `Database` class (which may alter schema on init).
5. **Debt budgets, not free passes.** Known issues use `must_not_increase` policies — the count must not go up. Ideally it goes down.

---

## Commands

```bash
# Run unit tests (models, parsers, utils — uses temp databases)
make test

# Run full validation against live database (audit mode — reports everything, never fails)
python scripts/validate.py audit

# Run validation gate (fails on invariant violations or debt budget increases)
python scripts/validate.py gate

# Run both
make validate
```

---

## Validation Architecture

Three components:

### 1. Core validation library (`src/validation/`)

- `checks.py` — 10-15 pure check functions, each accepting a `ValidationContext` and returning `ValidationResult`
- `policy.py` — Typed policy file defining invariants (max=0), coverage floors (min>=N), and debt budgets (must_not_increase)
- `report.py` — Console formatting

Check categories:

| Category | Type | Behavior |
|----------|------|----------|
| **Invariants** | `max=0` | Hard fail. percent_yes in 0-100, fingerprint uniqueness, duplicate flag consistency, canonical sources, derived key consistency |
| **Coverage floors** | `min>=N` | Hard fail. Source record counts, statewide election year coverage, title completeness |
| **Debt budgets** | `must_not_increase` | Soft fail. Curly quotes, passed/percent disagreements, empty content hashes |
| **Info** | report only | Never fails. Summary coverage, URL coverage |

### 2. CLI entry point (`scripts/validate.py`)

Two modes:
- `audit` — runs all checks, prints full report, always exits 0
- `gate` — runs all checks, exits 1 if any invariant or coverage floor fails, or any debt budget increased

Also calls `check_export_contract.py` as subprocess (reuse, don't rewrite).

### 3. Pytest module (`tests/test_validation.py`)

One file with parametrized tests over invariant checks. Uses a `live_db_conn` fixture that opens the real DB read-only via `sqlite3.connect(..., uri=True)`. Does NOT use the `Database` class.

Marked with `@pytest.mark.validation` so it can be run separately from unit tests.

---

## What to Run When

| Scenario | Command | What it checks |
|----------|---------|----------------|
| Changed any source code | `make test` | Unit tests pass |
| Changed data pipeline or DB | `make validate` | Data integrity intact |
| Before any commit | `make test && make validate` | Everything |
| Weekly pipeline run | `python scripts/validate.py gate` | Automated check |

---

## Data Quality Checks (reference)

These are the specific checks implemented in `src/validation/checks.py`:

**Invariants (must be 0):**
1. `check_percent_range` — all percent_yes values in 0-100
2. `check_year_range` — all years in 1902-2030
3. `check_fingerprint_uniqueness` — no duplicate fingerprints among active records
4. `check_duplicate_invariants` — is_duplicate=1 implies is_active=0, master_id NOT NULL, no self-references
5. `check_canonical_sources` — all data_source values in {CA_SOS, CEDA, ICPSR, NCSL, Ballotpedia, UC_Law_SF}
6. `check_derived_key_consistency` — sample records, recompute fingerprint/content_hash, verify match

**Coverage floors (min >= N):**
7. `check_source_record_counts` — per-source minimums (CEDA >= 8000, etc.)
8. `check_statewide_election_years` — each even year 2000-2024 has >= 5 statewide props
9. `check_title_coverage` — >= 90% of records have non-empty, non-generic title

**Debt budgets (must_not_increase):**
10. `check_curly_quotes` — smart/curly quotes in enum fields (measure_type, etc.)
11. `check_passed_percent_agreement` — passed field agrees with percent_yes
12. `check_empty_content_hashes` — records with the empty-content hash value

**Info (report only):**
13. `check_summary_coverage` — % with summaries by source
14. `check_url_coverage` — % with source_url/pdf_url

---

## Fixing Data Bugs

When a validation check reveals a data bug:

1. Write a fix script in `scripts/` (like `fix_data_bugs.py` or `migrate_canonicalize.py`)
2. Always include `--dry-run` mode
3. Back up the database before running: `cp data/ballot_measures.db data/ballot_measures_backup.db`
4. Run the fix
5. Run `python scripts/validate.py audit` to verify the fix worked
6. Update the debt budget baseline in `src/validation/policy.py` if applicable
7. Regenerate the site: `make website`

---

## Unit Tests (`tests/`)

Existing unit test files (run with `make test` or `pytest tests/ -v`):

| File | Covers |
|------|--------|
| `test_models.py` | BallotMeasure dataclass, fingerprints, serialization |
| `test_database.py` | Database CRUD, search, statistics |
| `test_deduplication.py` | Duplicate detection, marking, reporting |
| `test_parsers.py` | Parser initialization, file discovery |
| `test_utils.py` | normalize_measure_data() |

Unit tests use temp databases and do not touch live data.

---

## Querying the Database

For ad-hoc data exploration:

```bash
# Interactive DuckDB REPL
python scripts/query.py

# One-off query
python scripts/query.py "SELECT year, COUNT(*) FROM measures GROUP BY year"

# Export to CSV
python scripts/query.py --csv "SELECT * FROM measures WHERE year=2024" > output.csv
```
