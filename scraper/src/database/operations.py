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
                'id', 'fingerprint', 'measure_fingerprint', 'content_hash',
                'measure_id', 'measure_letter', 'year', 'state', 'county',
                'jurisdiction', 'title', 'description', 'ballot_question',
                'generated_title', 'original_title',
                'vote_threshold',
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
            
            # Fix year column type if needed
            self._fix_year_types(conn)
                
        finally:
            self.close()
    
    def _fix_year_types(self, conn):
        """Ensure year columns are stored as integers"""
        try:
            # Check if we have any non-integer years
            cursor = conn.execute("""
                SELECT COUNT(*) as count 
                FROM measures 
                WHERE typeof(year) != 'integer' AND year IS NOT NULL
            """)
            count = cursor.fetchone()['count']
            
            if count > 0:
                logger.info(f"Converting {count} year values to integers")
                conn.execute("""
                    UPDATE measures 
                    SET year = CAST(year AS INTEGER)
                    WHERE typeof(year) != 'integer' AND year IS NOT NULL
                """)
                conn.commit()
        except Exception as e:
            logger.warning(f"Could not fix year types: {e}")
    
    def insert_measure(self, measure: BallotMeasure) -> int:
        """Insert a new measure"""
        conn = self.connect()
        data = measure.to_dict()
        
        # Remove id field if present
        data.pop('id', None)
        
        # Ensure year is integer
        if 'year' in data and data['year'] is not None:
            data['year'] = int(data['year'])
        
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
        """Update an existing measure, recomputing derived keys if needed."""
        conn = self.connect()

        # Remove fields that shouldn't be directly set
        updates.pop('id', None)
        updates.pop('created_at', None)

        # Never overwrite populated fields with null/empty values.
        # This prevents data loss when a source reload sends incomplete records.
        #
        # Text fields: protect non-null from being set to None or ''
        # Numeric fields: protect non-null from being set to None
        #   (0 is a valid value for numeric fields like passed=0, yes_votes=0)
        # Boolean-like: has_summary is DERIVED, not directly settable here
        TEXT_PROTECTED = {
            'summary_text', 'summary_title',
            'ballot_question', 'description',
            'category_type', 'category_topic',
            'pass_fail',
        }
        NUMERIC_PROTECTED = {
            'yes_votes', 'no_votes', 'total_votes',
            'percent_yes', 'percent_no', 'passed',
        }
        row = conn.execute("SELECT * FROM measures WHERE id = ?", (measure_id,)).fetchone()
        if row:
            current = dict(row)
            for field in TEXT_PROTECTED:
                if field in updates:
                    new_val = updates[field]
                    old_val = current.get(field)
                    # Don't overwrite non-empty text with None or ''
                    if old_val is not None and old_val != '':
                        if new_val is None or new_val == '':
                            updates.pop(field)
            for field in NUMERIC_PROTECTED:
                if field in updates:
                    new_val = updates[field]
                    old_val = current.get(field)
                    # Don't overwrite non-null numeric with None
                    # (0 is valid — passed=0 means "failed", yes_votes=0 is real)
                    if old_val is not None:
                        if new_val is None:
                            updates.pop(field)

            # has_summary is derived: recompute from summary_text after all updates
            # Remove caller-provided has_summary — we'll set it ourselves
            updates.pop('has_summary', None)
            final_summary = updates.get('summary_text', current.get('summary_text'))
            updates['has_summary'] = 1 if (final_summary and final_summary != '') else 0

        # Ensure year is integer if present
        if 'year' in updates and updates['year'] is not None:
            updates['year'] = int(updates['year'])

        # If any fingerprint-affecting field changed, recompute derived keys
        fingerprint_fields = {'year', 'measure_id', 'county', 'data_source',
                              'title', 'ballot_question', 'description', 'measure_letter'}
        if fingerprint_fields & set(updates.keys()):
            # Get current record to merge with updates
            row = conn.execute("SELECT * FROM measures WHERE id = ?", (measure_id,)).fetchone()
            if row:
                current = dict(row)
                merged = {**current, **updates}
                # Build a temporary BallotMeasure to regenerate fingerprints
                temp = BallotMeasure(
                    year=merged.get('year'),
                    measure_id=merged.get('measure_id'),
                    measure_letter=merged.get('measure_letter'),
                    county=merged.get('county', 'Statewide'),
                    data_source=merged.get('data_source', 'Unknown'),
                    title=merged.get('title'),
                    ballot_question=merged.get('ballot_question'),
                    description=merged.get('description'),
                )
                updates['fingerprint'] = temp.fingerprint
                updates['measure_fingerprint'] = temp.measure_fingerprint
                updates['content_hash'] = temp.content_hash
        else:
            # Don't overwrite fingerprint with stale values from caller
            updates.pop('fingerprint', None)
            updates.pop('measure_fingerprint', None)
            updates.pop('content_hash', None)

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
    
    def search_measures(self, query: str = None, limit: int = 100, offset: int = 0, **filters) -> List[BallotMeasure]:
        """Full-text search for measures with filters"""
        conn = self.connect()

        # Build query
        where_clauses = ["is_active = 1", "is_duplicate = 0"]
        params = []

        # Add filters
        if filters.get('year'):
            where_clauses.append("year = ?")
            params.append(int(filters['year']))

        if filters.get('year_min'):
            where_clauses.append("year >= ?")
            params.append(int(filters['year_min']))

        if filters.get('year_max'):
            where_clauses.append("year <= ?")
            params.append(int(filters['year_max']))

        if filters.get('county'):
            where_clauses.append("county = ?")
            params.append(filters['county'])

        if filters.get('passed') is not None:
            where_clauses.append("passed = ?")
            params.append(filters['passed'])

        if filters.get('has_summary') is not None:
            where_clauses.append("has_summary = ?")
            params.append(filters['has_summary'])

        if filters.get('topic_primary'):
            where_clauses.append("topic_primary = ?")
            params.append(filters['topic_primary'])

        if filters.get('source'):
            where_clauses.append("data_source = ?")
            params.append(filters['source'])

        # Add text search if query provided
        if query:
            where_clauses.append("""
                (title LIKE ? OR description LIKE ? OR ballot_question LIKE ?)
            """)
            search_pattern = f"%{query}%"
            params.extend([search_pattern, search_pattern, search_pattern])

        # Build final query
        sql = f"""
            SELECT * FROM measures
            WHERE {' AND '.join(where_clauses)}
            ORDER BY year DESC, county, measure_letter
            LIMIT ? OFFSET ?
        """
        params.append(limit)
        params.append(offset)
        
        cursor = conn.execute(sql, params)
        
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
        """Get database statistics with proper type handling"""
        conn = self.connect()
        stats = {}
        
        # Total measures
        cursor = conn.execute("SELECT COUNT(*) as count FROM active_measures")
        stats['total_measures'] = int(cursor.fetchone()['count'] or 0)
        
        # With summaries
        cursor = conn.execute(
            "SELECT COUNT(*) as count FROM active_measures WHERE has_summary = 1"
        )
        stats['with_summaries'] = int(cursor.fetchone()['count'] or 0)
        
        # With votes
        cursor = conn.execute(
            "SELECT COUNT(*) as count FROM active_measures WHERE yes_votes IS NOT NULL"
        )
        stats['with_votes'] = int(cursor.fetchone()['count'] or 0)
        
        # Year range - ENSURE INTEGERS
        cursor = conn.execute("""
            SELECT 
                MIN(CAST(year AS INTEGER)) as min_year, 
                MAX(CAST(year AS INTEGER)) as max_year 
            FROM active_measures
            WHERE year IS NOT NULL
        """)
        row = cursor.fetchone()
        # Convert to int, with defaults if None
        stats['year_min'] = int(row['min_year']) if row['min_year'] is not None else 1902
        stats['year_max'] = int(row['max_year']) if row['max_year'] is not None else 2026
        
        # By source
        cursor = conn.execute("""
            SELECT data_source, COUNT(*) as count
            FROM active_measures
            GROUP BY data_source
        """)
        stats['by_source'] = {}
        stats['sources'] = []
        for row in cursor:
            source = row['data_source'] or 'Unknown'
            count = int(row['count'] or 0)
            stats['by_source'][source] = count
            stats['sources'].append(source)
        
        # Pass rate - ENSURE INTEGERS
        cursor = conn.execute("""
            SELECT 
                SUM(CASE WHEN passed = 1 THEN 1 ELSE 0 END) as passed,
                SUM(CASE WHEN passed = 0 THEN 1 ELSE 0 END) as failed
            FROM active_measures
        """)
        row = cursor.fetchone()
        stats['passed'] = int(row['passed'] or 0)
        stats['failed'] = int(row['failed'] or 0)
        stats['unknown'] = stats['total_measures'] - stats['passed'] - stats['failed']

        # Statewide vs local counts
        cursor = conn.execute(
            "SELECT COUNT(*) as count FROM active_measures "
            "WHERE county = 'Statewide' OR county IS NULL OR county = ''"
        )
        stats['statewide_count'] = int(cursor.fetchone()['count'] or 0)
        stats['local_count'] = stats['total_measures'] - stats['statewide_count']

        # County and topic counts
        cursor = conn.execute(
            "SELECT COUNT(DISTINCT county) as count FROM active_measures "
            "WHERE county IS NOT NULL AND county != '' AND county != 'Statewide'"
        )
        stats['counties'] = int(cursor.fetchone()['count'] or 0)
        cursor = conn.execute(
            "SELECT COUNT(DISTINCT topic_primary) as count FROM active_measures "
            "WHERE topic_primary IS NOT NULL AND topic_primary != ''"
        )
        stats['topics'] = int(cursor.fetchone()['count'] or 0)
        
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
    
    # Additional helper methods for compatibility
    def get_years_with_counts(self) -> List[Dict]:
        """Get all years with measure counts"""
        conn = self.connect()
        cursor = conn.execute("""
            SELECT 
                CAST(year AS INTEGER) as year,
                COUNT(*) as count
            FROM active_measures
            WHERE year IS NOT NULL
            GROUP BY year
            ORDER BY year DESC
        """)
        
        results = []
        for row in cursor:
            results.append({
                'year': int(row['year']),
                'count': int(row['count'])
            })
        return results
    
    def get_topics_with_counts(self) -> List[Dict]:
        """Get all topics with counts"""
        conn = self.connect()
        cursor = conn.execute("""
            SELECT 
                COALESCE(topic_primary, category_topic, 'Unknown') as topic,
                COUNT(*) as count
            FROM active_measures
            GROUP BY topic
            ORDER BY count DESC
        """)
        
        results = []
        for row in cursor:
            results.append({
                'topic': row['topic'],
                'count': int(row['count'])
            })
        return results
    
    def get_counties_with_counts(self) -> List[Dict]:
        """Get all counties with measure counts"""
        conn = self.connect()
        cursor = conn.execute("""
            SELECT 
                county,
                COUNT(*) as count
            FROM active_measures
            GROUP BY county
            ORDER BY count DESC
        """)
        
        results = []
        for row in cursor:
            results.append({
                'county': row['county'] or 'Unknown',
                'count': int(row['count'])
            })
        return results


class DuplicateError(Exception):
    """Raised when attempting to insert a duplicate measure"""
    pass


# Convenience class for backward compatibility
DatabaseOperations = Database