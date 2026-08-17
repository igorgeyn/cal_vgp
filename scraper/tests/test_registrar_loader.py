"""Tests for dry-run, deduplication, and atomic registrar loading."""
from __future__ import annotations

import json
import hashlib
import sqlite3
from pathlib import Path

import pytest

from src.database.models import BallotMeasure
from src.database.operations import Database
from src.scrapers.registrar.loader import NormalizedDataError, load_jsonl


def _record(
    *,
    row: int = 1,
    count: int = 1,
    letter: str = "A",
    digest_char: str = "A",
    jurisdiction: str = "City of Example",
    description: str = "Transactions and Use Tax Measure",
    text_pdf: bool = True,
) -> dict:
    origin_value = f"test-origin-{digest_char}"
    identity_payload = json.dumps(
        ["sb", "2026-11-03", "semantic", origin_value],
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    measure_id = f"REG_SB_20261103_{hashlib.sha256(identity_payload).hexdigest().upper()}"
    text_url = f"https://uploads.rov.sbcounty.gov/{letter}/text.pdf" if text_pdf else None
    documents = []
    if text_url:
        documents.append(
            {
                "role": "text",
                "source_url": text_url,
                "snapshot_filename": f"measure_{letter.lower()}_text.pdf",
                "sha256": digest_char.lower() * 64,
                "size_bytes": 100,
                "content_type": "application/pdf",
            }
        )
    return {
        "schema_version": 1,
        "county_slug": "sb",
        "election_date": "2026-11-03",
        "snapshot_id": "20260814T035115Z",
        "snapshot_row_count": count,
        "table_row": row,
        "scraped_at": "2026-08-14T03:51:15+00:00",
        "page_sha256": "f" * 64,
        "lineage": {
            "origin_snapshot_id": "20260727T171800Z",
            "origin_table_row": row,
            "origin_key_kind": "semantic",
            "origin_key_value": origin_value,
            "origin_key_sha256": hashlib.sha256(origin_value.encode("utf-8")).hexdigest(),
        },
        "measure": {
            "measure_id": measure_id,
            "measure_letter": letter,
            "year": 2026,
            "state": "CA",
            "county": "SAN BERNARDINO",
            "jurisdiction": jurisdiction,
            "title": f"{jurisdiction} — {description}",
            "description": description,
            "ballot_question": None,
            "yes_votes": None,
            "no_votes": None,
            "total_votes": None,
            "percent_yes": None,
            "percent_no": None,
            "passed": None,
            "pass_fail": None,
            "vote_threshold": "50%",
            "measure_type": "Measure",
            "topic_primary": None,
            "topic_secondary": None,
            "category_type": None,
            "category_topic": None,
            "data_source": "SB_County_Registrar",
            "source_url": "https://elections.sbcounty.gov/elections/2026/1103/measures/",
            "pdf_url": text_url,
            "has_summary": False,
            "summary_title": None,
            "summary_text": None,
            "election_type": "general",
            "election_type_imputed": 0,
            "election_date": "2026-11-03",
            "is_active": True,
            "is_duplicate": False,
            "duplicate_type": None,
            "master_id": None,
        },
        "documents": documents,
    }


def _write(path: Path, records: list[dict]) -> Path:
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )
    return path


def _database(path: Path) -> Path:
    Database(path).close()
    return path


def _rows(db_path: Path) -> list[sqlite3.Row]:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        return connection.execute("SELECT * FROM measures ORDER BY id").fetchall()
    finally:
        connection.close()


def test_dry_run_commit_and_second_run_are_idempotent(tmp_path: Path):
    db_path = _database(tmp_path / "measures.db")
    jsonl = _write(tmp_path / "records.jsonl", [_record()])

    dry_run = load_jsonl(jsonl, db_path=db_path)
    assert (dry_run.inserted, dry_run.updated, dry_run.skipped, dry_run.committed) == (1, 0, 0, False)
    assert _rows(db_path) == []

    backup = tmp_path / "before.db"
    first = load_jsonl(jsonl, db_path=db_path, commit=True, backup_path=backup)
    assert first.committed is True
    assert first.inserted == 1
    assert first.backup_path == backup
    assert backup.exists()
    stored = dict(_rows(db_path)[0])
    tracking = (stored["update_count"], stored["updated_at"], stored["last_seen_at"])

    second = load_jsonl(jsonl, db_path=db_path, commit=True)
    assert second.committed is False
    assert second.skipped == 1
    assert second.changed == 0
    stored_again = dict(_rows(db_path)[0])
    assert (stored_again["update_count"], stored_again["updated_at"], stored_again["last_seen_at"]) == tracking


