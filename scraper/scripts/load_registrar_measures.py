"""Thin CLI shim for the importable registrar loader."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.scrapers.registrar.loader import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
