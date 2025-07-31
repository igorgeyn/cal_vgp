#!/usr/bin/env python3
"""
Enhanced Ballot Measures Database with Full Integration
Fixed version - handles UNIQUE constraint issue and cross-source deduplication
"""

import sqlite3
import pandas as pd
import json
from pathlib import Path
from datetime import datetime
import re
import hashlib
from typing import Optional, Dict, List, Tuple
import argparse
import shutil

class EnhancedBallotDatabase:
    """Enhanced ballot measures database with full integration"""
    
    def __init__(self, db_path: str = 'data/ballot_measures.db'):
        self.db_path = db_path
        self.conn = None
        
    def connect(self):
        """Establish database connection"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row  # Enable column access by name
        self.conn.execute("PRAGMA foreign_keys = ON")
        
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            
    def create_enhanced_schema(self):
        """Create enhanced database schema for full integration"""
        print("📊 Creating enhanced database schema...")
        
        # Check if measures table exists
        cursor = self.conn.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='measures'
        """)
        table_exists = cursor.fetchone() is not None
        
        if table_exists:
            print("   📦 Existing measures table found - checking for schema updates...")
            
            # Get existing columns
            cursor = self.conn.execute("PRAGMA table_info(measures)")
            existing_columns = {row[1] for row in cursor.fetchall()}
            
            # Define columns that might need to be added
            columns_to_add = [
                # Core new columns
                ('fingerprint', 'TEXT'),  # Unique per source
                ('measure_fingerprint', 'TEXT'),  # Cross-source matching
                ('content_hash', 'TEXT'),
                
                # Fields that might be missing
                ('measure_letter', 'TEXT'),
                ('county', 'TEXT'),
                ('jurisdiction', 'TEXT'),
                ('ballot_question', 'TEXT'),
                
                # Vote data fields
                ('yes_votes', 'INTEGER'),
                ('no_votes', 'INTEGER'),
                ('total_votes', 'INTEGER'),
                ('percent_no', 'REAL'),
                ('pass_fail', 'TEXT'),
                
                # Classification fields
                ('category_type', 'TEXT'),
                ('category_topic', 'TEXT'),
                
                # Enhanced tracking fields
                ('is_active', 'BOOLEAN DEFAULT 1'),
                ('is_duplicate', 'BOOLEAN DEFAULT 0'),
                ('duplicate_type', 'TEXT'),  # 'within_source' or 'cross_source'
                ('master_id', 'INTEGER'),
                ('merged_from', 'TEXT'),  # JSON array of source IDs
                ('update_count', 'INTEGER DEFAULT 0'),
                ('last_seen_at', 'TIMESTAMP')
            ]
            
            # Add missing columns
            for col_name, col_type in columns_to_add:
                if col_name not in existing_columns:
                    try:
                        print(f"   ➕ Adding column: {col_name}")
                        if col_name == 'last_seen_at':
                            self.conn.execute(f"ALTER TABLE measures ADD COLUMN {col_name} {col_type}")
                            self.conn.execute(f"UPDATE measures SET {col_name} = CURRENT_TIMESTAMP WHERE {col_name} IS NULL")
                        else:
                            self.conn.execute(f"ALTER TABLE measures ADD COLUMN {col_name} {col_type}")
                    except sqlite3.OperationalError as e:
                        if "duplicate column name" not in str(e):
                            print(f"   ⚠️  Warning adding {col_name}: {e}")
            
            # Commit column additions
            self.conn.commit()
            print("   ✅ Columns added successfully")
            
            # Regenerate all fingerprints with enhanced logic
            print("   🔧 Regenerating fingerprints with enhanced logic...")
            self.regenerate_all_fingerprints()
            
        else:
            print("   🆕 Creating new measures table...")
            
            # Create the full enhanced table
            self.conn.execute("""
            CREATE TABLE measures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                
                -- Unique fingerprint for deduplication
                fingerprint TEXT UNIQUE,
                measure_fingerprint TEXT,  -- For cross-source matching
                content_hash TEXT,
                
                -- Core fields
                measure_id TEXT,
                measure_letter TEXT,
                year INTEGER NOT NULL,
                state TEXT DEFAULT 'CA',
                county TEXT,
                jurisdiction TEXT,
                title TEXT,
                description TEXT,
                ballot_question TEXT,
                
                -- Vote results
                yes_votes INTEGER,
                no_votes INTEGER,
                total_votes INTEGER,
                percent_yes REAL,
                percent_no REAL,
                passed INTEGER,
                pass_fail TEXT,
                
                -- Classification
                measure_type TEXT,
                topic_primary TEXT,
                topic_secondary TEXT,
                category_type TEXT,
                category_topic TEXT,
                
                -- Source tracking
                data_source TEXT NOT NULL,
                source_url TEXT,
                pdf_url TEXT,
                
                -- Summary data
                has_summary BOOLEAN DEFAULT 0,
                summary_title TEXT,
                summary_text TEXT,
                
                -- Metadata
                election_type TEXT,
                election_date DATE,
                decade INTEGER,
                century INTEGER,
                
                -- Tracking
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                update_count INTEGER DEFAULT 0,
                
                -- Status flags
                is_active BOOLEAN DEFAULT 1,
                is_duplicate BOOLEAN DEFAULT 0,
                duplicate_type TEXT,
                master_id INTEGER,
                merged_from TEXT,
                
                FOREIGN KEY(master_id) REFERENCES measures(id)
            )""")
        
        # Create indexes
        print("   📑 Creating indexes...")
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_fingerprint ON measures(fingerprint)",
            "CREATE INDEX IF NOT EXISTS idx_measure_fingerprint ON measures(measure_fingerprint)",
            "CREATE INDEX IF NOT EXISTS idx_year ON measures(year)",
            "CREATE INDEX IF NOT EXISTS idx_county ON measures(county)",
            "CREATE INDEX IF NOT EXISTS idx_passed ON measures(passed)",
            "CREATE INDEX IF NOT EXISTS idx_topic ON measures(topic_primary)",
            "CREATE INDEX IF NOT EXISTS idx_source ON measures(data_source)",
            "CREATE INDEX IF NOT EXISTS idx_has_summary ON measures(has_summary)",
            "CREATE INDEX IF NOT EXISTS idx_content_hash ON measures(content_hash)",
            "CREATE INDEX IF NOT EXISTS idx_is_duplicate ON measures(is_duplicate)",
            "CREATE INDEX IF NOT EXISTS idx_master_id ON measures(master_id)"
        ]
        
        for idx in indexes:
            try:
                self.conn.execute(idx)
            except sqlite3.OperationalError as e:
                if "already exists" not in str(e):
                    print(f"   ⚠️  Warning creating index: {e}")
        
        # Create or update other tables
        self._create_tracking_tables()
        self._create_search_table()
        self._create_analysis_views()
        
        self.conn.commit()
        print("   ✅ Enhanced schema ready!")
    
    # def regenerate_all_fingerprints(self):
    #     """Regenerate all fingerprints with enhanced logic"""
    #     cursor = self.conn.execute("""
    #         SELECT id, year, title, measure_text, data_source, county, 
    #                measure_letter, measure_id, ballot_question
    #         FROM measures
    #     """)
        
    #     records = cursor.fetchall()
    #     updated = 0
        
    #     for record in records:
    #         measure_data = {
    #             'id': record['id'],
    #             'year': record['year'],
    #             'title': record['title'] or record['measure_text'],
    #             'measure_text': record['measure_text'],
    #             'data_source': record['data_source'],
    #             'county': record['county'] or 'Statewide',
    #             'measure_letter': record['measure_letter'],
    #             'measure_id': record['measure_id'],
    #             'ballot_question': record['ballot_question']
    #         }
            
    #         unique_fp, measure_fp, content_hash = self.create_enhanced_fingerprint(measure_data)
            
    #         try:
    #             self.conn.execute(
    #                 """UPDATE measures 
    #                 SET fingerprint = ?, measure_fingerprint = ?, content_hash = ? 
    #                 WHERE id = ?""",
    #                 (unique_fp, measure_fp, content_hash, record['id'])
    #             )
    #             updated += 1
    #         except sqlite3.IntegrityError:
    #             # Handle duplicates by appending ID
    #             unique_fp = f"{unique_fp}_ID{record['id']}"
    #             self.conn.execute(
    #                 """UPDATE measures 
    #                 SET fingerprint = ?, measure_fingerprint = ?, content_hash = ?, 
    #                     is_duplicate = 1, duplicate_type = 'within_source'
    #                 WHERE id = ?""",
    #                 (unique_fp, measure_fp, content_hash, record['id'])
    #             )
    #             updated += 1
        
    #     self.conn.commit()
    #     print(f"   ✅ Regenerated {updated} fingerprints")

    def regenerate_all_fingerprints(self):
        """Regenerate all fingerprints with enhanced logic"""
        cursor = self.conn.execute("""
            SELECT id, year, title, data_source, county, 
                measure_letter, measure_id, ballot_question
            FROM measures
        """)
        
        records = cursor.fetchall()
        updated = 0
        
        for record in records:
            measure_data = {
                'id': record['id'],
                'year': record['year'],
                'title': record['title'],
                'measure_text': record['title'],  # Use title as measure_text
                'data_source': record['data_source'],
                'county': record['county'] or 'Statewide',
                'measure_letter': record['measure_letter'],
                'measure_id': record['measure_id'],
                'ballot_question': record['ballot_question']
            }
            
            unique_fp, measure_fp, content_hash = self.create_enhanced_fingerprint(measure_data)
            
            try:
                self.conn.execute(
                    """UPDATE measures 
                    SET fingerprint = ?, measure_fingerprint = ?, content_hash = ? 
                    WHERE id = ?""",
                    (unique_fp, measure_fp, content_hash, record['id'])
                )
                updated += 1
            except sqlite3.IntegrityError:
                # Handle duplicates by appending ID
                unique_fp = f"{unique_fp}_ID{record['id']}"
                self.conn.execute(
                    """UPDATE measures 
                    SET fingerprint = ?, measure_fingerprint = ?, content_hash = ?, 
                        is_duplicate = 1, duplicate_type = 'within_source'
                    WHERE id = ?""",
                    (unique_fp, measure_fp, content_hash, record['id'])
                )
                updated += 1
        
        self.conn.commit()
        print(f"   ✅ Regenerated {updated} fingerprints")
    
    def create_enhanced_fingerprint(self, measure_data: Dict) -> Tuple[str, str, str]:
        """
        Create THREE fingerprints:
        1. unique_fingerprint: For database uniqueness (includes source)
        2. measure_fingerprint: For cross-source matching (excludes source)
        3. content_hash: For content similarity
        """
        # Key components
        year = str(measure_data.get('year', '')).strip()
        source = measure_data.get('data_source', 'Unknown').upper()
        county = str(measure_data.get('county', 'Statewide')).upper()
        
        # Extract measure identifier with enhanced logic
        measure_id = None
        measure_text = str(measure_data.get('title', measure_data.get('measure_text', '')))
        
        # Enhanced patterns to catch more variations
        patterns = [
            # Standard propositions
            (r'(?:Proposition|Prop\.?)\s*(\d+[A-Z]?)', 'PROP_{}'),
            # Proposition Item X format (for CA_SOS_Scraper)
            (r'Proposition\s+Item\s+(\d+)', 'PROP_ITEM_{}'),
            # Constitutional amendments
            (r'([AS]CA)\s*(\d+)', '{}_{}'),
            # Bills
            (r'(AB|SB)\s*(\d+)', '{}_{}'),
            # Measures
            (r'(?:Measure)\s*([A-Z]+)', 'MEASURE_{}'),
            # ICPSR format like "Proposition 1-G"
            (r'Proposition\s*(\d+)-([A-Z])', 'PROP_{}_{}'),
        ]
        
        for pattern, format_str in patterns:
            match = re.search(pattern, str(measure_text), re.IGNORECASE)
            if match:
                groups = match.groups()
                measure_id = format_str.format(*groups).upper()
                break
        
        # If no pattern matched, use source-specific strategies
        if not measure_id:
            if source == 'NCSL':
                # For NCSL, use first 30 chars of title as unique identifier
                title_snippet = re.sub(r'[^A-Za-z0-9]+', '_', measure_text[:30]).upper()
                measure_id = f"NCSL_{title_snippet}"
            
            elif source == 'ICPSR' and measure_data.get('measure_id'):
                # Use ICPSR's measure ID if available
                measure_id = f"ICPSR_ID_{measure_data['measure_id']}"
            
            elif measure_data.get('measure_letter'):
                # Use measure letter for local measures
                measure_id = f"MEASURE_{measure_data['measure_letter']}"
            
            elif measure_data.get('measure_id'):
                # Use raw measure_id if available
                measure_id = f"ID_{measure_data['measure_id']}"
            
            else:
                # Last resort: hash of content
                content = measure_data.get('ballot_question', '') or measure_data.get('title', '')
                if content:
                    content_hash = hashlib.md5(content.encode()).hexdigest()[:8]
                    measure_id = f"HASH_{content_hash}"
                else:
                    # Absolute last resort: use database ID if available
                    if 'id' in measure_data:
                        measure_id = f"DBID_{measure_data['id']}"
                    else:
                        measure_id = 'UNKNOWN'
        
        # Create fingerprints
        unique_fingerprint = f"{year}|{measure_id}|{county}|{source}"
        measure_fingerprint = f"{year}|{measure_id}|{county}"
        
        # Content hash
        content_parts = [
            str(measure_data.get('title', '')),
            str(measure_data.get('ballot_question', '')),
            str(measure_data.get('description', ''))
        ]
        content_str = '|'.join(content_parts).lower().strip()
        content_hash = hashlib.md5(content_str.encode()).hexdigest()[:16]
        
        return unique_fingerprint, measure_fingerprint, content_hash
    
    def handle_cross_source_deduplication(self):
        """Identify and link measures that appear in multiple sources"""
        print("\n🔄 Handling cross-source deduplication...")
        
        # Find all measures grouped by measure_fingerprint
        cursor = self.conn.execute("""
            SELECT 
                measure_fingerprint,
                COUNT(*) as source_count,
                GROUP_CONCAT(id) as ids,
                GROUP_CONCAT(data_source) as sources
            FROM measures
            WHERE is_duplicate = 0 AND measure_fingerprint IS NOT NULL
            GROUP BY measure_fingerprint
            HAVING source_count > 1
            ORDER BY source_count DESC
        """)
        
        cross_source_groups = cursor.fetchall()
        print(f"   Found {len(cross_source_groups)} measures in multiple sources")
        
        for group in cross_source_groups:
            ids = [int(id) for id in group['ids'].split(',')]
            sources = group['sources'].split(',')
            
            # Get all versions of this measure
            placeholders = ','.join('?' * len(ids))
            cursor = self.conn.execute(f"""
                SELECT * FROM measures 
                WHERE id IN ({placeholders})
                ORDER BY 
                    (CASE WHEN has_summary = 1 THEN 0 ELSE 1 END),
                    (CASE WHEN yes_votes IS NOT NULL THEN 0 ELSE 1 END),
                    created_at
            """, ids)
            
            versions = list(cursor.fetchall())
            
            # Select master record (best data)
            master = self._select_master_record(versions)
            master_id = master['id']
            
            # Merge unique fields from other versions
            merged_data = self._merge_measure_data(versions, master_id)
            
            # Update master with merged data
            self._update_master_record(master_id, merged_data)
            
            # Mark others as cross-source duplicates
            for version in versions:
                if version['id'] != master_id:
                    self.conn.execute("""
                        UPDATE measures 
                        SET is_duplicate = 1, 
                            master_id = ?,
                            duplicate_type = 'cross_source'
                        WHERE id = ?
                    """, (master_id, version['id']))
            
            # Store merge history in master record
            merged_ids = [v['id'] for v in versions if v['id'] != master_id]
            if merged_ids:
                self.conn.execute("""
                    UPDATE measures 
                    SET merged_from = ?
                    WHERE id = ?
                """, (json.dumps(merged_ids), master_id))
        
        self.conn.commit()
        print(f"   ✅ Cross-source deduplication complete")
    
    def _select_master_record(self, versions):
        """Select the best record to be master based on data quality"""
        # Priority order for sources
        source_priority = {
            'CA_SOS': 1,
            'CA_SOS_Scraper': 2,
            'NCSL': 3,
            'CEDA': 4,
            'ICPSR': 5
        }
        
        # Score each version
        best_score = -1
        best_version = None
        
        for version in versions:
            score = 0
            
            # Has summary
            if version['has_summary']:
                score += 100
            
            # Has vote data
            if version['yes_votes'] is not None:
                score += 50
            
            # Has description
            if version['description']:
                score += 25
            
            # Has PDF
            if version['pdf_url'] and version['pdf_url'] != '#':
                score += 20
            
            # Source priority
            source_rank = source_priority.get(version['data_source'], 10)
            score += (10 - source_rank) * 5
            
            # Recency (if from scraper)
            if 'Scraper' in version['data_source']:
                score += 10
            
            if score > best_score:
                best_score = score
                best_version = version
        
        return best_version
    
    def _merge_measure_data(self, versions, master_id):
        """Merge unique fields from all versions"""
        merged = {}
        
        # Fields to merge (non-null wins)
        merge_fields = [
            'description', 'ballot_question', 'summary_title', 'summary_text',
            'yes_votes', 'no_votes', 'total_votes', 'percent_yes', 'percent_no',
            'passed', 'pass_fail', 'pdf_url', 'source_url',
            'category_type', 'category_topic', 'election_date'
        ]
        
        # Collect all non-null values
        for field in merge_fields:
            values = []
            for version in versions:
                if version[field] is not None and version[field] != '':
                    values.append({
                        'value': version[field],
                        'source': version['data_source'],
                        'id': version['id']
                    })
            
            if values:
                # For most fields, take the value from master if available
                master_value = next((v for v in values if v['id'] == master_id), None)
                if master_value:
                    merged[field] = master_value['value']
                else:
                    # Otherwise take first non-null value
                    merged[field] = values[0]['value']
        
        # Special handling for conflicting vote data
        if 'yes_votes' in merged and 'no_votes' in merged:
            # Recalculate percentages
            total = merged.get('yes_votes', 0) + merged.get('no_votes', 0)
            if total > 0:
                merged['percent_yes'] = round((merged['yes_votes'] / total) * 100, 2)
                merged['percent_no'] = round((merged['no_votes'] / total) * 100, 2)
                merged['total_votes'] = total
        
        return merged
    
    def _update_master_record(self, master_id, merged_data):
        """Update master record with merged data"""
        if not merged_data:
            return
        
        updates = []
        values = []
        
        for field, value in merged_data.items():
            updates.append(f"{field} = ?")
            values.append(value)
        
        if updates:
            sql = f"""
            UPDATE measures 
            SET {', '.join(updates)}, 
                updated_at = CURRENT_TIMESTAMP,
                update_count = update_count + 1
            WHERE id = ?
            """
            values.append(master_id)
            self.conn.execute(sql, values)
    
    def _create_tracking_tables(self):
        """Create tracking tables if they don't exist"""
        # Update history table
        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS measure_updates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            measure_id INTEGER NOT NULL,
            field_name TEXT NOT NULL,
            old_value TEXT,
            new_value TEXT,
            update_source TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(measure_id) REFERENCES measures(id)
        )""")
        
        # Scraper runs table
        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS scraper_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_type TEXT NOT NULL,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            measures_checked INTEGER DEFAULT 0,
            new_measures INTEGER DEFAULT 0,
            updated_measures INTEGER DEFAULT 0,
            duplicates_found INTEGER DEFAULT 0,
            status TEXT,
            error_message TEXT
        )""")
    
    def _create_search_table(self):
        """Create or recreate the FTS5 search table"""
        try:
            # Drop existing search table and trigger if they exist
            self.conn.execute("DROP TRIGGER IF EXISTS measure_search_insert")
            self.conn.execute("DROP TABLE IF EXISTS measure_search")
            
            # Create new search table
            self.conn.execute("""
            CREATE VIRTUAL TABLE measure_search 
            USING fts5(
                fingerprint UNINDEXED,
                title,
                description,
                ballot_question,
                summary_title,
                summary_text,
                county,
                content='measures',
                content_rowid='id'
            )""")
            
            # Populate search table with existing data
            self.conn.execute("""
            INSERT INTO measure_search(fingerprint, title, description, ballot_question, summary_title, summary_text, county)
            SELECT fingerprint, title, description, ballot_question, summary_title, summary_text, county
            FROM measures
            WHERE fingerprint IS NOT NULL
            """)
            
            # Create trigger for future inserts
            self.conn.execute("""
            CREATE TRIGGER measure_search_insert 
            AFTER INSERT ON measures
            BEGIN
                INSERT INTO measure_search(fingerprint, title, description, ballot_question, summary_title, summary_text, county)
                VALUES (new.fingerprint, new.title, new.description, new.ballot_question, new.summary_title, new.summary_text, new.county);
            END
            """)
        except Exception as e:
            print(f"   ⚠️  Warning creating search table: {e}")
    
    def _create_analysis_views(self):
        """Create analysis views"""
        
        try:
            # Main public view (excludes duplicates)
            self.conn.execute("DROP VIEW IF EXISTS active_measures")
            self.conn.execute("""
            CREATE VIEW active_measures AS
            SELECT * FROM measures 
            WHERE is_active = 1 AND is_duplicate = 0
            ORDER BY year DESC, county, measure_letter
            """)
            
            # Cross-source unified view
            self.conn.execute("DROP VIEW IF EXISTS unique_measures")
            self.conn.execute("""
            CREATE VIEW unique_measures AS
            SELECT * FROM measures 
            WHERE is_duplicate = 0 OR duplicate_type = 'master'
            ORDER BY year DESC, county, measure_letter
            """)
            
            # Summary statistics view
            self.conn.execute("DROP VIEW IF EXISTS measure_stats")
            self.conn.execute("""
            CREATE VIEW measure_stats AS
            SELECT 
                year,
                COUNT(*) as total_measures,
                COUNT(DISTINCT county) as counties,
                SUM(CASE WHEN passed = 1 THEN 1 ELSE 0 END) as passed_count,
                SUM(CASE WHEN passed = 0 THEN 1 ELSE 0 END) as failed_count,
                SUM(CASE WHEN has_summary = 1 THEN 1 ELSE 0 END) as with_summaries,
                SUM(CASE WHEN yes_votes IS NOT NULL THEN 1 ELSE 0 END) as with_votes,
                ROUND(AVG(percent_yes), 1) as avg_percent_yes
            FROM active_measures
            GROUP BY year
            ORDER BY year DESC
            """)
            
            # Data quality view
            self.conn.execute("DROP VIEW IF EXISTS data_quality")
            self.conn.execute("""
            CREATE VIEW data_quality AS
            SELECT 
                data_source,
                COUNT(*) as total_records,
                SUM(CASE WHEN title IS NOT NULL THEN 1 ELSE 0 END) as has_title,
                SUM(CASE WHEN ballot_question IS NOT NULL THEN 1 ELSE 0 END) as has_question,
                SUM(CASE WHEN yes_votes IS NOT NULL THEN 1 ELSE 0 END) as has_votes,
                SUM(CASE WHEN passed IS NOT NULL THEN 1 ELSE 0 END) as has_outcome,
                SUM(CASE WHEN has_summary = 1 THEN 1 ELSE 0 END) as has_summary,
                COUNT(DISTINCT year) as years_covered
            FROM active_measures
            GROUP BY data_source
            """)
        except Exception as e:
            print(f"   ⚠️  Warning creating views: {e}")
    
    def create_fingerprint(self, measure_data: Dict) -> Tuple[str, str]:
        """Legacy method for compatibility - calls enhanced version"""
        unique_fp, measure_fp, content_hash = self.create_enhanced_fingerprint(measure_data)
        return unique_fp, content_hash
    
    def check_duplicate(self, fingerprint: str, content_hash: str) -> Optional[Dict]:
        """Check if measure already exists"""
        # First check exact fingerprint match
        cursor = self.conn.execute(
            "SELECT id, fingerprint, content_hash FROM measures WHERE fingerprint = ?",
            (fingerprint,)
        )
        exact_match = cursor.fetchone()
        if exact_match:
            return {'type': 'exact', 'id': exact_match['id']}
        
        # Check content hash for near-duplicates
        cursor = self.conn.execute(
            "SELECT id, fingerprint, title FROM measures WHERE content_hash = ? AND is_duplicate = 0",
            (content_hash,)
        )
        content_match = cursor.fetchone()
        if content_match:
            return {'type': 'content', 'id': content_match['id'], 'fingerprint': content_match['fingerprint']}
        
        return None
    
    def insert_or_update_measure(self, measure_data: Dict) -> Tuple[str, int]:
        """Insert new measure or update existing, returns (action, measure_id)"""
        # Generate fingerprints
        unique_fp, measure_fp, content_hash = self.create_enhanced_fingerprint(measure_data)
        measure_data['fingerprint'] = unique_fp
        measure_data['measure_fingerprint'] = measure_fp
        measure_data['content_hash'] = content_hash
        
        # Check for duplicates
        duplicate = self.check_duplicate(unique_fp, content_hash)
        
        if duplicate:
            if duplicate['type'] == 'exact':
                # Update existing record
                return self._update_measure(duplicate['id'], measure_data)
            else:
                # Mark as duplicate of content match
                measure_data['is_duplicate'] = True
                measure_data['master_id'] = duplicate['id']
                measure_data['duplicate_type'] = 'within_source'
                return self._insert_measure(measure_data), duplicate['id']
        else:
            # Insert new measure
            return self._insert_measure(measure_data), None
    
    def _insert_measure(self, measure_data: Dict) -> str:
        """Insert a new measure"""
        # Prepare data
        year = self._parse_year(measure_data.get('year'))
        if not year:
            return 'skipped'
        
        measure_data['year'] = year
        measure_data['decade'] = (year // 10) * 10
        measure_data['century'] = ((year - 1) // 100) + 1
        
        # Build insert statement
        fields = []
        values = []
        for key, value in measure_data.items():
            if value is not None and key in [
                'fingerprint', 'measure_fingerprint', 'content_hash', 'measure_id', 'measure_letter',
                'year', 'county', 'jurisdiction', 'title', 'description',
                'ballot_question', 'yes_votes', 'no_votes', 'total_votes',
                'percent_yes', 'percent_no', 'passed', 'pass_fail',
                'measure_type', 'topic_primary', 'topic_secondary',
                'category_type', 'category_topic', 'data_source',
                'source_url', 'pdf_url', 'has_summary', 'summary_title',
                'summary_text', 'election_type', 'election_date',
                'decade', 'century', 'is_duplicate', 'duplicate_type', 'master_id'
            ]:
                fields.append(key)
                values.append(value)
        
        placeholders = ['?' for _ in fields]
        sql = f"""
        INSERT INTO measures ({', '.join(fields)})
        VALUES ({', '.join(placeholders)})
        """
        
        try:
            cursor = self.conn.execute(sql, values)
            self.conn.commit()
            return 'inserted'
        except sqlite3.Error as e:
            print(f"   ⚠️  Error inserting measure: {e}")
            return 'error'
    
    def _update_measure(self, measure_id: int, new_data: Dict) -> Tuple[str, int]:
        """Update existing measure with change tracking"""
        # Get current data
        cursor = self.conn.execute("SELECT * FROM measures WHERE id = ?", (measure_id,))
        current = dict(cursor.fetchone())
        
        # Track what changed
        updates = []
        changes = []
        
        update_fields = [
            'yes_votes', 'no_votes', 'total_votes', 'percent_yes',
            'percent_no', 'passed', 'pass_fail', 'has_summary',
            'summary_title', 'summary_text', 'pdf_url', 'ballot_question'
        ]
        
        for field in update_fields:
            if field in new_data and new_data[field] != current[field]:
                if new_data[field] is not None:  # Only update if new value is not None
                    updates.append(f"{field} = ?")
                    changes.append((measure_id, field, current[field], new_data[field], new_data.get('data_source', 'Unknown')))
        
        if updates:
            # Update the measure
            sql = f"""
            UPDATE measures 
            SET {', '.join(updates)}, 
                updated_at = CURRENT_TIMESTAMP,
                update_count = update_count + 1,
                last_seen_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """
            values = [c[3] for c in changes] + [measure_id]
            self.conn.execute(sql, values)
            
            # Log changes
            for change in changes:
                self.conn.execute(
                    "INSERT INTO measure_updates (measure_id, field_name, old_value, new_value, update_source) VALUES (?, ?, ?, ?, ?)",
                    change
                )
            
            self.conn.commit()
            return 'updated', measure_id
        else:
            # Just update last_seen_at
            self.conn.execute(
                "UPDATE measures SET last_seen_at = CURRENT_TIMESTAMP WHERE id = ?",
                (measure_id,)
            )
            self.conn.commit()
            return 'unchanged', measure_id
    
    def _parse_year(self, year_value):
        """Parse year from various formats"""
        if not year_value or year_value == 'TBD' or year_value == 'Unknown':
            return None
        try:
            year = int(year_value)
            # Sanity check
            if 1800 <= year <= 2100:
                return year
        except:
            pass
        return None
    
    def load_ceda_data(self):
        """Load CEDA parsed data"""
        print("\n📊 Loading CEDA data...")
        
        csv_path = Path('data/ceda_combined.csv')
        if not csv_path.exists():
            print("   ❌ CEDA data not found. Run 'make parse-ceda' first")
            return
        
        df = pd.read_csv(csv_path)
        print(f"   Found {len(df)} CEDA records")
        
        inserted = 0
        updated = 0
        errors = 0
        
        for _, row in df.iterrows():
            measure_data = {
                'year': row.get('year'),
                'county': row.get('county'),
                'measure_letter': row.get('measure_letter'),
                'measure_id': row.get('measure_id'),
                'title': f"{row.get('county', 'Unknown')} Measure {row.get('measure_letter', '?')}" if pd.notna(row.get('measure_letter')) else None,
                'ballot_question': row.get('measure_text'),
                'yes_votes': row.get('yes_votes'),
                'no_votes': row.get('no_votes'),
                'total_votes': row.get('total_votes'),
                'percent_yes': row.get('percent_yes'),
                'pass_fail': row.get('pass_fail'),
                'passed': 1 if str(row.get('pass_fail')).lower() == 'pass' else 0 if str(row.get('pass_fail')).lower() == 'fail' else None,
                'measure_type': row.get('measure_type'),
                'category_type': row.get('rec_type_name'),
                'category_topic': row.get('rec_topic_name'),
                'data_source': 'CEDA'
            }
            
            action, _ = self.insert_or_update_measure(measure_data)
            if action == 'inserted':
                inserted += 1
            elif action == 'updated':
                updated += 1
            elif action == 'error':
                errors += 1
        
        print(f"   ✅ CEDA import complete: {inserted} inserted, {updated} updated, {errors} errors")
    
    def load_scraped_data(self):
        """Load scraped data from JSON files"""
        scraped_files = ['data/enhanced_measures.json', 'data/all_measures.json']
        
        for file_path in scraped_files:
            if Path(file_path).exists():
                print(f"\n📄 Loading {file_path}...")
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    measures = data.get('measures', [])
                    
                print(f"   Found {len(measures)} measures")
                
                inserted = 0
                updated = 0
                errors = 0
                
                for measure in measures:
                    measure_data = {
                        'year': measure.get('year'),
                        'title': measure.get('measure_text'),
                        'description': measure.get('description'),
                        'ballot_question': measure.get('ballot_question'),
                        'data_source': measure.get('source', 'CA_SOS'),
                        'source_url': measure.get('source_url'),
                        'pdf_url': measure.get('pdf_url'),
                        'has_summary': measure.get('has_summary', False),
                        'summary_title': measure.get('summary_title'),
                        'summary_text': measure.get('summary_text'),
                        'yes_votes': measure.get('yes_votes'),
                        'no_votes': measure.get('no_votes'),
                        'total_votes': measure.get('total_votes'),
                        'percent_yes': measure.get('percent_yes'),
                        'pass_fail': measure.get('pass_fail'),
                        'county': measure.get('county', 'Statewide'),
                        'measure_letter': measure.get('measure_letter')
                    }
                    
                    action, _ = self.insert_or_update_measure(measure_data)
                    if action == 'inserted':
                        inserted += 1
                    elif action == 'updated':
                        updated += 1
                    elif action == 'error':
                        errors += 1
                
                print(f"   ✅ Import complete: {inserted} inserted, {updated} updated, {errors} errors")
                break  # Only load the first file found
    
    def get_measures_for_website(self) -> List[Dict]:
        """Get all measures formatted for website generation"""
        cursor = self.conn.execute("""
            SELECT 
                fingerprint,
                year,
                county,
                measure_letter,
                title,
                COALESCE(title, 
                    CASE 
                        WHEN measure_letter IS NOT NULL THEN county || ' Measure ' || measure_letter
                        ELSE ballot_question
                    END
                ) as measure_text,
                ballot_question,
                description,
                summary_text,
                summary_title,
                has_summary,
                yes_votes,
                no_votes,
                total_votes,
                percent_yes,
                pass_fail,
                passed,
                measure_type,
                category_type,
                category_topic,
                data_source,
                source_url,
                pdf_url,
                updated_at
            FROM active_measures
            ORDER BY year DESC, county, measure_letter
        """)
        
        measures = []
        for row in cursor:
            measure = dict(row)
            # Convert SQLite boolean to Python boolean
            measure['has_summary'] = bool(measure['has_summary'])
            # Set source for display
            measure['source'] = measure['data_source'] or 'Historical'
            measures.append(measure)
        
        return measures
    
    def get_statistics(self) -> Dict:
        """Get database statistics"""
        stats = {}
        
        # Total measures
        cursor = self.conn.execute("SELECT COUNT(*) FROM active_measures")
        stats['total_measures'] = cursor.fetchone()[0]
        
        # With summaries
        cursor = self.conn.execute("SELECT COUNT(*) FROM active_measures WHERE has_summary = 1")
        stats['measures_with_summaries'] = cursor.fetchone()[0]
        
        # With votes
        cursor = self.conn.execute("SELECT COUNT(*) FROM active_measures WHERE yes_votes IS NOT NULL")
        stats['measures_with_votes'] = cursor.fetchone()[0]
        
        # Year range
        cursor = self.conn.execute("SELECT MIN(year), MAX(year) FROM active_measures WHERE year IS NOT NULL")
        min_year, max_year = cursor.fetchone()
        stats['year_range'] = f"{min_year}-{max_year}" if min_year else "Unknown"
        
        # By source
        cursor = self.conn.execute("""
            SELECT data_source, COUNT(*) 
            FROM active_measures 
            GROUP BY data_source
        """)
        stats['by_source'] = dict(cursor.fetchall())
        
        return stats
    
    def log_scraper_run(self, run_type: str) -> int:
        """Start a new scraper run log"""
        cursor = self.conn.execute(
            "INSERT INTO scraper_runs (run_type, status) VALUES (?, 'running')",
            (run_type,)
        )
        self.conn.commit()
        return cursor.lastrowid
    
    def update_scraper_run(self, run_id: int, **kwargs):
        """Update scraper run with results"""
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
            self.conn.execute(sql, values)
            self.conn.commit()


def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(description='Setup California Ballot Measures Database')
    parser.add_argument('--fresh', action='store_true', 
                       help='Start with a fresh database (backup existing)')
    parser.add_argument('--no-backup', action='store_true',
                       help='Skip backup when using --fresh')
    parser.add_argument('--dedupe', action='store_true',
                       help='Run cross-source deduplication after setup')
    
    args = parser.parse_args()
    
    print("🚀 Enhanced California Ballot Measures Database Setup")
    print("=" * 60)
    
    # Ensure data directory exists
    Path('data').mkdir(exist_ok=True)
    
    # Handle fresh database request
    db_path = Path('data/ballot_measures.db')
    if args.fresh and db_path.exists():
        if not args.no_backup:
            backup_path = Path(f'data/ballot_measures.db.backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}')
            print(f"📦 Backing up existing database to {backup_path}")
            shutil.copy2(db_path, backup_path)
        
        print("🗑️  Removing existing database for fresh start...")
        db_path.unlink()
    
    # Initialize database
    db = EnhancedBallotDatabase()
    
    try:
        db.connect()
        
        # Create enhanced schema
        db.create_enhanced_schema()
        
        # Load all data sources
        print("\n📥 Loading data sources...")
        
        # Load scraped data
        db.load_scraped_data()
        
        # Load CEDA data
        db.load_ceda_data()
        
        # Run cross-source deduplication if requested
        if args.dedupe:
            db.handle_cross_source_deduplication()
        
        # Generate summary
        stats = db.get_statistics()
        print("\n📊 Database Summary")
        print("=" * 50)
        print(f"Total measures: {stats['total_measures']}")
        print(f"With summaries: {stats['measures_with_summaries']}")
        print(f"With vote data: {stats['measures_with_votes']}")
        print(f"Year range: {stats['year_range']}")
        print("\nBy source:")
        for source, count in stats['by_source'].items():
            print(f"  {source}: {count}")
        
        print("\n✅ Enhanced database ready!")
        print("   Location: data/ballot_measures.db")
        
        if not args.dedupe:
            print("\n💡 Tip: Run 'python setup_ballot_database.py --dedupe' to handle cross-source duplicates")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()