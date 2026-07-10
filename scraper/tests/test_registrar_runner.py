"""Tests for the registrar pipeline runner: county resolution,
per-county failure isolation, run-manifest emission, exit codes."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from src.scrapers.registrar import runner
from src.scrapers.registrar.base import CountyRegistrarScraper, ScrapeResult
from src.scrapers.registrar.noop import NoOpCountyScraper
from src.scrapers.registrar.runner import (
    exit_code_for,
    resolve_counties,
    run_pipeline,
)
from src.scrapers.registrar.storage import LocalArtifactStore

FIXED_NOW = datetime(2026, 7, 6, 12, 0, 0, tzinfo=timezone.utc)


class ExplodingScraper(CountyRegistrarScraper):
    """Fails mid-scrape; used to prove isolation."""

    county = "exploding"

    def scrape(self) -> ScrapeResult:
        raise RuntimeError("registrar site melted")


@pytest.fixture
def store(tmp_path) -> LocalArtifactStore:
    return LocalArtifactStore(base_dir=tmp_path / "artifacts", env="dev")


@pytest.fixture
def manifest_dir(tmp_path):
    return tmp_path / "runs"


# ---------------------------------------------------------------- resolve


def test_resolve_enabled_is_currently_empty():
    # Phase 1 flips this by adding real counties to ENABLED_COUNTIES.
    assert resolve_counties("enabled") == []


def test_resolve_explicit_names():
    assert resolve_counties("noop") == ["noop"]
    assert resolve_counties(" noop , noop ") == ["noop", "noop"]


def test_resolve_unknown_county_raises():
    with pytest.raises(ValueError, match="unknown counties: sb"):
        resolve_counties("noop,sb")


# ---------------------------------------------------------------- run


def test_run_pipeline_success_writes_manifest(store, manifest_dir):
    manifest = run_pipeline(
        ["noop"],
        store=store,
        env="dev",
        manifest_dir=manifest_dir,
        clock=lambda: FIXED_NOW,
    )

    assert manifest["schema_version"] == 1
    assert manifest["run_id"] == "20260706T120000Z"
    assert manifest["env"] == "dev"
    assert manifest["store_backend"] == "local"
    assert manifest["totals"] == {
        "counties_attempted": 1,
        "counties_succeeded": 1,
        "counties_failed": 0,
    }
    report = manifest["counties"][0]
    assert report["county"] == "noop"
    assert report["status"] == "success"
    assert report["elections_scraped"] == 1
    assert report["artifacts_written"] == 2
    assert report["snapshots"][0]["snapshot_id"] == "20260706T120000Z"

    on_disk = json.loads(
        (manifest_dir / "run_manifest_20260706T120000Z.json").read_text()
    )
    assert on_disk == manifest
    assert exit_code_for(manifest) == 0


def test_run_pipeline_isolates_failures_and_continues(
    store, manifest_dir, monkeypatch
):
    monkeypatch.setitem(runner.REGISTRY, "exploding", ExplodingScraper)

    # Failing county first — the run must still reach noop.
    manifest = run_pipeline(
        ["exploding", "noop"],
        store=store,
        env="dev",
        manifest_dir=manifest_dir,
        clock=lambda: FIXED_NOW,
    )

    assert manifest["totals"] == {
        "counties_attempted": 2,
        "counties_succeeded": 1,
        "counties_failed": 1,
    }
    failed, succeeded = manifest["counties"]
    assert failed["county"] == "exploding"
    assert failed["status"] == "failed"
    assert failed["error"] == "RuntimeError: registrar site melted"
    assert succeeded["county"] == "noop"
    assert succeeded["status"] == "success"

    # ANY failure -> nonzero (the self-audit fix; never fail-open).
    assert exit_code_for(manifest) == 1
    # Manifest still written on partial failure.
    assert (manifest_dir / "run_manifest_20260706T120000Z.json").exists()


def test_run_pipeline_all_failed_exit_nonzero(store, manifest_dir, monkeypatch):
    monkeypatch.setitem(runner.REGISTRY, "exploding", ExplodingScraper)
    manifest = run_pipeline(
        ["exploding"],
        store=store,
        env="dev",
        manifest_dir=manifest_dir,
        clock=lambda: FIXED_NOW,
    )
    assert exit_code_for(manifest) == 1


def test_run_pipeline_empty_counties_is_clean_noop(store, manifest_dir):
    manifest = run_pipeline(
        [],
        store=store,
        env="dev",
        manifest_dir=manifest_dir,
        clock=lambda: FIXED_NOW,
    )
    assert manifest["totals"]["counties_attempted"] == 0
    assert exit_code_for(manifest) == 0


def test_run_pipeline_artifacts_land_in_store(store, manifest_dir):
    manifest = run_pipeline(
        ["noop"],
        store=store,
        env="dev",
        manifest_dir=manifest_dir,
        clock=lambda: FIXED_NOW,
    )
    snap = manifest["counties"][0]["snapshots"][0]
    stored = store.get_manifest(
        county="noop",
        election_date=snap["election_date"],
        snapshot_id=snap["snapshot_id"],
    )
    # Scraper-level manifest carries the same run_id the runner minted.
    assert stored["run_id"] == manifest["run_id"]
    assert len(stored["artifacts"]) == 2


def test_run_pipeline_mirrors_run_manifest_to_store(
    store, manifest_dir, tmp_path
):
    run_pipeline(
        ["noop"],
        store=store,
        env="dev",
        manifest_dir=manifest_dir,
        clock=lambda: FIXED_NOW,
    )
    mirrored = (
        tmp_path
        / "artifacts"
        / "runs"
        / "dev"
        / "20260706T120000Z"
        / "run_manifest.json"
    )
    assert mirrored.exists()
    assert json.loads(mirrored.read_text())["run_id"] == "20260706T120000Z"


def test_run_pipeline_mirror_failure_does_not_fail_run(
    store, manifest_dir, monkeypatch
):
    def explode(**kwargs):
        raise ConnectionError("R2 is having a day")

    monkeypatch.setattr(store, "put_run_manifest", explode, raising=False)

    manifest = run_pipeline(
        ["noop"],
        store=store,
        env="dev",
        manifest_dir=manifest_dir,
        clock=lambda: FIXED_NOW,
    )
    # Run stays green; local manifest copy still written.
    assert exit_code_for(manifest) == 0
    assert (manifest_dir / "run_manifest_20260706T120000Z.json").exists()


def test_run_pipeline_trigger_and_sha_from_ci_env(
    store, manifest_dir, monkeypatch
):
    monkeypatch.setenv("GITHUB_EVENT_NAME", "schedule")
    monkeypatch.setenv("GITHUB_SHA", "abc123")
    manifest = run_pipeline(
        ["noop"],
        store=store,
        env="prod",
        manifest_dir=manifest_dir,
        clock=lambda: FIXED_NOW,
    )
    assert manifest["trigger"] == "schedule"
    assert manifest["runner_git_sha"] == "abc123"


# ---------------------------------------------------------------- cli


def test_main_smoke_noop(tmp_path, monkeypatch):
    """End-to-end through the CLI surface with the store redirected
    off the real data directory."""
    store = LocalArtifactStore(base_dir=tmp_path / "artifacts", env="dev")
    monkeypatch.setattr(runner, "make_store", lambda *, env: store)

    code = runner.main(
        ["--counties=noop", "--manifest-dir", str(tmp_path / "runs")]
    )

    assert code == 0
    manifests = list((tmp_path / "runs").glob("run_manifest_*.json"))
    assert len(manifests) == 1


def test_main_empty_selection_exits_zero(tmp_path):
    # Legitimate only while no real counties are registered.
    assert (
        runner.main(
            ["--counties=enabled", "--manifest-dir", str(tmp_path / "runs")]
        )
        == 0
    )
    # No manifest for a run that did nothing.
    assert not (tmp_path / "runs").exists()


def test_main_empty_enabled_fails_once_real_counties_exist(
    tmp_path, monkeypatch
):
    """Someone registered a real county but forgot ENABLED_COUNTIES —
    a silently-green no-op cron would mask it (Codex round-2)."""
    monkeypatch.setitem(runner.REGISTRY, "sb", ExplodingScraper)

    assert (
        runner.main(
            ["--counties=enabled", "--manifest-dir", str(tmp_path / "runs")]
        )
        == 1
    )


def test_main_unknown_county_exits_two(tmp_path):
    with pytest.raises(SystemExit) as exc_info:
        runner.main(
            ["--counties=atlantis", "--manifest-dir", str(tmp_path / "runs")]
        )
    assert exc_info.value.code == 2


def test_main_failure_exit_code(tmp_path, monkeypatch):
    store = LocalArtifactStore(base_dir=tmp_path / "artifacts", env="dev")
    monkeypatch.setattr(runner, "make_store", lambda *, env: store)
    monkeypatch.setitem(runner.REGISTRY, "exploding", ExplodingScraper)

    code = runner.main(
        ["--counties=exploding,noop", "--manifest-dir", str(tmp_path / "runs")]
    )
    assert code == 1
