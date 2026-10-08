"""Exercise Grid/List wayfinding against an isolated generated site, without external requests."""
from __future__ import annotations

import argparse
import json
import mimetypes
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site-dir', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--widths', type=int, nargs='+', default=[1440, 768, 640, 390, 320])
    args = parser.parse_args()
    root = args.site_dir.resolve()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    records = json.loads((root / 'measures-data.json').read_text(encoding='utf-8'))
    report = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for width in args.widths:
            page = browser.new_page(viewport={'width': width, 'height': 1000 if width > 640 else 844}, reduced_motion='reduce')
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))

            def route(request):
                url = urlparse(request.request.url)
                path = (root / (url.path.lstrip('/') or 'index.html')).resolve()
                if url.netloc == 'browse.test' and path.is_relative_to(root) and path.is_file():
                    request.fulfill(path=str(path), content_type=mimetypes.guess_type(path)[0] or 'application/octet-stream')
                else:
                    request.abort()

            def ready():
                page.wait_for_function('(n) => typeof allMeasures !== "undefined" && allMeasures.length === n && document.getElementById("heroSection").dataset.rendered', arg=len(records))

            def positioned(target):
                box = page.locator('#' + target).bounding_box()
                header = page.locator('.header').bounding_box()
                assert box and header and box['y'] >= header['y'] + header['height'] - 1, (width, target, box, header)
                assert box['y'] < page.viewport_size['height'] - 20, (width, target, box)
                if not page.evaluate('document.documentElement.scrollWidth <= innerWidth'):
                    page.screenshot(path=str(args.output_dir / f'{width}-overflow.png'))
                    overflow = page.evaluate('''() => [...document.querySelectorAll('body *')].filter(e => {
                        const r = e.getBoundingClientRect();
                        for (let p = e.parentElement; p && p !== document.body; p = p.parentElement) {
                            if (['hidden', 'clip', 'auto', 'scroll'].includes(getComputedStyle(p).overflowX)) return false;
                        }
                        return r.width && r.right > innerWidth + 1;
                    }).slice(0, 15).map(e => ({tag: e.tagName, cls: e.className, id: e.id, width: e.getBoundingClientRect().width}))''')
                    raise AssertionError((width, overflow))

            page.route('**/*', route)
            page.goto('https://browse.test/', wait_until='domcontentloaded')
            ready()
            baseline_filtered = page.evaluate('filteredMeasures.length')
            assert page.locator('.header button[onclick="openAboutModal()"]').get_attribute('aria-pressed') is None
            assert page.locator('#browse-navigation a').all_text_contents() == ['Statewide measures', 'Local measures', 'Full grid']
            assert page.evaluate('''() => {
                const ids = ['browse-navigation', 'statewide-measures', 'local-measures', 'full-catalog', 'resultsContainer'];
                return ids.every((id, i) => !i || !!(document.getElementById(ids[i-1]).compareDocumentPosition(document.getElementById(id)) & Node.DOCUMENT_POSITION_FOLLOWING));
            }''')
            page.keyboard.press('Tab')
            assert page.locator('.browse-skip-link').evaluate('(e) => e === document.activeElement')
            page.keyboard.press('Enter')
            assert page.locator('#main-content').evaluate('(e) => e === document.activeElement')
            page.screenshot(path=str(args.output_dir / f'{width}-grid-top.png'))

            for view in ('grid', 'list'):
                page.locator('#' + view + 'View').click()
                assert page.locator('#catalogJumpLink').inner_text() == 'Full ' + view
                assert page.locator('#full-catalog').inner_text() == 'Full ' + view
                for target in ('statewide-measures', 'local-measures', 'full-catalog'):
                    link = page.locator('#browse-navigation a[data-browse-jump="' + target + '"]')
                    link.focus()
                    page.keyboard.press('Enter')
                    assert page.locator('#' + target).evaluate('(e) => e === document.activeElement')
                    positioned(target)
                    assert page.url.endswith('#' + target)
                    # A second activation of the same URL must still jump and focus.
                    link.focus()
                    page.keyboard.press('Enter')
                    positioned(target)
                    if target == 'local-measures':
                        page.keyboard.press('Tab')
                        assert page.locator('.upcoming-local-band .browse-return').evaluate('(e) => e === document.activeElement')
                        page.keyboard.press('Tab')
                        assert page.locator('#localCountySelect').evaluate('(e) => e === document.activeElement')
                page.keyboard.press('Tab')
                assert page.locator('#catalogHeader .browse-return').evaluate('(e) => e === document.activeElement')
                page.keyboard.press('Enter')
                assert page.locator('#browse-navigation').evaluate('(e) => e === document.activeElement')
                positioned('browse-navigation')
                assert page.locator('#resultsContainer .results-' + view).is_visible()

            # Search affects the catalog while both current-election targets remain useful.
            page.locator('#searchInput').fill('zzzz-unmatched-navigation-test')
            page.wait_for_function('filteredMeasures.length === 0')
            positioned('full-catalog')
            assert page.locator('#heroGrid .statewide-card').count() == 14
            page.locator('#browse-navigation a[data-browse-jump="local-measures"]').click()
            positioned('local-measures')
            assert page.locator('#browse-navigation a[data-browse-jump="local-measures"]').evaluate('(e) => e === document.activeElement')
            assert page.locator('#searchInput').input_value() == 'zzzz-unmatched-navigation-test'
            page.locator('#searchInput').fill('')
            page.wait_for_function('(n) => filteredMeasures.length === n', arg=baseline_filtered)
            page.locator('#localCountySelect').select_option('San Mateo')
            local_before = page.locator('#localUpcomingCount').inner_text()
            page.locator('#browse-navigation a[data-browse-jump="full-catalog"]').click()
            page.locator('.pagination-btn[title="Next page"]').click()
            assert page.evaluate('pagination.currentPage') == 2
            assert '?view=list&page=2#full-catalog' in page.url
            page.locator('#browse-navigation a[data-browse-jump="local-measures"]').click()
            assert page.locator('#localCountySelect').input_value() == 'San Mateo'
            assert page.locator('#localUpcomingCount').inner_text() == local_before
            page.go_back(wait_until='domcontentloaded')
            page.wait_for_function('location.hash === "#full-catalog"')
            positioned('full-catalog')
            assert page.evaluate('pagination.currentPage') == 2
            page.go_forward(wait_until='domcontentloaded')
            page.wait_for_function('location.hash === "#local-measures"')
            positioned('local-measures')

            # Shared/reloaded section URLs restore List and land after data has loaded.
            page.reload(wait_until='domcontentloaded')
            ready()
            page.wait_for_timeout(100)
            assert page.evaluate('currentView') == 'list'
            assert page.evaluate('pagination.currentPage') == 2
            positioned('local-measures')
            page.locator('#browse-navigation a[data-browse-jump="full-catalog"]').click()
            page.screenshot(path=str(args.output_dir / f'{width}-list-catalog.png'))
            before_modal = page.url
            row = page.locator('#resultsContainer .measure-list-item').first
            row.focus()
            page.keyboard.press('Enter')
            assert page.locator('#measureDetailModal').is_visible()
            assert '#m=' in page.url
            page.locator('#measureDetailModal .modal-close').click()
            assert page.url == before_modal

            page.locator('#insightsView').click()
            assert not page.locator('#browse-navigation').is_visible()
            assert not page.locator('#catalogHeader').is_visible()
            page.locator('#exploreView').click()
            assert not page.locator('#heroSection').is_visible()
            assert not page.locator('#browse-navigation').is_visible()
            assert not page.locator('#catalogHeader').is_visible()
            page.locator('#gridView').click()
            assert page.locator('#browse-navigation').is_visible()
            assert page.locator('#heroSection').is_visible()

            page.goto('https://browse.test/#page=2', wait_until='domcontentloaded')
            ready()
            page.wait_for_timeout(100)
            assert page.evaluate('pagination.currentPage') == 2
            positioned('full-catalog')
            mid = next(m['id'] for m in records if m.get('statewide_guide'))
            page.goto(f'https://browse.test/?view=list#m={mid}', wait_until='domcontentloaded')
            ready()
            assert page.locator('#measureDetailModal').is_visible()
            assert page.evaluate('currentView') == 'list'
            page.locator('#measureDetailModal .modal-close').click()
            assert page.url == 'https://browse.test/?view=list'

            # Text enlargement plus a 640 CSS-pixel viewport covers a desktop 200% reflow case.
            if width == 640:
                page.add_style_tag(content='html { font-size: 200% !important; }')
                for target in ('statewide-measures', 'local-measures', 'full-catalog'):
                    page.locator('#browse-navigation a[data-browse-jump="' + target + '"]').click()
                    positioned(target)
                page.screenshot(path=str(args.output_dir / '640-enlarged-text.png'))
            assert not errors, errors
            report.append({'width': width, 'grid_and_list': 'PASS', 'keyboard_focus_and_offset': 'PASS',
                           'filters_county_pagination_history_reload': 'PASS', 'legacy_and_measure_links': 'PASS',
                           'page_errors': errors})
            page.close()
        browser.close()
    (args.output_dir / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
