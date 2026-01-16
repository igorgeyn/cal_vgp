# VGP Data Enrichment Implementation Prompt

## Context

I'm building a website (VGP - https://cal-vgp.igorgeyn.com/) that displays California ballot measure data. The database contains 10,861 measures from 1911-present with basic metadata (title, year, jurisdiction, vote percentages, pass/fail, topic classification).

The current display is sparse for historically significant measures. I want to enrich the data with:
1. **External links** to authoritative sources (Ballotpedia, CA Secretary of State, etc.)
2. **AI-generated summaries** for important measures
3. **Infrastructure** to support future enrichment

## Technical Stack (Verify Before Starting)

Before implementing, please examine the existing codebase to understand:
- Frontend framework (React? Vue? Plain JS?)
- Backend/database (Node? Python? What DB?)
- Current data schema for measures
- How existing AI summaries are stored and displayed
- Deployment setup

## Implementation Requirements

### Phase 1: Deterministic Link Generation

Create a link generation system that constructs external URLs from existing metadata. No scraping required.

**URL Patterns to Implement:**

```javascript
const LINK_SOURCES = {
  ballotpedia: {
    name: 'Ballotpedia',
    // Pattern: California_Proposition_13_(1978)
    generate: (measure) => {
      if (measure.jurisdiction !== 'state' || !measure.prop_number) return null;
      // Handle different naming conventions over time
      // Pre-1970s may use different formats
      return `https://ballotpedia.org/California_Proposition_${measure.prop_number}_(${measure.year})`;
    },
    // Only reliable for ~1970s onward
    confidence: (measure) => measure.year >= 1970 ? 'high' : 'medium'
  },
  
  sos_vig: {
    name: 'CA Secretary of State (Voter Guide)',
    // Archive of official voter information guides
    generate: (measure) => {
      if (measure.jurisdiction !== 'state') return null;
      // Archive structure varies by year - may need year-specific logic
      return `https://vigarchive.sos.ca.gov/${measure.year}/`;
    },
    confidence: (measure) => measure.year >= 1996 ? 'high' : 'low'
  },
  
  uc_hastings: {
    name: 'UC Hastings Ballot Props Database',
    // Academic repository with analysis
    generate: (measure) => {
      if (measure.jurisdiction !== 'state') return null;
      // Search-based URL since direct linking is complex
      return `https://repository.uclawsf.edu/ca_ballot_props/?search=${encodeURIComponent(measure.title)}`;
    },
    confidence: () => 'medium'
  },
  
  wikipedia_search: {
    name: 'Wikipedia',
    // Only for famous measures - search URL
    generate: (measure) => {
      if (measure.jurisdiction !== 'state') return null;
      const query = `California Proposition ${measure.prop_number} ${measure.year}`;
      return `https://en.wikipedia.org/wiki/Special:Search?search=${encodeURIComponent(query)}`;
    },
    confidence: () => 'low' // Just a search, may not have article
  }
};
```

**Requirements:**
1. Create a utility function/module for link generation
2. Add a database field or computed property for external links
3. Display links on measure detail pages with source attribution
4. Handle edge cases:
   - Measures without proposition numbers
   - County/local measures (most sources won't have coverage)
   - Historical measures with different naming conventions
   - Special elections vs. general elections

**UI Considerations:**
- Group links under "External Resources" or "Learn More"
- Show source name and indicate confidence level subtly (e.g., "Official source" vs. "Search results")
- Open links in new tab
- Consider lazy validation (check if link 404s on first click, cache result)

### Phase 2: Tiered AI Summarization

Implement a system to generate and store AI summaries for important measures.

**Tiering Logic:**

```javascript
const MEASURE_TIERS = {
  // Tier 1: Landmark measures - rich summaries, manually curated list
  LANDMARK: {
    tier: 1,
    measures: [
      // Famous propositions - expand this list
      { year: 1978, prop: 13, name: 'Property Tax Limitation' },
      { year: 1994, prop: 187, name: 'Illegal Immigration' },
      { year: 1996, prop: 209, name: 'Affirmative Action Ban' },
      { year: 1996, prop: 215, name: 'Medical Marijuana' },
      { year: 2000, prop: 22, name: 'Marriage Definition' },
      { year: 2008, prop: 8, name: 'Same-Sex Marriage Ban' },
      { year: 2010, prop: 14, name: 'Open Primary' },
      { year: 2012, prop: 30, name: 'Tax Increase for Education' },
      { year: 2014, prop: 47, name: 'Criminal Sentencing Reform' },
      { year: 2016, prop: 64, name: 'Recreational Marijuana' },
      { year: 2020, prop: 22, name: 'Gig Worker Classification' },
      { year: 2024, prop: 36, name: 'Criminal Sentencing Changes' },
      // Add more...
    ],
    summaryLength: 'detailed' // 3-4 sentences
  },
  
  // Tier 2: State propositions post-1970
  STATE_MODERN: {
    tier: 2,
    filter: (m) => m.jurisdiction === 'state' && m.year >= 1970,
    summaryLength: 'standard' // 2-3 sentences
  },
  
  // Tier 3: State propositions pre-1970
  STATE_HISTORICAL: {
    tier: 3,
    filter: (m) => m.jurisdiction === 'state' && m.year < 1970,
    summaryLength: 'brief' // 1-2 sentences
  },
  
  // Tier 4: County/local measures - no summary by default
  LOCAL: {
    tier: 4,
    filter: (m) => m.jurisdiction !== 'state',
    summaryLength: null
  }
};
```

**AI Summary Generation:**

Create a script/function to generate summaries using the Anthropic API (or adapt if using a different provider).

```javascript
const SUMMARY_PROMPT_TEMPLATE = `You are helping create factual, neutral descriptions of California ballot measures for a public information website.

Given this ballot measure:
- Title: {title}
- Year: {year}
- Jurisdiction: {jurisdiction}
- Proposition Number: {prop_number}
- Result: {result} ({yes_pct}% Yes, {no_pct}% No)
- Topic Category: {topic}

Generate a {length_instruction} summary that explains:
1. What the measure proposed to do
2. Key context (why it was on the ballot, who supported/opposed it if notable)
3. The outcome and any significant lasting effects

Guidelines:
- Be factual and politically neutral
- Use past tense for historical measures
- Don't editorialize about whether it was good or bad policy
- If you're uncertain about details, keep the summary more general
- For famous/controversial measures, briefly note the significance

{length_instruction_detail}`;

