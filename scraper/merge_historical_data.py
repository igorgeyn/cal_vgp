#!/usr/bin/env python3
"""
Merge Historical Ballot Measure Data
Combines scraped CA ballot measures with NCSL and ICPSR national datasets
"""

import pandas as pd
import json
from pathlib import Path
import numpy as np
from datetime import datetime

def load_scraped_data():
    """Load the scraped California ballot measure data"""
    print("📄 Loading scraped California data...")
    
    # Try enhanced data first, fall back to basic data
    data_files = [
        'data/enhanced_measures.json',
        'data/all_measures.json'
    ]
    
    for file_path in data_files:
        if Path(file_path).exists():
            with open(file_path, 'r') as f:
                data = json.load(f)
                measures = data.get('measures', [])
                print(f"   ✅ Loaded {len(measures)} scraped measures from {file_path}")
                return pd.DataFrame(measures)
    
    print("   ⚠️  No scraped data found")
    return pd.DataFrame()

def load_ncsl_data():
    """Load NCSL ballot measures data (2014-present)"""
    print("📊 Loading NCSL data (2014-present)...")
    
    # Check multiple possible locations
    file_paths = [
        Path('../downloaded/ncsl_ballot_measures_2014_present.xlsx'),
        Path('downloaded/ncsl_ballot_measures_2014_present.xlsx'),
        Path('data/downloaded/ncsl_ballot_measures_2014_present.xlsx')
    ]
    
    file_path = None
    for path in file_paths:
        if path.exists():
            file_path = path
            break
    
    if not file_path:
        print(f"   ❌ NCSL file not found in downloaded/, ../downloaded/, or data/downloaded/")
        return pd.DataFrame()
    
    try:
        # Read Excel file
        df = pd.read_excel(file_path)
        
        # Filter for California only
        ca_df = df[df['StateName'] == 'California'].copy()
        
        # Standardize column names
        ca_df.rename(columns={
            'Title': 'measure_text',
            'Year': 'year',
            'ID': 'measure_id',
            'PercentageVote': 'percent_yes',
            'Summary': 'summary',
            'IRTypeDefinition': 'measure_type',
            'IRStatusDefinition': 'status',
            'TOPICDESCRIPTION': 'topic'
        }, inplace=True)
        
        # Add source
        ca_df['source'] = 'NCSL'
        
        print(f"   ✅ Loaded {len(ca_df)} California measures from NCSL")
        return ca_df
        
    except Exception as e:
        print(f"   ❌ Error loading NCSL data: {e}")
        return pd.DataFrame()

def load_icpsr_data():
    """Load ICPSR historical ballot measures data (1902-2016)"""
    print("📚 Loading ICPSR historical data (1902-2016)...")
    
    # Check multiple possible locations
    file_paths = [
        Path('../downloaded/ncslballotmeasures_icpsr_1902_2016.csv'),
        Path('downloaded/ncslballotmeasures_icpsr_1902_2016.csv'),
        Path('data/downloaded/ncslballotmeasures_icpsr_1902_2016.csv')
    ]
    
    file_path = None
    for path in file_paths:
        if path.exists():
            file_path = path
            break
    
    if not file_path:
        print(f"   ❌ ICPSR file not found in downloaded/, ../downloaded/, or data/downloaded/")
        return pd.DataFrame()
    
    try:
        # Read CSV with explicit encoding
        df = pd.read_csv(file_path, encoding='cp1252')
        
        # Filter for California (state code 'CA' or full name)
        ca_df = df[(df['st'] == 'CA') | (df['state'] == 'California')].copy()
        
        # Standardize column names
        ca_df.rename(columns={
            'ballotname': 'measure_text',
            'ballotdescrip': 'description',
            'year': 'year',
            'ballotid': 'measure_id',
            'pctyesvotes': 'percent_yes',
            'passed': 'passed',
            'type': 'measure_type',
            'topicarea': 'topic'
        }, inplace=True)
        
        # Add source
        ca_df['source'] = 'ICPSR'
        
        # Convert year to numeric if it's not already
        ca_df['year'] = pd.to_numeric(ca_df['year'], errors='coerce')
        
        print(f"   ✅ Loaded {len(ca_df)} California measures from ICPSR")
        return ca_df
        
    except Exception as e:
        print(f"   ❌ Error loading ICPSR data: {e}")
        return pd.DataFrame()

