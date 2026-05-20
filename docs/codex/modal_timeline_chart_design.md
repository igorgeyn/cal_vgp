# Codex consult: modal Finance tab timeline chart design

> **For Codex:** Pure design / dataviz consult. The per-measure modal
> Finance tab has a "Weekly fundraising flow" bar chart that's been
> through two iterations and still isn't communicating well. We want
> your recommendation — either a polish-the-existing-chart fix or a
> swap-to-a-different-idiom recommendation. This is NOT a code-review
> request, it's a design ask.

## Where this chart lives

Per-measure modal, Finance tab. Two cards above the chart show the
support/oppose totals + per-receipt-type breakdown + top donors:

```
┌─SUPPORT $188.6M─┬─OPPOSE $18.9M─┐
│ Direct  $81M    │ Direct $16M   │
│ IE      $95M    │ IE     $795K  │
│ In-kind $12M    │ In-kind $1.9M │
│                 │               │
│ TOP DONORS      │ TOP DONORS    │
│ 1. Uber  $61M   │ 1. SEIU  $2.8M│
│ 2. ...          │ 2. ...        │
└─────────────────┴───────────────┘
[ Weekly fundraising flow ←─── THIS IS THE PROBLEM CHART ]
```

So the chart's job is **not** "what are the totals" (cards already
say that) and **not** "who funded what" (donor list already says
that). The job is **WHEN did each side spend** — temporal pattern.

## The two iterations and why they're not great

### Iteration 1: Cumulative (original)

Stacked support/oppose bars showing running-total receipts by week.
Problem: cumulative is monotonically increasing, so the shape is
always a ramp; the only signal is the support/oppose height ratio
that the cards above already tell you. Conveys nothing about
**when** money flowed.

### Iteration 2: Weekly (non-cumulative), shared y-axis

Same bars but per-week receipts, not cumulative. Shared y-axis
(both stances scale to the global max). Problem on lopsided fights:
for PROP_22, one week ($141.8M consolidated Uber+Lyft+DoorDash
payment on 2020-08-31) is **40x** the next-largest week. That bar
fills the chart; every other bar — including all oppose activity
— is 1-2% of chart height, indistinguishable from baseline noise.

### Iteration 3: Weekly, per-side y-axis (current state)

Each stance scales to its OWN max. So support bars are heights
relative to $141.8M (support peak); oppose bars relative to $3.4M
(oppose peak). New problem: visually, oppose bars now look **as
tall as** support bars on most weeks — implying parity. But oppose
spent 1/55th of support. The chart now visually **misleads**.

## The data we have to work with

Per (stance, week), the modal payload carries:
- `weekly_receipts` — total dollars that week, combining monetary +
  loan + in-kind + IE
- `cumulative_receipts` — running total through that week

We don't currently split by receipt type per week, but it's a
~30-min method change if it'd help (the underlying `finance_flow_v3`
table has `receipt_type` per row + `week_start`).

Election dates: knowable from the measure record (e.g.
PROP_22_2020 = 2020-11-03). Not currently passed to the timeline
function but trivial to add.

## What we've considered

- **Tornado / mirror chart** (support up, oppose down from
  centerline) — still has the per-side scale problem; either we
  scale each side to its own max (misleading) or shared max (oppose
  invisible).
- **Two stacked small multiples** (separate mini-charts per side) —
  preserves scale honesty but doubles vertical space. Modal is
  already tall.
- **Cumulative line chart with election-day marker** — actually
  pretty informative; trivializes the iteration-1 problem because
  the LINE SHAPE matters (steep vs shallow ramp, late spike vs
  early raise), not just the ratio. The election marker contextualizes
  "this was 6 weeks before election." Bonus: handles lopsided fights
  fine because they show as steep-vs-flat lines.
- **Stacked receipt-type bars** — per-week stacked bars showing
  monetary / IE / in-kind contributions per side. Reveals "when did
  IE flood in" — a real research question we now have data for. But
  doubles the visual complexity (4 colors × 2 sides = 8 series).
- **Just remove the chart** — totals + per-type breakdown +
  donor list might be enough; the temporal layer might not earn its
  space.
- **Calendar heatmap** — months × weeks grid, color intensity =
  spending. Compact, abstract. Hard to compare two sides side-by-side.
- **Annotated prose callouts** instead of a chart — "Support: 64%
  of total raised in final 30 days; first $1M arrived 2020-01-23.
  Oppose: 88% in final 60 days; first $1M arrived 2020-09-14." Lower
  visual interest but high information density.

## Constraints

- Width: ~700px (fits inside the modal which fits inside the
  measure card grid)
