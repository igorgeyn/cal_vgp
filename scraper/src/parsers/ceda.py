"""
CEDA (California Elections Data Archive) parser
Handles format changes across years and standardizes data
"""
import pandas as pd
import numpy as np
import logging
from pathlib import Path
from typing import Dict, List, Optional
import json
from datetime import datetime

from ..config import PROCESSED_DATA_DIR, DATA_DIR
from ..database.models import BallotMeasure

logger = logging.getLogger(__name__)


class CEDAParser:
    """Parser for California Elections Data Archive files (1998-2024)"""
    
    def __init__(self, data_dir: Path = None):
        self.data_dir = data_dir or DATA_DIR / "downloaded"
        self.output_dir = PROCESSED_DATA_DIR
        
        # Column mappings based on analysis of actual CEDA files
        self.column_mappings = {
            # Ballot measure identifiers
            'measure_id': ['MeasID', 'MeasID_First', 'Multi_MeasID'],
            'measure_text': ['BALQUEST', 'ballot_question', 'question'],
            'measure_letter': ['LTR', 'letter', 'measure_letter'],
            'measure_type': ['MEASTYPE', 'type'],
            
            # Election info
            'election_date': ['DATE', 'election_date'],
            'year': ['YEAR', 'year'],
            
            # Vote data - handle variations with/without spaces
            'yes_votes': [' YES ', 'YES', ' YES_sum ', 'YES_sum', 'yes_votes'],
            'no_votes': [' NO ', 'NO', ' NO_sum ', 'NO_sum', 'no_votes'],
            'total_votes': [' TOTAL ', 'TOTAL', ' Total_sum ', 'Total_sum', 'total_votes'],
            
            # Geographic info
            'county': ['CNTYNAME', 'county', 'County'],
            'place': ['PLACE', 'place', 'city'],
            'jurisdiction': ['JUR', 'jurisdiction'],
            
            # Results
            'pass_fail': ['PASSFAIL', 'passfail_sum', 'pass_fail', 'outcome_text'],
            'percent_yes': ['PERCENT', 'Percent_sum', 'percent', 'yes_percent'],
            'outcome': ['outcome', 'Outcome_sum'],
            
            # Measure categorization
            'rec_type': ['RECTYPE', 'typerec'],
            'rec_type_name': ['RECTYPENAME', 'type_name'],
            'rec_topic': ['RECTOPIC', 'toprec'],  
            'rec_topic_name': ['RECTOPICNAME', 'topic_name']
        }
        
        # Sheet name patterns across years
        self.sheet_patterns = [
            'Measures {year}',      # 2024: "Measures 2024"
            'Measures_{year}',      # 2020: "Measures_2020"
            'Measures{year}',       # 2000-2010: "Measures2000"
            'measures{year}',       # 2015: "measures2015" (lowercase)
            'Measures',             # Generic fallback
            'measures'              # Lowercase fallback
        ]
    
    def parse_all_files(self) -> List[BallotMeasure]:
        """Parse all CEDA files in the directory"""
        files = sorted(self.data_dir.glob('ceda_data_*.xls*'))
        logger.info(f"Found {len(files)} CEDA files to parse")
        
        all_measures = []
        
        for filepath in files:
            measures = self.parse_file(filepath)
            all_measures.extend(measures)
        
        # Remove duplicates based on key fields
        all_measures = self._deduplicate_measures(all_measures)
        
        logger.info(f"Parsed {len(all_measures)} total measures from CEDA files")
        return all_measures
    
    def parse_file(self, filepath: Path) -> List[BallotMeasure]:
        """Parse a single CEDA file"""
        logger.info(f"Parsing CEDA file: {filepath.name}")
        
        try:
            # Extract year from filename
            year = filepath.stem.split('_')[-1]
            
            # Read Excel file
            if filepath.suffix == '.xls':
                excel_file = pd.ExcelFile(filepath, engine='xlrd')
            else:  # .xlsx
                excel_file = pd.ExcelFile(filepath)
            
            # Find the Measures sheet
            sheet_name = self._find_measures_sheet(excel_file, year)
            
            if not sheet_name:
                logger.warning(f"No measures sheet found in {filepath.name}")
                return []
            
            # Read the measures data
            df = pd.read_excel(excel_file, sheet_name=sheet_name)
            
            # Skip if it's candidate data
            if self._is_candidate_data(df):
                logger.info(f"Skipping candidate data in {filepath.name}")
                return []
            
            # Standardize the dataframe
            standardized_df = self._standardize_dataframe(df, year)
            
            # Convert to BallotMeasure objects
            measures = self._dataframe_to_measures(standardized_df)
            
            logger.info(f"Extracted {len(measures)} measures from {filepath.name}")
            return measures
            
        except Exception as e:
            logger.error(f"Error parsing {filepath.name}: {e}")
            return []
    
    def _find_measures_sheet(self, excel_file: pd.ExcelFile, year: str) -> Optional[str]:
        """Find the correct Measures sheet based on year patterns"""
        sheet_names = excel_file.sheet_names
        
        # Try year-specific patterns first
        for pattern in self.sheet_patterns:
            if '{year}' in pattern:
                sheet_name = pattern.format(year=year)
                if sheet_name in sheet_names:
                    return sheet_name
                # Try case-insensitive match
                for actual_sheet in sheet_names:
                    if sheet_name.lower() == actual_sheet.lower():
                        return actual_sheet
        
        # Try generic patterns
        for pattern in self.sheet_patterns:
            if '{year}' not in pattern:
                for actual_sheet in sheet_names:
                    if pattern.lower() in actual_sheet.lower():
                        return actual_sheet
        
        # Last resort: look for any sheet with 'measure' in name
        for sheet in sheet_names:
            if 'measure' in sheet.lower():
                return sheet
        
        return None
    
    def _is_candidate_data(self, df: pd.DataFrame) -> bool:
        """Check if dataframe contains candidate data instead of measures"""
        if df is None or df.empty:
            return False
        
        # Look for candidate-specific columns
        candidate_indicators = ['candidate', 'CAND#', 'FIRST', 'LAST', 'party']
        cols_lower = [str(col).lower() for col in df.columns]
        
        for indicator in candidate_indicators:
            if any(indicator.lower() in col for col in cols_lower):
                return True
        
        # Check if we have measure-specific columns
        measure_indicators = ['BALQUEST', 'LTR', 'YES', 'NO']
        measure_count = sum(1 for indicator in measure_indicators 
                          if any(indicator.lower() in col.lower() for col in df.columns))
        
        return measure_count < 2
    
    def _find_column(self, df: pd.DataFrame, target_col: str) -> Optional[str]:
        """Find a column by checking multiple possible names"""
        if df is None or df.empty:
            return None
            
        # First try exact matches
        for possible_name in self.column_mappings.get(target_col, [target_col]):
            if possible_name in df.columns:
                return possible_name
        
        # Then try case-insensitive partial matches
        df_cols_lower = [col.lower() for col in df.columns]
        for possible_name in self.column_mappings.get(target_col, [target_col]):
            for i, col in enumerate(df_cols_lower):
                if possible_name.lower() in col:
                    return df.columns[i]
        
        return None
    
    def _standardize_dataframe(self, df: pd.DataFrame, year: str) -> pd.DataFrame:
        """Standardize a dataframe to common format"""
        if df is None or df.empty:
            return pd.DataFrame()
        
        standardized = pd.DataFrame()
        
        # Map columns
        for target_col, source_options in self.column_mappings.items():
            found_col = self._find_column(df, target_col)
            if found_col:
                standardized[target_col] = df[found_col]
        
        # Ensure we have year
        if 'year' not in standardized:
            standardized['year'] = int(year)
        
        # Clean numeric columns
        numeric_cols = ['yes_votes', 'no_votes', 'total_votes', 'percent_yes']
        for col in numeric_cols:
            if col in standardized:
                standardized[col] = pd.to_numeric(standardized[col], errors='coerce')
        
        # Calculate total votes if missing
        if 'total_votes' not in standardized or standardized['total_votes'].isna().all():
            if 'yes_votes' in standardized and 'no_votes' in standardized:
                standardized['total_votes'] = (
                    standardized['yes_votes'].fillna(0) + 
                    standardized['no_votes'].fillna(0)
                )
        
        # Calculate percent if missing
        if 'percent_yes' not in standardized or standardized['percent_yes'].isna().all():
            if 'yes_votes' in standardized and 'total_votes' in standardized:
                standardized['percent_yes'] = (
                    standardized['yes_votes'] / standardized['total_votes'] * 100
                ).round(2)
        
        # Add source info
        standardized['data_source'] = 'CEDA'
        
        return standardized
    
    def _dataframe_to_measures(self, df: pd.DataFrame) -> List[BallotMeasure]:
        """Convert dataframe rows to BallotMeasure objects"""
        measures = []
        
        for _, row in df.iterrows():
            # Skip if no meaningful data
            if pd.isna(row.get('measure_text')) and pd.isna(row.get('measure_letter')):
                continue
            
            # Create title
            county = row.get('county', 'Unknown')
            measure_letter = row.get('measure_letter')
            
            if pd.notna(measure_letter):
                title = f"{county} Measure {measure_letter}"
            else:
                title = row.get('measure_text', 'Unknown Measure')[:100]
            
            # Create measure
            measure = BallotMeasure(
                fingerprint="",  # Will be generated
                measure_fingerprint="",  # Will be generated
                content_hash="",  # Will be generated
                
                year=int(row.get('year', 0)) if pd.notna(row.get('year')) else None,
                county=county,
                measure_letter=measure_letter,
                measure_id=row.get('measure_id'),
                title=title,
                ballot_question=row.get('measure_text'),
                
                yes_votes=int(row.get('yes_votes')) if pd.notna(row.get('yes_votes')) else None,
                no_votes=int(row.get('no_votes')) if pd.notna(row.get('no_votes')) else None,
                total_votes=int(row.get('total_votes')) if pd.notna(row.get('total_votes')) else None,
                percent_yes=float(row.get('percent_yes')) if pd.notna(row.get('percent_yes')) else None,
                
                pass_fail=row.get('pass_fail'),
                passed=1 if str(row.get('pass_fail')).lower() == 'pass' else 0 if str(row.get('pass_fail')).lower() == 'fail' else None,
                
                measure_type=row.get('measure_type'),
                category_type=row.get('rec_type_name'),
                category_topic=row.get('rec_topic_name'),
                
                data_source='CEDA'
            )
            
            # Generate fingerprints
            measure.generate_fingerprints()
            
            measures.append(measure)
        
        return measures
    
    def _deduplicate_measures(self, measures: List[BallotMeasure]) -> List[BallotMeasure]:
        """Remove duplicate measures within CEDA data"""
        seen_fingerprints = set()
        unique_measures = []
        
        for measure in measures:
            if measure.fingerprint not in seen_fingerprints:
                seen_fingerprints.add(measure.fingerprint)
                unique_measures.append(measure)
        
        logger.info(f"Deduplicated {len(measures)} to {len(unique_measures)} unique measures")
        return unique_measures
    
    def save_parsed_data(self, measures: List[BallotMeasure]):
        """Save parsed data in multiple formats"""
        # Save as CSV
        csv_path = self.output_dir / 'ceda_parsed.csv'
        df = pd.DataFrame([m.to_dict() for m in measures])
        df.to_csv(csv_path, index=False)
        logger.info(f"Saved CSV: {csv_path}")
        
        # Save as JSON with summary
        summary = {
            'parsed_at': datetime.now().isoformat(),
            'total_measures': len(measures),
            'years_covered': sorted(list(set(m.year for m in measures if m.year))),
            'counties': sorted(list(set(m.county for m in measures if m.county))),
            'measures_with_votes': sum(1 for m in measures if m.yes_votes is not None),
            'measures_with_text': sum(1 for m in measures if m.ballot_question),
        }
        
        json_data = {
            'summary': summary,
            'measures': [m.to_dict() for m in measures]
        }
        
        json_path = self.output_dir / 'ceda_parsed.json'
        with open(json_path, 'w') as f:
            json.dump(json_data, f, indent=2, default=str)
        logger.info(f"Saved JSON: {json_path}")