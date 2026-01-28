# Audit Report

## Executive Summary
- All 7 expected files under `docs/for_review/` exist and have been audited against the current repo state on branch `docs-audit-p1-consistency`.
- Core DB metrics are correct across all docs: 12,156 active measures, 1998-2026 range, 10,908 with vote data, 3,457 summaries, 66.1% pass rate.
- P0 issues (from prior audit) have all been resolved.
- P1 issues (export field counts, schema column count, source IDs, quiz description, data inventory, server imports) have been resolved in commit `202b40c`.
- Remaining issues are P2 (cosmetic or minor accuracy) and are documented below.
- No P0 issues remain. No P1 issues remain. Only P2 items persist.

## Scorecard (0-5)
| Document | Factual Accuracy | Evidence Quality | Completeness | Actionability | Audience Fit |
| --- | --- | --- | --- | --- | --- |
| `PROJECT_OVERVIEW.md` | 4 | 3 | 4 | 3 | 4 |
| `FEATURES_AND_UI.md` | 4 | 5 | 4 | 3 | 4 |
| `DATA_INVENTORY_AND_SOURCES.md` | 4 | 4 | 4 | 3 | 4 |
| `SCHEMA_AND_IDS.md` | 4 | 4 | 4 | 3 | 4 |
| `ARCHITECTURE.md` | 4 | 4 | 4 | 4 | 4 |
| `RESEARCHER_READINESS.md` | 3 | 3 | 3 | 3 | 3 |
| `PRACTITIONER_READINESS.md` | 3 | 3 | 3 | 3 | 4 |

Note: Scores improved from prior audit due to P0+P1 fixes. `RESEARCHER_READINESS.md` and `PRACTITIONER_READINESS.md` still have unverified numeric examples.

## Resolved Issues (P0 + P1)

The following issues from the prior audit have been fixed:

1. **Export field counts** — Docs now correctly state 25 CSV columns (24 DB + 1 computed `summary_length`) and 21 JSON fields.
2. **Schema column count** — `models.py` SCHEMA and dataclass now define 48 columns, matching the actual DB. `related_measures` and `relationship_type` added.
3. **Source ID canonicalization** — `SD_County_Registrar` and `OC_County_Registrar` replace the incorrect `San_Diego_County_ROV` / `Orange_County_ROV`. `UC_Law_SF` added to source table.
4. **Quiz description** — Dynamic generation documented with evidence; fixed "16 pre-loaded" claim removed.
5. **Data inventory** — UC Law SF, ceda_parsed.*, and summary_quality export added.
6. **Server imports** — `VERSION` added to `config.py`; historical imports made optional with `HISTORICAL_AVAILABLE` flag; 501 responses documented.
7. **Content hash** — Code snippet now shows `hexdigest()[:16]` truncation.
8. **Ballotpedia coverage** — Changed from "2002-2026" to "2006-2025" based on DB evidence.

## Remaining Hallucination / Accuracy Issues (P2)

H1. **"8 data scrapers"** (`PROJECT_OVERVIEW.md:79`).
- Actual: On this branch, `src/scrapers/` contains 5 files (`__init__.py`, `base.py`, `ballotpedia_statewide.py`, `ballotpedia_counties.py`, `ca_sos.py`). The county scrapers (LA, SD, OC, SB) are untracked. Counting non-base, non-init scrapers: 3 committed, 4 untracked. Either "3 data scrapers" (committed) or "7 data scrapers" (including untracked county scrapers) would be accurate, depending on scope.
- Recommendation: Update to "7 data scrapers" once county scrapers are committed, or "3 data scrapers" for current committed state.

H2. **"index.html 35 MB" / "35.3 MB"** (`PROJECT_OVERVIEW.md:25,90`, `FEATURES_AND_UI.md:5,315`, `ARCHITECTURE.md:51,202,350`).
- Actual: `index.html` is 35,323,534 bytes ≈ 33.7 MB (SI) or 35.3 MB in some contexts. The claim "35 MB" is close but not precisely "35.3 MB".
- Recommendation: Use "~34 MB" or "~35 MB" consistently.

H3. **`SCRAPING_CONFIG['headers']`** (`ARCHITECTURE.md:87`).
- Actual: `base.py:29-30` uses `SCRAPING_CONFIG['user_agent']` (not `['headers']`).
- Recommendation: Fix the code snippet to show `'user_agent'`.