- Height: tall is okay (~250px); short is also okay (~120px). Modal
  is scrollable.
- Audience: voters/researchers, not finance pros. Should be
  legible without a stats background.
- Data range varies: some measures span ~4 months of activity, some
  span 4+ years (year-offset collisions). Most are 1-2 year spans.
- This chart is **secondary** to the totals + donor list above it.
  Worst case we just remove it — the page still works.

## What we want from you

Either:

**A.** A polish for the current weekly-bar chart that fixes the
"oppose looks taller than support but actually spent 55x less"
problem honestly. Specific suggestion preferred.

**B.** A recommendation to swap to a different idiom, with reasoning
about why it fits this data better. From the list above or
something we haven't thought of.

**C.** A recommendation to drop the chart entirely if you think the
data isn't worth visualizing in this surface.

If your recommendation involves new data (e.g. receipt-type per
week, election-day annotation), name that explicitly — we'll wire
it in.

Calibration: previous Codex rounds on this project caught real
correctness bugs in arithmetic / SQL. This one is design taste +
dataviz judgment. Trust your instincts; opinions welcome.

## Current chart code (for context, not for code review)

```javascript
function buildTimelineChart(timeline) {
    // timeline: array of {stance, week_start, weekly_receipts, cumulative_receipts}
    const supportData = timeline.filter(t => t.stance === 'support');
    const opposeData = timeline.filter(t => t.stance === 'oppose');
    if (supportData.length === 0 && opposeData.length === 0) return '';
    const allWeeks = [...new Set(timeline.map(t => t.week_start))].sort();
    if (allWeeks.length < 2) return '';

    const supportByWeek = {};
    supportData.forEach(t => { supportByWeek[t.week_start] = t.weekly_receipts || 0; });
    const opposeByWeek = {};
    opposeData.forEach(t => { opposeByWeek[t.week_start] = t.weekly_receipts || 0; });

    // Per-side scaling — iteration 3.
    const maxSupportWeekly = Math.max(0, ...Object.values(supportByWeek));
    const maxOpposeWeekly = Math.max(0, ...Object.values(opposeByWeek));
    if (maxSupportWeekly === 0 && maxOpposeWeekly === 0) return '';

    // Find peak week per side for annotation.
    let supportPeak = {week: null, amount: 0};
    let opposePeak = {week: null, amount: 0};
    Object.entries(supportByWeek).forEach(([w, a]) => {
        if (a > supportPeak.amount) supportPeak = {week: w, amount: a};
    });
    Object.entries(opposeByWeek).forEach(([w, a]) => {
        if (a > opposePeak.amount) opposePeak = {week: w, amount: a};
    });

    let sampledWeeks = allWeeks;
    if (allWeeks.length > 60) {
        const step = Math.ceil(allWeeks.length / 60);
        sampledWeeks = allWeeks.filter((_, i) => i % step === 0);
    }

    let html = '<div class="finance-timeline">';
    html += '<h4>Weekly fundraising flow</h4>';
    html += '<div class="finance-chart">';
    sampledWeeks.forEach(week => {
        const sAmt = supportByWeek[week] || 0;
        const oAmt = opposeByWeek[week] || 0;
        const sHeight = maxSupportWeekly > 0 ? sAmt / maxSupportWeekly * 100 : 0;
        const oHeight = maxOpposeWeekly > 0 ? oAmt / maxOpposeWeekly * 100 : 0;
        if (sHeight > 0) html += `<div class="finance-chart-bar support" style="height:${sHeight}%"></div>`;
        if (oHeight > 0) html += `<div class="finance-chart-bar oppose" style="height:${oHeight}%"></div>`;
    });
    html += '</div>';
    // Date axis + peak annotations + legend...
    return html;
}
```

Bars render in a flex row, all growing from the same baseline.

## Reference data — what PROP_22_2020 looks like

Support side ($188.6M total across ~14 active weeks):
- Vast majority of activity in Aug-Nov 2020 (4 months before election)
- Single dominant week: 2020-08-31 = $141.8M (the consolidated
  gig-company contribution)
- Other notable weeks: ~$10-20M in early Sept, late Oct, early Nov

Oppose side ($18.9M total across ~30 active weeks):
- More gradual — labor unions chipping in over time
- Peak week: 2020-09-07 = $3.4M
- Most weeks $0.5-1.5M

Election: 2020-11-03

So the temporal story is something like: *"Support raised
~$140M in one massive consolidated payment 9 weeks before election,
plus smaller follow-ups; oppose raised ~$19M over a much longer
period without any single dominant payment."* That narrative
matters; the chart should reveal it.
