"""Official documents survive both site entry points and modal rendering."""
import json
import re
import socket
from pathlib import Path

import pytest

from src.database.operations import Database
from src.scrapers.registrar.loader import load_jsonl
from src.website.generator import WebsiteGenerator
from tests.test_registrar_loader import _record, _write, _database


@pytest.mark.parametrize("prepared", [False, True])
def test_documents_reach_export_through_both_generator_entry_points(tmp_path, monkeypatch, prepared):
    db_path = _database(tmp_path / "measures.db")
    record = _record()
    record["documents"].append(dict(record["documents"][0], role="resolution"))
    jsonl = _write(tmp_path / "records.jsonl", [record])
    load_jsonl(jsonl, db_path=db_path, commit=True)
    database = Database(db_path)
    generator = WebsiteGenerator(database, tmp_path / "site" / "index.html")
    monkeypatch.setattr(generator, "_load_finance_data", lambda: {})
    monkeypatch.setattr(generator, "_load_insights_data", lambda: {})
    monkeypatch.setattr(generator, "_load_recommendations", lambda: {})
    if prepared:
        data = database.get_all_active_measures()[0].to_dict()
        # A stale prepared payload must never override database associations.
        data["official_documents"] = [{"source_url": "https://stale.example/a.pdf"}]
        generator.generate_prepared([data], {}, [], {})
    else:
        generator.generate()
    exported = json.loads((tmp_path / "site" / "measures-data.json").read_text(encoding="utf-8"))
    assert exported[0]["id"] == 1
    documents = exported[0]["official_documents"]
    assert len(documents) == 1
    assert documents[0]["roles"] == ["text", "resolution"]
    assert documents[0]["captured_at"] == record["scraped_at"]
    assert documents[0]["sha256"] == record["documents"][0]["sha256"]
    assert "snapshot_id" not in documents[0] and "snapshot_filename" not in documents[0]
    assert exported[0]["pdf_url"] == record["measure"]["pdf_url"]
    assert exported[0]["ballot_question"] is None
    database.close()


def test_official_document_browser_rendering(tmp_path, monkeypatch):
    """Exercise actual generated JS without loading external scripts or URLs."""
    from playwright.sync_api import sync_playwright
    database = Database(tmp_path / "measures.db")
    generator = WebsiteGenerator(database)
    monkeypatch.setattr(generator, "_load_finance_data", lambda: {})
    monkeypatch.setattr(generator, "_load_insights_data", lambda: {})
    html = generator._generate_html([], {}, [], {})
    render = re.search(r"        function renderOfficialDocuments\(measure\).*?(?=        // Check if measure is pending)", html, re.S).group()
    sanitize = re.search(r"        function sanitizeUrl\(url\).*?\n        }", html, re.S).group()
    with sync_playwright() as playwright:
        if not Path(playwright.chromium.executable_path).exists():
            pytest.skip("Chromium is not installed; run playwright install chromium")
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 390, "height": 844})
        page.route("**/*", lambda route: route.abort())
        page.set_content('<section id="modalOfficialDocuments"><ul id="modalOfficialDocumentList"></ul></section>')
        page.add_script_tag(content=sanitize + "\n" + render)
        document = {
            "source_url": "https://example.gov/packet.pdf",
            "labels": ["Full ballot text", "Resolution", "<img src=x onerror=alert(1)>"],
            "content_type": "application/pdf",
            "captured_at": "2026-09-01T02:41:42+00:00",
        }
        page.evaluate("data => renderOfficialDocuments(data)", {"official_documents": [document]})
        link = page.locator("#modalOfficialDocuments a")
        assert link.count() == 1
        assert "Last captured 2026-09-01" in link.inner_text()
        assert "Full ballot text · Resolution" in link.inner_text()
        assert page.locator("img").count() == 0
        link.focus()
        assert link.evaluate("element => element === document.activeElement")
        assert link.get_attribute("rel") == "noopener noreferrer"
        page.evaluate("renderOfficialDocuments({official_documents: [{source_url: 'javascript:alert(1)'}]})")
        assert page.locator("#modalOfficialDocuments").is_hidden()
        assert page.locator("#modalOfficialDocuments a").count() == 0
        page.evaluate("renderOfficialDocuments({})")
        assert page.locator("#modalOfficialDocuments").is_hidden()
        browser.close()
    database.close()


