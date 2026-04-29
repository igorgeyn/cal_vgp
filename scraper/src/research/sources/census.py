"""
Census/ACS demographics source — provides total households, population, and
median household income per CA county and statewide.

Used by the briefing pipeline to give the LLM the inputs needed to translate
fiscal figures into per-household terms (e.g. "$24M annually" -> "$40/household/year"),
which the briefing spec lists as a SHOULD field when this data is available.

Data is loaded once at module import from scraper/data/ca_county_demographics.json,
which is produced by scripts/ingest_ca_census.py. Re-run the ingest script when
ACS publishes a new release.
"""
import json
import logging
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent.parent.parent / "data"
DEMOGRAPHICS_PATH = DATA_DIR / "ca_county_demographics.json"

_DATA = None


def _load() -> Optional[Dict]:
    global _DATA
    if _DATA is not None:
        return _DATA
    if not DEMOGRAPHICS_PATH.exists():
        logger.warning(
            "Demographics file not found at %s. Run scripts/ingest_ca_census.py.",
            DEMOGRAPHICS_PATH,
        )
        _DATA = {}
        return _DATA
    try:
        _DATA = json.loads(DEMOGRAPHICS_PATH.read_text())
    except Exception as e:
        logger.warning("Failed to load demographics: %s", e)
        _DATA = {}
    return _DATA


def get_county_demographics(county_name: str) -> Optional[Dict]:
    """Look up demographics by county name. Case-insensitive; tolerates
    'Alameda', 'ALAMEDA', 'Alameda County', etc."""
    if not county_name:
        return None
    data = _load()
    if not data:
        return None
    key = county_name.strip().upper()
    if key.endswith(' COUNTY'):
        key = key[:-len(' COUNTY')]
    return (data.get('counties') or {}).get(key)


def get_statewide_demographics() -> Optional[Dict]:
    data = _load()
    if not data:
        return None
    return data.get('statewide')


def get_demographics_for_measure(measure: Dict) -> Optional[Dict]:
    """Return the right demographic record for a measure based on jurisdiction.

    Statewide measure -> statewide record.
    County measure -> county record (if found).
    Returns dict with: scope, name, households, population, median_income.
    Returns None when no match.
    """
    county = (measure.get('county') or '').strip()
    if not county:
        return None

    if county.lower() == 'statewide':
        sw = get_statewide_demographics()
        if not sw:
            return None
        return {
            'scope': 'statewide',
            'name': sw.get('name', 'California'),
            'households': sw.get('households'),
            'population': sw.get('population'),
            'median_household_income': sw.get('median_household_income'),
        }

    rec = get_county_demographics(county)
    if not rec:
        return None
    return {
        'scope': 'county',
        'name': rec.get('name', county),
        'households': rec.get('households'),
        'population': rec.get('population'),
        'median_household_income': rec.get('median_household_income'),
    }


def format_demographics_for_prompt(demographics: Dict) -> str:
    """Render demographics as an LLM-facing block including a per-household
    translation example, so the model knows exactly how to use the numbers."""
    if not demographics:
        return ""

    name = demographics.get('name', 'this jurisdiction')
    households = demographics.get('households')
    population = demographics.get('population')
    median_income = demographics.get('median_household_income')
    scope = demographics.get('scope', 'jurisdiction')

    lines = [f"Jurisdiction: {name} ({scope}-level)"]
    if households:
        lines.append(f"- Households: {households:,}")
    if population:
        lines.append(f"- Residents: {population:,}")
    if median_income:
        lines.append(f"- Median household income: ${median_income:,}")

    if households and households > 0:
        # Concrete example anchored to this jurisdiction's actual household count
        example_amount = 10_000_000
        per_hh = example_amount / households
        lines.append(
            f"- Use these to translate fiscal figures into per-household terms. "
            f"Example: a measure raising ${example_amount:,}/year "
            f"= ${per_hh:.2f}/household/year in {name}."
        )

    return "\n".join(lines)
