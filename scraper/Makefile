.PHONY: install setup test lint format run-cli run-gui run-api clean db merge analyze site preview help check-new update stats force-website init-db clean-temp query db-shell db-export db-summary migrate-to-sqlite complete-pipeline quickstart fix-db first-time-safe dedupe-cross-source

# Default target - show help
help:
	@echo "🗳️  California Ballot Measures - Available Commands"
	@echo "=================================================="
	@echo "Quick Start:"
	@echo "  make quickstart   - Fast setup with defaults (recommended)"
	@echo "  make first-time   - Complete first-time setup"
	@echo "  make fix-db       - Fix database issues"
	@echo ""
	@echo "Setup & Installation:"
	@echo "  make install      - Install dependencies"
	@echo "  make setup        - Complete project setup"
	@echo "  make init-db      - Initialize enhanced SQLite database"
	@echo "  make migrate-to-sqlite - Migrate from JSON to SQLite"
	@echo ""
	@echo "Smart Pipeline (NEW):"
	@echo "  make check-new    - Check for new measures (no updates)"
	@echo "  make update       - Smart update - only if new measures found"
	@echo "  make stats        - Show database statistics"
	@echo "  make dedupe-cross-source - Deduplicate across data sources"
	@echo ""
	@echo "Data Management:"
	@echo "  make scrape       - Scrape latest CA ballot measures"
	@echo "  make merge        - Merge historical data (NCSL + ICPSR)"
	@echo "  make db           - Create/update SQLite database"
	@echo "  make db-clean     - Recreate database from scratch"
	@echo "  make parse-ceda   - Parse CEDA historical data"
	@echo "  make query        - Interactive SQLite query interface"
	@echo ""
	@echo "Analysis & Development:"
	@echo "  make analyze      - Run sample analyses"
	@echo "  make run-api      - Start REST API server"
	@echo "  make test-api     - Test API endpoints"
	@echo "  make run-gui      - Start Streamlit interface"
	@echo "  make run-cli      - Run CLI interface"
	@echo ""
	@echo "Website:"
	@echo "  make site         - Build and deploy static website"
	@echo "  make preview      - Preview website locally"
	@echo "  make site-dev     - Build static site for development"
	@echo ""
	@echo "Workflows:"
	@echo "  make daily        - Daily check for new measures"
	@echo "  make weekly       - Weekly full update"
	@echo ""
	@echo "Utilities:"
	@echo "  make clean        - Clean temporary files"
	@echo "  make backup       - Backup database"
	@echo "  make status       - Show system status"
	@echo "  make check-data   - Check if historical data files are present"
	@echo ""
	@echo "SQLite Database:"
	@echo "  make query        - Interactive SQL query interface"
	@echo "  make db-shell     - Open SQLite shell"
	@echo "  make db-summary   - Quick database summary"
	@echo "  make db-export    - Export database to CSV"

install:
	@echo "📦 Installing dependencies..."
	poetry install || pip install -r requirements.txt

setup: install
	@echo "🔧 Setting up project..."
	mkdir -p data logs downloaded ../downloaded data/downloaded
	cp .env.example .env 2>/dev/null || touch .env
	@echo "📄 Checking for historical data files..."
	@poetry run python check_downloads.py 2>/dev/null || python check_downloads.py
	@echo "✅ Setup complete!"

# Quick start - fastest way to get going
quickstart:
	@echo "🚀 Quick Start - Setting up everything with defaults..."
	@$(MAKE) setup
	@python setup_ballot_database.py --fresh --no-backup
	@$(MAKE) scrape-with-summaries
	@$(MAKE) parse-ceda
	@$(MAKE) init-db
	@$(MAKE) dedupe-cross-source
	@$(MAKE) force-website
	@echo ""
	@echo "✅ Quick start complete!"
	@echo "📄 Open auto_enhanced_ballot_measures.html in your browser"
	@echo ""
	@$(MAKE) stats

# Smart pipeline commands (using SQLite)
check-new:
	@echo "🔍 Checking for new ballot measures..."
	@poetry run python smart_scraper_sqlite.py --check || python smart_scraper_sqlite.py --check

update:
	@echo "🔄 Updating ballot measures database..."
	@poetry run python smart_scraper_sqlite.py || python smart_scraper_sqlite.py

