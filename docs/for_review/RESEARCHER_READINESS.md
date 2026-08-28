# Researcher Readiness

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

## Overview

This document assesses how well the California Ballot Measures Database serves academic and professional researchers studying direct democracy, civic engagement, and electoral behavior.

---

## Data Completeness

### Coverage Assessment

| Dimension | Coverage | Notes |
|-----------|----------|-------|
| **Geographic** | 100% | All 58 CA counties + statewide |
| **Temporal (Primary)** | 1998-2026 | 28 years, excellent coverage |
| **Temporal (Historical)** | Raw ICPSR file covers 1902-2016 | Not loaded into active DB |
| **Vote Results** | 89.7% | 10,908 of 12,156 measures |
| **Measure Text** | ~70% | Varies by source |
| **AI Summaries** | 28.4% | 3,457 measures |

### Vote Data Quality

| Metric | Status |
|--------|--------|
| Yes/No vote counts | Available for 89.6% of measures |
| Percentage calculations | Computed where raw counts exist |
| Pass/Fail determination | Available with threshold logic |
| Total votes cast | 520 million+ recorded |

### Missing Data

- **Pre-1998:** Limited to ICPSR historical data (less detailed)
- **Some special elections:** May lack complete vote counts
- **Ballot text:** Not always available for local measures
- **Campaign finance:** Not included (separate dataset)

---

## Export Capabilities

### Available Formats

#### CSV Export
- **File:** `scraper/data/exports/ballot_measures_YYYYMMDD.csv`
- **Size:** ~4.5 MB
- **Fields:** 25 columns (24 DB fields + 1 computed `summary_length`; see `scraper/scripts/export_data.py:21-46`)
- **Encoding:** UTF-8
- **Delimiter:** Comma

**Sample columns:**
```
measure_id,year,county,jurisdiction,title,summary_title,summary_text,
summary_length,passed,pass_fail,yes_votes,no_votes,total_votes,
percent_yes,percent_no,topic_primary,topic_secondary,measure_type,
data_source,has_summary,election_date,election_type,source_url,
ballot_question,description
```

#### JSON Export
- **File:** `scraper/data/exports/ballot_measures_YYYYMMDD.json`
- **Size:** ~6.1 MB
- **Structure:** Array of measure objects
- **Encoding:** UTF-8

**Sample structure:**
```json
[
  {
    "id": 12345,
    "measure_id": "PROP_36",
    "year": 2024,
    "county": "Statewide",
    "title": "Criminal Sentencing...",
    "yes_votes": 8234567,
    "no_votes": 3456789,
    "percent_yes": 70.5,
    "passed": true,
    "topic_primary": "Public Safety & Crime",
    "data_source": "CA_SOS"
  },
  ...
]
```

#### SQLite Database
- **File:** `scraper/data/ballot_measures.db`
- **Size:** 24.8 MB
- **Tool:** Any SQLite client

**Direct query access:**
```bash
sqlite3 data/ballot_measures.db "SELECT * FROM active_measures LIMIT 10"
```

### Export Commands

```bash
# Generate CSV export
make export-csv

# Custom export script
python scripts/export_data.py --format csv --year 2024 --county "Los Angeles"
```

> _Note: `make export-json` and `make export-all` do not exist as Makefile targets. Use `export_data.py` directly for JSON output._

---

## Data Documentation

### Codebook Elements

#### Variable Definitions

| Variable | Type | Description | Values |
|----------|------|-------------|--------|
| `measure_id` | String | Standardized identifier | PROP_*, MEASURE_* |
| `year` | Integer | Election year | 1998-2026 (active DB) |
| `county` | String | County or "Statewide" | 59 values |
| `passed` | Boolean | Pass/fail outcome | 0, 1, NULL |
| `percent_yes` | Float | Yes vote percentage | 0.0-100.0 |
| `topic_primary` | String | Primary topic category | 12 categories |
| `election_type` | String | Type of election | General, Primary, Special, etc. |

#### Topic Categories

| Category | Description | Measure Count |
|----------|-------------|---------------|
| Education | Schools, colleges, bonds | 2,421 |
| Taxes & Finance | Tax measures, revenue | 2,156 |
| Government & Elections | Elections, recalls | 1,089 |
| Public Safety & Crime | Police, criminal justice | 612 |
| Healthcare & Welfare | Healthcare programs | 498 |
| Environment | Parks, water, climate | 445 |
| Transportation | Transit, roads | 387 |
| Housing & Land Use | Zoning, housing | 601 |
| Business & Labor | Labor, business regs | 234 |
| Utilities & Energy | Utilities, energy | 189 |
| Civil Rights | Rights, discrimination | 112 |
| Other | Miscellaneous | 5,412 |

#### Pass Thresholds

