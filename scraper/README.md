# California Ballot Measures Database

A comprehensive system for collecting, organizing, and presenting California ballot measure data from 1902 to present.

## 🚀 Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/yourusername/cal-ballot-measures.git
cd cal-ballot-measures/scraper

# 2. Install dependencies
make install

# 3. Set up the project
make setup

# 4. Update database with latest data
make update

# 5. Generate website
make website

# 6. (Optional) Start API server
make api
```

## 📋 Features

- **Comprehensive Data Collection**: Scrapes from CA Secretary of State, NCSL, ICPSR, and CEDA
- **Smart Deduplication**: Identifies and merges duplicate measures across sources
- **Rich Data**: Includes voting results, summaries, topics, and PDF links
- **Modern Web Interface**: Faceted search with filters for year, status, and topics
- **REST API**: Full-featured API with documentation at `/docs`
- **Historical Coverage**: Data from 1902 to present
- **Automated Updates**: Check for and incorporate new measures

## 🏗️ Project Structure

```
scraper/
├── src/                    # Source code
│   ├── config.py          # Central configuration
│   ├── scrapers/          # Web scrapers
│   ├── parsers/           # Data parsers (NCSL, ICPSR, CEDA)
│   ├── database/          # Database operations
│   ├── enrichment/        # Data enrichment (summaries)
│   ├── website/           # Website generation
│   └── api/               # REST API
├── scripts/               # Entry point scripts
│   ├── scrape.py         # Run scrapers
│   ├── update_db.py      # Smart database updates
│   ├── check_updates.py  # Check for new measures
│   └── generate_site.py  # Generate website
├── data/                  # Data storage
│   ├── raw/              # Raw scraped data
│   ├── processed/        # Processed data
│   └── ballot_measures.db # SQLite database
├── tests/                 # Test files
└── docs/                  # Documentation
```

## 📊 Data Sources

### Current Measures
- **CA Secretary of State**: Official qualified ballot measures
- **UC Law SF Repository**: Historical ballot propositions

### Historical Data
- **NCSL**: National Conference of State Legislatures (2014-present)
- **ICPSR**: Historical data (1902-2016)
- **CEDA**: California Elections Data Archive (1998-2024)

## 🛠️ Usage

### Basic Commands

```bash
# Check for new measures without updating
make check

# Update database with new measures
make update

# Generate static website
make website

# Start API server
make api

# Show database statistics
make db-stats

# Backup database
make backup
```

### Advanced Usage

```bash
# Scrape specific sources
python scripts/scrape.py --sources ca_sos ncsl

# Check specific sources for updates
python scripts/check_updates.py --sources all --json

# Generate website with specific style
python scripts/generate_site.py --style modern --preview

# Initialize fresh database
python scripts/initialize_db.py --fresh
```

## 🌐 API Endpoints

Start the API server:
```bash
make api  # Runs at http://localhost:8000
```

### Available Endpoints

- `GET /api/measures` - List all measures with filters
- `GET /api/measures/{id}` - Get specific measure
- `POST /api/search` - Advanced search
- `GET /api/stats` - Database statistics
- `GET /api/years` - Years with measure counts
- `GET /api/topics` - Topics with counts
- `GET /api/export` - Export data (JSON/CSV)

API documentation available at `http://localhost:8000/docs`

## 🔍 Search Features

The system supports advanced searching:

- **Full-text search** across titles, descriptions, and summaries
- **Filter by year range** (1902-present)
- **Filter by county** (statewide and local measures)
- **Filter by status** (passed, failed, pending)
- **Filter by topic** (taxes, healthcare, environment, etc.)
- **Filter by data source** (CA SOS, NCSL, ICPSR, CEDA)

## 📈 Database Schema

The SQLite database uses intelligent fingerprinting for deduplication:

- **Unique fingerprint**: Per-source identifier
- **Cross-source fingerprint**: For matching across sources
- **Content hash**: For identifying similar content

Key fields include:
- Basic info (year, title, description)
- Voting data (yes/no votes, percentages, outcome)
- Enrichment (summaries, topics, categories)
- Source tracking (data source, URLs, PDFs)

## 🚀 Deployment

### Website Deployment (GitHub Pages)

```bash
# Generate and deploy website
make website-deploy
```

### API Deployment

The API can be deployed to any platform supporting Python/FastAPI:

```bash
# For production
uvicorn src.api.server:app --host 0.0.0.0 --port 8000
```

## 🧪 Testing

```bash
# Run all tests
make test

# Check code style
make lint

# Format code
make format
```

## 📦 Migration from Old Structure

If you have the old project structure:

```bash
# Dry run to see what will change
make migrate-dry-run

# Perform migration
make migrate
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- California Secretary of State for official ballot measure data
- UC Law SF for historical repository
- NCSL for comprehensive ballot measure tracking
- ICPSR for historical data preservation
- CEDA for California elections data

## 📞 Support

For issues, questions, or suggestions:
- Open an issue on GitHub
- Check the documentation in the `docs/` directory
- Review the API documentation at `/docs` when running the API

## 🔄 Automated Workflows

### Daily Updates
```bash
make daily  # Check for new measures
```

### Weekly Full Update
```bash
make weekly  # Update, backup, and deploy
```

### Quick Update and Deploy
```bash
make quick  # Update database and regenerate website
```