H4. **Approval thresholds tracked** (`PROJECT_OVERVIEW.md:16`).
- "Track Results" claims "approval thresholds" are tracked. No `threshold` column exists in the schema. Some county scrapers use thresholds to compute `passed` but don't persist them.
- Recommendation: Remove "approval thresholds" or qualify as "pass/fail status".

H5. **Topic category counts** (`RESEARCHER_READINESS.md:128-141`).
- The table shows counts for 12 display categories (e.g., Education: 2,421) but the `topic_primary` column in DB stores 47+ raw categories, not the 12 display categories. The counts appear computed by aggregating raw→display mapping but are UNVERIFIED.
- Recommendation: Add SQL evidence or mark as approximate.

H6. **Reliability percentages** (`PRACTITIONER_READINESS.md:204-213`).
- "year: 100%", "county: 100%", "passed: 99%", "yes_votes/no_votes: 95%", "topic_primary: 90%" — no supporting evidence provided.
- Recommendation: Mark as qualitative assessments or add verification queries.

H7. **Practitioner use case numeric outputs** (`PRACTITIONER_READINESS.md:21,130-133,166-169,182-188`).
- "67 measures, 42% pass rate", "78% historically", "23 housing measures", "14 passed", "54% (n=23)" — all UNVERIFIED hypothetical examples.
- Recommendation: Mark as illustrative examples, not actual query results.

H8. **Export `--county` flag** (`RESEARCHER_READINESS.md:103`).
- `export_data.py` supports `--format`, `--output`, `--year`, `--summaries-only` but NOT `--county`.
- Recommendation: Remove `--county` from the example command.

H9. **Ballotpedia "vote counts (yes/no)"** (`DATA_INVENTORY_AND_SOURCES.md:31`).
- `ballotpedia_counties.py` extracts pass/fail only; yes/no counts parsed for statewide only.
- Recommendation: Clarify as "Vote counts (yes/no) for statewide; pass/fail for counties".

H10. **CEDA file format "ceda_YYYY.xlsx"** (`DATA_INVENTORY_AND_SOURCES.md:108`).
- Repo has `ceda_combined.csv` and `ceda_parsed.*`. Parser accepts `ceda*.csv` or `ceda_data_*.xls*`.
- Recommendation: Replace with actual filename.

H11. **CEDA records "10,909"** (`DATA_INVENTORY_AND_SOURCES.md:118`).
- `ceda_parsed.csv` has 11,050 rows (including header). Active measures from CEDA: 10,908.
- Recommendation: Clarify "10,908 active measures from CEDA" vs raw parsed count.

H12. **Fingerprint example uses `San_Diego_County_ROV`** (`SCHEMA_AND_IDS.md:229`).
- DB fingerprints for SD show `Ballotpedia` as source (county scraper not yet committed). `SD_County_Registrar` is the correct scraper-emitted ID but no records exist in DB yet.
- Recommendation: Update example to use an actual DB fingerprint like `2024|C|SAN DIEGO|Ballotpedia`.

H13. **City/district measure ID format `MEASURE_A_OAKLAND`** (`SCHEMA_AND_IDS.md:248-249`).
- `models.py` `extract_measure_identifier` produces `MEASURE_{letter}` without jurisdiction suffix.
- Recommendation: Remove `_{jurisdiction_code}` suffix or mark as planned format.

H14. **`BASE_DIR = Path(__file__).resolve().parent.parent`** (`ARCHITECTURE.md:484`).
- Actual: `config.py:15` uses `Path(__file__).parent.parent` (no `.resolve()`).
- Recommendation: Remove `.resolve()` from the doc snippet.

H15. **County registrar source IDs in source table** (`SCHEMA_AND_IDS.md:255-258`).
- `LA_County_Registrar`, `SD_County_Registrar`, `OC_County_Registrar`, `San_Bernardino_County_ROV` are documented but none appear in `SELECT DISTINCT data_source FROM measures`. Only `Ballotpedia`, `CA_SOS`, `CEDA`, `UC_Law_SF` exist.
- Recommendation: Note these IDs are emitted by untracked county scrapers and will appear once those scrapers are committed and run.

H16. **Ballotpedia coverage in source documentation** (`RESEARCHER_READINESS.md:160`).
- Says "2002-present" but DB shows 2006-2025.
- Recommendation: Update to "2006-present".