stats:
	@echo "📊 Database statistics..."
	@poetry run python smart_scraper_sqlite.py --stats || python smart_scraper_sqlite.py --stats

# force-website:
# 	@echo "🌐 Force regenerating website..."
# 	@poetry run python smart_scraper_sqlite.py --force-website || python smart_scraper_sqlite.py --force-website
force-website:
	@echo "🌐 Force regenerating website..."
	@poetry run python smart_scraper_sqlite.py --force-website || python smart_scraper_sqlite.py --force-website
	@cp auto_enhanced_ballot_measures.html index.html
	@echo "✅ Updated both auto_enhanced_ballot_measures.html and index.html"

# Cross-source deduplication
dedupe-cross-source:
	@echo "🔄 Running cross-source deduplication..."
	@poetry run python -c "from setup_ballot_database import EnhancedBallotDatabase; db = EnhancedBallotDatabase(); db.connect(); db.handle_cross_source_deduplication(); db.close(); print('✅ Cross-source deduplication complete')" || \
	python -c "from setup_ballot_database import EnhancedBallotDatabase; db = EnhancedBallotDatabase(); db.connect(); db.handle_cross_source_deduplication(); db.close(); print('✅ Cross-source deduplication complete')"

# Initialize SQLite database with better error handling
init-db:
	@echo "🔧 Setting up enhanced SQLite database..."
	@if [ -f data/ballot_measures.db ]; then \
		echo "⚠️  Existing database found."; \
		echo "Choose an option:"; \
		echo "  1. make db-clean     # Start fresh (backs up existing)"; \
		echo "  2. make migrate      # Migrate existing (keeps data)"; \
		echo "  3. python setup_ballot_database.py  # Auto-migrate"; \
		echo ""; \
		echo "Running auto-migration..."; \
	fi
	@poetry run python setup_ballot_database.py || python setup_ballot_database.py

# Fix database issues
fix-db:
	@echo "🔧 Attempting to fix database issues..."
	@echo "Current status:"
	@ls -la data/ballot_measures.db 2>/dev/null || echo "  No database found"
	@echo ""
	@echo "Options:"
	@echo "1. Migrate existing database:"
	@echo "   python setup_ballot_database.py"
	@echo ""
	@echo "2. Start fresh (recommended if having issues):"
	@echo "   make db-clean && make init-db"
	@echo ""
	@echo "3. Complete fresh start:"
	@echo "   rm -f data/ballot_measures.db && make first-time"

# Database operations
db: init-db
	@echo "✅ Enhanced SQLite database ready!"

db-clean:
	@echo "🧹 Recreating database from scratch..."
	@if [ -f data/ballot_measures.db ]; then \
		echo "📦 Backing up existing database..."; \
		cp data/ballot_measures.db data/ballot_measures.db.backup_$(shell date +%Y%m%d_%H%M%S); \
	fi
	rm -f data/ballot_measures.db
	$(MAKE) init-db

merge:
	@echo "🔄 Merging historical data sources..."
	@poetry run python check_downloads.py 2>/dev/null || python check_downloads.py || true
	poetry run python merge_historical_data.py || python merge_historical_data.py

# CEDA operations
parse-ceda:
	@echo "📊 Parsing CEDA data files..."
	@if [ ! -f data/ceda_combined.csv ]; then \
		poetry run python ceda_parser_comprehensive.py || python ceda_parser_comprehensive.py; \
	else \
		echo "✅ CEDA data already parsed (data/ceda_combined.csv exists)"; \
		echo "   To reparse, delete data/ceda_combined.csv first"; \
	fi

# Scraping operations
scrape:
	@echo "🕷️  Running enhanced scraper..."
	poetry run python enhanced_scraper.py || python enhanced_scraper.py

scrape-with-summaries:
	@echo "🕷️  Running scraper with summary generation..."
	poetry run python enhanced_scraper_with_summaries.py || python enhanced_scraper_with_summaries.py

scrape-state:
	poetry run python -m ca_gov_scrapers.interfaces.cli scrape --level state 2>/dev/null || echo "Using simple scraper instead..."
	$(MAKE) scrape

# Analysis
analyze:
	@echo "📈 Running sample analyses..."
	poetry run python analysis_examples.py || python analysis_examples.py
	@echo "📊 Check data/ directory for results"

