# County Clerk Website Scraper - Implementation Plan

## Current Status

### Existing Data Sources
✅ **CEDA Archive**: 10,909 historical measures (1998-2024)
✅ **Ballotpedia**: 1,666 county measures (2002-2025) - all 58 CA counties
✅ **CA Secretary of State**: 16 statewide 2026 measures
✅ **UC Law SF**: 11 measures

**Total Database**: 12,602 active measures

### What We Have
- Comprehensive historical data (1998-2024)
- Good county-level coverage from Ballotpedia (2002-2025)
- Current 2026 statewide measures

### What We're Missing
- **Official upcoming 2026 county/local measures** from county clerk websites
- Real-time updates for newly announced local measures
- Official ballot language and voting results from primary sources

## Goal: County Clerk Website Scrapers

Build scrapers for official county clerk/registrar of voters websites to get:
1. **Upcoming 2026 local ballot measures** (cities, school districts, special districts)
2. **Official ballot language** and summaries
3. **Real-time election results** when available
4. **Verification** of Ballotpedia data accuracy

## Phase 1: Research & Prototype (Top 5 Counties)

Focus on the 5 most populous California counties:

### 1. Los Angeles County
- **Population**: ~10 million (26% of CA)
- **Registrar**: https://lavote.gov
- **Expected Structure**:
  - Election results page
  - Sample ballots
  - Measure text/analysis
- **Why First**: Largest county, likely best website infrastructure

### 2. San Diego County
- **Population**: ~3.3 million
- **Registrar**: https://sdvote.com
- **Expected Structure**:
  - Similar to LA - modern website
  - Sample ballots by precinct
  - Measure details

### 3. Orange County
- **Population**: ~3.2 million
- **Registrar**: https://ocvote.com
- **Expected Structure**:
  - Election information
  - Results archives
  - Ballot measures section

### 4. Riverside County
- **Population**: ~2.5 million
- **Registrar**: https://voteinfo.net
- **Expected Structure**:
  - Voter information
  - Sample ballots
  - Election results

### 5. San Bernardino County
- **Population**: ~2.2 million
- **Registrar**: https://sbcrov.com
- **Expected Structure**:
  - Election dates
  - Measure information
  - Results portal

**Combined**: These 5 counties represent **~50% of California's population**

## Technical Approach

### Step 1: Manual Reconnaissance
For each county website:
1. Navigate to elections/ballot measures section
2. Document URL patterns
3. Identify HTML structure (tables, divs, classes)
4. Check for structured data (JSON APIs, RSS feeds)
5. Note any anti-scraping measures (rate limits, CAPTCHAs)
6. Download sample HTML for offline testing

### Step 2: Create Unified Scraper Architecture
```python
class CountyClerkScraper:
    """Base class for county clerk website scrapers"""

    def get_upcoming_elections(self) -> List[Election]:
        """Get list of upcoming elections"""
        pass

    def get_ballot_measures(self, election_date: str) -> List[BallotMeasure]:
        """Get all measures for a specific election"""
        pass

    def get_measure_details(self, measure_id: str) -> BallotMeasure:
        """Get full details for a specific measure"""
        pass

    def get_election_results(self, election_date: str) -> Dict:
        """Get results for completed elections"""
        pass
```

### Step 3: Implement County-Specific Scrapers
```python
class LACountyScraper(CountyClerkScraper):
    """Los Angeles County Registrar scraper"""
    BASE_URL = "https://lavote.gov"
    # Implementation specific to LA County website structure

class SDCountyScraper(CountyClerkScraper):
    """San Diego County Registrar scraper"""
    BASE_URL = "https://sdvote.com"
    # Implementation specific to SD County website structure
```

### Step 4: Data Integration
- Parse measure data into `BallotMeasure` objects
- Normalize jurisdiction names (city vs county vs district)
- Use fingerprinting to deduplicate against existing data
- Prioritize official county data over Ballotpedia when conflicts arise

### Step 5: Validation & Testing
- Compare scraped data against Ballotpedia
- Verify measure IDs, titles, election dates
- Check for missing measures or jurisdictions
- Test on past elections before running on 2026 data

## Expected Challenges

