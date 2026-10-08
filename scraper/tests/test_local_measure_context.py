"""Reviewed local-measure type crosswalk and build-time context."""

import pytest

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
    previous = {
        "Bond Measure": "GO Bond",
        "School Bonds": "GO Bond",
        "Municipal Bonds": "GO Bond",
        "District Bonds": "GO Bond",
        "Municipal Code Amendment": "Ordinance",
        "Charter Amendment": "Charter Amendment",
        "Transactions and Use Tax Measure": "Sales Tax",
        "Transactions and Use Tax": "Sales Tax",
        "Transient Occupancy Tax": "Transient Occupancy Tax",
        "Special Parcel Tax": "Property Tax",
        "Local Transportation Improvement Program": None,
    }
    assert previous.items() <= LOCAL_MEASURE_CATEGORY_CROSSWALK.items()
    assert get_reviewed_historical_category("  bond   measure ") == "GO Bond"
    assert get_reviewed_historical_category("Local Transportation Improvement Program") is None
    assert get_reviewed_historical_category("Unreviewed type") is None


def test_new_county_types_link_auditable_prior_records_without_numeric_jurisdictions():
    current = _current('Parcel Tax Measure', county='San Mateo')
    history = _history(6, county='San Mateo', category='Property Tax', passed=4)
    for index, row in enumerate(history):
        row.update(id=100 + index, jurisdiction='1', measure_letter='A', title='School parcel tax')
    future = dict(history[0], id=999, year=2028)
    other_type = dict(history[0], id=998, category_type='GO Bond')
    assert attach_local_historical_context(history + [future, other_type, current]) == 1
    context = current['local_historical_context']
    assert context['record_ids'] == [105, 104, 103, 102, 101, 100]
    assert context['total'] == 6 and context['passed'] == 4
    assert len(context['records']) == 5
    assert all(r['jurisdiction'] == 'San Mateo County' for r in context['records'])
    assert context['through'] == 2003


def test_county_label_refresh_preserves_existing_context_and_adds_confirmed_sales_tax():
    old = [_current("Bond Measure"), _current("Transactions and Use Tax Measure")]
    new = [_current(label) for label in (
        "School Bonds", "Municipal Bonds", "District Bonds", "Transactions and Use Tax",
    )]
    history = _history(8, passed=5) + _history(6, category="Sales Tax", passed=2)
    assert attach_local_historical_context(history + old + new) == 6
    for row in new[:3]:
        assert row['local_historical_context'] == old[0]['local_historical_context']
    assert new[3]['local_historical_context'] == old[1]['local_historical_context']


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


@pytest.mark.parametrize("unknown", [None, "PassT", "1", 2])
def test_unknown_outcomes_do_not_count_as_failures_or_extend_date_range(unknown):
    current = _current()
    history = _history(5, passed=3)
    missing = {**history[0], "passed": unknown, "year": 1900, "percent_yes": 99, "pass_fail": "PassT"}
    assert attach_local_historical_context([missing, *history, current]) == 1
    assert current['local_historical_context']['total'] == 5
    assert current['local_historical_context']['passed'] == 3
    assert current['local_historical_context']['pass_rate'] == 60
    assert current['local_historical_context']['since'] == 1998
    assert missing['passed'] == unknown  # Never repair raw data in the display layer.


@pytest.mark.parametrize("known_count", [0, 4])
def test_unknown_outcomes_cannot_satisfy_minimum_sample(known_count):
    current = _current()
    current['local_historical_context'] = {'stale': True}
    missing = [{**row, 'passed': None} for row in _history(10)]
    assert attach_local_historical_context(_history(known_count) + missing + [current]) == 0
    assert 'local_historical_context' not in current


def test_decided_cohorts_produce_expected_statistics():
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
