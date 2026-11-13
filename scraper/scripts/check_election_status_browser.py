"""Check election status and official-results links on every surface, in a browser.

    python scraper/scripts/check_election_status_browser.py --site-dir SITE --output-dir OUT
        [--clock 2026-11-07T12:00:00-08:00] [--expect-count 63]
        [--transition-to 2026-11-04T00:01:00-08:00]

Serves SITE from a fake host (no network) with the browser clock fixed (to
--clock, or to the real time now) and checks, at 1440, 390 and 320px, every
current-cycle measure: rendered statewide card badges, card and list-row
markup, the modal badge, results link and note, and both section notes.
Current rows are selected by ``upcoming_scope``, not by the field under test,
so a row that lost ``election_status`` fails instead of dropping out.
Rows that depend on the date (not withdrawn, no outcome, no stored votes) must
carry a calendar status; the expected status is the forward-only rule: the
later of the build's status and the reader's clock. Rows with a recorded
outcome or stored votes (review R7) must carry no calendar status or results
link, and must read Passed, Failed or Result unknown on every surface.

With --transition-to, a further same-page check loads at --clock, opens a
modal, advances the clock to the given time and requires the rendered cards
and the open modal to show the new status (review finding R1).
Writes report.json and screenshots to OUT; exits non-zero on any failure.
"""
import argparse
import json
import mimetypes
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.website.election_status import (  # noqa: E402
    DATE_DRIVEN_STATUSES, STATUS_LABELS, date_status, election_status, has_recorded_votes,
    parse_election_date, pacific_date,
)

HOST = 'status.test'
LINKED = ('election_day', 'results_pending')
# Exact badge text for current rows whose status does not depend on the date.
RESOLVED_CARD_BADGES = {'passed': '✓ Passed', 'failed': '✗ Failed', 'unknown': '• Result unknown'}
RESOLVED_LIST_BADGES = {'passed': '✓', 'failed': '✗', 'unknown': '?'}
CALENDAR_LABELS = ('Upcoming', 'Election day', 'Results pending', 'Pending')


def depends_on_date(row):
    """True when the row's status must come from the calendar (review R7).

    Decided from withdrawal, outcome and stored-vote evidence, never from the
    ``election_status`` field under test: not withdrawn, no recorded outcome
    and no stored vote figure.
    """
    return (row.get('ballot_status') != 'withdrawn' and row.get('passed') not in (0, 1)
            and not has_recorded_votes(row))


def classify_current(current, reader_date):
    """Split current rows into calendar rows and resolved rows, with data failures.

    Calendar rows must carry a calendar status: a missing one is a failure, not
    a reason to drop the row. Resolved rows (outcome or stored votes) must
    carry neither a calendar status nor a results link, as attachment leaves
    them; their expected display is passed, failed or unknown.
    """
    failures, calendar, resolved = [], [], []
    for row in current:
        if depends_on_date(row):
            if row.get('election_status') in DATE_DRIVEN_STATUSES:
                calendar.append(row)
            else:
                failures.append(f'{row["id"]}: current row has no calendar status ({row.get("election_status")!r})')
            continue
        want = election_status(row, reader_date)
        resolved.append((row, want))
        if row.get('election_status') is not None:
            failures.append(f'{row["id"]}: {want} row carries calendar status {row["election_status"]!r}')
        if row.get('official_results'):
            failures.append(f'{row["id"]}: {want} row carries a results link')
    return calendar, resolved, failures


def badge_text(markup):
    match = re.search(r'class="badge badge-[a-z]+">([^<]*)<', markup or '')
    return match.group(1) if match else None


def expected_status(row, reader_date):
    built = row['election_status']
    by_clock = date_status(parse_election_date(row['election_date']), reader_date)
    order = list(DATE_DRIVEN_STATUSES)
    return by_clock if order.index(by_clock) > order.index(built) else built


def badge_label(status):
    return 'Upcoming election' if status == 'upcoming' else STATUS_LABELS[status]


