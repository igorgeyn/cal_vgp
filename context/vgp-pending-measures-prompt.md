# VGP Pending Measures Enhancement Implementation Prompt

## Context

I'm building a website (VGP - https://cal-vgp.igorgeyn.com/) that displays California ballot measure data. The site contains 10,861 measures from 1911-present.

**The problem:** Upcoming/pending 2026 measures are where users need the most help (researching before voting), but they currently have the least content. Example current state:

- Title: "Assembly Bill 440, Chapter 82, Statutes of 2024"
- Year: 2026
- Status: "PENDING"
- Summary: "No summary available for this measure"
- Links: Only "Full Ballot Text (PDF)"
- No vote data (hasn't happened yet)

**Goal:** Transform pending measure pages from sparse placeholders into genuinely useful voter resources, while maintaining strict political neutrality and being honest about information limitations.

## Technical Stack Discovery

Before implementing, examine the existing codebase to understand:
- Frontend framework and component structure
- How measures are currently rendered (card component? detail page?)
- How status/pending is determined and stored
- Current link generation system (from previous enrichment work)
- How AI summaries are stored and displayed
- Any existing differentiation between pending/historical measures

## Implementation Phases

---

### Phase 1: Visual Differentiation & Messaging (Priority: High, Effort: Low)

**Goal:** Make pending measures visually distinct and reframe "no content" as "content coming."

#### 1.1 Status Badge System

Create/update a status badge component:

```jsx
// Example React component structure
const MeasureStatusBadge = ({ status, electionDate }) => {
  if (status === 'PENDING') {
    const daysUntil = calculateDaysUntil(electionDate);
    return (
      <div className="status-badge pending">
        <span className="badge-icon">🗳️</span>
        <span className="badge-text">On November 2026 Ballot</span>
        {daysUntil && <span className="badge-countdown">{daysUntil} days away</span>}
      </div>
    );
  }
  
  if (status === 'PASSED') {
    return <div className="status-badge passed">✓ Passed</div>;
  }
  
  if (status === 'FAILED') {
    return <div className="status-badge failed">✗ Failed</div>;
  }
  
  return null;
};
```

**Styling guidance:**
- Pending: Blue or amber accent color, forward-looking
- Passed: Green accent
- Failed: Gray or muted red
- Make pending badges more prominent than historical status

#### 1.2 Reframe Empty Content States

Replace generic "No summary available" with contextual messaging:

```javascript
const PENDING_CONTENT_MESSAGES = {
  summary: {
    empty: "Summary in development",
    detail: "A plain-language summary will be added as we review the official ballot text.",
    cta: "See official sources below for the full ballot language."
  },
  
  fiscalImpact: {
    empty: "Fiscal analysis pending",
    detail: "The Legislative Analyst's Office typically publishes fiscal impact analyses in the months before an election.",
    cta: "Check the LAO website for updates.",
    expectedDate: "Expected: Q1-Q2 2026"
  },
  
  proConArguments: {
    empty: "Official arguments not yet available",
    detail: "Pro and con arguments are published in the Official Voter Information Guide approximately 10 weeks before the election.",
    cta: "The voter guide will be available at voterguide.sos.ca.gov",
    expectedDate: "Expected: August 2026"
  },
  
  voteData: {
    // Don't show vote sections at all for pending measures
    // Or show: "Election: November 3, 2026"
  }
};
```

#### 1.3 Information Hierarchy Changes

For pending measures, reorder content to prioritize decision-making:

```
HISTORICAL MEASURE ORDER:          PENDING MEASURE ORDER:
1. Title + Year                    1. Title + Election Date Badge
2. Vote Results (Yes/No %)         2. "What This Measure Does" (Summary)
3. Outcome (Passed/Failed)         3. How It Qualified (Legislative/Initiative)
4. Summary                         4. Fiscal Impact (or "Coming soon")
5. Topic Category                  5. Official Sources (Prominent)
6. External Links                  6. Pro/Con Arguments (When available)
                                   7. Related Past Measures
                                   8. Timeline/What to Expect
```

#### 1.4 Hide Irrelevant Sections

For pending measures, conditionally hide or adapt:

```javascript
const MeasureDetail = ({ measure }) => {
  const isPending = measure.status === 'PENDING';
  
  return (
    <div className="measure-detail">
      <MeasureHeader measure={measure} />
      
      {/* Always show */}
      <MeasureSummary measure={measure} isPending={isPending} />
      <MeasureQualificationPath measure={measure} />
      
      {/* Show different content based on status */}
      {isPending ? (
        <>
          <PendingFiscalImpact measure={measure} />
          <PendingArgumentsPreview measure={measure} />
          <OfficialSourcesSection measure={measure} prominent={true} />
          <RelatedPastMeasures measure={measure} />
          <ElectionTimeline measure={measure} />
        </>
      ) : (
        <>
          <VoteResults measure={measure} />
          <ExternalLinks measure={measure} />
        </>
      )}
      
      {/* Always show for pending */}
      {isPending && <PendingMeasureDisclaimer />}
    </div>
  );
};
```

---

### Phase 2: Deterministic Link Enrichment for Pending Measures (Priority: High, Effort: Low)

**Goal:** Generate useful links to authoritative sources without scraping.

#### 2.1 Official Source Links

```javascript
const PENDING_MEASURE_SOURCES = {
  // California Secretary of State - Primary authority
  sos_qualified: {
    name: 'CA Secretary of State',
    description: 'Official ballot measure status and text',
    url: 'https://www.sos.ca.gov/elections/ballot-measures/qualified-ballot-measures',
    type: 'official',
    icon: '🏛️',
    priority: 1
  },
  
  // Legislative Analyst's Office - Nonpartisan fiscal analysis
  lao: {
    name: 'Legislative Analyst\'s Office',
    description: 'Nonpartisan fiscal impact analysis',
    generate: (measure) => {
      // LAO organizes by election year
      return `https://lao.ca.gov/BallotAnalysis/Propositions?year=${measure.year}`;
    },
    type: 'official',
    icon: '📊',
    priority: 2,
    note: 'Fiscal analyses typically available several months before election'
  },
  
  // For legislatively-referred measures, link to the bill
  legislature: {
    name: 'CA Legislature - Bill Details',
    description: 'Full bill text, history, and committee analyses',
    generate: (measure) => {
      // Extract bill info if available (e.g., "AB 440" or "SB 1234")
      const billMatch = measure.title?.match(/(A|S)\.?B\.?\s*(\d+)/i) ||
                        measure.description?.match(/(A|S)\.?B\.?\s*(\d+)/i);
      
      if (billMatch) {
        const chamber = billMatch[1].toUpperCase() === 'A' ? 'ab' : 'sb';
        const number = billMatch[2];
        // Session year logic - adjust based on your data
        const session = getSessionYear(measure.year);
        return `https://leginfo.legislature.ca.gov/faces/billNavClient.xhtml?bill_id=${session}0${chamber.toUpperCase()}${number}`;
      }
      return null;
    },
    type: 'official',
    icon: '📜',
    priority: 3,
    condition: (measure) => measure.qualification_type === 'legislative'
  },
  
  // Official Voter Guide (when available)
  voter_guide: {
    name: 'Official Voter Information Guide',
    description: 'Pro/con arguments, full text, fiscal analysis',
    url: 'https://voterguide.sos.ca.gov/',
    type: 'official',
    icon: '📖',
    priority: 4,
    availableDate: 'August 2026',
    note: 'Available approximately 10 weeks before election'
  },
  
  // Voter's Edge - League of Women Voters + MapLight
  voters_edge: {
    name: 'Voter\'s Edge California',
    description: 'Nonpartisan voter guide with endorsements and funding info',
    url: 'https://votersedge.org/ca',
    type: 'nonpartisan',
    icon: '✓',
    priority: 5
  },
  
  // Ballotpedia
  ballotpedia: {
    name: 'Ballotpedia',
    description: 'Background, endorsements, and campaign information',
    generate: (measure) => {
      // Try to construct specific measure URL
      if (measure.prop_number) {
        return `https://ballotpedia.org/California_Proposition_${measure.prop_number}_(${measure.year})`;
      }
      // Fallback to year overview
      return `https://ballotpedia.org/California_${measure.year}_ballot_propositions`;
    },
    type: 'nonpartisan',
    icon: 'ⓘ',
    priority: 6
  },
  
  // CalMatters - Nonpartisan journalism
  calmatters: {
    name: 'CalMatters Voter Guide',
    description: 'Nonpartisan news coverage and analysis',
    generate: (measure) => {
      return `https://calmatters.org/california-voter-guide-${measure.year}/`;
    },
    type: 'journalism',
    icon: '📰',
    priority: 7,
    note: 'Typically available closer to election'
  },
  
  // Campaign finance - CAL-ACCESS
  cal_access: {
    name: 'CAL-ACCESS Campaign Finance',
    description: 'Campaign contributions and expenditures',
    url: 'https://cal-access.sos.ca.gov/Campaign/Measures/',
    type: 'official',
    icon: '💰',
    priority: 8,
    note: 'See who is funding campaigns for and against'
  }
};

