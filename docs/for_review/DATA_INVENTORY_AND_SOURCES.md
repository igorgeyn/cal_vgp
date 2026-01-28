# Data Inventory and Sources

## Data Summary

| Metric | Value |
|--------|-------|
| **Total Active Measures** | 12,156 |
| **County Coverage** | 59 (all 58 CA counties + statewide) |
| **Year Range (Primary)** | 1998-2026 |
| **Year Range (Historical)** | Raw ICPSR file covers 1902-2016 (not loaded into active DB) |
| **Measures with Vote Data** | 10,908 (89.7%) |
| **Measures with AI Summaries** | 3,457 (28.4%) |
| **Total Votes Recorded** | 520,521,064+ |
| **Average Votes per Measure** | 47,724 |

---

## Primary Data Sources

### 1. Ballotpedia (Web Scraping)

**Coverage:** Statewide propositions + all 58 counties (2002-2026)

**Scrapers:**
- `src/scrapers/ballotpedia_statewide.py` - CA propositions
- `src/scrapers/ballotpedia_counties.py` - All California counties

**Data Collected:**
- Measure titles
- Descriptions
- Vote counts (yes/no)
- Pass/fail status
- Links to detailed pages

**Rate Limiting:** 10s base delay, exponential backoff on 202/empty responses

**Output:** Stored in database (no `ballotpedia_*.json` raw files exist in current repo snapshot)

---

### 2. California Secretary of State (Web Scraping)

**Coverage:** Qualified measures, initiative status (current)

**Scraper:** `src/scrapers/ca_sos.py`

**Endpoints:**
- `/elections/ballot-measures/qualified-ballot-measures`
- `/elections/ballot-measures/initiative-and-referendum-status`

**Data Collected:**
- Official measure titles
- Ballot question text
- Qualification status
- Filing dates

**Note:** Past election results scraper disabled (CA SOS changed URL structure)

**Output:** `data/raw/ca_sos_*.json`

---

### 3. NCSL (National Conference of State Legislatures)

**Coverage:** 2014-present California measures

**File Format:** Excel (.xlsx)
**Filename:** `ncsl_ballot_measures_2014_present.xlsx`

**Parser:** `src/parsers/ncsl.py`

**Data Collected:**
- Measure details
- Vote counts
- Pass/fail status
- Measure type classification

**Storage:** `scraper/data/raw/` or `scraper/data/downloaded/`

---

### 4. ICPSR (Inter-University Consortium for Political and Social Research)

**Coverage:** 1902-2016 (114 years of historical data)

**File Format:** CSV
**Filename:** `ncslballotmeasures_icpsr_1902_2016.csv`

**Parser:** `src/parsers/icpsr.py`

**Data Collected:**
- Historical ballot measures
- Vote counts
- Categorical classifications
- Geographic data

**Encoding Support:** UTF-8, Latin-1, ISO-8859-1, CP1252

**Note:** Most comprehensive historical dataset

---

### 5. CEDA (California Elections Data Archive)

**Coverage:** 1998-2024 California county-level measures

**File Format:** Excel by year
**Filename Pattern:** `ceda_YYYY.xlsx`

**Parser:** `src/parsers/ceda.py`

**Data Collected:**
- County-level ballot measures
- Fiscal measures
- Turnout effects
- Detailed categorization

**Records:** 10,909 measures (1998-2024)

---

### 6. County-Specific Scrapers

High-value county implementations for detailed, current data:

#### Los Angeles County
- **Scraper:** `src/scrapers/la_county.py`
- **Website:** results.lavote.gov
- **Coverage:** 2013-2025
- **Measures:** 698 collected
- **Data:** Full vote counts, all jurisdiction types

#### San Diego County
- **Scraper:** `src/scrapers/san_diego_county.py`
- **Website:** sdvote.com
- **Coverage:** 2022-2024
- **Measures:** 77 collected
- **Format:** Excel Statement of Votes Cast

#### Orange County
- **Scraper:** `src/scrapers/orange_county.py`
- **Website:** ocvote.gov
- **Coverage:** 2012-2025
- **Measures:** 192 collected
- **Format:** Tab-separated media.zip archives

#### San Bernardino County
- **Scraper:** `src/scrapers/san_bernardino_county.py`
- **Website:** results.rov.sbcounty.gov
- **Coverage:** 2020-2024
- **Measures:** 103 collected
- **Format:** Excel ElectionSummaryReportRPT.xlsx

---

## Data Quality & Deduplication

### Fingerprinting System

**Primary Fingerprint:** `{year}|{measure_id}|{county}|{source}`
- Used for exact duplicate detection
- Unique constraint in database

**Measure Fingerprint:** `{year}|{measure_id}|{county}`
- Used for cross-source matching
- Identifies same measure from different sources

