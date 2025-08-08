"""
Summary generation for ballot measures
"""
import re
import time
import logging
from typing import Dict, List, Optional
from datetime import datetime

from ..database.models import BallotMeasure
from ..database.operations import Database
from ..config import SUMMARY_CONFIG, KNOWN_SUMMARIES

logger = logging.getLogger(__name__)


class SummaryGenerator:
    """Generates summaries for ballot measures"""
    
    def __init__(self, database: Database = None):
        self.db = database or Database()
        self.enabled = SUMMARY_CONFIG['enabled']
        self.max_attempts = SUMMARY_CONFIG['max_attempts']
        self.rate_limit = SUMMARY_CONFIG['rate_limit']
        self.last_request_time = 0
        self.summary_count = 0
        
    def enrich_measures(self, limit: Optional[int] = None):
        """Enrich measures with summaries"""
        if not self.enabled:
            logger.info("Summary generation is disabled")
            return
            
        logger.info("Starting summary enrichment...")
        
        # Get measures that need summaries
        measures = self._get_measures_needing_summaries(limit)
        logger.info(f"Found {len(measures)} measures needing summaries")
        
        # Process each measure
        for measure in measures:
            if self.summary_count >= self.max_attempts:
                logger.info(f"Reached maximum attempts limit ({self.max_attempts})")
                break
                
            self._generate_summary_for_measure(measure)
            
        logger.info(f"Summary enrichment complete: {self.summary_count} summaries generated")
    
    def _get_measures_needing_summaries(self, limit: Optional[int]) -> List[BallotMeasure]:
        """Get measures that don't have summaries"""
        conn = self.db.connect()
        
        # Priority order: recent measures first, then by importance
        query = """
        SELECT * FROM active_measures
        WHERE has_summary = 0
        AND (
            year >= 2020 OR
            measure_id LIKE 'ACA_%' OR
            measure_id LIKE 'SCA_%' OR
            measure_id LIKE 'PROP_%'
        )
        ORDER BY 
            year DESC,
            CASE 
                WHEN measure_id LIKE 'ACA_%' THEN 1
                WHEN measure_id LIKE 'SCA_%' THEN 2
                WHEN measure_id LIKE 'PROP_%' THEN 3
                ELSE 4
            END
        """
        
        if limit:
            query += f" LIMIT {limit}"
            
        cursor = conn.execute(query)
        
        measures = []
        for row in cursor:
            measures.append(BallotMeasure.from_dict(dict(row)))
            
        return measures
    
    def _generate_summary_for_measure(self, measure: BallotMeasure):
        """Generate summary for a single measure"""
        # First check known summaries
        measure_key = self._extract_measure_key(measure)
        
        if measure_key in KNOWN_SUMMARIES:
            summary_info = KNOWN_SUMMARIES[measure_key]
            self._save_summary(measure, summary_info)
            return
            
        # Otherwise attempt to generate
        summary_info = self._search_for_summary(measure)
        if summary_info:
            self._save_summary(measure, summary_info)
    
    def _extract_measure_key(self, measure: BallotMeasure) -> Optional[str]:
        """Extract measure key like 'ACA 13', 'SCA 1', etc."""
        text = measure.title or measure.ballot_question or ''
        
        # Try to match common patterns
        patterns = [
            r'\b(ACA\s+\d+)\b',
            r'\b(SCA\s+\d+)\b',
            r'\b(AB\s+\d+)\b',
            r'\b(SB\s+\d+)\b',
            r'\b(Prop(?:osition)?\s+\d+[A-Z]?)\b'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).upper().replace('PROPOSITION', 'Prop')
                
        return None
    
    def _search_for_summary(self, measure: BallotMeasure) -> Optional[Dict]:
        """Search for summary information (placeholder for future implementation)"""
        # Rate limiting
        self._rate_limit()
        
        # In a real implementation, this would:
        # 1. Search legislative websites
        # 2. Query APIs for ballot measure information
        # 3. Use NLP to extract key points
        
        # For now, we'll just log the attempt
        logger.debug(f"Searching for summary: {measure.title}")
        self.summary_count += 1
        
        # Placeholder - in production this would do actual searching
        return None
    
    def _save_summary(self, measure: BallotMeasure, summary_info: Dict):
        """Save summary to database"""
        updates = {
            'has_summary': True,
            'summary_title': summary_info.get('title'),
            'summary_text': summary_info.get('summary'),
            'updated_at': datetime.now()
        }
        
        self.db.update_measure(measure.id, updates)
        self.summary_count += 1
        
        logger.info(f"Added summary for: {measure.title}")
    
    def _rate_limit(self):
        """Ensure we don't make requests too frequently"""
        elapsed = time.time() - self.last_request_time
        wait_time = self.rate_limit - elapsed
        
        if wait_time > 0:
            time.sleep(wait_time)
            
        self.last_request_time = time.time()
    
    def add_known_summary(self, measure_key: str, title: str, summary: str):
        """Add a summary to the known summaries"""
        KNOWN_SUMMARIES[measure_key] = {
            'title': title,
            'summary': summary
        }
        
        # Also update any existing measures with this key
        conn = self.db.connect()
        
        # Find measures matching this key
        pattern = f"%{measure_key}%"
        cursor = conn.execute(
            """SELECT id FROM active_measures 
            WHERE (title LIKE ? OR ballot_question LIKE ?) 
            AND has_summary = 0""",
            (pattern, pattern)
        )
        
        updated = 0
        for row in cursor:
            measure = self.db.get_measure(row['id'])
            if measure and self._extract_measure_key(measure) == measure_key:
                self._save_summary(measure, KNOWN_SUMMARIES[measure_key])
                updated += 1
                
        if updated:
            logger.info(f"Updated {updated} existing measures with summary for {measure_key}")
    
    def get_summary_statistics(self) -> Dict:
        """Get statistics about summaries"""
        conn = self.db.connect()
        
        stats = {}
        
        # Total with summaries
        cursor = conn.execute(
            "SELECT COUNT(*) as count FROM active_measures WHERE has_summary = 1"
        )
        stats['total_with_summaries'] = cursor.fetchone()['count']
        
        # By year
        cursor = conn.execute("""
            SELECT year, 
                   COUNT(*) as total,
                   SUM(CASE WHEN has_summary = 1 THEN 1 ELSE 0 END) as with_summary
            FROM active_measures
            WHERE year >= 2020
            GROUP BY year
            ORDER BY year DESC
        """)
        
        stats['by_year'] = []
        for row in cursor:
            coverage = (row['with_summary'] / row['total'] * 100) if row['total'] > 0 else 0
            stats['by_year'].append({
                'year': row['year'],
                'total': row['total'],
                'with_summary': row['with_summary'],
                'coverage_percent': round(coverage, 1)
            })
            
        # By measure type
        cursor = conn.execute("""
            SELECT 
                CASE 
                    WHEN measure_id LIKE 'ACA_%' THEN 'Constitutional Amendment (ACA)'
                    WHEN measure_id LIKE 'SCA_%' THEN 'Constitutional Amendment (SCA)'
                    WHEN measure_id LIKE 'PROP_%' THEN 'Proposition'
                    WHEN measure_id LIKE 'MEASURE_%' THEN 'Local Measure'
                    ELSE 'Other'
                END as measure_type,
                COUNT(*) as total,
                SUM(CASE WHEN has_summary = 1 THEN 1 ELSE 0 END) as with_summary
            FROM active_measures
            GROUP BY measure_type
            ORDER BY with_summary DESC
        """)
        
        stats['by_type'] = []
        for row in cursor:
            coverage = (row['with_summary'] / row['total'] * 100) if row['total'] > 0 else 0
            stats['by_type'].append({
                'type': row['measure_type'],
                'total': row['total'],
                'with_summary': row['with_summary'],
                'coverage_percent': round(coverage, 1)
            })
            
        return stats