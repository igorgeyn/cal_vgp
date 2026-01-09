# Database Migration - Generated Titles

## Overview

The database schema has been updated to support AI-generated titles for ballot measures.

## Schema Changes

Two new columns have been added to the `measures` table:

```sql
-- AI-generated content
generated_title TEXT,    -- Short, AI-generated title (max 80 chars)
original_title TEXT,     -- Original title before generation
```

## Migration Process

The database migration is **automatic**. When you run any script that uses the database, it will:

1. Detect missing columns
2. Add `generated_title` and `original_title` columns automatically
3. Log the changes

No manual migration needed!

## How to Populate Generated Titles

### Option 1: Generate and Store in One Step

```bash
# Set your API key
export ANTHROPIC_API_KEY='your-key-here'

# Generate website (also saves to database)
python scripts/generate_site.py --force
```

When the website generator runs with an API key configured, it will:
- Generate titles for measures that need them
- Save to JSON cache (`data/title_cache.json`)
- Save to database (`measures` table)

### Option 2: Use the Dedicated Title Generation Script

```bash
# Generate all titles and show progress
python scripts/generate_titles.py

# Update database from cache
python scripts/update_generated_titles.py
```

This approach gives you:
- Progress tracking
- Cost estimates before running
- Confirmation prompt
- Better control over the process

## Verification

Check if titles were saved to database:

```bash
sqlite3 data/ballot_measures.db "SELECT COUNT(*) FROM measures WHERE generated_title IS NOT NULL"
```

View some examples:

```bash
sqlite3 data/ballot_measures.db "SELECT measure_id, generated_title, SUBSTR(original_title, 1, 80) FROM measures WHERE generated_title IS NOT NULL LIMIT 10"
```

## Data Flow

```
1. AI Generation (Claude Haiku API)
   ↓
2. JSON Cache (data/title_cache.json)
   ↓
3. Database (measures.generated_title, measures.original_title)
   ↓
4. Website (uses generated_title if available)
```

## Rollback

If you want to remove generated titles:

```sql
-- Remove all generated titles
UPDATE measures SET generated_title = NULL, original_title = NULL;
```

Or delete specific ones:

```sql
-- Remove for specific measure
UPDATE measures
SET generated_title = NULL, original_title = NULL
WHERE measure_id = '202400533';
```

## Benefits

**Before database integration:**
- Titles only in JSON cache
- Lost if cache deleted
- Not searchable in database queries

**After database integration:**
- Permanently stored with measure data
- Survives cache deletion
- Can query by generated title
- Automatic schema migration
- Dual storage (cache + database)

## Files Modified

- `src/database/models.py` - Added fields to BallotMeasure model and schema
- `src/database/operations.py` - Added columns to expected_columns check
- `src/utils/title_generator.py` - Added database persistence
- `src/website/generator.py` - Passes database to title generator
- `scripts/update_generated_titles.py` - NEW: Sync cache to database

---

**Last Updated:** 2026-01-09
**Schema Version:** 2.1.0