def open_page(browser, root, width, clock, install=False):
    page = browser.new_page(viewport={'width': width, 'height': 950}, reduced_motion='reduce')
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    if install:
        page.clock.install(time=clock)
    else:
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
    return page, errors


def wait_loaded(page, count):
    page.wait_for_function(
        '(n)=>typeof allMeasures!=="undefined" && allMeasures.length===n && document.getElementById("heroSection").dataset.rendered',
        arg=count)


def rendered_hero_badges(page):
    return dict(page.evaluate(
        "()=>Array.from(document.querySelectorAll('#heroGrid .measure-card')).map(c=>[allMeasures[c.dataset.midx].id, c.querySelector('.badge').textContent])"))


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--site-dir', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--clock', help='Fixed browser time, ISO 8601 with offset (default: now)')
    parser.add_argument('--expect-count', type=int, help='Required number of current-cycle measures')
    parser.add_argument('--transition-to', help='Same-page check: advance the clock to this time')
    args = parser.parse_args()
    root = args.site_dir.resolve()
    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    rows = json.loads((root / 'measures-data.json').read_text(encoding='utf-8'))
    current = [m for m in rows if m.get('upcoming_scope') and m.get('ballot_status') != 'withdrawn']
    clock = datetime.fromisoformat(args.clock) if args.clock else datetime.now(timezone.utc).replace(microsecond=0)
    reader_date = pacific_date(clock)
    failures = []
    report = {'clock': clock.isoformat(), 'reader_date': str(reader_date),
              'current_measures': len(current), 'widths': {}}

    def check(condition, message):
        if not condition:
            failures.append(message)

    if args.expect_count is not None:
        check(len(current) == args.expect_count,
              f'{len(current)} current-cycle measures, expected {args.expect_count}')
    local_counties = sorted({m['county'] for m in current if m['upcoming_scope'] == 'local'})
    current, resolved, data_failures = classify_current(current, reader_date)
    failures.extend(data_failures)
    report['calendar_measures'] = len(current)
    report['resolved_measures'] = {}
    for _, want in resolved:
        report['resolved_measures'][want] = report['resolved_measures'].get(want, 0) + 1

    def linked(m, when):
        return bool(m.get('official_results')) and expected_status(m, when) in LINKED

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        for width in (1440, 390, 320):
            page, errors = open_page(browser, root, width, clock)
            wait_loaded(page, len(rows))
            tag = f'{width}px'
            statuses = {}
            hero = rendered_hero_badges(page)
            for row in current:
                want = expected_status(row, reader_date)
                statuses[want] = statuses.get(want, 0) + 1
                label = STATUS_LABELS[want]
                got = page.evaluate('(id)=>getElectionStatus(allMeasures.find(m=>m.id===id))', row['id'])
                check(got == want, f'{tag} {row["id"]}: status {got!r}, expected {want!r}')
                card = page.evaluate('(id)=>createCard(allMeasures.find(m=>m.id===id))', row['id'])
                check(label in card, f'{tag} {row["id"]}: card markup lacks {label!r}')
                check(want == 'upcoming' or 'Upcoming' not in card, f'{tag} {row["id"]}: card says Upcoming')
                item = page.evaluate('(id)=>createListItem(allMeasures.find(m=>m.id===id))', row['id'])
                check(label in item, f'{tag} {row["id"]}: list row lacks {label!r}')
                if row['upcoming_scope'] == 'statewide':
                    check(label in hero.get(row['id'], ''),
                          f'{tag} {row["id"]}: rendered card badge {hero.get(row["id"])!r}')
                page.evaluate('(id)=>viewMeasure(allMeasures.find(m=>m.id===id))', row['id'])
                badges = page.locator('#modalBadges').text_content()  # CSS uppercases it
                check(badge_label(want) in badges, f'{tag} {row["id"]}: modal badge {badges!r}')
                links = page.locator('#modalLinks')
                results = links.locator('.official-results-row a')
                shows_link = linked(row, reader_date)
                check(results.count() == int(shows_link),
                      f'{tag} {row["id"]}: {results.count()} results links, expected {int(shows_link)}')
                if shows_link and results.count() == 1:
                    check(results.get_attribute('href') == row['official_results']['url'],
                          f'{tag} {row["id"]}: results link href differs')
                    check(results.get_attribute('rel') == 'noopener noreferrer', f'{tag} {row["id"]}: link rel')
                    check('link checked' in links.locator('.official-results-row').inner_text(),
                          f'{tag} {row["id"]}: results link lacks its check date')
                note = links.locator('.pending-disclaimer').inner_text()
                if want == 'results_pending':
                    check('has not recorded a result' in note and 'not yet been voted' not in note,
                          f'{tag} {row["id"]}: note {note!r}')
                page.evaluate('()=>closeMeasureDetail()')
            for row, want in resolved:
                # Outcome or stored votes: Passed, Failed or Result unknown on every
                # surface, with no calendar label, results link or pending note.
                statuses[want] = statuses.get(want, 0) + 1
                got = page.evaluate('(id)=>getElectionStatus(allMeasures.find(m=>m.id===id))', row['id'])
                check(got == want, f'{tag} {row["id"]}: status {got!r}, expected {want!r}')
                card = badge_text(page.evaluate('(id)=>createCard(allMeasures.find(m=>m.id===id))', row['id']))
                check(card == RESOLVED_CARD_BADGES[want], f'{tag} {row["id"]}: card badge {card!r}')
                item = badge_text(page.evaluate('(id)=>createListItem(allMeasures.find(m=>m.id===id))', row['id']))
                check(item == RESOLVED_LIST_BADGES[want], f'{tag} {row["id"]}: list badge {item!r}')
                if row['upcoming_scope'] == 'statewide':
                    check(hero.get(row['id']) == RESOLVED_CARD_BADGES[want],
                          f'{tag} {row["id"]}: rendered card badge {hero.get(row["id"])!r}')
                page.evaluate('(id)=>viewMeasure(allMeasures.find(m=>m.id===id))', row['id'])
                badges = page.locator('#modalBadges').text_content()
                check(RESOLVED_CARD_BADGES[want] in badges and not any(t in badges for t in CALENDAR_LABELS),
                      f'{tag} {row["id"]}: modal badge {badges!r}')
                links = page.locator('#modalLinks')
                check(links.locator('.official-results-row a').count() == 0,
                      f'{tag} {row["id"]}: {want} row shows a results link')
                check(links.locator('.pending-disclaimer').count() == 0,
                      f'{tag} {row["id"]}: {want} row shows a pending note')
                page.evaluate('()=>closeMeasureDetail()')
            statewide_rows = [m for m in current if m['upcoming_scope'] == 'statewide']
            want_statewide = any(linked(m, reader_date) for m in statewide_rows)
            check(page.locator('#statewideSourceNote a.section-results-link').count() == int(want_statewide),
                  f'{tag}: statewide section results link count')
            for county in local_counties:
                page.evaluate('(c)=>selectLocalCounty(c)', county)
                link = page.locator('#localMeasuresScope a.section-results-link')
                county_row = next((m for m in current if m['county'] == county and linked(m, reader_date)), None)
                want_link = county_row is not None
                check(link.count() == int(want_link), f'{tag} {county}: local section results link count')
                if want_link and link.count() == 1:
                    check(link.get_attribute('href') == county_row['official_results']['url'],
                          f'{tag} {county}: local section link href')
                page.locator('#local-measures').evaluate(
                    '(el)=>window.scrollTo(0,el.getBoundingClientRect().top+scrollY-100)')
                page.screenshot(path=str(out / f'{width}-local-{county.replace(" ", "-")}.png'))
            visible = page.evaluate('()=>document.body.innerText').casefold()
            if all(expected_status(m, reader_date) != 'upcoming' for m in current):
                check('upcoming' not in visible, f'{tag}: visible page text still says Upcoming')
            overflow = page.evaluate('()=>document.documentElement.scrollWidth - window.innerWidth')
            check(overflow <= 0, f'{tag}: horizontal overflow {overflow}px')
            page.locator('#heroSection').evaluate('(el)=>window.scrollTo(0,el.getBoundingClientRect().top+scrollY-20)')
            page.screenshot(path=str(out / f'{width}-statewide.png'))
            sample = next((m for m in current if linked(m, reader_date)), current[0] if current else None)
            if sample is not None:
                page.evaluate('(id)=>viewMeasure(allMeasures.find(m=>m.id===id))', sample['id'])
                page.locator('#modalLinksSection').scroll_into_view_if_needed()
                page.screenshot(path=str(out / f'{width}-modal-{sample["id"]}.png'))
                modal_overflow = page.evaluate(
                    "()=>{const el=document.querySelector('#modalLinks'); return el.scrollWidth-el.clientWidth;}")
                check(modal_overflow <= 0, f'{tag}: modal links overflow {modal_overflow}px')
            check(not errors, f'{tag}: page errors {errors}')
            report['widths'][tag] = {'statuses': statuses, 'page_errors': errors}
            page.close()

        if args.transition_to:
            later = datetime.fromisoformat(args.transition_to)
            later_date = pacific_date(later)
            page, errors = open_page(browser, root, 1440, clock, install=True)
            wait_loaded(page, len(rows))
            # Prefer a linked statewide calendar row, then any calendar row. With none
            # left (every current row resolved), the badge checks below still run but
            # there is no date-driven modal to sample.
            statewide = [m for m in current if m['upcoming_scope'] == 'statewide']
            sample = next((m for m in statewide if m.get('official_results')),
                          statewide[0] if statewide else (current[0] if current else None))
            if sample is not None:
                page.evaluate('(id)=>viewMeasure(allMeasures.find(m=>m.id===id))', sample['id'])
            before = rendered_hero_badges(page)
            # Past the new time plus one refresh interval, so the timer fires.
            page.clock.fast_forward(int((later - clock).total_seconds() * 1000) + 61_000)
            after = rendered_hero_badges(page)
            transition = {'from': clock.isoformat(), 'to': later.isoformat(),
                          'sample': sample['id'] if sample is not None else None,
                          'before': {}, 'after': {}}
            for row in current:
                if row['upcoming_scope'] != 'statewide':
                    continue
                want_before = STATUS_LABELS[expected_status(row, reader_date)]
                want_after = STATUS_LABELS[expected_status(row, later_date)]
                transition['before'][want_before] = transition['before'].get(want_before, 0) + 1
                transition['after'][want_after] = transition['after'].get(want_after, 0) + 1
                check(want_before in before.get(row['id'], ''), f'transition {row["id"]}: before {before.get(row["id"])!r}')
                check(want_after in after.get(row['id'], ''), f'transition {row["id"]}: after {after.get(row["id"])!r}')
            for row, want in resolved:
                if row['upcoming_scope'] == 'statewide':
                    check(after.get(row['id']) == RESOLVED_CARD_BADGES[want],
                          f'transition {row["id"]}: {want} row after {after.get(row["id"])!r}')
            if sample is not None:
                check(page.locator('#measureDetailModal').is_visible(), 'transition: modal closed by the refresh')
                want_modal = badge_label(expected_status(sample, later_date))
                badges = page.locator('#modalBadges').text_content()
                check(want_modal in badges, f'transition: open modal badge {badges!r}, expected {want_modal!r}')
                results = page.locator('#modalLinks .official-results-row a').count()
                check(results == int(linked(sample, later_date)),
                      f'transition: open modal has {results} results links')
                note = page.locator('#modalLinks .pending-disclaimer').inner_text()
                if expected_status(sample, later_date) == 'results_pending':
                    check('has not recorded a result' in note, f'transition: open modal note {note!r}')
            check(not errors, f'transition: page errors {errors}')
            page.screenshot(path=str(out / 'transition-after.png'))
            report['transition'] = transition
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
