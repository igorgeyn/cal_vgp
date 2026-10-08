"""Reader and destination contracts for standalone measure pages."""
import importlib.util
import json
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

spec = importlib.util.spec_from_file_location('measure_pages', Path(__file__).resolve().parents[2] / 'build_measure_pages.py')
pages = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pages)


def measure():
    return {'id': 7, 'year': 2026, 'title': 'District bonds', 'county': 'San Mateo',
            'official_documents': [{'source_url': 'https://example.gov/packet.pdf',
                'sha256': 'a' * 64, 'roles': ['text', 'resolution'],
                'labels': ['Full ballot text', 'Resolution'], 'content_type': 'application/pdf',
                'captured_at': '2026-09-07T17:33:00Z'}]}


def test_composite_packet_is_one_link_with_both_roles_and_capture_date():
    soup = BeautifulSoup(pages.build_page(measure()), 'html.parser')
    links = soup.select('.official-documents a')
    assert len(links) == 1
    assert links[0]['href'] == 'https://example.gov/packet.pdf'
    assert 'Full ballot text · Resolution' in links[0].get_text()
    assert 'Last captured 2026-09-07' in links[0].get_text()
    assert links[0]['target'] == '_blank' and 'noopener' in links[0]['rel']
    assert 'county may update' in soup.select_one('.official-documents').get_text()
    assert soup.select_one('.cta')['href'] == '/#m=7'


@pytest.mark.parametrize('url', ['javascript:alert(1)', '//example.gov/a.pdf', 'https://user:secret@example.gov/a', 'https://example.gov/\na', 'https://example.gov\\evil'])
def test_unsafe_document_urls_fail_before_output(url, tmp_path):
    row = measure()
    row['official_documents'][0]['source_url'] = url
    (tmp_path / 'measures-data.json').write_text(json.dumps([row]))
    with pytest.raises(ValueError, match='Unsafe'):
        pages.build_site_pages(tmp_path)
    assert not (tmp_path / 'measures').exists()


def test_missing_date_is_honest_and_labels_are_escaped():
    row = measure()
    row['official_documents'][0]['captured_at'] = None
    row['official_documents'][0]['labels'] = ['<script>alert(1)</script>']
    soup = BeautifulSoup(pages.build_page(row), 'html.parser')
    assert not soup.find('script')
    assert 'Capture date unavailable' in soup.get_text()


def test_document_review_note_is_visible_and_escaped():
    row = measure()
    row['official_documents'][0]['role_review_note'] = 'County label corrected. <img src=x onerror=alert(1)>'
    soup = BeautifulSoup(pages.build_page(row), 'html.parser')
    assert 'County label corrected.' in soup.select_one('.official-documents').get_text()
    assert not soup.find('img')


def test_no_documents_no_empty_section_and_existing_pages_are_preserved(tmp_path):
    row = measure()
    row['official_documents'] = []
    assert 'id="official-documents-title"' not in pages.build_page(row)
    (tmp_path / 'measures-data.json').write_text(json.dumps([row]))
    pages.build_site_pages(tmp_path)
    output = tmp_path / 'measures/7.html'
    before = output.read_bytes()
    with pytest.raises(FileExistsError):
        pages.build_site_pages(tmp_path)
    assert output.read_bytes() == before


@pytest.mark.parametrize('row_id', ['../escape', True, -1])
def test_invalid_page_identifiers_never_escape_output(tmp_path, row_id):
    row = measure()
    row['id'] = row_id
    (tmp_path / 'measures-data.json').write_text(json.dumps([row]))
    with pytest.raises(ValueError, match='positive integers'):
        pages.build_site_pages(tmp_path)


def test_release_mode_rejects_missing_enrichment_and_corrupt_payloads(tmp_path, monkeypatch):
    from src.website import generator as module
    from src.database.operations import Database
    from src.finance import schema
    db = Database(tmp_path / 'copy.db')
    generator = module.WebsiteGenerator(db, tmp_path / 'index.html', strict=True)
    assert generator.title_generator is None
    monkeypatch.setattr(module, 'BASE_DIR', tmp_path)
    for loader in (generator._load_recommendations, generator._load_insights_data):
        with pytest.raises(FileNotFoundError):
            loader()
    monkeypatch.setattr(schema, 'FINANCE_DB_PATH', tmp_path / 'missing-finance.db')
    with pytest.raises(FileNotFoundError):
        generator._load_finance_data()
    (tmp_path / 'data').mkdir(exist_ok=True)
    (tmp_path / 'data/insights.json').write_text('{broken')
    with pytest.raises(RuntimeError, match='Insights'):
        generator._load_insights_data()
    db.close()
