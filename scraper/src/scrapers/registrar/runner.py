"""
Registrar pipeline runner.

Iterates the selected county scrapers, isolates per-county failures
(one county's crash never aborts the others), and emits a run-level
manifest answering "what happened in this run?" without walking the
artifact store.

Exit-code contract: nonzero if ANY county failed — a 4-of-5 partial
outage must show as a red CI run, not fail-open green (self-audit
fix to Codex round-1; see docs/plans/registrar_pipeline_infra.md).

The run manifest is written to a local directory
(scraper/data/registrar_runs/, repo-root-relative like the local
artifact store) for CI workflow-artifact upload, and mirrored into
the store under runs/{env}/{run_id}/ (best-effort — a mirror failure
logs a warning but never fails the run).

Counties run sequentially: per-domain rate limits dominate runtime
and counties are distinct domains, so parallelism buys little until
several real scrapers exist. Revisit in Phase 1+ if run times demand.

CLI entry point: scraper/scripts/run_registrar_pipeline.py.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from .base import CountyRegistrarScraper
from .noop import NoOpCountyScraper
from .storage import R2ArtifactStore, RawArtifactStore, make_store

RUNNER_VERSION = "0.1.0"
RUN_ID_FORMAT = "%Y%m%dT%H%M%SZ"

# Repo-root-relative, matching storage.DEFAULT_LOCAL_BASE convention.
DEFAULT_MANIFEST_DIR = Path("scraper/data/registrar_runs")

# All known county scrapers, keyed by slug.
REGISTRY: dict[str, type[CountyRegistrarScraper]] = {
    "noop": NoOpCountyScraper,
}

# Counties selected by --counties=enabled. Phase 1 adds real ones
# ("sb" first). "noop" stays opt-in by explicit name — it exists to
# validate wiring, not to run on every production cron.
ENABLED_COUNTIES: tuple[str, ...] = ()

log = logging.getLogger("registrar.runner")


def resolve_counties(spec: str) -> list[str]:
    """Turn the --counties value into a list of registry slugs.
    'enabled' selects ENABLED_COUNTIES; otherwise a comma-separated
    list of explicit slugs. Unknown slugs raise ValueError."""
    if spec == "enabled":
        return list(ENABLED_COUNTIES)
    names = [s.strip() for s in spec.split(",") if s.strip()]
    unknown = sorted(set(names) - set(REGISTRY))
    if unknown:
        raise ValueError(
            f"unknown counties: {', '.join(unknown)} "
            f"(known: {', '.join(sorted(REGISTRY))})"
        )
    return names


def run_pipeline(
    counties: list[str],
    *,
    store: Optional[RawArtifactStore] = None,
    env: Optional[str] = None,
    run_id: Optional[str] = None,
    manifest_dir: Path = DEFAULT_MANIFEST_DIR,
    clock: Optional[Callable[[], datetime]] = None,
) -> dict:
    """Run each county scraper with failure isolation; write and
    return the run manifest. Callers derive the process exit code
    via exit_code_for()."""
    clock = clock or (lambda: datetime.now(timezone.utc))
    env = env or os.environ.get("R2_ENV", "dev")
    store = store or make_store(env=env)
    run_id = run_id or clock().strftime(RUN_ID_FORMAT)
    started_at = clock()

    county_reports: list[dict] = []
    for county in counties:
        scraper_cls = REGISTRY[county]
        t0 = time.monotonic()
        try:
            result = scraper_cls(store, run_id=run_id, clock=clock).scrape()
        except Exception as e:
            # Isolation boundary: record and move on. The nonzero
            # exit at the end is the aggregate signal.
            log.exception("county %s failed", county)
            county_reports.append(
                {
                    "county": county,
                    "status": "failed",
                    "error": f"{type(e).__name__}: {e}",
                    "duration_seconds": round(time.monotonic() - t0, 3),
                }
            )
            continue
        log.info(
            "county %s ok: %d election(s), %d artifact(s)",
            county, result.elections_scraped, result.artifacts_written,
        )
        county_reports.append(
            {
                "county": county,
                "status": "success",
                "elections_scraped": result.elections_scraped,
                "artifacts_written": result.artifacts_written,
                "snapshots": [
                    {
                        "election_date": s.election_date,
                        "snapshot_id": s.snapshot_id,
                        "artifacts_written": s.artifacts_written,
                    }
                    for s in result.snapshots
                ],
                "duration_seconds": round(time.monotonic() - t0, 3),
            }
        )

    succeeded = sum(1 for r in county_reports if r["status"] == "success")
    manifest = {
        "schema_version": 1,
        "run_id": run_id,
        "env": env,
        # Observability for the storage-backend guard: a prod run
        # showing "local" here means something is misconfigured
        # (make_store refuses that combination in CI outright).
        "store_backend": (
            "r2" if isinstance(store, R2ArtifactStore) else "local"
        ),
        "trigger": os.environ.get("GITHUB_EVENT_NAME", "local"),
        "runner_version": RUNNER_VERSION,
        "runner_git_sha": os.environ.get("GITHUB_SHA"),
        "started_at": started_at.isoformat(),
        "finished_at": clock().isoformat(),
        "counties": county_reports,
        "totals": {
            "counties_attempted": len(county_reports),
            "counties_succeeded": succeeded,
            "counties_failed": len(county_reports) - succeeded,
        },
    }

    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = manifest_dir / f"run_manifest_{run_id}.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    log.info("run manifest written to %s", manifest_path)
    try:
        store_uri = store.put_run_manifest(run_id=run_id, manifest=manifest)
        log.info("run manifest mirrored to %s", store_uri)
    except Exception:
        # Observability artifact, not pipeline truth — a failed
        # mirror must not turn an otherwise-good run red. The local
        # copy above still reaches CI as a workflow artifact.
        log.warning("run manifest mirror to store failed", exc_info=True)
    return manifest


def exit_code_for(manifest: dict) -> int:
    """Nonzero if ANY county failed."""
    return 1 if manifest["totals"]["counties_failed"] > 0 else 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run county registrar scrapers and emit a run manifest."
    )
    parser.add_argument(
        "--counties",
        default="enabled",
        help="'enabled' for the production set, or comma-separated "
        "slugs (e.g. 'noop' for the wiring smoke test)",
    )
    parser.add_argument(
        "--env",
        default=None,
        help="store env prefix (dev/prod); defaults to $R2_ENV, then 'dev'",
    )
    parser.add_argument(
        "--manifest-dir",
        type=Path,
        default=DEFAULT_MANIFEST_DIR,
        help="where the run manifest JSON is written",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    try:
        counties = resolve_counties(args.counties)
    except ValueError as e:
        parser.error(str(e))  # exits 2

    if not counties:
        real_counties = sorted(c for c in REGISTRY if c != "noop")
        if args.counties == "enabled" and real_counties:
            # Real scrapers registered but none enabled: someone
            # forgot ENABLED_COUNTIES. A silently-green no-op cron
            # would mask it (Codex round-2).
            log.error(
                "--counties=enabled resolved to an empty set even "
                "though real scrapers are registered (%s); refusing "
                "to no-op silently",
                ", ".join(real_counties),
            )
            return 1
        log.warning(
            "no counties selected (--counties=%s resolved to an empty "
            "set); nothing to do", args.counties,
        )
        return 0

    manifest = run_pipeline(
        counties,
        env=args.env,
        manifest_dir=args.manifest_dir,
    )

    for report in manifest["counties"]:
        if report["status"] == "success":
            print(
                f"[ok]     {report['county']}: "
                f"{report['elections_scraped']} election(s), "
                f"{report['artifacts_written']} artifact(s) "
                f"in {report['duration_seconds']}s"
            )
        else:
            print(
                f"[FAILED] {report['county']}: {report['error']} "
                f"({report['duration_seconds']}s)"
            )
    totals = manifest["totals"]
    print(
        f"run {manifest['run_id']} ({manifest['env']}): "
        f"{totals['counties_succeeded']}/{totals['counties_attempted']} "
        f"counties succeeded"
    )
    return exit_code_for(manifest)
