"""
Raw artifact storage for the registrar pipeline.

Scrapers fetch HTML/PDF/JSON from county registrar sites and write
them here via the RawArtifactStore interface. Downstream parsers
read them back by (county, election_date, snapshot_id). Two
implementations:

- LocalArtifactStore: writes under scraper/data/registrar_raw/.
  Default for dev (no creds needed) and tests.
- R2ArtifactStore: writes to a Cloudflare R2 bucket via boto3
  (S3-compatible). Used in CI and production runs; selected by
  make_store() when all four R2_* env vars are set. Provisioning
  walkthrough: docs/setup/registrar_r2_setup.md.

Snapshots are immutable: each scraping run gets a fresh snapshot_id
(typically a UTC timestamp like 20260608T142200Z). Re-scrapes never
overwrite prior data; in-cycle ballot-language updates produce a
new snapshot folder under the same election_date.

Storage layout:

    {env}/{county}/{election_date}/{snapshot_id}/
        manifest.json    # per-snapshot manifest
        page.html        # primary measure-list page
        analysis.pdf     # impartial analyses
        argument-*.pdf   # arguments/rebuttals
        ...

The store is the canonical truth layer. Scrapers write here, parsers
read here, nothing else does either.

See docs/plans/registrar_pipeline_infra.md for full design rationale.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Protocol, runtime_checkable

# Type aliases for clarity in signatures
County = str          # short slug: "la", "sd", "oc", "riverside", "sb"
ElectionDate = str    # ISO 8601: "2026-06-02"
SnapshotID = str      # immutable per-run; recommended: "YYYYMMDDTHHMMSSZ"

DEFAULT_LOCAL_BASE = Path("scraper/data/registrar_raw")


class ArtifactNotFound(KeyError):
    """Raised when a requested artifact or manifest does not exist."""


class ArtifactIntegrityError(ValueError):
    """Raised when an artifact's stored SHA256 disagrees with its
    actual content. Indicates corruption, tampering, or a stale
    ArtifactRef pointing at a regenerated artifact."""


@dataclass(frozen=True)
class ArtifactMetadata:
    """Caller-provided metadata that travels with an artifact PUT.

    The store fills in SHA256, size, and storage-side timestamps
    itself; this dataclass carries HTTP-response info the scraper
    knows but the store can't derive on its own."""
    source_url: str
    content_type: str
    http_status: int
    final_url: Optional[str] = None       # after redirects
    etag: Optional[str] = None
    last_modified: Optional[str] = None   # from response header
    fetch_mode: str = "requests"          # "requests" or "playwright"


@dataclass(frozen=True)
class ArtifactRef:
    """Returned from put_artifact. Identifies and locates a stored
    artifact; safe to pass around as a 'I have this artifact' handle
    that downstream code can dereference via get_artifact()."""
    county: County
    election_date: ElectionDate
    snapshot_id: SnapshotID
    filename: str               # e.g. "page.html", "analysis.pdf"
    sha256: str
    size_bytes: int
    content_type: str
    storage_uri: str            # absolute fs path (Local) or
                                # s3://bucket/key (R2)


@runtime_checkable
class RawArtifactStore(Protocol):
    """Abstract storage for raw registrar-site artifacts.

    The canonical truth layer of the pipeline. The interface is
    intentionally narrow — eight methods covering put, get, list,
    and exists for both artifacts and the per-snapshot manifest.
    """

    def put_artifact(
        self,
        *,
        county: County,
        election_date: ElectionDate,
        snapshot_id: SnapshotID,
        filename: str,
        body: bytes,
        metadata: ArtifactMetadata,
    ) -> ArtifactRef:
        """Write one artifact. Returns an ArtifactRef with the
        store-computed sha256, size, and storage URI."""
        ...

    def put_manifest(
        self,
        *,
        county: County,
        election_date: ElectionDate,
        snapshot_id: SnapshotID,
        manifest: dict,
    ) -> str:
        """Write the per-snapshot manifest. Returns its storage URI.
        Scraper is responsible for building the manifest dict;
        store does not enforce its schema."""
        ...

    def put_run_manifest(self, *, run_id: str, manifest: dict) -> str:
        """Write the run-level manifest under
        runs/{env}/{run_id}/run_manifest.json (a namespace separate
        from the per-county snapshot tree). Returns its storage URI.
        The runner also keeps a local copy for CI artifact upload;
        this is the durable mirror."""
        ...

    def get_artifact(self, ref: ArtifactRef) -> bytes:
        """Read an artifact by ref. Verifies the stored content's
        SHA256 against ref.sha256; raises ArtifactIntegrityError on
        mismatch and ArtifactNotFound if missing."""
        ...

    def get_manifest(
        self,
        *,
        county: County,
        election_date: ElectionDate,
        snapshot_id: SnapshotID,
    ) -> dict:
        """Read and return the per-snapshot manifest dict.
        Raises ArtifactNotFound if missing."""
        ...

    def list_artifacts(
        self,
        *,
        county: County,
        election_date: ElectionDate,
        snapshot_id: SnapshotID,
    ) -> list[ArtifactRef]:
        """List artifacts in a snapshot, derived from the manifest
        (canonical source — store does not walk the filesystem)."""
        ...

    def list_snapshots(
        self,
        *,
        county: County,
        election_date: ElectionDate,
    ) -> list[SnapshotID]:
        """List snapshot IDs for a (county, election_date), sorted
        ascending. Returns empty list if no snapshots exist."""
        ...

    def exists(
        self,
        *,
        county: County,
        election_date: ElectionDate,
        snapshot_id: SnapshotID,
        filename: Optional[str] = None,
    ) -> bool:
        """Cheap existence check. With filename, checks for that
        specific artifact; without, checks whether the snapshot
        exists at all. Used for idempotency in re-scrapes."""
        ...


