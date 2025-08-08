# California Ballot Measures - Simplified Makefile
# For use with the reorganized project structure

.PHONY: help install setup update scrape check website api clean test backup migrate

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
	@echo "  make export-csv   - Export data to CSV"
	@echo "  make stats        - Show database statistics"
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

# Main operations
update:
	@echo "🔄 Updating ballot measures database..."
	@python scripts/update_db.py

scrape:
	@echo "🕷️ Scraping latest measures..."
	@python scripts/scrape.py --sources all

check:
	@echo "🔍 Checking for new measures..."
	@python scripts/check_updates.py --sources all

website:
	@echo "🌐 Generating website..."
	@python scripts/generate_site.py

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
	           backup_path = db.backup_database(); \
	           print(f'Backup saved to: {backup_path}')"

export-csv:
	@echo "📤 Exporting data to CSV..."
	@mkdir -p data/exports
	@python -c "from src.database.operations import Database; \
	           from src.config import DB_PATH; \
	           import pandas as pd; \
	           from datetime import datetime; \
	           db = Database(DB_PATH); \
	           measures = db.get_all_measures(); \
	           df = pd.DataFrame(measures); \
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

weekly: update backup website-deploy
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