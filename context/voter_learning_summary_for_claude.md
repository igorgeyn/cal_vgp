# Dissertation Project Summary: Direct Democracy and Civic Engagement

## Project Overview

This dissertation research examines whether ballot measures genuinely enhance voter knowledge and political participation—the "educative hypothesis" of direct democracy. The core finding is that traditional econometric methods (Two-Way Fixed Effects) suggest positive civic engagement effects, but modern difference-in-differences estimators reveal **null effects** when using proper identification strategies.

---

## Research Question

**Do ballot measures serve an educative function by increasing civic engagement and political knowledge?**

The research challenges the conventional wisdom in political science (dating to Smith & Tolbert 2004, Tolbert & McNeal 2003) that exposure to direct democracy improves citizen competence.

---

## Data Sources

### 1. Cooperative Election Study (CES)
- **Coverage**: 2006-2020 cumulative file
- **Sample size**: 480,383 respondents after cleaning
- **Key variables**:
  - `news_interest_score`: Primary outcome (1-4 scale of news interest)
  - Political knowledge questions (objective knowledge measure)
  - Demographics: age, gender, education, party ID, ideology
  - State and year identifiers
- **Format**: Originally `.dta` (Stata), converted to `.rds` for R analysis

### 2. Ballot Measure Data

#### NCSL (National Conference of State Legislatures)
- **Coverage**: Historical ballot measures 1902-2020
- **File**: `ncslballotmeasures_ippsr_2016.csv` (pre-2016 data)
- **Variables**: State, year, measure type, topic classifications, vote percentages, pass/fail

#### Combined Ballot Measures Dataset
- **File**: `ballot_measures_combined.csv`
- **Coverage**: 1,547 ballot measures during 2006-2020
- **Topic classifications** (binary indicators):
  - `drug` (marijuana)
  - `gambling_lottery`
  - `abort` (abortion)
  - `tax_rev`, `ed_prek12`, `ed_higher`, `health`, `elections`, `criminal`, `environ`
- **Key derived variables**:
  - `has_morality_measure`: Marijuana, gambling, abortion, or same-sex marriage
  - `n_morality_measures`: Count of morality measures per state-year
  - `ballotdescrip`: Text description (used for keyword matching)
  - `pctyesvotes`: Vote percentage
  - `passed`: Binary pass/fail indicator

### 3. CEDA (California Elections Data Archive)
- **Coverage**: California county-level ballot measures 2014-2021
- **Format**: Excel files by year (`ceda_YYYY.xlsx`)
- **Location**: `/data/ceda/`
- **Key fields**: Date, county, measure text, fiscal measures
- **Used for**: County-level fiscal ballot measure analysis, turnout effects

### 4. L2 National Voter File (via UCLA Redivis)
- **Coverage**: Multi-state voter records, focus on California
- **Access**: Redivis API with UCLA institutional credentials
- **Key variables**:
  - `LALVOTERID`: Unique voter identifier
  - `state`, `County`
  - `Voters_Age`, `Parties_Description`
  - `elec_date`, `elec_type` (P=Primary, G=General)
  - `voted` (Y/N per election)
- **Used for**: Behavioral validation of survey-based findings, turnout analysis
- **Analytical concept**: Participation Gradient Score (PGS) - measures voting consistency across election types

---

## Treatment Definitions

### Primary Treatment: Morality Politics Measures
Following Mooney (2001), four issue types define "morality politics":

| Issue Type | N Measures (2006-2020) | % of Total |
|------------|------------------------|------------|
| Marijuana | 187 | 43% |
| Gambling | 142 | 33% |
| Abortion | 68 | 16% |
| Same-sex Marriage | 40 | 9% |

**Rationale**: These measures should theoretically maximize civic engagement effects because they:
1. Generate exceptional media coverage
2. Have personal moral relevance regardless of material stake
3. Scramble partisan alignments, forcing independent thinking
4. Attract substantial campaign resources

### Alternative Treatments
- `has_salient_economic`: Competitive tax measures or high-complexity education ballots
- `has_any_measure`: Any ballot measure (old treatment definition)
- Topic-specific: `did_marijuana`, `did_gambling`, `did_abortion`, `did_marriage`

### Control Group
**19 never-treated states** (no morality politics measures 2006-2020):
> AL, CT, DE, GA, HI, IA, IN, KS, KY, MN, NC, NH, NJ, NM, NY, PA, TN, TX, WI

This is a critical improvement over the original approach (only Delaware as control).

---

## Analytical Methods

### Traditional Estimators
- **Simple DiD**: Basic difference-in-differences
- **Two-Way Fixed Effects (TWFE)**: State and year fixed effects
- **TWFE + State Trends**: State-specific linear time trends

### Modern DiD Estimators (for staggered adoption)

| Estimator | Purpose | Key Feature |
|-----------|---------|-------------|
| **Sun-Abraham (2021)** | Cohort-specific effects | Separate treatment paths by adoption cohort |
| **Callaway-Sant'Anna (2021)** | Doubly-robust estimation | Combines outcome regression + propensity scores |
| **de Chaisemartin-d'Haultfoeuille (2020)** | Heterogeneous effects | Alternative bias correction |
| **Bacon Decomposition** | Diagnostic | Shows weight on clean vs. problematic comparisons |

### Key R Packages
- `fixest`: Primary econometric package for panel data
- `did`: Callaway-Sant'Anna implementation
- `data.table`: Large-scale data processing
- `modelsummary`: Publication-quality tables
- `redivis`: Voter file API access

