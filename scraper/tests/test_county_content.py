"""Failure cases for reviewed county content and faithful public presentation."""
from copy import deepcopy
import importlib.util
from pathlib import Path

from bs4 import BeautifulSoup
import pytest

from src.website.county_content import attach_county_content, load_package, render_sections


def sample():
    e = deepcopy(load_package()['entries'][0])
    m = {k: e.get(k) for k in ('id', 'measure_id', 'county', 'jurisdiction', 'election_date', 'measure_letter', 'vote_threshold')}
    m.update(summary_text='Retained editorial text', ballot_question='Retained database question',
             official_documents=[dict(source_url=s['url'], sha256=s['sha256'], roles=[s['role']], captured_at='2026-09-28') for s in e['sources']])
    return m, dict(schema_version=1, election_date='2026-11-03', entries=[e])


def test_identical_bytes_in_a_new_snapshot_preserve_review_and_raw_fields():
    m, package = sample()
    before = deepcopy(m)
    first = attach_county_content([m], package)[0]
    m['official_documents'][0]['captured_at'] = '2026-10-08'
    second = attach_county_content([m], package)[0]
    assert first['county_guide'] == second['county_guide']
    assert first['summary_text'] == before['summary_text']
    assert first['ballot_question'] == before['ballot_question']
    assert 'county_guide' not in m


@pytest.mark.parametrize('mutation', ['changed_bytes', 'missing_file', 'changed_url', 'advocacy_role'])
def test_changed_or_missing_source_stops_publication(mutation):
    m, package = sample()
    if mutation == 'changed_bytes':
        m['official_documents'][0]['sha256'] = 'f' * 64
    elif mutation == 'missing_file':
        m['official_documents'] = []
    elif mutation == 'changed_url':
        m['official_documents'][0]['source_url'] += '?replacement=1'
    else:
        m['official_documents'][0]['roles'] = ['argument_for']
    with pytest.raises(ValueError, match='source re-review'):
        attach_county_content([m], package)


@pytest.mark.parametrize('field,value', [('id', 88), ('measure_id', 'REG_SB_20261103_WRONG'),
                                       ('county', 'San Mateo'), ('jurisdiction', 'Another district'),
                                       ('election_date', '2028-11-07'), ('measure_letter', 'Z'), ('vote_threshold', '50%')])
def test_wrong_measure_cannot_receive_reviewed_content(field, value):
    m, package = sample()
    m[field] = value
    with pytest.raises(ValueError, match='identity mismatch'):
        attach_county_content([m], package)


def test_all_reviewed_questions_render_in_full_with_page_specific_sources():
    for e in load_package()['entries']:
        soup = BeautifulSoup(render_sections(e), 'html.parser')
        assert soup.blockquote.get_text() == e['question']
        source = e['sources'][e['question_source']]
        assert source['url'] + '#page=' + str(source['pages'][0]) in [a['href'] for a in soup.select('a')]
        assert 'campaign arguments' in soup.get_text()


def test_source_markup_is_escaped_and_nonofficial_urls_are_rejected():
    m, p = sample()
    p['entries'][0]['question'] = '<script>bad()</script>'
    assert '<script>' not in attach_county_content([m], p)[0]['county_sections']
    p['entries'][0]['sources'][0]['url'] = 'javascript:alert(1)'
    with pytest.raises(ValueError, match='source URL'):
        attach_county_content([m], p)


def test_county_standalone_page_has_full_explanation_and_question():
    spec = importlib.util.spec_from_file_location('county_page_builder', Path(__file__).resolve().parents[2] / 'build_measure_pages.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    m, p = sample()
    m.update(title='College facilities', year=2026)
    rendered = BeautifulSoup(module.build_page(attach_county_content([m], p)[0]), 'html.parser')
    assert p['entries'][0]['explanation'] in rendered.get_text()
    assert p['entries'][0]['question'] in rendered.get_text()
    assert 'Retained editorial text' not in rendered.get_text()


def test_unreviewed_county_and_historical_records_remain_unchanged():
    m, p = sample()
    other = dict(id=12466, measure_id='REG_SMC_20261103_UNREVIEWED', summary_text=None)
    old = dict(id=99, year=2024, summary_text='Historical content')
    assert attach_county_content([m, other, old], p)[1:] == [other, old]
