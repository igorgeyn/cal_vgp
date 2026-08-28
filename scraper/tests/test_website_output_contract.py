"""Static-site HTML and data assets are published as one consistent bundle."""
from __future__ import annotations

import json
from pathlib import Path

from src.database.operations import Database
from src.website.generator import WebsiteGenerator


def test_prepared_generation_writes_matching_html_and_json_pairs(tmp_path: Path, monkeypatch):
    database = Database(tmp_path / "measures.db")
    generator = WebsiteGenerator(database=database, output_path=tmp_path / "unused.html")

    def render(measures, stats, topics, recommendations):
        generator._measures_json = json.dumps(measures, sort_keys=True)
        return "<html><script>fetch('measures-data.json')</script></html>"

    monkeypatch.setattr(generator, "_generate_html", render)
    root_output = tmp_path / "root" / "index.html"
    local_output = tmp_path / "scraper" / "index.html"
    measures = [{"measure_id": "one"}, {"measure_id": "two"}]

    generator.generate_prepared(
        measures,
        {"total_measures": 2},
        [],
        {},
        output_paths=[root_output, local_output],
    )

    assert root_output.read_bytes() == local_output.read_bytes()
    root_json = root_output.parent / "measures-data.json"
    local_json = local_output.parent / "measures-data.json"
    assert root_json.read_bytes() == local_json.read_bytes()
    assert json.loads(root_json.read_text(encoding="utf-8")) == measures
    root_use_page = root_output.parent / "use-calballot" / "index.html"
    local_use_page = local_output.parent / "use-calballot" / "index.html"
    assert root_use_page.read_bytes() == local_use_page.read_bytes()
    assert "Use CalBallot" in root_use_page.read_text(encoding="utf-8")
    database.close()


def test_explicit_output_keeps_auxiliary_page_inside_scratch_root(tmp_path: Path, monkeypatch):
    database = Database(tmp_path / "measures.db")
    default_output = tmp_path / "must-not-be-written" / "index.html"
    generator = WebsiteGenerator(database=database, output_path=default_output)

    def render(measures, stats, topics, recommendations):
        generator._measures_json = json.dumps(measures)
        return "<html><script>fetch('measures-data.json')</script></html>"

    monkeypatch.setattr(generator, "_generate_html", render)
    explicit_output = tmp_path / "scratch" / "index.html"

    generator.generate_prepared(
        [{"measure_id": "one"}],
        {"total_measures": 1},
        [],
        {},
        output_paths=[explicit_output],
    )

    assert explicit_output.exists()
    assert (explicit_output.parent / "measures-data.json").exists()
    assert (explicit_output.parent / "use-calballot" / "index.html").exists()
    assert not default_output.exists()
    assert not (default_output.parent / "use-calballot" / "index.html").exists()
    database.close()
