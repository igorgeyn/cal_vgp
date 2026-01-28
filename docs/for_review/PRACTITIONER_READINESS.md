# Practitioner Readiness

## Overview

This document assesses how well the California Ballot Measures Database serves practitioners: journalists, policy analysts, civic organizations, campaign strategists, and government officials who need to access and use ballot measure data.

---

## Quick Start Guide

### For Journalists

**Finding Historical Context:**
1. Visit [cal-vgp.igorgeyn.com](https://cal-vgp.igorgeyn.com)
2. Search for topic (e.g., "housing bonds")
3. Filter by county and year range
4. Click measure for full details and sources

**Example Query:** "What's the historical pass rate for tax measures in Los Angeles County?"
- Filter: County = Los Angeles, Topic = Taxes & Finance
- Review results showing 67 measures, 42% pass rate

### For Policy Analysts

**Comparing Similar Measures:**
1. Find measure of interest
2. Click the measure card to open detail modal
3. Scroll to "Similar Measures" (AI-powered)
4. Export data for deeper analysis

**Data Export:**
- Download CSV from `/scraper/data/exports/`
- Contains 25 fields (24 DB fields + 1 computed `summary_length`; see `scraper/scripts/export_data.py:21-46`)
- Open in Excel, R, Python, Stata

### For Civic Organizations

**Tracking Your Issues:**
1. Use topic filters (12 categories)
2. Set county to your region
3. Use AI chat: "What education measures are on the 2026 ballot?"
4. Bookmark relevant measures

---

## Data Access Methods

### Method 1: Website Interface (Easiest)

**URL:** [cal-vgp.igorgeyn.com](https://cal-vgp.igorgeyn.com)

**Features:**
- Search across 12,156 measures
- Filter by status, year, county, topic
- View full measure details
- AI chat for questions
- Click any measure card for full details

**Best For:** Quick lookups, research starting point

### Method 2: CSV/JSON Download (Analysis)

**Location:** `scraper/data/exports/`

**Files:**
- `ballot_measures_YYYYMMDD.csv` - Excel-compatible
- `ballot_measures_YYYYMMDD.json` - For programming

**How to Get:**
1. Clone repository: `git clone [repo-url]`
2. Navigate to `scraper/data/exports/`
3. Open in Excel, Google Sheets, or analysis tool

**Best For:** Statistical analysis, large-scale queries

### Method 3: Direct Database Query (Advanced)

**File:** `scraper/data/ballot_measures.db`

**Tool:** Any SQLite client (DB Browser, DBeaver, command line)

**Example Query:**
```sql
SELECT county, year, COUNT(*) as measures,
       ROUND(100.0 * SUM(passed) / COUNT(*), 1) as pass_rate
FROM active_measures
WHERE topic_primary = 'Education'
GROUP BY county, year
ORDER BY year DESC, measures DESC;
```

**Best For:** Complex queries, custom aggregations

### Method 4: API (Developers)

**Local API:** Run FastAPI server

```bash
cd scraper
make api
# Server at http://localhost:8000
```

**Endpoints:**
- `GET /api/measures?county=Los%20Angeles&year=2024`
- `GET /api/stats`
- `POST /api/search` (full-text)

**Best For:** Integration with other systems

> **Note:** Historical context endpoints (`/api/historical/*`) return HTTP 501 because the underlying modules are not yet implemented. Core endpoints work normally.

---

## Use Case Examples

### Journalist: Writing About 2024 Election

**Task:** Write story about Proposition 36 (criminal sentencing)

**Steps:**
1. Search "Proposition 36" on website
2. View details: 70.5% yes, passed
3. Use AI chat: "What similar criminal justice measures have passed in California?"
4. Find historical context (3 Strikes, Prop 47, etc.)
5. Note sources for attribution

**Output:**
```
Proposition 36 passed with 70.5% support (8.2M yes votes),
joining a long history of California voters supporting
tougher criminal sentencing measures. Similar measures
have passed at rates of 78% historically.
```

### Policy Analyst: School Bond Trends

**Task:** Analyze school bond success rates over time

**Steps:**
1. Export CSV
2. Filter: `topic_primary = "Education"`
3. Further filter: title contains "bond"
4. Calculate pass rates by year
5. Note 55% threshold (Prop 39)

**Sample Analysis:**
```python
import pandas as pd
df = pd.read_csv('ballot_measures.csv')
school_bonds = df[(df['topic_primary'] == 'Education') &
                  (df['title'].str.contains('bond', case=False, na=False))]
school_bonds.groupby('year')['passed'].agg(['mean', 'count'])
```

### Civic Organization: Tracking Housing Measures

**Task:** Monitor housing-related measures across Bay Area

**Steps:**
1. Filter: Topic = "Housing & Land Use"
2. Filter: Counties = Bay Area (9 counties)
3. Filter: Year = 2024-2026
4. Set up watchlist

**Finding:**
- 23 housing measures in Bay Area (2024)
- 14 passed (61%)
- 3 pending for 2026

### Campaign Strategist: Predicting Outcomes

**Task:** Estimate likelihood of new tax measure passing

**Steps:**
1. Export data for target county
2. Filter to similar measure types
3. Calculate historical pass rate
4. Identify threshold (66.67% for special tax)

**Analysis:**
```
County: Sacramento
Measure Type: Special Tax (Public Safety)
Historical Pass Rate: 54% (n=23)
Threshold Needed: 66.67%
Assessment: Challenging - only 3 of 23 similar measures passed
```

---

## Data Quality Indicators

### Reliability by Source

| Source | Reliability | Best For |
|--------|-------------|----------|
| CA Secretary of State | Highest | Official current data |
| County ROVs | Highest | Local vote counts |
| CEDA | Very High | Academic research |
| NCSL | High | National comparison |
| Ballotpedia | Good | Quick reference |

### Fields Most Reliable

| Field | Reliability | Notes |
|-------|-------------|-------|
| `year` | 100% | Always accurate |
| `county` | 100% | Standardized |
| `passed` | 99% | From official sources |
| `yes_votes`, `no_votes` | 95% | Some historical gaps |
| `topic_primary` | 90% | Some miscategorization |
| `summary_text` | AI-generated | Flag with `has_summary` |

### Caveats

1. **AI Summaries:** Marked with `has_summary=1`. Review for accuracy.
2. **Generated Titles:** Field `generated_title` is AI-simplified.
3. **Historical Data:** Pre-1998 measures have less detail.
4. **Pending Measures:** 2025-2026 measures may change.

---

## Common Questions

### How Current is the Data?

- **Statewide measures:** Updated weekly during election season
- **County measures:** Updated monthly
- **Historical data:** Complete through 2024
- **Last full update:** Check `scraper_runs` table

### Can I Use This Data Commercially?

- Data from government sources is public domain
- Ballotpedia data should be attributed
- Check individual source terms
- Recommend: "Data compiled from California Secretary of State, CEDA, and other public sources"

### How Do I Get Updates?

**Option 1:** Check website periodically

**Option 2:** Clone repo and run scrapers
```bash
cd scraper
make scrape
make website
```

**Option 3:** Watch GitHub repo for releases

### What's Missing?

- Campaign finance data (see FPPC)
- Precinct-level results (see county ROVs)
- Voter demographics (see census)
- Full ballot text (varies by measure)

---

## Integration Examples

### Excel/Google Sheets

1. Download `ballot_measures.csv`
2. Import into spreadsheet
3. Use pivot tables for aggregation
4. Create charts from data

**Pivot Table Example:**
- Rows: Year
- Columns: Passed (Yes/No)
- Values: Count of measures
- Filter: County = Your county

### Tableau/Power BI

1. Connect to CSV or SQLite
2. Create relationships (Year, County)
3. Build dashboards
4. Filter and drill down

**Recommended Visualizations:**
- Map: Pass rate by county
- Line chart: Measures over time
- Bar chart: Topic distribution
- Scatter: Yes% vs Total votes

### Python/R

**Python Example:**
```python
import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_csv('ballot_measures.csv')

# Pass rate by topic
topic_rates = df[df['passed'].notna()].groupby('topic_primary')['passed'].mean()
topic_rates.sort_values().plot(kind='barh', title='Pass Rate by Topic')
plt.xlabel('Pass Rate')
plt.tight_layout()
plt.savefig('topic_pass_rates.png')
```

**R Example:**
```r
library(tidyverse)

df <- read_csv('ballot_measures.csv')

df %>%
  filter(!is.na(passed)) %>%
  group_by(topic_primary) %>%
  summarize(
    pass_rate = mean(passed),
    n = n()
  ) %>%
  arrange(desc(pass_rate))
```

---

## Support & Updates

### Getting Help

1. **Website issues:** Open GitHub issue
2. **Data questions:** Check documentation first
3. **Feature requests:** GitHub discussions

### Staying Updated

- **GitHub:** Watch repository for updates
- **Website:** Check "About" section for changelog
- **Data exports:** Dated filenames show freshness

### Contributing

- Report data errors via GitHub issues
- Suggest new data sources
- Contribute county scrapers (Python)
