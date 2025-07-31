#!/usr/bin/env python3
"""
CEDA Data Integration Script - Updated Version
Integrates parsed CEDA data with existing ballot measures from web scraping
Handles the actual CEDA column structure
"""

import pandas as pd
import json
from pathlib import Path
from datetime import datetime
import re

class CEDAIntegrator:
    """Integrates CEDA data with existing ballot measures data"""
    
    def __init__(self):
        self.data_dir = Path('data')
        
    def load_existing_measures(self):
        """Load existing scraped ballot measures"""
        # Try different possible files
        possible_files = [
            'enhanced_measures.json',
            'all_measures.json',
            'ballot_measures.json'
        ]
        
        for filename in possible_files:
            filepath = self.data_dir / filename
            if filepath.exists():
                print(f"📄 Loading existing measures from: {filename}")
                with open(filepath, 'r') as f:
                    data = json.load(f)
                    return data.get('measures', [])
        
        print("⚠️  No existing measures file found")
        return []
    
    def load_ceda_data(self):
        """Load parsed CEDA data"""
        csv_path = self.data_dir / 'ceda_combined.csv'
        if csv_path.exists():
            print(f"📊 Loading CEDA data from: {csv_path}")
            df = pd.read_csv(csv_path)
            print(f"   Loaded {len(df)} CEDA records")
            
            # Show available columns
            print(f"   CEDA columns: {', '.join(df.columns[:10])}...")
            
            return df
        else:
            print("❌ CEDA combined data not found. Run the parser first!")
            return None
    
    def extract_measure_identifier(self, text):
        """Extract measure identifier from text (e.g., 'Prop 8', 'ACA 13', 'Measure A')"""
        if pd.isna(text):
            return None
            
        text = str(text)
        
        # Patterns to match various measure formats
        patterns = [
            # State propositions: "Proposition 8", "Prop. 13"
            (r'(?:Proposition|Prop\.?)\s*(\d+[A-Z]?)', 'Prop {}'),
            # Constitutional amendments: "SCA 1", "ACA 13"
            (r'([AS]CA)\s*(\d+)', '{} {}'),
            # Assembly/Senate bills: "AB 440", "SB 1"
            (r'(AB|SB)\s*(\d+)', '{} {}'),
            # Local measures: "Measure A", "Measure AA"
            (r'(?:Measure)\s*([A-Z]+)', 'Measure {}'),
            # Simple letter measures: just "A", "B", etc.
            (r'^([A-Z]{1,2})$', 'Measure {}'),
        ]
        
        for pattern, format_str in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                groups = match.groups()
                return format_str.format(*groups).upper()
        
        return None
    
    def extract_proposition_number(self, text):
        """Extract just the proposition number for matching"""
        if pd.isna(text):
            return None
            
        # Look for "Proposition X" or "Prop X"
        match = re.search(r'(?:Proposition|Prop\.?)\s*(\d+)', str(text), re.IGNORECASE)
        if match:
            return match.group(1)
        return None
    
    def match_measures(self, existing_measures, ceda_df):
        """Match CEDA data with existing measures"""
        matches = []
        unmatched_ceda = []
        unmatched_existing = []
        
        # Create indices for matching
        print("\n🔄 Building matching indices...")
        
        # For CEDA data, we'll use multiple matching strategies
        ceda_index = {}
        for idx, row in ceda_df.iterrows():
            year = str(row.get('year', ''))
            
            # Strategy 1: Use measure letter (LTR field)
            if pd.notna(row.get('measure_letter')):
                letter_key = f"{year}_Measure_{row['measure_letter']}"
                if letter_key not in ceda_index:
                    ceda_index[letter_key] = []
                ceda_index[letter_key].append(idx)
            
            # Strategy 2: Extract from ballot question text
            if pd.notna(row.get('measure_text')):
                measure_id = self.extract_measure_identifier(row['measure_text'])
                if measure_id:
                    id_key = f"{year}_{measure_id}"
                    if id_key not in ceda_index:
                        ceda_index[id_key] = []
                    ceda_index[id_key].append(idx)
                
                # Also try proposition number
                prop_num = self.extract_proposition_number(row['measure_text'])
                if prop_num:
                    prop_key = f"{year}_Prop_{prop_num}"
                    if prop_key not in ceda_index:
                        ceda_index[prop_key] = []
                    ceda_index[prop_key].append(idx)
        
        print(f"   Created {len(ceda_index)} CEDA index entries")
        
        # Match existing measures
        matched_existing = set()
        for idx, measure in enumerate(existing_measures):
            measure_text = measure.get('measure_text', '')
            year = str(measure.get('year', ''))
            
            # Extract identifier from existing measure
            measure_id = self.extract_measure_identifier(measure_text)
            
            matched = False
            
            # Try different matching strategies
            if measure_id:
                # Direct ID match
                key = f"{year}_{measure_id}"
                if key in ceda_index:
                    for ceda_idx in ceda_index[key]:
                        ceda_row = ceda_df.iloc[ceda_idx]
                        matches.append({
                            'existing_idx': idx,
                            'ceda_idx': ceda_idx,
                            'measure_id': measure_id,
                            'year': year,
                            'existing_data': measure,
                            'ceda_data': ceda_row.to_dict(),
                            'match_type': 'id_match',
                            'match_confidence': 'high'
                        })
                        matched = True
                        matched_existing.add(idx)
                        break
                
                # Try proposition number match
                if not matched:
                    prop_num = self.extract_proposition_number(measure_text)
                    if prop_num:
                        prop_key = f"{year}_Prop_{prop_num}"
                        if prop_key in ceda_index:
                            for ceda_idx in ceda_index[prop_key]:
                                ceda_row = ceda_df.iloc[ceda_idx]
                                matches.append({
                                    'existing_idx': idx,
                                    'ceda_idx': ceda_idx,
                                    'measure_id': f"Prop {prop_num}",
                                    'year': year,
                                    'existing_data': measure,
                                    'ceda_data': ceda_row.to_dict(),
                                    'match_type': 'prop_number',
                                    'match_confidence': 'medium'
                                })
                                matched = True
                                matched_existing.add(idx)
                                break
            
            if not matched:
                unmatched_existing.append(measure)
        
        # Find unmatched CEDA records
        matched_ceda_indices = set()
        for match in matches:
            matched_ceda_indices.add(match['ceda_idx'])
        
        for idx, row in ceda_df.iterrows():
            if idx not in matched_ceda_indices:
                # Only include CEDA records that have meaningful data
                if pd.notna(row.get('measure_text')) or pd.notna(row.get('measure_letter')):
                    unmatched_ceda.append(row.to_dict())
        
        return {
            'matches': matches,
            'unmatched_ceda': unmatched_ceda[:100],  # Limit to first 100
            'unmatched_existing': unmatched_existing,
            'match_stats': {
                'total_existing': len(existing_measures),
                'total_ceda': len(ceda_df),
                'matched': len(matches),
                'unmatched_existing': len(unmatched_existing),
                'unmatched_ceda': len([idx for idx in range(len(ceda_df)) 
                                     if idx not in matched_ceda_indices])
            }
        }
    
    def enrich_existing_measures(self, existing_measures, matches):
        """Enrich existing measures with CEDA data"""
        enriched = []
        
        # Create a lookup for matches
        match_lookup = {}
        for match in matches:
            match_lookup[match['existing_idx']] = match
        
        for idx, measure in enumerate(existing_measures):
            enriched_measure = measure.copy()
            
            if idx in match_lookup:
                match = match_lookup[idx]
                ceda_data = match['ceda_data']
                
                # Add CEDA fields
                enriched_measure['ceda_matched'] = True
                enriched_measure['match_confidence'] = match['match_confidence']
                
                # Add vote data (ensure proper type conversion)
                if pd.notna(ceda_data.get('yes_votes')):
                    enriched_measure['yes_votes'] = int(ceda_data.get('yes_votes'))
                if pd.notna(ceda_data.get('no_votes')):
                    enriched_measure['no_votes'] = int(ceda_data.get('no_votes'))
                if pd.notna(ceda_data.get('total_votes')):
                    enriched_measure['total_votes'] = int(ceda_data.get('total_votes'))
                if pd.notna(ceda_data.get('percent_yes')):
                    enriched_measure['percent_yes'] = float(ceda_data.get('percent_yes'))
                
                # Add results
                enriched_measure['pass_fail'] = ceda_data.get('pass_fail')
                enriched_measure['outcome'] = ceda_data.get('outcome')
                
                # Add additional CEDA fields
                enriched_measure['measure_type'] = ceda_data.get('measure_type')
                enriched_measure['measure_letter'] = ceda_data.get('measure_letter')
                enriched_measure['county'] = ceda_data.get('county')
                enriched_measure['place'] = ceda_data.get('place')
                
                # Add categorization if available
                if ceda_data.get('rec_type_name'):
                    enriched_measure['category_type'] = ceda_data.get('rec_type_name')
                if ceda_data.get('rec_topic_name'):
                    enriched_measure['category_topic'] = ceda_data.get('rec_topic_name')
                
                # Add the full ballot question if we don't have it
                if not enriched_measure.get('ballot_question') and ceda_data.get('measure_text'):
                    enriched_measure['ballot_question'] = ceda_data.get('measure_text')
                
            else:
                enriched_measure['ceda_matched'] = False
                enriched_measure['match_confidence'] = None
            
            enriched.append(enriched_measure)
        
        return enriched
    
    def add_historical_ceda_measures(self, enriched_measures, ceda_df, matched_indices):
        """Add unmatched CEDA records as historical measures"""
        historical_measures = []
        
        for idx, row in ceda_df.iterrows():
            if idx not in matched_indices:
                # Only add if it has meaningful content
                if pd.notna(row.get('measure_text')) or pd.notna(row.get('measure_letter')):
                    # Create measure entry from CEDA data
                    measure = {
                        'source': 'CEDA Historical',
                        'year': str(int(row.get('year', 0))),
                        'measure_text': self._create_measure_title(row),
                        'ballot_question': row.get('measure_text'),
                        'pdf_url': '#',  # No PDF for historical
                        'has_summary': False,
                        'ceda_matched': True,
                        'is_historical': True,
                        # Vote data
                        'yes_votes': int(row.get('yes_votes')) if pd.notna(row.get('yes_votes')) else None,
                        'no_votes': int(row.get('no_votes')) if pd.notna(row.get('no_votes')) else None,
                        'total_votes': int(row.get('total_votes')) if pd.notna(row.get('total_votes')) else None,
                        'percent_yes': float(row.get('percent_yes')) if pd.notna(row.get('percent_yes')) else None,
                        'pass_fail': row.get('pass_fail'),
                        # Additional fields
                        'county': row.get('county', 'Unknown'),
                        'place': row.get('place'),
                        'measure_type': row.get('measure_type'),
                        'measure_letter': row.get('measure_letter'),
                        'category_type': row.get('rec_type_name'),
                        'category_topic': row.get('rec_topic_name')
                    }
                    historical_measures.append(measure)
        
        return historical_measures
    
    def _create_measure_title(self, ceda_row):
        """Create a descriptive title from CEDA data"""
        parts = []
        
        # Add location
        if pd.notna(ceda_row.get('county')) and ceda_row['county'] != 'Unknown':
            parts.append(ceda_row['county'])
        elif pd.notna(ceda_row.get('place')):
            parts.append(ceda_row['place'])
        
        # Add measure identifier
        if pd.notna(ceda_row.get('measure_letter')):
            parts.append(f"Measure {ceda_row['measure_letter']}")
        
        # Add type if available
        if pd.notna(ceda_row.get('rec_type_name')):
            parts.append(f"({ceda_row['rec_type_name']})")
        
        return ' '.join(parts) if parts else 'Historical Measure'
    
    def generate_integrated_dataset(self):
        """Generate the final integrated dataset"""
        # Load data
        existing = self.load_existing_measures()
        ceda_df = self.load_ceda_data()
        
        if ceda_df is None:
            return None
        
        print(f"\n🔄 Matching {len(existing)} existing measures with {len(ceda_df)} CEDA records...")
        
        # Perform matching
        results = self.match_measures(existing, ceda_df)
        
        print(f"\n📊 Matching Results:")
        print(f"   ✅ Matched: {results['match_stats']['matched']}")
        print(f"   ❓ Unmatched existing: {results['match_stats']['unmatched_existing']}")
        print(f"   ❓ Unmatched CEDA: {results['match_stats']['unmatched_ceda']}")
        
        # Enrich existing measures
        enriched_measures = self.enrich_existing_measures(existing, results['matches'])
        
        # Get matched CEDA indices
        matched_indices = set()
        for match in results['matches']:
            matched_indices.add(match['ceda_idx'])
        
        # Add historical CEDA measures
        print("\n📚 Adding historical CEDA measures...")
        historical_measures = self.add_historical_ceda_measures(enriched_measures, ceda_df, matched_indices)
        print(f"   Added {len(historical_measures)} historical measures")
        
        # Combine all measures
        all_measures = enriched_measures + historical_measures
        
        # Create enhanced summary statistics
        stats = {
            'total_measures': len(all_measures),
            'scraped_measures': len(existing),
            'historical_measures': len(historical_measures),
            'matched_count': results['match_stats']['matched'],
            'match_rate': f"{(results['match_stats']['matched'] / len(existing) * 100):.1f}%" if existing else "0%",
            'measures_with_votes': sum(1 for m in all_measures if m.get('yes_votes') is not None),
            'measures_with_summaries': sum(1 for m in all_measures if m.get('has_summary')),
            'measures_passed': sum(1 for m in all_measures if m.get('pass_fail') == 'Pass'),
            'measures_failed': sum(1 for m in all_measures if m.get('pass_fail') == 'Fail')
        }
        
        # Save integrated data in enhanced_measures format
        output = {
            'scraped_at': datetime.now().isoformat(),
            'total_measures': len(all_measures),
            'measures_with_summaries': stats['measures_with_summaries'],
            'measures_with_votes': stats['measures_with_votes'],
            'statistics': stats,
            'measures': all_measures
        }
        
        # Save as enhanced_measures.json (to work with existing website generator)
        output_path = self.data_dir / 'enhanced_measures.json'
        with open(output_path, 'w') as f:
            json.dump(output, f, indent=2)
        
        print(f"\n💾 Saved integrated data: {output_path}")
        
        # Also save backup
        backup_path = self.data_dir / 'integrated_measures_backup.json'
        with open(backup_path, 'w') as f:
            json.dump(output, f, indent=2)
        
        # Save summary CSV
        summary_df = pd.DataFrame(all_measures)
        summary_path = self.data_dir / 'integrated_measures.csv'
        summary_df.to_csv(summary_path, index=False)
        print(f"📊 Saved summary CSV: {summary_path}")
        
        # Print enriched summary
        print(f"\n📈 Integration Summary:")
        print(f"   - Total measures: {stats['total_measures']}")
        print(f"   - From web scraping: {stats['scraped_measures']}")
        print(f"   - From CEDA historical: {stats['historical_measures']}")
        print(f"   - Measures with vote data: {stats['measures_with_votes']}")
        print(f"   - Measures with summaries: {stats['measures_with_summaries']}")
        if stats['measures_passed'] + stats['measures_failed'] > 0:
            pass_rate = (stats['measures_passed'] / (stats['measures_passed'] + stats['measures_failed']) * 100)
            print(f"   - Overall pass rate: {pass_rate:.1f}%")
        
        return output