// Helper function to get legislative session year
function getSessionYear(electionYear) {
  // California legislative sessions are two years
  // 2025-2026 session = "20252026"
  // 2023-2024 session = "20232024"
  const sessionStart = electionYear % 2 === 0 ? electionYear - 1 : electionYear;
  return `${sessionStart}${sessionStart + 1}`;
}
```

#### 2.2 Link Display Component

```jsx
const OfficialSourcesSection = ({ measure, prominent = false }) => {
  const links = generatePendingMeasureLinks(measure);
  
  // Sort by priority
  const sortedLinks = links.sort((a, b) => a.priority - b.priority);
  
  // Split into available now vs coming later
  const availableNow = sortedLinks.filter(l => !l.availableDate);
  const comingSoon = sortedLinks.filter(l => l.availableDate);
  
  return (
    <section className={`sources-section ${prominent ? 'prominent' : ''}`}>
      <h3>📚 Official & Nonpartisan Sources</h3>
      
      <div className="sources-grid">
        {availableNow.map(link => (
          <a 
            href={link.url} 
            target="_blank" 
            rel="noopener noreferrer"
            className={`source-link source-${link.type}`}
            key={link.name}
          >
            <span className="source-icon">{link.icon}</span>
            <div className="source-info">
              <span className="source-name">{link.name}</span>
              <span className="source-desc">{link.description}</span>
            </div>
            <span className="external-icon">↗</span>
          </a>
        ))}
      </div>
      
      {comingSoon.length > 0 && (
        <div className="coming-soon-sources">
          <h4>📅 Coming Later</h4>
          {comingSoon.map(link => (
            <div className="source-preview" key={link.name}>
              <span>{link.icon} {link.name}</span>
              <span className="availability">Available: {link.availableDate}</span>
            </div>
          ))}
        </div>
      )}
    </section>
  );
};
```

---

### Phase 3: AI Summaries for Pending Measures (Priority: High, Effort: Medium)

**Goal:** Generate neutral, voter-focused summaries that help people understand what they're voting on.

#### 3.1 Pending-Specific Summary Prompt

```javascript
const PENDING_MEASURE_SUMMARY_PROMPT = `You are helping create factual, neutral descriptions of upcoming California ballot measures for a nonpartisan voter information website.

**Measure Information:**
- Title: {title}
- Election: {election_date}
- Type: {qualification_type} (legislative measure / initiative / referendum)
- Official Ballot Label: {ballot_label}
- Available Text/Description: {text_excerpt}

**Generate a voter-focused summary with these sections:**

## What This Measure Would Do
[2-3 sentences in plain language explaining what changes if voters approve this measure. Use "would" language since it hasn't passed yet.]

## How It Qualified for the Ballot
[1 sentence: Was this placed on the ballot by the Legislature, or did it qualify through signature gathering? Include bill number if legislative.]

## A YES Vote Means
[1 sentence: What happens if you vote yes]

## A NO Vote Means  
[1 sentence: What happens if you vote no]

**Strict Guidelines - Follow These Exactly:**
- Be strictly neutral - do NOT advocate for or against
- Use present/future tense ("This measure would..." not "This measure will...")
- Use plain language accessible to general voters (8th grade reading level)
- Do NOT include arguments for or against
- Do NOT speculate about likelihood of passage
- Do NOT mention polls, endorsements, or campaign activity
- If fiscal impact is officially known (from LAO), include a brief mention
- If you're uncertain about any detail, be more general rather than guessing
- Do NOT editorialize with words like "controversial," "important," "significant"

**Formatting:**
- Use the exact section headers shown above
- Keep each section concise (1-3 sentences max)
- Total length: 150-250 words`;