# Run services
run-api:
	@echo "🚀 Starting API server at http://localhost:8000..."
	@echo "📚 API docs will be at http://localhost:8000/docs"
	poetry run uvicorn ballot_measures_api:app --reload --host 0.0.0.0 --port 8000 || \
	python -m uvicorn ballot_measures_api:app --reload --host 0.0.0.0 --port 8000

test-api:
	@echo "🧪 Testing API endpoints..."
	@curl -s http://localhost:8000/ | python -m json.tool || echo "❌ API not running - start with 'make run-api'"
	@echo ""
	@curl -s http://localhost:8000/stats | python -m json.tool || echo "❌ Stats endpoint failed"

run-gui:
	@echo "🌐 Starting Streamlit interface..."
	poetry run streamlit run src/ca_gov_scrapers/interfaces/gui.py 2>/dev/null || \
	echo "Streamlit GUI not available - use 'make run-api' and 'make preview' instead"

run-cli:
	@echo "💻 Starting CLI..."
	poetry run python -m ca_gov_scrapers.interfaces.cli $(ARGS) 2>/dev/null || \
	echo "CLI not available - use individual make commands instead"

# Complete integrated system
run-system:
	@echo "🎯 Starting complete integrated system..."
	poetry run python integrated_ballot_system.py || python integrated_ballot_system.py

# Website operations - now using SQLite
site: update
	@echo "🌐 Building website from SQLite database..."
	# Generate website from database
	@$(MAKE) force-website
	
	# Copy to root directory
	cp auto_enhanced_ballot_measures.html ../index.html
	
	# Stage and commit changes
	git -C .. add index.html scraper/data/
	git -C .. commit -m "Update site $(shell date +%F_%T)" || echo "Nothing to commit"
	git -C .. push
	
	@echo "✅ Site updated and pushed!"

# Development site - builds from SQLite
site-dev: update
	@echo "🔧 Generating development site from SQLite..."
	@$(MAKE) force-website
	@echo "✅ Development site ready!"
	@echo "Open auto_enhanced_ballot_measures.html in your browser"

# Just preview without commit
# preview:
# 	@echo "👀 Opening website preview..."
# 	@if [ -f ../index.html ]; then \
# 		open ../index.html 2>/dev/null || xdg-open ../index.html 2>/dev/null || echo "Please open ../index.html manually"; \
# 	else \
# 		open auto_enhanced_ballot_measures.html 2>/dev/null || xdg-open auto_enhanced_ballot_measures.html 2>/dev/null || echo "Please open auto_enhanced_ballot_measures.html manually"; \
# 	fi
preview:
	@echo "👀 Opening website preview..."
	@if [ -f ../index.html ]; then \
		open ../index.html 2>/dev/null || xdg-open ../index.html 2>/dev/null || echo "Please open ../index.html manually"; \
	else \
		open auto_enhanced_ballot_measures.html 2>/dev/null || xdg-open auto_enhanced_ballot_measures.html 2>/dev/null || echo "Please open auto_enhanced_ballot_measures.html manually"; \
	fi


# Workflow shortcuts
daily: check-new
	@echo "✅ Daily check complete"

weekly: update dedupe-cross-source
	@echo "✅ Weekly update complete"

# Testing
test:
	@echo "🧪 Running tests..."
	poetry run pytest tests/ -v 2>/dev/null || echo "No tests configured yet"

# Code quality
lint:
	@echo "🔍 Linting code..."
	poetry run flake8 *.py --max-line-length=88 --extend-ignore=E203,W503 2>/dev/null || \
	python -m flake8 *.py --max-line-length=88 --extend-ignore=E203,W503 2>/dev/null || \
	echo "Flake8 not installed"

format:
	@echo "🎨 Formatting code..."
	poetry run black *.py 2>/dev/null || python -m black *.py 2>/dev/null || echo "Black not installed"
	poetry run isort *.py 2>/dev/null || python -m isort *.py 2>/dev/null || echo "isort not installed"