def standardize_measure_text(text):
    """Standardize measure text for matching"""
    if pd.isna(text):
        return ""
    
    # Convert to string and uppercase
    text = str(text).upper()
    
    # Remove common variations
    text = text.replace("PROPOSITION", "PROP")
    text = text.replace("AMENDMENT", "AMEND")
    text = text.replace("MEASURE", "")
    
    # Remove extra whitespace
    text = ' '.join(text.split())
    
    return text

def merge_datasets(scraped_df, ncsl_df, icpsr_df):
    """Merge the three datasets intelligently"""
    print("\n🔄 Merging datasets...")
    
    all_dfs = []
    
    # Process scraped data
    if not scraped_df.empty:
        scraped_df['data_source'] = 'CA_SOS_Scraper'
        scraped_df['year'] = pd.to_numeric(scraped_df['year'], errors='coerce')
        all_dfs.append(scraped_df)
    
    # Process NCSL data
    if not ncsl_df.empty:
        ncsl_df['data_source'] = 'NCSL'
        # Select relevant columns
        ncsl_cols = ['measure_text', 'year', 'measure_id', 'percent_yes', 
                     'summary', 'measure_type', 'status', 'topic', 'source', 'data_source']
        ncsl_df = ncsl_df[[col for col in ncsl_cols if col in ncsl_df.columns]]
        all_dfs.append(ncsl_df)
    
    # Process ICPSR data  
    if not icpsr_df.empty:
        icpsr_df['data_source'] = 'ICPSR'
        # Select relevant columns
        icpsr_cols = ['measure_text', 'description', 'year', 'measure_id', 
                      'percent_yes', 'passed', 'measure_type', 'topic', 'source', 'data_source']
        icpsr_df = icpsr_df[[col for col in icpsr_cols if col in icpsr_df.columns]]
        all_dfs.append(icpsr_df)
    
    if not all_dfs:
        print("   ❌ No data to merge")
        return pd.DataFrame()
    
    # Combine all dataframes
    combined_df = pd.concat(all_dfs, ignore_index=True, sort=False)
    
    # Sort by year (newest first) and measure text
    combined_df = combined_df.sort_values(['year', 'measure_text'], 
                                          ascending=[False, True], 
                                          na_position='last')
    
    print(f"   ✅ Combined {len(combined_df)} total measures")
    
    # Handle duplicates in overlap years (2014-2016)
    print("\n🔍 Handling overlap period (2014-2016)...")
    overlap_years = [2014, 2015, 2016]
    
    for year in overlap_years:
        year_data = combined_df[combined_df['year'] == year]
        if len(year_data) > 0:
            # Create standardized text for matching
            year_data['std_text'] = year_data['measure_text'].apply(standardize_measure_text)
            
            # Find potential duplicates
            duplicates = year_data[year_data.duplicated(subset=['std_text'], keep=False)]
            if len(duplicates) > 0:
                print(f"   Found {len(duplicates)} potential duplicates in {year}")
    
    return combined_df