// For measures with very limited information
const MINIMAL_INFO_PROMPT = `You are helping create a brief, factual description of an upcoming California ballot measure. You have limited information available.

**Available Information:**
- Title: {title}
- Election Year: {year}
- Any additional context: {additional_context}

**Generate a brief summary:**
- 2-3 sentences maximum
- Explain what the measure appears to address based on its title
- Clearly indicate that full details will be available closer to the election
- Do NOT speculate beyond what the title suggests
- Be strictly neutral

**Example format:**
"This measure addresses [topic based on title]. [Brief explanation if title is clear enough]. Full ballot language and official analysis will be available from the California Secretary of State as the election approaches."`;
```

#### 3.2 Summary Generation Script

```javascript
// batch-generate-pending-summaries.js

const Anthropic = require('@anthropic-ai/sdk');

const client = new Anthropic();

async function generatePendingSummary(measure) {
  // Determine which prompt to use based on available info
  const hasDetailedInfo = measure.ballot_text || measure.description?.length > 100;
  
  const prompt = hasDetailedInfo 
    ? PENDING_MEASURE_SUMMARY_PROMPT
        .replace('{title}', measure.title)
        .replace('{election_date}', `November ${measure.year}`)
        .replace('{qualification_type}', measure.qualification_type || 'ballot measure')
        .replace('{ballot_label}', measure.ballot_label || measure.title)
        .replace('{text_excerpt}', truncate(measure.ballot_text || measure.description, 2000))
    : MINIMAL_INFO_PROMPT
        .replace('{title}', measure.title)
        .replace('{year}', measure.year)
        .replace('{additional_context}', measure.description || 'None available');

  try {
    const response = await client.messages.create({
      model: 'claude-sonnet-4-20250514',
      max_tokens: 500,
      messages: [{ role: 'user', content: prompt }]
    });
    
    return {
      summary: response.content[0].text,
      generated_at: new Date().toISOString(),
      model: 'claude-sonnet-4-20250514',
      prompt_type: hasDetailedInfo ? 'detailed' : 'minimal',
      measure_id: measure.id
    };
  } catch (error) {
    console.error(`Error generating summary for measure ${measure.id}:`, error);
    return null;
  }
}

