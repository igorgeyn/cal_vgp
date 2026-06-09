"""Tests for the registrar artifact storage layer."""
from __future__ import annotations

import hashlib
import json

import pytest

from src.scrapers.registrar.storage import (
    ArtifactIntegrityError,
    ArtifactMetadata,
    ArtifactNotFound,
    ArtifactRef,
    LocalArtifactStore,
    RawArtifactStore,
    make_store,
)


# ---------------------------------------------------------------- fixtures


@pytest.fixture
def store(tmp_path) -> LocalArtifactStore:
    return LocalArtifactStore(base_dir=tmp_path, env="dev")


@pytest.fixture
def sample_meta() -> ArtifactMetadata:
    return ArtifactMetadata(
        source_url="https://example.com/measures",
        content_type="text/html",
        http_status=200,
        final_url="https://example.com/measures",
        etag='W/"abc123"',
        last_modified="Sun, 08 Jun 2026 12:00:00 GMT",
        fetch_mode="requests",
    )


# ---------------------------------------------------------------- put / get


def test_put_artifact_returns_ref_with_correct_sha_and_size(store, sample_meta):
    body = b"<html>hello world</html>"
    ref = store.put_artifact(
        county="sb",
        election_date="2026-03-24",
        snapshot_id="20260101T120000Z",
        filename="page.html",
        body=body,
        metadata=sample_meta,
    )

    assert ref.sha256 == hashlib.sha256(body).hexdigest()
    assert ref.size_bytes == len(body)
    assert ref.county == "sb"
    assert ref.election_date == "2026-03-24"
    assert ref.snapshot_id == "20260101T120000Z"
    assert ref.filename == "page.html"
    assert ref.content_type == "text/html"
    assert ref.storage_uri  # non-empty fs path


def test_get_artifact_round_trip(store, sample_meta):
    body = b"<html>roundtrip</html>"
    ref = store.put_artifact(
        county="sb",
        election_date="2026-03-24",
        snapshot_id="snap1",
        filename="page.html",
        body=body,
        metadata=sample_meta,
    )

    assert store.get_artifact(ref) == body


def test_get_artifact_raises_when_missing(store):
    ghost = ArtifactRef(
        county="sb",
        election_date="2026-03-24",
        snapshot_id="ghost-snap",
        filename="missing.html",
        sha256="0" * 64,
        size_bytes=0,
        content_type="text/html",
        storage_uri="",
    )
    with pytest.raises(ArtifactNotFound):
        store.get_artifact(ghost)


def test_get_artifact_raises_on_integrity_mismatch(store, sample_meta, tmp_path):
    """Tamper with file on disk after put; get_artifact should detect."""
    ref = store.put_artifact(
        county="sb",
        election_date="2026-03-24",
        snapshot_id="snap1",
        filename="page.html",
        body=b"original content",
        metadata=sample_meta,
    )

    # Overwrite the file directly to break the SHA invariant.
    tampered_path = (
        tmp_path / "dev" / "sb" / "2026-03-24" / "snap1" / "page.html"
    )
    tampered_path.write_bytes(b"tampered content")

    with pytest.raises(ArtifactIntegrityError):
        store.get_artifact(ref)


# ---------------------------------------------------------------- manifest


def test_put_and_get_manifest_round_trip(store):
    manifest = {
        "schema_version": 1,
        "snapshot_id": "snap1",
        "county": "sb",
        "election_date": "2026-03-24",
        "artifacts": [
            {
                "filename": "page.html",
                "sha256": "a" * 64,
                "size_bytes": 42,
                "content_type": "text/html",
            },
        ],
    }
    storage_uri = store.put_manifest(
        county="sb",
        election_date="2026-03-24",
        snapshot_id="snap1",
        manifest=manifest,
    )
    assert storage_uri  # non-empty path

    retrieved = store.get_manifest(
        county="sb",
        election_date="2026-03-24",
        snapshot_id="snap1",
    )
    assert retrieved == manifest


def test_get_manifest_raises_when_missing(store):
    with pytest.raises(ArtifactNotFound):
        store.get_manifest(
            county="sb",
            election_date="2026-03-24",
            snapshot_id="ghost-snap",
        )


def test_manifest_stored_as_pretty_json(store, tmp_path):
    store.put_manifest(
        county="sb",
        election_date="2026-03-24",
        snapshot_id="snap1",
        manifest={"a": 1, "b": [2, 3]},
    )
    # Verify human-readable formatting on disk
    path = tmp_path / "dev" / "sb" / "2026-03-24" / "snap1" / "manifest.json"
    content = path.read_text()
    assert "\n" in content  # pretty-printed, not one-line
    assert json.loads(content) == {"a": 1, "b": [2, 3]}


# ---------------------------------------------------------------- listing


