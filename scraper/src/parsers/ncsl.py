"""
NCSL (National Conference of State Legislatures) Data Parser
Handles ballot measures data from 2014-present
"""
import pandas as pd
import logging
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class NCSLParser:
    """Parser for NCSL ballot measures Excel files"""
    
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.file_paths = [
            data_dir / 'raw' / 'ncsl_ballot_measures_2014_present.xlsx',  # Check raw first
            data_dir / 'downloaded' / 'ncsl_ballot_measures_2014_present.xlsx',
            data_dir.parent / 'downloaded' / 'ncsl_ballot_measures_2014_present.xlsx'
        ]
    
    def find_file(self) -> Optional[Path]:
        """Find the NCSL file in various possible locations"""
        for path in self.file_paths:
            if path.exists():
                logger.info(f"Found NCSL file at: {path}")
                return path
        
        logger.warning("NCSL file not found in any expected location")
        return None
    
    def parse(self) -> List[Dict]:
        """Parse NCSL data and return standardized records"""
        file_path = self.find_file()
        if not file_path:
            logger.error("Cannot parse NCSL data - file not found")
            return []
        
        try:
            logger.info(f"Parsing NCSL data from {file_path}")
            df = pd.read_excel(file_path)
            
            # Filter for California — try multiple possible column names
            state_col = None
            for col_name in ['StateName', 'State', 'state', 'state_name']:
                if col_name in df.columns:
                    state_col = col_name
                    break
            if state_col is None:
                logger.error(f"NCSL: No state column found. Columns: {list(df.columns)}")
                return []

            ca_df = df[df[state_col] == 'California'].copy()
            logger.info(f"Found {len(ca_df)} California measures in NCSL data (state col: {state_col})")
            
            measures = []
            for _, row in ca_df.iterrows():
                measure = self._standardize_record(row)
                if measure:
                    measures.append(measure)
            
            logger.info(f"Successfully parsed {len(measures)} NCSL measures")
            return measures
            
        except Exception as e:
            logger.error(f"Error parsing NCSL data: {e}")
            return []
    
    def _standardize_record(self, row) -> Optional[Dict]:
        """Convert NCSL row to standardized format"""
        try:
            # Extract year
            year = self._parse_year(row.get('Year'))
            if not year:
                return None
            
            # Build standardized record — use get() with fallbacks for column name variants
            def _get(row, *keys):
                for k in keys:
                    v = row.get(k)
                    if v is not None and not (isinstance(v, float) and pd.isna(v)):
                        return str(v)
                return ''

            measure = {
                'year': year,
                'state': 'CA',
                'source': 'NCSL',
                'measure_id': _get(row, 'ID', 'id', 'MeasureID'),
                'title': _get(row, 'Title', 'title', 'MeasureTitle'),
                'description': _get(row, 'Summary', 'summary', 'Description'),
                'measure_type': _get(row, 'IRTypeDefinition', 'Type', 'type', 'MeasureType'),
                'topic_primary': _get(row, 'TOPICDESCRIPTION', 'Topic', 'topic', 'TopicDescription'),
                'status': _get(row, 'IRStatusDefinition', 'Status', 'status'),
                'election_type': _get(row, 'ElectionType', 'election_type', 'Election')
            }
            
            # Parse vote data
            percent_yes = row.get('PercentageVote')
            if pd.notna(percent_yes):
                try:
                    measure['percent_yes'] = float(percent_yes)
                    # Determine pass/fail based on percentage
                    if measure['percent_yes'] > 50:
                        measure['passed'] = 1
                        measure['pass_fail'] = 'Pass'
                    else:
                        measure['passed'] = 0
                        measure['pass_fail'] = 'Fail'
                except (ValueError, TypeError):
                    pass
            
            # Clean empty strings
            for key, value in measure.items():
                if value == '' or pd.isna(value):
                    measure[key] = None
            
            return measure
            
        except Exception as e:
            logger.warning(f"Error standardizing NCSL record: {e}")
            return None
    
    def _parse_year(self, year_value) -> Optional[int]:
        """Parse year from various formats"""
        if pd.isna(year_value):
            return None
        
        try:
            year = int(year_value)
            if 2014 <= year <= 2030:  # Sanity check
                return year
        except (ValueError, TypeError):
            pass
        
        return None
    
    def validate_data(self, measures: List[Dict]) -> Dict:
        """Validate parsed data and return statistics"""
        stats = {
            'total_records': len(measures),
            'years': set(),
            'has_title': 0,
            'has_vote_data': 0,
            'has_outcome': 0,
            'topics': set()
        }
        
        for measure in measures:
            if measure.get('year'):
                stats['years'].add(measure['year'])
            if measure.get('title'):
                stats['has_title'] += 1
            if measure.get('percent_yes') is not None:
                stats['has_vote_data'] += 1
            if measure.get('passed') is not None:
                stats['has_outcome'] += 1
            if measure.get('topic_primary'):
                stats['topics'].add(measure['topic_primary'])
        
        # Convert sets to lists for JSON serialization
        stats['years'] = sorted(list(stats['years']))
        stats['topics'] = sorted(list(stats['topics']))
        
        return stats
    
    def get_summary_stats(self) -> Dict:
        """Get summary statistics without parsing all data"""
        file_path = self.find_file()
        if not file_path:
            return {'error': 'NCSL file not found'}
        
        try:
            # Quick read to get basic stats
            df = pd.read_excel(file_path, nrows=100)  # Sample first 100 rows
            
            ca_count = len(df[df['StateName'] == 'California']) if 'StateName' in df.columns else 0
            
            return {
                'file_found': True,
                'file_path': str(file_path),
                'total_rows_sampled': len(df),
                'california_measures_in_sample': ca_count,
                'columns': list(df.columns)
            }
        except Exception as e:
            return {'error': str(e)}