async function batchGenerateSummaries(measures, options = {}) {
  const { 
    delayMs = 500,  // Rate limiting
    dryRun = false,
    onProgress = () => {}
  } = options;
  
  const results = [];
  
  for (let i = 0; i < measures.length; i++) {
    const measure = measures[i];
    
    onProgress({ current: i + 1, total: measures.length, measure: measure.title });
    
    if (dryRun) {
      console.log(`[DRY RUN] Would generate summary for: ${measure.title}`);
      continue;
    }
    
    const result = await generatePendingSummary(measure);
    if (result) {
      results.push(result);
      // Save to database here
      await saveSummaryToDatabase(result);
    }
    
    // Rate limiting
    if (i < measures.length - 1) {
      await sleep(delayMs);
    }
  }
  
  return results;
}

// Run for all pending 2026 measures
async function main() {
  const pendingMeasures = await getPendingMeasures(2026);
  console.log(`Found ${pendingMeasures.length} pending measures for 2026`);
  
  await batchGenerateSummaries(pendingMeasures, {
    dryRun: process.argv.includes('--dry-run'),
    onProgress: ({ current, total, measure }) => {
      console.log(`[${current}/${total}] Processing: ${measure}`);
    }
  });
}
```

#### 3.3 Summary Display with Clear Attribution

```jsx
const PendingMeasureSummary = ({ measure }) => {
  const { ai_summary, ai_summary_generated_at } = measure;
  
  if (!ai_summary) {
    return (
      <div className="summary-placeholder">
        <p className="placeholder-message">
          Summary in development. See official sources below for the full ballot language.
        </p>
      </div>
    );
  }
  
  // Parse structured summary (with ## headers) into sections
  const sections = parseSummarySections(ai_summary);
  
  return (
    <div className="pending-summary">
      {sections.whatItDoes && (
        <div className="summary-section primary">
          <h3>What This Measure Would Do</h3>
          <p>{sections.whatItDoes}</p>
        </div>
      )}
      
      {sections.howQualified && (
        <div className="summary-section">
          <h4>How It Qualified</h4>
          <p>{sections.howQualified}</p>
        </div>
      )}
      
      <div className="yes-no-container">
        {sections.yesVote && (
          <div className="vote-meaning yes">
            <strong>A YES Vote Means:</strong>
            <p>{sections.yesVote}</p>
          </div>
        )}
        {sections.noVote && (
          <div className="vote-meaning no">
            <strong>A NO Vote Means:</strong>
            <p>{sections.noVote}</p>
          </div>
        )}
      </div>
      
      <div className="summary-attribution">
        <span className="ai-label">✨ AI-generated summary</span>
        <span className="summary-date">
          Last updated: {formatDate(ai_summary_generated_at)}
        </span>
        <a href="#official-sources" className="verify-link">
          Verify with official sources ↓
        </a>
      </div>
    </div>
  );
};
```

---

### Phase 4: 2026 Ballot Landing Page (Priority: Medium, Effort: Medium)

**Goal:** Create a dedicated hub for the upcoming election that's bookmarkable and shareable.

#### 4.1 Page Structure

```jsx
// pages/ballot/2026.jsx (or equivalent for your framework)

