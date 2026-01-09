"""
Tests for data parsers
"""
import pytest
from pathlib import Path
from src.parsers.ceda import CEDAParser
from src.parsers.ncsl import NCSLParser
from src.parsers.icpsr import ICPSRParser


def test_ceda_parser_initialization():
    """Test CEDA parser can be initialized"""
    parser = CEDAParser()
    assert parser is not None


def test_ncsl_parser_initialization():
    """Test NCSL parser can be initialized"""
    data_dir = Path(__file__).parent.parent / "data"
    parser = NCSLParser(data_dir)
    assert parser is not None
    assert parser.data_dir == data_dir


def test_icpsr_parser_initialization():
    """Test ICPSR parser can be initialized"""
    data_dir = Path(__file__).parent.parent / "data"
    parser = ICPSRParser(data_dir)
    assert parser is not None
    assert parser.data_dir == data_dir


def test_ncsl_parser_file_paths():
    """Test NCSL parser checks correct file paths"""
    data_dir = Path(__file__).parent.parent / "data"
    parser = NCSLParser(data_dir)

    # Should check raw directory first
    assert parser.file_paths[0] == data_dir / 'raw' / 'ncsl_ballot_measures_2014_present.xlsx'


def test_icpsr_parser_file_paths():
    """Test ICPSR parser checks correct file paths"""
    data_dir = Path(__file__).parent.parent / "data"
    parser = ICPSRParser(data_dir)

    # Should check raw directory first
    assert parser.file_paths[0] == data_dir / 'raw' / 'ncslballotmeasures_icpsr_1902_2016.csv'


def test_icpsr_parser_find_file():
    """Test ICPSR parser can find existing file"""
    data_dir = Path(__file__).parent.parent / "data"
    parser = ICPSRParser(data_dir)

    found_file = parser.find_file()

    # If file exists, should return Path
    if found_file:
        assert isinstance(found_file, Path)
        assert found_file.exists()


def test_ncsl_parser_find_file():
    """Test NCSL parser file finding"""
    data_dir = Path(__file__).parent.parent / "data"
    parser = NCSLParser(data_dir)

    found_file = parser.find_file()

    # If file exists, should return Path; otherwise None
    if found_file:
        assert isinstance(found_file, Path)
        assert found_file.exists()
    else:
        # This is expected if file doesn't exist
        assert found_file is None


@pytest.mark.skipif(
    not (Path(__file__).parent.parent / "data" / "raw" / "ncslballotmeasures_icpsr_1902_2016.csv").exists(),
    reason="ICPSR data file not available"
)
def test_icpsr_parser_parse():
    """Test ICPSR parser can parse data"""
    data_dir = Path(__file__).parent.parent / "data"
    parser = ICPSRParser(data_dir)

    measures = parser.parse()

    # Should return a list (may be empty if no CA data)
    assert isinstance(measures, list)

    # If measures found, check structure
    if len(measures) > 0:
        measure = measures[0]
        assert isinstance(measure, dict)
        assert 'year' in measure or 'state' in measure


def test_parser_standardize_year():
    """Test that parsers handle year parsing correctly"""
    data_dir = Path(__file__).parent.parent / "data"
    icpsr_parser = ICPSRParser(data_dir)

    # Test valid years
    assert icpsr_parser._parse_year(2024) == 2024
    assert icpsr_parser._parse_year("2024") == 2024
    assert icpsr_parser._parse_year("2024.0") == 2024

    # Test invalid years
    assert icpsr_parser._parse_year(None) is None
    assert icpsr_parser._parse_year("invalid") is None
    assert icpsr_parser._parse_year(1800) is None  # Before 1900
    assert icpsr_parser._parse_year(2100) is None  # After 2030
