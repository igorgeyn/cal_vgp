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
from .smc import extract_measures_page as extract_smc_measures_page
from .smc_interpretation import interpret_measures_page as interpret_smc_measures_page


@dataclass(frozen=True)
class RegistrarCountyConfig:
    slug: str
    county_name: str
    data_source: str
    extractor: Callable[[bytes, str], CapturedMeasuresPage]
    interpreter: Callable[[CapturedMeasuresPage], MeasuresPage]
    lineage_overrides: dict[tuple[str, int], tuple[str, int]] = field(default_factory=dict)
    origin_role_priority: tuple[str, ...] = ()


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
            # The same reviewed transition under the immutable production
            # snapshot IDs. Keep the fixture pair above for local replay tests.
            ("20260814T035115Z", 4): ("20260727T171800Z", 1),
        },
    ),
    "smc": RegistrarCountyConfig(
        slug="smc",
        county_name="SAN MATEO",
        data_source="SMC_County_Registrar",
        extractor=extract_smc_measures_page,
        interpreter=interpret_smc_measures_page,
        # Four county measures share one resolution/full-text packet. Every
        # impartial-analysis URL is measure-specific in the pinned fixture, so
        # it is the strongest collision-free identity origin for this county.
        origin_role_priority=(
            "analysis",
            "resolution",
            "text",
            "tax_rate_statement",
            "argument_for",
            "argument_against",
            "rebuttal_for",
            "rebuttal_against",
        ),
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
