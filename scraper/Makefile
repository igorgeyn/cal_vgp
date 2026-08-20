# California Ballot Measures - Fixed Makefile
# For use with the reorganized project structure

.PHONY: help install setup update scrape check insights website api clean test backup restore migrate

# Default - show help
help:
	@echo "California Ballot Measures - Available Commands"
	@echo "=============================================="
	@echo ""
	@echo "Quick Start:"
	@echo "  make setup        - Initial project setup"
	@echo "  make update       - Update database with latest data"
	@echo "  make website      - Generate static website"
	@echo ""
	@echo "Core Commands:"
	@echo "  make scrape       - Scrape latest measures"
	@echo "  make check        - Check for new measures (no update)"
	@echo "  make db-init      - Initialize database"
	@echo "  make api          - Run API server"
	@echo ""
	@echo "Development:"
	@echo "  make test         - Run tests"
	@echo "  make lint         - Check code style"
	@echo "  make format       - Format code"
	@echo "  make clean        - Clean temporary files"
	@echo ""
	@echo "Data Management:"
	@echo "  make backup       - Backup database"
	@echo "  make restore      - Restore database from backup"
	@echo "  make export-csv   - Export data to CSV"
	@echo "  make stats        - Show database statistics"
	@echo ""
	@echo "Summary Generation:"
	@echo "  make summaries    - Complete summary workflow (Ballotpedia + AI)"
	@echo "  make summaries-web    - Scrape summaries from Ballotpedia only"
	@echo "  make summaries-ai     - Generate AI summaries for remaining measures"
	@echo ""
	@echo "Migration:"
	@echo "  make migrate      - Migrate from old structure to new"

# Installation and setup
install:
	@echo "📦 Installing dependencies..."
	@pip install -r requirements.txt

setup: install
	@echo "🔧 Setting up project..."
	@mkdir -p data/raw data/processed data/exports logs
	@cp .env.example .env 2>/dev/null || true
	@python scripts/initialize_db.py
	@echo "✅ Setup complete!"

# Main operations — all route through unified pipeline
update:
	@echo "🔄 Updating ballot measures database (incremental)..."
	@python scripts/pipeline.py incremental

scrape:
	@echo "🕷️ Scraping all sources (incremental)..."
	@python scripts/pipeline.py incremental

check:
	@echo "🔍 Checking for new measures (dry run)..."
	@python scripts/pipeline.py check

website:
	@echo "🌐 Generating website..."
	@python scripts/generate_insights.py
	@python scripts/generate_site.py --force
	@echo ""
	@echo "✓ Checking files were created..."
	@ls -lh index.html measures-data.json ../index.html ../measures-data.json | awk '{print "  " $$5, $$6, $$7, $$8, $$9}'
	@echo ""
	@echo "📂 Generated site bundles:"
	@echo "  - scraper/index.html + measures-data.json (ignored local preview)"
	@echo "  - ../index.html + ../measures-data.json (tracked GitHub Pages pair)"

insights:
	@echo "📊 Generating insights analysis payload..."
	@python scripts/generate_insights.py

website-preview: website
	@echo "👀 Opening website in browser..."
	@python -m webbrowser index.html

website-deploy: website
	@echo "🚀 Deploying website to GitHub Pages..."
	@python scripts/generate_site.py --deploy

# API server
api:
	@echo "🚀 Starting API server at http://localhost:8000..."
	@echo "📚 API docs at http://localhost:8000/docs"
	@cd src/api && python server.py

api-test:
	@echo "🧪 Testing API endpoints..."
	@curl -s http://localhost:8000/api/health | python -m json.tool

# Database operations
db-init:
	@echo "📊 Initializing database..."
	@python scripts/initialize_db.py --fresh

db-init-historical:
	@echo "📊 Loading historical sources into database..."
	@python scripts/pipeline.py historical

db-stats:
	@echo "📊 Database statistics..."
	@python -c "from src.database.operations import Database; \
	           from src.config import DB_PATH; \
	           db = Database(DB_PATH); \
	           stats = db.get_statistics(); \
	           print(f'Total measures: {stats[\"total_measures\"]}'); \
	           print(f'With summaries: {stats[\"with_summaries\"]}'); \
	           print(f'With votes: {stats[\"with_votes\"]}'); \
	           print(f'Year range: {stats.get(\"year_min\", \"N/A\")}-{stats.get(\"year_max\", \"N/A\")}')"

