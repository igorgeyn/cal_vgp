"""Pure Explore presentation rules, shared by the generated browser and Node tests."""

SCRIPT = r"""
const Explore = (() => {
    function yearSpan(years) {
        const valid = years.filter(y => y !== null && y !== '').map(Number).filter(Number.isInteger);
        if (!valid.length) return 'Years unavailable';
        const first = Math.min(...valid), last = Math.max(...valid);
        return first === last ? String(first) : `${first}–${last}`;
    }
    function yearRanges(years) {
        // "2011, 2013, 2015, 2022–24": distinct years, consecutive runs collapsed.
        const sorted = [...new Set(years.filter(y => y !== null && y !== '').map(Number).filter(Number.isInteger))].sort((a, b) => a - b);
        if (!sorted.length) return 'Years unavailable';
        const runs = [];
        for (const year of sorted) {
            const last = runs[runs.length - 1];
            if (last && year === last[1] + 1) last[1] = year; else runs.push([year, year]);
        }
        return runs.map(([a, b]) => a === b ? String(a)
            : String(a).slice(0, 2) === String(b).slice(0, 2) ? `${a}–${String(b).slice(-2)}` : `${a}–${b}`).join(', ');
    }
    function decadeLabel(years) {
        const span = yearSpan(years);
        const [first, last] = span.split('–');
        return last && first.slice(0, 2) === last.slice(0, 2) ? `${first}–${last.slice(-2)}` : span;
    }
    function coverage(measures, column) {
        let counted = 0, missingColumn = 0, missingOutcome = 0;
        for (const measure of measures) {
            if (measure.passed !== 0 && measure.passed !== 1) missingOutcome++;
            else if (!String(measure[column] ?? '').trim()) missingColumn++;
            else counted++;
        }
        return {total: measures.length, counted, missingColumn, missingOutcome};
    }
    function tint(fraction) {
        const t = Math.max(0, Math.min(1, Number(fraction) || 0));
        // One slate hue; even the darkest endpoint supports dark text.
        return `rgb(${Math.round(241 - 80*t)}, ${Math.round(245 - 64*t)}, ${Math.round(248 - 53*t)})`;
    }
    function cell(passed, total, minN = 5, reason = null) {
        // `reason` forces counts only (e.g. a county or Status filter), whatever the size.
        const rated = !reason && total >= Math.max(5, minN);
        return {
            rated,
            text: rated ? `${Math.round(100 * passed / total)}%` : `${passed} of ${total}`,
            subtext: rated ? `${total} measures` : (total ? 'count only' : 'no measures'),
            bg: rated ? tint(passed / total) : 'transparent',
            label: `${passed} of ${total} passed${rated ? '' : '; ' + (reason || 'too few to show a rate')}`
        };
    }
    function compareCells(a, b, value, direction = 'desc', minN = 5) {
        const ar = a.total >= Math.max(5, minN), br = b.total >= Math.max(5, minN);
        if (ar !== br) return ar ? -1 : 1;
        if (!ar) return 0;
        const av = value(a), bv = value(b);
        if (!Number.isFinite(av) || !Number.isFinite(bv)) {
            return Number.isFinite(av) ? -1 : Number.isFinite(bv) ? 1 : 0;
        }
        return direction === 'desc' ? bv - av : av - bv;
    }
    return {yearSpan, yearRanges, decadeLabel, coverage, tint, cell, compareCells};
})();
"""

STYLE = """
/* Explore E1: contained scrolling, readable counts and one neutral hue. */
.matrix-wrapper { min-width: 0; max-width: 100%; color: #172934; }
.matrix-wrapper .explore-heading { margin: 0; padding: 1rem 1rem .35rem; font-size: 1.3rem; }
.matrix-wrapper .explore-coverage, .matrix-wrapper .explore-note { margin: 0; padding: .3rem 1rem .6rem; line-height: 1.5; }
.matrix-wrapper .explore-note { font-size: .85rem; color: #374955; }
.matrix-wrapper .explore-filters { display: flex; flex-wrap: wrap; gap: .4rem; padding: .5rem 1rem; }
.matrix-wrapper .explore-filters button { max-width: 100%; overflow-wrap: anywhere; white-space: normal; padding: .4rem .6rem; background: white; color: #172934; border: 1px solid #8996a0; border-radius: .4rem; cursor: pointer; }
.matrix-wrapper .matrix-toolbar, .matrix-wrapper .matrix-toolbar-group { min-width: 0; max-width: 100%; flex-wrap: wrap; }
.matrix-wrapper .matrix-toolbar label { max-width: 100%; }
.matrix-wrapper .matrix-toolbar select { min-width: 0; max-width: 100%; }
.matrix-wrapper .matrix-legend { flex-wrap: wrap; color: #172934; width: 100%; }
.matrix-wrapper .explore-legend-scale { display: flex; flex-wrap: wrap; gap: .3rem; }
.matrix-wrapper .explore-legend-scale span { padding: .25rem .4rem; border-radius: .2rem; }
.matrix-wrapper .matrix-scroll, .matrix-wrapper .matrix-top-scroll { max-width: 100%; }
.matrix-wrapper .matrix-cell { color: #172934; border: 1px solid transparent; }
.matrix-wrapper .matrix-cell .cell-rate, .matrix-wrapper .matrix-cell .cell-count { color: #172934; text-shadow: none; }
.matrix-wrapper .matrix-cell .cell-count { font-size: .75rem; }
.matrix-wrapper .matrix-cell.count-only { border-color: #8996a0; }
.matrix-wrapper .matrix-totals td { font-weight: 700; }
.matrix-wrapper .matrix-totals td:first-child { background: #fdfcfa; color: #172934; }
.matrix-cell-modal .matrix-modal-metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.matrix-cell-modal .matrix-modal-metric { color: #172934; }
/* An older narrow-screen rule (.matrix-toolbar span:first-child) would stretch the first swatch. */
.matrix-wrapper .explore-legend-scale span:first-child { flex-basis: auto; }
.matrix-wrapper .explore-level { display: inline-flex; gap: .25rem; }
.matrix-wrapper details.explore-notes { padding: 0 1rem .5rem; }
.matrix-wrapper details.explore-notes summary { cursor: pointer; font-size: .85rem; color: #374955; }
.matrix-wrapper details.explore-notes .explore-note { padding-left: 0; padding-right: 0; }
.matrix-wrapper .explore-caution { margin: 0 1rem .6rem; padding: .5rem .75rem; border-left: 3px solid #8996a0; background: #f4f6f8; color: #172934; font-size: .9rem; }
"""
