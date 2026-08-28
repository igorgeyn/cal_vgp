"""Reviewed local-measure type crosswalk and build-time context."""

from src.website.local_measure_context import (
    LOCAL_MEASURE_CATEGORY_CROSSWALK,
    attach_local_historical_context,
    get_reviewed_historical_category,
)


def _history(count, *, county="San Bernardino", category="GO Bond", passed=0):
    return [
        {
            "year": 1998 + index,
            "county": county,
            "category_type": category,
            "passed": 1 if index < passed else 0,
            "data_source": "CEDA",
        }
        for index in range(count)
    ]


def _current(description="Bond Measure", *, county="San Bernardino"):
    return {
        "year": 2026,
        "county": county,
        "description": description,
        "data_source": "SB_County_Registrar",
        "upcoming_scope": "local",
    }


def test_reviewed_crosswalk_keeps_transportation_explicitly_unmapped():
    assert LOCAL_MEASURE_CATEGORY_CROSSWALK == {
        "Bond Measure": "GO Bond",
        "Municipal Code Amendment": "Ordinance",
        "Charter Amendment": "Charter Amendment",
        "Transactions and Use Tax Measure": "Sales Tax",
        "Transient Occupancy Tax": "Transient Occupancy Tax",
        "Special Parcel Tax": "Property Tax",
        "Local Transportation Improvement Program": None,
    }
    assert get_reviewed_historical_category("  bond   measure ") == "GO Bond"
    assert get_reviewed_historical_category("Local Transportation Improvement Program") is None
    assert get_reviewed_historical_category("Unreviewed type") is None


def test_context_is_county_scoped_and_excludes_registrar_rows():
    current = _current()
    measures = _history(5, passed=3) + _history(
        7, county="Los Angeles", passed=7
    ) + [
        {
            "year": 2025,
            "county": "San Bernardino",
            "category_type": "GO Bond",
            "passed": 1,
            "data_source": "SB_County_Registrar",
        },
        current,
    ]

    assert attach_local_historical_context(measures) == 1
    assert current["local_historical_context"] == {
        "category_type": "GO Bond",
        "total": 5,
        "passed": 3,
        "pass_rate": 60,
        "since": 1998,
        "county_label": "SB",
    }


def test_context_uses_source_exact_county_key_before_display_correction():
    current = _current()
    current["_historical_context_county"] = "SAN BERNARDINO"
    corrected_typo_rows = _history(2, passed=2)
    for row in corrected_typo_rows:
        row["_historical_context_county"] = "SAN BERNADINO"
    measures = _history(5, passed=3) + corrected_typo_rows + [current]

    assert attach_local_historical_context(measures) == 1
    assert current["local_historical_context"]["total"] == 5
    assert current["local_historical_context"]["passed"] == 3
    assert "_historical_context_county" not in current
    assert all("_historical_context_county" not in row for row in corrected_typo_rows)


def test_context_is_suppressed_below_five_and_for_unmapped_type():
    small_sample = _current()
    unmapped = _current("Local Transportation Improvement Program")
    measures = _history(4, passed=4) + [small_sample, unmapped]

    assert attach_local_historical_context(measures) == 0
    assert "local_historical_context" not in small_sample
    assert "local_historical_context" not in unmapped


def test_all_reviewed_cohorts_produce_the_verified_card_statistics():
    cohorts = {
        "Bond Measure": ("GO Bond", 90, 60, 1998, 67),
        "Municipal Code Amendment": ("Ordinance", 71, 40, 1998, 56),
        "Charter Amendment": ("Charter Amendment", 38, 28, 1998, 74),
        "Transactions and Use Tax Measure": ("Sales Tax", 31, 17, 2000, 55),
        "Transient Occupancy Tax": ("Transient Occupancy Tax", 16, 12, 2002, 75),
        "Special Parcel Tax": ("Property Tax", 16, 3, 1998, 19),
    }
    measures = []
    current = {}
    for description, (category, total, passed, since, _) in cohorts.items():
        measures.extend(
            {
                "year": since,
                "county": "San Bernardino",
                "category_type": category,
                "passed": 1 if index < passed else 0,
                "data_source": "CEDA",
            }
            for index in range(total)
        )
        current[description] = _current(description)
        measures.append(current[description])

    assert attach_local_historical_context(measures) == len(cohorts)
    for description, (category, total, passed, since, pass_rate) in cohorts.items():
        assert current[description]["local_historical_context"] == {
            "category_type": category,
            "total": total,
            "passed": passed,
            "pass_rate": pass_rate,
            "since": since,
            "county_label": "SB",
        }
