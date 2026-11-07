"""Check election status and official-results links on every surface, in a browser.

    python scraper/scripts/check_election_status_browser.py --site-dir SITE --output-dir OUT
        [--clock 2026-11-07T12:00:00-08:00]

Serves SITE from a fake host (no network), optionally fixes the browser clock,
and checks, at 1440, 390 and 320px, for every measure whose status depends on
the calendar: statewide card badge, list row, modal badge, official-results link
and note, plus the statewide and local section notes. The expected status is the
forward-only rule: the later of the build's status and the reader's clock.
Writes report.json and screenshots to OUT. Exits non-zero on any failure.
"""
import argparse
import json
import mimetypes
import sys
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.website.election_status import (  # noqa: E402
    DATE_DRIVEN_STATUSES, STATUS_LABELS, date_status, parse_election_date, pacific_date,
)

HOST = 'status.test'


def expected_status(row, reader_date):
    built = row['election_status']
    if reader_date is None:
        return built
    by_clock = date_status(parse_election_date(row['election_date']), reader_date)
    order = list(DATE_DRIVEN_STATUSES)
    return by_clock if order.index(by_clock) > order.index(built) else built


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--site-dir', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--clock', help='Fixed browser time, ISO 8601 with offset')
    args = parser.parse_args()
    root = args.site_dir.resolve()
    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    rows = json.loads((root / 'measures-data.json').read_text(encoding='utf-8'))
    current = [m for m in rows if m.get('election_status')]
    clock = datetime.fromisoformat(args.clock) if args.clock else None
    reader_date = pacific_date(clock) if clock else None
    failures, report = [], {'clock': args.clock, 'reader_date': str(reader_date) if reader_date else None,
                            'current_measures': len(current), 'widths': {}}

    def check(condition, message):
        if not condition:
            failures.append(message)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        for width in (1440, 390, 320):
            page = browser.new_page(viewport={'width': width, 'height': 950}, reduced_motion='reduce')
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            if clock:
                page.clock.set_fixed_time(clock)

            def route(request_route):
                url = urlparse(request_route.request.url)
                path = (root / (url.path.lstrip('/') or 'index.html')).resolve()
                if url.netloc == HOST and path.is_relative_to(root) and path.is_file():
                    request_route.fulfill(path=str(path),
                                          content_type=mimetypes.guess_type(path)[0] or 'application/octet-stream')
                else:
                    request_route.abort()
            page.route('**/*', route)
            page.goto(f'https://{HOST}/', wait_until='domcontentloaded')
            page.wait_for_function(
                '(n)=>typeof allMeasures!=="undefined" && allMeasures.length===n && document.getElementById("heroSection").dataset.rendered',
                arg=len(rows))
            tag = f'{width}px'
            statuses = {}
            for row in current:
                want = expected_status(row, reader_date)
                statuses[want] = statuses.get(want, 0) + 1
                label = STATUS_LABELS[want]
                got = page.evaluate('(id)=>getElectionStatus(allMeasures.find(m=>m.id===id))', row['id'])
                check(got == want, f'{tag} {row["id"]}: status {got!r}, expected {want!r}')
                card = page.evaluate('(id)=>createCard(allMeasures.find(m=>m.id===id))', row['id'])
                check(label in card and 'Upcoming' not in card or want == 'upcoming',
                      f'{tag} {row["id"]}: card badge lacks {label!r}')
                item = page.evaluate('(id)=>createListItem(allMeasures.find(m=>m.id===id))', row['id'])
                check(label in item, f'{tag} {row["id"]}: list row lacks {label!r}')
                page.evaluate('(id)=>viewMeasure(allMeasures.find(m=>m.id===id))', row['id'])
                badges = page.locator('#modalBadges').text_content()  # CSS uppercases it
                check((label if want != 'upcoming' else 'Upcoming election') in badges,
                      f'{tag} {row["id"]}: modal badge {badges!r}')
                links = page.locator('#modalLinks')
                results = links.locator('.official-results-row a')
                shows_link = bool(row.get('official_results')) and want in ('election_day', 'results_pending')
                check(results.count() == (1 if shows_link else 0),
                      f'{tag} {row["id"]}: {results.count()} results links, expected {int(shows_link)}')
                if shows_link:
                    check(results.get_attribute('href') == row['official_results']['url'],
                          f'{tag} {row["id"]}: results link href differs')
                    check(results.get_attribute('rel') == 'noopener noreferrer', f'{tag} {row["id"]}: link rel')
                note = links.locator('.pending-disclaimer').inner_text()
                if want == 'results_pending':
                    check('has not recorded a result' in note and 'not yet been voted' not in note,
                          f'{tag} {row["id"]}: note {note!r}')
                page.evaluate('()=>closeMeasureDetail()')
            # Section notes and the visible page.
            statewide_rows = [m for m in current if m.get('upcoming_scope') == 'statewide']
            linked = lambda m: bool(m.get('official_results')) and expected_status(m, reader_date) in ('election_day', 'results_pending')
            want_statewide_link = any(linked(m) for m in statewide_rows)
            check(page.locator('#statewideSourceNote a.section-results-link').count() == int(want_statewide_link),
                  f'{tag}: statewide section results link count')
            for county in sorted({m['county'] for m in current if m.get('upcoming_scope') == 'local'}):
                page.evaluate('(c)=>selectLocalCounty(c)', county)
                link = page.locator('#localMeasuresScope a.section-results-link')
                county_row = next(m for m in current if m['county'] == county)
                want_link = linked(county_row)
                check(link.count() == int(want_link), f'{tag} {county}: local section results link count')
                if want_link:
                    check(link.get_attribute('href') == county_row['official_results']['url'],
                          f'{tag} {county}: local section link href')
                page.locator('#local-measures').evaluate(
                    '(el)=>window.scrollTo(0,el.getBoundingClientRect().top+scrollY-100)')
                page.screenshot(path=str(out / f'{width}-local-{county.replace(" ", "-")}.png'))
            visible = page.evaluate('()=>document.body.innerText')
            if reader_date is None or all(expected_status(m, reader_date) != 'upcoming' for m in current):
                check('Upcoming' not in visible, f'{tag}: visible page text still says Upcoming')
            overflow = page.evaluate('()=>document.documentElement.scrollWidth - window.innerWidth')
            check(overflow <= 0, f'{tag}: horizontal overflow {overflow}px')
            page.locator('#heroSection').evaluate('(el)=>window.scrollTo(0,el.getBoundingClientRect().top+scrollY-20)')
            page.screenshot(path=str(out / f'{width}-statewide.png'))
            sample = next((m for m in current if m.get('official_results')), current[0])
            page.evaluate('(id)=>viewMeasure(allMeasures.find(m=>m.id===id))', sample['id'])
            page.locator('#modalLinksSection').scroll_into_view_if_needed()
            page.screenshot(path=str(out / f'{width}-modal-{sample["id"]}.png'))
            modal_overflow = page.evaluate(
                "()=>{const el=document.querySelector('#modalLinks'); return el.scrollWidth-el.clientWidth;}")
            check(modal_overflow <= 0, f'{tag}: modal links overflow {modal_overflow}px')
            check(not errors, f'{tag}: page errors {errors}')
            report['widths'][tag] = {'statuses': statuses, 'page_errors': errors}
            page.close()
        browser.close()
    report['failures'] = failures
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k != 'failures'}, indent=2))
    print(f'{len(failures)} failures')
    for failure in failures[:40]:
        print(' -', failure)
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
