# UI Improvements - Website Card Enhancements

## Overview
Implemented "quick wins" to improve the visual appearance and user experience of ballot measure cards on the website.

## Changes Made (2026-01-09)

### ✅ Quick Win 1: Truncated Descriptions with "Read More"
- Added description field extraction from multiple sources (description, summary, ballot_question)
- Implemented 200-character truncation with "..." for long descriptions
- Added "Read more →" link when description is truncated
- CSS styling with 3-line clamp for consistent card heights

**CSS Added:**
```css
.card-description {
    font-size: 0.875rem;
    color: var(--text-secondary);
    line-height: 1.6;
    margin: 0.5rem 0;
    display: -webkit-box;
    -webkit-line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
    text-overflow: ellipsis;
}

.read-more {
    color: var(--primary);
    font-size: 0.813rem;
    font-weight: 500;
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
}
```

### ✅ Quick Win 2: Enhanced Icons for Metadata
- Added calendar emoji (📅) to year display
- Kept existing chart emoji (📊) for vote percentage
- Kept tag emoji (🏷️) for topics
- Changed folder emoji to file box (🗂️) for better visual clarity on data source

**Before:** `2024` `📊 60% Yes` `🏷️ Education`
**After:** `📅 2024` `📊 60% Yes` `🏷️ Education` `🗂️ CEDA`

### ✅ Quick Win 3: Improved Status Badges
Enhanced badge design with:
- Increased padding (0.375rem × 0.75rem)
- Bold font weight (600)
- Uppercase text with letter spacing
- Gradient backgrounds for depth
- Colored borders matching badge type
- Status indicator dots (6px circles) before text

