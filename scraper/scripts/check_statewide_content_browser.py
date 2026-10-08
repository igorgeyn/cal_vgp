"""Exercise all statewide reader components against an isolated site bundle."""
import argparse
import hashlib
import json
import mimetypes
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site-dir', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    root = args.site_dir.resolve()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    data = json.loads((root / 'measures-data.json').read_text(encoding='utf-8'))
    data_hash = hashlib.sha256((root / 'measures-data.json').read_bytes()).hexdigest()
    current = sorted((m for m in data if m.get('statewide_guide')), key=lambda m: m['proposition_number'])
    assert [m['proposition_number'] for m in current] == [1, 2, 3, 4, 5, 37, 38, 39, 40, 41, 42, 43, 44, 45]
    by_id = {m['id']: m for m in data}
    for m in current:
        context = m['historical_context']
        assert context['scope'] == 'statewide'
        assert not {'pass_rate','avg_yes','median_yes','closest_races'} & context.keys()
        assert all(by_id[mid]['county'] == 'Statewide' and by_id[mid]['year'] < 2026
                   for mid in context['comparison_ids'])
        assert all(t['id'] in context['comparison_ids'] for t in context['top_similar'])
    report = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for width, height in [(1440, 1000), (390, 844), (320, 800)]:
            page = browser.new_page(viewport={'width': width, 'height': height})
            errors = []
            requests = []
            page.on('pageerror', lambda e: errors.append(str(e)))
            def route(r):
                url = urlparse(r.request.url)
                if url.netloc != 'content.test':
                    r.abort()
                    return
                path = (root / url.path.lstrip('/')).resolve()
                if path.is_dir():
                    path /= 'index.html'
                if path.is_relative_to(root) and path.is_file():
                    requests.append(r.request.url)
                    r.fulfill(path=str(path), content_type=mimetypes.guess_type(path)[0] or 'application/octet-stream')
                else:
                    r.abort()
            page.route('**/*', route)
            page.goto('https://content.test/', wait_until='domcontentloaded')
            page.wait_for_function('(n) => typeof allMeasures !== "undefined" && allMeasures.length === n', arg=len(data))
            assert page.locator('#statewideUpcomingCount').inner_text() == '14 measures'
            assert any('measures-data.json?v=' + data_hash[:20] in url for url in requests)
            assert page.evaluate('document.querySelector("style").sheet.cssRules[0].type === CSSRule.IMPORT_RULE')
            page.locator('#heroGrid').scroll_into_view_if_needed()
            page.screenshot(path=str(args.output_dir / f'{width}-statewide.png'))
            card = page.locator('#heroGrid .statewide-card').first
            card.focus()
            page.keyboard.press('Enter')
            assert page.locator('#measureDetailModal').is_visible()
            assert page.locator('#modalMeasureId').inner_text() == 'Prop 1'
            checked = []
            for measure in current:
                page.evaluate('(id) => viewMeasure(allMeasures.find(m => m.id === id))', measure['id'])
                assert page.locator('#modalTitle').inner_text() == measure['official_title']
                main = page.locator('#modalStatewideMain')
                assert main.is_visible() and measure['statewide_guide']['yes_meaning'] in main.inner_text()
                assert measure['statewide_guide']['no_meaning'] in main.inner_text()
                page.locator('.modal-tab[data-tab="research"]').click()
                assert page.locator('#modalBriefingSection').is_visible()
                research = page.locator('#modalBriefingContent').inner_text()
                assert 'fiscal impact' in research.lower() and 'argument against' in research.lower(), (measure['id'], research)
                assert measure['statewide_guide']['argument_for'] in research
                page.locator('#modalBriefingContent details').evaluate_all('(nodes) => nodes.forEach(e => e.open = true)')
                assert measure['statewide_guide']['analysis'][0]['paragraphs'][0] in page.locator('#modalBriefingContent').inner_text()
                assert 'related statewide history' in page.locator('#modalHistoricalContext').inner_text().lower()
                assert 'not a representative sample' in page.locator('#modalHistoricalContext').inner_text()
                page.locator('.modal-tab[data-tab="finance"]').click()
                finance = page.locator('#modalFinanceContent')
                assert finance.is_visible() and '2026 reported campaign contributions' in finance.inner_text().lower()
                assert not page.locator('#modalFinanceEmpty').is_visible()
                finance.locator('details').evaluate_all('(nodes) => nodes.forEach(e => e.open = true)')
                for side in measure['statewide_guide']['finance'].values():
                    assert side['as_of'] in finance.inner_text()
                    if side['total'] is not None:
                        assert side['total'] in finance.inner_text()
                if not page.evaluate('document.documentElement.scrollWidth <= innerWidth'):
                    page.screenshot(path=str(args.output_dir / f'{width}-overflow.png'))
                    overflow = page.evaluate('''() => [...document.querySelectorAll('body *')].filter(e => {
                        const r=e.getBoundingClientRect();return r.width && (r.right>innerWidth+1 || r.left < -1);
                    }).slice(0,10).map(e=>({tag:e.tagName,cls:e.className,id:e.id,width:e.getBoundingClientRect().width,parent:e.parentElement.outerHTML.slice(0,700)}))''')
                    raise AssertionError((width, measure['id'], overflow))
                assert page.locator('.measure-detail-modal').evaluate('(e) => e.scrollWidth <= e.clientWidth + 1')
                if measure['proposition_number'] in (3, 39):
                    page.screenshot(path=str(args.output_dir / f'{width}-prop-{measure["proposition_number"]}-finance.png'))
                    page.locator('.modal-tab[data-tab="research"]').click()
                    page.screenshot(path=str(args.output_dir / f'{width}-prop-{measure["proposition_number"]}-research.png'))
                checked.append(measure['id'])
            # A current measure must not leak its content into local, withdrawn,
            # or historical Finance views when the same modal is reused.
            for mid in (12419, 1, 10939):
                page.evaluate('(id) => viewMeasure(allMeasures.find(m => m.id === id))', mid)
                assert not page.locator('#modalStatewideMain').is_visible()
                page.locator('.modal-tab[data-tab="finance"]').click()
                assert '2026 reported campaign contributions' not in page.locator('#tabFinance').inner_text()
                if mid == 10939:
                    assert page.locator('#modalFinanceSection').is_visible()
            page.locator('#measureDetailModal .modal-close').click()
            # Exercise actual carousel controls through the last proposition.
            for _ in range(14):
                next_button = page.locator('.hero-carousel .carousel-next')
                if next_button.is_disabled():
                    break
                next_button.click()
            last_card = page.locator('#heroGrid .statewide-card').last
            last_card.click()
            assert page.locator('#modalMeasureId').inner_text() == 'Prop 45'
            page.locator('#measureDetailModal .modal-close').click()
            page.locator('#searchInput').fill('Housing & Land Use')
            page.wait_for_function('filteredMeasures.some(m => m.id === 12467) && filteredMeasures.some(m => m.id === 12469) && currentFilters.search === "housing & land use"')
            for m in current:
                page.goto(f'https://content.test/measures/{m["id"]}.html', wait_until='domcontentloaded')
                text = page.locator('body').inner_text()
                assert 'What your vote means' in text and 'Fiscal impact' in text
                assert '2026 reported campaign contributions' in text
                assert m['statewide_guide']['yes_meaning'] in text
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            assert not errors, errors
            report.append(dict(width=width, checked_ids=checked, no_page_errors=True,
                               versioned_data=True, no_horizontal_overflow=True))
            page.close()
        browser.close()
    output = dict(html_sha256=hashlib.sha256((root / 'index.html').read_bytes()).hexdigest(), cases=report)
    (args.output_dir / 'report.json').write_text(json.dumps(output, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(output, indent=2))


if __name__ == '__main__':
    main()
