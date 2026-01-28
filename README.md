# California Ballot Measures Database

**Explore California direct democracy from 1998 to present**

A comprehensive, searchable database of 12,156 active ballot measures from across California—spanning statewide propositions to local county measures from 1998 to 2026. Built to make civic data accessible and understandable for researchers, journalists, voters, and anyone interested in California politics.

> *Archival note: A raw ICPSR file covering 1902–2016 is available but not loaded into the active database.*

🌐 **Live Website**: [cal-vgp.igorgeyn.com](https://cal-vgp.igorgeyn.com)

---

## 🎯 What This Is

The California Ballot Measures Database (Cal VGP) helps you:

- **Search** thousands of ballot measures by keyword, topic, location, or year
- **Browse by region** through 9 major California regions (Bay Area, LA, etc.)
- **Analyze results** with vote counts, pass rates, and historical trends
- **Understand measures** through AI-generated summaries
- **Export data** for your own analysis (CSV, JSON)

### Key Features

- 📊 **12,156 ballot measures** from all 58 counties plus statewide propositions
- 🗳️ **Vote results** for 10,908 measures (89.7%)
- 📝 **AI summaries** for easier understanding of complex measures
- 🗺️ **Regional browsing** organized by geographic areas
- 🔍 **Advanced filtering** by year, status, topic, and location
- 💬 **AI chat interface** (BYOLLM - bring your own LLM key)
- 📥 **Data exports** for researchers (CSV/JSON)

---

## 🚀 Quick Start

### View the Website

Just visit [cal-vgp.igorgeyn.com](https://cal-vgp.igorgeyn.com) - no setup required!

### Run Locally

```bash
# Clone the repository
git clone https://github.com/igorgeyn/cal_vgp.git
cd cal_vgp/scraper

# Install dependencies
pip install -r requirements.txt

# Generate the website
make website

# Open in browser
open ../index.html
```

---

## 📂 Project Structure

```
cal_vgp/
├── scraper/                    # Main application code
│   ├── src/
│   │   ├── database/          # Database operations
│   │   ├── scrapers/          # Data collection from various sources
│   │   ├── website/           # Static website generator
│   │   └── utils/             # Helper utilities
│   ├── scripts/               # Utility scripts
│   │   ├── generate_site.py   # Main website generator
│   │   ├── export_data.py     # Data export utility
│   │   └── generate_ai_summaries.py  # AI summary generation
│   ├── data/
│   │   └── exports/           # CSV/JSON exports
│   ├── Makefile               # Common commands
│   └── requirements.txt       # Python dependencies
├── cloudflare-worker/         # CORS proxy for AI chat
├── ballot_measures.db         # SQLite database
└── index.html                 # Generated website
```

---

## 🛠️ Usage

### Common Commands

```bash
cd scraper

# Generate the website
make website

# Export data to CSV/JSON
make export-csv

# Generate AI summaries (requires Ollama)
make summaries-ai

# Scrape new data
make scrape

# Update (dedup + enrich) and regenerate
make quick
```

### Export Data

Export ballot measures data for your own analysis:

```bash
# Export all measures to CSV
python scripts/export_data.py --format csv

# Export only 2024 measures
python scripts/export_data.py --year 2024

# Export as JSON
python scripts/export_data.py --format json

# Export summary quality analysis
python scripts/export_data.py --format summary-quality
```

Exports are saved to `scraper/data/exports/`.

### Generate AI Summaries

Generate neutral summaries for ballot measures using local AI (Ollama):

```bash
# Install Ollama first: https://ollama.ai
ollama pull llama3.2

# Generate summaries
cd scraper
python scripts/generate_ai_summaries.py
```

---

## 📊 Data Sources

The database aggregates data from multiple authoritative sources:

- **Ballotpedia** - Detailed measure information and summaries
- **California Secretary of State** - Official statewide propositions
- **CEDA (California Elections Data Archive)** - Historical vote data
- **NCSL (National Conference of State Legislatures)** - Policy analysis
- **ICPSR** - Historical ballot measure research

---

## 🤖 AI Chat Interface

The website includes an interactive AI chat for exploring the data. Users provide their own API keys:

- **Anthropic Claude** - ~$0.003 per question
- **OpenAI GPT** - ~$0.01 per question
- **Ollama** - Free (requires local installation)

The Cloudflare Worker proxy (`cloudflare-worker/`) handles CORS while keeping costs zero for the site owner.

---

## 🔧 Development

### Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt

# Initialize database (if needed)
make db-init
```

### Tech Stack

- **Backend**: Python 3.8+
- **Database**: SQLite
- **Web Scrapers**: BeautifulSoup, Requests
- **AI**: Ollama (local), Anthropic/OpenAI APIs
- **Frontend**: Vanilla JavaScript, CSS
- **Deployment**: GitHub Pages + Cloudflare Workers

### Key Files

- `src/website/generator.py` - Generates the static website
- `src/database/operations.py` - Database interface
- `src/scrapers/ballotpedia_*.py` - Data collection
- `src/utils/regions.py` - California regional definitions

---

## 📈 Database Statistics

- **Total Active Measures**: 12,156
- **With Vote Results**: 10,908 (89.7%)
- **With AI Summaries**: 3,457 (28.4%)
- **Years Covered**: 1998–2026 (active database)
- **Counties**: All 58 California counties + statewide
- **Database Schema**: 48 columns per measure, 26 exported fields

---

## 🤝 Contributing

Contributions welcome! Areas where help is needed:

- **Data Quality**: Improve scrapers, fix duplicates
- **AI Summaries**: Enhance prompt engineering, add more summaries
- **Features**: Better visualizations, advanced search, mobile UX
- **Documentation**: User guides, API docs

### Submit Issues

Found a bug or have a feature request? [Open an issue](https://github.com/igorgeyn/cal_vgp/issues)

---

## 📝 License

This project is open source. Data is aggregated from public sources. Please respect the terms of service of data providers.

---

## 🙏 Acknowledgments

- Built with data from Ballotpedia, California Secretary of State, CEDA, NCSL, and ICPSR
- Inspired by the need for accessible civic data
- AI summaries powered by Ollama and Claude

---

## 📬 Contact

- **Website**: [cal-vgp.igorgeyn.com](https://cal-vgp.igorgeyn.com)
- **GitHub**: [github.com/igorgeyn/cal_vgp](https://github.com/igorgeyn/cal_vgp)
- **Issues**: [Submit here](https://github.com/igorgeyn/cal_vgp/issues)

---

**Made with ❤️ for California voters, researchers, and civic engagement enthusiasts**
