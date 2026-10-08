"""Acceptance checks for evidence, identity, finance semantics and safe rendering."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path

from bs4 import BeautifulSoup
import pytest

from src.website.statewide_content import (
    DATA, NUMBERS, attach_statewide_content, load_package, money_cents,
    parse_finance, parse_guide, parse_top_contributors, render_sections,
)

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = Path(__file__).parent / 'fixtures/statewide/20261008_content'
SOURCES = EVIDENCE / 'sources'


def load_script(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def row(entry):
    return dict(id=entry['id'], measure_id=entry['canonical_id'],
                proposition_number=entry['proposition_number'], election_date='2026-11-03',
                ballot_status='qualified', source_url=entry['source_url'],
                summary_text='Unreviewed legacy editorial text', external_links=[])


def test_published_package_reproduces_from_all_pinned_sources():
    builder = load_script('build_statewide_content', ROOT / 'scraper/scripts/build_statewide_content.py')
    assert builder.build_package(EVIDENCE) == load_package()


@pytest.mark.parametrize('number', NUMBERS)
def test_every_proposition_has_usable_source_bound_components(number):
    entry = next(e for e in load_package()['entries'] if e['proposition_number'] == number)
    rendered = render_sections(entry)
    assert all(rendered.values())
    main = BeautifulSoup(rendered['main'], 'html.parser')
    assert entry['yes_meaning'] in main.get_text()
    assert entry['no_meaning'] in main.get_text()
    assert all(f'/propositions/{number}/' in doc['url'] or 'vig.cdn.sos.ca.gov' in doc['url']
               for doc in entry['documents'])
    research = BeautifulSoup(rendered['research'], 'html.parser')
    assert 'Fiscal impact' in research.get_text()
    assert entry['argument_for'] in research.get_text()
    assert entry['argument_against'] in research.get_text()
    assert 'not impartial analysis' in research.get_text()
    assert 'not exhaustive lists' in research.get_text()
    finance = BeautifulSoup(rendered['finance'], 'html.parser')
    assert 'contributions, not spending' in finance.get_text()
    assert 'timeline' in finance.get_text()
    assert entry['sources']['finance']['final_url'] in [a['href'] for a in finance.select('a')]


def test_current_identity_is_exact_and_raw_editorial_fields_survive():
    entry = load_package()['entries'][0]
    measure = row(entry)
    projected = attach_statewide_content([measure])[0]
    assert projected['summary_text'] == measure['summary_text']
    assert 'statewide_guide' not in measure
    assert projected['id'] == measure['id']
    assert projected['official_description'] == entry['summary']
    for field, wrong in [('id', 1), ('proposition_number', 3), ('measure_id', 'PROP_1'),
                         ('source_url', 'https://example.org')]:
        with pytest.raises(ValueError, match='identity mismatch'):
            attach_statewide_content([{**measure, field: wrong}])


def test_other_year_county_and_withdrawal_are_untouched():
    entry = load_package()['entries'][0]
    others = [dict(id=12418, county='San Bernardino'),
              dict(id=1, ballot_status='withdrawn', election_date='2026-11-03'),
              dict(id=99, ballot_status='qualified', election_date='2028-11-07')]
    before = deepcopy(others)
    assert attach_statewide_content([row(entry), *others])[1:] == before
    assert others == before


def test_wrong_proposition_or_election_is_rejected():
    raw = [(SOURCES / f'prop-3-{p}.html').read_bytes() for p in ['index', 'title-summary', 'analysis']]
    with pytest.raises(ValueError, match='identity'):
        parse_guide(*raw, 4)
    with pytest.raises(ValueError, match='election'):
        parse_guide(raw[0].replace(b'November 3, 2026', b'November 5, 2024'), *raw[1:], 3)


def test_unknown_overview_label_stops_instead_of_relabelling():
    raw = [(SOURCES / f'prop-3-{p}.html').read_bytes() for p in ['index', 'title-summary', 'analysis']]
    with pytest.raises(ValueError, match='fields'):
        parse_guide(raw[0].replace(b'>Opponents<', b'>Other<'), *raw[1:], 3)


def test_finance_absence_is_not_zero_and_source_discrepancy_is_visible():
    p2 = parse_finance((SOURCES / 'prop-2-finance.html').read_bytes(), 2)
    assert p2['support']['total'] is None and p2['oppose']['total'] is None
    p3 = parse_finance((SOURCES / 'prop-3-finance.html').read_bytes(), 3)
    assert p3['support']['total'] == '$46,260,006'
    assert p3['oppose']['total'] == '$5,500'
    assert len(p3['support']['committees']) == 4
    p39 = next(e for e in load_package()['entries'] if e['proposition_number'] == 39)
    assert p39['finance']['oppose']['source_row_difference_cents'] == 100
    assert '$1.00' in render_sections(p39)['finance']
    with pytest.raises(ValueError, match='proposition'):
        parse_finance((SOURCES / 'prop-3-finance.html').read_bytes(), 4)


def test_fppc_table_ownership_and_raw_ambiguity_are_preserved():
    entries = parse_top_contributors((SOURCES / 'fppc.html').read_bytes())
    assert [c['side'] for c in entries[45]['committees']] == ['support'] * 3 + ['oppose'] * 3
    # The source spells the heading "Propostion 3"; still the correct panel.
    assert len(entries[3]['committees']) == 2
    assert entries[3]['committees'][1]['donors'][0]['shared_campaign'] is True
    issues = [d for c in entries[39]['committees'] for d in c['donors'] if d['source_issue']]
    assert any(d['amount'] == '$2,000,0000' for d in issues)
    assert 2 not in entries and 5 not in entries
    assert money_cents('$ 3,204,703.12') == 320470312
    assert money_cents('$1,234*') == 123400
    assert all(d['amount'] != '$ 3,204,703.12' or d['source_issue'] is None
               for e in entries.values() for c in e['committees'] for d in c['donors'])
    with pytest.raises(ValueError, match='Malformed'):
        money_cents('$2,000,0000')


def test_unknown_fppc_side_cannot_inherit_previous_table_ownership():
    raw = (SOURCES / 'fppc.html').read_bytes()
    with pytest.raises(ValueError, match='side heading'):
        parse_top_contributors(raw.replace(b'>Opposing</h5>', b'>Other</h5>'))


def test_future_assignments_are_separate_from_current_slate():
    from src.website.statewide_content import render_future_ballots
    package = load_package()
    assert [e['proposition_number'] for e in package['entries']] == list(NUMBERS)
    assert {e['election_date'] for e in package['future_ballots']} == {'2028-03-07', '2028-11-07'}
    html = render_future_ballots(package)
    assert '2028' in html and 'SB 895' in html and 'ACA 7' in html


def test_shared_renderer_escapes_content_and_rejects_unsafe_links():
    e = deepcopy(load_package()['entries'][0])
    e['yes_meaning'] = '<img src=x onerror=alert(1)>'
    out = render_sections(e)
    assert '<img src=x' not in out['main']
    assert '&lt;img' in out['main']
    e['documents'][0]['url'] = 'javascript:alert(1)'
    with pytest.raises(ValueError, match='Unsafe'):
        render_sections(e)


def test_standalone_page_has_same_substantive_components():
    pages = load_script('content_test_pages', ROOT / 'build_measure_pages.py')
    entry = load_package()['entries'][2]
    measure = attach_statewide_content([row(entry)])[0]
    measure.update(year=2026, county='Statewide', official_title=entry['official_title'])
    out = pages.build_page(measure)
    for section in render_sections(entry).values():
        assert section in out
    assert 'What your vote means' in out and 'Top contributors by committee' in out


def test_contributor_names_notes_and_grouped_entities_keep_their_own_links():
    entries = parse_top_contributors((SOURCES / 'fppc.html').read_bytes())
    donors = [d for e in entries.values() for c in e['committees'] for d in c['donors']]
    nea = next(d for d in donors if d['name'] == 'National Education Association (MPO)')
    assert nea['contributor_blocks'][1]['attribution'] is True
    assert 'Top Donor' not in nea['name']
    aclu = next(d for d in donors if 'Nothern California Issues Committee' in d['name'])
    assert aclu['grouped_names'] is True
    assert [b['attribution'] for b in aclu['contributor_blocks']] == [False, True, False, True]
    links = [p for b in aclu['contributor_blocks'] for p in b['parts'] if p.get('url')]
    assert len(links) == 2
    assert links[0]['url'].endswith('id=1423278') and links[1]['url'].endswith('id=1440576')
    entry = deepcopy(load_package()['entries'][0])
    entry['top_contributors']['committees'][0]['donors'] = [aclu, nea]
    soup = BeautifulSoup(render_sections(entry)['finance'], 'html.parser')
    for part in links:
        assert soup.find('a', href=part['url']).get_text() == part['text']
    assert not any('Top Donor' in a.get_text() for a in soup.find_all('a'))
    assert 'amount is not split between them' in soup.get_text()


def test_unsafe_statewide_link_fails_before_any_standalone_page_is_written(tmp_path):
    pages = load_script('invalid_statewide_pages', ROOT / 'build_measure_pages.py')
    entry = deepcopy(load_package()['entries'][0])
    entry['documents'][0]['url'] = 'javascript:alert(1)'
    measures = [dict(id=99, year=2024), {**row(entry), 'statewide_guide': entry}]
    (tmp_path / 'measures-data.json').write_text(json.dumps(measures), encoding='utf-8')
    with pytest.raises(ValueError, match='Unsafe'):
        pages.build_site_pages(tmp_path)
    assert not (tmp_path / 'measures').exists()
