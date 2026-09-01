"""Shared county configuration does not require per-election code edits."""
import ast
from pathlib import Path

from src.scrapers.registrar.contracts import CapturedMeasuresPage
from src.scrapers.registrar.county_config import derive_election_type, get_county_config
from src.scrapers.registrar.sb import CapturedMeasuresPage as SbCapturedMeasuresPage
from src.scrapers.registrar.smc import CapturedMeasuresPage as SmcCapturedMeasuresPage


def test_election_type_is_derived_for_new_dates_and_marked_imputed():
    assert derive_election_type("2028-11-07") == ("general", 1)
    assert derive_election_type("2028-06-06") == ("primary", 1)
    assert derive_election_type("2027-04-13") == ("special", 1)


def test_county_configuration_owns_source_and_extractor():
    config = get_county_config("SB")
    assert config.county_name == "SAN BERNARDINO"
    assert config.data_source == "SB_County_Registrar"
    assert callable(config.extractor)
    assert callable(config.interpreter)
    assert config.lineage_overrides[("20260814T035115Z", 4)] == (
        "20260727T171800Z",
        1,
    )


def test_san_mateo_configuration_matches_existing_database_convention():
    config = get_county_config("SMC")
    assert config.county_name == "SAN MATEO"
    assert config.data_source == "SMC_County_Registrar"
    assert callable(config.extractor)
    assert callable(config.interpreter)
    assert config.origin_role_priority[0] == "analysis"


def test_county_modules_share_contract_without_importing_each_other():
    assert SbCapturedMeasuresPage is CapturedMeasuresPage
    assert SmcCapturedMeasuresPage is CapturedMeasuresPage

    registrar_dir = Path(__file__).parents[1] / "src" / "scrapers" / "registrar"
    county_modules = ("sb.py", "sb_interpretation.py", "smc.py", "smc_interpretation.py")
    forbidden = {"sb", "sb_interpretation", "smc", "smc_interpretation"}
    for filename in county_modules:
        tree = ast.parse((registrar_dir / filename).read_text(encoding="utf-8"))
        imports = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
        assert imports.isdisjoint(forbidden), f"{filename} imports {imports & forbidden}"
