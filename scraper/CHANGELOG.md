# Changelog - California Ballot Measures Scraper

## [2.1.0] - 2026-01-09

### 🚀 Added
- **In-progress initiatives scraper**: Now captures ~159 initiatives in various stages (pending AG, cleared for circulation, etc.) from CA SOS
- **Increased UC Law SF limit**: From 50 to 200 measures (4x increase)
- **CSV support for CEDA parser**: Now parses `ceda_combined.csv` containing 10,909 historical measures
- **Comprehensive test suite**: 48 tests covering models, database, parsers, and utilities

### 🔧 Fixed
- **CEDA parser**: Now looks in `data/raw/` directory first (where files actually exist)
- **ICPSR parser**: Updated to check `data/raw/` for CSV file
- **NCSL parser**: Updated file path priority
- **Parser configuration**: Fixed `HISTORICAL_DATA` paths in config.py

### ♻️ Refactored
- **Eliminated code duplication**: Extracted `normalize_measure_data()` to shared `src/database/utils.py`
  - Removed 200+ lines of duplicate code from 3 scripts
  - All scripts now use single shared function
- **Cleaned up codebase**: Removed 12 one-off migration/fix scripts (~88 KB)
- **Organized data files**: Archived redundant CSV/JSON exports, deleted old backups (68.5 MB)

### ⚠️ Removed
- **Past elections scraper**: Disabled due to CA SOS URL changes (all 404s)
  - Saves ~60 seconds of failed requests
  - Eliminates 60+ warning messages in logs
  - Historical data fully covered by CEDA (10,909 measures, 1998-2024)

### 📊 Performance
- **CA SOS scraping**: Reduced from ~75s to ~7.5s (10x faster)
- **Total measures collected**: Increased from 10,963 to 11,272 (3% increase)
- **Data sources breakdown**:
  - CA SOS: 163 measures (4 qualified + 159 in-progress)
  - UC Law SF: 200 historical measures
  - CEDA: 10,909 historical measures

### 📝 Documentation
- Added `ENHANCEMENTS.md`: Comprehensive documentation of all enhancements
- Added `TESTING.md`: Complete testing guide with commands
- Added `test_pipeline.sh`: Automated test script
- Updated `README.md`: Reflected new capabilities

### 🧪 Testing
- Created 5 test files with 48 test cases:
  - `test_models.py`: 10 tests for BallotMeasure model
  - `test_database.py`: 12 tests for database operations
  - `test_utils.py`: 9 tests for utility functions
  - `test_parsers.py`: 9 tests for data parsers
  - `test_deduplication.py`: 8 tests for deduplication logic
- Added `pytest.ini` configuration
- All tests passing ✅

---

## [2.0.0] - 2025-08-08

### Major Reorganization
- Restructured codebase with proper `src/` package structure
- Separated scrapers, parsers, database, and website modules
- Migrated from flat structure to organized hierarchy
- Created comprehensive Makefile for common operations

### Features
- Modern responsive website generation
- FastAPI REST API server
- SQLite database with deduplication
- Multiple data sources (CA SOS, UC Law SF, CEDA)
- Summary generation (optional)

---

## [1.0.0] - 2025-06-26

### Initial Release
- Basic web scraping for CA SOS ballot measures
- Simple CSV export functionality
- Manual data collection

---

## Version Comparison

| Version | Measures | Sources | Speed | Tests |
|---------|----------|---------|-------|-------|
| 1.0.0 | ~100 | 1 | ~10s | 0 |
| 2.0.0 | 10,963 | 3 | ~120s | 0 |
| **2.1.0** | **11,272** | **3** | **~15s** | **48** |

---

## Migration Guide

### From 2.0.0 to 2.1.0

No breaking changes! Simply pull the latest code and run:

```bash
# Update dependencies (only if new ones added)
pip install -r requirements.txt

# Run database migration (if needed)
python scripts/update_db.py --dedupe

# Test everything works
./test_pipeline.sh

# Scrape with new enhancements
python scripts/scrape.py --source all
```

### Key Behavioral Changes

1. **CA SOS scraper now faster**: No more past elections attempts (404s)
2. **More in-progress initiatives**: Now captures ~159 initiatives in pipeline
3. **UC Law SF limit increased**: Gets 200 measures instead of 50
4. **CEDA parser improved**: Handles CSV files directly

---

## Upcoming Features

### Planned for 2.2.0
- Local measures scraper (county/city level)
- Proposition text extraction from PDFs
- Vote results real-time tracking
- Campaign finance integration
- Social media monitoring

### Under Consideration
- Natural language processing for topics
- Geographic visualization
- Historical trend analysis
- API rate limiting and caching
- Web UI for data exploration

---

**For detailed enhancement information, see [ENHANCEMENTS.md](ENHANCEMENTS.md)**

**For testing instructions, see [TESTING.md](TESTING.md)**