# Utilities
clean:
	@echo "🧹 Cleaning up..."
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	find . -type f -name ".DS_Store" -delete 2>/dev/null || true
	rm -f data/*.png 2>/dev/null || true

clean-temp:
	@echo "🧹 Cleaning temporary files..."
	@rm -f data/temp_scraped.json
	@find . -type f -name "*.pyc" -delete
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# SQLite database helpers
db-shell:
	@echo "🔍 Opening SQLite shell..."
	@echo "Useful commands:"
	@echo "  .tables              - List all tables"
	@echo "  .schema measures     - Show table structure"
	@echo "  .quit                - Exit"
	@echo ""
	@sqlite3 data/ballot_measures.db

query:
	@echo "🔍 SQLite Query Interface"
	@echo "Example queries:"
	@echo "  SELECT COUNT(*) FROM active_measures;"
	@echo "  SELECT year, COUNT(*) FROM active_measures GROUP BY year ORDER BY year DESC LIMIT 10;"
	@echo "  SELECT * FROM active_measures WHERE has_summary = 1 LIMIT 5;"
	@echo ""
	@sqlite3 -header -column data/ballot_measures.db

db-export:
	@echo "📤 Exporting database to CSV..."
	@mkdir -p data/exports
	@sqlite3 -header -csv data/ballot_measures.db "SELECT * FROM active_measures" > data/exports/measures_$(shell date +%Y%m%d).csv
	@echo "✅ Exported to data/exports/measures_$(shell date +%Y%m%d).csv"

db-summary:
	@echo "📊 Quick Database Summary"
	@echo "========================"
	@sqlite3 data/ballot_measures.db "SELECT 'Total measures:', COUNT(*) FROM active_measures;"
	@sqlite3 data/ballot_measures.db "SELECT 'Years covered:', MIN(year) || '-' || MAX(year) FROM active_measures WHERE year IS NOT NULL;"
	@sqlite3 data/ballot_measures.db "SELECT 'With summaries:', COUNT(*) || ' (' || ROUND(COUNT(*)*100.0/(SELECT COUNT(*) FROM active_measures), 1) || '%)' FROM active_measures WHERE has_summary = 1;"
	@sqlite3 data/ballot_measures.db "SELECT 'With vote data:', COUNT(*) || ' (' || ROUND(COUNT(*)*100.0/(SELECT COUNT(*) FROM active_measures), 1) || '%)' FROM active_measures WHERE yes_votes IS NOT NULL;"
	@echo ""
	@echo "Top 5 years by measure count:"
	@sqlite3 -column data/ballot_measures.db "SELECT year, COUNT(*) as measures FROM active_measures GROUP BY year ORDER BY COUNT(*) DESC LIMIT 5;"

check-data:
	@echo "📄 Checking data files..."
	@poetry run python check_downloads.py || python check_downloads.py

backup:
	@echo "💾 Backing up databases..."
	@if [ -f data/ballot_measures.db ]; then \
		cp data/ballot_measures.db data/ballot_measures_backup_$(shell date +%Y%m%d_%H%M%S).db; \
		echo "✅ SQLite backup saved"; \
	else \
		echo "❌ No SQLite database found"; \
	fi
	@if [ -f data/ballot_measures_db.json ]; then \
		cp data/ballot_measures_db.json data/ballot_measures_db_backup_$(shell date +%Y%m%d_%H%M%S).json; \
		echo "✅ JSON database backup saved"; \
	else \
		echo "❌ No JSON database found"; \
	fi

status:
	@echo "📊 System Status"
	@echo "================"
	@echo -n "SQLite Database: "
	@if [ -f data/ballot_measures.db ]; then \
		echo "✅ Exists ($(shell du -h data/ballot_measures.db | cut -f1))"; \
		echo "  Total measures: $(shell sqlite3 data/ballot_measures.db "SELECT COUNT(*) FROM active_measures" 2>/dev/null || echo "Unknown")"; \
		echo "  With summaries: $(shell sqlite3 data/ballot_measures.db "SELECT COUNT(*) FROM active_measures WHERE has_summary = 1" 2>/dev/null || echo "Unknown")"; \
		echo "  With votes: $(shell sqlite3 data/ballot_measures.db "SELECT COUNT(*) FROM active_measures WHERE yes_votes IS NOT NULL" 2>/dev/null || echo "Unknown")"; \
		echo "  Sources: $(shell sqlite3 data/ballot_measures.db "SELECT DISTINCT data_source FROM active_measures" 2>/dev/null | tr '\n' ', ' || echo "Unknown")"; \
	else \
		echo "❌ Not found (run 'make init-db')"; \
	fi
	@echo -n "CEDA Data: "
	@if [ -f data/ceda_combined.csv ]; then \
		echo "✅ Parsed"; \
	else \
		echo "❌ Not parsed"; \
	fi
	@echo -n "Website: "
	@if [ -f ../index.html ]; then \
		echo "✅ Deployed"; \
	elif [ -f auto_enhanced_ballot_measures.html ]; then \
		echo "✅ Generated locally"; \
	else \
		echo "❌ Not generated"; \
	fi

# Development shortcuts
dev:
	@echo "🔧 Development Menu"
	@echo "=================="
	@echo "1. make scrape      - Scrape latest measures"
	@echo "2. make check-new   - Check for new measures"
	@echo "3. make update      - Smart update with dedup"
	@echo "4. make db          - Update database" 
	@echo "5. make run-api     - Start API server"
	@echo "6. make preview     - Preview website"
	@echo "7. make analyze     - Run analyses"
	@echo "8. make site-dev    - Full dev environment"

# Quick commands for common workflows
quick-update: scrape db
	@echo "✅ Quick update complete!"

full-rebuild: clean scrape-with-summaries parse-ceda db analyze dedupe-cross-source site
	@echo "✅ Full rebuild complete!"

# Complete pipeline with CEDA and SQLite
complete-pipeline:
	@echo "🚀 Running complete pipeline with SQLite..."
	@$(MAKE) parse-ceda
	@$(MAKE) init-db
	@$(MAKE) dedupe-cross-source
	@$(MAKE) update
	@$(MAKE) force-website

# First time setup - simplified and safer
first-time: setup check-data
	@echo "🚀 Running first-time setup..."
	@echo "This will download, merge, and set up everything."
	@$(MAKE) scrape-with-summaries
	@$(MAKE) parse-ceda
	@$(MAKE) init-db  # Now handles existing databases gracefully
	@$(MAKE) dedupe-cross-source  # Add cross-source deduplication
	@$(MAKE) site-dev  # Generate site but don't auto-push
	@echo ""
	@echo "✅ First-time setup complete!"
	@echo ""
	@echo "📊 Database statistics:"
	@$(MAKE) stats
	@echo ""
	@echo "Next steps:"
	@echo "1. make preview     - View the website locally"
	@echo "2. make site        - Deploy to GitHub Pages"
	@echo "3. make check-new   - Check for new measures"

# Safe version for development
first-time-safe: setup check-data
	@echo "🚀 Running first-time setup (safe mode)..."
	@$(MAKE) scrape-with-summaries
	@$(MAKE) parse-ceda
	@$(MAKE) db-clean  # This already handles backup
	@$(MAKE) init-db
	@$(MAKE) dedupe-cross-source  # Add cross-source deduplication
	@$(MAKE) site-dev   # Don't push on first run
	@$(MAKE) stats      # Show what we have

# Migration from JSON to SQLite
migrate-to-sqlite:
	@echo "🔄 Migrating from JSON to SQLite..."
	@echo "This will import all your existing data into the new SQLite database"
	@$(MAKE) init-db
	@echo "✅ Migration complete! You can now use SQLite-based commands."

# Production deployment helpers
deploy-api:
	@echo "🚀 API Deployment Instructions:"
	@echo "1. Ensure requirements.txt is up to date"
	@echo "2. Set DATABASE_URL environment variable"
	@echo "3. Deploy ballot_measures_api.py to your hosting service"
	@echo ""
	@echo "Example for Heroku:"
	@echo "  heroku create ca-ballot-api"
	@echo "  git push heroku main"

deploy-check:
	@echo "🔍 Deployment Checklist:"
	@echo -n "requirements.txt: "
	@if [ -f requirements.txt ]; then echo "✅"; else echo "❌ Run: make requirements"; fi
	@echo -n "Database: "
	@if [ -f data/ballot_measures.db ]; then echo "✅"; else echo "❌ Run: make db"; fi
	@echo -n "API tested: "
	@echo "❓ Run: make run-api (then test endpoints)"
	@echo -n "Website updated: "
	@if [ -f ../index.html ]; then echo "✅"; else echo "❌ Run: make site"; fi

# Install requirements.txt if poetry is not available
requirements:
	@echo "📝 Generating requirements.txt..."
	poetry export -f requirements.txt --output requirements.txt --without-hashes 2>/dev/null || \
	pip freeze > requirements.txt