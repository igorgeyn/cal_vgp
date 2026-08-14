"""Tests for stored-snapshot parsing and cross-snapshot registrar lineage."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.scrapers.registrar.parser import (
    LineageConflictError,
    SnapshotValidationError,
    parse_election,
)
from src.scrapers.registrar.sb import extract_measures_page
from src.scrapers.registrar.storage import (
    ArtifactIntegrityError,
    ArtifactMetadata,
    LocalArtifactStore,
)


FIXTURES = Path(__file__).parent / "fixtures" / "registrar" / "sb"
PAGE_URL = "https://elections.sbcounty.gov/elections/2026/1103/measures/"


def _put_snapshot(
    store: LocalArtifactStore,
    snapshot_id: str,
    fixture_name: str,
    *,
    row_count_override: int | None = None,
) -> dict[str, Path]:
    body = (FIXTURES / fixture_name).read_bytes()
    page = extract_measures_page(body, PAGE_URL)
    artifacts = []
    paths = {}

    page_ref = store.put_artifact(
        county="sb",
        election_date="2026-11-03",
        snapshot_id=snapshot_id,
        filename="page.html",
        body=body,
        metadata=ArtifactMetadata(PAGE_URL, "text/html", 200),
    )
    artifacts.append(
        {
            "filename": page_ref.filename,
            "source_url": PAGE_URL,
            "content_type": page_ref.content_type,
            "sha256": page_ref.sha256,
            "size_bytes": page_ref.size_bytes,
        }
    )
    paths[page_ref.filename] = Path(page_ref.storage_uri)

    for document in page.expected_documents:
        pdf_body = f"%PDF-1.4\n{document.filename}\n%%EOF".encode()
        ref = store.put_artifact(
            county="sb",
            election_date="2026-11-03",
            snapshot_id=snapshot_id,
            filename=document.filename,
            body=pdf_body,
            metadata=ArtifactMetadata(document.url, "application/pdf", 200),
        )
        artifacts.append(
            {
                "filename": ref.filename,
                "source_url": document.url,
                "content_type": ref.content_type,
                "sha256": ref.sha256,
                "size_bytes": ref.size_bytes,
            }
        )
        paths[ref.filename] = Path(ref.storage_uri)

    manifest = {
        "schema_version": 1,
        "county": "sb",
        "election_date": "2026-11-03",
        "snapshot_id": snapshot_id,
        "run_id": f"run-{snapshot_id}",
        "scraped_at": "2026-08-14T03:51:15+00:00",
        "scraper_version": "test",
        "fetch_mode": "requests",
        "source_base_url": "https://elections.sbcounty.gov",
        "election_url": PAGE_URL,
        "table_row_count": len(page.rows) if row_count_override is None else row_count_override,
        "table_headers": list(page.headers),
        "pdf_counts": {"expected": len(page.expected_documents), "saved": len(page.expected_documents)},
        "pdf_artifacts": [
            {
                "filename": document.filename,
                "table_row": document.table_row,
                "measure_letter": document.measure_letter,
                "role": document.role,
                "source_url": document.url,
            }
            for document in page.expected_documents
        ],
        "artifacts": artifacts,
    }
    store.put_manifest(
        county="sb",
        election_date="2026-11-03",
        snapshot_id=snapshot_id,
        manifest=manifest,
    )
    return paths


def test_parser_maps_lettered_snapshot_and_writes_deterministically(tmp_path: Path):
    store = LocalArtifactStore(tmp_path / "raw")
    _put_snapshot(store, "20260814T035115Z", "measures_2026_1103_lettered.html")
    output = tmp_path / "normalized.jsonl"

    first = parse_election(
        store,
        county="sb",
        election_date="2026-11-03",
        output_path=output,
    )
    first_bytes = output.read_bytes()
    second = parse_election(
        store,
        county="sb",
        election_date="2026-11-03",
        output_path=output,
    )

    assert first.record_count == second.record_count == 20
    assert output.read_bytes() == first_bytes
    assert len({item["measure"]["measure_id"] for item in first.records}) == 20
    assert all(item["measure"]["measure_id"].startswith("REG_SB_20261103_") for item in first.records)
    assert all(len(item["measure"]["measure_id"].rsplit("_", 1)[1]) == 64 for item in first.records)

    needles_l = next(item for item in first.records if item["measure"]["measure_letter"] == "L")
    assert needles_l["measure"]["county"] == "SAN BERNARDINO"
    assert needles_l["measure"]["jurisdiction"] == "City of Needles"
    assert needles_l["measure"]["title"] == "City of Needles — Bond Measure"
    assert needles_l["measure"]["vote_threshold"] == "66.67%"
    assert needles_l["measure"]["passed"] is None
    assert needles_l["measure"]["pass_fail"] is None
    assert needles_l["measure"]["pdf_url"].endswith("/30/FT_CityofNeedles.pdf")
    assert {document["role"] for document in needles_l["documents"]} == {
        "resolution",
        "text",
        "analysis",
        "tax_rate_statement",
    }
    assert json.loads(output.read_text(encoding="utf-8").splitlines()[13]) == needles_l


def test_lineage_survives_tbd_letters_description_and_url_drift(tmp_path: Path):
    store = LocalArtifactStore(tmp_path / "raw")
    _put_snapshot(store, "20260727T171800Z", "measures_2026_1103_mixed.html")
    old = parse_election(
        store,
        county="sb",
        election_date="2026-11-03",
        output_path=tmp_path / "old.jsonl",
    )
    old_by_jurisdiction = {record["measure"]["jurisdiction"]: record for record in old.records}

    _put_snapshot(store, "20260814T035115Z", "measures_2026_1103_lettered.html")
    latest = parse_election(
        store,
        county="sb",
        election_date="2026-11-03",
        output_path=tmp_path / "latest.jsonl",
    )

    # Beaumont has no old documents and its description changed from
    # "School Bonds" to "Bond Measure"; unique jurisdiction+threshold links it.
    beaumont = next(record for record in latest.records if record["measure"]["jurisdiction"] == "Beaumont Unified School District")
    assert beaumont["measure"]["measure_letter"] == "B"
    assert beaumont["measure"]["measure_id"] == old_by_jurisdiction["Beaumont Unified School District"]["measure"]["measure_id"]

    # Needles' source URLs acquired /27/ while two more Needles measures were
    # added. Exact semantic evidence links only the original tax measure.
    needles_k = next(record for record in latest.records if record["measure"]["measure_letter"] == "K")
    assert needles_k["measure"]["measure_id"] == old_by_jurisdiction["City of Needles"]["measure"]["measure_id"]
    assert len([record for record in latest.records if record["measure"]["jurisdiction"] == "City of Needles"]) == 3


def test_parser_rejects_checksum_corruption(tmp_path: Path):
    store = LocalArtifactStore(tmp_path / "raw")
    paths = _put_snapshot(store, "20260814T035115Z", "measures_2026_1103_lettered.html")
    paths["page.html"].write_bytes(b"corrupt")

    with pytest.raises(ArtifactIntegrityError):
        parse_election(
            store,
            county="sb",
            election_date="2026-11-03",
            output_path=tmp_path / "never.jsonl",
        )
    assert not (tmp_path / "never.jsonl").exists()


def test_parser_rejects_manifest_cardinality_mismatch(tmp_path: Path):
    store = LocalArtifactStore(tmp_path / "raw")
    _put_snapshot(
        store,
        "20260814T035115Z",
        "measures_2026_1103_lettered.html",
        row_count_override=19,
    )

    with pytest.raises(SnapshotValidationError, match="row count mismatch"):
        parse_election(
            store,
            county="sb",
            election_date="2026-11-03",
            output_path=tmp_path / "never.jsonl",
        )
