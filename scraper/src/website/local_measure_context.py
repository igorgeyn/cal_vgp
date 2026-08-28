"""Reviewed type crosswalk for local-measure historical context.

County registrars and CEDA describe the same broad measure forms with different
vocabularies. This small crosswalk is deliberately hand-curated: it maps only
reviewed equivalents and leaves ambiguous registrar descriptions unmapped.

The display statistics are computed from active historical rows at build time,
within the current measure's county, and exclude every ``*_County_Registrar``
row so a current measure is never counted as its own precedent.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable, MutableMapping, Optional


MIN_HISTORICAL_CONTEXT_SAMPLE = 5

# Reviewed 2026-08-27 against San Bernardino CEDA history. ``None`` is an
# explicit decision not to infer a match; it is not a missing implementation.
LOCAL_MEASURE_CATEGORY_CROSSWALK: dict[str, Optional[str]] = {
    "Bond Measure": "GO Bond",
    "Municipal Code Amendment": "Ordinance",
    "Charter Amendment": "Charter Amendment",
    "Transactions and Use Tax Measure": "Sales Tax",
    "Transient Occupancy Tax": "Transient Occupancy Tax",
    "Special Parcel Tax": "Property Tax",
    "Local Transportation Improvement Program": None,
}

COUNTY_CONTEXT_LABELS = {
    "los angeles": "LA",
    "orange": "OC",
    "riverside": "Riverside",
    "san bernardino": "SB",
    "san diego": "SD",
}

_NORMALIZED_CROSSWALK = {
    " ".join(description.split()).casefold(): category
    for description, category in LOCAL_MEASURE_CATEGORY_CROSSWALK.items()
}


def get_reviewed_historical_category(description: object) -> Optional[str]:
    """Return the reviewed CEDA category for a registrar description."""
    key = " ".join(str(description or "").split()).casefold()
    return _NORMALIZED_CROSSWALK.get(key)


def _county_key(county: object) -> str:
    return " ".join(str(county or "").split()).casefold()


def _is_registrar_measure(measure: MutableMapping) -> bool:
    source = str(measure.get("data_source") or measure.get("source") or "")
    return source.casefold().endswith("_county_registrar".casefold())


def attach_local_historical_context(
    measures: Iterable[MutableMapping],
    *,
    minimum_sample: int = MIN_HISTORICAL_CONTEXT_SAMPLE,
) -> int:
    """Attach deterministic context to eligible current registrar measures.

    Returns the number of measures enriched. Percentages describe observed
    historical outcomes; they are not predictions about the current measure.
    """
    measure_list = list(measures)
    reviewed_categories = {
        category.casefold()
        for category in LOCAL_MEASURE_CATEGORY_CROSSWALK.values()
        if category
    }
    aggregates = defaultdict(lambda: {"total": 0, "passed": 0, "since": None})

    for measure in measure_list:
        if _is_registrar_measure(measure):
            continue
        county = _county_key(
            measure.get("_historical_context_county", measure.get("county"))
        )
        category = " ".join(str(measure.get("category_type") or "").split())
        if not county or category.casefold() not in reviewed_categories:
            continue
        try:
            year = int(measure.get("year"))
        except (TypeError, ValueError):
            continue

        aggregate = aggregates[(county, category.casefold())]
        aggregate["total"] += 1
        aggregate["passed"] += int(measure.get("passed") == 1)
        if aggregate["since"] is None or year < aggregate["since"]:
            aggregate["since"] = year

    attached = 0
    for measure in measure_list:
        measure.pop("local_historical_context", None)
        if measure.get("upcoming_scope") != "local" or not _is_registrar_measure(measure):
            continue
        category = get_reviewed_historical_category(measure.get("description"))
        if not category:
            continue
        county = _county_key(
            measure.get("_historical_context_county", measure.get("county"))
        )
        aggregate = aggregates.get((county, category.casefold()))
        if not aggregate or aggregate["total"] < minimum_sample:
            continue

        total = aggregate["total"]
        passed = aggregate["passed"]
        measure["local_historical_context"] = {
            "category_type": category,
            "total": total,
            "passed": passed,
            "pass_rate": round(100 * passed / total),
            "since": aggregate["since"],
            "county_label": COUNTY_CONTEXT_LABELS.get(county, measure.get("county") or "county"),
        }
        attached += 1

    for measure in measure_list:
        measure.pop("_historical_context_county", None)

    return attached
