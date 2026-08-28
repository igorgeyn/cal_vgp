# Architecture

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
>
> **Most changed here:** the pipeline diagram predates the registrar
> pipeline entirely. See [`../plans/registrar_pipeline_infra.md`](../plans/registrar_pipeline_infra.md).

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DATA COLLECTION                                 │
│                                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │  Ballotpedia │  │   CA SOS     │  │   County     │  │  Historical  │    │
│  │   Scrapers   │  │   Scraper    │  │   Scrapers   │  │   Parsers    │    │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘    │
│         │                 │                 │                 │             │
│         └────────────────┬┴─────────────────┴─────────────────┘             │
│                          │                                                   │
│                          ▼                                                   │
│                 ┌────────────────┐                                           │
│                 │   Raw JSON     │  scraper/data/raw/                       │
│                 └────────┬───────┘                                           │
└──────────────────────────┼──────────────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                           DATA PROCESSING                                    │
│                                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │ Deduplication│  │    Topic     │  │    Title     │  │   Summary    │    │
│  │   Engine     │  │   Mapping    │  │  Generation  │  │  Generation  │    │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘    │
│         │                 │                 │                 │             │
│         └────────────────┬┴─────────────────┴─────────────────┘             │
│                          │                                                   │
│                          ▼                                                   │
│                 ┌────────────────┐                                           │
│                 │   SQLite DB    │  scraper/data/ballot_measures.db         │
│                 │   (24.8 MB)    │                                           │
│                 └────────┬───────┘                                           │
└──────────────────────────┼──────────────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                         OUTPUT GENERATION                                    │
│                                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │   Website    │  │     CSV      │  │     JSON     │  │  Embeddings  │    │
│  │  Generator   │  │    Export    │  │    Export    │  │  Generator   │    │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘    │
│         │                 │                 │                 │             │
│         ▼                 ▼                 ▼                 ▼             │
│    index.html        .csv files        .json files      embeddings.npz     │
│     (35 MB)          (4.5 MB)          (6.1 MB)          (15.8 MB)         │
└──────────────────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                            DEPLOYMENT                                        │
│                                                                              │
│  ┌──────────────────────────────┐    ┌──────────────────────────────┐       │
│  │       GitHub Pages           │    │    Cloudflare Worker         │       │
│  │    (Static Hosting)          │    │    (CORS Proxy)              │       │
│  │                              │    │                              │       │
│  │  ┌────────────────────────┐  │    │  ┌────────────────────────┐  │       │
│  │  │     index.html         │  │    │  │   POST /anthropic      │  │       │
│  │  │   (embedded data)      │  │    │  │   POST /openai         │  │       │
│  │  └────────────────────────┘  │    │  └────────────────────────┘  │       │
│  │                              │    │                              │       │
│  │  URL: cal-vgp.igorgeyn.com  │    │  URL: *.workers.dev          │       │
│  └──────────────────────────────┘    └──────────────────────────────┘       │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Component Details

### 1. Data Collection Layer

#### Scrapers (`src/scrapers/`)

**Base Scraper Pattern:**
```python
class BaseScraper:
    # Uses SCRAPING_CONFIG from src/config.py for rate limit, timeout, retries
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(SCRAPING_CONFIG['headers'])

    def _rate_limit(self):
        # Enforce delay between requests (config-driven)

    def _fetch_page(self, url):
        # Fetch with retry logic and exponential backoff

    def run(self) -> List[BallotMeasure]:
        # Main entry point
```

> _Evidence: `scraper/src/scrapers/base.py:17-69`, `base.py:133-158`. No `delay_seconds` init arg, no `scrape_all()`, no `_fetch()`. Methods are `_fetch_page()` and `run()`._

**Scraper Registry:**
| Scraper | File | Target |
|---------|------|--------|
| Ballotpedia Statewide | `ballotpedia_statewide.py` | State propositions |
| Ballotpedia Counties | `ballotpedia_counties.py` | All 58 counties |
| CA Secretary of State | `ca_sos.py` | Qualified measures |
| LA County | `la_county.py` | results.lavote.gov |
| San Diego County | `san_diego_county.py` | sdvote.com |
| Orange County | `orange_county.py` | ocvote.gov |
| San Bernardino County | `san_bernardino_county.py` | rov.sbcounty.gov |

#### Parsers (`src/parsers/`)