**Badge Colors:**
- **Passed:** Green gradient with dark green text (#1a7a3e) and border
- **Failed:** Red gradient with dark red text (#c4241f) and border
- **Pending:** Orange gradient with dark orange text (#b87503) and border

**CSS Enhancement:**
```css
.badge {
    padding: 0.375rem 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.025em;
    display: inline-flex;
    align-items: center;
    gap: 0.375rem;
}

.badge::before {
    content: '';
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: [status-color];
}
```

### ✅ Quick Win 4: Enhanced Hover Effects
Improved card hover state with:
- Increased shadow depth (0 8px 16px rgba)
- Greater vertical lift (-2px translateY)
- Blue border glow on hover
- Vote bar glow effect on card hover

**Before:** Subtle shadow, 1px lift
**After:** Prominent shadow, 2px lift, blue border glow, vote bar highlight

**CSS Enhancement:**
```css
.measure-card {
    transition: all 0.2s ease;
    border: 1px solid rgba(0, 0, 0, 0.05);
}

.measure-card:hover {
    box-shadow: 0 8px 16px rgba(0, 0, 0, 0.12);
    transform: translateY(-2px);
    border-color: rgba(66, 133, 244, 0.2);
}

.measure-card:hover .vote-bar-fill {
    box-shadow: 0 0 8px rgba(30, 142, 62, 0.4);
}
```

### ✅ Quick Win 5: Better Spacing and Layout
Enhanced overall card layout with:
- Increased card padding (1.25rem → 1.5rem)
- Increased gap between elements (0.75rem → 0.875rem)
- Enhanced card title styling (font-size: 1.0625rem, font-weight: 600)
- Added top border separator to metadata section
- Increased meta item spacing (1rem → 1.25rem)
- Improved meta item font weight (500)
- Enhanced vote bar (4px → 6px height with gradient fill)

**Visual Hierarchy:**
1. Card header (year + badges) at top
2. Bold, prominent title
3. Truncated description (if available)
4. Visual vote bar (if applicable)
5. Separated metadata section with icons

### ✅ Bonus: Featured Label Enhancement
Added prominent featured label styling:
- Blue background with white text
- Small, uppercase text with high letter-spacing
- Rounded corners matching site design
- Positioned next to year in card header

## Technical Details

**Files Modified:**
- `src/website/generator.py` - Updated CSS styles and createCard() function

**JavaScript Changes:**
```javascript
// Added description extraction and truncation
const description = measure.description || measure.summary || measure.ballot_question || '';
const truncatedDesc = description.length > 200 ? description.substring(0, 200) + '...' : description;

// Added conditional "Read more" link
${description.length > 200 ? '<span class="read-more">Read more →</span>' : ''}
```

**CSS Sections Modified:**
- `.measure-card` - Enhanced padding, border, transition
- `.measure-card:hover` - Stronger shadow and lift
- `.card-title` - Increased size and weight
- `.card-description` - NEW: Truncated description styling
- `.read-more` - NEW: Read more link styling
- `.badge` - Enhanced with gradients, borders, dots
- `.card-meta` - Added border separator, increased spacing
- `.vote-bar` - Increased height, added gradient
- `.vote-bar-fill` - Gradient fill with hover glow
- `.featured-label` - NEW: Enhanced featured badge

## Visual Impact

### Before:
- Basic card layout with minimal visual hierarchy
- Simple flat badges
- Small hover effect
- No descriptions shown on cards
- Basic spacing

### After:
- Clear visual hierarchy with separated sections
- Prominent badges with status indicators
- Strong hover effects with multiple visual cues
- Truncated descriptions with "Read more" prompts
- Professional spacing and typography
- Enhanced vote bars with gradients

## Browser Compatibility

All enhancements use standard CSS3 properties supported by modern browsers:
- Flexbox layout
- CSS transitions
- Linear gradients
- Box shadows
- Border radius
- Webkit line clamp (for description truncation)

## Performance

- No JavaScript performance impact (static rendering)
- CSS transitions are GPU-accelerated
- Minimal CSS overhead (~50 lines added)
- No additional HTTP requests

## AI-Powered Title Generation (NEW - 2026-01-09)

### Problem Solved
Many ballot measures have extremely long titles (200+ characters) that are actually the full ballot text. This creates messy, inconsistent cards that are hard to scan.

### Solution
Implemented AI-powered title generation using Claude Haiku to create concise, informative titles from long ballot text.

**Features:**
- Automatically detects measures with titles >150 characters
- Generates concise titles (max 80 characters) using Claude
- Caches generated titles to avoid re-generating
- Shows original text as description below the generated title
- Gracefully degrades to CSS truncation if API key not available

**Files Added:**
- `src/utils/title_generator.py` - AI title generation module
- `scripts/generate_titles.py` - Script to pre-generate titles

**How It Works:**
1. During website generation, the system checks each measure's title length
2. If title is too long (>150 chars) or complex (multiple sentences), it generates a new one
3. Generated titles are cached in `data/title_cache.json`
4. The card displays: **Generated Title** with original as description below

**Setup:**
```bash
# Install dependencies
pip install anthropic

# Set API key
export ANTHROPIC_API_KEY='your-key-here'

# Or add to .env file
echo "ANTHROPIC_API_KEY=your-key-here" >> .env

# Generate titles for all measures
python scripts/generate_titles.py

# Rebuild website with new titles
python scripts/generate_site.py --force
```

**Cost:**
- Uses Claude Haiku (cheapest model)
- ~$0.0001 per title generation
- Results are cached, so only generated once
- Example: 1000 titles ≈ $0.10

**Example:**

*Before:*
```
202400533: To improve local high schools, upgrade vocational classrooms/labs/technology for skilled trades, science, engineering, math, aerospace education, practical career skills; fix deteriorating gas/sewer lines, leaky roofs, ensure safe drinking water; upgrade student/school safety; attract/retain quality teachers; shall Antelope Valley Union High School District's measure authorizing $398,000,000 in bonds at legal rates, levying 2 cents per $100 assessed value, raising $25,000,000 annually while bonds are outstanding, be adopted, with citizen oversight, spending disclosure, local control?
```

*After:*
```
Title: School Bond Measure for Facility Improvements
Description: To improve local high schools, upgrade vocational classrooms/labs/technology for skilled trades, science, engineering, math, aerospace education, practical career skills; fix deteriorating gas/sewer lines...
```

**Fallback:**
If `ANTHROPIC_API_KEY` is not set, the website still works perfectly - it just uses CSS truncation (line-clamp) instead of AI-generated titles.

## Next Steps - Medium Term Enhancements

Consider implementing in future updates:
1. **Expandable cards** - Click to expand and show full description
2. **Vote visualization** - Donut charts showing yes/no breakdown
3. **Clickable filter tags** - Click topic/year to filter
4. **Quick view modal** - Preview full details without navigation
5. **Card comparison** - Select multiple cards to compare
6. **Timeline view** - Alternative view showing measures on timeline

## Testing

✅ Website generated successfully
✅ All CSS changes applied
✅ No JavaScript errors
✅ Responsive grid layout maintained
✅ Hover effects working correctly

**Test Command:**
```bash
python scripts/generate_site.py --force
open index.html  # macOS - view in browser
```

---

**Generated:** 2026-01-09
**Version:** 2.1.0
**By:** Claude Code (Sonnet 4.5)