class LocalArtifactStore:
    """Filesystem-backed RawArtifactStore.

    Default for dev + tests; no cloud credentials required.

    Layout:
        {base_dir}/{env}/{county}/{election_date}/{snapshot_id}/
            manifest.json
            page.html
            analysis.pdf
            ...
    """

    def __init__(
        self,
        base_dir: Path | str = DEFAULT_LOCAL_BASE,
        env: str = "dev",
    ):
        self._base = Path(base_dir)
        self._env = env

    def _snap_dir(
        self,
        county: County,
        election_date: ElectionDate,
        snapshot_id: SnapshotID,
    ) -> Path:
        return self._base / self._env / county / election_date / snapshot_id

    def put_artifact(
        self,
        *,
        county: County,
        election_date: ElectionDate,
        snapshot_id: SnapshotID,
        filename: str,
        body: bytes,
        metadata: ArtifactMetadata,
    ) -> ArtifactRef:
        d = self._snap_dir(county, election_date, snapshot_id)
        d.mkdir(parents=True, exist_ok=True)
        path = d / filename
        path.write_bytes(body)
        return ArtifactRef(
            county=county,
            election_date=election_date,
            snapshot_id=snapshot_id,
            filename=filename,
            sha256=hashlib.sha256(body).hexdigest(),
            size_bytes=len(body),
            content_type=metadata.content_type,
            storage_uri=str(path.resolve()),
        )

    def put_manifest(
        self,
        *,
        county: County,
        election_date: ElectionDate,
        snapshot_id: SnapshotID,
        manifest: dict,
    ) -> str:
        d = self._snap_dir(county, election_date, snapshot_id)
        d.mkdir(parents=True, exist_ok=True)
        path = d / "manifest.json"
        path.write_text(json.dumps(manifest, indent=2))
        return str(path.resolve())

    def put_run_manifest(self, *, run_id: str, manifest: dict) -> str:
        # runs/ sits beside the {env}/ snapshot tree, mirroring the
        # bucket layout (county slugs never collide with "runs").
        d = self._base / "runs" / self._env / run_id
        d.mkdir(parents=True, exist_ok=True)
        path = d / "run_manifest.json"
        path.write_text(json.dumps(manifest, indent=2))
        return str(path.resolve())

    def get_artifact(self, ref: ArtifactRef) -> bytes:
        path = (
            self._snap_dir(ref.county, ref.election_date, ref.snapshot_id)
            / ref.filename
        )
        if not path.exists():
            raise ArtifactNotFound(
                f"artifact not found: "
                f"{ref.county}/{ref.election_date}/{ref.snapshot_id}/{ref.filename}"
            )
        body = path.read_bytes()
        actual = hashlib.sha256(body).hexdigest()
        if actual != ref.sha256:
            raise ArtifactIntegrityError(
                f"sha256 mismatch for {path}: "
                f"expected {ref.sha256}, got {actual}"
            )
        return body

    def get_manifest(
        self,
        *,
        county: County,
        election_date: ElectionDate,
        snapshot_id: SnapshotID,
    ) -> dict:
        path = self._snap_dir(county, election_date, snapshot_id) / "manifest.json"
        if not path.exists():
            raise ArtifactNotFound(
                f"manifest not found: {county}/{election_date}/{snapshot_id}/manifest.json"
            )
        return json.loads(path.read_text())

    def list_artifacts(
        self,
        *,
        county: County,
        election_date: ElectionDate,
        snapshot_id: SnapshotID,
    ) -> list[ArtifactRef]:
        manifest = self.get_manifest(
            county=county,
            election_date=election_date,
            snapshot_id=snapshot_id,
        )
        d = self._snap_dir(county, election_date, snapshot_id)
        refs: list[ArtifactRef] = []
        for entry in manifest.get("artifacts", []):
            refs.append(
                ArtifactRef(
                    county=county,
                    election_date=election_date,
                    snapshot_id=snapshot_id,
                    filename=entry["filename"],
                    sha256=entry["sha256"],
                    size_bytes=entry["size_bytes"],
                    content_type=entry.get("content_type", ""),
                    storage_uri=str((d / entry["filename"]).resolve()),
                )
            )
        return refs

    def list_snapshots(
        self,
        *,
        county: County,
        election_date: ElectionDate,
    ) -> list[SnapshotID]:
        d = self._base / self._env / county / election_date
        if not d.is_dir():
            return []
        return sorted(p.name for p in d.iterdir() if p.is_dir())

    def exists(
        self,
        *,
        county: County,
        election_date: ElectionDate,
        snapshot_id: SnapshotID,
        filename: Optional[str] = None,
    ) -> bool:
        d = self._snap_dir(county, election_date, snapshot_id)
        if filename is None:
            return d.is_dir()
        return (d / filename).is_file()


