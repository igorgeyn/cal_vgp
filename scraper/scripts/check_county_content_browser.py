"""Check every reviewed county question, citation and history link in browser."""
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
    args = parser.parse_args()
    root = args.site_dir.resolve()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    rows = json.loads((root/'measures-data.json').read_text(encoding='utf-8'))
    reviewed = [m for m in rows if m.get('county_guide')]
    assert len(reviewed) == 49, 'The complete two-county release must contain 49 reviewed records'
    by_id = {m['id']:m for m in rows}
    report = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for width in (1440,390,320):
            page = browser.new_page(viewport={'width':width,'height':950}, reduced_motion='reduce')
            errors=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            def route(r):
                url=urlparse(r.request.url)
                path=(root/(url.path.lstrip('/') or 'index.html')).resolve()
                if url.netloc=='county.test' and path.is_relative_to(root) and path.is_file():
                    r.fulfill(path=str(path),content_type=mimetypes.guess_type(path)[0] or 'application/octet-stream')
                else:r.abort()
            page.route('**/*',route)
            page.goto('https://county.test/',wait_until='domcontentloaded')
            page.wait_for_function('(n)=>typeof allMeasures!=="undefined" && allMeasures.length===n && document.getElementById("heroSection").dataset.rendered',arg=len(rows))
            page.locator('#local-measures').evaluate('(el)=>window.scrollTo(0,el.getBoundingClientRect().top+scrollY-100)')
            page.screenshot(path=str(args.output_dir/f'{width}-local-cards.png'))
            first=page.locator('.local-measure-card').first
            first.focus()
            page.keyboard.press('Enter')
            assert page.locator('#measureDetailModal').is_visible()
            for m in reviewed:
                page.evaluate('(id)=>viewMeasure(allMeasures.find(m=>m.id===id))',m['id'])
                assert page.locator('#modalSummary').text_content()==m['county_explanation']
                assert 'truncated' not in (page.locator('#modalSummary').get_attribute('class') or '')
                assert page.locator('#modalCountyGuide blockquote').text_content()==m['county_guide']['question']
                assert not page.locator('#modalBallotQuestion').is_visible()
                assert 'Approval requirement:' in page.locator('#modalCountyGuide').inner_text()
                assert 'Filed' not in page.locator('#modalTimeline').inner_text()
                page.evaluate("switchModalTab('finance')")
                assert 'has not yet linked campaign-finance filings' in page.locator('#modalFinanceContent').inner_text()
                assert page.locator('#modalFinanceContent a').get_attribute('href').startswith('https://')
                page.evaluate("switchModalTab('main')")
                for source in m['county_guide']['sources']:
                    assert page.locator('#modalCountyGuide a').evaluate_all('(nodes,url)=>nodes.some(a=>a.href===url)',source['url']+'#page='+str(source['pages'][0]))
                history=m.get('local_historical_context')
                if history and history.get('record_ids'):
                    assert len(history['record_ids'])==history['total']
                    assert len(set(history['record_ids']))==history['total']
                    assert sum(by_id[i]['passed']==1 for i in history['record_ids'])==history['passed']
                    assert all(by_id[i]['county']==m['county'] and by_id[i]['year']<m['year'] for i in history['record_ids'])
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),(width,m['id'])
                if m['id'] in (12418,12442,12443):
                    page.screenshot(path=str(args.output_dir/f'{width}-{m["id"]}-modal.png'))
            page.evaluate('closeMeasureDetail()')
            # An old measure must not inherit the previous county guide.
            old=next(m for m in rows if m['id']<100 and not m.get('county_guide') and not m.get('statewide_guide'))
            page.evaluate('(id)=>viewMeasure(allMeasures.find(m=>m.id===id))',old['id'])
            assert not page.locator('#modalCountyGuide').is_visible()
            assert 'has not yet linked campaign-finance filings' not in page.locator('#modalFinanceContent').inner_text()
            for m in reviewed:
                page.goto(f'https://county.test/measures/{m["id"]}.html',wait_until='domcontentloaded')
                assert page.locator('.county-guide blockquote').text_content()==m['county_guide']['question']
                assert m['county_explanation'] in page.locator('body').inner_text()
                assert 'has not yet linked campaign-finance filings' in page.locator('body').inner_text()
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),(width,m['id'],'standalone')
                for href in page.locator('.county-history a').evaluate_all('(nodes)=>nodes.map(a=>a.getAttribute("href"))'):
                    assert (root/href.lstrip('/')).is_file()
            assert not errors,errors
            report.append(dict(width=width,reviewed=len(reviewed),errors=errors))
            page.close()
        browser.close()
    (args.output_dir/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))

if __name__=='__main__':main()
