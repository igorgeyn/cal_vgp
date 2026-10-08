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
    # Reviewed against Aug 28/Sep 7 production captures: the county renamed
    # these descriptions while retaining byte-identical full-text documents.
    "School Bonds": "GO Bond",
    "Municipal Bonds": "GO Bond",
    "District Bonds": "GO Bond",
    "Municipal Code Amendment": "Ordinance",
    "Charter Amendment": "Charter Amendment",
    "Transactions and Use Tax Measure": "Sales Tax",
    "Transactions and Use Tax": "Sales Tax",
    "Transient Occupancy Tax": "Transient Occupancy Tax",
    "Special Parcel Tax": "Property Tax",
    # Reviewed against the October 8 San Mateo questions and filing packets.
    "Parcel Tax Measure": "Property Tax",
    "Transient Occupancy Tax Measure": "Transient Occupancy Tax",
    "Business License Tax Measure": "Business Tax",
    "Charter Amendment Measure": "Charter Amendment",
    "Charter Amendment Measure – Affirmation of Rights": "Charter Amendment",
    "Charter Amendment Measure – Extension to Call a Special Election or Appoint": "Charter Amendment",
    "Charter Amendment Measure – Extreme Weather Events": "Charter Amendment",
    "Charter Amendment Measure – Reapportionment of Supervisorial Districts": "Charter Amendment",
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
    cohorts = defaultdict(list)

    for measure in measure_list:
        if _is_registrar_measure(measure):
            continue
        # Unknown normalized outcomes are neither passes nor failures. Apply
        # this before the sample count and date range, not just the numerator.
        if measure.get("passed") not in (0, 1):
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

        cohorts[(county, category.casefold())].append((year, measure))

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
        try:
            election_year = int(measure.get('year'))
        except (TypeError, ValueError):
            continue
        cohort = [(year, row) for year, row in cohorts.get((county, category.casefold()), [])
                  if year < election_year]
        if len(cohort) < minimum_sample:
            continue

        total = len(cohort)
        passed = sum(row['passed'] == 1 for _, row in cohort)
        measure["local_historical_context"] = {
            "category_type": category,
            "total": total,
            "passed": passed,
            "pass_rate": round(100 * passed / total),
            "since": min(year for year, _ in cohort),
            "county_label": COUNTY_CONTEXT_LABELS.get(county, measure.get("county") or "county"),
        }
        # Link only stable, public record IDs. The complete ID list permits an
        # audit of the statistic; the UI offers the five most recent records.
        linkable = [(year, row) for year, row in cohort if type(row.get('id')) is int and row['id'] > 0]
        if len(linkable) == total and len({row['id'] for _, row in linkable}) == total:
            linkable.sort(key=lambda item: (-item[0], item[1]['id']))
            measure['local_historical_context'].update(
                through=max(year for year, _ in cohort),
                record_ids=[row['id'] for _, row in linkable],
                records=[dict(id=row['id'], year=year, jurisdiction=(str(row['jurisdiction']) if row.get('jurisdiction') and not str(row['jurisdiction']).strip().isdigit() else str(row.get('county') or '') + ' County'),
                              title=row.get('title') or '',
                              designation=('Measure ' + str(row['measure_letter'])) if row.get('measure_letter') else (row.get('title') or 'Ballot measure'),
                              passed=row['passed']) for year, row in linkable[:5]],
            )
        attached += 1

    for measure in measure_list:
        measure.pop("_historical_context_county", None)

    return attached
