#!/usr/bin/env python3
"""
CEDA Data Parser - Comprehensive parser for all years (1998-2024)
Updated based on analysis of actual CEDA files
Handles format changes and standardizes data across years
"""

import pandas as pd
import numpy as np
from pathlib import Path
import json
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

class CEDAParser:
    """Parser for California Elections Data Archive files (1998-2024)"""
    
    def __init__(self, data_dir='data/downloaded'):
        self.data_dir = Path(data_dir)
        self.output_dir = Path('data')
        self.output_dir.mkdir(exist_ok=True)
        
        # Based on analysis of actual CEDA files
        self.column_mappings = {
            # Ballot measure identifiers (from CEDA files)
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
    
    def find_column(self, df, target_col):
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
    
    def find_measures_sheet(self, excel_file, year):
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
    
    def parse_file(self, filepath):
        """Parse a single CEDA file, handling different formats"""
        print(f"\n📄 Parsing: {filepath.name}")
        
        try:
            # Extract year from filename
            year = filepath.stem.split('_')[-1]
            
            # Read Excel file
            if filepath.suffix == '.xls':
                excel_file = pd.ExcelFile(filepath, engine='xlrd')
            else:  # .xlsx
                excel_file = pd.ExcelFile(filepath)
            
            sheet_names = excel_file.sheet_names
            print(f"   Found sheets: {', '.join(sheet_names)}")
            
            # Find the Measures sheet
            measures_sheet = self.find_measures_sheet(excel_file, year)
            
            if not measures_sheet:
                print(f"   ⚠️  No measures sheet found")
                return None, None
            
            print(f"   ✅ Using sheet: {measures_sheet}")
            
            # Read the measures data
            measures_df = pd.read_excel(excel_file, sheet_name=measures_sheet)
            
            # Skip if it's actually candidate data
            if self.is_candidate_data(measures_df):
                print(f"   ⚠️  Sheet contains candidate data, skipping")
                return None, None
            
            print(f"   Loaded {len(measures_df)} rows, {len(measures_df.columns)} columns")
            
            # Add year if not present
            if 'YEAR' not in measures_df.columns and 'year' not in measures_df.columns:
                measures_df['YEAR'] = int(year)
            
            return measures_df, year
            
        except Exception as e:
            print(f"   ❌ Error reading {filepath.name}: {e}")
            return None, None
    
    def is_candidate_data(self, df):
        """Check if dataframe contains candidate data instead of measures"""
        if df is None or df.empty:
            return False
        
        # Look for candidate-specific columns
        candidate_indicators = ['candidate', 'CAND#', 'FIRST', 'LAST', 'party']
        cols_lower = [str(col).lower() for col in df.columns]
        
        for indicator in candidate_indicators:
            if any(indicator.lower() in col for col in cols_lower):
                return True
        
        # Also check if we have measure-specific columns
        measure_indicators = ['BALQUEST', 'LTR', 'YES', 'NO']
        measure_count = sum(1 for indicator in measure_indicators 
                          if any(indicator.lower() in col.lower() for col in df.columns))
        
        return measure_count < 2  # If we have fewer than 2 measure indicators, probably not measures
    
    def convert_numpy_types(self, obj):
        """Convert numpy types to native Python types for JSON serialization"""
        if isinstance(obj, np.bool_):
            return bool(obj)
        elif isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            if np.isnan(obj):
                return None
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, dict):
            return {k: self.convert_numpy_types(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self.convert_numpy_types(item) for item in obj]
        elif pd.isna(obj):
            return None
        else:
            return obj
    
    def standardize_dataframe(self, df, year):
        """Standardize a dataframe to common format"""
        if df is None or df.empty:
            return None
        
        standardized = pd.DataFrame()
        
        # Map columns
        column_mapping = {}
        for target_col, source_options in self.column_mappings.items():
            found_col = self.find_column(df, target_col)
            if found_col:
                column_mapping[target_col] = found_col
        
        # Create standardized dataframe with mapped columns
        for target, source in column_mapping.items():
            standardized[target] = df[source]
        
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
        
        # Convert Excel dates if present
        if 'election_date' in standardized:
            try:
                # Excel stores dates as numbers
                standardized['election_date'] = pd.to_datetime(
                    standardized['election_date'], 
                    unit='D', 
                    origin='1899-12-30',
                    errors='coerce'
                )
            except:
                pass
        
        # Add source info
        standardized['source'] = 'CEDA'
        
        print(f"   ✅ Standardized {len(standardized)} rows with {len(standardized.columns)} columns")
        
        return standardized
    
    def parse_all_files(self, analyze_only=False):
        """Parse all CEDA files in the directory"""
        files = sorted(self.data_dir.glob('ceda_data_*.xls*'))
        print(f"🔍 Found {len(files)} CEDA files")
        
        if analyze_only:
            # Just analyze structure
            for filepath in files:
                self.analyze_file_structure(filepath)
            return None
        
        all_data = []
        file_info = []
        
        for filepath in files:
            df, year = self.parse_file(filepath)
            
            if df is not None:
                # Standardize the data
                std_df = self.standardize_dataframe(df, year)
                
                if std_df is not None and len(std_df) > 0:
                    all_data.append(std_df)
                    
                    # Track file info
                    info = {
                        'file': filepath.name,
                        'year': int(year),
                        'rows': len(std_df),
                        'has_ballot_text': std_df['measure_text'].notna().sum() if 'measure_text' in std_df else 0,
                        'has_votes': std_df['yes_votes'].notna().sum() if 'yes_votes' in std_df else 0
                    }
                    file_info.append(info)
                    
                    print(f"   📊 Extracted {info['rows']} measures, "
                          f"{info['has_ballot_text']} with text, "
                          f"{info['has_votes']} with vote data")
        
        if all_data:
            # Combine all dataframes
            combined_df = pd.concat(all_data, ignore_index=True)
            
            # Remove duplicates based on key columns
            if 'measure_id' in combined_df.columns:
                combined_df = combined_df.drop_duplicates(
                    subset=['measure_id', 'county', 'year'], 
                    keep='first'
                )
            
            # Sort by year (descending) and county
            sort_cols = []
            if 'year' in combined_df.columns:
                sort_cols.append('year')
            if 'county' in combined_df.columns:
                sort_cols.append('county')
            if sort_cols:
                combined_df = combined_df.sort_values(sort_cols, ascending=[False, True])
            
            print(f"\n✅ Combined data: {len(combined_df)} total rows")
            
            # Save outputs
            self.save_outputs(combined_df, file_info)
            
            return combined_df
        else:
            print("\n❌ No data could be parsed")
            return None
    
    def analyze_file_structure(self, filepath):
        """Analyze and report the structure of a CEDA file"""
        try:
            year = filepath.stem.split('_')[-1]
            
            if filepath.suffix == '.xls':
                excel_file = pd.ExcelFile(filepath, engine='xlrd')
            else:
                excel_file = pd.ExcelFile(filepath)
            
            print(f"\n📊 Analyzing: {filepath.name}")
            print(f"   Year: {year}")
            print(f"   Sheets: {', '.join(excel_file.sheet_names)}")
            
            # Find measures sheet
            measures_sheet = self.find_measures_sheet(excel_file, year)
            
            if measures_sheet:
                df = pd.read_excel(excel_file, sheet_name=measures_sheet)
                print(f"\n   Measures sheet: '{measures_sheet}'")
                print(f"     - Rows: {len(df)}")
                print(f"     - Columns: {len(df.columns)}")
                
                # Show key columns
                key_cols = ['MeasID', 'BALQUEST', 'LTR', 'YES', 'NO', 'PASSFAIL']
                found_cols = [col for col in key_cols if col in df.columns or f' {col} ' in df.columns]
                if found_cols:
                    print(f"     - Key columns found: {', '.join(found_cols)}")
                
                # Sample ballot question
                if 'BALQUEST' in df.columns:
                    sample_q = df['BALQUEST'].dropna().iloc[0] if not df['BALQUEST'].dropna().empty else None
                    if sample_q:
                        print(f"     - Sample question: {str(sample_q)[:80]}...")
            
            return True
            
        except Exception as e:
            print(f"   ❌ Error analyzing {filepath.name}: {e}")
            return False
    
    def save_outputs(self, df, file_info):
        """Save parsed data in multiple formats"""
        # Save combined CSV
        csv_path = self.output_dir / 'ceda_combined.csv'
        df.to_csv(csv_path, index=False)
        print(f"\n💾 Saved combined data: {csv_path}")
        
        # Prepare summary data
        summary_stats = {
            'total_measures': len(df),
            'unique_measure_ids': df['measure_id'].nunique() if 'measure_id' in df else 0,
            'counties_covered': df['county'].nunique() if 'county' in df else 0,
            'years_covered': sorted(df['year'].unique().tolist()) if 'year' in df else [],
            'measures_with_text': df['measure_text'].notna().sum() if 'measure_text' in df else 0,
            'measures_with_votes': df['yes_votes'].notna().sum() if 'yes_votes' in df else 0,
            'pass_rate': (df['pass_fail'] == 'Pass').mean() * 100 if 'pass_fail' in df else None
        }
        
        # Convert sample data
        sample_data = []
        if len(df) > 0:
            sample_df = df.head(10)
            for _, row in sample_df.iterrows():
                sample_data.append(self.convert_numpy_types(row.to_dict()))
        
        # Save summary JSON
        summary = {
            'generated_at': datetime.now().isoformat(),
            'statistics': self.convert_numpy_types(summary_stats),
            'files_processed': self.convert_numpy_types(file_info),
            'columns_available': df.columns.tolist(),
            'sample_data': sample_data
        }
        
        json_path = self.output_dir / 'ceda_summary.json'
        with open(json_path, 'w') as f:
            json.dump(summary, f, indent=2)
        print(f"📊 Saved summary: {json_path}")
        
        # Save year-by-year breakdown
        if 'year' in df:
            year_summary = []
            for year in sorted(df['year'].unique()):
                year_df = df[df['year'] == year]
                year_info = {
                    'year': int(year),
                    'total_records': len(year_df),
                    'unique_measures': year_df['measure_id'].nunique() if 'measure_id' in year_df else len(year_df),
                    'counties': sorted(year_df['county'].dropna().unique().tolist()) if 'county' in year_df else [],
                    'pass_rate': float((year_df['pass_fail'] == 'Pass').mean() * 100) if 'pass_fail' in year_df else None,
                    'total_yes_votes': int(year_df['yes_votes'].sum()) if 'yes_votes' in year_df else None,
                    'total_no_votes': int(year_df['no_votes'].sum()) if 'no_votes' in year_df else None
                }
                year_summary.append(self.convert_numpy_types(year_info))
            
            year_path = self.output_dir / 'ceda_by_year.json'
            with open(year_path, 'w') as f:
                json.dump(year_summary, f, indent=2)
            print(f"📅 Saved year summary: {year_path}")

def main():
    """Main function to run the parser"""
    parser = CEDAParser()
    
    print("🚀 CEDA Data Parser - Enhanced Edition")
    print("=" * 50)
    print("Based on analysis of actual CEDA file structures")
    
    # First, analyze file structures
    print("\n📋 Step 1: Analyzing file structures...")
    parser.parse_all_files(analyze_only=True)
    
    # Then parse and combine
    print("\n📋 Step 2: Parsing and standardizing data...")
    combined_df = parser.parse_all_files(analyze_only=False)
    
    if combined_df is not None:
        print("\n🎉 Parsing complete!")
        print(f"📊 Summary statistics:")
        print(f"   - Total records: {len(combined_df):,}")
        
        if 'year' in combined_df:
            print(f"   - Years covered: {sorted(combined_df['year'].unique())}")
        
        if 'county' in combined_df:
            print(f"   - Counties: {combined_df['county'].nunique()}")
        
        if 'pass_fail' in combined_df:
            pass_rate = (combined_df['pass_fail'] == 'Pass').mean() * 100
            print(f"   - Overall pass rate: {pass_rate:.1f}%")
        
        # Show sample measures
        if 'measure_text' in combined_df and combined_df['measure_text'].notna().any():
            print("\n📝 Sample ballot questions:")
            samples = combined_df[combined_df['measure_text'].notna()].head(3)
            for _, row in samples.iterrows():
                year = row.get('year', 'N/A')
                county = row.get('county', 'N/A')
                text = str(row.get('measure_text', ''))[:80]
                print(f"   - {year} {county}: {text}...")
        
        print("\n✅ Data saved to:")
        print("   - data/ceda_combined.csv (main dataset)")
        print("   - data/ceda_summary.json (statistics)")
        print("   - data/ceda_by_year.json (yearly breakdown)")

if __name__ == "__main__":
    main()