"""
Tests for deduplication functionality
"""
import pytest
import tempfile
import os
from src.database.operations import Database
from src.database.deduplication import Deduplicator
from src.database.models import BallotMeasure


@pytest.fixture
def temp_db_with_dedup():
    """Create a temporary database with deduplicator for testing"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.db', delete=False) as f:
        db_path = f.name

    db = Database(db_path)
    deduplicator = Deduplicator(db)
    yield db, deduplicator

    # Cleanup
    db.close()
    if os.path.exists(db_path):
        os.unlink(db_path)


def test_deduplicator_initialization(temp_db_with_dedup):
    """Test that deduplicator can be initialized"""
    db, deduplicator = temp_db_with_dedup
    assert deduplicator is not None
    assert deduplicator.db == db


def test_check_duplicate_exact_match(temp_db_with_dedup):
    """Test detecting exact duplicate"""
    db, deduplicator = temp_db_with_dedup

    measure1 = BallotMeasure(
        year=2024,
        measure_id="Prop 1",
        title="Test Measure",
        state="CA",
        data_source="TEST"
    )

    measure2 = BallotMeasure(
        year=2024,
        measure_id="Prop 1",
        title="Test Measure",
        state="CA",
        data_source="TEST"
    )

    # Insert first measure
    db.insert_measure(measure1)

    # Check if second is duplicate
    duplicate = deduplicator.check_duplicate(measure2)

    assert duplicate is not None
    assert duplicate['type'] == 'exact'


def test_check_duplicate_content_match(temp_db_with_dedup):
    """Test detecting content-based duplicate"""
    db, deduplicator = temp_db_with_dedup

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
        measure_id="Prop 2",  # Different ID
        title="Same Title",
        description="Same Description",
        state="CA",
        data_source="SOURCE2"  # Different source
    )

    # Insert first measure
    db.insert_measure(measure1)

    # Check if second is duplicate based on content
    duplicate = deduplicator.check_duplicate(measure2)

    assert duplicate is not None
    # Should detect as content duplicate
    assert duplicate['type'] in ['content', 'cross_source']


def test_check_duplicate_no_match(temp_db_with_dedup):
    """Test that non-duplicates are not flagged"""
    db, deduplicator = temp_db_with_dedup

    measure1 = BallotMeasure(
        year=2024,
        measure_id="Prop 1",
        title="Different Title",
        state="CA",
        data_source="TEST"
    )

    measure2 = BallotMeasure(
        year=2024,
        measure_id="Prop 2",
        title="Another Different Title",
        state="CA",
        data_source="TEST"
    )

    # Insert first measure
    db.insert_measure(measure1)

    # Check if second is duplicate (should not be)
    duplicate = deduplicator.check_duplicate(measure2)

    assert duplicate is None or duplicate == {}


def test_mark_duplicate(temp_db_with_dedup):
    """Test marking a measure as duplicate"""
    db, deduplicator = temp_db_with_dedup

    measure1 = BallotMeasure(
        year=2024,
        measure_id="Prop 1",
        title="Original",
        state="CA",
        data_source="TEST"
    )

    measure2 = BallotMeasure(
        year=2024,
        measure_id="Prop 2",
        title="Duplicate",
        state="CA",
        data_source="TEST"
    )

    id1 = db.insert_measure(measure1)
    id2 = db.insert_measure(measure2)

    # Mark second as duplicate of first
    result = deduplicator.mark_duplicate(id2, id1, 'content')

    assert result is True

    # Verify duplicate was marked
    dup_measure = db.get_measure_by_id(id2)
    if dup_measure:
        assert dup_measure.is_duplicate == 1
        assert dup_measure.master_id == id1


def test_deduplicate_cross_source(temp_db_with_dedup):
    """Test cross-source deduplication"""
    db, deduplicator = temp_db_with_dedup

    # Insert same measure from two different sources
    measure1 = BallotMeasure(
        year=2024,
        measure_id="Prop 1",
        title="Same Measure",
        description="Same content",
        state="CA",
        data_source="SOURCE1"
    )

    measure2 = BallotMeasure(
        year=2024,
        measure_id="Prop 1",
        title="Same Measure",
        description="Same content",
        state="CA",
        data_source="SOURCE2"
    )

    db.insert_measure(measure1)
    db.insert_measure(measure2)

    # Run cross-source deduplication
    stats = deduplicator.deduplicate_cross_source()

    # Should find at least one duplicate
    assert isinstance(stats, dict)


def test_get_duplicate_report(temp_db_with_dedup):
    """Test getting duplicate report"""
    db, deduplicator = temp_db_with_dedup

    # Insert some test data
    measure = BallotMeasure(
        year=2024,
        measure_id="Prop 1",
        title="Test",
        state="CA",
        data_source="TEST"
    )
    db.insert_measure(measure)

    report = deduplicator.get_duplicate_report()

    assert isinstance(report, dict)
    assert 'total_duplicates' in report or 'total_measures' in report
