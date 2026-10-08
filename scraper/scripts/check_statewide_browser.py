#!/usr/bin/env python3
"""Check actual candidate HTML/JSON in Chromium, blocking external requests."""
import argparse
import hashlib
import json
import mimetypes
from pathlib import Path
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup

from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site-dir', type=Path, required=True)
    parser.add_argument('--review', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    measures = json.loads((args.site_dir / 'measures-data.json').read_text(encoding='utf-8'))
    review = json.loads(args.review.read_text(encoding='utf-8'))
    numbers = [e['proposition_number'] for e in review['entries']]
    by_number = {m['proposition_number']: m for m in measures if m.get('proposition_number')}
    # Independently inspect the complete static bundle, including the old URL.
    page_ids = {int(p.stem) for p in (args.site_dir / 'measures').glob('*.html')}
    assert page_ids == {m['id'] for m in measures}
    sitemap = ET.parse(args.site_dir / 'sitemap.xml')
    urls = {e.text for e in sitemap.findall('.//{*}loc')}
    assert len(urls) == len(measures) + 2
    assert all(f'https://cal-vgp.igorgeyn.com/measures/{i}.html' in urls for i in page_ids)
    for row in [*by_number.values(), next(m for m in measures if m['id'] == 1)]:
        soup = BeautifulSoup((args.site_dir / 'measures' / f'{row["id"]}.html').read_text(encoding='utf-8'), 'html.parser')
        assert (row.get('official_description') or row['status_reason']) in soup.get_text(' ', strip=True)
        assert soup.select_one('.cta')['href'] == f'/#m={row["id"]}'
        assert soup.select_one('.src a')['href'] == row['source_url']
    cases = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        for label, width, height in [('desktop', 1440, 1000), ('mobile', 390, 844)]:
            page = browser.new_page(viewport={'width': width, 'height': height})
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))

            def route(request):
                path = urlparse(request.request.url).path
                if urlparse(request.request.url).netloc != 'statewide.test':
                    request.abort()
                else:
                    target = (args.site_dir / path.lstrip('/')).resolve()
                    if target.is_dir():
                        target = target / 'index.html'
                    if target.is_relative_to(args.site_dir.resolve()) and target.is_file():
                        request.fulfill(path=str(target), content_type=mimetypes.guess_type(target)[0] or 'application/octet-stream')
                    else:
                        request.abort()

            page.route('**/*', route)
            page.goto('https://statewide.test/', wait_until='domcontentloaded')
            page.wait_for_function('(n) => typeof allMeasures !== "undefined" && allMeasures.length === n', arg=len(measures))
            assert page.evaluate('heroMeasures.map(m => m.proposition_number)') == numbers
            assert page.locator('#heroGrid .measure-card').count() == len(numbers)
            assert page.locator('#statewideUpcomingCount').inner_text() == f'{len(numbers)} measures'
            assert page.evaluate('(id) => allMeasures.some(m => m.id === id && m.ballot_status === "withdrawn")', review['withdrawal']['id'])
            page.locator('#heroGrid').scroll_into_view_if_needed()
            page.screenshot(path=str(args.output_dir / f'{label}-slate.png'))
            for index, number in enumerate(numbers):
                row = next(m for m in measures if m.get('proposition_number') == number)
                card = page.locator('#heroGrid .measure-card').nth(index)
                assert row['official_description'][:150] in card.inner_text()
                assert 'Official CA SOS description' in card.inner_text()
                card.click()
                assert page.locator('#measureDetailModal').is_visible()
                assert page.locator('#modalMeasureId').inner_text() == f'Prop {number}'
                assert page.locator('#modalTitle').inner_text() == row['official_title']
                assert page.locator('#modalSummary').inner_text() == row['official_description']
                assert 'California Secretary of State' in page.locator('#modalSummarySource').inner_text()
                assert page.locator('#modalSummarySource a').get_attribute('href') == row['source_url']
                assert 'Circulating' not in page.locator('#modalTimeline').inner_text()
                assert 'On the November 3, 2026 ballot.' in page.locator('#modalTimeline').inner_text()
                assert page.evaluate('(m) => getMeasureStage(m)', row) == 3
                assert page.locator('#modalLinks a').evaluate_all('(links,url) => links.some(a => a.href === url)', row['source_url'])
                assert page.url.endswith(f'#m={row["id"]}')
                if number == 3:
                    page.screenshot(path=str(args.output_dir / f'{label}-prop3.png'))
                page.locator('#measureDetailModal .modal-close').click()

            search_results = []
            def search(query):
                page.locator('#searchInput').fill(query)
                page.wait_for_function('(q) => currentFilters.search === q', arg=query.lower())
                ids = page.evaluate('filteredMeasures.map(m => m.id)')
                search_results.append({'query': query, 'ids': ids,
                                       'sort': page.evaluate('currentSort'),
                                       'selected_years': page.evaluate('currentFilters.selectedYears')})
                return ids

            for number, historical in ((1, [10944, 10937, 1356]), (3, [10951, 1261]), (4, [10952, 1279])):
                short = search(f'Prop {number}')
                assert short == search(f'Proposition {number}')
                assert short[:len(historical) + 1] == [by_number[number]['id'], *historical], short
                assert not set(short) & {m['id'] for n,m in by_number.items() if n != number}
                assert page.locator('#resultsContainer .card-title').first.inner_text().startswith(f'Prop {number}:')
                assert search(f'Prop {number} 2026') == [by_number[number]['id']]
                assert search(f'Proposition {number} (2024)') == [historical[0]]
            # Query year and selected year must intersect, not override each other.
            page.evaluate('currentFilters.selectedYears = [2024]; applyFilters()')
            assert search('Proposition 3 2026') == []
            assert search('Prop 3') == [10951]
            page.evaluate('currentFilters.selectedYears = []; applyFilters()')
            page.locator('#sortSelect').select_option('year-asc')
            search('Proposition 1')
            years = page.evaluate('filteredMeasures.map(m => Number(m.year))')
            assert years == sorted(years)
            page.locator('#sortSelect').select_option('year-desc')
            assert search('ACA 13') == [1]
            assert 'withdrawn' in page.locator('#resultsContainer').inner_text().lower()
            page.screenshot(path=str(args.output_dir / f'{label}-withdrawal-search.png'))
            # Exercise the old static URL and its actual explorer link on a new document load.
            page.goto('https://statewide.test/measures/1.html', wait_until='domcontentloaded')
            assert 'Withdrawn' in page.locator('body').inner_text()
            assert 'June 25, 2026' in page.locator('body').inner_text()
            page.locator('.cta').click()
            page.wait_for_selector('#measureDetailModal', state='visible')
            assert page.url.endswith('#m=1')
            assert page.locator('#modalSummary').inner_text() == review['withdrawal']['status_reason']
            assert page.locator('#modalBadges').inner_text().lower().startswith('withdrawn')
            assert page.locator('#modalTimelineSection').is_hidden()
            assert 'withdrawal' in page.locator('#modalLinks').inner_text().lower()
            page.screenshot(path=str(args.output_dir / f'{label}-withdrawal-detail.png'))
            page.locator('#measureDetailModal .modal-close').click()
            page.goto('about:blank')
            page.goto('https://statewide.test/#m=1', wait_until='domcontentloaded')
            page.wait_for_selector('#measureDetailModal', state='visible')
            assert page.locator('#modalSummary').inner_text() == review['withdrawal']['status_reason']
            page.locator('#measureDetailModal .modal-close').click()
            page.evaluate("currentFilters.status = ['pending']; applyFilters()")
            assert not page.evaluate('filteredMeasures.some(m => m.id === 1)')
            page.evaluate("currentFilters.status = ['withdrawn']; applyFilters()")
            assert page.evaluate('filteredMeasures.map(m => m.id)') == [1]
            page.evaluate("setView('list')")
            assert 'withdrawn' in page.locator('.measure-list-item').inner_text().lower()
            county_rows = [m for m in measures if m.get('official_documents')]
            assert len(county_rows) == 49 and sum(len(m['official_documents']) for m in county_rows) == 239
            for source in ('SB_County_Registrar', 'SMC_County_Registrar'):
                row = next(m for m in county_rows if m['data_source'] == source)
                page.evaluate('(m) => viewMeasure(m)', row)
                assert page.locator('#modalOfficialDocuments a').count() == len(row['official_documents'])
            finance = next(m for m in measures if m.get('year') == 2022 and m['measure_id'] == 'PROP_27')
            page.evaluate('(m) => viewMeasure(m)', finance)
            page.evaluate("switchModalTab('finance')")
            assert page.locator('#modalFinanceSection').is_visible()
            assert len(page.locator('#modalFinanceContent').inner_text()) > 100
            assert page.locator('#modalOfficialDocuments').is_hidden()
            static_counties = []
            for source in ('SB_County_Registrar', 'SMC_County_Registrar'):
                row = max((m for m in county_rows if m['data_source'] == source), key=lambda m: len(m['official_documents']))
                page.goto(f'https://statewide.test/measures/{row["id"]}.html', wait_until='domcontentloaded')
                links = page.locator('.official-documents a')
                assert links.count() == len(row['official_documents'])
                assert links.evaluate_all('(els) => els.map(e => e.href)') == [d['source_url'] for d in row['official_documents']]
                assert 'Last captured 2026-09-07' in page.locator('.official-documents').inner_text()
                assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
                links.first.focus()
                page.keyboard.press('Tab')
                assert links.nth(1).evaluate('(e) => e === document.activeElement')
                assert links.nth(1).evaluate('(e) => getComputedStyle(e).outlineStyle !== "none"')
                page.screenshot(path=str(args.output_dir / f'{label}-{source}-documents.png'), full_page=True)
                page.locator('.cta').click()
                page.wait_for_selector('#measureDetailModal', state='visible')
                assert page.url.endswith(f'#m={row["id"]}')
                assert page.locator('#modalOfficialDocuments a').count() == len(row['official_documents'])
                static_counties.append(row['id'])
            reviewed = next(m for m in county_rows if m['id'] == 12419)
            corrected = next(d for d in reviewed['official_documents'] if d.get('role_review_note'))
            assert corrected['roles'] == ['argument_for']
            page.goto('https://statewide.test/measures/12419.html', wait_until='domcontentloaded')
            corrected_link = page.locator('.official-documents a').filter(has_text='Argument in favor')
            assert corrected_link.count() == 1 and 'Impartial analysis' not in corrected_link.inner_text()
            assert corrected['role_review_note'] in page.locator('.official-documents').inner_text()
            assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
            page.screenshot(path=str(args.output_dir / f'{label}-measure-z-role-review.png'), full_page=True)
            page.locator('.cta').click()
            page.wait_for_selector('#measureDetailModal', state='visible')
            assert corrected['role_review_note'] in page.locator('#modalOfficialDocuments').inner_text()
            assert not page.locator('#modalOfficialDocuments a').filter(has_text='Impartial analysis').count()
            assert not errors, errors
            cases.append({'viewport': label, 'propositions': numbers, 'all_modals_checked': True,
                          'typed_search_results': search_results, 'withdrawal_routes_and_filters': True,
                          'official_descriptions_and_attribution': True, 'county_document_groups': 49,
                          'county_links': 239, 'finance_preserved': True, 'page_errors': errors,
                          'reviewed_document_role_correction': 12419,
                          'county_static_keyboard_and_explorer_routes': static_counties})
            page.close()
        browser.close()
    result = {'cases': cases, 'external_requests_blocked': True,
              'static_pages_verified': len(page_ids), 'sitemap_urls_verified': len(urls),
              'html_sha256': hashlib.sha256((args.site_dir / 'index.html').read_bytes()).hexdigest(),
              'json_sha256': hashlib.sha256((args.site_dir / 'measures-data.json').read_bytes()).hexdigest()}
    (args.output_dir / 'browser-report.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({**{k:v for k,v in result.items() if k != 'cases'},
                      'viewports_passed': [c['viewport'] for c in cases]}, indent=2))


if __name__ == '__main__':
    main()