**Historical Data Sources:**
| Parser | File | Format | Coverage |
|--------|------|--------|----------|
| NCSL | `ncsl.py` | Excel | 2014-present |
| ICPSR | `icpsr.py` | CSV | 1902-2016 |
| CEDA | `ceda.py` | Excel | 1998-2024 |

---

### 2. Data Processing Layer

#### Database Operations (`src/database/`)

**Models (`models.py`):**
```python
@dataclass
class BallotMeasure:
    measure_id: str
    year: int
    state: str = 'CA'
    county: Optional[str] = None
    jurisdiction: Optional[str] = None
    title: str = None
    description: Optional[str] = None
    ballot_question: Optional[str] = None
    yes_votes: Optional[int] = None
    no_votes: Optional[int] = None
    # ... 48 columns total in DB schema
```

**Operations (`operations.py`):**
- `insert_measure()` - Insert with fingerprint check
- `update_measure()` - Update existing record
- `get_measure()` - Retrieve by fingerprint or ID
- `search_measures()` - Full-text search
- `get_stats()` - Aggregate statistics

**Deduplication (`deduplication.py`):**
- Fingerprint generation
- Cross-source matching
- Content hash comparison
- Master record selection
- Merge operations

#### Enrichment (`src/enrichment/`)

**Summary Generation:**
- `src/enrichment/summaries.py` is a **placeholder module** (contains known-summaries config and helper functions but does not call LLMs directly)
- **Actual AI summary generation** is in `scripts/generate_ai_summaries.py` — uses Ollama only
- Neutral 2-3 sentence summaries
- Priority: Recent measures first

> _Evidence: `summaries.py:85-135` (placeholder), `scripts/generate_ai_summaries.py:1-98` (Ollama-only implementation)._

#### Utilities (`src/utils/`)

**Topic Mapping (`topic_mapping.py`):**
- 47 raw categories → 12 display categories
- Keyword-based classification
- Source category normalization

**Title Generation (`title_generator.py`):**
- Multi-provider support (Ollama > Groq > Claude, auto-detection order)

> _Note: Groq is available for title generation only (via `title_generator.py`), NOT in the browser chat UI._
- Simplified, readable titles
- Caching system

**Regions (`regions.py`):**
- 9 California regions defined
- County → Region mapping

---

### 3. Output Generation Layer

#### Website Generator (`src/website/generator.py`)

**Process:**
1. Query database for active measures
2. Prepare JSON data structure
3. Load embeddings for recommendations
4. Generate filter options
5. Compile statistics
6. Render HTML template
7. Embed all data as JSON
8. Save to `index.html`

**Output:** Single 35 MB HTML file with:
- All 12,156 measures as embedded JSON
- CSS styles inline
- JavaScript inline
- No external dependencies (except AI APIs)

#### Export Scripts (`scripts/`)

| Script | Output | Format |
|--------|--------|--------|
| `export_data.py` | `exports/*.csv` | CSV with 25 fields (24 DB + 1 computed) |
| `export_data.py` | `exports/*.json` | JSON array |
| `generate_embeddings.py` | `embeddings.npz` | NumPy compressed |

---

### 4. Deployment Layer

#### GitHub Pages

**Configuration:**
- Repository root `index.html`
- `CNAME` file for custom domain
- No build step (pre-generated)

**Domain:** `cal-vgp.igorgeyn.com`

#### Cloudflare Worker (`cloudflare-worker/`)

**Purpose:** CORS proxy for AI API calls from browser

**worker.js:**
```javascript
export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (url.pathname === '/anthropic') {
      // Proxy to api.anthropic.com
    }

    if (url.pathname === '/openai') {
      // Proxy to api.openai.com
    }

    // Add CORS headers
    return response;
  }
}
```

**Deployment:**
```bash
cd cloudflare-worker
wrangler deploy
```

---

## Data Flow

### 1. Scraping Flow

```
External Website
      │
      ▼
┌─────────────┐
│   Scraper   │  requests.get() with rate limiting
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Parse HTML  │  BeautifulSoup / pandas
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ BallotMeasure│  Dataclass instance
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Raw JSON   │  data/raw/{source}_{timestamp}.json
└─────────────┘
```

### 2. Processing Flow