### 1. Website Inconsistency
- **Problem**: Each county has different website structure
- **Solution**: Create flexible base class, implement county-specific parsers
- **Mitigation**: Start with 5 counties, identify common patterns

### 2. Dynamic Content
- **Problem**: JavaScript-rendered pages, AJAX requests
- **Solution**: Use Selenium/Playwright for JS-heavy sites, or reverse-engineer API calls
- **Tools**: requests + BeautifulSoup (preferred), Selenium (fallback)

### 3. Rate Limiting
- **Problem**: County sites may have rate limits or anti-bot measures
- **Solution**: Respectful scraping (1-2 second delays), user-agent headers
- **Caching**: Store intermediate results, avoid re-scraping

### 4. Data Availability
- **Problem**: 2026 measures may not be posted yet (elections months away)
- **Solution**:
  - Test on 2024/2025 historical data first
  - Set up monitoring to check for new measures periodically
  - May need to wait until closer to election dates

### 5. Jurisdiction Complexity
- **Problem**: Counties contain cities, school districts, special districts
- **Solution**:
  - Build jurisdiction hierarchy (county → city → district)
  - Track jurisdiction types separately
  - Research sample ballots to understand coverage

### 6. Data Quality
- **Problem**: Inconsistent measure numbering, missing data
- **Solution**:
  - Validate required fields before database insertion
  - Log warnings for incomplete data
  - Manual review of first batch

## Success Metrics

### Phase 1 (Research & Prototype)
- [ ] Successfully scrape 5 county websites
- [ ] Extract at least 50 historical measures (2024/2025)
- [ ] Achieve >90% match rate with Ballotpedia data
- [ ] Document HTML structure for each county
- [ ] Create reusable scraper architecture

### Phase 2 (Expansion)
- [ ] Add remaining 53 counties (prioritize by population)
- [ ] Automated weekly/monthly scraping schedule
- [ ] Alert system for new 2026 measures
- [ ] Data validation pipeline

### Phase 3 (Production)
- [ ] Real-time updates for election results
- [ ] Historical data backfill (pre-2002 if available)
- [ ] API for accessing scraped data
- [ ] Website integration with live county data

## Next Steps

1. **Manual Research** (1-2 hours)
   - Visit each of the 5 county registrar websites
   - Document current 2026 measures (if any)
   - Download sample HTML pages
   - Identify scraping feasibility

2. **Prototype LA County Scraper** (2-3 hours)
   - Build first working scraper
   - Test on 2024 election data
   - Validate against existing database

3. **Generalize Architecture** (1-2 hours)
   - Extract common patterns
   - Create base class
   - Add configuration system

4. **Expand to 5 Counties** (3-4 hours)
   - Implement remaining 4 scrapers
   - Run comparison tests
   - Document findings

5. **Integration** (1 hour)
   - Add to main scraping pipeline
   - Update database with new measures
   - Create scraper monitoring script

**Total Estimated Time**: 8-12 hours for Phase 1

## Alternative: Manual Entry

If websites are too inconsistent or don't have 2026 data yet:
- **Monitor** county clerk websites manually
- **Subscribe** to election mailing lists
- **Enter** new 2026 measures manually as they're announced
- **Revisit** automated scraping closer to election dates (May/November 2026)

## Risk Assessment

**Low Risk**:
- Historical data scraping (2024/2025)
- Public information, no authentication required
- Respectful scraping practices

**Medium Risk**:
- Website changes breaking scrapers
- Anti-bot measures blocking access
- Missing or incomplete data

**High Risk**:
- Legal concerns (unlikely - public data, robots.txt compliant)
- Time investment if websites too variable
- Maintenance burden (58 counties × website changes)

## Recommendation

**Proceed with Phase 1**:
1. Research the top 5 county websites manually
2. Assess 2026 data availability
3. Build 1-2 prototype scrapers
4. Evaluate feasibility before expanding

**If 2026 data not yet available**:
- Set up monitoring system (check monthly)
- Focus on historical data validation
- Prioritize website UI improvements using existing data
- Return to county scraping in March-April 2026

---

**Created**: 2026-01-09
**Status**: Planning Phase
**Next Action**: Manual reconnaissance of top 5 county clerk websites