def test_list_artifacts_reads_from_manifest(store, sample_meta):
    """list_artifacts is manifest-derived, not filesystem-walked."""
    ref1 = store.put_artifact(
        county="sb",
        election_date="2026-03-24",
        snapshot_id="snap1",
        filename="page.html",
        body=b"page",
        metadata=sample_meta,
    )
    ref2 = store.put_artifact(
        county="sb",
        election_date="2026-03-24",
        snapshot_id="snap1",
        filename="analysis.pdf",
        body=b"%PDF-1.4\n...",
        metadata=ArtifactMetadata(
            source_url="https://example.com/analysis.pdf",
            content_type="application/pdf",
            http_status=200,
        ),
    )
    store.put_manifest(
        county="sb",
        election_date="2026-03-24",
        snapshot_id="snap1",
        manifest={
            "artifacts": [
                {
                    "filename": ref1.filename,
                    "sha256": ref1.sha256,
                    "size_bytes": ref1.size_bytes,
                    "content_type": ref1.content_type,
                },
                {
                    "filename": ref2.filename,
                    "sha256": ref2.sha256,
                    "size_bytes": ref2.size_bytes,
                    "content_type": ref2.content_type,
                },
            ],
        },
    )

    refs = store.list_artifacts(
        county="sb",
        election_date="2026-03-24",
        snapshot_id="snap1",
    )
    assert len(refs) == 2
    assert {r.filename for r in refs} == {"page.html", "analysis.pdf"}
    assert all(r.county == "sb" for r in refs)
    assert {r.content_type for r in refs} == {"text/html", "application/pdf"}


def test_list_artifacts_raises_if_no_manifest(store, sample_meta):
    """list_artifacts depends on manifest; without one, raises."""
    store.put_artifact(
        county="sb",
        election_date="2026-03-24",
        snapshot_id="snap1",
        filename="page.html",
        body=b"orphan",
        metadata=sample_meta,
    )
    with pytest.raises(ArtifactNotFound):
        store.list_artifacts(
            county="sb",
            election_date="2026-03-24",
            snapshot_id="snap1",
        )


def test_list_snapshots_sorted_ascending(store, sample_meta):
    for snap in ["20260102T120000Z", "20260101T120000Z", "20260103T120000Z"]:
        store.put_artifact(
            county="sb",
            election_date="2026-03-24",
            snapshot_id=snap,
            filename="page.html",
            body=b"x",
            metadata=sample_meta,
        )
    snaps = store.list_snapshots(county="sb", election_date="2026-03-24")
    assert snaps == [
        "20260101T120000Z",
        "20260102T120000Z",
        "20260103T120000Z",
    ]


def test_list_snapshots_empty_for_unknown(store):
    assert store.list_snapshots(county="sb", election_date="2099-01-01") == []


# ---------------------------------------------------------------- exists


def test_exists_snapshot_and_artifact(store, sample_meta):
    store.put_artifact(
        county="sb",
        election_date="2026-03-24",
        snapshot_id="snap1",
        filename="page.html",
        body=b"x",
        metadata=sample_meta,
    )

    assert store.exists(
        county="sb", election_date="2026-03-24", snapshot_id="snap1"
    )
    assert store.exists(
        county="sb",
        election_date="2026-03-24",
        snapshot_id="snap1",
        filename="page.html",
    )
    assert not store.exists(
        county="sb",
        election_date="2026-03-24",
        snapshot_id="snap1",
        filename="ghost.html",
    )
    assert not store.exists(
        county="sb",
        election_date="2026-03-24",
        snapshot_id="ghost-snap",
    )


# ---------------------------------------------------------------- env split


def test_dev_and_prod_envs_are_isolated(tmp_path, sample_meta):
    dev = LocalArtifactStore(base_dir=tmp_path, env="dev")
    prod = LocalArtifactStore(base_dir=tmp_path, env="prod")

    dev.put_artifact(
        county="sb",
        election_date="2026-03-24",
        snapshot_id="snap1",
        filename="page.html",
        body=b"DEV ONLY",
        metadata=sample_meta,
    )

    assert dev.exists(
        county="sb", election_date="2026-03-24", snapshot_id="snap1"
    )
    assert not prod.exists(
        county="sb", election_date="2026-03-24", snapshot_id="snap1"
    )


# ---------------------------------------------------------------- factory


def test_make_store_returns_local_when_no_r2_env(monkeypatch):
    for k in (
        "R2_ACCESS_KEY_ID",
        "R2_SECRET_ACCESS_KEY",
        "R2_ENDPOINT_URL",
        "R2_BUCKET",
    ):
        monkeypatch.delenv(k, raising=False)

    store = make_store()
    assert isinstance(store, LocalArtifactStore)


def test_make_store_raises_not_implemented_when_r2_env_set(monkeypatch):
    monkeypatch.setenv("R2_ACCESS_KEY_ID", "key")
    monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "secret")
    monkeypatch.setenv("R2_ENDPOINT_URL", "https://r2.example.com")
    monkeypatch.setenv("R2_BUCKET", "test-bucket")

    with pytest.raises(NotImplementedError):
        make_store()


def test_make_store_env_arg_overrides_r2_env_var(monkeypatch, tmp_path):
    for k in (
        "R2_ACCESS_KEY_ID",
        "R2_SECRET_ACCESS_KEY",
        "R2_ENDPOINT_URL",
        "R2_BUCKET",
    ):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("R2_ENV", "prod")

    store = make_store(env="dev")
    assert isinstance(store, LocalArtifactStore)
    assert store._env == "dev"  # explicit arg wins


# ---------------------------------------------------------------- protocol


def test_local_store_satisfies_protocol():
    """LocalArtifactStore should satisfy the RawArtifactStore protocol."""
    assert isinstance(LocalArtifactStore(), RawArtifactStore)
