# Testing Guide - California Ballot Measures

This guide provides commands to test all functionality after the cleanup.

## 🚀 Quick Test - Run Automated Script

```bash
./test_pipeline.sh
```

This comprehensive test script validates:
- ✅ All imports work
- ✅ Parsers find their data files
- ✅ Scrapers are functional
- ✅ Database operations work
- ✅ Code refactoring succeeded
- ✅ Cleanup was complete

---

## 📋 Manual Testing Commands

### 1. Test CEDA Parser (Now Fixed!)

The CEDA parser now works with the CSV file at `data/raw/ceda_combined.csv`:

```bash
# Parse CEDA data (dry run - no database save)
python scripts/scrape.py --source ceda --no-save

# Expected: Parses 10,909 measures from CSV
```

### 2. Test CA Secretary of State Scraper

```bash
# Scrape current qualified ballot measures
python scripts/scrape.py --source ca-sos --no-save

# Expected: Finds 4+ current measures
```

### 3. Test UC Law SF Scraper

```bash
# Scrape historical UC Law SF data
python scripts/scrape.py --source uc-law-sf --no-save

# Expected: Finds 50 historical measures (default limit)
```

### 4. Test All Scrapers

```bash
# Run all scrapers (dry run)
python scripts/scrape.py --source all --no-save
```

### 5. Test ICPSR Parser (Now Fixed!)

The ICPSR parser now looks in `data/raw/` first:

```bash
python -c "
from src.parsers.icpsr import ICPSRParser
from pathlib import Path

parser = ICPSRParser(Path('data'))
file = parser.find_file()
print(f'✅ ICPSR file found: {file}')

if file:
    measures = parser.parse()
    print(f'✅ Parsed {len(measures)} CA measures')
"
```

### 6. Test Refactored normalize_measure_data()

Verify all scripts use the shared function:

```bash
python -c "
from scripts.scrape import normalize_measure_data as nm1
from scripts.update_db import normalize_measure_data as nm2
from scripts.check_updates import normalize_measure_data as nm3
from src.database.utils import normalize_measure_data as nm4

assert nm1 is nm2 is nm3 is nm4
print('✅ All scripts using shared normalize_measure_data()')
print(f'   Location: {nm1.__module__}')
"
```

### 7. Test Database Operations

```bash
# Check database status
python scripts/update_db.py --stats

# Check for new measures (non-destructive)
python scripts/check_updates.py --sources ca_sos

# Update database (check only, no writes)
python scripts/update_db.py --check-only

# Full update with deduplication
python scripts/update_db.py --dedupe
```

### 8. Test Website Generation

```bash
# Generate static website
python scripts/generate_site.py

# Verify file created
ls -lh index.html

# Open in browser (macOS)
open index.html
```

### 9. Test API Server

```bash
# Start server
python src/api/server.py &
API_PID=$!

# Wait for startup
sleep 2

# Test endpoints
curl http://localhost:8000/
curl http://localhost:8000/statistics
curl "http://localhost:8000/search?q=education"

# Stop server
kill $API_PID
```

### 10. Run Test Suite

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_models.py -v

# Run with coverage
pytest --cov=src --cov-report=html
open htmlcov/index.html
```

---

## 🔍 Verification Commands

### Verify Cleanup Success

```bash
# Check cruft files are gone
ls cleanup_post_reorg.py 2>/dev/null && echo "❌ Still exists" || echo "✅ Removed"
ls ca_ballot_measures.csv 2>/dev/null && echo "❌ Still exists" || echo "✅ Removed"
ls -d config/ 2>/dev/null && echo "❌ Still exists" || echo "✅ Removed"

# Check new files exist
ls src/database/utils.py && echo "✅ Created"
ls tests/test_models.py && echo "✅ Created"
ls pytest.ini && echo "✅ Created"

# Check archives created
ls -lh data/archives/
```

### Verify Parser Paths Fixed

```bash
# ICPSR should find file in data/raw/
python -c "
from src.parsers.icpsr import ICPSRParser
from pathlib import Path
p = ICPSRParser(Path('data'))
assert p.file_paths[0].parts[-2] == 'raw'
print('✅ ICPSR checks raw/ directory first')
"