def enrich_with_metadata(df):
    """Add additional metadata and clean up the dataset"""
    print("\n✨ Enriching dataset...")
    
    # Add decade column
    df['decade'] = (df['year'] // 10) * 10
    
    # Add century column  
    df['century'] = ((df['year'] - 1) // 100) + 1
    
    # Clean percentage values
    if 'percent_yes' in df.columns:
        df['percent_yes'] = pd.to_numeric(df['percent_yes'], errors='coerce')
    
    # Add pass/fail status where missing
    if 'passed' in df.columns and 'percent_yes' in df.columns:
        # If passed is missing but we have vote percentage, infer it
        mask = df['passed'].isna() & df['percent_yes'].notna()
        df.loc[mask, 'passed'] = (df.loc[mask, 'percent_yes'] > 50).astype(int)
    
    # Create a unified ID column
    df['unified_id'] = df.apply(lambda row: 
        row.get('measure_id', '') or 
        f"{row.get('year', 'UNKNOWN')}_{row.get('measure_text', '')[:20]}", 
        axis=1
    )
    
    print("   ✅ Dataset enriched with metadata")
    return df

def generate_summary_stats(df):
    """Generate summary statistics for the merged dataset"""
    print("\n📊 Summary Statistics:")
    print("=" * 50)
    
    # Overall stats
    print(f"Total measures: {len(df)}")
    print(f"Year range: {df['year'].min():.0f} - {df['year'].max():.0f}")
    print(f"Sources: {', '.join(df['data_source'].unique())}")
    
    # By decade
    print("\nMeasures by decade:")
    decade_counts = df.groupby('decade').size().sort_index()
    for decade, count in decade_counts.items():
        if not pd.isna(decade):
            print(f"  {int(decade)}s: {count} measures")
    
    # By source
    print("\nMeasures by source:")
    source_counts = df.groupby('data_source').size()
    for source, count in source_counts.items():
        print(f"  {source}: {count} measures")
    
    # Pass rate (where available)
    if 'passed' in df.columns:
        passed_data = df[df['passed'].notna()]
        if len(passed_data) > 0:
            pass_rate = (passed_data['passed'].sum() / len(passed_data)) * 100
            print(f"\nOverall pass rate: {pass_rate:.1f}% (of {len(passed_data)} with known outcomes)")
    
    return {
        'total_measures': len(df),
        'year_min': int(df['year'].min()) if not df['year'].isna().all() else None,
        'year_max': int(df['year'].max()) if not df['year'].isna().all() else None,
        'sources': list(df['data_source'].unique()),
        'decade_counts': decade_counts.to_dict()
    }

def save_merged_data(df, stats):
    """Save the merged dataset"""
    print("\n💾 Saving merged data...")
    
    # Ensure data directory exists
    Path('data').mkdir(exist_ok=True)
    
    # Save as CSV
    csv_path = 'data/merged_ballot_measures.csv'
    df.to_csv(csv_path, index=False)
    print(f"   ✅ Saved CSV: {csv_path}")
    
    # Save as JSON with metadata
    json_data = {
        'generated_at': datetime.now().isoformat(),
        'statistics': stats,
        'total_measures': len(df),
        'measures': df.to_dict('records')
    }
    
    json_path = 'data/merged_ballot_measures.json'
    with open(json_path, 'w') as f:
        json.dump(json_data, f, indent=2, default=str)
    print(f"   ✅ Saved JSON: {json_path}")
    
    # Save a summary file
    summary_path = 'data/merge_summary.txt'
    with open(summary_path, 'w') as f:
        f.write("California Ballot Measures - Merged Dataset Summary\n")
        f.write("=" * 50 + "\n\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
        f.write(f"Total Measures: {len(df)}\n")
        f.write(f"Year Range: {stats['year_min']} - {stats['year_max']}\n")
        f.write(f"Data Sources: {', '.join(stats['sources'])}\n\n")
        f.write("Measures by Decade:\n")
        for decade, count in sorted(stats['decade_counts'].items()):
            if not pd.isna(decade):
                f.write(f"  {int(decade)}s: {count}\n")
    print(f"   ✅ Saved summary: {summary_path}")

def main():
    """Main execution function"""
    print("🚀 California Ballot Measures - Historical Data Merger")
    print("=" * 60)
    
    # Load all data sources
    scraped_df = load_scraped_data()
    ncsl_df = load_ncsl_data()
    icpsr_df = load_icpsr_data()
    
    # Check if we have any data
    if scraped_df.empty and ncsl_df.empty and icpsr_df.empty:
        print("\n❌ No data sources found. Please ensure data files are in place.")
        return
    
    # Merge datasets
    merged_df = merge_datasets(scraped_df, ncsl_df, icpsr_df)
    
    if merged_df.empty:
        print("\n❌ Failed to merge datasets")
        return
    
    # Enrich with metadata
    merged_df = enrich_with_metadata(merged_df)
    
    # Generate statistics
    stats = generate_summary_stats(merged_df)
    
    # Save results
    save_merged_data(merged_df, stats)
    
    print("\n✅ Data merge completed successfully!")
    print(f"📈 Total California ballot measures: {len(merged_df)}")
    print(f"📅 Spanning {stats['year_min']} to {stats['year_max']}")
    print("\n🎯 Next steps:")
    print("   - Review merged data in data/merged_ballot_measures.csv")
    print("   - Check data/merge_summary.txt for statistics")
    print("   - Run website generator to display historical data")

if __name__ == "__main__":
    main()