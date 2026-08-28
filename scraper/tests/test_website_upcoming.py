"""Deterministic preparation for the split upcoming-measures section."""

import re

from src.database.operations import Database

from src.website.generator import (
    WebsiteGenerator,
    get_compact_local_measure_type,
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


def test_compact_local_measure_type_uses_reviewed_short_labels():
    for description, expected in (
        ("Bond Measure", "Bond"),
        ("Transactions and Use Tax Measure", "Sales tax"),
        ("Municipal Code Amendment", "Municipal code"),
        ("Local Transportation Improvement Program", "Transportation"),
    ):
        assert get_compact_local_measure_type(
            {
                "display_category_type": "Other",
                "measure_type": "Measure",
                "description": description,
            }
        ) == expected


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
    assert prepared["local_measure_type_short"] == "Bond"
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


def test_compact_card_carousel_keeps_scope_accessibility_and_statewide_renderer(tmp_path):
    database = Database(tmp_path / "compact-cards.db")
    generator = WebsiteGenerator(database=database, output_path=tmp_path / "unused.html")
    script = generator._get_javascript("[]", "[]", "{}", {})
    css = generator._get_css()
    compact_renderer = script.split("function createLocalMeasureCard", 1)[1].split(
        "function handleLocalCardKey", 1
    )[0]
    normalized_script = re.sub(r"\s+", " ", script)

    assert "const LOCAL_COUNTY_ROADMAP" in script
    for county in ("San Bernardino", "Los Angeles", "Orange", "San Diego", "Riverside"):
        assert f"'{county}'" in script
    assert "County — not yet captured" in script
    assert 'class="local-carousel-track" id="localCarouselTrack"' in script
    assert 'aria-live="polite"' in script
    assert 'role="button" tabindex="0"' in compact_renderer
    assert "handleLocalCardKey" in compact_renderer
    assert "local_historical_context" in compact_renderer
    assert "% passed" in compact_renderer
    assert "Official county page" not in compact_renderer
    assert "source_display" not in compact_renderer
    assert "badge-pending" not in compact_renderer
    assert "height: 120px" in css
    assert ".upcoming-local-band .local-measure-card" in css
    assert "Currently captured:" in normalized_script
    assert "These are county-scoped official records, not a complete address-specific ballot." in normalized_script
    assert "Local coverage will appear county by county" in normalized_script

    # The statewide selection, card renderer, and carousel DOM contract stay intact.
    assert "heroMeasures.map(measure => createCard(measure, false, null, true))" in script
    assert "const isStatewide = m => m.upcoming_scope" in script
    assert "function heroCarouselPrev()" in script
    assert "function heroCarouselNext()" in script
    database.close()
