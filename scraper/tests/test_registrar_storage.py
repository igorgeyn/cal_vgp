"""Tests for the registrar artifact storage layer."""
from __future__ import annotations

import hashlib
import io
import json

import pytest

from src.scrapers.registrar.storage import (
    ArtifactIntegrityError,
    ArtifactMetadata,
    ArtifactNotFound,
    ArtifactRef,
    LocalArtifactStore,
    R2ArtifactStore,
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


def test_make_store_returns_r2_when_r2_env_set(monkeypatch):
    monkeypatch.setenv("R2_ACCESS_KEY_ID", "key")
    monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "secret")
    monkeypatch.setenv("R2_ENDPOINT_URL", "https://r2.example.com")
    monkeypatch.setenv("R2_BUCKET", "test-bucket")
    monkeypatch.setenv("R2_ENV", "prod")

    # Client creation is lazy, so no boto3/network needed here.
    store = make_store()
    assert isinstance(store, R2ArtifactStore)
    assert store._env == "prod"
    assert store._bucket == "test-bucket"


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


# ---------------------------------------------------------------- run manifest


def test_local_put_run_manifest_lands_beside_env_tree(store, tmp_path):
    uri = store.put_run_manifest(
        run_id="20260706T120000Z", manifest={"totals": {"counties_failed": 0}}
    )
    path = (
        tmp_path / "runs" / "dev" / "20260706T120000Z" / "run_manifest.json"
    )
    assert path.exists()
    assert uri == str(path.resolve())
    assert json.loads(path.read_text()) == {"totals": {"counties_failed": 0}}


# ---------------------------------------------------------------- protocol


def test_local_store_satisfies_protocol():
    """LocalArtifactStore should satisfy the RawArtifactStore protocol."""
    assert isinstance(LocalArtifactStore(), RawArtifactStore)


def test_r2_store_satisfies_protocol():
    assert isinstance(R2ArtifactStore(client=object()), RawArtifactStore)


# ---------------------------------------------------------------- R2 store
#
# Exercised against a scripted fake S3 client (boto3's surface, no
# network). Error shapes duck-type botocore ClientError: an exception
# with a .response dict carrying Error.Code.


class FakeClientError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.response = {"Error": {"Code": code}}


class FakeS3Client:
    def __init__(self):
        # (bucket, key) -> {"Body": bytes, "ContentType": str, "Metadata": dict}
        self.objects: dict[tuple[str, str], dict] = {}

    def put_object(self, *, Bucket, Key, Body, ContentType=None, Metadata=None):
        self.objects[(Bucket, Key)] = {
            "Body": bytes(Body),
            "ContentType": ContentType,
            "Metadata": Metadata or {},
        }
        return {}

    def get_object(self, *, Bucket, Key):
        if (Bucket, Key) not in self.objects:
            raise FakeClientError("NoSuchKey")
        return {"Body": io.BytesIO(self.objects[(Bucket, Key)]["Body"])}

    def head_object(self, *, Bucket, Key):
        if (Bucket, Key) not in self.objects:
            raise FakeClientError("404")
        return {}

    def list_objects_v2(
        self, *, Bucket, Prefix="", Delimiter=None, MaxKeys=1000,
        ContinuationToken=None,
    ):
        keys = sorted(
            k for (b, k) in self.objects if b == Bucket and k.startswith(Prefix)
        )
        if Delimiter:
            prefixes: list[str] = []
            contents: list[str] = []
            for k in keys:
                rest = k[len(Prefix):]
                if Delimiter in rest:
                    p = Prefix + rest.split(Delimiter)[0] + Delimiter
                    if p not in prefixes:
                        prefixes.append(p)
                else:
                    contents.append(k)
            return {
                "CommonPrefixes": [{"Prefix": p} for p in prefixes],
                "Contents": [{"Key": k} for k in contents],
                "KeyCount": len(prefixes) + len(contents),
                "IsTruncated": False,
            }
        keys = keys[:MaxKeys]
        return {
            "Contents": [{"Key": k} for k in keys],
            "KeyCount": len(keys),
            "IsTruncated": False,
        }


@pytest.fixture
def s3() -> FakeS3Client:
    return FakeS3Client()


@pytest.fixture
def r2(s3) -> R2ArtifactStore:
    return R2ArtifactStore(bucket="test-bucket", env="prod", client=s3)


def test_r2_put_artifact_stores_under_env_key(r2, s3, sample_meta):
    body = b"<html>r2</html>"
    ref = r2.put_artifact(
        county="sb",
        election_date="2026-03-24",
        snapshot_id="snap1",
        filename="page.html",
        body=body,
        metadata=sample_meta,
    )

    key = "prod/sb/2026-03-24/snap1/page.html"
    assert ref.storage_uri == f"s3://test-bucket/{key}"
    assert ref.sha256 == hashlib.sha256(body).hexdigest()
    assert ref.size_bytes == len(body)
    stored = s3.objects[("test-bucket", key)]
    assert stored["Body"] == body
    assert stored["ContentType"] == "text/html"
    assert stored["Metadata"]["sha256"] == ref.sha256


