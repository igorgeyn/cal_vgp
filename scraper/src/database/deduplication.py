"""
Database deduplication logic
"""
import logging
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
import json

from .models import BallotMeasure
from .operations import Database

logger = logging.getLogger(__name__)


class Deduplicator:
    """Handles deduplication of ballot measures"""
    
    def __init__(self, database: Database):
        self.db = database
        
    def check_duplicate(self, measure: BallotMeasure) -> Optional[Dict]:
        """Check if a measure is a duplicate"""
        conn = self.db.connect()
        
        # First check exact fingerprint match
        existing = self.db.find_by_fingerprint(measure.fingerprint)
        if existing:
            return {
                'type': 'exact',
                'id': existing.id,
                'fingerprint': existing.fingerprint
            }
        
        # Check content hash for near-duplicates
        content_matches = self.db.find_by_content_hash(measure.content_hash)
        if content_matches:
            return {
                'type': 'content',
                'id': content_matches[0].id,
                'fingerprint': content_matches[0].fingerprint,
                'matches': len(content_matches)
            }
        
        # Check cross-source duplicates by measure_fingerprint
        cursor = conn.execute(
            """SELECT id, fingerprint, data_source 
            FROM measures 
            WHERE measure_fingerprint = ? AND is_duplicate = 0""",
            (measure.measure_fingerprint,)
        )
        
        cross_source = cursor.fetchone()
        if cross_source:
            return {
                'type': 'cross_source',
                'id': cross_source['id'],
                'fingerprint': cross_source['fingerprint'],
                'source': cross_source['data_source']
            }
        
        return None
    
    def find_cross_source_duplicates(self) -> List[Dict]:
        """Find measures that appear in multiple sources"""
        conn = self.db.connect()
        
        cursor = conn.execute("""
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
        
        duplicates = []
        for row in cursor:
            duplicates.append({
                'measure_fingerprint': row['measure_fingerprint'],
                'source_count': row['source_count'],
                'ids': [int(id) for id in row['ids'].split(',')],
                'sources': row['sources'].split(',')
            })
            
        logger.info(f"Found {len(duplicates)} cross-source duplicate groups")
        return duplicates
    
    def deduplicate_cross_source(self):
        """Handle cross-source deduplication"""
        logger.info("Starting cross-source deduplication...")
        
        duplicate_groups = self.find_cross_source_duplicates()
        
        for group in duplicate_groups:
            self._process_duplicate_group(group)
            
        self.db.conn.commit()
        logger.info(f"Processed {len(duplicate_groups)} duplicate groups")
    
    def _process_duplicate_group(self, group: Dict):
        """Process a group of cross-source duplicates"""
        ids = group['ids']
        
        # Get all versions of this measure
        versions = []
        for measure_id in ids:
            measure = self.db.get_measure(measure_id)
            if measure:
                versions.append(measure)
        
        if not versions:
            return
            
        # Select the best version as master
        master = self._select_master_record(versions)
        master_id = master.id
        
        logger.debug(f"Selected master record {master_id} for group {group['measure_fingerprint']}")
        
        # Merge data from other versions
        merged_data = self._merge_measure_data(versions, master_id)
        
        # Update master with merged data
        if merged_data:
            self.db.update_measure(master_id, merged_data)
        
        # Mark others as duplicates
        for measure in versions:
            if measure.id != master_id:
                self.db.update_measure(measure.id, {
                    'is_duplicate': True,
                    'duplicate_type': 'cross_source',
                    'master_id': master_id
                })
        
        # Store merge history
        merged_ids = [m.id for m in versions if m.id != master_id]
        if merged_ids:
            self.db.update_measure(master_id, {
                'merged_from': json.dumps(merged_ids)
            })
    
    def _select_master_record(self, versions: List[BallotMeasure]) -> BallotMeasure:
        """Select the best record to be master based on data quality"""
        # Priority order for sources
        source_priority = {
            'CA_SOS': 1,
            'CA_SOS_Scraper': 2,
            'NCSL': 3,
            'CEDA': 4,
            'ICPSR': 5,
            'UC_Law_SF': 6
        }
        
        # Score each version
        best_score = -1
        best_version = None
        
        for version in versions:
            score = 0
            
            # Has summary (highest priority)
            if version.has_summary:
                score += 100
            
            # Has vote data
            if version.yes_votes is not None:
                score += 50
            
            # Has description
            if version.description:
                score += 25
            
            # Has PDF
            if version.pdf_url and version.pdf_url != '#':
                score += 20
            
            # Has ballot question
            if version.ballot_question:
                score += 15
            
            # Source priority
            source_rank = source_priority.get(version.data_source, 10)
            score += (10 - source_rank) * 5
            
            # Recency (newer updates are better)
            if hasattr(version, 'updated_at'):
                # More recent updates get higher scores
                days_old = (datetime.now() - version.updated_at).days
                score += max(0, 30 - days_old)  # Up to 30 points for recent updates
            
            logger.debug(f"Version {version.id} ({version.data_source}) scored {score}")
            
            if score > best_score:
                best_score = score
                best_version = version
        
        return best_version
    
    def _merge_measure_data(self, versions: List[BallotMeasure], 
                           master_id: int) -> Dict:
        """Merge unique fields from all versions"""
        merged = {}
        
        # Fields to merge (prefer non-null values)
        merge_fields = [
            'description', 'ballot_question', 'summary_title', 'summary_text',
            'yes_votes', 'no_votes', 'total_votes', 'percent_yes', 'percent_no',
            'passed', 'pass_fail', 'pdf_url', 'source_url',
            'category_type', 'category_topic', 'election_date', 'election_type',
            'topic_primary', 'topic_secondary', 'measure_type'
        ]
        
        # Collect all non-null values for each field
        for field in merge_fields:
            values = []
            for version in versions:
                value = getattr(version, field, None)
                if value is not None and value != '':
                    values.append({
                        'value': value,
                        'source': version.data_source,
                        'id': version.id,
                        'updated_at': getattr(version, 'updated_at', None)
                    })
            
            if values:
                # For most fields, prefer value from master if available
                master_value = next((v for v in values if v['id'] == master_id), None)
                if master_value:
                    merged[field] = master_value['value']
                else:
                    # Otherwise take most recent or highest priority source
                    values.sort(key=lambda x: (
                        x['updated_at'] if x['updated_at'] else datetime.min,
                        -self._get_source_priority(x['source'])
                    ), reverse=True)
                    merged[field] = values[0]['value']
        
        # Special handling for vote data consistency
        if 'yes_votes' in merged and 'no_votes' in merged:
            total = merged.get('yes_votes', 0) + merged.get('no_votes', 0)
            if total > 0:
                merged['percent_yes'] = round((merged['yes_votes'] / total) * 100, 2)
                merged['percent_no'] = round((merged['no_votes'] / total) * 100, 2)
                merged['total_votes'] = total
                
                # Update pass/fail based on percentage
                if merged['percent_yes'] > 50:
                    merged['passed'] = 1
                    merged['pass_fail'] = 'Pass'
                else:
                    merged['passed'] = 0
                    merged['pass_fail'] = 'Fail'
        
        return merged
    
    def _get_source_priority(self, source: str) -> int:
        """Get priority ranking for a data source"""
        priority = {
            'CA_SOS': 1,
            'CA_SOS_Scraper': 2,
            'NCSL': 3,
            'CEDA': 4,
            'ICPSR': 5,
            'UC_Law_SF': 6
        }
        return priority.get(source, 10)
    
    def find_content_duplicates(self, threshold: float = 0.8) -> List[Dict]:
        """Find potential duplicates based on content similarity"""
        # This is a placeholder for more sophisticated content matching
        # Could implement fuzzy matching, edit distance, etc.
        conn = self.db.connect()
        
        cursor = conn.execute("""
            SELECT content_hash, COUNT(*) as count
            FROM measures
            WHERE is_duplicate = 0
            GROUP BY content_hash
            HAVING count > 1
        """)
        
        content_groups = []
        for row in cursor:
            content_groups.append({
                'content_hash': row['content_hash'],
                'count': row['count']
            })
            
        return content_groups
    
    def mark_duplicate(self, duplicate_id: int, master_id: int, 
                      duplicate_type: str = 'content'):
        """Mark a measure as duplicate of another"""
        self.db.update_measure(duplicate_id, {
            'is_duplicate': True,
            'duplicate_type': duplicate_type,
            'master_id': master_id
        })
        
        logger.info(f"Marked measure {duplicate_id} as {duplicate_type} duplicate of {master_id}")
    
    def unmark_duplicate(self, measure_id: int):
        """Unmark a measure as duplicate"""
        self.db.update_measure(measure_id, {
            'is_duplicate': False,
            'duplicate_type': None,
            'master_id': None
        })
        
        logger.info(f"Unmarked measure {measure_id} as duplicate")
    
    def get_duplicate_report(self) -> Dict:
        """Generate a report on duplicates"""
        conn = self.db.connect()
        
        report = {
            'total_duplicates': 0,
            'by_type': {},
            'by_source': {},
            'cross_source_groups': 0
        }
        
        # Total duplicates
        cursor = conn.execute(
            "SELECT COUNT(*) as count FROM measures WHERE is_duplicate = 1"
        )
        report['total_duplicates'] = cursor.fetchone()['count']
        
        # By type
        cursor = conn.execute("""
            SELECT duplicate_type, COUNT(*) as count
            FROM measures
            WHERE is_duplicate = 1
            GROUP BY duplicate_type
        """)
        report['by_type'] = {row['duplicate_type']: row['count'] for row in cursor}
        
        # By source
        cursor = conn.execute("""
            SELECT data_source, COUNT(*) as count
            FROM measures
            WHERE is_duplicate = 1
            GROUP BY data_source
        """)
        report['by_source'] = {row['data_source']: row['count'] for row in cursor}
        
        # Cross-source groups
        report['cross_source_groups'] = len(self.find_cross_source_duplicates())
        
        return report