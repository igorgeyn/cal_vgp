#!/usr/bin/env python3
"""Verify F1 on a new database copy and build an offline review bundle.

The source database and published assets are read only. Existing finance,
insights, recommendations and prepared measure fields are reused, so this
bounded preview does not regenerate unrelated enrichments or use the network.
The output directory must not exist. This is not a publication command.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import socket
import sqlite3
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.database.operations import Database
from src.scrapers.registrar.loader import load_jsonl
from src.website.generator import WebsiteGenerator
from scripts import generate_site


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--site", required=True, type=Path, help="existing index.html")
    parser.add_argument("--jsonl", required=True, action="append", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path, help="new isolated directory")
    args = parser.parse_args()
    source_db = args.db.resolve()
    site = args.site.resolve()
    data = site.with_name("measures-data.json")
    sources = [source_db, site, data, *(path.resolve() for path in args.jsonl)]
    before_hashes = {str(path): digest(path) for path in sources}
    original_measures = json.loads(data.read_text(encoding="utf-8"))
    existing_html = site.read_text(encoding="utf-8")

    def existing_payload(name):
        match = re.search(r"\bconst " + re.escape(name) + r" = (.*?);\s*\n", existing_html)
        if match is None:
            raise ValueError(f"existing site lacks {name}; cannot preserve that payload")
        return json.loads(match.group(1))

    cached = {name: existing_payload(name) for name in ("topics", "recommendations", "financeData", "insightsData")}
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=False)
    copy_db = output / "measures.db"
    source = sqlite3.connect(source_db.as_uri() + "?mode=ro", uri=True)
    target = sqlite3.connect(copy_db)
    try:
        source.backup(target)
        before_rows = source.execute("SELECT * FROM measures ORDER BY id").fetchall()
    finally:
        source.close()
        target.close()

    reports = []
    for path in args.jsonl:
        dry = load_jsonl(path, db_path=copy_db)
        if dry.conflicts or dry.changed:
            raise AssertionError(f"preview must add documents only: {dry}")
        loaded = load_jsonl(path, db_path=copy_db, commit=True)
        if loaded.conflicts:
            raise AssertionError(str(loaded))
        replay = load_jsonl(path, db_path=copy_db, commit=True)
        if replay.committed or replay.documents_changed:
            raise AssertionError("replay was not idempotent")
        reports.append({
            "input": str(path), "measure_rows_changed": loaded.changed,
            "document_roles_inserted": loaded.documents_inserted,
            "document_roles_updated": loaded.documents_updated,
            "document_roles_removed": loaded.documents_removed,
            "same_snapshot_replay_wrote": replay.committed,
        })

    database = Database(copy_db)
    with patch.object(socket.socket, "connect", side_effect=AssertionError("network forbidden in preview")):
        generator = WebsiteGenerator(database, output / "site" / "index.html")
        generator._load_finance_data = lambda: cached["financeData"]
        generator._load_insights_data = lambda: cached["insightsData"]
        generator.generate_prepared(original_measures, database.get_statistics(), cached["topics"], cached["recommendations"])

        # Separately exercise the real CLI database -> model field filter ->
        # export path. Keep enrichment inputs controlled and disclose the limit;
        # this is not evidence of successful semantic-model refresh (E5).
        with (
            patch.object(generate_site, "EMBEDDING_DATA_DIR", output / "without-embedding-inputs"),
            patch.object(WebsiteGenerator, "_load_finance_data", return_value=cached["financeData"]),
            patch.object(WebsiteGenerator, "_load_insights_data", return_value=cached["insightsData"]),
            patch.object(WebsiteGenerator, "_load_recommendations", return_value=cached["recommendations"]),
        ):
            cli_status = generate_site.main([
                "--db", str(copy_db), "--output", str(output / "cli-site" / "index.html"), "--force",
            ])
            assert cli_status == 0, "CLI export failed"
    after_rows = database.connect().execute("SELECT * FROM measures ORDER BY id").fetchall()
    assert [tuple(row) for row in after_rows] == before_rows, "measure rows changed"
    document_counts = [dict(row) for row in database.connect().execute(
        "SELECT m.county, d.snapshot_id, COUNT(*) AS role_records, "
        "COUNT(DISTINCT d.source_url) AS distinct_urls "
        "FROM measure_documents d JOIN measures m ON m.id = d.measure_id "
        "GROUP BY m.county, d.snapshot_id ORDER BY m.county"
    )]
    database.close()
    exported = json.loads((output / "site" / "measures-data.json").read_text(encoding="utf-8"))
    without_documents = lambda rows: [{k: v for k, v in row.items() if k != "official_documents"} for row in rows]
    assert without_documents(exported) == without_documents(original_measures), "existing site fields changed"
    cli_exported = json.loads((output / "cli-site" / "measures-data.json").read_text(encoding="utf-8"))
    with sqlite3.connect(copy_db) as connection:
        active_ids = {row[0] for row in connection.execute("SELECT id FROM active_measures")}
    assert {row["id"] for row in cli_exported} == active_ids, "CLI lost or changed database ids"
    assert {row["id"]: row.get("official_documents") for row in cli_exported} == {
        row["id"]: row.get("official_documents") for row in exported
    }, "CLI documents differ from prepared export"
    after_hashes = {str(path): digest(path) for path in sources}
    assert before_hashes == after_hashes, "source artifact changed"
    report = {
        "measure_count": len(exported), "all_measure_rows_unchanged": True,
        "prepared_input_fields_preserved": True, "source_hashes_unchanged": True,
        "cli_active_ids_and_documents_verified": True,
        "cli_enrichment_inputs": "cached finance/insights/recommendations; embedding step not exercised",
        "full_production_rebuild_verified": False,
        "finance_insights_recommendations_preserved": True,
        "sources_sha256": after_hashes, "loads": reports, "documents": document_counts,
        "measures_with_documents": sum(bool(row.get("official_documents")) for row in exported),
        "displayed_document_links": sum(len(row.get("official_documents", [])) for row in exported),
    }
    (output / "verification.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "sources_sha256"}, indent=2))


if __name__ == "__main__":
    main()
