"""County-specific registrar parsing configuration.

The parser and loader consume this registry; adding an election date does not
require a code change, while adding a county requires one reviewed adapter entry.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Callable

from .sb import CapturedMeasuresPage, extract_measures_page
from .sb_interpretation import MeasuresPage, interpret_measures_page


@dataclass(frozen=True)
class RegistrarCountyConfig:
    slug: str
    county_name: str
    data_source: str
    extractor: Callable[[bytes, str], CapturedMeasuresPage]
    interpreter: Callable[[CapturedMeasuresPage], MeasuresPage]
    lineage_overrides: dict[tuple[str, int], tuple[str, int]] = field(default_factory=dict)


COUNTY_CONFIGS = {
    "sb": RegistrarCountyConfig(
        slug="sb",
        county_name="SAN BERNARDINO",
        data_source="SB_County_Registrar",
        extractor=extract_measures_page,
        interpreter=interpret_measures_page,
        lineage_overrides={
            # Reviewed fixture fact: the county changed "School Bonds" to
            # "Bond Measure" while assigning B and publishing first documents.
            # No automatic weak-key rule is allowed to make this decision.
            ("20260814T034259Z", 4): ("20260727T170014Z", 1),
        },
    ),
}


def get_county_config(slug: str) -> RegistrarCountyConfig:
    try:
        return COUNTY_CONFIGS[slug.lower()]
    except KeyError as exc:
        raise ValueError(f"unsupported registrar county {slug!r}") from exc


def derive_election_type(election_date: str) -> tuple[str, int]:
    """Return a deterministic type and mark it as date-derived/imputed."""
    try:
        parsed = date.fromisoformat(election_date)
    except ValueError as exc:
        raise ValueError(f"invalid ISO election date {election_date!r}") from exc
    if parsed.month == 11:
        return "general", 1
    if parsed.month in {3, 6}:
        return "primary", 1
    return "special", 1
