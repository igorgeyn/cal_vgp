# AI-Powered Title Generation

## Overview

This feature automatically generates concise, informative titles from long ballot measure text using Claude AI.

## Problem It Solves

Many California ballot measures have extremely long "titles" that are actually the full ballot question text - sometimes 200+ characters. This makes the website cards look messy and hard to scan.

**Example of a problematic title:**
```
202400533: To improve local high schools, upgrade vocational classrooms/labs/technology for skilled trades, science, engineering, math, aerospace education, practical career skills; fix deteriorating gas/sewer lines, leaky roofs, ensure safe drinking water; upgrade student/school safety; attract/retain quality teachers; shall Antelope Valley Union High School District's measure authorizing $398,000,000 in bonds at legal rates, levying 2 cents per $100 assessed value, raising $25,000,000 annually while bonds are outstanding, be adopted, with citizen oversight, spending disclosure, local control?
```

## How It Works

1. When generating the website, the system analyzes each measure's title
2. If a title is >150 characters or contains complex structure, it's flagged for generation
3. Claude Haiku generates a concise title (max 80 characters)
4. The generated title is cached to avoid re-generating
5. The card displays the short title, with the original text as the description

## Setup

### 1. Install Dependencies

```bash
pip install anthropic
```

Or install from requirements.txt:

```bash
pip install -r requirements.txt
```

### 2. Get an API Key

1. Go to https://console.anthropic.com/
2. Sign up or log in
3. Create an API key

### 3. Configure the API Key

**Option A: Environment Variable**
```bash
export ANTHROPIC_API_KEY='your-api-key-here'
```

**Option B: .env File (Recommended)**
```bash
cd scraper
echo "ANTHROPIC_API_KEY=your-api-key-here" >> .env
```

The system will automatically load from `.env` using python-dotenv.

## Usage

### Generate Titles for All Measures

```bash
python scripts/generate_titles.py
```

This will:
- Find all measures with long/complex titles
- Show you how many titles need generation
- Estimate the cost
- Ask for confirmation
- Generate and cache titles

### Rebuild Website with New Titles

```bash
python scripts/generate_site.py --force
```

The website generator automatically uses cached titles when building the site.

## Cost

- Uses Claude Haiku (cheapest model)
- ~$0.0001 per title generation
- Results are cached permanently
- Typical cost for 1000 titles: ~$0.10

## Storage and Persistence

Generated titles are stored in **two places** for maximum reliability:

### 1. Database (Primary Storage)
- Generated titles are saved to the database in the `generated_title` and `original_title` columns
- Persists permanently with the measure data
- Survives cache deletion
- Automatically loaded when generating the website

### 2. JSON Cache (Backup/Fast Lookup)
- Also cached in `data/title_cache.json`
- Provides fast lookups without database queries
- Can be deleted and regenerated from database
- Useful for sharing generated titles between systems

**How it works:**
1. Title is generated via Claude API
2. Saved to JSON cache immediately
3. If database connection available, also saved to database
4. On subsequent runs, loads from database first, then cache

## Fallback Behavior

**Without API Key:**
The website generator still works perfectly! If no API key is configured:
- Long titles are truncated using CSS (line-clamp)
- Cards still look clean and consistent
- No errors or warnings

**With API Key:**
- Titles are intelligently generated
- Original text becomes the description
- Better semantic understanding

## Examples

### Before (CSS Truncation)
```
Title: 202400533: To improve local high schools, upgrade vocational classrooms/labs/...
```

### After (AI Generation)
```
Title: School Bond Measure for Facility Improvements
Description: To improve local high schools, upgrade vocational classrooms/labs/technology for skilled trades, science, engineering, math, aerospace education, practical career skills; fix deteriorating gas/sewer lines...
```

## Technical Details

**Files:**
- `src/utils/title_generator.py` - Main title generation module
- `scripts/generate_titles.py` - Batch generation script
- `data/title_cache.json` - Cache storage (auto-created)

**Integration:**
The title generator is integrated into the website generation pipeline at [src/website/generator.py:75](src/website/generator.py#L75)

**Detection Logic:**
A title needs generation if:
- Length > 150 characters
- Contains > 2 semicolons
- Contains > 1 period

**Generation Prompt:**
```
Generate a concise, informative title (max 80 characters) for this
California ballot measure. The title should capture the main topic
and action. Respond with ONLY the title, no explanation.
```

## Troubleshooting

### "ANTHROPIC_API_KEY not found"
Set the environment variable or add to `.env` file (see Setup above)

### Titles not appearing on website
1. Check that titles were generated: `cat data/title_cache.json`
2. Rebuild website: `python scripts/generate_site.py --force`

### Cache is too large
The cache file is JSON and can grow large. You can safely delete it:
```bash
rm data/title_cache.json
```

Titles will be regenerated next time you run the generation script.

### Want to regenerate specific titles
Edit `data/title_cache.json` and remove the entries you want to regenerate, then rebuild.

## Future Enhancements

Potential improvements:
- Batch processing for better performance
- Topic classification from generated titles
- Multi-language support
- Custom prompt templates per topic
- Quality scoring for generated titles

---

**Last Updated:** 2026-01-09
**Model Used:** Claude Haiku (claude-3-haiku-20240307)
