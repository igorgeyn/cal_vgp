# Schema and IDs

## Database Overview

**Database:** SQLite
**File:** `scraper/data/ballot_measures.db`
**Size:** 24.8 MB

---

## Main Table: `measures`

48 columns organized into logical groups:

> _Verified via: `PRAGMA table_info(measures);` → 48 rows (indices 0-47). Evidence: `scraper/src/database/models.py:229-296`._

### Core Identification

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key, auto-increment |
| `fingerprint` | TEXT | Unique deduplication key: `{year}\|{measure_id}\|{county}\|{source}` |
| `measure_fingerprint` | TEXT | Cross-source matching: `{year}\|{measure_id}\|{county}` |
| `content_hash` | TEXT | MD5 hash of title+ballot_question+description |

### Measure Information

| Column | Type | Description |
|--------|------|-------------|
| `measure_id` | TEXT | Standardized ID (e.g., PROP_8, MEASURE_A) |
| `measure_letter` | TEXT | Local measure letter (A, B, etc.) |
| `year` | INTEGER | Election year |
| `state` | TEXT | Always "CA" |
| `county` | TEXT | County name or "Statewide" |
| `jurisdiction` | TEXT | City/District within county |

### Content Fields

| Column | Type | Description |
|--------|------|-------------|
| `title` | TEXT | Official ballot title |
| `description` | TEXT | Detailed description |
| `ballot_question` | TEXT | Actual ballot language |
| `generated_title` | TEXT | AI-simplified title |
| `original_title` | TEXT | Title before AI generation |

### Vote Results

| Column | Type | Description |
|--------|------|-------------|
| `yes_votes` | INTEGER | Number of yes votes |
| `no_votes` | INTEGER | Number of no votes |
| `total_votes` | INTEGER | Total votes cast |
| `percent_yes` | REAL | Percentage yes (0-100) |
| `percent_no` | REAL | Percentage no (0-100) |
| `passed` | INTEGER | Boolean (1=passed, 0=failed) |
| `pass_fail` | TEXT | String status ("Passed", "Failed", "Pending") |

### Classification

| Column | Type | Description |
|--------|------|-------------|
| `topic_primary` | TEXT | Primary topic category |
| `topic_secondary` | TEXT | Secondary topic |
| `measure_type` | TEXT | Type classification |
| `category_type` | TEXT | Category grouping |
| `category_topic` | TEXT | CEDA/ICPSR category |

### Source & Links

| Column | Type | Description |
|--------|------|-------------|
| `data_source` | TEXT | Origin (CA_SOS, Ballotpedia, NCSL, etc.) |
| `source_url` | TEXT | URL to original data |
| `pdf_url` | TEXT | Link to PDF document |

### AI Summaries

| Column | Type | Description |
|--------|------|-------------|
| `has_summary` | INTEGER | Boolean flag (1=has summary) |
| `summary_title` | TEXT | Short summary title |
| `summary_text` | TEXT | Full 2-3 sentence summary |

### Metadata

| Column | Type | Description |
|--------|------|-------------|
| `election_type` | TEXT | General, Primary, Special, etc. |
| `election_date` | TEXT | Date of election (ISO format) |
| `decade` | TEXT | Derived: 1990s, 2000s, etc. |
| `century` | TEXT | Derived: 19th, 20th, 21st |

### Tracking

| Column | Type | Description |
|--------|------|-------------|
| `created_at` | TEXT | Record creation timestamp |
| `updated_at` | TEXT | Last update timestamp |
| `last_seen_at` | TEXT | Last seen in scrape |
| `update_count` | INTEGER | Number of updates |

### Deduplication

| Column | Type | Description |
|--------|------|-------------|
| `is_active` | INTEGER | Active/inactive flag |
| `is_duplicate` | INTEGER | Duplicate flag |
| `duplicate_type` | TEXT | Type of duplication |
| `master_id` | INTEGER | FK to master record |
| `merged_from` | TEXT | JSON list of merged IDs |

### Related Measures

| Column | Type | Description |
|--------|------|-------------|
| `related_measures` | TEXT | JSON list of related measure IDs (populated by embedding similarity) |
| `relationship_type` | TEXT | Type of relationship (e.g., `embedding_similarity`) |

> _Evidence: `scraper/data/ballot_measures.db` `PRAGMA table_info(measures)` indices 46-47. Added to `models.py` SCHEMA for consistency._

---

## Supporting Tables

### `measure_updates` (Audit Trail)

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key |
| `measure_id` | INTEGER | FK to measures.id |
| `field_name` | TEXT | Changed field name |
| `old_value` | TEXT | Previous value |
| `new_value` | TEXT | New value |
| `updated_at` | TEXT | Timestamp |
| `update_source` | TEXT | Update source |

> _Evidence: `scraper/src/database/models.py:327-334` — column is `update_source`, not `source`._

### `measure_search` (Full-Text Search)

Virtual FTS5 table for fast text search:

| Column | Type | Description |
|--------|------|-------------|
| `fingerprint` | TEXT | Searchable fingerprint |
| `title` | TEXT | Searchable title |
| `description` | TEXT | Searchable description |
| `ballot_question` | TEXT | Searchable ballot question |
| `county` | TEXT | Searchable county |
| `summary_title` | TEXT | Searchable summary title |
| `summary_text` | TEXT | Searchable summary text |

> _Evidence: `scraper/src/database/models.py:312-323` — `county` is included in FTS table._

### `scraper_runs` (Execution Log)

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key |
| `run_type` | TEXT | Scraper type |
| `started_at` | TEXT | Start timestamp |
| `completed_at` | TEXT | End timestamp |
| `measures_checked` | INTEGER | Count checked |
| `new_measures` | INTEGER | New records |
| `updated_measures` | INTEGER | Updated records |
| `duplicates_found` | INTEGER | Duplicates detected |
| `status` | TEXT | Success/Failed |
| `error_message` | TEXT | Error details |

