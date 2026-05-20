# CalBallot: Complete Data Pipeline Documentation

> Comprehensive documentation of the California Ballot Measures database system — from data ingestion to website display.

**Original snapshot:** February 2026
**Most recently amended:** 2026-05-20 (header updated for v3 + Phase 5 closeout; Section 9 body remains v1-design snapshot — see finance/README.md for the current design)
**Database:** 11,483 active measures (1998–present)
**Coverage:** 58 California counties + statewide propositions
**Quality Score:** 86.7% (A-) — see [KNOWN_ISSUES.md](KNOWN_ISSUES.md)

> **Finance section is a snapshot — substantially expanded since this
> doc was written.** Section 9 below describes the original
> `finance_statewide.db` design (v1; contaminated). The finance pipeline
> has had two major rebuilds since:
>
> - **v2 (2026-05-04, `finance_statewide_v2.db`):** keyed by year-scoped
>   `finance_campaign_id` (e.g. `PROP_16_2020`), fixing the cross-cycle
>   contamination bug. v2 scope is itemized monetary contributions only.
> - **v3 (Phase 4–5, 2026-05-15 → 2026-05-20, `finance_statewide_v3.db`):**
>   expanded scope. v3 carries loans (`LOAN_CD`), in-kind contributions
>   (`RCPT_CD` Schedule C), and independent expenditures (`EXPN_CD` +
>   `S496_CD`). Phase 5 stitched v2 monetary + v3 non-monetary into a
>   single read layer (`FinanceDatabase.get_combined_*`).
>
> Current production state: **181 matched measures / $5.75B reportable
> money** across 194 campaigns (v2 monetary $3.24B + v3 loans+in-kind+IE
> $2.51B; some measures collide via year-offset recoveries, hence the
> measure/campaign split). See
> [`scraper/data/finance/README.md`](../scraper/data/finance/README.md)
> for the live design + methodology and `plans/finance-rebuild-verification.md`
> for the verification framework (Layers 1–3 + Phase G).

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Data Sources](#2-data-sources)
3. [Scraper Architecture](#3-scraper-architecture)
4. [Historical Data Parsers](#4-historical-data-parsers)
5. [Data Models & Schema](#5-data-models--schema)
6. [Database Operations](#6-database-operations)
7. [Deduplication System](#7-deduplication-system)
8. [Data Enrichment](#8-data-enrichment)
9. [Finance Data Pipeline](#9-finance-data-pipeline)
10. [Website Generation](#10-website-generation)
11. [Topic Classification](#11-topic-classification)
12. [Configuration](#12-configuration)
13. [Scripts & Workflows](#13-scripts--workflows)
14. [Data Flow Diagram](#14-data-flow-diagram)
15. [Error Handling & Robustness](#15-error-handling--robustness)
16. [Data Quality Evaluation](#16-data-quality-evaluation)
17. [Known Issues & Limitations](#17-known-issues--limitations)

---

## 1. System Overview

CalBallot is a comprehensive California ballot measures database that:

- **Aggregates** data from 6+ authoritative sources
- **Deduplicates** measures across sources using multi-level matching
- **Enriches** with AI-generated summaries (Claude Sonnet) and semantic embeddings
- **Integrates** campaign finance data from CalAccess
- **Presents** via a searchable, filterable static website with recommendations

### Directory Structure

```
cal_vgp/
├── index.html                      # Generated website
├── scraper/
│   ├── data/
│   │   ├── ballot_measures.db      # Main SQLite database (29 MB)
│   │   ├── finance/                # Finance databases (combined v2 + v3)
│   │   │   ├── finance_statewide_v2.db   # v2: monetary contributions ($3.24B)
│   │   │   ├── finance_statewide_v3.db   # v3: loans + in-kind + IE ($2.51B)
│   │   │   └── finance_statewide.db      # Legacy v1, audit-only
│   │   ├── embeddings.npz          # Semantic vectors (15.8 MB)
│   │   ├── embedding_metadata.json # Measure IDs & recommendations
│   │   ├── title_cache.json        # Generated titles cache
│   │   └── raw/                    # Raw scraped data (JSON)
│   ├── src/
│   │   ├── scrapers/               # Web scrapers
│   │   ├── parsers/                # Historical data parsers
│   │   ├── database/               # Models & operations
│   │   ├── enrichment/             # Summary generation
│   │   ├── finance/                # Finance data operations
│   │   ├── website/                # Static site generator
│   │   ├── utils/                  # Helpers (topics, regions, etc.)
│   │   ├── api/                    # FastAPI server (optional)
│   │   └── config.py               # Central configuration
│   └── scripts/                    # Standalone utilities
└── docs/
    └── DATA_PIPELINE.md            # This document
```

---

## 2. Data Sources

### 2.1 Primary Sources

| Source | Coverage | Data Type | Update Frequency |
|--------|----------|-----------|------------------|
| **California Secretary of State** | Current cycle | Qualified measures, initiatives | Weekly during election season |
| **Ballotpedia (Statewide)** | 2020–present | Propositions, vote results | After each election |
| **Ballotpedia (County)** | 2020–present | County/local measures | After each election |
| **UC Law SF Repository** | 1900s–recent | Historical propositions, PDFs | Static archive |

### 2.2 Historical Archives

| Source | Coverage | Records | Notes |
|--------|----------|---------|-------|
| **CEDA** (CA Elections Data Archive) | 1995–2024 | ~8,000 | Excel files by year, most complete for county-level |
| **ICPSR** | 1902–2016 | ~2,500 | Academic dataset, statewide focus |
| **NCSL** | Various | ~500 | National conference data |

### 2.3 Finance Data

| Source | Coverage | Data Type |
|--------|----------|-----------|
| **CalAccess** | 2016–present | Campaign contributions, committees, expenditures |

### 2.4 Source Priority (for deduplication)

When the same measure appears in multiple sources:

1. **CA Secretary of State** (most authoritative for current measures)
2. **CEDA** (most complete vote data)
3. **Ballotpedia** (good descriptions, recent coverage)
4. **UC Law SF** (historical PDFs)
5. **ICPSR/NCSL** (academic archives)

---

## 3. Scraper Architecture

### 3.1 Base Scraper Class

**Location:** `scraper/src/scrapers/base.py`

All scrapers inherit from `BaseScraper`, which provides:

```python
class BaseScraper:
    """Abstract base class for all scrapers."""

    # Features:
    # - HTTP session management with User-Agent headers
    # - Rate limiting (configurable delay between requests)
    # - Exponential backoff retry (max 3 retries, 2^n seconds)
    # - Raw data persistence to JSON files
    # - Measure ID extraction with regex patterns
    # - Standardization to BallotMeasure format
```

**Configuration:**

```python
SCRAPING_CONFIG = {
    "rate_limit": 1.0,       # seconds between requests
    "timeout": 30,           # seconds per request
    "max_retries": 3,
    "user_agent": "Mozilla/5.0 (compatible; CalBallotBot/1.0)"
}
```

### 3.2 California Secretary of State Scraper

**Location:** `scraper/src/scrapers/ca_sos.py`
**Class:** `CASOSScraper`
**Source:** https://www.sos.ca.gov

**Endpoints Scraped:**

| Endpoint | Content |
|----------|---------|
| `/elections/ballot-measures/qualified-ballot-measures` | Currently qualified measures |
| `/elections/ballot-measures/initiative-and-referendum-status` | In-progress initiatives |
| `/elections/ballot-measures/text-of-proposed-laws` | Full measure text |

**Key Methods:**

```python
def scrape(self) -> List[BallotMeasure]:
    """Main entry point."""

def _scrape_endpoint(self, url: str) -> List[dict]:
    """Scrape a specific SOS page."""

def _parse_measure(self, element) -> dict:
    """Extract individual measure with regex patterns."""

def _scrape_initiative_status(self) -> List[dict]:
    """Parse status table for in-progress initiatives."""
```

**Measure ID Patterns:**

```python
# ACA/SCA format (Constitutional Amendments)
r'([AS]CA\s+\d+)'  # Matches: "ACA 1", "SCA 13"

# Proposition format
r'Prop(?:osition)?\s*(\d+[A-Z]?)'  # Matches: "Prop 47", "Proposition 13A"

# Bill format
r'(Assembly|Senate)\s+Bill\s*(\d+)'  # Matches: "Assembly Bill 123"
```

**Data Extracted:**

- Measure ID (normalized)
- Title (with Chapter/Statute info stripped)
- Year (extracted from election date)
- PDF URLs (full URLs via `urljoin`)
- Election date and type
- Support/Opposition status

### 3.3 UC Law SF Repository Scraper

**Location:** `scraper/src/scrapers/ca_sos.py`
**Class:** `UCLawSFScraper`
**Source:** https://repository.uclawsf.edu/ca_ballot_props/

**Features:**

- Pagination handling (up to 20 pages, 200 items)
- Year extraction from detail pages
- Deduplication by PDF URL and source URL

**Key Methods:**

```python
def scrape(self) -> List[BallotMeasure]:
    """Paginate through repository."""

def _parse_repository_page(self, soup) -> Tuple[List[dict], Optional[str]]:
    """Extract listings and next page URL."""

def _extract_year_from_detail_page(self, url: str) -> Optional[int]:
    """Follow links to extract year from detail page."""
```

### 3.4 Ballotpedia Statewide Scraper

**Location:** `scraper/src/scrapers/ballotpedia_statewide.py`
**Class:** `BallotpediaStatewideScraper`
**Source:** `https://ballotpedia.org/California_{YEAR}_ballot_propositions`

**Coverage:** 2020–2026 (configurable)

**Section Extraction:**

| Section Name | Content |
|--------------|---------|
| `Ballot title` | Official title |
| `Text of measure` | Full ballot text |
| `Petition summary` | AG summary |
| `Election results` | Vote counts and percentages |

**Data Extracted:**

- Proposition number
- Ballot question and measure text
- Election results with parsing:
  - Yes/No vote counts
  - Percentages
  - Pass/Fail determination

### 3.5 Ballotpedia County Scraper

**Location:** `scraper/src/scrapers/ballotpedia_counties.py`
**Class:** `BallotpediaCountyScraper`
**Source:** `https://ballotpedia.org/{County}_County,_California_ballot_measures`

**Coverage:** All 58 California counties

**Special Handling:**

- URL encoding (spaces → underscores)
- Year-based section extraction
- County name standardization

---

## 4. Historical Data Parsers

### 4.1 CEDA Parser (California Elections Data Archive)

**Location:** `scraper/src/parsers/ceda.py`
**Class:** `CEDAParser`
**Coverage:** 1995–2024

**Input Formats:**

- Excel files (`.xls`, `.xlsx`)
- CSV files

**Sheet Name Patterns:**

```python
# All recognized patterns:
"Measures 2024"
"Measures_2020"
"Measures2000"
"measures2015"
```

**Column Mapping (handles variations):**

```python
COLUMN_MAPPING = {
    # Measure identification
    'measure_id': ['MeasID', 'MeasID_First', 'Multi_MeasID'],

    # Election info
    'year': ['DATE', 'YEAR'],
    'election_type': ['ELECNAME'],

    # Vote data (note: handles spacing variations)
    'yes_votes': [' YES ', 'YES', ' YES_sum '],
    'no_votes': [' NO ', 'NO', ' NO_sum '],

    # Results
    'pass_fail': ['PASSFAIL', 'PERCENT', 'outcome'],

    # Classification
    'category_type': ['RECTYPE'],
    'topic': ['RECTOPIC'],

    # Geography
    'county': ['CNTYNAME', 'PLACE', 'JUR'],
}
```

**Vote Threshold Derivation:**

```python
# From CEDA pass_fail codes:
'Pass'/'Fail'   → vote_threshold = '50%'    (simple majority)
'PassF'/'FailF' → vote_threshold = '55%'    (Prop 39 school bonds)
'PassT'/'FailT' → vote_threshold = '66.67%' (2/3 supermajority)
```

### 4.2 ICPSR Parser

**Location:** `scraper/src/parsers/icpsr.py`
**Class:** `ICPSRParser`
**Coverage:** 1902–2016
**File:** `ncslballotmeasures_icpsr_1902_2016.csv`

**Features:**

- Multiple encoding support (UTF-8, Latin-1, ISO-8859-1, CP1252)
- State filtering (California only)
- Year extraction from various column formats

**Search Paths:**

```python
['raw/', 'downloaded/', '../downloaded/']
```

### 4.3 NCSL Parser

**Location:** `scraper/src/parsers/ncsl.py`
**Class:** `NCSLParser`
**Coverage:** National Conference of State Legislatures data

---

## 5. Data Models & Schema

### 5.1 Core Data Model

**Location:** `scraper/src/database/models.py`
**Class:** `BallotMeasure` (Python dataclass)

```python
@dataclass
class BallotMeasure:
    # === Identity ===
    id: Optional[int] = None
    fingerprint: Optional[str] = None      # UNIQUE: year|measure_id|county|source
    measure_fingerprint: Optional[str] = None  # Cross-source: year|measure_id|county
    content_hash: Optional[str] = None     # MD5 of title+question+description

    # === Core Information ===
    measure_id: Optional[str] = None       # "PROP 47", "A", "SCA 1"
    measure_letter: Optional[str] = None   # Single letter for county measures
    year: Optional[int] = None
    state: str = "California"
    county: Optional[str] = None           # "Los Angeles", "Statewide"
    jurisdiction: Optional[str] = None     # City/district name

    # === Content ===
    title: Optional[str] = None            # Official ballot title
    description: Optional[str] = None      # Longer description
    ballot_question: Optional[str] = None  # "Shall..." question

    # === AI-Generated Content ===
    generated_title: Optional[str] = None  # Short AI title
    original_title: Optional[str] = None   # Preserved original
    summary_text: Optional[str] = None     # AI-generated summary (Claude)

    # === Vote Results ===
    yes_votes: Optional[int] = None
    no_votes: Optional[int] = None
    total_votes: Optional[int] = None
    percent_yes: Optional[float] = None
    percent_no: Optional[float] = None
    passed: Optional[int] = None           # 1=passed, 0=failed, NULL=pending
    pass_fail: Optional[str] = None        # "Pass", "Fail", "PassF", etc.
    vote_threshold: Optional[str] = None   # "50%", "55%", "66.67%"

    # === Classification ===
    measure_type: Optional[str] = None     # "proposition", "bond", "initiative"
    topic_primary: Optional[str] = None    # Raw topic from source
    topic_secondary: Optional[str] = None
    category_type: Optional[str] = None    # CEDA category
    category_topic: Optional[str] = None

    # === Source Tracking ===
    data_source: Optional[str] = None      # "CA_SOS", "CEDA", "Ballotpedia"
    source_url: Optional[str] = None
    pdf_url: Optional[str] = None

    # === Deduplication ===
    is_active: int = 1                     # 0 = duplicate/inactive
    is_duplicate: int = 0
    duplicate_type: Optional[str] = None   # "exact", "content", "cross_source"
    master_id: Optional[int] = None        # FK to canonical record
    merged_from: Optional[str] = None      # JSON list of merged IDs

    # === Timestamps ===
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    last_seen_at: Optional[str] = None
```

### 5.2 Database Schema

**Database:** SQLite (`scraper/data/ballot_measures.db`)

#### Tables

```sql
-- Main measures table
CREATE TABLE measures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fingerprint TEXT UNIQUE,
    measure_fingerprint TEXT,
    content_hash TEXT,
    -- ... all BallotMeasure fields ...
    FOREIGN KEY (master_id) REFERENCES measures(id)
);

-- Audit trail
CREATE TABLE measure_updates (
    id INTEGER PRIMARY KEY,
    measure_id INTEGER,
    field_name TEXT,
    old_value TEXT,
    new_value TEXT,
    updated_at TEXT,
    FOREIGN KEY (measure_id) REFERENCES measures(id)
);

-- Scraper execution logs
CREATE TABLE scraper_runs (
    id INTEGER PRIMARY KEY,
    scraper_name TEXT,
    started_at TEXT,
    completed_at TEXT,
    measures_found INTEGER,
    measures_added INTEGER,
    measures_updated INTEGER,
    status TEXT,
    error_message TEXT
);
```

#### Indexes

```sql
CREATE UNIQUE INDEX idx_fingerprint ON measures(fingerprint);
CREATE INDEX idx_measure_fingerprint ON measures(measure_fingerprint);
CREATE INDEX idx_year ON measures(year);
CREATE INDEX idx_county ON measures(county);
CREATE INDEX idx_passed ON measures(passed);
CREATE INDEX idx_topic ON measures(topic_primary);
CREATE INDEX idx_source ON measures(data_source);
CREATE INDEX idx_has_summary ON measures(summary_text);
CREATE INDEX idx_content_hash ON measures(content_hash);
CREATE INDEX idx_is_duplicate ON measures(is_duplicate);
```

#### Full-Text Search

```sql
-- FTS5 virtual table for fast text search
CREATE VIRTUAL TABLE measure_search USING fts5(
    title,
    description,
    ballot_question,
    summary_text,
    content='measures',
    content_rowid='id'
);
```

#### Views

```sql
-- Active (non-duplicate) measures only
CREATE VIEW active_measures AS
SELECT * FROM measures
WHERE is_active = 1 AND is_duplicate = 0;

-- Year-by-year statistics
CREATE VIEW measure_stats AS
SELECT
    year,
    COUNT(*) as total,
    SUM(CASE WHEN passed = 1 THEN 1 ELSE 0 END) as passed,
    SUM(CASE WHEN passed = 0 THEN 1 ELSE 0 END) as failed
FROM measures
WHERE is_active = 1
GROUP BY year;
```

---

## 6. Database Operations

**Location:** `scraper/src/database/operations.py`
**Class:** `Database`

### 6.1 Core Methods

```python
class Database:
    def __init__(self, db_path: str = None):
        """Initialize connection, ensure schema exists."""

    def insert_measure(self, measure: BallotMeasure) -> int:
        """Insert new measure, return ID."""

    def update_measure(self, measure_id: int, **fields) -> bool:
        """Update specific fields, log changes."""

    def get_measure(self, measure_id: int) -> Optional[BallotMeasure]:
        """Fetch single measure by ID."""

    def find_by_fingerprint(self, fingerprint: str) -> Optional[BallotMeasure]:
        """Exact match lookup."""

    def find_by_content_hash(self, content_hash: str) -> List[BallotMeasure]:
        """Find content-based duplicates."""

    def search_measures(self, query: str, **filters) -> List[BallotMeasure]:
        """Full-text search with optional filters."""

    def get_all_active_measures(self) -> List[BallotMeasure]:
        """Retrieve all non-duplicate active measures."""
```

### 6.2 Statistics Methods

```python
    def get_statistics(self) -> dict:
        """Aggregate stats: counts, year ranges, sources."""

    def get_years_with_counts(self) -> List[Tuple[int, int]]:
        """Year distribution."""

    def get_topics_with_counts(self) -> List[Tuple[str, int]]:
        """Topic frequency."""

    def get_counties_with_counts(self) -> List[Tuple[str, int]]:
        """Geographic distribution."""
```

### 6.3 Maintenance Methods

```python
    def log_scraper_run(self, scraper_name: str) -> int:
        """Start scraper log entry."""

    def update_scraper_run(self, run_id: int, **results):
        """Update with results."""

    def backup(self, suffix: str = None) -> str:
        """Create timestamped backup."""

    def _check_schema(self):
        """Auto-add missing columns."""

    def _fix_year_types(self):
        """Ensure year stored as INTEGER."""
```

---

## 7. Deduplication System

**Location:** `scraper/src/database/deduplication.py`
**Class:** `Deduplicator`

### 7.1 Deduplication Strategy

Three levels of duplicate detection, applied in order:

#### Level 1: Exact Fingerprint Match

```python
fingerprint = f"{year}|{measure_id}|{county}|{data_source}"
# Example: "2024|PROP 36|Statewide|CA_SOS"
```

Catches: Same measure scraped multiple times from same source.

#### Level 2: Content Hash Match

```python
import hashlib
content = f"{title}|{ballot_question}|{description}"
content_hash = hashlib.md5(content.encode()).hexdigest()
```

Catches: Reformatted duplicates with identical content.

#### Level 3: Cross-Source Matching

```python
measure_fingerprint = f"{year}|{measure_id}|{county}"
# Example: "2024|PROP 36|Statewide"
```

Catches: Same measure from different sources (CA_SOS vs Ballotpedia).

### 7.2 Master Record Selection

When duplicates are found, a scoring system selects the "master" record:

```python
def _score_measure(self, measure: BallotMeasure) -> int:
    score = 0

    # Content completeness
    if measure.summary_text:    score += 100
    if measure.percent_yes:     score += 50
    if measure.description:     score += 25
    if measure.pdf_url:         score += 20
    if measure.ballot_question: score += 15

    # Source authority
    SOURCE_PRIORITY = {
        'CA_SOS': 10,
        'CEDA': 5,
        'Ballotpedia': 3,
        'UC_Law_SF': 0
    }
    score += SOURCE_PRIORITY.get(measure.data_source, 0)

    # Recency bonus (up to 30 points for recent updates)
    if measure.updated_at:
        days_old = (now - parse(measure.updated_at)).days
        score += max(0, 30 - days_old)

    return score
```

### 7.3 Merge Strategy

When merging duplicates into a master record:

```python
def _merge_measures(self, master: BallotMeasure,
                    duplicates: List[BallotMeasure]) -> BallotMeasure:
    """
    Merge strategy:
    1. Keep master's data when available
    2. Fill gaps from other versions
    3. Merge vote data with consistency checks
    4. Recalculate derived fields
    5. Store merge history
    """
    merged = copy(master)

    for dup in duplicates:
        # Fill gaps
        for field in ['description', 'ballot_question', 'pdf_url']:
            if not getattr(merged, field) and getattr(dup, field):
                setattr(merged, field, getattr(dup, field))

        # Vote data (prefer non-null, validate consistency)
        if dup.yes_votes and not merged.yes_votes:
            merged.yes_votes = dup.yes_votes
            merged.no_votes = dup.no_votes
            merged.total_votes = dup.total_votes

    # Recalculate percentages
    if merged.yes_votes and merged.total_votes:
        merged.percent_yes = (merged.yes_votes / merged.total_votes) * 100
        merged.percent_no = (merged.no_votes / merged.total_votes) * 100

    # Track merge history
    merged.merged_from = json.dumps([d.id for d in duplicates])

    return merged
```

### 7.4 Deduplication Methods

```python
class Deduplicator:
    def check_duplicate(self, measure: BallotMeasure) -> Optional[int]:
        """Check if measure is duplicate, return master_id if so."""

    def find_cross_source_duplicates(self) -> List[List[BallotMeasure]]:
        """Find all cross-source duplicate groups."""

    def deduplicate_cross_source(self) -> int:
        """Process all groups, return count merged."""

    def mark_duplicate(self, measure_id: int, master_id: int,
                       duplicate_type: str):
        """Mark measure as duplicate of master."""

    def unmark_duplicate(self, measure_id: int):
        """Restore measure to active status."""

    def get_duplicate_report(self) -> dict:
        """Statistics on duplicates by type."""
```

---

## 8. Data Enrichment

### 8.1 Summary Generation

**Location:** `scraper/scripts/generate_summaries.py`

#### Process

1. **Query measures needing summaries:**

```python
SELECT id, title, county, year, topic_primary, category_type,
       vote_threshold, percent_yes, passed
FROM measures
WHERE is_active = 1
  AND (summary_text IS NULL OR summary_text = '')
  AND LENGTH(title) > 50
ORDER BY LENGTH(title) DESC, year DESC
```

2. **Build context-aware prompt:**

```python
def build_prompt(measure):
    context_parts = []
    if county:
        context_parts.append(f"Location: {county}, California")
    if year:
        context_parts.append(f"Year: {year}")
    if category_type and topic:
        context_parts.append(f"Type: {category_type} ({topic})")
    if passed is not None and percent_yes:
        outcome = "Passed" if passed == 1 else "Failed"
        threshold_str = f" (required {threshold})" if threshold else ""
        context_parts.append(f"Outcome: {outcome} with {percent_yes:.1f}% yes{threshold_str}")

    return f"""Summarize this California ballot measure in 1-2 neutral sentences.
Focus on what it would do (or did), not persuasive language from the ballot text.
Output only the summary - no preamble, labels, or explanations.

Context:
{chr(10).join(context_parts)}

Ballot Text:
{title}"""
```

3. **Call Claude API:**

```python
MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 150

client = anthropic.Anthropic(api_key=api_key)
response = client.messages.create(
    model=MODEL,
    max_tokens=MAX_TOKENS,
    messages=[{"role": "user", "content": prompt}]
)
summary = response.content[0].text.strip()
```

4. **Batch commit with checkpointing:**

```python
BATCH_SIZE = 50
RATE_LIMIT_DELAY = 0.1  # seconds

# Save checkpoint every batch
save_checkpoint(list(processed_ids), stats)

# Resume capability
if args.resume:
    checkpoint = load_checkpoint()
    processed_ids = set(checkpoint.get("processed_ids", []))
```

#### API Key Storage

```bash
# Store in macOS Keychain
security add-generic-password -a "$USER" -s anthropic_api_key -w <your-key>

# Retrieved by script
security find-generic-password -a "$USER" -s anthropic_api_key -w
```

### 8.2 Summary Quality Inspection

**Location:** `scraper/scripts/inspect_summaries.py`

**Quality Checks:**

```python
QUALITY_ISSUES = {
    'too_short': lambda s: len(s) < 50,
    'too_long': lambda s: len(s) > 500,
    'has_preamble': lambda s: any(re.match(p, s.lower()) for p in [
        r'^here is', r'^this is a', r'^summary:', r'^the summary',
        r'^in summary', r'^to summarize'
    ]),
    'ends_badly': lambda s: s.rstrip()[-1] not in '.?!"\')',
    'has_bullet_points': lambda s: '•' in s or '\n-' in s or '\n*' in s,
    'mentions_vote': lambda s: 'vote yes' in s.lower() or 'vote no' in s.lower(),
    'too_many_sentences': lambda s: s.count('. ') > 4,
}
```

**Report Sections:**

1. Coverage statistics
2. Length distribution (characters and words)
3. Quality issues detected
4. Examples of flagged summaries
5. Sample summaries by category
6. Random samples for manual review
7. Measures still without summaries

### 8.3 Embeddings & Recommendations

**Files:**
- `scraper/data/embeddings.npz` — Numerical vectors (15.8 MB)
- `scraper/data/embedding_metadata.json` — Measure IDs and recommendations (3.4 MB)

**Recommendation Format:**

```json
{
  "12345": {
    "recommendations": [
      {"id": 12346, "score": 0.92},
      {"id": 12347, "score": 0.87},
      {"id": 12348, "score": 0.85}
    ]
  }
}
```

### 8.4 Title Generation

**Location:** `scraper/src/utils/title_generator.py`

**Purpose:** Generate concise, readable titles for measures with verbose official titles.

**Cache:** `scraper/data/title_cache.json` (1.6 MB)

**Providers:**
- Ollama (local, free) — preferred
- Claude API (cloud, paid) — fallback

---

## 9. Finance Data Pipeline

### 9.1 Source: CalAccess

California's official campaign finance database, processed into a local SQLite database.

**Database:** `scraper/data/finance/finance_statewide_v2.db` (live; the
unsuffixed `finance_statewide.db` is the legacy v1, kept for audit only).
The schema and column descriptions in this section describe the v1 design.

### 9.2 Finance Schema

```sql
-- Campaign committees
CREATE TABLE committee (
    committee_id TEXT PRIMARY KEY,
    name TEXT,
    filer_type TEXT,
    stance TEXT  -- 'support' or 'oppose'
);

-- Individual transactions (contributions, loans)
CREATE TABLE transaction_record (
    txn_id TEXT PRIMARY KEY,
    committee_id TEXT,
    date TEXT,
    amount REAL,
    donor_name TEXT,
    donor_name_canon TEXT,  -- Standardized name
    donor_type TEXT,        -- 'individual', 'organization', etc.
    donor_sector TEXT,      -- Industry classification
    FOREIGN KEY (committee_id) REFERENCES committee(committee_id)
);

-- Measure-committee relationships
CREATE TABLE measure_committee_link (
    measure_id TEXT,
    committee_id TEXT,
    stance TEXT,  -- 'support' or 'oppose'
    PRIMARY KEY (measure_id, committee_id)
);

-- Pre-aggregated summaries
CREATE TABLE measure_finance_summary (
    measure_id TEXT,
    stance TEXT,
    total_receipts REAL,
    n_committees INTEGER,
    top5_share REAL,  -- Concentration: % from top 5 donors
    hhi REAL,         -- Herfindahl-Hirschman Index
    PRIMARY KEY (measure_id, stance)
);

-- Weekly timeline for charts
CREATE TABLE measure_finance_timeline_weekly (
    measure_id TEXT,
    stance TEXT,
    week_start TEXT,
    weekly_receipts REAL,
    cumulative_receipts REAL
);

-- Top donors per measure
CREATE TABLE measure_top_donors (
    measure_id TEXT,
    stance TEXT,
    donor_name_canon TEXT,
    donor_type TEXT,
    donor_sector TEXT,
    total_amount REAL
);
```

### 9.3 Finance Operations

**Location:** `scraper/src/finance/operations.py`
**Class:** `FinanceDatabase`

```python
class FinanceDatabase:
    def get_finance_summary(self, measure_id: str) -> List[dict]:
        """Get summary stats by stance (support/oppose)."""

    def get_finance_timeline(self, measure_id: str) -> List[dict]:
        """Get weekly contribution timeline."""

    def get_top_donors(self, measure_id: str) -> List[dict]:
        """Get top 10 donors per stance."""

    def get_contribution_breakdown(self, measure_id: str) -> dict:
        """Get size distribution."""
        # Returns: {
        #   'small': {'count': N, 'total': $},    # < $100
        #   'medium': {'count': N, 'total': $},   # $100-$999
        #   'large': {'count': N, 'total': $},    # $1,000-$9,999
        #   'mega': {'count': N, 'total': $}      # $10,000+
        # }

    def get_all_measure_ids(self) -> List[str]:
        """Get all measures with finance data."""
```

### 9.4 Finance Display Features

**Website Integration:**

1. **Summary Cards** — Total raised, committee count, concentration (top 5 share)
2. **Timeline Chart** — Weekly cumulative fundraising (support vs oppose)
3. **Contribution Breakdown** — Size buckets with "grassroots score"
4. **Top Donors List** — Names, types, amounts

---

## 10. Website Generation

**Location:** `scraper/src/website/generator.py`
**Class:** `WebsiteGenerator`

### 10.1 Generation Process

```python
def generate(self):
    """Main orchestration."""

    # 1. Load all active measures
    measures = self.db.get_all_active_measures()

    # 2. Transform to display format
    measures_data = self._prepare_measures_data(measures)

    # 3. Load recommendations from embeddings
    recommendations = self._load_recommendations()

    # 4. Load finance data
    finance_data = self._load_finance_data()

    # 5. Extract filter options
    years = sorted(set(m['year'] for m in measures_data))
    topics = self._extract_topics(measures_data)
    counties = sorted(set(m['county'] for m in measures_data if m['county']))

    # 6. Generate HTML
    html = self._generate_html(measures_data, recommendations,
                               finance_data, years, topics, counties)

    # 7. Write to output
    with open(self.output_path, 'w') as f:
        f.write(html)
```

### 10.2 Data Preparation

```python
def _prepare_measures_data(self, measures: List[BallotMeasure]) -> List[dict]:
    """Transform measures for JSON embedding."""

    for measure in measures:
        data = {
            'id': measure.id,
            'measure_id': measure.measure_id,
            'year': str(measure.year),  # String for JSON consistency
            'county': measure.county or 'Unknown',
            'title': measure.generated_title or measure.title,
            'original_title': measure.title,
            'summary': measure.summary_text,
            'passed': measure.passed,
            'percent_yes': measure.percent_yes,
            'vote_threshold': measure.vote_threshold,
            'display_topic': get_display_topic(measure),  # Normalized topic
            'data_source': measure.data_source,
            'pdf_url': measure.pdf_url,
            # ... more fields
        }
        yield data
```

### 10.3 Topic Consolidation

```python
def get_display_topic(measure: BallotMeasure) -> str:
    """Map raw topics to display categories."""

    # Check multiple source fields
    raw_topic = (measure.topic_primary or
                 measure.category_topic or
                 measure.category_type or '')

    # Apply mapping
    return TOPIC_MAPPING.get(raw_topic.lower(), 'Other')
```

### 10.4 Output Locations

```
cal_vgp/
├── index.html                 # Primary output (project root)
└── scraper/
    └── index.html             # Secondary copy
```

### 10.5 Website Features

| Feature | Description |
|---------|-------------|
| **Grid/List Views** | Toggle between card grid and compact list |
| **Explore View** | County × Topic heatmap matrix |
| **Filters** | Year, county, topic, outcome, search text |
| **Sort Options** | Year, title, pass rate |
| **Measure Modal** | Full details with recommendations |
| **Finance Section** | Charts and donor data (when available) |
| **Summary Truncation** | Show more/less for long summaries |
| **DuckDB Chat** | Text-to-SQL natural language queries |

---

## 11. Topic Classification

**Location:** `scraper/src/utils/topic_mapping.py`

### 11.1 Display Categories (12 total)

1. **Education** — Schools, bonds, parcel taxes
2. **Public Safety & Crime** — Police, fire, jails
3. **Taxes & Finance** — Sales tax, general fund
4. **Government & Elections** — Redistricting, term limits
5. **Healthcare & Welfare** — Hospitals, mental health
6. **Environment & Natural Resources** — Parks, water, climate
7. **Transportation** — Roads, transit, bridges
8. **Housing & Land Use** — Zoning, rent control
9. **Business & Labor** — Wages, regulations
10. **Utilities & Energy** — Power, telecommunications
11. **Civil Rights** — Voting, discrimination
12. **Other** — Uncategorized

### 11.2 Mapping Sources

```python
TOPIC_MAPPING = {
    # ICPSR compound topics
    'education: prek-12 | tax & revenue': 'Education',
    'education: higher ed | bonds': 'Education',

    # CEDA categories
    'bonds_ed': 'Education',
    'bonds_infra': 'Transportation',
    'taxes_sales': 'Taxes & Finance',
    'safety_police': 'Public Safety & Crime',

    # Keywords
    'school': 'Education',
    'police': 'Public Safety & Crime',
    'transit': 'Transportation',
    # ... many more
}
```

### 11.3 Keyword Fallback

When no direct mapping exists:

```python
def classify_by_keywords(title: str) -> str:
    title_lower = title.lower()

    KEYWORD_TOPICS = {
        'Education': ['school', 'education', 'student', 'teacher',
                      'college', 'university', 'classroom'],
        'Public Safety & Crime': ['police', 'fire', 'safety', 'crime',
                                  'prison', 'jail', 'emergency'],
        # ... etc
    }

    for topic, keywords in KEYWORD_TOPICS.items():
        if any(kw in title_lower for kw in keywords):
            return topic

    return 'Other'
```

---

## 12. Configuration

**Location:** `scraper/src/config.py`

### 12.1 Path Configuration

```python
from pathlib import Path

# Base paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "scraper" / "data"
DB_PATH = DATA_DIR / "ballot_measures.db"
FINANCE_DB_PATH = DATA_DIR / "finance" / "finance_statewide_v2.db"

# Output paths
OUTPUT_HTML = PROJECT_ROOT / "index.html"
EMBEDDINGS_PATH = DATA_DIR / "embeddings.npz"
METADATA_PATH = DATA_DIR / "embedding_metadata.json"
```

### 12.2 Source Configuration

```python
SOURCES = {
    "ca_sos": {
        "name": "California Secretary of State",
        "base_url": "https://www.sos.ca.gov",
        "endpoints": {
            "qualified": "/elections/ballot-measures/qualified-ballot-measures",
            "initiative_status": "/elections/ballot-measures/initiative-and-referendum-status",
        }
    },
    "uc_law_sf": {
        "name": "UC Law SF Repository",
        "base_url": "https://repository.uclawsf.edu",
        "collection": "/ca_ballot_props/",
        "max_items": 200,
        "max_pages": 20
    },
    "ballotpedia": {
        "name": "Ballotpedia",
        "base_url": "https://ballotpedia.org",
        "statewide_pattern": "/California_{year}_ballot_propositions",
        "county_pattern": "/{county}_County,_California_ballot_measures",
        "years": [2020, 2021, 2022, 2023, 2024, 2025, 2026]
    }
}
```

### 12.3 Scraping Configuration

```python
SCRAPING_CONFIG = {
    "rate_limit": 1.0,       # seconds between requests
    "timeout": 30,           # seconds per request
    "max_retries": 3,
    "backoff_factor": 2,     # exponential backoff multiplier
    "user_agent": "Mozilla/5.0 (compatible; CalBallotBot/1.0; +https://github.com/...)"
}
```

### 12.4 Summary Configuration

```python
SUMMARY_CONFIG = {
    "enabled": True,
    "model": "claude-sonnet-4-20250514",
    "max_tokens": 150,
    "batch_size": 50,
    "rate_limit": 0.1,  # seconds between API calls
}

# Pre-defined summaries for special measures
KNOWN_SUMMARIES = {
    "ACA 13": "Protect and Retain the Majority Vote Act",
    "SCA 1": "Recall Process Reform",
    # ... etc
}
```

### 12.5 Deduplication Configuration

```python
DEDUP_CONFIG = {
    "fingerprint_fields": ["year", "measure_id", "county", "data_source"],
    "measure_fingerprint_fields": ["year", "measure_id", "county"],
    "content_fields": ["title", "ballot_question", "description"],
    "cross_source_matching": True,
    "auto_merge": True
}
```

### 12.6 Environment Variable Overrides

```bash
# Database location
DATABASE_URL=/path/to/ballot_measures.db

# API server
API_HOST=0.0.0.0
API_PORT=8000

# Scraping
SCRAPING_RATE_LIMIT=2.0

# Features
ENABLE_SUMMARIES=true
ENABLE_FINANCE=true

# Logging
LOG_LEVEL=INFO
```

---

## 13. Scripts & Workflows

### 13.1 Script Inventory

**Location:** `scraper/scripts/`

| Script | Purpose | Usage |
|--------|---------|-------|
| `update_db.py` | Smart update checking | `python scripts/update_db.py` |
| `generate_summaries.py` | Batch Claude summaries | `python scripts/generate_summaries.py [--limit N] [--resume]` |
| `inspect_summaries.py` | Quality analysis | `python scripts/inspect_summaries.py [--export]` |
| `generate_embeddings.py` | Create vectors | `python scripts/generate_embeddings.py` |
| `generate_titles.py` | AI title improvement | `python scripts/generate_titles.py` |
| `export_data.py` | Export to CSV/JSON | `python scripts/export_data.py --format csv` |
| `generate_site.py` | Build website | `python scripts/generate_site.py` |
| `build_finance_crosswalk.py` | Build (prop_num, year) → measure_db_id crosswalk for finance v2 | `python -m scripts.build_finance_crosswalk` |
| `rebuild_finance_db.py` | Rebuild `finance_statewide_v2.db` from CalAccess CSV + crosswalk | `python -m scripts.rebuild_finance_db` |
| ~~`build_statewide_prop_finance_db.py`~~ | DEPRECATED v1 ETL — refuses to run; superseded by the two scripts above | — |
| `backfill_statewide_2022_2024.py` | Backfill historical data | `python scripts/backfill_statewide_2022_2024.py` |

### 13.2 Typical Workflow

```bash
# 1. Update database with new data
python scripts/update_db.py

# 2. Generate summaries for new measures
python scripts/generate_summaries.py

# 3. Inspect summary quality
python scripts/inspect_summaries.py --export

# 4. Regenerate embeddings (if needed)
python scripts/generate_embeddings.py

# 5. Build website
python -c "from src.website.generator import WebsiteGenerator; WebsiteGenerator().generate()"

# 6. Serve locally for testing
python -m http.server 8000
```

### 13.3 Quick Website Regeneration

```bash
cd /Users/igorgeyn/Desktop/personal/cal_vgp/scraper
python3 -c "from src.website.generator import WebsiteGenerator; gen = WebsiteGenerator(); gen.generate()"
```

---

## 14. Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         DATA INGESTION LAYER                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │
│  │  CA SOS     │  │ Ballotpedia │  │ Ballotpedia │  │  UC Law SF  │   │
│  │  Scraper    │  │  Statewide  │  │   County    │  │   Scraper   │   │
│  │             │  │  Scraper    │  │  Scraper    │  │             │   │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘   │
│         │                │                │                │           │
│  ┌──────┴──────┐  ┌──────┴──────┐  ┌──────┴──────┐  ┌──────┴──────┐   │
│  │ CEDA Parser │  │ICPSR Parser │  │ NCSL Parser │  │ CalAccess   │   │
│  │ (1995-2024) │  │ (1902-2016) │  │             │  │ (Finance)   │   │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘   │
│         │                │                │                │           │
└─────────┼────────────────┼────────────────┼────────────────┼───────────┘
          │                │                │                │
          └────────────────┼────────────────┘                │
                           │                                 │
                    ┌──────▼───────┐                  ┌──────▼───────┐
                    │ BallotMeasure│                  │   Finance    │
                    │   Objects    │                  │   Records    │
                    └──────┬───────┘                  └──────┬───────┘
                           │                                 │
┌──────────────────────────┼─────────────────────────────────┼───────────┐
│                    DATA PROCESSING LAYER                   │           │
├──────────────────────────┼─────────────────────────────────┼───────────┤
│                          │                                 │           │
│                   ┌──────▼───────┐                  ┌──────▼───────┐  │
│                   │ Deduplication│                  │   Finance    │  │
│                   │              │                  │  Aggregation │  │
│                   │ ┌──────────┐ │                  │              │  │
│                   │ │ Exact    │ │                  │ - Summaries  │  │
│                   │ │ Match    │ │                  │ - Timelines  │  │
│                   │ └──────────┘ │                  │ - Top Donors │  │
│                   │ ┌──────────┐ │                  └──────┬───────┘  │
│                   │ │ Content  │ │                         │          │
│                   │ │ Hash     │ │                         │          │
│                   │ └──────────┘ │                         │          │
│                   │ ┌──────────┐ │                         │          │
│                   │ │ Cross-   │ │                         │          │
│                   │ │ Source   │ │                         │          │
│                   │ └──────────┘ │                         │          │
│                   └──────┬───────┘                         │          │
│                          │                                 │          │
└──────────────────────────┼─────────────────────────────────┼──────────┘
                           │                                 │
┌──────────────────────────┼─────────────────────────────────┼──────────┐
│                     STORAGE LAYER                          │          │
├──────────────────────────┼─────────────────────────────────┼──────────┤
│                          │                                 │          │
│    ┌─────────────────────▼──────────────────┐    ┌────────▼───────┐ │
│    │        ballot_measures.db              │    │ finance_       │ │
│    │                                        │    │ statewide.db   │ │
│    │  ┌─────────────┐  ┌─────────────┐    │    │                │ │
│    │  │  measures   │  │measure_search│    │    │ - committee    │ │
│    │  │  (main)     │  │   (FTS5)    │    │    │ - transaction  │ │
│    │  └─────────────┘  └─────────────┘    │    │ - summary      │ │
│    │  ┌─────────────┐  ┌─────────────┐    │    │ - timeline     │ │
│    │  │  measure_   │  │ scraper_    │    │    │ - top_donors   │ │
│    │  │  updates    │  │ runs        │    │    └────────────────┘ │
│    │  └─────────────┘  └─────────────┘    │                       │
│    └────────────────────────────────────────┘                       │
│                                                                      │
│    ┌────────────────┐    ┌────────────────┐    ┌────────────────┐  │
│    │ embeddings.npz │    │ embedding_     │    │ title_cache    │  │
│    │ (vectors)      │    │ metadata.json  │    │ .json          │  │
│    └────────────────┘    └────────────────┘    └────────────────┘  │
│                                                                      │
└──────────────────────────────┬───────────────────────────────────────┘
                               │
┌──────────────────────────────▼───────────────────────────────────────┐
│                       ENRICHMENT LAYER                                │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌────────────────────┐  ┌────────────────────┐  ┌────────────────┐ │
│  │ Summary Generation │  │ Embedding Creation │  │Title Generation│ │
│  │                    │  │                    │  │                │ │
│  │ ┌────────────────┐ │  │ ┌────────────────┐ │  │ ┌────────────┐ │ │
│  │ │  Claude API    │ │  │ │ Sentence       │ │  │ │  Ollama    │ │ │
│  │ │  (Sonnet)      │ │  │ │ Transformers   │ │  │ │  (local)   │ │ │
│  │ └────────────────┘ │  │ └────────────────┘ │  │ └────────────┘ │ │
│  │                    │  │                    │  │                │ │
│  │ - Context-aware    │  │ - Cosine similarity│  │ - Verbose →   │ │
│  │ - Neutral tone     │  │ - Top-N neighbors  │  │   concise     │ │
│  │ - 1-2 sentences    │  │ - Recommendations  │  │ - Caching     │ │
│  └────────────────────┘  └────────────────────┘  └────────────────┘ │
│                                                                       │
└──────────────────────────────┬───────────────────────────────────────┘
                               │
┌──────────────────────────────▼───────────────────────────────────────┐
│                      PRESENTATION LAYER                               │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────────┐│
│  │                    WebsiteGenerator                              ││
│  │                                                                  ││
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐││
│  │  │ Load Data  │→│ Transform  │→│ Load Recs  │→│ Generate   │││
│  │  │ from DB    │  │ to JSON    │  │ & Finance  │  │ HTML       │││
│  │  └────────────┘  └────────────┘  └────────────┘  └────────────┘││
│  └──────────────────────────────────────────────────────────────────┘│
│                               │                                       │
│                        ┌──────▼──────┐                               │
│                        │ index.html  │                               │
│                        │             │                               │
│                        │ - Grid/List │                               │
│                        │ - Explore   │                               │
│                        │ - Filters   │                               │
│                        │ - Modal     │                               │
│                        │ - Finance   │                               │
│                        │ - DuckDB    │                               │
│                        └─────────────┘                               │
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────────┐│
│  │                    FastAPI Server (Optional)                     ││
│  │                                                                  ││
│  │  /measures  /search  /statistics  /finance/{id}                 ││
│  └──────────────────────────────────────────────────────────────────┘│
│                                                                       │
└───────────────────────────────────────────────────────────────────────┘
```

---

## 15. Error Handling & Robustness

### 15.1 Scraper Level

```python
# HTTP error handling with retries
for attempt in range(max_retries):
    try:
        response = session.get(url, timeout=timeout)
        response.raise_for_status()
        return response
    except RequestException as e:
        if attempt < max_retries - 1:
            sleep(backoff_factor ** attempt)  # Exponential backoff
        else:
            logger.error(f"Failed after {max_retries} attempts: {e}")
            raise
```

### 15.2 Database Level

```python
# Transaction safety
with conn:
    try:
        conn.execute(query, params)
        conn.commit()
    except sqlite3.Error as e:
        conn.rollback()
        raise

# Schema migration
def _check_schema(self):
    """Auto-add missing columns."""
    existing = {row[1] for row in conn.execute("PRAGMA table_info(measures)")}
    for field in BallotMeasure.__dataclass_fields__:
        if field not in existing:
            conn.execute(f"ALTER TABLE measures ADD COLUMN {field} TEXT")
```

### 15.3 Parsing Level

```python
# Encoding detection for ICPSR
ENCODINGS = ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252']

for encoding in ENCODINGS:
    try:
        df = pd.read_csv(path, encoding=encoding)
        break
    except UnicodeDecodeError:
        continue

# Null field handling
year = int(row.get('year') or row.get('YEAR') or 0) or None
```

### 15.4 Summary Generation Level

```python
# Checkpoint-based resume
try:
    for measure in measures:
        summary = call_claude_api(prompt)
        batch_updates.append((summary, measure_id))

        if len(batch_updates) >= BATCH_SIZE:
            conn.executemany(update_query, batch_updates)
            conn.commit()
            save_checkpoint(processed_ids, stats)
            batch_updates = []

except KeyboardInterrupt:
    # Save progress on interrupt
    if batch_updates:
        conn.executemany(update_query, batch_updates)
        conn.commit()
    save_checkpoint(processed_ids, stats)
    logger.info("Checkpoint saved. Resume with --resume flag.")
```

---

## 16. Data Quality Evaluation

### 16.1 Quality Evaluation Pipeline

**Location:** `scraper/scripts/evaluate_data_quality.py`

A comprehensive data quality evaluation system that scores data across 9 dimensions:

```bash
# Run evaluation
python scripts/evaluate_data_quality.py --export

# Output: data/data_quality_report.json
```

### 16.2 Quality Dimensions

| Dimension | Weight | What It Measures |
|-----------|--------|------------------|
| **Completeness** | 20% | Missing values across critical, important, and optional fields |
| **Accuracy** | 20% | Vote math, percentage calculations, outcome logic |
| **Consistency** | 15% | Type validation, cross-field logic, value ranges |
| **Uniqueness** | 10% | Duplicate detection, fingerprint integrity |
| **Timeliness** | 10% | Coverage gaps, data freshness |
| **Validity** | 10% | Format validation, enum constraints |
| **Summary Quality** | 10% | AI-generated content analysis |
| **Finance Quality** | 5% | Campaign finance data validation |
| **Recommendations** | 5% | Embedding coverage, self-references |

### 16.3 Current Quality Score

**Overall: 86.7% (Grade: A-)**

| Dimension | Score | Notes |
|-----------|-------|-------|
| Completeness | 90.9% | Optional fields sparse (by design) |
| Accuracy | 96.4% | Vote math perfect |
| Consistency | 83.3% | Some threshold mismatches |
| Uniqueness | 80.0% | Content duplicates expected |
| Timeliness | 89.9% | 2025 gap expected |
| Validity | 52.4% | Non-standard IDs accepted |
| Summary Quality | 96.1% | 100% coverage |
| Finance Quality | 90.0% | 75% statewide coverage |
| Recommendations | 95.3% | 95% coverage |

### 16.4 Data Quality Fix Script

**Location:** `scraper/scripts/fix_data_quality_issues.py`

```bash
# Dry run (preview changes)
python scripts/fix_data_quality_issues.py --dry-run

# Apply fixes
python scripts/fix_data_quality_issues.py
```

**Fixes Applied:**
- Active duplicates → Set `is_active=0`
- `has_summary` flag sync → Match actual summary presence
- Incorrect `passed` values → Fix based on percentage/threshold
- Election date normalization → Convert to `YYYY-MM-DD`

---

## 17. Known Issues & Limitations

See [KNOWN_ISSUES.md](KNOWN_ISSUES.md) for detailed documentation of accepted limitations.

### 17.1 Source Limitations

| Issue | Description | Mitigation |
|-------|-------------|------------|
| **CA SOS URL changes** | Historical election URLs have changed | UC Law SF + CEDA backfill |
| **ICPSR cutoff** | Data ends at 2016 | CEDA fills 2016–2024 gap |
| **CEDA format variance** | Column names differ by year | Flexible column mapping |
| **Ballotpedia scraper bugs** | Duplicate records across years | Year extraction + dedup |
| **Special district gaps** | Fire/recreation districts incomplete | Ballotpedia provides some |
| **Finance coverage** | Only statewide props with committees | Limited to high-profile measures |

### 17.2 Data Validation

```python
# Year validation
assert isinstance(measure.year, int), "Year must be integer"
assert 1900 <= measure.year <= 2030, "Year out of range"

# Percentage validation
if measure.yes_votes and measure.no_votes:
    total = measure.yes_votes + measure.no_votes
    calc_pct = (measure.yes_votes / total) * 100
    assert abs(calc_pct - measure.percent_yes) < 0.1, "Percentage mismatch"

# Fingerprint uniqueness
assert len(set(m.fingerprint for m in measures)) == len(measures)
```

### 17.3 Deferred Issues

| Issue | Count | Status |
|-------|-------|--------|
| Vote threshold encoding errors | 5 | Needs manual verification |
| Exactly 50% ties | 2 | Accepted (correct behavior) |
| Content duplicates (cross-source) | 257 | Accepted (by design) |
| 2025 coverage gap | 1 year | Expected (no statewide elections) |
| Negative finance total | 1 | Needs investigation |

### 17.4 Recommended Improvements

1. **Historical PDF scraping** — UC Law SF has PDFs we're not downloading
2. **Special district coverage** — Partner with county registrars
3. **Finance expansion** — Include county-level campaign finance
4. **Real-time updates** — Webhook integration with CA SOS
5. **Multi-state expansion** — Generalize scrapers for other states

---

## Appendix A: Quick Reference Commands

```bash
# Database location
DB=/Users/igorgeyn/Desktop/personal/cal_vgp/scraper/data/ballot_measures.db

# Count active measures
sqlite3 $DB "SELECT COUNT(*) FROM measures WHERE is_active = 1"

# Check data sources
sqlite3 $DB "SELECT data_source, COUNT(*) FROM measures WHERE is_active = 1 GROUP BY data_source"

# Find measures without summaries
sqlite3 $DB "SELECT COUNT(*) FROM measures WHERE is_active = 1 AND summary_text IS NULL"

# Regenerate website
cd /Users/igorgeyn/Desktop/personal/cal_vgp/scraper
python3 -c "from src.website.generator import WebsiteGenerator; WebsiteGenerator().generate()"

# Generate summaries (with resume)
python scripts/generate_summaries.py --resume

# Inspect summary quality
python scripts/inspect_summaries.py --export

# Backup database
sqlite3 $DB ".backup 'data/ballot_measures_$(date +%Y%m%d).db'"
```

---

## Appendix B: File Size Reference

| File | Size | Description |
|------|------|-------------|
| `ballot_measures.db` | 29 MB | Main SQLite database |
| `finance_statewide_v2.db` | ~12 MB | Finance data (live, post-2026-05-04 rebuild) |
| `finance_statewide.db` | ~15 MB | Legacy v1 finance data, audit-only |
| `embeddings.npz` | 15.8 MB | Semantic vectors |
| `embedding_metadata.json` | 3.4 MB | Recommendations |
| `title_cache.json` | 1.6 MB | Generated titles |
| `index.html` | ~2 MB | Generated website |

---

*Document generated: February 2026*
