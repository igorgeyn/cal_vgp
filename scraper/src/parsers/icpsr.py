"""
ICPSR (Inter-university Consortium for Political and Social Research) Data Parser
Handles historical ballot measures data from 1902-2016
"""
import pandas as pd
import logging
from pathlib import Path
from typing import List, Dict, Optional
import re

logger = logging.getLogger(__name__)

class ICPSRParser:
    """Parser for ICPSR historical ballot measures CSV file"""
    
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.file_paths = [
            data_dir / 'downloaded' / 'ncslballotmeasures_icpsr_1902_2016.csv',
            data_dir / 'raw' / 'ncslballotmeasures_icpsr_1902_2016.csv',
            data_dir.parent / 'downloaded' / 'ncslballotmeasures_icpsr_1902_2016.csv',
            data_dir / 'downloaded' / 'icpsr_ballot_measures.csv',
            data_dir / 'raw' / 'icpsr_ballot_measures.csv'
        ]
    
    def find_file(self) -> Optional[Path]:
        """Find the ICPSR file in various possible locations"""
        for path in self.file_paths:
            if path.exists():
                logger.info(f"Found ICPSR file at: {path}")
                return path
        
        logger.warning("ICPSR file not found in any expected location")
        return None
    
    def parse(self) -> List[Dict]:
        """Parse ICPSR data and return standardized records"""
        file_path = self.find_file()
        if not file_path:
            logger.error("Cannot parse ICPSR data - file not found")
            return []
        
        try:
            logger.info(f"Parsing ICPSR data from {file_path}")
            
            # Read CSV with various encoding attempts
            encodings = ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252']
            df = None
            
            for encoding in encodings:
                try:
                    df = pd.read_csv(file_path, encoding=encoding)
                    logger.info(f"Successfully read file with {encoding} encoding")
                    break
                except UnicodeDecodeError:
                    continue
            
            if df is None:
                logger.error("Could not read ICPSR file with any encoding")
                return []
            
            # Filter for California
            if 'state' in df.columns:
                ca_df = df[df['state'].str.upper() == 'CALIFORNIA'].copy()
            elif 'State' in df.columns:
                ca_df = df[df['State'].str.upper() == 'CALIFORNIA'].copy()
            else:
                logger.warning("No state column found in ICPSR data")
                return []
            
            logger.info(f"Found {len(ca_df)} California measures in ICPSR data")
            
            measures = []
            for _, row in ca_df.iterrows():
                measure = self._standardize_record(row)
                if measure:
                    measures.append(measure)
            
            logger.info(f"Successfully parsed {len(measures)} ICPSR measures")
            return measures
            
        except Exception as e:
            logger.error(f"Error parsing ICPSR data: {e}")
            return []
    
    def _standardize_record(self, row) -> Optional[Dict]:
        """Convert ICPSR row to standardized format"""
        try:
            # Extract year - ICPSR uses various column names
            year = None
            for year_col in ['year', 'Year', 'YEAR', 'election_year']:
                if year_col in row and pd.notna(row[year_col]):
                    year = self._parse_year(row[year_col])
                    if year:
                        break
            
            if not year:
                return None
            
            # Build standardized record
            measure = {
                'year': year,
                'state': 'CA',
                'source': 'ICPSR',
                'measure_id': self._get_value(row, ['measure_id', 'MeasureID', 'ID']),
                'title': self._get_value(row, ['title', 'Title', 'measure_title', 'ballot_title']),
                'description': self._get_value(row, ['description', 'Description', 'summary', 'ballot_summary']),
                'measure_type': self._get_value(row, ['type', 'Type', 'measure_type', 'initiative_type']),
                'topic_primary': self._get_value(row, ['topic', 'Topic', 'subject', 'Subject']),
                'status': self._get_value(row, ['status', 'Status', 'result', 'Result'])
            }
            
            # Parse vote data
            yes_votes = self._get_numeric_value(row, ['yes_votes', 'Yes_Votes', 'YES', 'yes'])
            no_votes = self._get_numeric_value(row, ['no_votes', 'No_Votes', 'NO', 'no'])
            
            if yes_votes is not None:
                measure['yes_votes'] = int(yes_votes)
            if no_votes is not None:
                measure['no_votes'] = int(no_votes)
            
            # Calculate percentages if we have vote data
            if yes_votes is not None and no_votes is not None:
                total = yes_votes + no_votes
                if total > 0:
                    measure['percent_yes'] = round((yes_votes / total) * 100, 2)
                    measure['percent_no'] = round((no_votes / total) * 100, 2)
                    measure['total_votes'] = int(total)
                    
                    # Determine pass/fail
                    if measure['percent_yes'] > 50:
                        measure['passed'] = 1
                        measure['pass_fail'] = 'Pass'
                    else:
                        measure['passed'] = 0
                        measure['pass_fail'] = 'Fail'
            
            # Try to get pass/fail from status if not calculated
            if 'passed' not in measure and measure.get('status'):
                status_lower = str(measure['status']).lower()
                if 'pass' in status_lower or 'adopt' in status_lower or 'approv' in status_lower:
                    measure['passed'] = 1
                    measure['pass_fail'] = 'Pass'
                elif 'fail' in status_lower or 'defeat' in status_lower or 'reject' in status_lower:
                    measure['passed'] = 0
                    measure['pass_fail'] = 'Fail'
            
            # Clean empty strings
            for key, value in measure.items():
                if value == '' or (isinstance(value, str) and value.lower() == 'nan'):
                    measure[key] = None
            
            return measure
            
        except Exception as e:
            logger.warning(f"Error standardizing ICPSR record: {e}")
            return None
    
    def _get_value(self, row, possible_columns: list) -> Optional[str]:
        """Get value from row trying multiple possible column names"""
        for col in possible_columns:
            if col in row and pd.notna(row[col]):
                return str(row[col])
        return None
    
    def _get_numeric_value(self, row, possible_columns: list) -> Optional[float]:
        """Get numeric value from row trying multiple possible column names"""
        for col in possible_columns:
            if col in row and pd.notna(row[col]):
                try:
                    # Remove commas and convert to float
                    value = str(row[col]).replace(',', '')
                    return float(value)
                except (ValueError, TypeError):
                    continue
        return None
    
    def _parse_year(self, year_value) -> Optional[int]:
        """Parse year from various formats"""
        if pd.isna(year_value):
            return None
        
        try:
            # Handle string years like "2016" or "2016.0"
            year_str = str(year_value).split('.')[0]
            year = int(year_str)
            
            # Sanity check for historical data
            if 1900 <= year <= 2030:
                return year
        except (ValueError, TypeError):
            pass
        
        return None
    
    def validate_data(self, measures: List[Dict]) -> Dict:
        """Validate parsed data and return statistics"""
        stats = {
            'total_records': len(measures),
            'years': set(),
            'decades': {},
            'has_title': 0,
            'has_vote_data': 0,
            'has_outcome': 0,
            'topics': set()
        }
        
        for measure in measures:
            year = measure.get('year')
            if year:
                stats['years'].add(year)
                decade = (year // 10) * 10
                stats['decades'][decade] = stats['decades'].get(decade, 0) + 1
            
            if measure.get('title'):
                stats['has_title'] += 1
            if measure.get('yes_votes') is not None:
                stats['has_vote_data'] += 1
            if measure.get('passed') is not None:
                stats['has_outcome'] += 1
            if measure.get('topic_primary'):
                stats['topics'].add(measure['topic_primary'])
        
        # Convert sets to lists for JSON serialization
        stats['years'] = sorted(list(stats['years']))
        stats['topics'] = sorted(list(stats['topics']))
        stats['year_range'] = f"{min(stats['years'])}-{max(stats['years'])}" if stats['years'] else "N/A"
        
        return stats
    
    def get_summary_stats(self) -> Dict:
        """Get summary statistics without parsing all data"""
        file_path = self.find_file()
        if not file_path:
            return {'error': 'ICPSR file not found'}
        
        try:
            # Quick read to get basic stats
            df = pd.read_csv(file_path, nrows=100)  # Sample first 100 rows
            
            # Find state column
            state_col = None
            for col in ['state', 'State', 'STATE']:
                if col in df.columns:
                    state_col = col
                    break
            
            ca_count = 0
            if state_col:
                ca_count = len(df[df[state_col].str.upper() == 'CALIFORNIA'])
            
            return {
                'file_found': True,
                'file_path': str(file_path),
                'total_rows_sampled': len(df),
                'california_measures_in_sample': ca_count,
                'columns': list(df.columns)[:20]  # First 20 columns
            }
        except Exception as e:
            return {'error': str(e)}