---

## Indexes

| Index Name | Column(s) | Purpose |
|------------|-----------|---------|
| `idx_fingerprint` | fingerprint | Deduplication key lookup |
| `idx_measure_fingerprint` | measure_fingerprint | Cross-source matching |
| `idx_year` | year | Year filtering |
| `idx_county` | county | Geographic filtering |
| `idx_passed` | passed | Result filtering |
| `idx_topic` | topic_primary | Topic filtering |
| `idx_source` | data_source | Source filtering |
| `idx_has_summary` | has_summary | Summary availability |
| `idx_content_hash` | content_hash | Content matching |
| `idx_is_duplicate` | is_duplicate | Duplicate filtering |

---

## Views

### `active_measures`

Returns only active, non-duplicate measures:

```sql
CREATE VIEW active_measures AS
SELECT * FROM measures
WHERE is_active = 1 AND is_duplicate = 0;
```

### `measure_stats`

Year-by-year aggregated statistics:

```sql
CREATE VIEW measure_stats AS
SELECT
    year,
    COUNT(*) as total_measures,
    SUM(CASE WHEN passed = 1 THEN 1 ELSE 0 END) as passed_count,
    ROUND(AVG(percent_yes), 2) as avg_percent_yes
FROM active_measures
GROUP BY year
ORDER BY year DESC;
```

---

## ID Formats

### Fingerprint Format
```
{year}|{measure_id}|{county}|{source}

Examples:
2024|PROP_36|Statewide|CA_SOS
2024|MEASURE_A|Los Angeles|LA_County_Registrar
2022|MEASURE_J|San Diego|San_Diego_County_ROV
```

### Measure ID Standardization

**State Propositions:**
```
PROP_{number}
Examples: PROP_8, PROP_36, PROP_99
```

**County Measures:**
```
MEASURE_{letter}
Examples: MEASURE_A, MEASURE_BB, MEASURE_Z
```

**City/District Measures:**
```
MEASURE_{letter}_{jurisdiction_code}
Examples: MEASURE_A_OAKLAND, MEASURE_B_LASD
```

### Content Hash
MD5 hash of concatenated fields:
```python
content = f"{title or ''}|{ballot_question or ''}|{description or ''}"
content_str = content.lower().strip()
content_hash = hashlib.md5(content_str.encode()).hexdigest()[:16]
```

---

## Data Source Identifiers

| Source ID | Description | Coverage |
|-----------|-------------|----------|
| `CA_SOS` | CA Secretary of State | Current measures |
| `Ballotpedia` | Ballotpedia website | 2006-2025 |
| `NCSL` | National Conference of State Legislatures | 2014-present |
| `ICPSR` | Historical archive | 1902-2016 |
| `CEDA` | CA Elections Data Archive | 1998-2024 |
| `LA_County_Registrar` | LA County ROV | 2013-2025 |
| `SD_County_Registrar` | SD County ROV | 2022-2024 |
| `OC_County_Registrar` | OC County ROV | 2012-2025 |
| `San_Bernardino_County_ROV` | SB County ROV | 2020-2024 |
| `UC_Law_SF` | UC Law SF Repository | Statewide propositions |

---

## Topic Categories

### 12 Display Categories

| Category | Description |
|----------|-------------|
| Education | Schools, colleges, bonds |
| Public Safety & Crime | Police, fire, criminal justice |
| Taxes & Finance | Tax measures, revenue |
| Government & Elections | Elections, recalls, government |
| Healthcare & Welfare | Healthcare, welfare programs |
| Environment & Natural Resources | Environment, water, parks |
| Transportation | Transit, infrastructure |
| Housing & Land Use | Land use, zoning, housing |
| Business & Labor | Labor, business regulations |
| Utilities & Energy | Utilities, energy policy |
| Civil Rights | Rights, discrimination |
| Other | Miscellaneous |

### 47+ Raw Topic Categories
Detailed categorization from source data, mapped to 12 display categories.

---

## Jurisdiction Types

| Type | Description | Example |
|------|-------------|---------|
| State | Statewide proposition | California |
| County | County-wide measure | Los Angeles County |
| City | City measure | City of Oakland |
| School District | School district measure | LAUSD |
| Special District | Water, fire, etc. | Metro Water District |
| Healthcare District | Hospital districts | Desert Healthcare |
| Library District | Library measures | LA County Library |
| Recreation District | Park/rec measures | East Bay Regional Park |
| Water District | Water agency measures | MWD |

---

## Election Types

| Type | Description |
|------|-------------|
| General | November general election |
| Primary | June primary election |
| Special | Special election |
| Runoff | Runoff election |
| Recall | Recall election |
| Local | Local-only election |

---

## Example Queries

### Get all active measures for a county
```sql
SELECT * FROM active_measures
WHERE county = 'Los Angeles'
ORDER BY year DESC;
```

### Get pass rate by topic
```sql
SELECT
    topic_primary,
    COUNT(*) as total,
    ROUND(100.0 * SUM(passed) / COUNT(*), 1) as pass_rate
FROM active_measures
WHERE passed IS NOT NULL
GROUP BY topic_primary
ORDER BY pass_rate DESC;
```

### Find duplicates across sources
```sql
SELECT measure_fingerprint, COUNT(*) as sources
FROM measures
WHERE is_active = 1
GROUP BY measure_fingerprint
HAVING COUNT(*) > 1;
```

### Search measures
```sql
SELECT m.* FROM measures m
JOIN measure_search ms ON m.fingerprint = ms.fingerprint
WHERE measure_search MATCH 'school bond'
ORDER BY m.year DESC;
```
