# Summary Generation Workflow

This document explains how to add summaries to ballot measures using both web scraping and AI generation.

## Overview

We use a two-phase approach to maximize summary quality while maintaining coverage:

1. **Phase 1: Web Scraping (Ballotpedia)** - High quality, authoritative summaries
2. **Phase 2: AI Generation (Ollama)** - Fallback for measures without web-scraped summaries

## Quick Start

### Complete Workflow (Recommended)

Run the entire workflow with a single command:

```bash
make summaries
```

This will:
1. Scrape summaries from Ballotpedia (~286 unique URLs, ~14 minutes)
2. Generate AI summaries for remaining measures
3. Show final coverage statistics

### Individual Steps

You can also run each phase separately:

```bash
# Phase 1: Web scraping only
make summaries-web

# Phase 2: AI generation only
make summaries-ai
```

## Phase 1: Ballotpedia Scraping

### What it does

- Fetches summaries from Ballotpedia measure pages
- Extracts "Impartial analysis" and "Ballot question" sections
- Handles duplicate URLs efficiently (76% of measures are duplicates)
- Includes rate limiting with exponential backoff retry

### Features

**Optimizations:**
- Deduplicates URLs before fetching (286 unique vs 1,193 total)
- Propagates summaries to all duplicate entries automatically
- 76% reduction in requests = faster completion + less rate limiting

**Rate Limiting:**
- 3 second delay between requests
- Exponential backoff on HTTP 202: 10s, 20s, 40s
- Up to 3 retries per URL
- Respects Ballotpedia's server capacity

### Expected Results

- **Coverage**: ~40-60% of measures (depends on Ballotpedia availability)
- **Quality**: High - official "impartial analysis" from county/city clerks
- **Time**: ~14 minutes for 286 unique URLs

### Manual Usage

```bash
cd scraper
python scripts/update_ballotpedia_summaries_deduped.py
```

## Phase 2: AI Summary Generation

### What it does

- Generates summaries using Ollama (local, free AI)
- Creates 2-3 sentence neutral summaries
- Uses measure titles, descriptions, and ballot questions as input

### Prerequisites

