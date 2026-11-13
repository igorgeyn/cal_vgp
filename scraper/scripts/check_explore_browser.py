"""Check Explore against an isolated site; all external requests are blocked."""
from __future__ import annotations

import argparse
import json
import mimetypes
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright


def expected_coverage(records, *, county=None, year=None, field='display_category_type'):
    # Independent reproduction of the catalog's default current-pending exclusion.
    selected = [m for m in records
                if (county is None or str(m.get('county', '')).casefold() == county.casefold())
                and (year is None or m.get('year') == year)
                and (year is not None or not (
                    (m.get('year') or 0) >= 2026 and m.get('passed') not in (0, 1)
                    and m.get('ballot_status') != 'withdrawn'))]
    unknown = sum(m.get('passed') not in (0, 1) for m in selected)
    missing = sum(m.get('passed') in (0, 1) and not str(m.get(field) or '').strip() for m in selected)
    return {'total': len(selected), 'counted': len(selected)-unknown-missing,
            'missingColumn': missing, 'missingOutcome': unknown}


CELL_CHECK = r"""() => {
    const rgb = value => value.match(/[\d.]+/g).map(Number);
    const luminance = channels => channels.slice(0,3).map(v=>{
        v /= 255; return v<=.04045 ? v/12.92 : ((v+.055)/1.055)**2.4;
    }).reduce((s,v,i)=>s+v*[.2126,.7152,.0722][i],0);
    let minimum=Infinity, small=0;
    for (const cell of document.querySelectorAll('.matrix-wrapper .matrix-cell')) {
        const n=Number(cell.dataset.n), cs=getComputedStyle(cell);
        if(n<5) {
            small++;
            if(cell.textContent.includes('%') || rgb(cs.backgroundColor)[3] !== 0 || cell.dataset.rated !== 'false')
                throw Error('Small cell shows rate or fill: '+cell.outerHTML);
        }
        let parent=cell, background;
        while(parent) {
            const color=rgb(getComputedStyle(parent).backgroundColor);
            if(color.length===3 || color[3]===1) {background=color;break;}
            parent=parent.parentElement;
        }
        background=background || [255,255,255];
        for(const text of cell.querySelectorAll('.cell-rate,.cell-count')) {
            const a=luminance(rgb(getComputedStyle(text).color)), b=luminance(background);
            const ratio=(Math.max(a,b)+.05)/(Math.min(a,b)+.05);
            minimum=Math.min(minimum,ratio);
            if(ratio<4.5) throw Error('Insufficient cell contrast: '+ratio);
        }
    }
    if(document.documentElement.scrollWidth>innerWidth) throw Error('Document overflow');
    return {minimumContrast:Number.isFinite(minimum)?minimum:null,smallCells:small};
}"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site-dir', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    root = args.site_dir.resolve()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    records = json.loads((root / 'measures-data.json').read_text(encoding='utf-8'))
    report = {'widths': [], 'failures': [], 'catalogRecords': len(records)}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for width in (1440, 768, 390, 320):
            page = browser.new_page(viewport={'width': width, 'height': 1000 if width>768 else 844}, reduced_motion='reduce')
            errors = []
            page.on('pageerror', lambda e: errors.append(str(e)))

            def route(request):
                url = urlparse(request.request.url)
                path = (root / (url.path.lstrip('/') or 'index.html')).resolve()
                if url.netloc == 'explore.test' and path.is_relative_to(root) and path.is_file():
                    request.fulfill(path=str(path), content_type=mimetypes.guess_type(path)[0] or 'application/octet-stream')
                else:
                    request.abort()

            def coverage(expected):
                actual = page.locator('.explore-coverage').evaluate('e=>Object.fromEntries(Object.entries(e.dataset).map(([k,v])=>[k,Number(v)]))')
                assert actual == expected, (actual, expected)
                assert actual['counted'] + actual['missingColumn'] + actual['missingOutcome'] == actual['total']
                return actual

            try:
                page.route('**/*', route)
                page.goto('https://explore.test/', wait_until='domcontentloaded')
                page.wait_for_function('(n)=>typeof allMeasures!=="undefined" && allMeasures.length===n && filteredMeasures.length>0', arg=len(records))
                page.locator('#exploreView').click()
                assert page.evaluate("matrixState.colField==='measureType' && matrixState.rowGrouping==='decade' && matrixState.minN===5")
                labels = page.locator('.matrix-table tbody tr:not(.matrix-totals) td:first-child').all_text_contents()
                starts = [int(label.strip()[:4]) for label in labels]
                assert starts == sorted(starts)
                assert '1998–99' in labels[0], labels
                baseline = coverage(expected_coverage(records))
                checks = page.evaluate(CELL_CHECK)
                assert not page.locator('.matrix-insight-strip, .matrix-insight-card').count()
                assert not page.locator('.matrix-wrapper option[value="jurisdiction"], .matrix-wrapper option[value="close"], .matrix-wrapper option[value="trap"]').count()
                assert 'Threshold' not in page.locator('.matrix-toolbar').inner_text()
                page.screenshot(path=str(args.output_dir / f'{width}-explore.png'))

                page.evaluate("currentFilters.county='San Mateo'; applyFilters()")
                coverage(expected_coverage(records, county='San Mateo'))
                assert page.locator('.explore-filters').get_by_role('button', name='Remove County: San Mateo').count() == 1
                page.locator('[data-explore-clear]').click()
                coverage(baseline)
                page.evaluate('currentFilters.selectedYears=[2024]; applyFilters()')
                coverage(expected_coverage(records, year=2024))
                page.locator('[data-explore-filter]').click()
                coverage(baseline)
                page.evaluate("setMatrixColField('topic')")
                coverage(expected_coverage(records, field='display_topic'))
                page.evaluate(CELL_CHECK)
                page.evaluate("setMatrixRowGrouping('region')")
                for metric in ('passRate','volume','avgYes','baseline'):
                    page.evaluate('(m)=>setMatrixMetric(m)', metric)
                    page.evaluate(CELL_CHECK)
                page.evaluate('resetMatrixControls()')

                page.locator('.matrix-table tbody tr:not(.matrix-totals) td:first-child').first.click()
                assert page.evaluate("currentView==='grid'")
                page.locator('#exploreView').click()
                assert page.locator('[data-explore-filter]').count()
                page.locator('[data-explore-clear]').click()
                coverage(baseline)
                page.evaluate("currentFilters.search='no-such-measure-xyz'; applyFilters()")
                coverage(dict(total=0,counted=0,missingColumn=0,missingOutcome=0))
                page.get_by_role('button', name='Reset Explore', exact=True).click()
                coverage(baseline)

                # Deliberately small synthetic cohorts exercise real rendered cells/modal.
                page.evaluate("""() => {
                    filteredMeasures=[];
                    for(const [year,n,type] of [[1998,1,'Bond'],[2000,4,'Bond'],[2010,5,'Bond'],[1998,5,'Recall']])
                        for(let i=0;i<n;i++) filteredMeasures.push({id:year*10+i,year,passed:i?1:0,display_category_type:type,percent_yes:60});
                    setMatrixRowGrouping('year');
                }""")
                synthetic = page.evaluate(CELL_CHECK)
                assert synthetic['smallCells'] > 0
                page.locator('.matrix-cell[data-n="1"]').first.click()
                assert '%' not in page.locator('#matrixCellBody').inner_text()
                assert 'Close calls' not in page.locator('#matrixCellBody').inner_text()
                page.evaluate('closeMatrixCellModal(); resetMatrixControls()')
                coverage(baseline)
                assert not errors, errors
                report['widths'].append({'width': width, 'coverage': baseline, 'decades': labels,
                                         'cells': checks, 'synthetic': synthetic, 'pageErrors': errors})
            except Exception as error:
                report['failures'].append({'width': width, 'error': str(error), 'pageErrors': errors})
                page.screenshot(path=str(args.output_dir / f'{width}-failure.png'))
            finally:
                page.close()
        browser.close()
    (args.output_dir / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))
    return 1 if report['failures'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