const Ballot2026Page = () => {
  const { measures, loading } = usePendingMeasures(2026);
  const electionDate = new Date('2026-11-03');
  const daysUntil = calculateDaysUntil(electionDate);
  
  // Group measures by type
  const statewideMeasures = measures.filter(m => m.jurisdiction === 'statewide');
  const localMeasures = measures.filter(m => m.jurisdiction !== 'statewide');
  
  return (
    <div className="ballot-page">
      {/* Hero Section */}
      <header className="ballot-header">
        <h1>California November 2026 Ballot</h1>
        <div className="election-countdown">
          <span className="countdown-number">{daysUntil}</span>
          <span className="countdown-label">days until Election Day</span>
          <span className="election-date">Tuesday, November 3, 2026</span>
        </div>
      </header>
      
      {/* Quick Stats */}
      <div className="ballot-stats">
        <div className="stat">
          <span className="stat-number">{statewideMeasures.length}</span>
          <span className="stat-label">Statewide Measures</span>
        </div>
        <div className="stat">
          <span className="stat-number">{localMeasures.length}</span>
          <span className="stat-label">Local Measures</span>
        </div>
      </div>
      
      {/* Statewide Measures */}
      <section className="measures-section">
        <h2>Statewide Propositions</h2>
        <p className="section-intro">
          These measures will appear on every California voter's ballot.
        </p>
        <div className="measures-list">
          {statewideMeasures.map(measure => (
            <PendingMeasureCard key={measure.id} measure={measure} />
          ))}
        </div>
      </section>
      
      {/* Local Measures Teaser */}
      {localMeasures.length > 0 && (
        <section className="measures-section local">
          <h2>Local Measures</h2>
          <p className="section-intro">
            {localMeasures.length} local measures have qualified. 
            Your ballot will include measures specific to your county and city.
          </p>
          <LocalMeasureFinder />
        </section>
      )}
      
      {/* Resources Section */}
      <section className="resources-section">
        <h2>Voter Resources</h2>
        <div className="resource-cards">
          <ResourceCard
            icon="📍"
            title="Check Your Registration"
            description="Verify you're registered to vote"
            url="https://voterstatus.sos.ca.gov/"
          />
          <ResourceCard
            icon="📖"
            title="Official Voter Guide"
            description="Available August 2026"
            url="https://voterguide.sos.ca.gov/"
            comingSoon={true}
          />
          <ResourceCard
            icon="🗓️"
            title="Key Dates"
            description="Registration deadlines and early voting"
            url="#key-dates"
          />
        </div>
      </section>
      
      {/* Timeline */}
      <section className="timeline-section">
        <h2>What to Expect</h2>
        <ElectionTimeline electionDate={electionDate} />
      </section>
      
      {/* Disclaimer */}
      <PendingBallotDisclaimer />
    </div>
  );
};
```

#### 4.2 Election Timeline Component

```jsx
const ElectionTimeline = ({ electionDate }) => {
  const timelineEvents = [
    {
      date: 'Now',
      title: 'Measures Qualifying',
      description: 'Ballot measures are being certified for the November ballot',
      status: 'current'
    },
    {
      date: 'Spring 2026',
      title: 'Fiscal Analyses Published',
      description: 'Legislative Analyst\'s Office releases nonpartisan fiscal impact reports',
      status: 'upcoming'
    },
    {
      date: 'August 2026',
      title: 'Official Voter Guide',
      description: 'Pro/con arguments and full ballot text available',
      status: 'upcoming'
    },
    {
      date: 'October 5, 2026',
      title: 'Voter Registration Deadline',
      description: 'Last day to register online or by mail',
      status: 'upcoming'
    },
    {
      date: 'October 5, 2026',
      title: 'Vote-by-Mail Begins',
      description: 'Ballots mailed to registered voters',
      status: 'upcoming'
    },
    {
      date: 'November 3, 2026',
      title: 'Election Day',
      description: 'Polls open 7am - 8pm',
      status: 'upcoming'
    }
  ];
  
  return (
    <div className="election-timeline">
      {timelineEvents.map((event, index) => (
        <div key={index} className={`timeline-event ${event.status}`}>
          <div className="timeline-marker" />
          <div className="timeline-content">
            <span className="timeline-date">{event.date}</span>
            <h4>{event.title}</h4>
            <p>{event.description}</p>
          </div>
        </div>
      ))}
    </div>
  );
};
```

---

### Phase 5: Related Past Measures (Priority: Medium, Effort: Low)

**Goal:** Leverage your historical data to provide valuable context.

#### 5.1 Topic-Based Matching

```javascript
// Find related historical measures based on topic classification
async function findRelatedMeasures(measure, options = {}) {
  const { limit = 5, minYear = 1970 } = options;
  
  // Your data has topic classifications - use them
  const related = await db.query(`
    SELECT 
      id, title, year, jurisdiction, 
      passed, yes_percentage, topic
    FROM measures
    WHERE 
      topic = $1
      AND year >= $2
      AND year < $3
      AND status != 'PENDING'
    ORDER BY year DESC
    LIMIT $4
  `, [measure.topic, minYear, measure.year, limit]);
  
  return related.map(m => ({
    ...m,
    relevance: calculateRelevance(measure, m),
    outcomeNote: m.passed 
      ? `Passed with ${m.yes_percentage}% yes` 
      : `Failed with ${m.yes_percentage}% yes`
  }));
}