# CEDA should use data/raw/ by default
python -c "
from src.parsers.ceda import CEDAParser
p = CEDAParser()
print(f'✅ CEDA using directory: {p.data_dir}')
assert 'raw' in str(p.data_dir)
"
```

### Verify No Duplicate Code

```bash
# Should only find one definition
grep -rn "^def normalize_measure_data" scripts/ src/

# Expected output:
# src/database/utils.py:7:def normalize_measure_data(data: dict) -> dict:
```

---

## 🎯 Integration Test - Full Workflow

Test the complete pipeline:

```bash
# 1. Check database status
echo "=== Database Status ==="
python scripts/update_db.py --stats

# 2. Scrape CEDA data (10,909 measures)
echo -e "\n=== Scraping CEDA ==="
python scripts/scrape.py --source ceda --no-save | tail -5

# 3. Scrape CA SOS (4+ measures)
echo -e "\n=== Scraping CA SOS ==="
python scripts/scrape.py --source ca-sos --no-save | tail -5

# 4. Check for updates
echo -e "\n=== Checking Updates ==="
python scripts/check_updates.py --sources ca_sos

# 5. Generate website
echo -e "\n=== Generating Website ==="
python scripts/generate_site.py

echo -e "\n✅ Full pipeline test complete!"
```

---

## 🧪 Component-Specific Tests

### Test BallotMeasure Model

```bash
python -c "
from src.database.models import BallotMeasure

measure = BallotMeasure(
    year=2024,
    measure_id='Prop 1',
    title='Test Measure',
    state='CA',
    data_source='TEST'
)

print(f'✅ Created measure: {measure.title}')
print(f'✅ Fingerprint: {measure.fingerprint[:20]}...')
print(f'✅ to_dict works: {bool(measure.to_dict())}')
"
```

### Test Database Context Manager

```bash
python -c "
from src.database import Database, BallotMeasure
from pathlib import Path
import tempfile

with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
    db_path = f.name

try:
    with Database(db_path) as db:
        measure = BallotMeasure(
            year=2024,
            measure_id='Test',
            title='Test Measure',
            state='CA',
            data_source='TEST'
        )
        measure_id = db.insert_measure(measure)
        print(f'✅ Database context manager works')
        print(f'✅ Inserted measure with ID: {measure_id}')
finally:
    Path(db_path).unlink(missing_ok=True)
"
```

---

## 📊 Performance Tests

### Measure Parsing Performance

```bash
# Time CEDA parsing
time python scripts/scrape.py --source ceda --no-save

# Expected: ~2-3 seconds for 10,909 measures
```

### Database Query Performance

```bash
python -c "
import time
from src.database import Database

db = Database()

# Test query performance
start = time.time()
measures = db.get_all_measures(limit=1000)
elapsed = time.time() - start

print(f'✅ Retrieved {len(measures)} measures in {elapsed:.3f} seconds')
"
```

---

## 🐛 Troubleshooting

### If tests fail:

1. **Import errors**: Run `pip install -r requirements.txt`
2. **Parser not finding files**: Check `data/raw/` directory exists
3. **Database errors**: Run `python scripts/initialize_db.py --fresh`
4. **Website generation fails**: Ensure database has data

### Common Issues:

```bash
# Reinitialize database
python scripts/initialize_db.py --fresh

# Rebuild with CEDA data
python scripts/scrape.py --source ceda
python scripts/update_db.py --dedupe

# Clean generated files
make clean
```

---

## ✨ Success Indicators

After running tests, you should see:

- ✅ CEDA parser finds 10,909 measures
- ✅ CA SOS scraper finds 4+ current measures
- ✅ ICPSR parser finds CSV file in data/raw/
- ✅ All imports work without errors
- ✅ normalize_measure_data() shared across scripts
- ✅ 48 pytest tests pass
- ✅ Database statistics show proper data

---

## 📞 Next Steps

After successful testing:

1. Run full scrape: `make update`
2. Generate website: `make website`
3. Commit changes: `git add . && git commit -m "Cleanup and refactor complete"`
4. Push to remote: `git push`

---

**Happy Testing! 🚀**
