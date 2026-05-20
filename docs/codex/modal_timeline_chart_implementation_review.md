# Codex review: implementation of the cumulative-line timeline chart

> **For Codex:** Follow-up to `modal_timeline_chart_design.md`. You
> recommended a cumulative line chart with shared y-axis, election-day
> marker, and timing-facts strip. This is the implementation. Review
> for fidelity to your spec, correctness, and edge-case soundness.
>
> Live in the regenerated `index.html`. Embedded JS function:
> `buildTimelineChart` + helpers `generalElectionDate` and `weeksBefore`.

## What I implemented vs what you recommended

| Your recommendation | Implementation | Notes |
|---|---|---|
| Cumulative line chart | ✅ SVG `<path>` per stance | step-after pathing (see below) |
| Shared y-axis, dollars | ✅ shared `yMax = max(supportMax, opposeMax, 1)` | honest scale |
| Two lines: support + oppose | ✅ green + red `<path>` elements | |
| Vertical election-day marker | ✅ dashed grey vertical line in plot area, plus date label on the x-axis row | election date computed from `measure.year` (see deviation #1) |
| Big-jump annotation, e.g. "+$141.8M week of Aug 31" | ⚠️ implemented in the timing-facts strip below the chart, NOT inline on the line itself (see deviation #2) | |
| Timing facts strip with peak week + relative timing | ✅ "Peak support week: $141.8M (week of 2020-08-31, 9 weeks before election)" | |
| Lopsided-fight inset: "Support raised 7.5x more overall" | ✅ rendered as a ratio-note when ratio ≥ 3x | |
| Don't keep per-side-scaled bars | ✅ removed | |
| Don't jump to receipt-type stacked bars | ✅ skipped | receipt breakdown already in the cards above |

## Deviations worth your eye

### Deviation #1: election-date approximation

You said "data to add if convenient: election_date." I checked — the
measure record has an `election_date` column but it's null in the
data for the measures I sampled. Rather than plumb a backfill, I
compute the election date in JS from `measure.year`:

```javascript
function generalElectionDate(year) {
    // First Tuesday after first Monday of November of `year`.
    const y = parseInt(year, 10);
    if (!y || y < 1900 || y > 2100) return null;
    const nov1 = new Date(Date.UTC(y, 10, 1));
    const dow = nov1.getUTCDay();
    const firstMondayOffset = (1 - dow + 7) % 7;
    const firstMonday = new Date(nov1.getTime() + firstMondayOffset * 86400000);
    return new Date(firstMonday.getTime() + 86400000);
}
```

This is **correct for general-election November dates** (most
California statewide props). It will plot the marker a few months
off for:
- **June primary measures** (PROP_68 / 69 / 70 in 2018, some
  recall-cycle props) — marker would point at Nov 6, 2018 when the
  actual election was June 5, 2018
- **Special-election measures** (rare for statewide props but
  possible)

The line shape still carries the timing story even with a wrong
marker, but the "N weeks before election" facts would be wrong by
~22 weeks for June-primary cases. **Acceptable trade-off, or worth
backfilling `election_date` in the measure table?**

### Deviation #2: peak-jump labels in strip, not inline

Your spec said: *"Annotate each side's biggest weekly jump with a
small label, e.g. +$141.8M week of Aug 31."* I rendered this as a
line in the timing-facts strip BELOW the chart instead of as an
inline SVG `<text>` callout on the line itself at the jump point.

Reasoning: in-SVG text labels would need collision detection (the
two peak labels could overlap if they're at adjacent weeks) and
would have to size-clamp to the chart viewBox. Strip below the
chart is simpler and the data is the same.

**Is the strip placement sufficient, or do you want the labels
on-line?** I can do on-line if you think the storytelling matters
more than the implementation overhead.

### Choice you didn't specify: step-after lines

I used **step-after** pathing for the cumulative lines (each week's
jump renders as a vertical step, then horizontal), not smooth linear
interpolation. Reasoning: cumulative *receipts* don't flow
continuously between weeks — they jump at weekly bucket boundaries.
A consolidated $141M payment really IS a single-week event; smooth
slope would imply gradual accumulation through the week.

Visually this also makes big jumps more visible (a vertical step
draws the eye more than a steep slope). For lopsided fights this
matters.

**Step-after vs smooth — your call?**

### Choice you didn't specify: horizontal gridlines

Added three dashed horizontal gridlines at 25 / 50 / 75% of yMax.
Helps the eye estimate dollar values without explicit y-axis
labels. Did NOT add the explicit y-axis ticks (would clutter the
small modal viewport).

### Choice you suggested but I didn't take: cumulative % milestones

You suggested "date when each side crossed 50% / 75% / 90% of final
total." I didn't add these — felt redundant with the peak-week info
already in the strip. **Add them, or are peaks enough?**

## Things to scrutinize

### A. Chart legibility for various measures

I've only eyeballed PROP_22_2020 (the lopsided case). The design
should also work for:

- **PROP_27_2022** (closer ratio, $140M vs $173M) — both lines
  tall, election marker meaningful
- **PROP_8_2018** ($23M vs $101M) — moderate lopsided
- **PROP_50_2025** ($283M, support-dominant) — recent measure
- **Older measures** like PROP_87_2006 — likely a multi-month
  timeline; chart should still be readable

Worth opening 2-3 of these and confirming the line idiom doesn't
break on any common shape.

### B. Edge cases in `buildTimelineChart`

```javascript
function buildTimelineChart(timeline, measure) {
    const supportData = timeline.filter(t => t.stance === 'support')
        .sort((a, b) => a.week_start.localeCompare(b.week_start));
    const opposeData = timeline.filter(t => t.stance === 'oppose')
        .sort((a, b) => a.week_start.localeCompare(b.week_start));
    if (supportData.length === 0 && opposeData.length === 0) return '';
    const allWeeks = [...new Set(timeline.map(t => t.week_start))].sort();
    if (allWeeks.length < 2) return '';
    // ... yMax computation ...
    // ... path drawing ...
}
```

Edge cases to confirm:
- **One stance has data, other doesn't** (uncontested measures) —
  `supportData.length === 0` but `opposeData.length` > 0, code
  should handle it (pathFor returns '' on empty series; election
  marker still renders)
- **All weeks have $0** — shouldn't happen with `quarantine_reason
  IS NULL` filter but worth thinking about
- **Single week** — chart returns '' early; OK
- **Timeline spans 4+ years** (collision-campaign measures) — axis
  scaling should compress; the 700x180 viewBox stays the same
- **measure.year is null/missing** — `generalElectionDate` returns
  null; election marker doesn't render; facts strip omits "weeks
  before election" suffix

### C. Visual contract / honesty

Shared y-axis = honest scale. Big jumps render as visible vertical
steps. Lopsided ratio shows as steep-vs-flat (line shape carries the
ratio info). The ratio-note for ≥3x cases makes the magnitude
explicit even when the y-axis is hard to read precisely.

**Is the visual contract right?** Any case where a viewer would
misinterpret what they're seeing?

### D. SVG technical bits

```javascript
const W = 700, H = 180;
const padL = 8, padR = 8, padT = 12, padB = 24;
```

ViewBox `0 0 700 180` with `preserveAspectRatio="none"`, CSS scales
to the container width. Width: 100%; height: 180px (CSS fixed).

Path computation uses `Date.UTC(...).getTime()` for the x-axis time
basis. ISO week_start strings parsed as `new Date(s + 'T00:00:00Z')`.

**Any timezone gotchas?** `Date.UTC` should keep things consistent
but I want a second look.

## Full chart function for scrutiny

```javascript
function generalElectionDate(year) {
    // First Tuesday after first Monday of November of `year`.
    // Approximation for measures without an explicit election_date.
    if (!year) return null;
    const y = parseInt(year, 10);
    if (!y || y < 1900 || y > 2100) return null;
    const nov1 = new Date(Date.UTC(y, 10, 1));
    const dow = nov1.getUTCDay();
    const firstMondayOffset = (1 - dow + 7) % 7;
    const firstMonday = new Date(nov1.getTime() + firstMondayOffset * 86400000);
    return new Date(firstMonday.getTime() + 86400000);
}

function weeksBefore(electionDate, weekStart) {
    if (!electionDate || !weekStart) return null;
    const wd = new Date(weekStart + 'T00:00:00Z');
    const diffDays = (electionDate.getTime() - wd.getTime()) / 86400000;
    return Math.round(diffDays / 7);
}

function buildTimelineChart(timeline, measure) {
    const supportData = timeline.filter(t => t.stance === 'support')
        .sort((a, b) => a.week_start.localeCompare(b.week_start));
    const opposeData = timeline.filter(t => t.stance === 'oppose')
        .sort((a, b) => a.week_start.localeCompare(b.week_start));

    if (supportData.length === 0 && opposeData.length === 0) return '';

    const allWeeks = [...new Set(timeline.map(t => t.week_start))].sort();
    if (allWeeks.length < 2) return '';

    const supportMax = supportData.length
        ? supportData[supportData.length - 1].cumulative_receipts || 0
        : 0;
    const opposeMax = opposeData.length
        ? opposeData[opposeData.length - 1].cumulative_receipts || 0
        : 0;
    const yMax = Math.max(supportMax, opposeMax, 1);

    const firstWeek = new Date(allWeeks[0] + 'T00:00:00Z');
    const lastWeek = new Date(allWeeks[allWeeks.length - 1] + 'T00:00:00Z');
    const electionDate = measure ? generalElectionDate(measure.year) : null;
    const axisEnd = electionDate && electionDate.getTime() > lastWeek.getTime()
        ? new Date(electionDate.getTime() + 14 * 86400000)
        : lastWeek;
    const axisSpanMs = Math.max(axisEnd.getTime() - firstWeek.getTime(), 1);

    const W = 700, H = 180;
    const padL = 8, padR = 8, padT = 12, padB = 24;
    const plotW = W - padL - padR;
    const plotH = H - padT - padB;

    const xOf = (weekStart) => {
        const t = new Date(weekStart + 'T00:00:00Z').getTime();
        return padL + ((t - firstWeek.getTime()) / axisSpanMs) * plotW;
    };
    const yOf = (amount) => padT + plotH - (amount / yMax) * plotH;

    const pathFor = (series) => {
        if (!series.length) return '';
        // Step-after: vertical jumps at week boundaries.
        let d = 'M ' + padL + ',' + yOf(0);
        let lastY = yOf(0);
        series.forEach(pt => {
            const px = xOf(pt.week_start);
            const py = yOf(pt.cumulative_receipts || 0);
            d += ' L ' + px + ',' + lastY + ' L ' + px + ',' + py;
            lastY = py;
        });
        d += ' L ' + (padL + plotW) + ',' + lastY;
        return d;
    };

    const peakJump = (series) => {
        let best = {week: null, amount: 0};
        for (let i = 0; i < series.length; i++) {
            const w = series[i].weekly_receipts || 0;
            if (w > best.amount) best = {week: series[i].week_start, amount: w};
        }
        return best;
    };
    const sPeak = peakJump(supportData);
    const oPeak = peakJump(opposeData);

    let svg = '<svg class="finance-line-chart" viewBox="0 0 ' + W + ' ' + H +
              '" preserveAspectRatio="none" role="img" aria-label="Cumulative fundraising over time">';
    // Gridlines at 25/50/75%.
    [0.25, 0.5, 0.75].forEach(frac => {
        const y = yOf(yMax * frac);
        svg += '<line class="finance-line-grid" x1="' + padL + '" x2="' + (padL + plotW) +
               '" y1="' + y + '" y2="' + y + '"/>';
    });
    // Election-day marker.
    let electionLabel = '';
    if (electionDate
        && electionDate.getTime() >= firstWeek.getTime()
        && electionDate.getTime() <= axisEnd.getTime()) {
        const xElection = padL + ((electionDate.getTime() - firstWeek.getTime()) / axisSpanMs) * plotW;
        svg += '<line class="finance-line-election" x1="' + xElection + '" x2="' + xElection +
               '" y1="' + padT + '" y2="' + (padT + plotH) + '"/>';
        const isoDate = electionDate.toISOString().slice(0, 10);
        electionLabel = '<span class="finance-line-electionlabel">Election day: ' + isoDate + '</span>';
    }
    svg += '<path class="finance-line oppose" d="' + pathFor(opposeData) + '"/>';
    svg += '<path class="finance-line support" d="' + pathFor(supportData) + '"/>';
    svg += '</svg>';

    const facts = [];
    const fmtRel = (w) => {
        const wb = weeksBefore(electionDate, w);
        if (wb === null) return '';
        if (wb > 1) return ', ' + wb + ' weeks before election';
        if (wb === 1) return ', 1 week before election';
        if (wb === 0) return ', election week';
        if (wb === -1) return ', 1 week after election';
        return ', ' + Math.abs(wb) + ' weeks after election';
    };
    if (sPeak.week) {
        facts.push('<span class="peak-support">Peak support week: ' +
                   formatDollars(sPeak.amount) + ' (week of ' + sPeak.week +
                   fmtRel(sPeak.week) + ')</span>');
    }
    if (oPeak.week) {
        facts.push('<span class="peak-oppose">Peak oppose week: ' +
                   formatDollars(oPeak.amount) + ' (week of ' + oPeak.week +
                   fmtRel(oPeak.week) + ')</span>');
    }
    const big = Math.max(supportMax, opposeMax);
    const small = Math.min(supportMax, opposeMax);
    if (small > 0 && big / small >= 3) {
        const ratio = (big / small).toFixed(1);
        const bigger = supportMax > opposeMax ? 'Support' : 'Oppose';
        facts.push('<span class="ratio-note">' + bigger + ' raised ' + ratio + 'x more overall.</span>');
    }

    let html = '<div class="finance-timeline">';
    html += '<h4>Funding over time</h4>';
    html += svg;
    html += '<div class="finance-chart-dates">' +
            '<span>' + allWeeks[0] + '</span>' +
            electionLabel +
            '<span>' + (electionDate ? electionDate.toISOString().slice(0, 10) : allWeeks[allWeeks.length - 1]) + '</span>' +
            '</div>';
    html += '<div class="finance-chart-peaks">' + facts.join('') + '</div>';
    html += '<div class="finance-chart-legend"><span class="legend-support">Support</span><span class="legend-oppose">Oppose</span></div>';
    html += '</div>';
    return html;
}
```

## CSS for the SVG

```css
svg.finance-line-chart {
    display: block;
    width: 100%;
    height: 180px;
    overflow: visible;
}
svg.finance-line-chart .finance-line {
    fill: none;
    stroke-width: 2;
    stroke-linejoin: round;
    stroke-linecap: round;
}
svg.finance-line-chart .finance-line.support { stroke: var(--success); }
svg.finance-line-chart .finance-line.oppose { stroke: var(--danger); }
svg.finance-line-chart .finance-line-grid {
    stroke: var(--border, #e2e8f0);
    stroke-width: 0.5;
    stroke-dasharray: 2 3;
    opacity: 0.6;
}
svg.finance-line-chart .finance-line-election {
    stroke: var(--text-secondary, #64748b);
    stroke-width: 1;
    stroke-dasharray: 3 2;
    opacity: 0.7;
}
.finance-line-electionlabel {
    font-size: 0.7rem;
    color: var(--text-secondary);
    font-style: italic;
}
.finance-chart-peaks .ratio-note {
    color: var(--text-secondary);
    font-style: italic;
}
```

## What we want from you

1. **Fidelity check** — does the implementation match your spec
   meaningfully? Anything materially different?
2. **Election-date approximation** — is the November-Tuesday
   approach acceptable, or should we backfill `election_date` in the
   measure table?
3. **Peak-jump labels** — strip below the chart vs inline on the
   line. Your preference, and is the strip sufficient?
4. **Step-after vs smooth lines** — visual fidelity choice. Right
   call?
5. **Edge cases** — anything in `buildTimelineChart` that could
   fail on real measures?
6. **Visual honesty** — does the chart misrepresent anything?
7. **Anything else** — including the things you mentioned but I
   didn't take (% milestones).

Light review wanted — design implementation, not full code audit.