backup:
	@echo "💾 Backing up database..."
	@python -c "from src.database.operations import Database; \
	           from src.config import DB_PATH; \
	           db = Database(DB_PATH); \
	           backup_path = db.backup(); \
	           print(f'Backup saved to: {backup_path}')"

restore:
	@echo "🔄 Restoring database from backup..."
	@if [ -f data/backups/ballot_measures_backup_20250730_180629.db ]; then \
		cp data/backups/ballot_measures_backup_20250730_180629.db data/ballot_measures.db; \
		echo "✅ Database restored from backup (10,871 measures)"; \
	else \
		echo "❌ Backup file not found. Run 'git pull' to get the backup."; \
		exit 1; \
	fi

export-csv:
	@echo "📤 Exporting data to CSV..."
	@mkdir -p data/exports
	@python -c "from src.database.operations import Database; \
	           from src.config import DB_PATH; \
	           import pandas as pd; \
	           from datetime import datetime; \
	           db = Database(DB_PATH); \
	           measures = db.get_all_active_measures(); \
	           df = pd.DataFrame([m.to_dict() for m in measures]); \
	           filename = f'data/exports/measures_{datetime.now().strftime(\"%Y%m%d\")}.csv'; \
	           df.to_csv(filename, index=False); \
	           print(f'Exported to: {filename}')"

# Development tools
test:
	@echo "🧪 Running tests..."
	@python -m pytest tests/ -v

lint:
	@echo "🔍 Checking code style..."
	@python -m flake8 src/ scripts/ --max-line-length=100 --extend-ignore=E203,W503

format:
	@echo "🎨 Formatting code..."
	@python -m black src/ scripts/ tests/
	@python -m isort src/ scripts/ tests/

clean:
	@echo "🧹 Cleaning temporary files..."
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@find . -type f -name ".DS_Store" -delete 2>/dev/null || true
	@rm -rf .pytest_cache 2>/dev/null || true

# Migration from old structure
migrate:
	@echo "🔄 Migrating to new project structure..."
	@echo "This will:"
	@echo "  1. Backup your current setup"
	@echo "  2. Reorganize files into new structure"
	@echo "  3. Update configuration"
	@echo ""
	@read -p "Continue? [y/N] " -n 1 -r; \
	echo ""; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		python migrate_to_new_structure.py; \
	else \
		echo "Migration cancelled."; \
	fi

migrate-dry-run:
	@echo "🔍 Showing what migration would do (dry run)..."
	@python migrate_to_new_structure.py --dry-run

# Shortcuts and workflows
quick: update website
	@echo "✅ Quick update complete!"

daily: check
	@$(MAKE) -s db-stats

weekly: update backup website
	@echo "✅ Weekly update complete!"

# Installation check
check-deps:
	@echo "🔍 Checking dependencies..."
	@python -c "import requests; print('✅ requests')" || echo "❌ requests"
	@python -c "import bs4; print('✅ beautifulsoup4')" || echo "❌ beautifulsoup4"
	@python -c "import pandas; print('✅ pandas')" || echo "❌ pandas"
	@python -c "import fastapi; print('✅ fastapi')" || echo "❌ fastapi"
	@python -c "import pydantic; print('✅ pydantic')" || echo "❌ pydantic"

# Show current status
status: db-stats
	@echo ""
	@echo "📁 Data files:"
	@ls -lh data/*.db 2>/dev/null || echo "  No database found"
	@echo ""
	@echo "🌐 Website:"
	@ls -lh index.html 2>/dev/null || echo "  Not generated"

# Development shortcuts
dev:
	@echo "Development Mode"
	@echo "==============="
	@echo "1. make update    - Update database"
	@echo "2. make website   - Generate website"
	@echo "3. make api       - Start API server"
	@echo "4. make test      - Run tests"

# Summary generation commands
summaries:
	@echo "🤖 Running complete summary workflow..."
	@python scripts/complete_summary_workflow.py

summaries-web:
	@echo "🌐 Scraping summaries from Ballotpedia..."
	@python scripts/update_ballotpedia_summaries_deduped.py

summaries-ai:
	@echo "🤖 Generating AI summaries..."
	@python scripts/generate_ai_summaries.py

# Complete pipeline
full-run:
	@echo "🔄 Running full pipeline (historical + incremental + dedupe + website)..."
	@python scripts/pipeline.py full
	@$(MAKE) -s website
	@$(MAKE) -s status

