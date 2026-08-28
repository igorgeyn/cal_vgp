# CalBallot Project History

> Summary of development work from January–February 2026 for context in announcing the project.
>
> **Snapshot, not current state.** The body of this document describes the
> Jan–Feb 2026 build. Two major arcs have happened since, summarized in
> "Since February 2026" at the end of this file:
>
> - **Finance rebuild (May 2026).** `finance_statewide.db` was replaced by
>   `finance_statewide_v2.db` keyed on year-scoped `finance_campaign_id` after
>   Codex caught a cross-cycle contamination bug, then extended with a v3 layer
>   for loans, in-kind, and independent expenditures. Current: 181 statewide
>   measures / $5.75B combined. See `scraper/data/finance/README.md`.
> - **Registrar pipeline (June–August 2026).** A recurring scraper for county
>   registrar websites — the project's first live data pipeline. See
>   `docs/plans/registrar_pipeline_infra.md`.
>
> For current state always read `docs/WORKING_LIST.md` first.

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

---

## Since February 2026

This section summarizes work after the original snapshot above. It is
deliberately brief; the authoritative records are `docs/WORKING_LIST.md`
(current state), `docs/LESSONS_LEARNED.md` (what went wrong and why), and
the per-arc plans in `docs/plans/`.

### Finance rebuild — v2 and v3 (May 2026)

A Codex review found that the original finance database keyed campaigns by
bare proposition number, letting different election cycles contaminate each
other. The rebuild introduced year-scoped `finance_campaign_id` (e.g.
`PROP_16_2020`) with eight row-level acceptance gates.

A second phase added `finance_statewide_v3.db` covering loans, in-kind
contributions, and independent expenditures — categories the original scope
omitted — followed by an atomic flip of every consumer surface onto a
combined v2+v3 read layer. Fourteen Codex review rounds went into the
attribution resolver alone.

Current: **181 statewide measures, $5.75B** in combined reportable money.
Verification runs in four layers (prior-state unchanged, source reconcile,
per-row trace, cross-layer integrity), all green at closeout.

Notable lesson: a dedup gate keyed on raw donor names rather than
canonicalized ones hid $78M of duplicate receipts. Any comparison that means
"are these the same thing?" must run through the canonical form.

### Registrar pipeline (June–August 2026)

The project's first **recurring** data pipeline, and a shift in kind: from
one-shot ingests of aggregator datasets to continuously collecting official
primary documents from county election offices.

Architecture: county scrapers → immutable checksummed snapshots in Cloudflare
R2 → parser → normalized JSONL → loader → `ballot_measures.db`. The artifact
store is the canonical truth layer, which makes every parse reproducible from
stored bytes forever and re-parsing free.

Milestones:

- **Phase 0 (June).** Reconnaissance across the five largest counties. Found
  three distinct URL architectures, one county requiring a polite User-Agent
  to avoid a 403, and one behind a Cloudflare challenge.
- **Phase 0.5 (July).** Storage layer, polite-scraping base class, runner with
  per-county failure isolation, and a GitHub Actions cron. Six external review
  rounds before the first real scraper.
- **Phase 1 (July 27).** San Bernardino live in production, capturing the
  November 2026 election as it is assembled.
- **Parser and loader (August).** Snapshot replay with stable cross-snapshot
  identity, scope watermarks preventing backward rolls, and an assign-once
  identity registry. Verified against database copies; **not yet activated**
  against the live database.

What the archive holds as of 2026-08-27: five immutable weekly snapshots of
the San Bernardino November 2026 ballot, which grew from 8 measures and 16
documents in July to **20 measures and 88 documents** — notices of election,
resolutions, full measure texts, impartial analyses, tax rate statements, and
arguments for and against. This is material the county will eventually remove
from its website.

Three production drift events (roughly one per two weeks) each surfaced as a
loud, precise failure rather than corrupted data — the county published a
document type the extractor had no role for, and the pipeline refused to
guess. One of those refusals prevented a silent misattribution of five tax
rate statements as impartial analyses.

---

*Original snapshot: February 2026. Addendum: August 2026.*
