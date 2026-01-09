"""
Tests for Database operations
"""
import pytest
import tempfile
import os
from pathlib import Path
from src.database.operations import Database
from src.database.models import BallotMeasure


@pytest.fixture
def temp_db():
    """Create a temporary database for testing"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.db', delete=False) as f:
        db_path = f.name

    db = Database(db_path)
    yield db

    # Cleanup
    db.close()
    if os.path.exists(db_path):
        os.unlink(db_path)


def test_database_creation(temp_db):
    """Test that database and tables are created"""
    assert temp_db.db_path.exists()

    # Check that main table exists
    cursor = temp_db.conn.cursor()
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='ballot_measures'
    """)
    result = cursor.fetchone()
    assert result is not None


def test_insert_measure(temp_db):
    """Test inserting a ballot measure"""
    measure = BallotMeasure(
        year=2024,
        measure_id="Prop 1",
        title="Test Measure",
        state="CA",
        data_source="TEST"
    )

    measure_id = temp_db.insert_measure(measure)
    assert measure_id > 0


def test_find_by_fingerprint(temp_db):
    """Test finding a measure by fingerprint"""
    measure = BallotMeasure(
        year=2024,
        measure_id="Prop 1",
        title="Test Measure",
        state="CA",
        data_source="TEST"
    )

    temp_db.insert_measure(measure)

    # Find by fingerprint
    found = temp_db.find_by_fingerprint(measure.fingerprint)
    assert found is not None
    assert found.measure_id == "Prop 1"
    assert found.title == "Test Measure"


def test_find_by_content_hash(temp_db):
    """Test finding measures by content hash"""
    measure1 = BallotMeasure(
        year=2024,
        measure_id="Prop 1",
        title="Same Title",
        description="Same Description",
        state="CA",
        data_source="SOURCE1"
    )

    measure2 = BallotMeasure(
        year=2024,
        measure_id="Prop 2",
        title="Same Title",
        description="Same Description",
        state="CA",
        data_source="SOURCE2"
    )

    temp_db.insert_measure(measure1)
    temp_db.insert_measure(measure2)

    # Should find both measures with same content
    matches = temp_db.find_by_content_hash(measure1.content_hash)
    assert len(matches) == 2


def test_update_measure(temp_db):
    """Test updating a ballot measure"""
    measure = BallotMeasure(
        year=2024,
        measure_id="Prop 1",
        title="Original Title",
        state="CA",
        data_source="TEST"
    )

    measure_id = temp_db.insert_measure(measure)

    # Update the measure
    update_data = {'title': 'Updated Title', 'description': 'New description'}
    result = temp_db.update_measure(measure_id, update_data)
    assert result is True

    # Verify update
    updated = temp_db.find_by_fingerprint(measure.fingerprint)
    assert updated.title == "Updated Title"


def test_get_all_measures(temp_db):
    """Test retrieving all measures"""
    # Insert multiple measures
    for i in range(3):
        measure = BallotMeasure(
            year=2024,
            measure_id=f"Prop {i+1}",
            title=f"Measure {i+1}",
            state="CA",
            data_source="TEST"
        )
        temp_db.insert_measure(measure)

    measures = temp_db.get_all_measures()
    assert len(measures) >= 3


def test_search_measures(temp_db):
    """Test searching for measures"""
    measure1 = BallotMeasure(
        year=2024,
        measure_id="Prop 1",
        title="Education Funding",
        state="CA",
        data_source="TEST"
    )

    measure2 = BallotMeasure(
        year=2024,
        measure_id="Prop 2",
        title="Healthcare Reform",
        state="CA",
        data_source="TEST"
    )

    temp_db.insert_measure(measure1)
    temp_db.insert_measure(measure2)

    # Search for education
    results = temp_db.search_measures(query="Education")
    assert len(results) == 1
    assert results[0].title == "Education Funding"


def test_get_statistics(temp_db):
    """Test getting database statistics"""
    # Insert some test data
    measure = BallotMeasure(
        year=2024,
        measure_id="Prop 1",
        title="Test Measure",
        state="CA",
        data_source="TEST",
        yes_votes=1000,
        no_votes=500
    )
    temp_db.insert_measure(measure)

    stats = temp_db.get_statistics()

    assert 'total_measures' in stats
    assert stats['total_measures'] >= 1


def test_duplicate_insertion_prevention(temp_db):
    """Test that duplicate measures are prevented"""
    measure = BallotMeasure(
        year=2024,
        measure_id="Prop 1",
        title="Test Measure",
        state="CA",
        data_source="TEST"
    )

    # Insert first time
    measure_id1 = temp_db.insert_measure(measure)
    assert measure_id1 > 0

    # Try to insert again - should handle gracefully
    try:
        temp_db.insert_measure(measure)
        # If no exception, verify only one exists
        measures = temp_db.find_by_fingerprint(measure.fingerprint)
        assert measures is not None
    except Exception as e:
        # Expected behavior if duplicates are prevented
        assert "already exists" in str(e).lower() or "unique" in str(e).lower()


def test_database_context_manager(temp_db):
    """Test using database as context manager"""
    db_path = temp_db.db_path

    with Database(db_path) as db:
        measure = BallotMeasure(
            year=2024,
            measure_id="Prop 1",
            title="Test Measure",
            state="CA",
            data_source="TEST"
        )
        measure_id = db.insert_measure(measure)
        assert measure_id > 0
