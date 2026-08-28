# Audit Fixlist

> **Snapshot: January 2026. Not current state.** This document is part of an
> audit suite written for a one-time external review and is preserved as a
> record of that review. The project has changed substantially since:
> the finance database was rebuilt twice (v2 in May, a combined v2+v3 read
> layer soon after), and a recurring **county registrar pipeline** was built
> June–August 2026, adding scrapers, an immutable artifact store in
> Cloudflare R2, a parser, and a loader.
>
> For current state, read [`../WORKING_LIST.md`](../WORKING_LIST.md) first,
> then [`../../CLAUDE.md`](../../CLAUDE.md).

## P0 (must fix)
- None found. All P0 issues from the prior audit have been resolved.

## P1 (should fix)
- None found. All P1 issues from the prior audit have been resolved in commit `202b40c`.

## P2 (nice to have)

### PROJECT_OVERVIEW.md
- Section: "Directory Structure" (line 79) | Change "8 data scrapers" to "7 data scrapers" (or "3 committed scrapers + 4 pending county scrapers"). Evidence: `ls scraper/src/scrapers/*.py` shows 3 non-base scrapers committed; 4 county scrapers are untracked.
- Section: "Core Purpose" (line 16) | Remove "approval thresholds" or change to "pass/fail status". Evidence: no `threshold` column in `models.py:229-296`.
- Section: "Architecture Pattern" (line 25) and "Directory Structure" (line 90) | Change "35 MB" to "~34 MB". Evidence: `index.html` is 35,323,534 bytes ≈ 33.7 MiB.

### FEATURES_AND_UI.md
- Section: "Website Interface" (line 5) | Change "35.3 MB" to "~34 MB". Evidence: same as above.
- Section: "Performance Considerations" (line 315) | Change "35 MB" to "~34 MB".

### DATA_INVENTORY_AND_SOURCES.md
- Section: "Ballotpedia" (line 31) | Clarify "Vote counts (yes/no)" as statewide only; county pages yield pass/fail without vote counts. Evidence: `ballotpedia_counties.py` has no yes/no parsing.
- Section: "CEDA" (line 108) | Replace `ceda_YYYY.xlsx` with `ceda_combined.csv`. Evidence: `ls scraper/data/raw/ceda*`.
- Section: "CEDA" (line 118) | Change "10,909 measures" to "10,908 active CEDA measures". Evidence: `SELECT COUNT(*) FROM active_measures WHERE data_source='CEDA'` → 10,908.

### SCHEMA_AND_IDS.md
- Section: "Fingerprint Format" (line 229) | Replace `2022|MEASURE_J|San Diego|San_Diego_County_ROV` with an actual DB fingerprint like `2024|C|SAN DIEGO|Ballotpedia`. Evidence: `SELECT fingerprint FROM measures WHERE county LIKE '%San Diego%' LIMIT 1`.
- Section: "City/District Measures" (lines 248-249) | Remove `_{jurisdiction_code}` suffix from examples or mark as planned. Evidence: `models.py:130-160` produces `MEASURE_{letter}` only.
- Section: "Data Source Identifiers" (lines 255-258) | Add note that county registrar IDs (`LA_County_Registrar`, `SD_County_Registrar`, `OC_County_Registrar`, `San_Bernardino_County_ROV`) are not yet in the DB; they will appear when county scrapers are committed and run. Evidence: `SELECT DISTINCT data_source FROM measures` → only 4 sources.

### ARCHITECTURE.md
- Section: "Base Scraper Pattern" (line 87) | Change `SCRAPING_CONFIG['headers']` to `SCRAPING_CONFIG['user_agent']`. Evidence: `base.py:29-30`.
- Section: "Config File" (line 484) | Change `Path(__file__).resolve().parent.parent` to `Path(__file__).parent.parent`. Evidence: `config.py:15`.
- Section: "Output Generation" (line 51) and "Website Generation Flow" (line 350) | Change "35 MB" to "~34 MB".

### RESEARCHER_READINESS.md
- Section: "Vote Data Quality" (line 28) | Qualify "Pass/Fail determination" — thresholds are not stored; pass/fail is computed by scrapers. Evidence: no `threshold` column in schema.
- Section: "Topic Categories" (lines 128-141) | Mark measure counts as UNVERIFIED or add SQL evidence. The `topic_primary` column stores 47+ raw categories, not the 12 display categories shown.
- Section: "Export Commands" (line 103) | Remove `--county "Los Angeles"` from example — `export_data.py` does not support `--county`. Evidence: `export_data.py --help`.
- Section: "Source Documentation" (line 160) | Change Ballotpedia coverage from "2002-present" to "2006-present". Evidence: `SELECT MIN(year) FROM active_measures WHERE data_source='Ballotpedia'` → 2006.

### PRACTITIONER_READINESS.md
- Section: "Use Case Examples" (lines 21, 130-133, 166-169, 182-188) | Mark numeric outputs as illustrative examples, not verified query results. Evidence: no supporting SQL provided.
- Section: "Fields Most Reliable" (lines 204-213) | Mark reliability percentages as qualitative assessments. Evidence: no supporting verification.
