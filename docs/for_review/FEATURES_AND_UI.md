# Features and UI

> **Snapshot: January 2026. Not current state.** This document is part of an
> audit suite written for a one-time external review and is preserved as a
> record of that review. The project has changed substantially since:
> the finance database was rebuilt twice (v2 in May, a combined v2+v3 read
> layer soon after), and a recurring **county registrar pipeline** was built
> June–August 2026, adding scrapers, an immutable artifact store in
> Cloudflare R2, a parser, and a loader.
>
> For current state, read [`../WORKING_LIST.md`](../WORKING_LIST.md) first,
> then [`../../CLAUDE.md`](../../CLAUDE.md).
>
> **Most changed here:** the Finance panel and modal were redesigned in May
> 2026 against the combined v2+v3 layer.

## Website Interface

The entire application is a single-page application embedded in `index.html` (35.3 MB), with all measure data embedded as JSON. No server-side rendering required.

---

## 1. Search & Navigation

### Global Search Bar
- **Debounced substring search** across title, description, summary, and ballot question fields
- **Instant filtering** - no page reload required
- No autocomplete or pre-built search index; matching is done client-side via JavaScript substring comparison

> _Evidence: `scraper/src/website/generator.py:4247-4256`, `generator.py:4387-4400`._

### View Controls
- **List View** - Compact display with essential info
- **Grid View** - Card-based layout with more detail

---

## 2. Sidebar Filters

**Sticky sidebar** (fixed position) with multiple filter categories:

### Status Filter (Chips)
- **Passed** (green) - Measures that passed
- **Failed** (red) - Measures that failed
- **Pending** (yellow) - Measures with year >= 2026 or missing vote results

> _Note: There is no explicit "All" chip. Evidence: `generator.py:4810-4813`, `generator.py:4951-4953`._

### Year Range Filter
- **Year chips grouped by decade** (not a dropdown or slider)
- Range: 1998-2026

> _Evidence: `generator.py:563-590` (year panel), `generator.py:3710-3765` (decade data)._

### County Filter
- All 58 California counties
- "Statewide" option for propositions
- Alphabetically sorted

### Topic Filter (12 Categories)
1. Education
2. Public Safety & Crime
3. Taxes & Finance
4. Government & Elections
5. Healthcare & Welfare
6. Environment & Natural Resources
7. Transportation
8. Housing & Land Use
9. Business & Labor
10. Utilities & Energy
11. Civil Rights
12. Other

---

## 3. Measure Display Cards

Each measure card shows:

```
┌─────────────────────────────────────────────┐
│  [PASSED]  2024                             │
│                                              │
│  Proposition 36: Allows Felony Charges...   │
│                                              │
│  California (Statewide)                      │
│  Topic: Public Safety & Crime                │
│                                              │
│  Yes: 70.5% (8,234,567)                     │
│  No: 29.5% (3,456,789)                      │
│                                              │
│  Summary excerpt if available...             │
│                                              │
└─────────────────────────────────────────────┘
```

**Card Elements:**
- Status badge (Passed/Failed/Pending)
- Year
- Measure title (AI-simplified or original)
- Jurisdiction (County/City/District)
- Topic tag
- Vote breakdown with percentages
- Summary excerpt
- **Entire card is clickable** (opens detail modal); no separate action buttons

> _Evidence: `generator.py:4816-4875` — cards have no `[View Details]` or `[External Links]` buttons._

---

## 4. Measure Detail Modal

Full-page overlay with complete information:

### Header Section
- Measure ID and title
- Status badge
- Year and election type

### Content Section
- **Full ballot question text** (official language)
- **Description** (if available)
- **AI-generated summary** (2-3 sentence neutral explanation)

### Vote Results
```
┌─────────────────────────────────────────────┐
│  Vote Results                                │
│                                              │
│  YES  ████████████████████░░░░  70.5%       │
│       8,234,567 votes                        │
│                                              │
│  NO   ██████░░░░░░░░░░░░░░░░░░  29.5%       │
│       3,456,789 votes                        │
│                                              │
│  Total Votes: 11,691,356                     │
│  Result: PASSED                              │
└─────────────────────────────────────────────┘
```

> _Note: No threshold field is rendered in the modal. Evidence: `generator.py:4989-4999`._

### Related Measures
- **Similar Measures** - Based on sentence embeddings
- Shows up to **4** most related measures (not 5)
- Click to navigate

> _Evidence: `generator.py:5015-5044` — `.slice(0, 4)`._

### External Links

Links are generated per-measure by `scraper/src/utils/external_links.py:290-331`:

- **CA Secretary of State** (Voter Guide archive)
- **Legislative Analyst's Office (LAO)**
- **UC Law SF** (Hastings scholarship archive)
- **Ballotpedia**
- **Wikipedia** (search link)

> _Note: Google News and Vote411.org are NOT generated. Evidence: `external_links.py` — no Google News or Vote411 functions._

### Actions
- **Close** button

> _Note: There is no "Copy Measure Info" / clipboard button. Evidence: `generator.py:4816-5085`._

---

## 5. Regional Browse

### 9 California Regions
Organized by geographic groupings:

1. **Greater Bay Area** (9 counties)
   - San Francisco, Alameda, Santa Clara, San Mateo, Contra Costa, Marin, Sonoma, Napa, Solano

