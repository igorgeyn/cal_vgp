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
    database.close()
