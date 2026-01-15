# VGP Historical Data Integration Spec

## Source File
`ballot_measures_combined.csv` — merged NCSL + Ballotpedia data, 1902–2020, all US states.

---

## Column Reference

### Core Fields
| Column | Type | Notes |
|--------|------|-------|
| `st` | text | 2-letter state abbreviation (use this, not `state`) |
| `year` | int | Election year |
| `ballotname` | text | Measure identifier (e.g., "Prop 64") |
| `ballotdescrip` | text | Full measure description |
| `pctyesvotes` | text/numeric | **CLEANING REQUIRED**: may contain `%` signs. Use `CAST(REPLACE(pctyesvotes, '%', '') AS REAL)` |
| `passed` | int/bool | 1 = passed, 0 = failed. Coerce to boolean. |
| `type` | text | "Initiative", "Referendum", "Legislative Referendum", etc. |
| `electiontype` | text | "General", "Primary", "Special" |

### Pre-Coded Topic Flags (binary 0/1)
| Column | User-Facing Label |
|--------|-------------------|
| `drug` | Marijuana/Cannabis |
| `gambling_lottery` | Gambling |
| `abort` | Abortion |
| `tax_rev` | Tax/Fiscal |
| `ed_prek12` | Education (K-12) |
| `ed_higher` | Education (Higher Ed) |
| `health` | Healthcare |
| `elections` | Election Reform |
| `criminal` | Criminal Justice |
| `environ` | Environment |

### Derived Topics (NOT native columns)
**Same-Sex Marriage** — must be derived via text search:
```sql
-- SQL version
CASE WHEN
  (LOWER(ballotdescrip) LIKE '%marriage%' OR
   LOWER(ballotdescrip) LIKE '%civil union%' OR
   LOWER(ballotdescrip) LIKE '%domestic partner%')
  AND
  (LOWER(ballotdescrip) LIKE '%same%sex%' OR
   LOWER(ballotdescrip) LIKE '%gay%' OR
   LOWER(ballotdescrip) LIKE '%homosexual%')
THEN 1 ELSE 0 END AS is_marriage
```

---

## Data Cleaning Checklist

1. **Filter to California**: `WHERE st = 'CA'`
2. **Clean vote percentages**: Strip `%` symbol, cast to numeric
3. **Handle multi-topic measures**: A single measure can have multiple flags = 1 (e.g., marijuana tax measure has both `drug = 1` AND `tax_rev = 1`). Display multiple tags.
4. **Derive marriage measures**: Use text search above
5. **Compute margin**: `pct_yes - 50` for competitiveness display

---

## Recommended Computed Fields

```sql
-- Add these during import
margin AS (CAST(REPLACE(pctyesvotes, '%', '') AS REAL) - 50),
is_close AS (ABS(margin) < 10),
is_very_close AS (ABS(margin) < 5),
is_initiative AS (type LIKE '%Initiative%'),
is_referendum AS (type LIKE '%Referendum%')
```

---

## Feature Implementation Notes

### Feature 1: Historical Context Panel
Query pattern:
```sql
SELECT
  COUNT(*) as total_measures,
  MIN(year) as first_year,
  AVG(CASE WHEN passed = 1 THEN 1.0 ELSE 0.0 END) as pass_rate,
  AVG(CAST(REPLACE(pctyesvotes, '%', '') AS REAL)) as avg_yes_pct
FROM measures
WHERE st = 'CA'
  AND [topic_flag] = 1
```

For "most recent similar measure":
```sql
SELECT ballotname, year, passed, pctyesvotes
FROM measures
WHERE st = 'CA' AND [topic_flag] = 1
ORDER BY year DESC
LIMIT 1
```

