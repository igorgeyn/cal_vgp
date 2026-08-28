"""Deterministic preparation for the split upcoming-measures section."""

from src.website.generator import (
    get_local_measure_type,
    get_official_source_label,
    get_upcoming_scope,
    is_county_registrar_measure,
    prepare_upcoming_display_fields,
)


def test_upcoming_scope_splits_statewide_and_local_measures():
    assert get_upcoming_scope("2026", "Statewide") == "statewide"
    assert get_upcoming_scope(2026, None) == "statewide"
    assert get_upcoming_scope(2026, "San Bernardino") == "local"
    assert get_upcoming_scope(2024, "San Bernardino") is None
    assert get_upcoming_scope("not-a-year", "San Bernardino") is None


def test_registrar_source_is_presented_as_a_human_label():
    assert (
        get_official_source_label("SB_County_Registrar", "San Bernardino")
        == "San Bernardino County Registrar of Voters"
    )
    assert (
        get_official_source_label("LA_County_Registrar", "Los Angeles")
        == "Los Angeles County Registrar"
    )
    assert get_official_source_label("County_Elections", "Example") == "County Elections"


def test_registrar_records_are_identified_for_semantic_context_suppression():
    assert is_county_registrar_measure({"data_source": "SB_County_Registrar"})
    assert is_county_registrar_measure({"source": "LA_County_Registrar"})
    assert not is_county_registrar_measure({"data_source": "CA_SOS"})


def test_local_measure_type_prefers_classification_then_description():
    assert get_local_measure_type(
        {"display_category_type": "Bond", "description": "Bond Measure"}
    ) == "Bond"
    assert get_local_measure_type(
        {
            "display_category_type": "Other",
            "measure_type": "Measure",
            "description": "Transactions and Use Tax Measure",
        }
    ) == "Transactions and Use Tax Measure"


def test_prepared_local_fields_support_grouping_and_card_labels():
    measure = {
        "year": "2026",
        "county": "San Bernardino",
        "description": "Bond Measure",
        "measure_type": "Measure",
        "display_category_type": "Other",
        "data_source": "SB_County_Registrar",
    }

    prepared = prepare_upcoming_display_fields(measure)

    assert prepared["upcoming_scope"] == "local"
    assert prepared["upcoming_county"] == "San Bernardino"
    assert prepared["local_measure_type"] == "Bond Measure"
    assert prepared["source_display"] == "San Bernardino County Registrar of Voters"


def test_prepared_statewide_measure_does_not_gain_local_card_fields():
    prepared = prepare_upcoming_display_fields(
        {"year": 2026, "county": "Statewide", "data_source": "CA_SOS"}
    )

    assert prepared == {
        "year": 2026,
        "county": "Statewide",
        "data_source": "CA_SOS",
        "upcoming_scope": "statewide",
    }