// Simple relevance scoring
function calculateRelevance(pending, historical) {
  let score = 0;
  
  // Same topic = base relevance
  if (pending.topic === historical.topic) score += 50;
  
  // Recency bonus
  const yearDiff = pending.year - historical.year;
  if (yearDiff <= 10) score += 30;
  else if (yearDiff <= 20) score += 20;
  else if (yearDiff <= 30) score += 10;
  
  // Same jurisdiction bonus
  if (pending.jurisdiction === historical.jurisdiction) score += 20;
  
  return score;
}
```

#### 5.2 Display Component

```jsx
const RelatedPastMeasures = ({ measure }) => {
  const { related, loading } = useRelatedMeasures(measure.id);
  
  if (loading || !related?.length) return null;
  
  return (
    <section className="related-measures">
      <h3>📜 Similar Past Measures</h3>
      <p className="section-intro">
        California voters have decided on related measures in the past:
      </p>
      
      <div className="related-list">
        {related.map(m => (
          <Link 
            key={m.id} 
            to={`/measure/${m.id}`}
            className="related-measure-card"
          >
            <span className="related-year">{m.year}</span>
            <span className="related-title">{m.title}</span>
            <span className={`related-outcome ${m.passed ? 'passed' : 'failed'}`}>
              {m.outcomeNote}
            </span>
          </Link>
        ))}
      </div>
      
      <p className="related-note">
        <em>Note: Past measure outcomes don't predict future results, 
        but can provide useful context.</em>
      </p>
    </section>
  );
};
```

---

## Database Schema Additions

```sql
-- Add pending-specific fields to measures table
ALTER TABLE measures ADD COLUMN IF NOT EXISTS qualification_type TEXT;
  -- 'legislative', 'initiative', 'referendum'
  