def test_repeated_short_descriptions_are_distinct_measures(tmp_path: Path):
    db_path = _database(tmp_path / "measures.db")
    records = [
        _record(row=1, count=2, letter="E", digest_char="A", jurisdiction="City of Example"),
        _record(row=2, count=2, letter="P", digest_char="B", jurisdiction="City of Example"),
    ]
    jsonl = _write(tmp_path / "records.jsonl", records)

    report = load_jsonl(jsonl, db_path=db_path, commit=True, backup_path=tmp_path / "before.db")
    assert report.inserted == 2
    assert report.conflicts == ()
    rows = _rows(db_path)
    assert len(rows) == 2
    assert len({row["fingerprint"] for row in rows}) == 2
    assert rows[0]["content_hash"] == rows[1]["content_hash"]  # deliberately not a dedup key

    replay = load_jsonl(jsonl, db_path=db_path, commit=True)
    assert replay.conflicts == ()
    assert replay.skipped == 2
    assert replay.committed is False


def test_substantive_update_increments_once_then_skips(tmp_path: Path):
    db_path = _database(tmp_path / "measures.db")
    jsonl = _write(tmp_path / "records.jsonl", [_record(description="Municipal Code Change")])
    load_jsonl(jsonl, db_path=db_path, commit=True, backup_path=tmp_path / "before.db")

    changed = _record(description="Municipal Code Amendment")
    _write(jsonl, [changed])
    update = load_jsonl(jsonl, db_path=db_path, commit=True, backup_path=tmp_path / "before-update.db")
    assert update.updated == 1
    assert dict(_rows(db_path)[0])["update_count"] == 1

    no_op = load_jsonl(jsonl, db_path=db_path, commit=True)
    assert no_op.skipped == 1
    assert dict(_rows(db_path)[0])["update_count"] == 1


def test_complete_snapshot_deactivates_and_reactivates_same_lineage(tmp_path: Path):
    db_path = _database(tmp_path / "measures.db")
    first_records = [
        _record(row=1, count=2, letter="A", digest_char="A"),
        _record(row=2, count=2, letter="B", digest_char="B", jurisdiction="City of Second"),
    ]
    jsonl = _write(tmp_path / "records.jsonl", first_records)
    load_jsonl(jsonl, db_path=db_path, commit=True, backup_path=tmp_path / "before.db")

    only_first = _record(row=1, count=1, letter="A", digest_char="A")
    only_first["snapshot_id"] = "20260821T035115Z"
    _write(jsonl, [only_first])
    removed = load_jsonl(
        jsonl,
        db_path=db_path,
        commit=True,
        backup_path=tmp_path / "before-remove.db",
    )
    assert removed.committed is False
    assert removed.deactivated == 0
    assert any("reconciliation" in conflict for conflict in removed.conflicts)
    assert [row["is_active"] for row in _rows(db_path)] == [1, 1]

    removed = load_jsonl(
        jsonl,
        db_path=db_path,
        commit=True,
        backup_path=tmp_path / "before-reviewed-remove.db",
        reconcile_snapshot_id="20260821T035115Z",
    )
    assert (removed.deactivated, removed.skipped) == (1, 1)
    assert [row["is_active"] for row in _rows(db_path)] == [1, 0]

    restored_records = [dict(record, snapshot_id="20260828T035115Z") for record in first_records]
    _write(jsonl, restored_records)
    restored = load_jsonl(
        jsonl,
        db_path=db_path,
        commit=True,
        backup_path=tmp_path / "before-restore.db",
    )
    assert restored.updated == 1
    assert [row["is_active"] for row in _rows(db_path)] == [1, 1]


