"""Shared county configuration does not require per-election code edits."""
from src.scrapers.registrar.county_config import derive_election_type, get_county_config


def test_election_type_is_derived_for_new_dates_and_marked_imputed():
    assert derive_election_type("2028-11-07") == ("general", 1)
    assert derive_election_type("2028-06-06") == ("primary", 1)
    assert derive_election_type("2027-04-13") == ("special", 1)


def test_county_configuration_owns_source_and_extractor():
    config = get_county_config("SB")
    assert config.county_name == "SAN BERNARDINO"
    assert config.data_source == "SB_County_Registrar"
    assert callable(config.extractor)
