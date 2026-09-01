"""Tests for stored-snapshot parsing and cross-snapshot registrar lineage."""
from __future__ import annotations

import json
import re
from dataclasses import replace
from pathlib import Path

import pytest

from src.scrapers.registrar.parser import (
    LineageConflictError,
    ParsedSnapshot,
    SnapshotValidationError,
    _link_snapshot,
    parse_election,
)
from src.scrapers.registrar.sb import extract_measures_page
from src.scrapers.registrar.sb_interpretation import (
    ExpectedDocument,
    MeasureRow,
    MeasuresPage,
    interpret_measures_page,
)
from src.scrapers.registrar.storage import (
    ArtifactRef,
    ArtifactIntegrityError,
    ArtifactMetadata,
    LocalArtifactStore,
)


FIXTURES = Path(__file__).parent / "fixtures" / "registrar" / "sb"
PAGE_URL = "https://elections.sbcounty.gov/elections/2026/1103/measures/"


def _synthetic_snapshot(snapshot_id: str, rows: tuple[MeasureRow, ...]) -> ParsedSnapshot:
    page_ref = ArtifactRef(
        county="sb",
        election_date="2026-11-03",
        snapshot_id=snapshot_id,
        filename="page.html",
        sha256="f" * 64,
        size_bytes=1,
        content_type="text/html",
        storage_uri="memory://page.html",
    )
    return ParsedSnapshot(
        snapshot_id=snapshot_id,
        manifest={},
        page=MeasuresPage((), rows, tuple(doc for row in rows for doc in row.documents)),
        page_ref=page_ref,
        artifact_refs={},
    )


def _synthetic_row(row: int, letter: str, description: str, url: str) -> MeasureRow:
    document = ExpectedDocument(
        filename=f"row_{row}.pdf",
        url=url,
        role="text",
        measure_letter=letter,
        table_row=row,
    )
    return MeasureRow(row, letter, f"City {description}", description, "50% + 1", (document,))


def _put_snapshot(
    store: LocalArtifactStore,
    snapshot_id: str,
    fixture_name: str,
    *,
    row_count_override: int | None = None,
    schema_version: int = 1,
) -> dict[str, Path]:
    body = (FIXTURES / fixture_name).read_bytes()
    captured = extract_measures_page(body, PAGE_URL)
    page = interpret_measures_page(captured)
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

    document_entries = []
    if schema_version == 1:
        slugs = [
            "_".join(re.findall(r"[a-z0-9]+", row.letter.casefold()))
            for row in page.rows
        ]
        collisions = {slug for slug in slugs if slugs.count(slug) > 1}
        for row, slug in zip(page.rows, slugs):
            stem = (
                f"measure_{slug}_r{row.table_row:03d}"
                if slug in collisions
                else f"measure_{slug}"
            )
            for document in row.documents:
                rebound = replace(
                    document,
                    filename=f"{stem}_{document.role}.pdf",
                )
                document_entries.append(
                    (
                        rebound,
                        {
                            "filename": rebound.filename,
                            "table_row": rebound.table_row,
                            "measure_letter": rebound.measure_letter,
                            "role": rebound.role,
                            "source_url": rebound.url,
                        },
                    )
                )
    elif schema_version == 2:
        roles_by_filename = {
            document.filename: document for document in page.expected_documents
        }
        for document in captured.expected_documents:
            document_entries.append(
                (
                    roles_by_filename[document.filename],
                    {
                        "filename": document.filename,
                        "table_row": document.table_row,
                        "measure_letter": document.measure_letter,
                        "column": document.column,
                        "label": document.label,
                        "source_url": document.url,
                    },
                )
            )
    else:
        raise AssertionError(f"unsupported test schema {schema_version}")

    for document, _audit in document_entries:
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
        "schema_version": schema_version,
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
        "pdf_artifacts": [audit for _document, audit in document_entries],
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


def test_v1_and_v2_assign_same_roles_and_identities(tmp_path: Path):
    outputs = {}
    for schema_version in (1, 2):
        store = LocalArtifactStore(tmp_path / f"raw-v{schema_version}")
        _put_snapshot(
            store,
            "20260814T035115Z",
            "measures_2026_1103_lettered.html",
            schema_version=schema_version,
        )
        report = parse_election(
            store,
            county="sb",
            election_date="2026-11-03",
            output_path=tmp_path / f"v{schema_version}.jsonl",
        )
        outputs[schema_version] = {
            record["measure"]["measure_letter"]: (
                record["measure"]["measure_id"],
                sorted(
                    (document["role"], document["source_url"])
                    for document in record["documents"]
                ),
            )
            for record in report.records
        }

    assert outputs[2] == outputs[1]


def test_lineage_survives_tbd_letters_description_and_url_drift(tmp_path: Path):
    store = LocalArtifactStore(tmp_path / "raw")
    _put_snapshot(store, "20260727T170014Z", "measures_2026_1103_mixed.html")
    old = parse_election(
        store,
        county="sb",
        election_date="2026-11-03",
        output_path=tmp_path / "old.jsonl",
    )
    old_by_jurisdiction = {record["measure"]["jurisdiction"]: record for record in old.records}

    _put_snapshot(
        store,
        "20260814T034259Z",
        "measures_2026_1103_lettered.html",
        schema_version=2,
    )
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


def test_reuploaded_documents_and_swapped_letters_raise_instead_of_swapping_identity():
    first = _synthetic_snapshot(
        "20260801T000000Z",
        (
            _synthetic_row(1, "A", "Alpha", "https://example.test/old-alpha.pdf"),
            _synthetic_row(2, "B", "Beta", "https://example.test/old-beta.pdf"),
        ),
    )
    second = _synthetic_snapshot(
        "20260808T000000Z",
        (
            _synthetic_row(1, "B", "Alpha", "https://example.test/new-alpha.pdf"),
            _synthetic_row(2, "A", "Beta", "https://example.test/new-beta.pdf"),
        ),
    )
    lineages = []
    _link_snapshot(lineages, first)

    with pytest.raises(LineageConflictError, match="letter.*contradicts"):
        _link_snapshot(lineages, second)


def test_override_cannot_make_a_shared_url_look_uniquely_owned():
    shared_url = "https://example.test/shared-packet.pdf"
    first = _synthetic_snapshot(
        "20260801T000000Z",
        (
            _synthetic_row(1, "A", "Alpha", shared_url),
            _synthetic_row(2, "B", "Beta", shared_url),
        ),
    )
    second = _synthetic_snapshot(
        "20260808T000000Z",
        (
            _synthetic_row(1, "A", "Alpha", shared_url),
            _synthetic_row(2, "TBD", "Gamma", shared_url),
        ),
    )
    lineages = []
    _link_snapshot(lineages, first)
    original_second_lineage = lineages[1]

    links = _link_snapshot(
        lineages,
        second,
        {("20260808T000000Z", 1): ("20260801T000000Z", 1)},
    )

    assert links[1] is not original_second_lineage
    assert links[1].origin_snapshot_id == "20260808T000000Z"
    assert len(lineages) == 3


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
