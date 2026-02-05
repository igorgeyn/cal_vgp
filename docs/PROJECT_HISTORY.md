# CalBallot Project History

> Summary of development work from January–February 2026 for context in announcing the project.

---

## Project Overview

**CalBallot** is a comprehensive, searchable database of California ballot measures spanning 1998 to the present. It aggregates data from multiple authoritative sources, enriches it with AI-generated summaries, and presents it through an interactive web interface with campaign finance analysis and semantic recommendations.

**Live Site:** [CalBallot](https://calballot.com) *(or wherever hosted)*
**GitHub:** [github.com/igorgeyn/cal_vgp](https://github.com/igorgeyn/cal_vgp)

---

## Key Statistics

- **11,483+ ballot measures** from all 58 California counties + statewide propositions
- **100% AI-generated summaries** using Claude Sonnet
- **98 statewide propositions** with campaign finance data
- **641,000+ campaign contribution records** from CalAccess
- **95% recommendation coverage** via semantic embeddings
- **86.7% data quality score** (Grade: A-)

---

## Development Timeline

### Week 1 (Early January 2026)

**Foundation & Data Ingestion**
- Set up project structure with Python scrapers and SQLite database
- Implemented scrapers for multiple data sources:
  - California Secretary of State (current measures)
  - Ballotpedia (statewide and county-level, 2020–2026)
  - UC Law SF Repository (historical propositions)
- Integrated historical data parsers:
  - CEDA (California Elections Data Archive, 1998–2024) — ~10,800 measures
  - ICPSR academic dataset (1902–2016)
  - NCSL ballot measures data

**Core Database Design**
- Designed `BallotMeasure` data model with 40+ fields
- Implemented multi-level deduplication system:
  - Exact fingerprint matching
  - Content hash matching
  - Cross-source measure matching
- Created scoring system to select "master" records when merging duplicates

### Week 2 (Mid-January 2026)

**Website Generation & UI**
- Built static site generator producing a single-page application
- Implemented filtering by year, county, topic, and pass/fail status
- Created responsive card grid and list views
- Added "Explore" matrix view showing measures by county × topic
- Implemented measure detail modal with full information

**DuckDB Integration**
- Added DuckDB-WASM for client-side SQL queries
- Implemented natural language "Ask a question" feature
- Created "Show your work" toggle to display generated SQL

### Week 3 (Late January 2026)

**AI Summary Generation**
- Developed batch summary generation pipeline using Claude Sonnet API
- Processed all ~9,000 measures lacking summaries
- Implemented checkpointing for resume capability
- Created summary quality inspection tools
- Cleaned preambles and quality issues from generated content
- Achieved **100% summary coverage** across all measures

**Vote Data Enrichment**
- Added `vote_threshold` field (50%, 55%, 66.67%) derived from CEDA pass_fail codes
- Backfilled vote percentages and counts from CEDA to Ballotpedia measures
- Fixed 1,106 measures with missing vote data

### Week 4 (Late January – Early February 2026)

**Campaign Finance Integration**
- Integrated CalAccess campaign finance data
- Built finance database with 641,000+ transaction records
- Created `finance_statewide.db` with:
  - Committee information
  - Transaction records with donor canonicalization
  - Pre-aggregated summaries by measure/stance
  - Weekly fundraising timelines
  - Top donors lists

**Finance UI Features**
- Added fundraising timeline chart (support vs oppose over time)
- Implemented contribution size breakdown ("grassroots score"):
  - Small: <$100
  - Medium: $100–$999
  - Large: $1,000–$9,999
  - Mega: $10,000+
- Displayed top donors with sector classification
- Added HHI concentration metrics

### Week 5 (Early February 2026)

**Semantic Recommendations**
- Generated embeddings for all measures using sentence transformers
- Computed nearest-neighbor recommendations
- Cleaned self-references and duplicate recommendations
- Achieved 95% recommendation coverage

**Data Quality Pipeline**
- Created comprehensive 9-dimension quality evaluation:
  - Completeness, Accuracy, Consistency, Uniqueness
  - Timeliness, Validity, Summary Quality
  - Finance Quality, Recommendations
- Built automated fix script for common issues
- Achieved **86.7% overall quality score (A-)**

**Documentation**
- Wrote comprehensive pipeline documentation (DATA_PIPELINE.md)
- Created known issues tracker (KNOWN_ISSUES.md)
- Documented all scripts and workflows

**UI Polish**
- Tightened modal display, reduced whitespace
- Added "Show more/less" toggle for long summaries
- Fixed No percentage calculation bug
- Made intro text dynamic (not dependent on exact measure count)

---

## Technical Highlights

### Multi-Source Data Aggregation
Combined 6+ authoritative sources with intelligent deduplication, preserving the most complete information from each while avoiding duplicates.

### AI-Powered Summaries
Used Claude Sonnet to generate neutral, informative summaries for every ballot measure. Each summary includes context like location, year, topic, and outcome when available.

### Campaign Finance Analysis
Integrated real CalAccess data showing who funds ballot measure campaigns, with timeline visualization and contribution breakdowns revealing grassroots vs. big-donor support patterns.

### Semantic Search & Recommendations
Embedded all measures using sentence transformers to power "related measures" recommendations, helping users discover similar ballot measures across years and counties.

### Client-Side SQL
Integrated DuckDB-WASM for powerful client-side querying, letting users ask natural language questions that get translated to SQL and executed entirely in the browser.

### Comprehensive Quality Assurance
Built a 9-dimension data quality evaluation pipeline that scores data completeness, accuracy, consistency, and more — currently achieving an A- grade.

---

## Data Sources

| Source | Type | Coverage |
|--------|------|----------|
| California Secretary of State | Scraper | Current cycle |
| Ballotpedia | Scraper | 2020–2026 |
| UC Law SF Repository | Scraper | Historical (1900s–recent) |
| CEDA | Parser | 1998–2024 |
| ICPSR | Parser | 1902–2016 |
| CalAccess | Finance | 2016–present |

---

## Tech Stack

- **Backend:** Python, SQLite, Claude API
- **Frontend:** Vanilla JavaScript, CSS Grid/Flexbox
- **Data:** DuckDB-WASM, sentence-transformers
- **Finance:** CalAccess TSV processing
- **Quality:** Custom evaluation pipeline

---

## Key Differentiators

1. **Comprehensive Coverage** — Not just statewide props, but county and local measures too
2. **AI Summaries** — Every measure has a neutral, readable summary
3. **Campaign Finance** — See who's funding Yes and No campaigns
4. **Historical Depth** — Data back to 1998 (with some records to 1902)
5. **Open Data** — Exportable, queryable, transparent
6. **Quality Tracked** — Documented data quality with known limitations

---

## Future Roadmap

- Historical PDF scraping from UC Law SF
- Special district coverage expansion
- County-level campaign finance
- Real-time updates via CA SOS webhooks
- Multi-state expansion

---

## Credits

Built with assistance from Claude (Anthropic) for:
- Code development and architecture
- AI summary generation
- Data quality analysis
- Documentation

---

*Last updated: February 2026*
