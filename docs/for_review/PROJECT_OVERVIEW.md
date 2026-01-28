# Project Overview

## What is This Project?

**California Ballot Measures Database (Cal VGP)** is a comprehensive, searchable database of 12,156 active California ballot measures spanning 1998-2026. The project makes civic data accessible for researchers, journalists, voters, and civic engagement enthusiasts.

> **Note:** A raw ICPSR historical file covering 1902-2016 exists in the repository (`scraper/data/raw/`) but has not been loaded into the active database.

**Live Site:** [cal-vgp.igorgeyn.com](https://cal-vgp.igorgeyn.com)

## Core Purpose

1. **Democratize Access** - Make 28 years of California ballot measure history freely available (1998-2026)
2. **Support Research** - Provide structured data for academic study of direct democracy
3. **Enable Exploration** - Interactive search, filtering, and AI-powered Q&A about ballot measures
4. **Track Results** - Comprehensive vote counts, pass/fail status, and approval thresholds

## Architecture Pattern

**Static Site + Embedded Database + BYOLLM AI Chat**

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (index.html)                     │
│   Single-page application with embedded JSON data (35 MB)       │
│   - Search & Filters  - Measure Cards  - AI Chat Widget         │
└──────────────────────────────┬──────────────────────────────────┘
                               │
┌──────────────────────────────┴──────────────────────────────────┐
│                    Cloudflare Worker (CORS Proxy)                │
│   Proxies AI API calls (Anthropic, OpenAI) - Zero cost to host  │
└──────────────────────────────┬──────────────────────────────────┘
                               │
┌──────────────────────────────┴──────────────────────────────────┐
│                     User's AI Provider                           │
│   Claude, GPT, or Ollama (local) - User pays their usage        │
└─────────────────────────────────────────────────────────────────┘
```

## Key Statistics

| Metric | Value |
|--------|-------|
| Total Measures | 12,156 active records |
| County Coverage | All 58 CA counties + statewide |
| Year Range | 1998-2026 |
| Measures with Vote Data | 10,908 (89.7%) |
| Measures with AI Summaries | 3,457 (28.4%) |
| Overall Pass Rate | 66.1% |
| Total Votes Recorded | 520,521,064+ |

## Technology Stack

### Backend (Python)
- **Database:** SQLite (24.8 MB)
- **Scraping:** BeautifulSoup, Requests
- **Data Processing:** Pandas, NumPy
- **API:** FastAPI (optional local server)
- **AI Integration:** Anthropic, OpenAI (browser chat only); Ollama (summaries + titles); Groq (title generation only, if configured)

### Frontend (Vanilla JS)
- Single HTML file with embedded data
- No frameworks (React, Vue, etc.)
- CSS variables for theming
- Responsive design

### Infrastructure
- **Hosting:** GitHub Pages (free)
- **AI Proxy:** Cloudflare Workers (free tier: 100k requests/day)
- **Build:** Makefile automation

## Directory Structure

```
cal_vgp/
├── scraper/                    # Main application
│   ├── src/
│   │   ├── database/          # SQLite operations
│   │   ├── scrapers/          # 8 data scrapers
│   │   ├── parsers/           # Historical file parsers
│   │   ├── website/           # Static site generator
│   │   ├── enrichment/        # AI summary generation
│   │   └── utils/             # Helper utilities
│   ├── scripts/               # Entry point scripts
│   ├── data/                  # Database, exports, cache
│   └── Makefile               # Build automation
├── cloudflare-worker/         # CORS proxy for AI chat
├── context/                   # Research documentation
├── docs/                      # Additional docs
├── index.html                 # Generated website (35 MB)
└── CNAME                      # GitHub Pages domain
```

## Design Philosophy

1. **Zero Backend Costs** - Static hosting + user-provided AI keys = $0/month
2. **Data First** - Multiple authoritative sources with sophisticated deduplication
3. **Research-Ready** - Complete exports in CSV/JSON for academic use
4. **Progressive Enhancement** - Works without AI; AI chat is optional enhancement
5. **Transparency** - All data sources documented, code open source

## Primary Use Cases

1. **Researchers** - Export complete datasets for academic analysis
2. **Journalists** - Search historical measures, find patterns
3. **Voters** - Understand what's on their ballot, see past results
4. **Policy Analysts** - Track measure types, pass rates, regional patterns
5. **Civic Organizations** - Access structured data for advocacy