def test_r2_get_artifact_round_trip(r2, sample_meta):
    ref = r2.put_artifact(
        county="sb",
        election_date="2026-03-24",
        snapshot_id="snap1",
        filename="page.html",
        body=b"roundtrip",
        metadata=sample_meta,
    )
    assert r2.get_artifact(ref) == b"roundtrip"


def test_r2_get_artifact_missing_raises(r2):
    ghost = ArtifactRef(
        county="sb",
        election_date="2026-03-24",
        snapshot_id="ghost",
        filename="missing.html",
        sha256="0" * 64,
        size_bytes=0,
        content_type="text/html",
        storage_uri="",
    )
    with pytest.raises(ArtifactNotFound):
        r2.get_artifact(ghost)


def test_r2_get_artifact_integrity_mismatch(r2, s3, sample_meta):
    ref = r2.put_artifact(
        county="sb",
        election_date="2026-03-24",
        snapshot_id="snap1",
        filename="page.html",
        body=b"original",
        metadata=sample_meta,
    )
    s3.objects[("test-bucket", "prod/sb/2026-03-24/snap1/page.html")][
        "Body"
    ] = b"tampered"

    with pytest.raises(ArtifactIntegrityError):
        r2.get_artifact(ref)


def test_r2_manifest_round_trip_and_missing(r2):
    manifest = {"schema_version": 1, "artifacts": []}
    uri = r2.put_manifest(
        county="sb",
        election_date="2026-03-24",
        snapshot_id="snap1",
        manifest=manifest,
    )
    assert uri == "s3://test-bucket/prod/sb/2026-03-24/snap1/manifest.json"
    assert (
        r2.get_manifest(
            county="sb", election_date="2026-03-24", snapshot_id="snap1"
        )
        == manifest
    )
    with pytest.raises(ArtifactNotFound):
        r2.get_manifest(
            county="sb", election_date="2026-03-24", snapshot_id="ghost"
        )


def test_r2_list_artifacts_from_manifest(r2, sample_meta):
    ref = r2.put_artifact(
        county="sb",
        election_date="2026-03-24",
        snapshot_id="snap1",
        filename="page.html",
        body=b"page",
        metadata=sample_meta,
    )
    r2.put_manifest(
        county="sb",
        election_date="2026-03-24",
        snapshot_id="snap1",
        manifest={
            "artifacts": [
                {
                    "filename": ref.filename,
                    "sha256": ref.sha256,
                    "size_bytes": ref.size_bytes,
                    "content_type": ref.content_type,
                }
            ]
        },
    )
    refs = r2.list_artifacts(
        county="sb", election_date="2026-03-24", snapshot_id="snap1"
    )
    assert len(refs) == 1
    assert refs[0].storage_uri.endswith("snap1/page.html")
    assert r2.get_artifact(refs[0]) == b"page"


def test_r2_list_snapshots_sorted(r2, sample_meta):
    for snap in ["20260102T120000Z", "20260101T120000Z"]:
        r2.put_artifact(
            county="sb",
            election_date="2026-03-24",
            snapshot_id=snap,
            filename="page.html",
            body=b"x",
            metadata=sample_meta,
        )
    assert r2.list_snapshots(county="sb", election_date="2026-03-24") == [
        "20260101T120000Z",
        "20260102T120000Z",
    ]
    assert r2.list_snapshots(county="sb", election_date="2099-01-01") == []


def test_r2_exists_snapshot_and_artifact(r2, sample_meta):
    r2.put_artifact(
        county="sb",
        election_date="2026-03-24",
        snapshot_id="snap1",
        filename="page.html",
        body=b"x",
        metadata=sample_meta,
    )
    assert r2.exists(
        county="sb", election_date="2026-03-24", snapshot_id="snap1"
    )
    assert r2.exists(
        county="sb",
        election_date="2026-03-24",
        snapshot_id="snap1",
        filename="page.html",
    )
    assert not r2.exists(
        county="sb",
        election_date="2026-03-24",
        snapshot_id="snap1",
        filename="ghost.html",
    )
    assert not r2.exists(
        county="sb", election_date="2026-03-24", snapshot_id="ghost"
    )


def test_r2_env_prefixes_are_isolated(s3, sample_meta):
    dev = R2ArtifactStore(bucket="test-bucket", env="dev", client=s3)
    prod = R2ArtifactStore(bucket="test-bucket", env="prod", client=s3)

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


def test_r2_put_run_manifest_key_layout(r2, s3):
    uri = r2.put_run_manifest(
        run_id="20260706T120000Z", manifest={"totals": {}}
    )
    key = "runs/prod/20260706T120000Z/run_manifest.json"
    assert uri == f"s3://test-bucket/{key}"
    assert json.loads(s3.objects[("test-bucket", key)]["Body"]) == {
        "totals": {}
    }
