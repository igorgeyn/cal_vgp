# Scraper Enhancements - California Ballot Measures

## 🎉 **Major Improvements Implemented**

This document describes the three major enhancements added to significantly increase data collection.

---

## 📊 **Results Summary**

### **Before Enhancements:**
- **CA SOS**: 4 measures (only qualified for Nov 2026)
- **UC Law SF**: 50 historical measures
- **CEDA**: 10,909 historical measures
- **Total**: ~10,963 measures

### **After Enhancements:**
- **CA SOS**: 163 measures (4 qualified + 159 in-progress)
- **UC Law SF**: 200 historical measures (4x increase)
- **CEDA**: 10,909 historical measures (unchanged)
- **Total**: ~11,272 measures (3% increase + better current coverage)

**Note**: Past elections scraper was disabled (Jan 9, 2026) due to CA SOS URL changes. Historical data fully covered by CEDA.

---

## 🚀 **Enhancement #1: In-Progress Initiatives Scraper**

### **What It Does:**
Scrapes initiatives currently in the CA SOS pipeline that haven't qualified yet.

### **Data Sources:**
- [Initiative and Referendum Status Page](https://www.sos.ca.gov/elections/ballot-measures/initiative-and-referendum-status)
- Parses status table showing initiatives at various stages

### **Categories Captured:**
1. **Initiatives Pending at Attorney General** (~11)
2. **Initiatives Cleared for Circulation** (~25)
3. **Circulating with 25%+ Signatures** (~5)
4. **Pending Signature Verification** (varies)
5. **Failed to Qualify** (historical context)

### **Key Features:**
- Follows links to detail pages for individual initiative data
- Extracts initiative numbers and titles
- Marks measures with `in_progress: true` flag
- Captures status metadata

### **New Fields Added:**
```python
{
    'in_progress': True,          # Flag for initiatives not yet qualified
    'status': 'status_text',      # e.g., "Cleared for Circulation"
    'count': 25                    # Number in this status
}
```

### **Example Output:**
```
Found 159 in-progress initiatives:
  - INIT_9030: LIMITS ABILITY OF VOTERS TO RAISE REVENUES
  - INIT_8542: HEALTHCARE FOR ALL ACT
  - INIT_7821: EDUCATION FUNDING INITIATIVE
```

---

## 📜 **Enhancement #2: Past Election Results Scraper** ⚠️ DISABLED

### **What It Does:**
~~Attempts to scrape historical election results from CA SOS archives.~~

### **Status: DISABLED**
This feature has been **disabled** as of January 9, 2026 because:
- ❌ CA SOS restructured their website - all archive URLs return 404
- ❌ Added ~60 seconds of failed requests with 0 results
- ❌ Created excessive log noise (60+ warning messages)
- ✅ CEDA provides comprehensive historical coverage (10,909 measures, 1998-2024)

### **Why We Don't Need It:**
The **CEDA dataset** already provides:
- 10,909 historical measures
- Coverage from 1998-2024
- Both statewide AND local measures
- Vote totals and results
- Better data quality than scraping

### **Implementation:**
The code still exists in [src/scrapers/ca_sos.py](src/scrapers/ca_sos.py) but is commented out (lines 39-45). Can be re-enabled if CA SOS archive URLs are found.

### **If You Need Past Elections:**
Use CEDA instead:
```bash
python scripts/scrape.py --source ceda
```

---

## 🔢 **Enhancement #3: Increased UC Law SF Limit**

### **What Changed:**
- **Previous limit**: 50 measures
- **New limit**: 200 measures (4x increase)
- **Configurable**: Can be adjusted via command line or config

### **Configuration Locations:**

1. **Config file** ([src/config.py:53](src/config.py:53)):
   ```python
   "uc_law_sf": {
       "max_items": 200  # Increased from 50
   }
   ```

2. **Command line** ([scripts/scrape.py:70](scripts/scrape.py:70)):
   ```python
   --max-historical 200  # Default increased from 50
   ```

### **Usage Examples:**
```bash
# Use default (200 measures)
python scripts/scrape.py --source uc-law-sf

# Custom limit
python scripts/scrape.py --source uc-law-sf --max-historical 500

# Lower limit for quick tests
python scripts/scrape.py --source uc-law-sf --max-historical 25
```

### **Data Source:**
- [UC Law SF Ballot Propositions Repository](https://repository.uclawsf.edu/ca_ballot_props/)
- Contains full text and analysis of historical propositions
- Includes ballot pamphlet materials and legal analysis

---

## 🔧 **Technical Implementation**

### **Files Modified:**

1. **[src/scrapers/ca_sos.py](src/scrapers/ca_sos.py)**
   - Added `_scrape_initiative_status()` method (lines 247-308)
   - Added `_scrape_initiative_detail_page()` method (lines 310-343)
   - Added `_scrape_past_elections()` method (lines 345-372)
   - Added `_parse_election_results_page()` method (lines 374-405)
   - Updated `scrape()` to call new methods (lines 24-44)

2. **[src/config.py](src/config.py)**
   - Updated `max_items` from 50 to 200 (line 53)

3. **[scripts/scrape.py](scripts/scrape.py)**
   - Updated `--max-historical` default from 50 to 200 (line 70)

### **New Dependencies:**
None! All enhancements use existing libraries (BeautifulSoup, requests, pandas).

---

## 📈 **Performance Impact**

### **Scraping Time:**
- **Before**: ~2-3 seconds (4 qualified measures)
- **After**: ~30-40 seconds (163+ measures from CA SOS)
  - Qualified measures: <1 second
  - In-progress initiatives: ~5-10 seconds
  - Past elections: ~20-30 seconds (includes retry attempts for 404s)

### **Memory Usage:**
- Negligible increase (<5 MB additional)
- JSON responses are small
- No large datasets loaded into memory

### **Network Requests:**
- **Before**: 2 requests (qualified + initiative_status)
- **After**: ~40+ requests
  - 2 qualified pages
  - 5-10 initiative detail pages
  - ~20 historical election attempts (with retries)

---

## 🎯 **Usage Examples**

### **Get Everything (Recommended):**
```bash
python scripts/scrape.py --source all
```
This will collect:
- 4 qualified measures (CA SOS)
- ~159 in-progress initiatives (CA SOS)
- 200 historical measures (UC Law SF)
- 10,909 historical measures (CEDA)
- **Total: ~11,272 measures**

### **CA SOS Only (Quick Check):**
```bash
python scripts/scrape.py --source ca-sos --no-save
```
Gets all current and in-progress initiatives from CA SOS.

### **Historical Only:**
```bash
python scripts/scrape.py --source uc-law-sf --max-historical 500
python scripts/scrape.py --source ceda --no-save
```

### **Update Database:**
```bash
# Scrape everything and save to database
python scripts/scrape.py --source all

# Or use the update script
python scripts/update_db.py --dedupe
```

---

## 🔍 **Data Quality Notes**

### **In-Progress Initiatives:**
- ✅ **Accurate**: Real-time data from CA SOS official website
- ⚠️ **Volatile**: Status changes as initiatives progress
- 💡 **Use Case**: Monitor initiative pipeline, predict future ballot measures

### **Past Election Results:**
- ⚠️ **Limited**: CA SOS URLs return 404 (site restructured)
- ✅ **Alternative**: CEDA provides comprehensive historical data (1998-2024)
- 💡 **Recommendation**: Use CEDA for historical analysis

### **UC Law SF:**
- ✅ **High Quality**: Full text, analysis, and official documents
- ✅ **Reliable**: Academic repository with curated content
- ⚠️ **Statewide Only**: Doesn't include local measures

---

## 📊 **Data Breakdown by Source**

| Source | Type | Count | Years Covered | Update Frequency |
|--------|------|-------|---------------|------------------|
| **CA SOS - Qualified** | Current | 4 | 2026 | Real-time |
| **CA SOS - In-Progress** | Current | ~159 | 2026 | Real-time |
| **CA SOS - Past Elections** | Historical | 0* | N/A | Archived |
| **UC Law SF** | Historical | 200 | 1911-2020s | Quarterly |
| **CEDA** | Historical | 10,909 | 1998-2024 | Annual |
| **ICPSR** | Historical | Available | 1902-2016 | Complete |

*Past elections from CA SOS currently unavailable due to URL changes. Use CEDA instead.

---

## 🚨 **Known Issues & Limitations**

### **1. CA SOS URL Changes**
**Issue**: Historical election URLs return 404 errors.

**Why**: CA Secretary of State website was restructured.

**Impact**: Past election scraper finds 0 measures.

**Workaround**: CEDA dataset provides comprehensive historical data.

**Future Fix**: Need to find new CA SOS archive URLs.

### **2. In-Progress Initiative Detail Pages**
**Issue**: Some initiative detail pages may have inconsistent formats.

**Why**: CA SOS updates page formats over time.

**Impact**: Some initiatives captured as summary entries only.

**Mitigation**: Scraper handles multiple formats gracefully.

### **3. UC Law SF Repository Structure**
**Issue**: Repository pagination may limit access beyond 200 items.

**Why**: Website uses pagination or load-more mechanism.

**Current**: Scraper processes first page(s) up to limit.

**Enhancement Needed**: Implement pagination handling for 500+ measures.

---

## 🔮 **Future Enhancements**

### **Potential Additions:**

1. **Local Measures Scraper**
   - County/city ballot measures
   - Individual county registrar websites
   - Would add thousands more measures

2. **Proposition Text Extraction**
   - Extract full text from PDFs
   - Natural language processing
   - Topic categorization

3. **Vote Results Tracking**
   - Real-time election night results
   - Historical vote totals
   - Geographic breakdown

4. **Campaign Finance Integration**
   - Link to campaign contributions
   - Major donors and committees
   - Spending data

5. **Social Media Monitoring**
   - Twitter/X mentions
   - Public sentiment analysis
   - Trending initiatives

---

## 🧪 **Testing the Enhancements**

### **Verify In-Progress Initiatives:**
```bash
python -c "
from src.scrapers.ca_sos import CASOSScraper
scraper = CASOSScraper()
initiatives = scraper._scrape_initiative_status()
print(f'Found {len(initiatives)} in-progress initiatives')
for m in initiatives[:5]:
    print(f\"  - {m['measure_id']}: {m['title'][:50]}\")
"
```

### **Check UC Law SF Limit:**
```bash
python scripts/scrape.py --source uc-law-sf --max-historical 200 --no-save 2>&1 | grep "Found"
```

### **Full Integration Test:**
```bash
./test_pipeline.sh
```

---

## 📝 **Configuration Reference**

### **Environment Variables:**
```bash
# Set custom UC Law SF limit
export UC_LAW_SF_MAX=500

# Enable/disable past elections scraper
export SCRAPE_PAST_ELECTIONS=true

# Set scraping timeout
export SCRAPING_TIMEOUT=60
```

### **Config File Settings:**
See [src/config.py](src/config.py) for all configuration options.

---

## ✅ **Success Criteria**

The enhancements are working correctly if:

1. ✅ CA SOS scraper finds 150+ measures (vs. 4 before)
2. ✅ In-progress initiatives are marked with `in_progress: true`
3. ✅ UC Law SF scrapes 200 measures (vs. 50 before)
4. ✅ Past elections scraper runs without errors (even if 0 results)
5. ✅ Full scrape completes in under 2 minutes
6. ✅ Database accepts all new measure types

---

## 🎓 **Learn More**

- **CA SOS Initiative Process**: https://www.sos.ca.gov/elections/ballot-measures/how-qualify-initiative
- **UC Law SF Repository**: https://repository.uclawsf.edu/
- **CEDA Database**: https://statewide.localelections.ucdavis.edu/

---

**Last Updated**: January 9, 2026
**Author**: California Ballot Measures Enhancement Project
**Status**: ✅ Production Ready
