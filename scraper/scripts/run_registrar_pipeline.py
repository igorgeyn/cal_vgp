"""
CLI entry point for the registrar pipeline.

Thin shim — the real logic lives in
src/scrapers/registrar/runner.py so it's importable and unit-tested
like the rest of the package.

Usage (from repo root; paths in the runner are repo-root-relative):

    python scraper/scripts/run_registrar_pipeline.py --counties=noop
    python scraper/scripts/run_registrar_pipeline.py --counties=enabled
"""
import sys
from pathlib import Path

# Make `src.*` importable when invoked as a script from repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.scrapers.registrar.runner import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
