.PHONY: install setup test lint format run-cli run-gui run-api clean

install:
	@echo "📦 Installing dependencies..."
	poetry install

setup: install
	@echo "🔧 Setting up project..."
	mkdir -p data logs
	cp .env.example .env 2>/dev/null || touch .env
	@echo "✅ Setup complete!"

test:
	@echo "🧪 Running tests..."
	poetry run pytest tests/ -v

lint:
	@echo "🔍 Linting code..."
	poetry run flake8 src/ --max-line-length=88 --extend-ignore=E203,W503

format:
	@echo "🎨 Formatting code..."
	poetry run black src/ tests/
	poetry run isort src/ tests/

# run-cli:
# 	@echo "💻 Starting CLI..."
# 	poetry run python -m ca_gov_scrapers.interfaces.cli

run-cli:
	poetry run python -m ca_gov_scrapers.interfaces.cli $(ARGS)

run-gui:
	@echo "🌐 Starting web interface..."
	poetry run streamlit run src/ca_gov_scrapers/interfaces/gui.py

run-api:
	@echo "🚀 Starting API server..."
	poetry run uvicorn src.ca_gov_scrapers.interfaces.api:app --reload

clean:
	@echo "🧹 Cleaning up..."
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Quick scraping commands
scrape-state:
	poetry run python -m ca_gov_scrapers.interfaces.cli scrape --level state

dev:
	@echo "🔧 Starting development environment..."
	@echo "Choose an option:"
	@echo "1. make run-gui    # Web interface"
	@echo "2. make run-cli    # Command line"
	@echo "3. make run-api    # REST API"