def test_older_snapshot_is_rejected_unless_exact_rollback_is_authorized(tmp_path: Path):
    db_path = _database(tmp_path / "measures.db")
    current = _record()
    current["snapshot_id"] = "20260814T035115Z"
    jsonl = _write(tmp_path / "records.jsonl", [current])
    first = load_jsonl(jsonl, db_path=db_path, commit=True, backup_path=tmp_path / "before.db")
    assert first.committed is True

    older = _record(description="Older wording")
    older["snapshot_id"] = "20260727T170014Z"
    older["page_sha256"] = "e" * 64
    _write(jsonl, [older])
    refused = load_jsonl(jsonl, db_path=db_path, commit=True)

    assert refused.committed is False
    assert refused.updated == 0
    assert any("older than" in conflict for conflict in refused.conflicts)
    assert dict(_rows(db_path)[0])["description"] == "Transactions and Use Tax Measure"
    assert not list(tmp_path.glob("*_registrar_backup_*.db"))

    accepted = load_jsonl(
        jsonl,
        db_path=db_path,
        commit=True,
        backup_path=tmp_path / "before-reviewed-rollback.db",
        allow_rollback_snapshot_id="20260727T170014Z",
    )
    assert accepted.committed is True
    assert accepted.updated == 1
    assert dict(_rows(db_path)[0])["description"] == "Older wording"


def test_newer_unchanged_snapshot_advances_scope_without_measure_churn(tmp_path: Path):
    db_path = _database(tmp_path / "measures.db")
    jsonl = _write(tmp_path / "records.jsonl", [_record()])
    load_jsonl(jsonl, db_path=db_path, commit=True, backup_path=tmp_path / "before.db")
    tracking = dict(_rows(db_path)[0])["update_count"]

    newer = _record()
    newer["snapshot_id"] = "20260821T035115Z"
    newer["page_sha256"] = "e" * 64
    _write(jsonl, [newer])
    advanced = load_jsonl(
        jsonl, db_path=db_path, commit=True, backup_path=tmp_path / "before-newer.db"
    )
    assert advanced.committed is True
    assert advanced.scope_advanced is True
    assert (advanced.updated, advanced.skipped) == (0, 1)
    assert dict(_rows(db_path)[0])["update_count"] == tracking

    repeated = load_jsonl(jsonl, db_path=db_path, commit=True)
    assert repeated.committed is False
    assert repeated.scope_advanced is False


def test_same_snapshot_with_changed_page_checksum_is_rejected(tmp_path: Path):
    db_path = _database(tmp_path / "measures.db")
    record = _record()
    jsonl = _write(tmp_path / "records.jsonl", [record])
    load_jsonl(jsonl, db_path=db_path, commit=True, backup_path=tmp_path / "before.db")

    record["page_sha256"] = "e" * 64
    _write(jsonl, [record])
    report = load_jsonl(jsonl, db_path=db_path, commit=True)

    assert report.committed is False
    assert any("checksum changed" in conflict for conflict in report.conflicts)
    assert not list(tmp_path.glob("*_registrar_backup_*.db"))


def test_identity_registry_keeps_first_canonical_id_when_parser_origin_changes(tmp_path: Path):
    db_path = _database(tmp_path / "measures.db")
    first_record = _record(digest_char="A")
    jsonl = _write(tmp_path / "records.jsonl", [first_record])
    first = load_jsonl(jsonl, db_path=db_path, commit=True, backup_path=tmp_path / "before.db")
    assert first.committed is True
    canonical_id = first_record["measure"]["measure_id"]

    # Restoring an older archive observation changes the parser's earliest-origin
    # proposal, but the selected current row and its official document are unchanged.
    changed_origin = _record(digest_char="B")
    changed_origin["snapshot_id"] = "20260821T035115Z"
    changed_origin["page_sha256"] = "e" * 64
    _write(jsonl, [changed_origin])
    second = load_jsonl(
        jsonl,
        db_path=db_path,
        commit=True,
        backup_path=tmp_path / "before-new-proposal.db",
    )

    assert second.conflicts == ()
    assert second.inserted == 0
    assert len(_rows(db_path)) == 1
    assert dict(_rows(db_path)[0])["measure_id"] == canonical_id

    connection = sqlite3.connect(db_path)
    try:
        registered = connection.execute(
            "SELECT canonical_measure_id FROM registrar_identities"
        ).fetchone()[0]
    finally:
        connection.close()
    assert registered == canonical_id