@pytest.mark.parametrize("bad_id", [None, "1", 999])
def test_missing_or_wrong_database_id_fails_before_output(tmp_path, bad_id):
    db_path = _database(tmp_path / "measures.db")
    jsonl = _write(tmp_path / "records.jsonl", [_record()])
    load_jsonl(jsonl, db_path=db_path, commit=True)
    database = Database(db_path)
    data = database.get_all_active_measures()[0].to_dict()
    data["id"] = bad_id
    output = tmp_path / "index.html"
    output.write_text("existing accepted site", encoding="utf-8")
    generator = WebsiteGenerator(database, output)
    with pytest.raises(ValueError, match="matching database id"):
        generator.generate_prepared([data], {}, [], {})
    assert output.read_text(encoding="utf-8") == "existing accepted site"
    assert not output.with_name("measures-data.json").exists()
    database.close()


def test_one_missing_id_fails_even_when_other_documents_attach(tmp_path):
    db_path = _database(tmp_path / "measures.db")
    records = [_record(count=2), _record(count=2, row=2, letter="B", digest_char="B")]
    load_jsonl(_write(tmp_path / "records.jsonl", records), db_path=db_path, commit=True)
    database = Database(db_path)
    data = [measure.to_dict() for measure in database.get_all_active_measures()]
    data[1].pop("id")
    generator = WebsiteGenerator(database, tmp_path / "index.html")
    with pytest.raises(ValueError, match="matching database id"):
        generator.generate_prepared(data, {}, [], {})
    database.close()


def test_legitimate_subset_without_documents_is_allowed(tmp_path, monkeypatch):
    db_path = _database(tmp_path / "measures.db")
    load_jsonl(_write(tmp_path / "records.jsonl", [_record()]), db_path=db_path, commit=True)
    database = Database(db_path)
    generator = WebsiteGenerator(database, tmp_path / "index.html")
    monkeypatch.setattr(generator, "_load_finance_data", lambda: {})
    monkeypatch.setattr(generator, "_load_insights_data", lambda: {})
    generator.generate_prepared([{"measure_id": "HISTORICAL", "year": 2024}], {}, [], {})
    assert (tmp_path / "index.html").exists()
    database.close()


def test_actual_cli_field_filter_preserves_ids_and_documents(tmp_path, monkeypatch, caplog):
    from scripts import generate_site
    db_path = _database(tmp_path / "measures.db")
    record = _record()
    load_jsonl(_write(tmp_path / "records.jsonl", [record]), db_path=db_path, commit=True)
    # Exercise main(), including its real valid_fields filter. Unrelated
    # enrichment providers use fixed inputs; the embedding step has no fixtures.
    monkeypatch.setattr(generate_site, "EMBEDDING_DATA_DIR", tmp_path / "without-embedding-inputs")
    monkeypatch.setattr(WebsiteGenerator, "_load_finance_data", lambda self: {})
    monkeypatch.setattr(WebsiteGenerator, "_load_insights_data", lambda self: {})
    monkeypatch.setattr(WebsiteGenerator, "_load_recommendations", lambda self: {})

    def no_network(*args, **kwargs):
        raise AssertionError("CLI contract test attempted network access")

    monkeypatch.setattr(socket.socket, "connect", no_network)
    output = tmp_path / "cli" / "index.html"
    assert generate_site.main(["--db", str(db_path), "--output", str(output), "--force"]) == 0
    exported = json.loads(output.with_name("measures-data.json").read_text(encoding="utf-8"))
    assert len(exported) == 1 and exported[0]["id"] == 1
    assert exported[0]["measure_id"] == record["measure"]["measure_id"]
    assert exported[0]["official_documents"][0]["source_url"] == record["documents"][0]["source_url"]
    assert not any("historical context" in record.message and record.levelno >= 30 for record in caplog.records)