def main():
    """Run the integration process"""
    print("🚀 CEDA Data Integration - Enhanced Version")
    print("=" * 50)
    
    integrator = CEDAIntegrator()
    
    # Check if CEDA data exists
    ceda_path = Path('data/ceda_combined.csv')
    if not ceda_path.exists():
        print("\n❌ CEDA data not found!")
        print("Please run the CEDA parser first:")
        print("  python ceda_parser_comprehensive.py")
        return
    
    # Check for CEDA summary to show what we're working with
    summary_path = Path('data/ceda_summary.json')
    if summary_path.exists():
        with open(summary_path, 'r') as f:
            summary = json.load(f)
            stats = summary.get('statistics', {})
            print(f"\n📊 CEDA data summary:")
            print(f"   - Total records: {stats.get('total_measures', 0):,}")
            print(f"   - Years: {stats.get('years_covered', [])}")
            print(f"   - Records with ballot text: {stats.get('measures_with_text', 0):,}")
            print(f"   - Records with vote data: {stats.get('measures_with_votes', 0):,}")
    
    # Run integration
    integrated_data = integrator.generate_integrated_dataset()
    
    if integrated_data:
        print("\n🎉 Integration successful!")
        print("\nNext steps:")
        print("1. Run: python enhanced_website_generator.py")
        print("2. Open: auto_enhanced_ballot_measures.html")
        print("\nOr run the complete pipeline:")
        print("   python run_complete_pipeline.py")

if __name__ == "__main__":
    main()