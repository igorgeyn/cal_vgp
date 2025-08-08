"""
Database operations and management
"""
import sqlite3
import json
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from pathlib import Path

from .models import BallotMeasure, SCHEMA
from ..config import DB_PATH

logger = logging.getLogger(__name__)


class Database:
    """Main database class for ballot measures"""
    
    def __init__(self, db_path: Path = None):
        self.db_path = db_path or DB_PATH
        self.conn = None
        self._ensure_database()
        
    def _ensure_database(self):
        """Ensure database exists and is properly initialized"""
        if not self.db_path.exists():
            logger.info(f"Creating new database at {self.db_path}")
            self.initialize_database()
        else:
            # Check if schema needs updating
            self._check_schema()
    
    def connect(self):
        """Establish database connection"""
        if self.conn:
            return self.conn
            
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        return self.conn
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        if exc_type:
            self.conn.rollback()
        else:
            self.conn.commit()
        self.close()
    
    def initialize_database(self):
        """Initialize database with schema"""
        conn = self.connect()
        try:
            # Execute schema creation
            conn.executescript(SCHEMA)
            conn.commit()
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            raise
        finally:
            self.close()
    
    def _check_schema(self):
        """Check and update schema if needed"""
        conn = self.connect()
        try:
            # Get existing tables
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            tables = {row['name'] for row in cursor}
            
            # If measures table doesn't exist, initialize
            if 'measures' not in tables:
                logger.info("Measures table not found, initializing database")
                self.close()
                self.initialize_database()
                return
                
            # Check for missing columns and add them
            cursor = conn.execute("PRAGMA table_info(measures)")
            existing_columns = {row['name'] for row in cursor}
            
            # Define expected columns
            expected_columns = {
                'fingerprint', 'measure_fingerprint', 'content_hash',
                'is_active', 'is_duplicate', 'duplicate_type', 'master_id',
                'merged_from', 'update_count', 'last_seen_at'
            }
            
            # Add missing columns
            missing_columns = expected_columns - existing_columns
            if missing_columns:
                logger.info(f"Adding missing columns: {missing_columns}")
                for col in missing_columns:
                    try:
                        if col == 'is_active':
                            conn.execute(f"ALTER TABLE measures ADD COLUMN {col} BOOLEAN DEFAULT 1")
                        elif col == 'is_duplicate':
                            conn.execute(f"ALTER TABLE measures ADD COLUMN {col} BOOLEAN DEFAULT 0")
                        elif col == 'update_count':
                            conn.execute(f"ALTER TABLE measures ADD COLUMN {col} INTEGER DEFAULT 0")
                        elif col == 'last_seen_at':
                            conn.execute(f"ALTER TABLE measures ADD COLUMN {col} TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
                        else:
                            conn.execute(f"ALTER TABLE measures ADD COLUMN {col} TEXT")
                    except sqlite3.OperationalError as e:
                        if "duplicate column name" not in str(e):
                            logger.warning(f"Error adding column {col}: {e}")
                            
                conn.commit()
                
        finally:
            self.close()
    
    def insert_measure(self, measure: BallotMeasure) -> int:
        """Insert a new measure"""
        conn = self.connect()
        data = measure.to_dict()
        
        # Remove id field if present
        data.pop('id', None)
        
        # Build insert query
        fields = list(data.keys())
        placeholders = ['?' for _ in fields]
        
        sql = f"""
        INSERT INTO measures ({', '.join(fields)})
        VALUES ({', '.join(placeholders)})
        """
        
        try:
            cursor = conn.execute(sql, list(data.values()))
            measure_id = cursor.lastrowid
            logger.debug(f"Inserted measure {measure.fingerprint} with ID {measure_id}")
            return measure_id
        except sqlite3.IntegrityError as e:
            if "UNIQUE constraint failed" in str(e):
                logger.debug(f"Measure already exists: {measure.fingerprint}")
                raise DuplicateError(f"Measure already exists: {measure.fingerprint}")
            else:
                raise
    
    def update_measure(self, measure_id: int, updates: Dict) -> bool:
        """Update an existing measure"""
        conn = self.connect()
        
        # Remove fields that shouldn't be updated
        updates.pop('id', None)
        updates.pop('fingerprint', None)
        updates.pop('created_at', None)
        
        # Add update metadata
        updates['updated_at'] = datetime.now()
        updates['update_count'] = conn.execute(
            "SELECT update_count FROM measures WHERE id = ?", (measure_id,)
        ).fetchone()['update_count'] + 1
        
        # Build update query
        set_clauses = [f"{field} = ?" for field in updates.keys()]
        sql = f"""
        UPDATE measures 
        SET {', '.join(set_clauses)}
        WHERE id = ?
        """
        
        values = list(updates.values()) + [measure_id]
        cursor = conn.execute(sql, values)
        
        return cursor.rowcount > 0
    
    def get_measure(self, measure_id: int) -> Optional[BallotMeasure]:
        """Get a measure by ID"""
        conn = self.connect()
        cursor = conn.execute("SELECT * FROM measures WHERE id = ?", (measure_id,))
        row = cursor.fetchone()
        
        if row:
            return BallotMeasure.from_dict(dict(row))
        return None
    
    def find_by_fingerprint(self, fingerprint: str) -> Optional[BallotMeasure]:
        """Find measure by fingerprint"""
        conn = self.connect()
        cursor = conn.execute(
            "SELECT * FROM measures WHERE fingerprint = ?", (fingerprint,)
        )
        row = cursor.fetchone()
        
        if row:
            return BallotMeasure.from_dict(dict(row))
        return None
    
    def find_by_content_hash(self, content_hash: str) -> List[BallotMeasure]:
        """Find measures by content hash"""
        conn = self.connect()
        cursor = conn.execute(
            "SELECT * FROM measures WHERE content_hash = ? AND is_duplicate = 0",
            (content_hash,)
        )
        
        measures = []
        for row in cursor:
            measures.append(BallotMeasure.from_dict(dict(row)))
        return measures
    
    def search_measures(self, query: str, limit: int = 100) -> List[BallotMeasure]:
        """Full-text search for measures"""
        conn = self.connect()
        
        try:
            cursor = conn.execute("""
                SELECT m.* FROM measures m
                JOIN measure_search ms ON m.id = ms.rowid
                WHERE measure_search MATCH ?
                AND m.is_active = 1 AND m.is_duplicate = 0
                ORDER BY rank
                LIMIT ?
            """, (query, limit))
            
            measures = []
            for row in cursor:
                measures.append(BallotMeasure.from_dict(dict(row)))
            return measures
            
        except sqlite3.OperationalError:
            # Fallback to LIKE search if FTS not available
            logger.warning("FTS search failed, falling back to LIKE search")
            cursor = conn.execute("""
                SELECT * FROM measures
                WHERE (title LIKE ? OR description LIKE ? OR ballot_question LIKE ?)
                AND is_active = 1 AND is_duplicate = 0
                ORDER BY year DESC
                LIMIT ?
            """, (f"%{query}%", f"%{query}%", f"%{query}%", limit))
            
            measures = []
            for row in cursor:
                measures.append(BallotMeasure.from_dict(dict(row)))
            return measures
    
    def get_all_active_measures(self) -> List[BallotMeasure]:
        """Get all active (non-duplicate) measures"""
        conn = self.connect()
        cursor = conn.execute("""
            SELECT * FROM active_measures
            ORDER BY year DESC, county, measure_letter
        """)
        
        measures = []
        for row in cursor:
            measures.append(BallotMeasure.from_dict(dict(row)))
        return measures
    
    def get_statistics(self) -> Dict:
        """Get database statistics"""
        conn = self.connect()
        stats = {}
        
        # Total measures
        cursor = conn.execute("SELECT COUNT(*) as count FROM active_measures")
        stats['total_measures'] = cursor.fetchone()['count']
        
        # With summaries
        cursor = conn.execute(
            "SELECT COUNT(*) as count FROM active_measures WHERE has_summary = 1"
        )
        stats['with_summaries'] = cursor.fetchone()['count']
        
        # With votes
        cursor = conn.execute(
            "SELECT COUNT(*) as count FROM active_measures WHERE yes_votes IS NOT NULL"
        )
        stats['with_votes'] = cursor.fetchone()['count']
        
        # Year range
        cursor = conn.execute(
            "SELECT MIN(year) as min_year, MAX(year) as max_year FROM active_measures"
        )
        row = cursor.fetchone()
        stats['year_min'] = row['min_year']
        stats['year_max'] = row['max_year']
        
        # By source
        cursor = conn.execute("""
            SELECT data_source, COUNT(*) as count
            FROM active_measures
            GROUP BY data_source
        """)
        stats['by_source'] = {row['data_source']: row['count'] for row in cursor}
        
        # Pass rate
        cursor = conn.execute("""
            SELECT 
                SUM(CASE WHEN passed = 1 THEN 1 ELSE 0 END) as passed,
                SUM(CASE WHEN passed = 0 THEN 1 ELSE 0 END) as failed
            FROM active_measures
        """)
        row = cursor.fetchone()
        stats['passed'] = row['passed'] or 0
        stats['failed'] = row['failed'] or 0
        
        return stats
    
    def log_scraper_run(self, run_type: str) -> int:
        """Start a new scraper run log"""
        conn = self.connect()
        cursor = conn.execute(
            "INSERT INTO scraper_runs (run_type, status) VALUES (?, 'running')",
            (run_type,)
        )
        return cursor.lastrowid
    
    def update_scraper_run(self, run_id: int, **kwargs):
        """Update scraper run with results"""
        conn = self.connect()
        
        updates = []
        values = []
        
        for key, value in kwargs.items():
            if key in ['measures_checked', 'new_measures', 'updated_measures', 
                      'duplicates_found', 'status', 'error_message']:
                updates.append(f"{key} = ?")
                values.append(value)
        
        if 'status' in kwargs and kwargs['status'] in ['success', 'failed']:
            updates.append("completed_at = CURRENT_TIMESTAMP")
        
        if updates:
            sql = f"UPDATE scraper_runs SET {', '.join(updates)} WHERE id = ?"
            values.append(run_id)
            conn.execute(sql, values)
    
    def backup(self, backup_path: Path = None) -> Path:
        """Create a database backup"""
        if backup_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = self.db_path.parent / f"ballot_measures_backup_{timestamp}.db"
            
        # Use SQLite backup API
        conn = self.connect()
        backup_conn = sqlite3.connect(backup_path)
        
        with backup_conn:
            conn.backup(backup_conn)
            
        backup_conn.close()
        logger.info(f"Database backed up to {backup_path}")
        
        return backup_path


class DuplicateError(Exception):
    """Raised when attempting to insert a duplicate measure"""
    pass