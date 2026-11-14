"""Explore E1 is enabled; its release flag still gates every entry point."""
import src.website.generator as generator_module
from tests.test_insights_hidden import _html

ENTRY_POINTS = ('id="exploreView"', 'id="exploreViewCard"', '&mdash; recorded outcomes by type and period')


def test_explore_has_no_entry_point_while_hidden(tmp_path, monkeypatch):
    monkeypatch.setattr(generator_module, "SHOW_EXPLORE", False)
    monkeypatch.setattr(generator_module, "EXPLORE_ENABLED_JS", "false")
    html = _html(tmp_path, monkeypatch)
    for marker in ENTRY_POINTS:
        assert marker not in html, marker
    assert "if (view === 'explore' && !false) view = 'grid';" in html
    # Grid and List stay reachable.
    assert 'id="gridView"' in html and 'id="listView"' in html


def test_flag_restores_every_explore_entry_point(tmp_path, monkeypatch):
    assert generator_module.SHOW_EXPLORE is True
    monkeypatch.setattr(generator_module, "SHOW_EXPLORE", True)
    monkeypatch.setattr(generator_module, "EXPLORE_ENABLED_JS", "true")
    html = _html(tmp_path, monkeypatch)
    for marker in ENTRY_POINTS:
        assert marker in html, marker
    assert "if (view === 'explore' && !true) view = 'grid';" in html
