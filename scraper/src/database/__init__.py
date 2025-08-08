# Add parent directory to path for imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

"""
Database package for California Ballot Measures
Provides data models, operations, and deduplication functionality
"""
from .models import BallotMeasure
from .operations import Database
from .deduplication import Deduplicator

__all__ = [
    'BallotMeasure',
    'Database', 
    'Deduplicator'
]

# Package metadata
__version__ = '1.0.0'
__author__ = 'California Ballot Measures Project'

# Convenience function for quick database access
def get_database(db_path=None):
    """
    Get a database operations instance
    
    Args:
        db_path: Path to database file (uses default if None)
    
    Returns:
        Database instance
    """
    from src.config import DB_PATH
    return Database(db_path or DB_PATH)

# Convenience function for checking database status
def check_database_status(db_path=None):
    """
    Check if database exists and return basic stats
    
    Args:
        db_path: Path to database file (uses default if None)
    
    Returns:
        Dict with database status and statistics
    """
    from pathlib import Path
    from src.config import DB_PATH
    
    path = Path(db_path or DB_PATH)
    
    if not path.exists():
        return {
            'exists': False,
            'path': str(path),
            'message': 'Database not found. Run scripts/initialize_db.py to create.'
        }
    
    try:
        db = get_database(path)
        stats = db.get_statistics()
        
        return {
            'exists': True,
            'path': str(path),
            'size_mb': round(path.stat().st_size / 1024 / 1024, 2),
            'total_measures': stats['total_measures'],
            'with_summaries': stats['with_summaries'],
            'with_votes': stats['with_votes'],
            'sources': stats['sources'],
            'year_range': f"{stats.get('year_min', 'N/A')}-{stats.get('year_max', 'N/A')}"
        }
    except Exception as e:
        return {
            'exists': True,
            'path': str(path),
            'error': str(e),
            'message': 'Database exists but could not read statistics'
        }

# Convenience function for quick searches
def quick_search(query, limit=10):
    """
    Perform a quick search of the database
    
    Args:
        query: Search query string
        limit: Maximum results to return
    
    Returns:
        List of matching measures
    """
    try:
        db = get_database()
        return db.search_measures(query=query, limit=limit)
    except Exception as e:
        print(f"Search error: {e}")
        return []