```
Raw JSON Files
      │
      ▼
┌─────────────┐
│ Fingerprint │  Generate unique key
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Dedupe     │  Check for duplicates
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Insert/     │  Database operation
│ Update      │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Enrich     │  AI summaries, titles
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   SQLite    │  ballot_measures.db
└─────────────┘
```

### 3. Website Generation Flow

```
SQLite Database
      │
      ▼
┌─────────────┐
│ Query Active│  SELECT * FROM active_measures
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Load        │  embeddings.npz + metadata
│ Embeddings  │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Generate    │  Jinja2 or string formatting
│ HTML        │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Embed JSON  │  All data in <script> tag
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ index.html  │  35 MB single file
└─────────────┘
```

---

## Build System (Makefile)

### Common Commands

```makefile
# Generate website
make website

# Scrape current data
make scrape

# Generate AI content
make summaries          # Ollama-based summaries
make summaries-web      # Web-based summaries
make summaries-ai       # AI summaries

# Export data
make export-csv

# Database operations
make db-init
make backup
make db-stats

# Development
make api        # Start FastAPI server
make test       # Run tests
make lint       # Run linter
make format     # Format code

# Composite targets
make update     # Update data
make check      # Check for new measures
make quick      # update + website
make full-run   # db-init + scrape + update + website
```

> _Evidence: `scraper/Makefile:4-111`. Non-existent targets removed: `scrape-ballotpedia`, `scrape-la-county`, `titles`, `embeddings`, `export-json`, `db-backup`, `import-*`, `scrape-all`, `export-all`._

### Full Build Pipeline

```bash
# 1. Initialize database (if new)
make db-init

# 2. Scrape current data
make scrape

# 3. Update (dedup, enrich)
make update

# 4. Generate AI summaries
make summaries

# 5. Export and generate website
make export-csv
make website

# 6. Deploy (manual git push)
git add index.html
git commit -m "Update website"
git push
```

---

## API Server (Optional)

**File:** `src/api/server.py`

**Framework:** FastAPI

**Endpoints:**
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/measures` | List measures (with filters) |
| GET | `/api/measures/{id}` | Get single measure |
| POST | `/api/search` | Advanced search |
| GET | `/api/stats` | Database statistics |
| GET | `/api/years` | Year aggregations |
| GET | `/api/topics` | Topic aggregations |
| GET | `/api/export` | Data export |

**Running:**
```bash
make api
# or
cd scraper && uvicorn src.api.server:app --reload --port 8000
```

**Known Limitations:**
- Historical context endpoints (`/api/historical/*`) require `historical_operations.py` and `historical_schema.py` modules which are not yet implemented. These endpoints return HTTP 501 when the modules are absent.
- Core endpoints (`/api/measures`, `/api/search`, `/api/stats`, `/api/years`, `/api/topics`, `/api/export`) work without the historical modules.

> _Evidence: `server.py:18-28` — historical imports are optional with graceful fallback._

---

## Configuration

### Environment Variables

```bash
# AI Providers
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
GROQ_API_KEY=gsk_...              # Used by title_generator.py only
OLLAMA_API_URL=http://localhost:11434  # Not OLLAMA_HOST

# Database
DATABASE_URL=sqlite:///data/ballot_measures.db  # Not DATABASE_PATH

# API Server
API_PORT=8000
API_HOST=0.0.0.0

# Scraping
SCRAPING_RATE_LIMIT=1.0           # Not SCRAPE_DELAY
```

> _Evidence: `scraper/src/config.py:24-62`, `scraper/src/utils/title_generator.py:54-57`._

### Config File (`src/config.py`)

Configuration uses **module-level constants** (no `Config` class):

```python
# Module-level constants
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "ballot_measures.db"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DB_PATH}")

API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))

SCRAPING_CONFIG = {
    "rate_limit": float(os.getenv("SCRAPING_RATE_LIMIT", "1.0")),
    # ...
}
```

> _Evidence: `scraper/src/config.py:20-80` — no `Config` class exists._

---

## Error Handling

### Scraping Errors
- Rate limiting with exponential backoff
- Retry on 429/503 responses
- Log and continue on individual failures
- Track failed items for later retry

### Database Errors
- Transaction rollback on failure
- Constraint violation handling
- Duplicate detection logging

### AI Errors
- Provider fallback chain
- Graceful degradation (no summary is fine)
- Cache to avoid re-requesting failed items
