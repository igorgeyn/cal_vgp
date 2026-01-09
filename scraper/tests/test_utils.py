"""
Tests for database utility functions
"""
import pytest
from src.database.utils import normalize_measure_data


def test_normalize_measure_data_basic():
    """Test basic field normalization"""
    input_data = {
        'year': 2024,
        'measure_id': 'Prop 1',
        'title': 'Test Measure',
        'state': 'CA',
        'source': 'TEST'  # Should be renamed to data_source
    }

    normalized = normalize_measure_data(input_data)

    assert 'data_source' in normalized
    assert normalized['data_source'] == 'TEST'
    assert 'source' not in normalized


def test_normalize_measure_data_measure_text():
    """Test that measure_text is renamed to title if title is missing"""
    input_data = {
        'year': 2024,
        'measure_id': 'Prop 1',
        'measure_text': 'This is the measure text',
        'state': 'CA',
        'data_source': 'TEST'
    }

    normalized = normalize_measure_data(input_data)

    assert 'title' in normalized
    assert normalized['title'] == 'This is the measure text'
    assert 'measure_text' not in normalized


def test_normalize_measure_data_keeps_existing_title():
    """Test that existing title is not overwritten by measure_text"""
    input_data = {
        'year': 2024,
        'measure_id': 'Prop 1',
        'title': 'Official Title',
        'measure_text': 'Measure Text',
        'state': 'CA',
        'data_source': 'TEST'
    }

    normalized = normalize_measure_data(input_data)

    assert normalized['title'] == 'Official Title'


def test_normalize_measure_data_removes_invalid_fields():
    """Test that invalid fields are removed"""
    input_data = {
        'year': 2024,
        'measure_id': 'Prop 1',
        'title': 'Test Measure',
        'state': 'CA',
        'data_source': 'TEST',
        'invalid_field': 'should be removed',
        'another_invalid': 123
    }

    normalized = normalize_measure_data(input_data)

    assert 'invalid_field' not in normalized
    assert 'another_invalid' not in normalized
    assert 'title' in normalized
    assert 'year' in normalized


def test_normalize_measure_data_preserves_valid_fields():
    """Test that all valid fields are preserved"""
    input_data = {
        'year': 2024,
        'measure_id': 'Prop 1',
        'title': 'Test Measure',
        'description': 'Test description',
        'state': 'CA',
        'county': 'Los Angeles',
        'data_source': 'TEST',
        'yes_votes': 1000,
        'no_votes': 500,
        'passed': 1,
        'pass_fail': 'Pass'
    }

    normalized = normalize_measure_data(input_data)

    assert normalized['year'] == 2024
    assert normalized['measure_id'] == 'Prop 1'
    assert normalized['title'] == 'Test Measure'
    assert normalized['description'] == 'Test description'
    assert normalized['state'] == 'CA'
    assert normalized['county'] == 'Los Angeles'
    assert normalized['yes_votes'] == 1000
    assert normalized['no_votes'] == 500
    assert normalized['passed'] == 1


def test_normalize_measure_data_adds_required_fields():
    """Test that required fingerprint fields are added with defaults"""
    input_data = {
        'year': 2024,
        'measure_id': 'Prop 1',
        'title': 'Test Measure',
        'state': 'CA',
        'data_source': 'TEST'
    }

    normalized = normalize_measure_data(input_data)

    assert 'fingerprint' in normalized
    assert 'measure_fingerprint' in normalized
    assert 'content_hash' in normalized


def test_normalize_measure_data_empty_input():
    """Test normalizing empty input"""
    input_data = {}
    normalized = normalize_measure_data(input_data)

    # Should at least have the default fields
    assert 'fingerprint' in normalized
    assert 'measure_fingerprint' in normalized
    assert 'content_hash' in normalized


def test_normalize_measure_data_does_not_modify_original():
    """Test that normalization doesn't modify the original dict"""
    input_data = {
        'year': 2024,
        'source': 'TEST',
        'measure_text': 'Text'
    }

    original_keys = set(input_data.keys())
    normalize_measure_data(input_data)

    # Original should be unchanged
    assert set(input_data.keys()) == original_keys
    assert 'source' in input_data
    assert 'data_source' not in input_data
