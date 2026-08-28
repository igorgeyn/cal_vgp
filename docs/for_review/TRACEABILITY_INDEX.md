# Traceability Index

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

Maps each major claim in the documentation to its repo evidence.

## PROJECT_OVERVIEW.md
- "12,156 active measures (1998-2026)" → `SELECT COUNT(*), MIN(year), MAX(year) FROM active_measures;` → (12156, 1998, 2026). ✅
- "All 58 counties + statewide" → `SELECT COUNT(DISTINCT county) FROM active_measures;` → 59. ✅
- "Measures with vote data: 10,908" → `SELECT COUNT(*) FROM active_measures WHERE total_votes IS NOT NULL;` → 10,908. ✅
- "AI summaries: 3,457" → `SELECT COUNT(*) FROM active_measures WHERE has_summary = 1;` → 3,457. ✅
- "Raw ICPSR file exists" → `scraper/data/raw/ncslballotmeasures_icpsr_1902_2016.csv`. ✅
- "Live site: cal-vgp.igorgeyn.com" → `CNAME`. ✅
- "BYO LLM chat providers: OpenAI, Anthropic, Ollama" → `generator.py:792-797`. ✅
- "Cloudflare Worker proxy" → `cloudflare-worker/worker.js`. ✅
- "Static single-page app with embedded JSON" → `generator.py:350-365`. ✅
- "8 data scrapers" → `ls scraper/src/scrapers/*.py` → 3 committed + 4 untracked county scrapers. ⚠️ P2
- "approval thresholds" → No `threshold` column in `models.py:229-296`. ⚠️ P2

## FEATURES_AND_UI.md
- "Debounced substring search" → `generator.py:4247-4256`, `generator.py:4387-4400`. ✅
- "Status chips (Passed/Failed/Pending)" → `generator.py:583-596`. ✅
- "Year chips grouped by decade" → `generator.py:568-575`, `generator.py:3709-3755`. ✅
- "Related measures show up to 4" → `generator.py:5015-5018`. ✅
- "External links list" → `scraper/src/utils/external_links.py:290-331`. ✅
- "Chat localStorage" → `generator.py:5239-5252`. ✅
- "Chat provider options (3)" → `generator.py:792-797`. ✅
- "Dynamically generated quiz questions" → `generator.py:145-220`, `generator.py:640-641`, `generator.py:5186-5226`. ✅
- "Example prompts" → `generator.py:760-763`. ✅
- "Chat context field mismatch" → `generator.py:5481-5513`. ✅
- "35.3 MB" → `index.html` = 35,323,534 bytes ≈ 33.7 MiB. ⚠️ P2

## DATA_INVENTORY_AND_SOURCES.md
- "Database location" → `scraper/data/ballot_measures.db`. ✅
- "CSV: 25 columns" → `scraper/scripts/export_data.py:21-46`. ✅
- "JSON: 21 fields" → `scraper/scripts/export_data.py:48-72`. ✅
- "Summary quality export" → `scraper/scripts/export_data.py` `--format summary-quality`. ✅
- "Ballotpedia coverage 2006-2025" → `SELECT MIN(year), MAX(year) FROM active_measures WHERE data_source='Ballotpedia'` → (2006, 2025). ✅
- "UC Law SF: 2 active records" → `SELECT COUNT(*) FROM active_measures WHERE data_source='UC_Law_SF'` → 2. ✅
- "ceda_parsed.csv" → `scraper/data/processed/ceda_parsed.csv`. ✅
- "Ballotpedia vote counts (yes/no)" → `ballotpedia_statewide.py:189-218` (statewide yes); `ballotpedia_counties.py` (no yes/no parsing). ⚠️ P2
- "CEDA file: ceda_YYYY.xlsx" → Repo has `ceda_combined.csv`. ⚠️ P2
- "CEDA records: 10,909" → Active CEDA measures: 10,908. ⚠️ P2
- "Ballotpedia scrapers" → `scraper/src/scrapers/ballotpedia_statewide.py`, `ballotpedia_counties.py`. ✅
- "CA SOS scraper" → `scraper/src/scrapers/ca_sos.py`. ✅
- "NCSL parser" → `scraper/src/parsers/ncsl.py`. ✅
- "ICPSR parser" → `scraper/src/parsers/icpsr.py`. ✅
- "CEDA parser" → `scraper/src/parsers/ceda.py`. ✅
- "Embeddings" → `scraper/scripts/generate_embeddings.py`, `scraper/data/embeddings.npz`. ✅