### Feature 2: Topic Tags
- Allow multiple tags per measure (don't force single classification)
- Consider a priority order for primary display: Marijuana > Gambling > Abortion > Marriage > Tax > Education > Health > Elections > Criminal > Environment
- Gray out or hide filter options with <3 historical measures in CA

---

## Schema Recommendation

```sql
CREATE TABLE ca_historical_measures (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ballot_name TEXT,
  year INTEGER NOT NULL,
  description TEXT,
  pct_yes REAL,
  passed BOOLEAN,
  measure_type TEXT,
  election_type TEXT,

  -- Topic flags
  is_marijuana BOOLEAN DEFAULT FALSE,
  is_gambling BOOLEAN DEFAULT FALSE,
  is_abortion BOOLEAN DEFAULT FALSE,
  is_marriage BOOLEAN DEFAULT FALSE,
  is_tax BOOLEAN DEFAULT FALSE,
  is_education BOOLEAN DEFAULT FALSE,
  is_health BOOLEAN DEFAULT FALSE,
  is_elections BOOLEAN DEFAULT FALSE,
  is_criminal BOOLEAN DEFAULT FALSE,
  is_environment BOOLEAN DEFAULT FALSE,

  -- Computed
  margin REAL,
  is_close BOOLEAN,

  -- Future expansion (nullable)
  campaign_spending REAL,

  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_year ON ca_historical_measures(year);
CREATE INDEX idx_marijuana ON ca_historical_measures(is_marijuana);
CREATE INDEX idx_gambling ON ca_historical_measures(is_gambling);
-- etc for other topics
```

---

## Things to AVOID

1. **No engagement/turnout predictions** — Research shows apparent effects disappear under rigorous causal methods. Don't imply "this measure type boosts civic engagement."

2. **No pass probability predictions** — Historical pass rates are descriptive only. "65% of similar measures passed" ≠ "65% chance this passes."

3. **Don't treat correlations as causal** — If you add any "research insights," caveat heavily.

---

## California-Specific Notes

- CA has dramatically more measures than most states (often 10-20+ per election cycle)
- Pass rates may differ significantly from national averages
- Marijuana measures concentrated post-2010
- Same-sex marriage measures concentrated 2000-2012
- Many "hybrid" measures (e.g., marijuana + tax revenue)

---

## Sample Import Query

```sql
INSERT INTO ca_historical_measures (
  ballot_name, year, description, pct_yes, passed, measure_type, election_type,
  is_marijuana, is_gambling, is_abortion, is_marriage, is_tax, is_education,
  is_health, is_elections, is_criminal, is_environment, margin, is_close
)
SELECT
  ballotname,
  year,
  ballotdescrip,
  CAST(REPLACE(pctyesvotes, '%', '') AS REAL) as pct_yes,
  CASE WHEN passed = 1 THEN TRUE ELSE FALSE END,
  type,
  electiontype,
  CASE WHEN drug = 1 THEN TRUE ELSE FALSE END,
  CASE WHEN gambling_lottery = 1 THEN TRUE ELSE FALSE END,
  CASE WHEN abort = 1 THEN TRUE ELSE FALSE END,
  CASE WHEN (ballotdescrip LIKE '%marriage%' OR ballotdescrip LIKE '%civil union%')
        AND (ballotdescrip LIKE '%same%sex%' OR ballotdescrip LIKE '%gay%')
       THEN TRUE ELSE FALSE END,
  CASE WHEN tax_rev = 1 THEN TRUE ELSE FALSE END,
  CASE WHEN ed_prek12 = 1 OR ed_higher = 1 THEN TRUE ELSE FALSE END,
  CASE WHEN health = 1 THEN TRUE ELSE FALSE END,
  CASE WHEN elections = 1 THEN TRUE ELSE FALSE END,
  CASE WHEN criminal = 1 THEN TRUE ELSE FALSE END,
  CASE WHEN environ = 1 THEN TRUE ELSE FALSE END,
  CAST(REPLACE(pctyesvotes, '%', '') AS REAL) - 50,
  ABS(CAST(REPLACE(pctyesvotes, '%', '') AS REAL) - 50) < 10
FROM ballot_measures_combined
WHERE st = 'CA'
  AND year IS NOT NULL
  AND pctyesvotes IS NOT NULL;
```

---

## Questions for Product Decisions

1. How far back should historical context go? (1902? 1970? 2000?)
2. Should users see national comparisons or CA-only?
3. Display multiple topic tags or pick primary?
4. Include measure descriptions in search/display?