**Content Hash:** MD5 of `title + ballot_question + description`
- Used for content-based matching
- Catches renamed/revised measures

### Duplicate Types
- `cross_source` - Same measure found via different data sources (matched by `measure_fingerprint`)
- `content` - Same content hash (MD5 of title+ballot_question+description)

> _Evidence: `scraper/src/database/deduplication.py:34-58` — only `cross_source` and `content` types used._

### Priority Order
When selecting the master record from duplicates (defined in `deduplication.py:150-157`):
1. `CA_SOS` (highest priority)
2. `CA_SOS_Scraper`
3. `NCSL`
4. `CEDA`
5. `ICPSR`
6. `UC_Law_SF`

> _Note: Ballotpedia and county registrar sources are not in the priority list. All other sources default to priority 10._

---

## Output Files

### Database
- **Location:** `scraper/data/ballot_measures.db`
- **Size:** 24.8 MB
- **Records:** 12,156 active measures

### Exports

**CSV Export:**
- **File:** `scraper/data/exports/ballot_measures_YYYYMMDD.csv`
- **Size:** ~4.5 MB
- **Fields:** 26 selected columns (see `scraper/scripts/export_data.py:21-46` for field list)

**JSON Export:**
- **File:** `scraper/data/exports/ballot_measures_YYYYMMDD.json`
- **Size:** ~6.1 MB
- **Format:** Array of measure objects

### Raw Scrape Data
- **Location:** `scraper/data/raw/`
- **Format:** JSON with timestamps
- **Naming:** `{source}_{timestamp}.json`

### County-Specific Data
| File | Size | Measures |
|------|------|----------|
| `la_county_measures.json` | 1.3 MB | 698 |
| `orange_county_measures.json` | 111 KB | 192 |
| `san_bernardino_measures.json` | 64 KB | 103 |
| `san_diego_measures.json` | 118 KB | 77 |

### AI/ML Data
| File | Size | Description |
|------|------|-------------|
| `embeddings.npz` | 15.8 MB | Sentence embeddings |
| `embedding_metadata.json` | 5.2 MB | Embedding mappings |
| `title_cache.json` | 1.6 MB | Generated titles |
| `topic_analysis.json` | 536 KB | Topic distributions |

---

## Coverage by Year

### Measures per Year (Recent)

| Year | Measures |
|------|----------|
| 2024 | 1,118 |
| 2023 | 176 |
| 2022 | 840 |
| 2021 | 156 |
| 2020 | 1,031 |
| 2019 | 70 |
| 2018 | 708 |
| 2017 | 116 |
| 2016 | 873 |

> _Verified via: `SELECT year, COUNT(*) FROM active_measures WHERE year BETWEEN 2016 AND 2024 GROUP BY year ORDER BY year DESC;`_

### Upcoming/Pending

| Year | Measures |
|------|----------|
| 2025 | 126 |
| 2026 | 10 |

---

## Coverage by County

### Top 10 Counties by Measure Count

| Rank | County | Measures |
|------|--------|----------|
| 1 | Los Angeles | 1,427 |
| 2 | Alameda | 678 |
| 3 | Santa Clara | 655 |
| 4 | San Diego | 584 |
| 5 | Orange | 505 |
| 6 | Riverside | 486 |
| 7 | San Mateo | 485 |
| 8 | Contra Costa | 410 |
| 9 | San Bernardino | 396 |
| 10 | Marin | 393 |

> _Verified via: `SELECT county, COUNT(*) as c FROM active_measures WHERE county != 'Statewide' GROUP BY county ORDER BY c DESC LIMIT 10;`_

### Statewide Propositions
- **Count:** 12 measures
- **Coverage:** 1998-2026

> _Verified via: `SELECT COUNT(*) FROM active_measures WHERE county = 'Statewide';` → 12_

---

## Known Data Gaps

### Blocked County Websites
- **Riverside County:** Cloudflare protection (403)
- **Santa Clara County:** Cloudflare protection (403)
- **Recommendation:** Manual browser investigation or use Ballotpedia + CEDA

### Counties Not Yet Scraped
- Sacramento County
- Contra Costa County
- San Francisco County
- Fresno County
- 44 other smaller counties

### Historical Gaps
- Pre-1998 data only from ICPSR (less detailed)
- Some counties missing pre-2000 data
- Vote counts may be missing for older measures

---

## Data Update Frequency

### Automated
- Ballotpedia scraping: On-demand
- CA SOS check: Weekly during election season

### Manual
- County scrapers: As needed
- CEDA imports: Annual (after data release)
- NCSL imports: Annual

### Website Regeneration
- After any data update
- Command: `make website`