## SCHEMA_AND_IDS.md
- "48 columns" → `PRAGMA table_info(measures)` → 48 rows. ✅
- "models.py defines 48 columns" → `models.py:229-296` (SCHEMA) + dataclass. ✅
- "related_measures, relationship_type" → DB indices 46-47; `models.py` SCHEMA and dataclass. ✅
- "Fingerprint format" → `models.py:112-119`. ✅
- "Content hash truncated to 16 chars" → `models.py:121-129` (`hexdigest()[:16]`). ✅
- "Source IDs: SD_County_Registrar, OC_County_Registrar" → Scrapers emit these IDs; not yet in DB (county scrapers untracked). ⚠️ P2
- "measure_search FTS table" → `models.py:312-323`. ✅
- "measure_updates table" → `models.py:327-334`. ✅
- "active_measures and measure_stats views" → `models.py:348-368`. ✅
- "Fingerprint example: San_Diego_County_ROV" → Not in DB; actual: `2024|C|SAN DIEGO|Ballotpedia`. ⚠️ P2
- "City/district format: MEASURE_A_OAKLAND" → `models.py:130-160` produces `MEASURE_{letter}` only. ⚠️ P2

## ARCHITECTURE.md
- "BaseScraper pattern" → `base.py:17-69`. ✅
- "SCRAPING_CONFIG['headers']" → Actual: `SCRAPING_CONFIG['user_agent']` at `base.py:29-30`. ⚠️ P2
- "Deduplication" → `deduplication.py:147-157`. ✅
- "Summary generation: placeholder + Ollama" → `summaries.py:85-135`, `generate_ai_summaries.py:1-98`. ✅
- "Title generation: Ollama > Groq > Claude" → `title_generator.py:53-97`. ✅
- "Website generator flow" → `generate_site.py:1-120`, `generator.py:350-365`. ✅
- "Cloudflare Worker" → `cloudflare-worker/worker.js`. ✅
- "Makefile targets" → `scraper/Makefile`. ✅
- "API server: historical endpoints return 501" → `server.py:22-32` (`HISTORICAL_AVAILABLE` flag). ✅
- "VERSION in config.py" → `config.py:12` (`VERSION = "2.0.0"`). ✅
- "CSV: 25 fields (24 DB + 1 computed)" → `export_data.py:21-46`. ✅
- "Path(__file__).resolve().parent.parent" → Actual: `Path(__file__).parent.parent` at `config.py:15`. ⚠️ P2

## RESEARCHER_READINESS.md
- "CSV: 25 columns" → `export_data.py:21-46`. ✅
- "Sample columns list" → Matches actual export header. ✅
- "SQLite DB: 24.8 MB" → `scraper/data/ballot_measures.db`. ✅
- "has_summary flag" → `models.py:269-276`. ✅
- "Measure text ~70%" → UNVERIFIED (needs query on `ballot_question`/`description`). ⚠️
- "Topic category counts" → UNVERIFIED (DB stores 47+ raw categories, not display categories). ⚠️ P2
- "Pass/Fail with threshold logic" → No `threshold` column; limited to scraper-level computation. ⚠️ P2
- "Export --county flag" → `export_data.py --help` shows no `--county` arg. ⚠️ P2
- "Ballotpedia: 2002-present" → DB shows 2006-2025. ⚠️ P2

## PRACTITIONER_READINESS.md
- "Search/filter UI" → `generator.py:4247-4400`, `generator.py:528-596`. ✅
- "Similar measures" → `generator.py:5015-5044`. ✅
- "CSV: 25 fields" → `export_data.py:21-46`. ✅
- "API: historical endpoints return 501" → `server.py:22-32`. ✅
- "67 measures, 42% pass rate" → UNVERIFIED hypothetical. ⚠️ P2
- "78% historically" → UNVERIFIED hypothetical. ⚠️ P2
- "23 housing measures / 14 passed / 3 pending" → UNVERIFIED hypothetical. ⚠️ P2
- "54% (n=23)" → UNVERIFIED hypothetical. ⚠️ P2
- "Reliability percentages (100%, 99%, 95%, 90%)" → UNVERIFIED qualitative assessments. ⚠️ P2
