# AI Title Generation - Multi-Provider Support

## Overview

The title generator now supports **3 different AI providers** with automatic fallback:

1. **Ollama** (local, free) - DEFAULT
2. **Groq** (cloud, free)
3. **Claude** (cloud, paid) - highest quality

## Quick Start

### Option 1: Ollama (Recommended - Free & Private)

```bash
# Install Ollama
brew install ollama

# Pull a small, fast model
ollama pull llama3.2:3b

# That's it! The system will auto-detect Ollama
python scripts/generate_titles.py
```

### Option 2: Groq (Free Cloud API)

```bash
# Get free API key from https://console.groq.com
export GROQ_API_KEY='your-key-here'

# Install client
pip install groq

# Generate titles
python scripts/generate_titles.py
```

### Option 3: Claude (Paid, Highest Quality)

```bash
# Get API key from https://console.anthropic.com
export ANTHROPIC_API_KEY='your-key-here'

# Install client
pip install anthropic

# Generate titles
python scripts/generate_titles.py
```

## Provider Comparison

| Provider | Cost | Speed | Quality | Privacy | Setup |
|----------|------|-------|---------|---------|-------|
| **Ollama** | Free | Fast (~2s) | Good | 100% Local | Easy |
| **Groq** | Free | Very Fast (<1s) | Good | Cloud | Easy |
| **Claude** | ~$0.0001/title | Medium (~1s) | Excellent | Cloud | Easy |

### Detailed Comparison

**Ollama (llama3.2:3b)**
- ✅ Completely free
- ✅ Runs offline
- ✅ Perfect privacy - data never leaves your machine
- ✅ Fast (1-2 seconds per title)
- ✅ No API limits
- ⚠️ Requires ~2GB disk space for model
- ⚠️ Quality slightly below Claude

**Groq (llama-3.2-3b-preview)**
- ✅ Free tier (very generous limits)
- ✅ Blazing fast (<1 second per title)
- ✅ No local installation
- ✅ Quality comparable to Ollama
- ⚠️ Data sent to third party
- ⚠️ Rate limits (but very high)

**Claude (claude-3-haiku-20240307)**
- ✅ Highest quality titles
- ✅ Most reliable formatting
- ✅ Best at understanding nuance
- ⚠️ Costs ~$0.0001 per title (~$0.10 for 1000 titles)
- ⚠️ Data sent to third party
- ⚠️ API rate limits

## Configuration

### Set Preferred Provider

```bash
# Let system auto-select (priority: ollama > groq > claude)
export TITLE_GENERATION_PROVIDER=auto

# Force specific provider
export TITLE_GENERATION_PROVIDER=ollama
export TITLE_GENERATION_PROVIDER=groq
export TITLE_GENERATION_PROVIDER=claude
```

### Model Selection

```bash
# Ollama model
export OLLAMA_MODEL=llama3.2:3b  # or llama3.2:1b for faster

# Groq model
export GROQ_MODEL=llama-3.2-3b-preview  # or llama-3.2-11b-vision-preview

# Claude model
export CLAUDE_MODEL=claude-3-haiku-20240307  # or claude-3-5-sonnet-20241022
```

### Custom Ollama URL

```bash
# If running Ollama on different host/port
export OLLAMA_API_URL=http://192.168.1.100:11434
```

## Compare Providers

Before committing to one provider, run a comparison test:

```bash
python scripts/compare_title_providers.py
```

This will:
1. Ask how many titles to test (default: 50)
2. Generate titles with ALL available providers
3. Show side-by-side comparison
4. Save detailed results to `data/title_comparison_YYYYMMDD_HHMMSS.json`
5. Show cost estimates

**Example output:**
```
[1/50] 202400533 (2024)
  Original: To improve local high schools, upgrade vocational classrooms/labs/...
  ollama  : School Bond for Vocational Education and Infrastructure
  groq    : High School Infrastructure and Vocational Education Bond
  claude  : School Bond Measure for Facility Improvements
```

### Cost for Comparison

Testing 50 measures with all 3 providers:
- Ollama: $0.00
- Groq: $0.00
- Claude: ~$0.005 ($0.0001 × 50)
- **Total: ~$0.01**

Testing 500 measures (up to your $5 budget):
- Would cost ~$0.05 with Claude
- Free with Ollama/Groq

## Usage Examples

### Generate All Titles (Auto Provider)

```bash
python scripts/generate_titles.py
```

### Generate with Specific Provider

```bash
TITLE_GENERATION_PROVIDER=ollama python scripts/generate_titles.py
```

### Compare Quality First

```bash
# Test 100 random measures across all providers
python scripts/compare_title_providers.py
# Enter: 100

# Review results, then pick your favorite
export TITLE_GENERATION_PROVIDER=ollama

# Generate all titles
python scripts/generate_titles.py
```

## Integration with Website

The website generator automatically uses generated titles:

```bash
# Generate website (uses titles from database)
python scripts/generate_site.py --force
```

Provider selection is only used during title generation, not website building.

## Troubleshooting

### "No AI providers available"

**Solution:** Install at least one provider:

```bash
# Easiest: Ollama
brew install ollama
ollama pull llama3.2:3b

# Or: Groq
export GROQ_API_KEY='your-key'
pip install groq

# Or: Claude
export ANTHROPIC_API_KEY='your-key'
pip install anthropic
```

### Ollama not detected

```bash
# Make sure Ollama is running
ollama list

# If not installed:
brew install ollama
ollama pull llama3.2:3b

# Check if server is running
curl http://localhost:11434/api/tags
```

### Groq rate limit errors

Groq has generous free tier limits, but if you hit them:
- Wait a few minutes
- Switch to Ollama (unlimited)
- Or use Claude

### Low quality titles

Try a larger/better model:

```bash
# Ollama - use larger model
ollama pull llama3.2:11b
export OLLAMA_MODEL=llama3.2:11b

# Groq - use larger model
export GROQ_MODEL=llama-3.2-11b-vision-preview

# Claude - use better model (more expensive)
export CLAUDE_MODEL=claude-3-5-sonnet-20241022
```

## Recommendations

**For most users:**
Use **Ollama** (llama3.2:3b)
- Free, fast, private
- Good quality
- No limits

**If you don't want to install locally:**
Use **Groq** (free API)
- Fastest
- Free
- Good quality

**If you need highest quality:**
Use **Claude** for final production titles
- Test 50-100 with comparison script first
- Cost: ~$0.10 for 1000 titles

**Best workflow:**
1. Run comparison on 50-100 measures
2. Pick your preferred provider
3. Generate all titles
4. Review a few manually
5. Adjust provider if needed

## Advanced: Running Multiple Providers

You can have all three set up simultaneously:

```bash
# .env file
OLLAMA_API_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:3b
GROQ_API_KEY=your_groq_key
GROQ_MODEL=llama-3.2-3b-preview
ANTHROPIC_API_KEY=your_anthropic_key
CLAUDE_MODEL=claude-3-haiku-20240307

# System will auto-select: ollama > groq > claude
TITLE_GENERATION_PROVIDER=auto
```

Then compare them anytime:
```bash
python scripts/compare_title_providers.py
```

---

**Last Updated:** 2026-01-09
**Supported Providers:** Ollama, Groq, Claude
