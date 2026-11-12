"""Insights is hidden while it is renovated; one flag brings it back."""
import pytest

import src.website.generator as generator_module
from src.database.operations import Database
from src.scrapers.registrar.loader import load_jsonl
from src.website.generator import WebsiteGenerator
from tests.test_registrar_loader import _record, _write, _database

ENTRY_POINTS = ('id="insightsView"', 'id="insightsViewCard"', 'class="local-rules-link"',
                '&mdash; trends and analysis from the data')


def _html(tmp_path, monkeypatch):
    db_path = _database(tmp_path / "measures.db")
    load_jsonl(_write(tmp_path / "records.jsonl", [_record()]), db_path=db_path, commit=True)
    database = Database(db_path)
    generator = WebsiteGenerator(database, tmp_path / "site" / "index.html")
    monkeypatch.setattr(generator, "_load_finance_data", lambda: {})
    monkeypatch.setattr(generator, "_load_insights_data", lambda: {})
    monkeypatch.setattr(generator, "_load_recommendations", lambda: {})
    generator.generate()
    database.close()
    return (tmp_path / "site" / "index.html").read_text(encoding="utf-8")


def test_insights_has_no_entry_point_while_hidden(tmp_path, monkeypatch):
    assert generator_module.SHOW_INSIGHTS is False
    html = _html(tmp_path, monkeypatch)
    for marker in ENTRY_POINTS:
        assert marker not in html, marker
    assert "if (view === 'insights' && !false) view = 'grid';" in html
    assert 'id="insightsSection" style="display: none;"' in html


@pytest.mark.parametrize("flag", [True])
def test_flag_restores_every_entry_point(tmp_path, monkeypatch, flag):
    monkeypatch.setattr(generator_module, "SHOW_INSIGHTS", flag)
    monkeypatch.setattr(generator_module, "INSIGHTS_ENABLED_JS", "true")
    html = _html(tmp_path, monkeypatch)
    for marker in ENTRY_POINTS:
        assert marker in html, marker
    assert "!true) view = 'grid';" in html