1. **Install Ollama**: Download from [ollama.ai](https://ollama.ai)
2. **Pull a model**:
   ```bash
   ollama pull llama3.2
   ```
3. **Install Python package**:
   ```bash
   pip install ollama
   ```

### Model Options

When running the script, you can choose:

1. **llama3.2** (recommended) - Fast, accurate
2. **llama3.2:1b** - Faster, smaller, less accurate
3. **mistral** - Alternative model

### Quality Expectations

**Strengths:**
- 100% coverage (generates for all measures)
- Fast (3 seconds per measure)
- Consistent neutral tone
- Free and local (no API costs)

**Limitations:**
- Not as authoritative as official impartial analysis
- May lack nuanced details
- Based only on title/description (not full text)

### Manual Usage

```bash
cd scraper
python scripts/generate_ai_summaries.py
```

## Understanding the Data

### Summary Fields

Each measure can have three summary-related fields:

- **ballot_question**: The official question appearing on the ballot
- **summary_title**: Short 1-sentence summary (~150 chars)
- **summary_text**: Full 2-3 sentence summary (~150-300 chars)
- **has_summary**: Boolean flag (1 if any summary exists)

### Data Priority

The website displays summaries in this order:
1. `summary_text` (preferred)
2. `ballot_question` (if no summary_text)
3. `description` (if neither above)
4. `original_title` (last resort)

### Data Sources

Summaries are marked with their source:
- **Ballotpedia**: Web-scraped from official pages
- **AI**: Generated using Ollama

## Troubleshooting

### Ballotpedia Rate Limiting

**Symptom**: Many "⚠️ No summary found" messages after ~40 measures

**Causes**:
- HTTP 202 responses with empty content
- Too many requests too quickly

**Solutions**:
- Script now includes automatic retry with exponential backoff
- Increased delays (3s between requests, 5s every 10th)
- Deduplication reduces total requests by 76%

### Ollama Not Working

**Symptom**: "❌ Error: Ollama not installed"

**Solutions**:
1. Install Ollama from [ollama.ai](https://ollama.ai)
2. Make sure it's running: `ollama serve`
3. Pull a model: `ollama pull llama3.2`
4. Install Python package: `pip install ollama`

**Symptom**: "Cannot connect to Ollama"

**Solutions**:
- Start Ollama server: `ollama serve`
- Check it's running: `curl http://localhost:11434`

### Database Issues

**Symptom**: Duplicate measures with same URL but different years

**Explanation**: This is a known data quality issue. The scraper stored the same March 2020 measures as years 2020, 2022, 2024, and 2025.

**Impact**: The deduplicated script handles this automatically by updating all duplicates when it fetches a URL once.

## Performance

### Estimated Times

For a database with ~1,200 measures without summaries:

| Step | URLs/Measures | Time | Notes |
|------|---------------|------|-------|
| Ballotpedia scraping | 286 unique URLs | ~14 min | 3s per URL |
| AI generation | ~800 remaining | ~40 min | 3s per measure |
| **Total** | ~1,200 measures | **~54 min** | Full coverage |

### Optimization Tips

1. **Run during off-hours**: Less chance of Ballotpedia rate limiting
2. **Use faster AI model**: llama3.2:1b is 2x faster
3. **Run in background**: Both scripts show progress, can run in tmux/screen

## Next Steps

After running the summary workflow:

1. **Rebuild website**:
   ```bash
   make website
   ```

2. **Check coverage**:
   ```bash
   python -c "from src.database.operations import Database; \
              db = Database(); \
              stats = db.get_statistics(); \
              print(f'Summaries: {stats[\"with_summaries\"]}/{stats[\"total_measures\"]} ({stats[\"with_summaries\"]/stats[\"total_measures\"]*100:.1f}%)')"
   ```

3. **Review quality**:
   - Open `index.html` in browser
   - Check that summary cards display correctly
   - Verify AI summaries are reasonable

4. **Deploy**:
   ```bash
   git add .
   git commit -m "Add ballot measure summaries"
   git push
   ```

## Files

### Scripts

- `scripts/complete_summary_workflow.py` - Orchestrates both phases
- `scripts/update_ballotpedia_summaries_deduped.py` - Ballotpedia scraping (optimized)
- `scripts/generate_ai_summaries.py` - AI summary generation
- `scripts/analyze_duplicates.py` - Analyze database duplicates
- `scripts/debug_summary_failures.py` - Debug scraping issues

### Source Code

- `src/scrapers/ballotpedia_counties.py` - County scraper with summary extraction
- `src/scrapers/ballotpedia_statewide.py` - Statewide proposition scraper

### Makefile Commands

- `make summaries` - Complete workflow
- `make summaries-web` - Ballotpedia only
- `make summaries-ai` - AI only

## FAQ

**Q: Why two phases instead of just AI for everything?**

A: Ballotpedia summaries are higher quality (official impartial analysis from government sources) but don't cover all measures. AI fills the gaps.

**Q: Can I use a different AI model?**

A: Yes! Edit `generate_ai_summaries.py` and change the model name. Any Ollama model works.

**Q: Why 76% duplicates?**

A: The original scraper stored March 2020 elections under multiple years (2020, 2022, 2024, 2025). This is a data quality issue that should be fixed in the scraper.

**Q: Are AI summaries good enough?**

A: For basic information, yes. They're neutral and accurate based on the title/description. But official impartial analysis is more detailed and authoritative.

**Q: Can I run this regularly?**

A: Yes, but only for new measures. The scripts skip measures that already have summaries.

**Q: What if Ballotpedia changes their HTML?**

A: The scraper may break. Debug with `scripts/debug_summary_failures.py` and update the selectors in `ballotpedia_counties.py`.