---

## Key Findings

### The Methodological Divergence

| Method | Estimate | SE | Interpretation |
|--------|----------|-----|----------------|
| Simple DiD | -0.0185* | (0.0100) | Negative without FE |
| TWFE | 0.0288 | (0.0188) | Positive, marginally sig. |
| TWFE + Trends | 0.0269 | (0.0203) | Slightly attenuated |
| **Sun-Abraham** | **-0.0001** | — | Essentially zero |
| **Callaway-Sant'Anna** | **-0.0014** | (0.0133) | Null effect |

### Why the Divergence?
1. **Parallel trends violation**: Pre-treatment coefficient trend upward (p = 0.016)
2. **Heterogeneous treatment effects**: Early vs. late adopters differ systematically
3. **Bacon decomposition**: 58% of TWFE weight from problematic comparisons

### Topic-Specific Results

| Measure Type | Coefficient | SE | N Treated | Assessment |
|--------------|-------------|-----|-----------|------------|
| Abortion | 0.2234*** | (0.0602) | 359 | Implausible outlier |
| Marijuana | 0.0448** | (0.0184) | 3,943 | Only robust effect |
| Gambling | 0.0207 | (0.0269) | 6,408 | Null |
| Marriage | 0.0183 | (0.0221) | 1,287 | Null |

---

## Outcome Variables

### Self-Reported Measures (CES)
- `news_interest_score`: 1-4 scale ("How often do you follow government and public affairs?")
- Mean: ~3.2 across sample

### Objective Political Knowledge (CES)
- Political awareness index combining multiple indicators
- Correlation with news interest: r = 0.208

### Behavioral Measures (L2 Voter File)
- **Turnout rate**: Voted in general election / eligible voters
- **Participation Gradient Score (PGS)**: Ratio of primary to general election participation (captures political sophistication)
- **Subgroup turnout**: By age, party, etc.

---

## File Structure

```
policy_learning/
├── data/
│   ├── cleaned/
│   │   └── ballot_measures_combined.csv
│   ├── ceda/
│   │   └── ceda_YYYY.xlsx
│   └── [CES files]
├── output/
│   ├── tables/
│   ├── figures/
│   ├── exploratory/
│   └── data/
│       ├── analysis_ready_all_years.rds
│       ├── ballot_treatments_all_years.rds
│       └── all_results_all_years.rds
└── scripts/
    ├── 01_setup_all_years.R
    ├── 02_analysis_all_years.R
    ├── 05_extensions_all_years.R
    ├── l2_redivis_main.R
    └── mvp_iterative_analysis.R
```

---

## Key Variables Quick Reference

### Treatment Variables
| Variable | Type | Description |
|----------|------|-------------|
| `did_treatment` | Binary | State has morality measure × post-period |
| `did_intensity` | Continuous | Count of morality measures × post-period |
| `treatment_group` | Binary | State ever has morality measure |
| `has_morality_measure` | Binary | State-year has morality measure |
| `state_first_treat` | Integer | Year of first morality measure (or 10000 if never) |

### Outcome Variables
| Variable | Type | Source | Description |
|----------|------|--------|-------------|
| `news_interest_score` | 1-4 scale | CES | Primary outcome |
| `political_knowledge` | Index | CES | Objective knowledge |
| `turnout_rate` | Proportion | L2 | Behavioral turnout |
| `pgs_normalized` | Continuous | L2 | Participation gradient score |

### Controls
| Variable | Type | Description |
|----------|------|-------------|
| `female` | Binary | Gender |
| `college` | Binary | Has college degree |
| `age`, `age_squared` | Continuous | Age and polynomial |
| `republican`, `democrat`, `independent` | Binary | Party ID |
| `pid7`, `ideo5` | Ordinal | Detailed party/ideology |

---

## Extensions & Future Work

### Completed Extensions
- **Heterogeneous effects by demographics**: Education, party, age
- **Topic-specific analysis**: Separate estimates by measure type
- **Modern estimator comparison**: Full robustness to staggered adoption
- **Behavioral validation**: L2 voter file analysis confirms null effects

### In Development
- **Spatial spillover effects**: Geographic boundary discontinuities
- **Voter habit formation**: Long-term engagement patterns
- **Campaign finance data**: DIME database integration for donation behavior
- **50-state voter file analysis**: Scaling beyond pilot states

---

## Technical Notes for VGP Integration

### Potential Data Overlaps
Your VGP app scrapes California ballot measures. Key overlap areas:
- **CEDA data**: County-level California measures (fiscal focus)
- **State-level California measures**: From combined ballot dataset
- **Morality measure classifications**: Marijuana, gambling, abortion, marriage

### Useful Classifications Available
- Standardized topic indicators (binary flags)
- Vote percentages and pass/fail outcomes
- Measure type (initiative vs. referendum)
- Election date and cycle information

### API/Data Access
- L2 voter file available via Redivis (requires UCLA credentials)
- CES data publicly available via Harvard Dataverse
- NCSL ballot measure data publicly available

---

## Contact & Resources

**Primary dissertation paper**: `policylearning.pdf` (current draft with advisor approval)
**Main analysis scripts**: `01_setup_all_years.R`, `02_analysis_all_years.R`
**Voter file analysis**: `l2_redivis_main.R`

---



*Last updated: January 2026*
