#!/bin/bash
# Comprehensive pipeline test script
# Tests all major components of the cleaned-up California Ballot Measures project

set -e  # Exit on error

echo "=============================================="
echo "California Ballot Measures - Pipeline Tests"
echo "=============================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counter
TESTS_PASSED=0
TESTS_FAILED=0

# Function to run a test
run_test() {
    local test_name="$1"
    local test_cmd="$2"

    echo -e "${BLUE}Testing:${NC} $test_name"
    if eval "$test_cmd" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ PASS${NC}"
        ((TESTS_PASSED++))
    else
        echo -e "${YELLOW}✗ FAIL${NC}"
        ((TESTS_FAILED++))
    fi
    echo ""
}

echo "1. Testing Imports and Module Structure"
echo "----------------------------------------"

run_test "Import normalize_measure_data from utils" \
    "python -c 'from src.database.utils import normalize_measure_data; print(\"OK\")'"

run_test "Import normalize_measure_data from database package" \
    "python -c 'from src.database import normalize_measure_data; print(\"OK\")'"

run_test "Import all parsers" \
    "python -c 'from src.parsers.ceda import CEDAParser; from src.parsers.icpsr import ICPSRParser; from src.parsers.ncsl import NCSLParser; print(\"OK\")'"

run_test "Import scrapers" \
    "python -c 'from src.scrapers.ca_sos import CASOSScraper, UCLawSFScraper; print(\"OK\")'"

run_test "Import database components" \
    "python -c 'from src.database import Database, BallotMeasure, Deduplicator; print(\"OK\")'"

echo ""
echo "2. Testing Parsers"
echo "----------------------------------------"

run_test "CEDA parser finds CSV file" \
    "python -c 'from src.parsers.ceda import CEDAParser; from pathlib import Path; p = CEDAParser(); files = list(p.data_dir.glob(\"ceda*.csv\")); assert len(files) > 0'"

run_test "ICPSR parser finds data file" \
    "python -c 'from src.parsers.icpsr import ICPSRParser; from pathlib import Path; p = ICPSRParser(Path(\"data\")); f = p.find_file(); assert f is not None'"

run_test "CEDA parser can parse data (dry run)" \
    "python scripts/scrape.py --source ceda --no-save"

echo ""
echo "3. Testing Scrapers"
echo "----------------------------------------"

run_test "CA SOS scraper works (dry run)" \
    "python scripts/scrape.py --source ca-sos --no-save"

echo ""
echo "4. Testing Database Utilities"
echo "----------------------------------------"

run_test "normalize_measure_data function works" \
    "python -c 'from src.database.utils import normalize_measure_data; data = {\"year\": 2024, \"source\": \"TEST\"}; result = normalize_measure_data(data); assert \"data_source\" in result'"

run_test "Database status check works" \
    "python -c 'from src.database import check_database_status; status = check_database_status(); print(status)'"

echo ""
echo "5. Testing Refactored Code"
echo "----------------------------------------"

run_test "All scripts use shared normalize_measure_data" \
    "python -c 'from scripts.scrape import normalize_measure_data as nm1; from scripts.update_db import normalize_measure_data as nm2; from scripts.check_updates import normalize_measure_data as nm3; from src.database.utils import normalize_measure_data as nm4; assert nm1 is nm2 is nm3 is nm4'"

echo ""
echo "6. Testing Scripts"
echo "----------------------------------------"

run_test "Database statistics" \
    "python scripts/update_db.py --stats"

run_test "Check for updates (non-destructive)" \
    "python scripts/check_updates.py --sources ca_sos"

echo ""
echo "7. File Cleanup Verification"
echo "----------------------------------------"

# Check that cruft files are gone
if [ ! -f "cleanup_post_reorg.py" ]; then
    echo -e "${GREEN}✓ PASS${NC} cleanup_post_reorg.py removed"
    ((TESTS_PASSED++))
else
    echo -e "${YELLOW}✗ FAIL${NC} cleanup_post_reorg.py still exists"
    ((TESTS_FAILED++))
fi
echo ""

if [ ! -f "config/" ]; then
    echo -e "${GREEN}✓ PASS${NC} config/ directory removed"
    ((TESTS_PASSED++))
else
    echo -e "${YELLOW}✗ FAIL${NC} config/ directory still exists"
    ((TESTS_FAILED++))
fi
echo ""

if [ -f "src/database/utils.py" ]; then
    echo -e "${GREEN}✓ PASS${NC} src/database/utils.py created"
    ((TESTS_PASSED++))
else
    echo -e "${YELLOW}✗ FAIL${NC} src/database/utils.py not found"
    ((TESTS_FAILED++))
fi
echo ""

if [ -f "tests/test_models.py" ]; then
    echo -e "${GREEN}✓ PASS${NC} Test files created"
    ((TESTS_PASSED++))
else
    echo -e "${YELLOW}✗ FAIL${NC} Test files not found"
    ((TESTS_FAILED++))
fi
echo ""

echo ""
echo "8. Optional: Run Test Suite"
echo "----------------------------------------"
if command -v pytest &> /dev/null; then
    run_test "pytest test suite" \
        "pytest -v --tb=short"
else
    echo -e "${YELLOW}pytest not installed, skipping${NC}"
    echo ""
fi

echo ""
echo "=============================================="
echo "Test Summary"
echo "=============================================="
echo -e "${GREEN}Tests Passed: $TESTS_PASSED${NC}"
if [ $TESTS_FAILED -gt 0 ]; then
    echo -e "${YELLOW}Tests Failed: $TESTS_FAILED${NC}"
fi
echo ""

TOTAL=$((TESTS_PASSED + TESTS_FAILED))
PERCENTAGE=$((TESTS_PASSED * 100 / TOTAL))
echo "Success Rate: $PERCENTAGE% ($TESTS_PASSED/$TOTAL)"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}🎉 All tests passed! Pipeline is healthy.${NC}"
    exit 0
else
    echo -e "${YELLOW}⚠️  Some tests failed. Review output above.${NC}"
    exit 1
fi