const LENGTH_INSTRUCTIONS = {
  detailed: {
    instruction: 'detailed (3-4 sentences)',
    detail: 'Include context about the political environment and lasting impact.'
  },
  standard: {
    instruction: 'standard (2-3 sentences)',
    detail: 'Focus on what it proposed and the outcome.'
  },
  brief: {
    instruction: 'brief (1-2 sentences)',
    detail: 'Just explain what it proposed and whether it passed.'
  }
};
```

**Requirements:**
1. Add database field for AI summary (text) and summary metadata (generated_at, model_version, tier)
2. Create a batch script to generate summaries by tier
3. Include rate limiting and error handling for API calls
4. Store summaries with clear provenance (when generated, what model)
5. Display summaries with "AI-generated summary" label
6. Create admin/CLI tool to regenerate individual summaries if needed

**Cost Management:**
- Start with Tier 1 only (~50 measures)
- Add Tier 2 in batches
- Log API usage/costs
- Consider caching prompts if regenerating

### Phase 3: Future Infrastructure (Lower Priority)

Set up infrastructure for ongoing enrichment:

1. **User suggestion system:**
   - "Suggest a resource" button on measure pages
   - Simple form: URL, description, submitter email (optional)
   - Store in review queue table
   - Basic admin view to approve/reject

2. **Analytics hooks:**
   - Track page views per measure
   - After 1-2 months, identify high-traffic measures for prioritization

3. **Summary regeneration pipeline:**
   - Flag for "needs review" on summaries
   - Bulk regeneration capability when improving prompts

## Database Schema Additions

Suggest appropriate schema changes based on the existing database structure. Likely needs:

```sql
-- If using SQL, something like:
ALTER TABLE measures ADD COLUMN ai_summary TEXT;
ALTER TABLE measures ADD COLUMN ai_summary_generated_at TIMESTAMP;
ALTER TABLE measures ADD COLUMN ai_summary_tier INTEGER;

-- For user suggestions (new table)
CREATE TABLE resource_suggestions (
  id SERIAL PRIMARY KEY,
  measure_id INTEGER REFERENCES measures(id),
  suggested_url TEXT NOT NULL,
  description TEXT,
  submitter_email TEXT,
  status TEXT DEFAULT 'pending', -- pending, approved, rejected
  created_at TIMESTAMP DEFAULT NOW(),
  reviewed_at TIMESTAMP,
  reviewer_notes TEXT
);

-- For caching link validation
CREATE TABLE external_link_cache (
  measure_id INTEGER,
  source_key TEXT,
  url TEXT,
  is_valid BOOLEAN,
  last_checked TIMESTAMP,
  PRIMARY KEY (measure_id, source_key)
);
```

## Implementation Order

1. **First:** Examine existing codebase structure
2. **Second:** Implement link generation (Phase 1) - immediate value, no API costs
3. **Third:** Add Tier 1 landmark measure list and summary generation
4. **Fourth:** UI updates to display links and summaries
5. **Fifth:** Expand to Tier 2 summaries if Phase 1-4 work well
6. **Later:** User suggestion infrastructure

## Important Notes

- **Conservative approach:** Keep summaries factual and descriptive, not analytical. This is a public information tool, not a research platform.
- **Clear labeling:** All AI-generated content should be clearly marked as such.
- **Graceful degradation:** Measures without summaries or links should still display well with existing data.
- **No scraping:** All external links are generated URLs, not scraped content. Respect robots.txt and ToS.
- **Error handling:** External links may 404 - handle gracefully in UI.

## Questions to Answer Before Starting

1. What's the current tech stack? (Examine package.json, requirements.txt, etc.)
2. How is the database accessed? (ORM? Raw queries?)
3. Where are the ~4 existing AI summaries stored?
4. Is there an existing admin interface?
5. How is the site deployed? (Vercel? AWS? etc.)
6. Are there environment variables for API keys already?

Please start by examining the codebase structure and confirming the tech stack, then proceed with implementation.
