# California Government Ballot Measures Scraper

A comprehensive tool for scraping ballot measures and propositions from all levels of California government.

## 🚀 Quick Start

```bash
# 1. Install dependencies
make install

# 2. Set up the project
make setup

# 3. Choose your interface:

# Web interface (easiest)
make run-gui

# Command line interface
make run-cli

# REST API
make run-api
```

## 📋 Features

- ✅ **Multiple Interfaces**: CLI, Web GUI, and REST API
- ✅ **Multi-level Coverage**: State, County, City, and Special Districts
- ✅ **Real-time Scraping**: Get the latest ballot measure information
- ✅ **Multiple Output Formats**: JSON, CSV, Excel
- ✅ **Configurable**: YAML-based configuration system
- ✅ **Scalable**: Modern architecture with Docker support

## 🏗️ Architecture

```
ca-gov-scrapers/
├── src/ca_gov_scrapers/          # Main package
│   ├── interfaces/               # CLI, GUI, API
│   ├── scrapers/                # Scraping logic
│   ├── core/                    # Shared utilities
│   └── data/                    # Data models
├── config/                      # Configuration files
├── tests/                       # Test suite
└── scripts/                     # Utility scripts
```

## 🎯 Coverage

### Government Levels
- **State**: California Secretary of State
- **Counties**: All 58 California counties
- **Cities**: 482+ incorporated cities
- **School Districts**: 1,000+ districts
- **Special Districts**: 2,949+ districts

### Data Sources
- Secretary of State ballot measures
- County election offices
- City clerk websites
- School district bond measures
- Special district elections

## 📊 Usage Examples

### Command Line
```bash
# Scrape state-level measures
ca-scraper scrape --level state --output data/state.json

# Check status
ca-scraper status
```

### Python API
```python
from ca_gov_scrapers.scrapers import CAStateScraper

scraper = CAStateScraper()
results = scraper.scrape_all()
print(f"Found {len(results['measures'])} measures")
```

### Web Interface
Visit http://localhost:8501 after running `make run-gui`

### REST API
Visit http://localhost:8000/docs after running `make run-api`

## 🛠️ Development

```bash
# Run tests
make test

# Format code
make format

# Lint code
make lint

# Clean up
make clean
```

## 📄 License

MIT License - see LICENSE file for details.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `make test`
5. Submit a pull request

## 📞 Support

- 📧 Create an issue for bugs or feature requests
- 💬 Discussion for questions and ideas
- 📚 Check the docs/ directory for detailed documentation