ALTER TABLE measures ADD COLUMN IF NOT EXISTS election_date DATE;
  -- Specific election date (not just year)
  
ALTER TABLE measures ADD COLUMN IF NOT EXISTS bill_number TEXT;
  -- For legislative measures: 'AB 440', 'SB 1234', etc.
  
ALTER TABLE measures ADD COLUMN IF NOT EXISTS ballot_label TEXT;
  -- Official short title that appears on ballot

-- Track summary types
ALTER TABLE measures ADD COLUMN IF NOT EXISTS ai_summary_type TEXT;
  -- 'detailed', 'minimal', 'voter_guide' (when available)

-- Add index for pending measure queries
CREATE INDEX IF NOT EXISTS idx_measures_pending 
ON measures (year, status) 
WHERE status = 'PENDING';
```

---

## Disclaimer Content

Add this disclaimer to all pending measure pages:

```jsx
const PendingMeasureDisclaimer = () => (
  <aside className="measure-disclaimer">
    <h4>ℹ️ About This Information</h4>
    <p>
      This page provides an overview of a measure on California's November 2026 
      ballot to help voters research their choices. For official and complete 
      information, please consult:
    </p>
    <ul>
      <li>
        <a href="https://www.sos.ca.gov/elections/ballot-measures/" 
           target="_blank" rel="noopener noreferrer">
          California Secretary of State
        </a>
      </li>
      <li>
        <a href="https://voterguide.sos.ca.gov/" 
           target="_blank" rel="noopener noreferrer">
          Official Voter Information Guide
        </a> (available August 2026)
      </li>
    </ul>
    <p>
      <strong>This site does not make voting recommendations.</strong> 
      Information is provided for educational purposes only.
    </p>
    <p className="last-updated">
      Last updated: {formatDate(new Date())}
    </p>
  </aside>
);
```

---

## Implementation Checklist

### Phase 1: Visual Differentiation (Do First)
- [ ] Add status badge component for pending measures
- [ ] Update empty state messages with contextual text
- [ ] Reorder information hierarchy for pending vs historical
- [ ] Hide vote results section for pending measures
- [ ] Add disclaimer to pending measure pages

### Phase 2: Link Enrichment (Do Second)
- [ ] Implement deterministic link generation for pending sources
- [ ] Create prominent "Official Sources" section
- [ ] Add "Coming Soon" section for future sources
- [ ] Test all generated URLs for validity

### Phase 3: AI Summaries (Do Third)
- [ ] Create pending-specific summary prompt
- [ ] Generate summaries for all 2026 measures
- [ ] Display summaries with clear AI attribution
- [ ] Add "Verify with official sources" CTA

### Phase 4: Landing Page (Do Fourth)
- [ ] Create dedicated /ballot/2026 page
- [ ] Add election countdown
- [ ] Create measures list grouped by type
- [ ] Add timeline component
- [ ] Add voter resources section

### Phase 5: Related Measures (If Time Permits)
- [ ] Implement topic-based matching query
- [ ] Create related measures display component
- [ ] Add relevance scoring

---

## Questions to Answer Before Starting

1. How is measure status currently stored? (What value indicates "pending"?)
2. What's the current URL structure for measure detail pages?
3. Is there existing component for measure cards/detail views to modify?
4. Do you have the bill numbers for legislative measures in your data?
5. How are the existing AI summaries being stored and displayed?
6. Is there a router/navigation system in place? (For the landing page)

Please start by examining the codebase to understand the current implementation, then proceed with Phase 1.