def test_semantics_alone_cannot_reassign_a_registered_identity(tmp_path: Path):
    db_path = _database(tmp_path / "measures.db")
    jsonl = _write(tmp_path / "records.jsonl", [_record(digest_char="A", text_pdf=False)])
    load_jsonl(jsonl, db_path=db_path, commit=True, backup_path=tmp_path / "before.db")

    changed_origin = _record(digest_char="B", text_pdf=False)
    changed_origin["snapshot_id"] = "20260821T035115Z"
    changed_origin["page_sha256"] = "e" * 64
    _write(jsonl, [changed_origin])
    report = load_jsonl(jsonl, db_path=db_path, commit=True)

    assert report.committed is False
    assert any("semantic-only" in conflict for conflict in report.conflicts)
    assert len(_rows(db_path)) == 1


def test_strict_cross_source_match_is_adopted_without_losing_richer_fields(tmp_path: Path):
    db_path = _database(tmp_path / "measures.db")
    database = Database(db_path)
    existing = BallotMeasure(
        measure_id="202699999",
        measure_letter="A",
        year=2026,
        county="SAN BERNARDINO",
        jurisdiction=None,
        title="Aggregator title",
        ballot_question="Shall the official question be adopted?",
        data_source="CEDA",
        election_date="November 3, 2026",
    )
    database.insert_measure(existing)
    database.connect().commit()
    database.close()
    original_id = _rows(db_path)[0]["id"]

    jsonl = _write(tmp_path / "records.jsonl", [_record(letter="A")])
    report = load_jsonl(jsonl, db_path=db_path, commit=True, backup_path=tmp_path / "before.db")

    assert report.updated == 1
    assert report.inserted == 0
    rows = _rows(db_path)
    assert len(rows) == 1
    row = dict(rows[0])
    assert row["id"] == original_id
    assert row["data_source"] == "SB_County_Registrar"
    assert row["measure_id"].startswith("REG_SB_20261103_")
    assert row["ballot_question"] == "Shall the official question be adopted?"


def test_multiple_cross_source_candidates_are_a_conflict_and_never_write(tmp_path: Path):
    db_path = _database(tmp_path / "measures.db")
    database = Database(db_path)
    for measure_id, source in (("candidate-1", "CEDA"), ("candidate-2", "Ballotpedia")):
        database.insert_measure(
            BallotMeasure(
                measure_id=measure_id,
                measure_letter="A",
                year=2026,
                county="SAN BERNARDINO",
                data_source=source,
                election_date="2026-11-03",
            )
        )
    database.connect().commit()
    database.close()

    jsonl = _write(tmp_path / "records.jsonl", [_record(letter="A")])
    report = load_jsonl(jsonl, db_path=db_path, commit=True)

    assert report.committed is False
    assert len(report.conflicts) == 1
    assert len(_rows(db_path)) == 2
    assert not list(tmp_path.glob("*_registrar_backup_*.db"))


def test_incomplete_jsonl_is_rejected_before_database_access(tmp_path: Path):
    record = _record(count=2)
    jsonl = _write(tmp_path / "records.jsonl", [record])

    with pytest.raises(NormalizedDataError, match="snapshot_row_count"):
        load_jsonl(jsonl, db_path=tmp_path / "does-not-exist.db")


def test_measure_id_must_match_lineage_digest(tmp_path: Path):
    record = _record()
    record["measure"]["measure_id"] = record["measure"]["measure_id"][:-1] + "0"
    jsonl = _write(tmp_path / "records.jsonl", [record])

    with pytest.raises(NormalizedDataError, match="measure_id does not match"):
        load_jsonl(jsonl, db_path=tmp_path / "does-not-exist.db")
