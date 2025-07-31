# Makefile Guide - California Ballot Measures

This guide explains all available `make` commands for managing the ballot measures system.

## Quick Start

```bash
# First time setup (recommended)
make first-time    # Complete setup with all data

# Or manual setup
make setup          # Create directories and basic setup
make install        # Install Python dependencies

# Build everything
make full-rebuild   # Complete rebuild: scrape, merge, database, website

# Daily workflow
make site          # Update website with latest data
make preview       # View website locally
```

## Common Workflows

### 1. Update Website with Latest Data
```bash
make site          # Scrapes, processes, and deploys
```

### 2. Development Environment
```bash
make site-dev      # Builds site + starts API server
# Then open browser to ../index.html
```

### 3. Database Operations
```bash
make db            # Create/update database
make backup        # Backup current database
make db-clean      # Start fresh (deletes existing)
```

### 4. Data Analysis
```bash
make analyze       # Run sample analyses
# Results saved to data/ directory
```

## All Available Commands

### Setup & Installation
- `make help` - Show all available commands
- `make install` - Install Python dependencies
- `make setup` - Initial project setup
- `make requirements` - Generate requirements.txt

### Data Collection
- `make scrape` - Scrape latest CA ballot measures
- `make scrape-with-summaries` - Scrape with auto-generated summaries
- `make merge` - Merge historical data (NCSL + ICPSR)

### Database Management
- `make db` - Create/update SQLite database
- `make db-clean` - Recreate database from scratch
- `make backup` - Backup current database with timestamp

### Analysis & Visualization
- `make analyze` - Run statistical analyses and generate plots
- `make status` - Show system status and data availability

### Development Tools
- `make run-api` - Start REST API server (http://localhost:8000)
- `make run-gui` - Start Streamlit interface (if available)
- `make preview` - Open website in browser

### Website Management
- `make site` - Complete website rebuild and deploy
- `make site-dev` - Build site + start API for testing

### Code Quality
- `make lint` - Check code style
- `make format` - Auto-format code
- `make test` - Run tests (if available)
- `make clean` - Remove temporary files

### Shortcuts
- `make first-time` - Complete first-time setup with all data
- `make quick-update` - Just scrape and update database
- `make full-rebuild` - Complete system rebuild
- `make dev` - Show development menu

## File Locations

After running commands, find your files here:

- **Database**: `data/ballot_measures.db`
- **Scraped Data**: `data/enhanced_measures.json`
- **Merged Data**: `data/merged_ballot_measures.json`
- **Analysis Results**: `data/*.png`, `data/example_queries.sql`
- **Website**: `../index.html` (deployed), `index.html` (local)
- **Backups**: `data/ballot_measures_backup_*.db`

## Troubleshooting

### Command not found
```bash
# Make sure you're in the scraper/ directory
cd scraper
make help
```

### Missing dependencies
```bash
make install
# or manually:
pip install -r requirements.txt
```

### Database errors
```bash
make db-clean    # Start fresh
make db          # Rebuild
```

### API won't start
```bash
# Check if port 8000 is in use
lsof -i :8000    # Mac/Linux
# Kill any existing process, then:
make run-api
```

### Historical data not found
Make sure you have the NCSL and ICPSR files in either:
- `scraper/downloaded/`
- `downloaded/` (repository root)

## Environment Variables

Copy `.env.example` to `.env` and customize:

```bash
cp .env.example .env
# Edit .env with your settings
```

Key settings:
- `API_PORT` - Change if 8000 is in use
- `DATABASE_URL` - Database location
- `WEBSITE_API_URL` - API URL for production

## Production Deployment

```bash
make deploy-check   # Check deployment readiness
make requirements   # Generate requirements.txt
make site          # Build and push to GitHub
```

Then follow the instructions in `DEPLOYMENT.md` for hosting the API.