# Object keys that S3 reports as missing, across get/head variants.
_S3_NOT_FOUND_CODES = {"NoSuchKey", "404", "NotFound"}


def _s3_error_code(exc: BaseException) -> str:
    """Extract the S3 error code from a botocore ClientError without
    importing botocore (duck-typed so tests can use stub errors)."""
    response = getattr(exc, "response", None)
    if isinstance(response, dict):
        return response.get("Error", {}).get("Code", "")
    return ""


class R2ArtifactStore:
    """Cloudflare R2-backed RawArtifactStore (S3-compatible, boto3).

    Config from env vars unless passed explicitly:
        R2_ACCESS_KEY_ID / R2_SECRET_ACCESS_KEY / R2_ENDPOINT_URL
        R2_BUCKET (default: cal-vgp-registrar-raw)
        R2_ENV    (dev/prod key prefix; default "dev")

    boto3 is imported lazily on first request so this module stays
    importable without it; tests inject a fake `client`.

    Key layout mirrors LocalArtifactStore:
        {env}/{county}/{election_date}/{snapshot_id}/{filename}
        runs/{env}/{run_id}/run_manifest.json
    """

    def __init__(
        self,
        *,
        bucket: Optional[str] = None,
        endpoint_url: Optional[str] = None,
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None,
        env: Optional[str] = None,
        client=None,
    ):
        self._bucket = bucket or os.environ.get(
            "R2_BUCKET", "cal-vgp-registrar-raw"
        )
        self._endpoint_url = endpoint_url or os.environ.get("R2_ENDPOINT_URL")
        self._access_key_id = access_key_id or os.environ.get(
            "R2_ACCESS_KEY_ID"
        )
        self._secret_access_key = secret_access_key or os.environ.get(
            "R2_SECRET_ACCESS_KEY"
        )
        self._env = env or os.environ.get("R2_ENV", "dev")
        self._client = client

    @property
    def client(self):
        if self._client is None:
            import boto3  # lazy: only real R2 use needs it

            self._client = boto3.client(
                "s3",
                endpoint_url=self._endpoint_url,
                aws_access_key_id=self._access_key_id,
                aws_secret_access_key=self._secret_access_key,
                region_name="auto",  # R2 convention
            )
        return self._client

    def _key(
        self,
        county: County,
        election_date: ElectionDate,
        snapshot_id: SnapshotID,
        filename: str,
    ) -> str:
        return f"{self._env}/{county}/{election_date}/{snapshot_id}/{filename}"

    def _uri(self, key: str) -> str:
        return f"s3://{self._bucket}/{key}"

    def put_artifact(
        self,
        *,
        county: County,
        election_date: ElectionDate,
        snapshot_id: SnapshotID,
        filename: str,
        body: bytes,
        metadata: ArtifactMetadata,
    ) -> ArtifactRef:
        key = self._key(county, election_date, snapshot_id, filename)
        sha256 = hashlib.sha256(body).hexdigest()
        self.client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=body,
            ContentType=metadata.content_type or "application/octet-stream",
            Metadata={"sha256": sha256},
        )
        return ArtifactRef(
            county=county,
            election_date=election_date,
            snapshot_id=snapshot_id,
            filename=filename,
            sha256=sha256,
            size_bytes=len(body),
            content_type=metadata.content_type,
            storage_uri=self._uri(key),
        )

    def put_manifest(
        self,
        *,
        county: County,
        election_date: ElectionDate,
        snapshot_id: SnapshotID,
        manifest: dict,
    ) -> str:
        key = self._key(county, election_date, snapshot_id, "manifest.json")
        self.client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=json.dumps(manifest, indent=2).encode("utf-8"),
            ContentType="application/json",
        )
        return self._uri(key)

    def put_run_manifest(self, *, run_id: str, manifest: dict) -> str:
        key = f"runs/{self._env}/{run_id}/run_manifest.json"
        self.client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=json.dumps(manifest, indent=2).encode("utf-8"),
            ContentType="application/json",
        )
        return self._uri(key)

    def _get_object_bytes(self, key: str, describe: str) -> bytes:
        try:
            resp = self.client.get_object(Bucket=self._bucket, Key=key)
        except Exception as e:
            if _s3_error_code(e) in _S3_NOT_FOUND_CODES:
                raise ArtifactNotFound(f"{describe}: {key}") from e
            raise
        return resp["Body"].read()

    def get_artifact(self, ref: ArtifactRef) -> bytes:
        key = self._key(
            ref.county, ref.election_date, ref.snapshot_id, ref.filename
        )
        body = self._get_object_bytes(key, "artifact not found")
        actual = hashlib.sha256(body).hexdigest()
        if actual != ref.sha256:
            raise ArtifactIntegrityError(
                f"sha256 mismatch for {self._uri(key)}: "
                f"expected {ref.sha256}, got {actual}"
            )
        return body

    def get_manifest(
        self,
        *,
        county: County,
        election_date: ElectionDate,
        snapshot_id: SnapshotID,
    ) -> dict:
        key = self._key(county, election_date, snapshot_id, "manifest.json")
        return json.loads(self._get_object_bytes(key, "manifest not found"))

    def list_artifacts(
        self,
        *,
        county: County,
        election_date: ElectionDate,
        snapshot_id: SnapshotID,
    ) -> list[ArtifactRef]:
        manifest = self.get_manifest(
            county=county,
            election_date=election_date,
            snapshot_id=snapshot_id,
        )
        refs: list[ArtifactRef] = []
        for entry in manifest.get("artifacts", []):
            key = self._key(
                county, election_date, snapshot_id, entry["filename"]
            )
            refs.append(
                ArtifactRef(
                    county=county,
                    election_date=election_date,
                    snapshot_id=snapshot_id,
                    filename=entry["filename"],
                    sha256=entry["sha256"],
                    size_bytes=entry["size_bytes"],
                    content_type=entry.get("content_type", ""),
                    storage_uri=self._uri(key),
                )
            )
        return refs

    def list_snapshots(
        self,
        *,
        county: County,
        election_date: ElectionDate,
    ) -> list[SnapshotID]:
        prefix = f"{self._env}/{county}/{election_date}/"
        snapshot_ids: list[str] = []
        token: Optional[str] = None
        while True:
            kwargs: dict = {
                "Bucket": self._bucket,
                "Prefix": prefix,
                "Delimiter": "/",
            }
            if token:
                kwargs["ContinuationToken"] = token
            resp = self.client.list_objects_v2(**kwargs)
            for cp in resp.get("CommonPrefixes", []):
                snapshot_ids.append(cp["Prefix"][len(prefix):].rstrip("/"))
            if not resp.get("IsTruncated"):
                break
            token = resp.get("NextContinuationToken")
        return sorted(snapshot_ids)

    def exists(
        self,
        *,
        county: County,
        election_date: ElectionDate,
        snapshot_id: SnapshotID,
        filename: Optional[str] = None,
    ) -> bool:
        if filename is None:
            prefix = f"{self._env}/{county}/{election_date}/{snapshot_id}/"
            resp = self.client.list_objects_v2(
                Bucket=self._bucket, Prefix=prefix, MaxKeys=1
            )
            return resp.get("KeyCount", 0) > 0
        try:
            self.client.head_object(
                Bucket=self._bucket,
                Key=self._key(county, election_date, snapshot_id, filename),
            )
        except Exception as e:
            if _s3_error_code(e) in _S3_NOT_FOUND_CODES:
                return False
            raise
        return True


_R2_ENV_KEYS = (
    "R2_ACCESS_KEY_ID",
    "R2_SECRET_ACCESS_KEY",
    "R2_ENDPOINT_URL",
    "R2_BUCKET",
)


def make_store(*, env: Optional[str] = None) -> RawArtifactStore:
    """Factory. Picks a backend based on env vars.

    - All four R2_* vars set → R2ArtifactStore (CI/prod).
    - Otherwise → LocalArtifactStore (dev, tests).

    `env` override defaults to R2_ENV env var, then "dev". Used to
    pin the dev/prod prefix without needing to touch the env vars
    themselves (e.g. in tests).
    """
    resolved_env = env or os.environ.get("R2_ENV", "dev")

    if all(os.environ.get(k) for k in _R2_ENV_KEYS):
        return R2ArtifactStore(env=resolved_env)

    return LocalArtifactStore(env=resolved_env)
