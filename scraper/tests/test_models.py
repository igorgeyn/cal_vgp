"""
Tests for BallotMeasure data model
"""
import pytest
from datetime import datetime
from src.database.models import BallotMeasure


def test_ballot_measure_creation():
    """Test creating a basic BallotMeasure instance"""
    measure = BallotMeasure(
        year=2024,
        measure_id="Prop 1",
        title="Test Measure",
        state="CA",
        data_source="TEST"
    )

    assert measure.year == 2024
    assert measure.measure_id == "Prop 1"
    assert measure.title == "Test Measure"
    assert measure.state == "CA"


def test_ballot_measure_fingerprint_generation():
    """Test that fingerprints are automatically generated"""
    measure = BallotMeasure(
        year=2024,
        measure_id="Prop 1",
        title="Test Measure",
        state="CA",
        county="Los Angeles",
        data_source="TEST"
    )

    # Fingerprint should be auto-generated
    assert measure.fingerprint
    assert measure.measure_fingerprint

    # Fingerprint should be consistent for same data
    measure2 = BallotMeasure(
        year=2024,
        measure_id="Prop 1",
        title="Test Measure",
        state="CA",
        county="Los Angeles",
        data_source="TEST"
    )

    assert measure.measure_fingerprint == measure2.measure_fingerprint


def test_ballot_measure_content_hash():
    """Test that content hash is generated from title/description"""
    measure1 = BallotMeasure(
        year=2024,
        measure_id="Prop 1",
        title="Education Funding",
        description="Increases education funding",
        state="CA",
        data_source="TEST"
    )

    measure2 = BallotMeasure(
        year=2024,
        measure_id="Prop 2",  # Different ID
        title="Education Funding",  # Same title
        description="Increases education funding",  # Same description
        state="CA",
        data_source="TEST2"  # Different source
    )

    # Content hash should be the same despite different IDs/sources
    assert measure1.content_hash == measure2.content_hash


def test_ballot_measure_to_dict():
    """Test converting BallotMeasure to dictionary"""
    measure = BallotMeasure(
        year=2024,
        measure_id="Prop 1",
        title="Test Measure",
        state="CA",
        data_source="TEST",
        yes_votes=1000,
        no_votes=500
    )

    data = measure.to_dict()

    assert isinstance(data, dict)
    assert data['year'] == 2024
    assert data['measure_id'] == "Prop 1"
    assert data['yes_votes'] == 1000
    assert data['no_votes'] == 500


def test_ballot_measure_from_dict():
    """Test creating BallotMeasure from dictionary"""
    data = {
        'year': 2024,
        'measure_id': 'Prop 1',
        'title': 'Test Measure',
        'state': 'CA',
        'data_source': 'TEST'
    }

    measure = BallotMeasure.from_dict(data)

    assert measure.year == 2024
    assert measure.measure_id == "Prop 1"
    assert measure.title == "Test Measure"


def test_ballot_measure_vote_percentages():
    """Test vote percentage calculations"""
    measure = BallotMeasure(
        year=2024,
        measure_id="Prop 1",
        title="Test Measure",
        state="CA",
        data_source="TEST",
        yes_votes=600,
        no_votes=400,
        total_votes=1000,
        percent_yes=60.0,
        percent_no=40.0
    )

    assert measure.percent_yes == 60.0
    assert measure.percent_no == 40.0
    assert measure.total_votes == 1000


def test_ballot_measure_pass_fail():
    """Test pass/fail status"""
    passed_measure = BallotMeasure(
        year=2024,
        measure_id="Prop 1",
        title="Passed Measure",
        state="CA",
        data_source="TEST",
        passed=1,
        pass_fail="Pass"
    )

    failed_measure = BallotMeasure(
        year=2024,
        measure_id="Prop 2",
        title="Failed Measure",
        state="CA",
        data_source="TEST",
        passed=0,
        pass_fail="Fail"
    )

    assert passed_measure.passed == 1
    assert passed_measure.pass_fail == "Pass"
    assert failed_measure.passed == 0
    assert failed_measure.pass_fail == "Fail"


def test_ballot_measure_optional_fields():
    """Test that optional fields can be None"""
    measure = BallotMeasure(
        year=2024,
        measure_id="Prop 1",
        title="Test Measure",
        state="CA",
        data_source="TEST"
    )

    # These should be None/empty by default
    assert measure.description is None or measure.description == ""
    assert measure.yes_votes is None
    assert measure.county is None
    assert measure.pdf_url is None