| Measure Type | Threshold | Notes |
|--------------|-----------|-------|
| Simple majority | 50% + 1 | Most measures |
| School bonds (post-2000) | 55% | Prop 39 (2000) |
| Special taxes | 66.67% | 2/3 supermajority |
| Charter amendments | Varies | Usually 50% |

### Source Documentation

| Source | Authority | Coverage | Limitations |
|--------|-----------|----------|-------------|
| CA SOS | Official | Current measures | URL changes |
| CEDA | Academic | 1998-2024 | Annual release |
| ICPSR | Academic | 1902-2016 | Historical only |
| NCSL | National org | 2014-present | National focus |
| Ballotpedia | Encyclopedia | 2002-present | Rate limits |
| County ROVs | Official | Varies | Format varies |

---

## Research Considerations

### Strengths for Research

1. **Longitudinal Coverage**
   - 28 years of data in active database (1998-2026)
   - Raw ICPSR historical file (1902-2016) available but not loaded into active DB
   - Consistent schema across time periods
   - Annual data available 1998-present

2. **Geographic Granularity**
   - All 58 California counties
   - City/district level measures
   - Regional aggregation available

3. **Multiple Source Triangulation**
   - Cross-validation between sources
   - Authoritative data prioritized
   - Deduplication system

4. **Machine-Readable Format**
   - CSV for statistical software
   - JSON for programmatic access
   - SQLite for complex queries

### Limitations for Research

1. **Measure Text Completeness**
   - Full ballot language not always available
   - Historical measures may lack description
   - Summary text is AI-generated (flag available)

2. **Campaign Finance**
   - Not included in this dataset
   - Separate data source needed (FPPC)

3. **Demographic Data**
   - No precinct-level data
   - No voter demographics
   - Would need merge with census/voter file

4. **Causal Inference Challenges**
   - Selection into ballot placement
   - Measure text variation
   - Context effects (election timing, other measures)

---

## Integration with Other Data

### Potential Merges

| External Dataset | Join Key | Purpose |
|------------------|----------|---------|
| Census data | County FIPS | Demographics |
| ACS | County FIPS | Socioeconomic |
| FPPC (campaign finance) | Measure ID + Year | Spending data |
| Voter file | County | Turnout analysis |
| CES/CCES | State + Year | Survey responses |

### Example Merge (Python/pandas)

```python
import pandas as pd

# Load ballot measures
measures = pd.read_csv('ballot_measures.csv')

# Load census data
census = pd.read_csv('census_ca_counties.csv')

# Merge on county
merged = measures.merge(
    census,
    left_on='county',
    right_on='county_name',
    how='left'
)
```

---

## Analysis Examples

### Pass Rate by Topic

```python
import pandas as pd

df = pd.read_csv('ballot_measures.csv')
df_valid = df[df['passed'].notna()]

pass_rates = df_valid.groupby('topic_primary').agg({
    'passed': ['mean', 'count']
}).round(3)
pass_rates.columns = ['pass_rate', 'n']
print(pass_rates.sort_values('pass_rate', ascending=False))
```

### Temporal Trends

```python
yearly = df_valid.groupby('year').agg({
    'passed': 'mean',
    'id': 'count'
}).rename(columns={'id': 'n_measures'})

yearly.plot(y='passed', kind='line', title='Pass Rate Over Time')
```

### Geographic Patterns

```python
county_stats = df_valid.groupby('county').agg({
    'passed': ['mean', 'count'],
    'percent_yes': 'mean'
})
county_stats.columns = ['pass_rate', 'n_measures', 'avg_yes_pct']
county_stats = county_stats[county_stats['n_measures'] >= 10]
```

---

## Citation

When using this data in academic work, please cite:

```
California Ballot Measures Database (2024).
Retrieved from https://cal-vgp.igorgeyn.com
Data sources: California Secretary of State, CEDA, NCSL, ICPSR, Ballotpedia.
```

### Data Source Citations

- **CEDA:** California Elections Data Archive, Institute for Social Research, CSU Sacramento
- **ICPSR:** National Conference of State Legislatures Ballot Measures Database, ICPSR
- **NCSL:** National Conference of State Legislatures
- **CA SOS:** California Secretary of State Elections Division

---

## Researcher Checklist

### Before Analysis

- [ ] Review data dictionary and variable definitions
- [ ] Check coverage for your time period and geography
- [ ] Identify relevant topic categories
- [ ] Understand pass threshold rules
- [ ] Note AI-generated fields (has_summary, generated_title)

### During Analysis

- [ ] Handle missing data appropriately
- [ ] Consider source differences when comparing across time
- [ ] Account for threshold variations (50% vs 55% vs 66.67%)
- [ ] Validate findings against known results

### For Publication

- [ ] Cite data sources appropriately
- [ ] Document any data cleaning/transformation
- [ ] Note any limitations identified
- [ ] Consider sharing analysis code
