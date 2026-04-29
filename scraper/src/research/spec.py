"""
Briefing spec loader.

The spec defines the editorial standard for every research briefing — what
sections must appear, what voice they use, what counts as a failure.

Lives at the repo root in `plans/briefing-spec.md` (gitignored). The pipeline
loads it on startup and injects its text into the LLM synthesis prompt as
governing guidance. Each generated briefing records the spec version and
hash so stale briefings can be identified and regenerated.
"""
import hashlib
import logging
import os
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# scraper/src/research/spec.py -> repo root is four parents up
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DEFAULT_SPEC_PATH = REPO_ROOT / "plans" / "briefing-spec.md"


def load_briefing_spec(
    path: Optional[Path] = None,
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Load the governing briefing spec.

    Resolution order:
        1. `path` argument if provided
        2. BRIEFING_SPEC_PATH environment variable
        3. plans/briefing-spec.md at the repo root

    Returns (spec_text, spec_version, spec_hash). When the file is missing,
    returns (None, None, None) and logs a loud warning. Callers are expected
    to proceed with embedded fallback guidance and stamp the resulting
    briefings with spec_version='missing'.
    """
    if path is not None:
        spec_path = Path(path)
    else:
        env_path = os.environ.get("BRIEFING_SPEC_PATH")
        spec_path = Path(env_path) if env_path else DEFAULT_SPEC_PATH

    if not spec_path.exists():
        logger.warning(
            "Briefing spec not found at %s. Proceeding without governing spec; "
            "generated briefings will be stamped spec_version='missing' and "
            "should be regenerated when the spec is available. Set "
            "BRIEFING_SPEC_PATH or place the spec at the default location.",
            spec_path,
        )
        return None, None, None

    text = spec_path.read_text(encoding="utf-8")
    spec_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
    spec_version = _parse_spec_version(text)

    logger.info(
        "Loaded briefing spec v%s (hash %s) from %s",
        spec_version,
        spec_hash,
        spec_path,
    )
    return text, spec_version, spec_hash


def _parse_spec_version(text: str) -> str:
    """Extract spec_version from the YAML-style frontmatter."""
    if not text.startswith("---"):
        return "unknown"
    try:
        end = text.index("---", 3)
    except ValueError:
        return "unknown"
    for line in text[3:end].splitlines():
        line = line.strip()
        if line.startswith("spec_version:"):
            return line.split(":", 1)[1].strip()
    return "unknown"