2. **Greater Los Angeles** (5 counties)
   - Los Angeles, Orange, Riverside, San Bernardino, Ventura

3. **San Diego Region** (2 counties)
   - San Diego, Imperial

4. **Central Valley** (8 counties)
   - Fresno, Kern, Kings, Madera, Merced, San Joaquin, Stanislaus, Tulare

5. **Sacramento Region** (6 counties)
   - Sacramento, Placer, El Dorado, Yolo, Sutter, Yuba

6. **Central Coast** (5 counties)
   - Monterey, San Luis Obispo, Santa Barbara, Santa Cruz, San Benito

7. **North Coast** (4 counties)
   - Mendocino, Humboldt, Del Norte, Lake

8. **Northern California** (10 counties)
   - Shasta, Tehama, Butte, Glenn, Colusa, Trinity, Siskiyou, Modoc, Lassen, Plumas

9. **Eastern Sierra** (9 counties)
   - Mono, Inyo, Alpine, Amador, Calaveras, Tuolumne, Mariposa, Nevada, Sierra

> _Evidence: `generator.py:3709-3755` — exact region definitions._

### Regional Browse
- Region chips displayed in accordion filter panel
- A separate hero carousel shows upcoming (2026) measures (not per-region)

> _Evidence: `generator.py:4560-4569` — single hero carousel, not per-region._

---

## 6. AI Chat Interface (BYOLLM)

### Chat Widget
- **Position:** Fixed bottom-right corner
- **Toggle Button:** 60px circular button, primary blue
- **Chat Panel:** 400px x 600px modal

### Provider Selection
Support for 3 AI providers:

| Provider | Setup |
|----------|-------|
| OpenAI (GPT-4) | API key required |
| Anthropic (Claude) | API key required |
| Local Ollama | Local installation required |

> _Evidence: `generator.py:792-797` — only three `<option>` values: `openai`, `anthropic`, `ollama`. Groq is NOT available in the chat UI._

### Chat Features
- **Context-aware responses** - Filters embedded JSON data based on question keywords
- **Example questions** provided for new users
- **Test connection** button
- **API key management** (stored in localStorage)
- **Markdown rendering** in responses
- **Cloudflare Worker CORS proxy** for OpenAI/Anthropic API calls

> _Caveat: Chat context logic references fields (`result`, `votes_for`, `votes_against`) that do not match the embedded dataset field names (`passed`, `yes_votes`, `no_votes`), so some context calculations may not work as intended. Evidence: `generator.py:5481-5513`._

### Example Questions (from UI buttons)
- "What were the 10 closest ballot measures in the last 5 years?"
- "Show me all housing-related measures in San Francisco"
- "What topics have the lowest pass rates?"
- "Tell me about education measures from 2020-2024"

> _Evidence: `generator.py:760-763`._

---

## 7. Trivia Quiz Widget

### Quiz Section
Purple gradient background with educational content

### Dynamically Generated Questions
Questions are generated at website build time from the embedded dataset. The count varies depending on available data (typically 15–20 questions). Examples include pass-rate stats, topic comparisons, and year-over-year trends.

> _Evidence: `generator.py:145-220` (dynamic generation), `generator.py:640-641` (default "Question 1 of N" text), `generator.py:5186-5226` (uses `quizQuestions.length`)._

### Quiz Flow
1. Question displayed with category tag
2. "Reveal Answer" button
3. Answer shows in green box
4. "Next Question" shuffles to next
5. Progress indicator (e.g., "5 of N")

---

## 8. About Modal

### Sections
- **Background** - Purpose and scope
- **Features** - Capabilities overview
- **Data Pipeline** - How data is collected
- **Author** - Credits

> _Evidence: `generator.py:652-716`. No "Infrastructure" or "Attribution" sections exist._

---

## 9. Responsive Design

### Desktop (1200px+)
- Two-column layout (sidebar + content)
- Grid view shows 3 cards per row

### Tablet (768px - 1199px)
- Collapsible sidebar
- Grid view shows 2 cards per row

### Mobile (<768px)
- Full-width stacked layout
- Sticky header
- Single card per row

> _Note: No bottom navigation for filters exists. Evidence: `generator.py:380-590` — no bottom-nav CSS or HTML._

---

## 10. Styling System

### CSS Variables
```css
:root {
  --primary: #1a73e8;      /* Google Blue */
  --accent: #1a73e8;
  --success: #1e8e3e;      /* Green - Passed */
  --danger: #d93025;       /* Red - Failed */
  --warning: #f9ab00;      /* Yellow - Pending */
  --bg-primary: #ffffff;
  --bg-secondary: #f8f9fa;
  --text-primary: #202124;
  --text-secondary: #5f6368;
  --border: #dadce0;
  --radius: 8px;
}
```

### Typography
- **Font Stack:** -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Arial
- **Monospace:** ui-monospace, SFMono-Regular, Menlo
- **Base Size:** 16px
- **Line Height:** 1.5

---

## 11. Performance Considerations

### Initial Load
- 35 MB HTML file (includes all data)
- Gzip compressed to ~4-5 MB transfer
- No additional API calls for data

### Filtering
- Client-side JavaScript filtering
- No server round-trips
- Instant response

### Search
- Client-side substring matching (no pre-built search index)
- Debounced input (300ms)

### AI Chat
- On-demand API calls
- User pays for their usage
- Cloudflare Worker handles CORS
