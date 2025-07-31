#!/usr/bin/env python3
"""
Smart Scraper Pipeline with Deduplication
Checks for new measures, deduplicates, and only updates if needed
"""

import json
import hashlib
import subprocess
import sys
from pathlib import Path
from datetime import datetime
import re
import pandas as pd

class SmartBallotMeasuresPipeline:
    def __init__(self):
        self.data_dir = Path('data')
        self.data_dir.mkdir(exist_ok=True)
        
        # Database file (using JSON for now, easy to switch to SQLite)
        self.db_file = self.data_dir / 'ballot_measures_db.json'
        self.temp_file = self.data_dir / 'temp_scraped.json'
        
    def load_database(self):
        """Load existing ballot measures database"""
        if self.db_file.exists():
            with open(self.db_file, 'r') as f:
                data = json.load(f)
                print(f"📚 Loaded database: {len(data.get('measures', []))} existing measures")
                return data
        else:
            print("🆕 No existing database found, creating new one")
            return {
                'created_at': datetime.now().isoformat(),
                'last_updated': datetime.now().isoformat(),
                'total_measures': 0,
                'measures': [],
                'update_history': []
            }
    
    def create_measure_fingerprint(self, measure):
        """Create a unique fingerprint for a measure to detect duplicates"""
        # Key fields that uniquely identify a measure
        key_parts = []
        
        # Year
        year = str(measure.get('year', '')).strip()
        key_parts.append(year)
        
        # Extract measure identifier (Prop 8, ACA 13, etc.)
        measure_text = str(measure.get('measure_text', ''))
        
        # Try to extract standardized identifier
        patterns = [
            (r'(?:Proposition|Prop\.?)\s*(\d+[A-Z]?)', 'PROP_{}'),
            (r'([AS]CA)\s*(\d+)', '{}_{}'),
            (r'(AB|SB)\s*(\d+)', '{}_{}'),
            (r'(?:Measure)\s*([A-Z]+)', 'MEASURE_{}'),
        ]
        
        measure_id = None
        for pattern, format_str in patterns:
            match = re.search(pattern, measure_text, re.IGNORECASE)
            if match:
                groups = match.groups()
                measure_id = format_str.format(*groups).upper()
                break
        
        if measure_id:
            key_parts.append(measure_id)
        
        # Add source to distinguish between different versions
        source = measure.get('source', '').upper()
        key_parts.append(source)
        
        # Create fingerprint
        fingerprint_str = '|'.join(key_parts)
        
        # Also create a content hash for detecting near-duplicates
        content_parts = [
            measure_text,
            str(measure.get('ballot_question', '')),
            str(measure.get('election', ''))
        ]
        content_str = '|'.join(content_parts).lower()
        content_hash = hashlib.md5(content_str.encode()).hexdigest()[:8]
        
        return {
            'fingerprint': fingerprint_str,
            'content_hash': content_hash,
            'year': year,
            'measure_id': measure_id,
            'source': source
        }
    
    def run_scrapers(self):
        """Run the scraping scripts and capture output"""
        print("\n🔄 Running scrapers to check for new measures...")
        
        # Run enhanced scraper
        try:
            result = subprocess.run(
                [sys.executable, 'enhanced_scraper.py'],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                print("✅ Scraper completed successfully")
                
                # Load the scraped data
                scraped_file = self.data_dir / 'all_measures.json'
                if scraped_file.exists():
                    with open(scraped_file, 'r') as f:
                        return json.load(f)
                else:
                    print("❌ Scraper didn't produce output file")
                    return None
            else:
                print("❌ Scraper failed:")
                print(result.stderr)
                return None
                
        except Exception as e:
            print(f"❌ Error running scraper: {e}")
            return None
    
    def deduplicate_measures(self, existing_measures, new_measures):
        """Deduplicate measures and identify genuinely new ones"""
        print("\n🔍 Checking for duplicates...")
        
        # Create fingerprint index for existing measures
        existing_fingerprints = {}
        existing_hashes = {}
        
        for measure in existing_measures:
            fp_data = self.create_measure_fingerprint(measure)
            fingerprint = fp_data['fingerprint']
            content_hash = fp_data['content_hash']
            
            existing_fingerprints[fingerprint] = measure
            existing_hashes[content_hash] = measure
        
        # Check new measures
        genuinely_new = []
        duplicates = []
        updated = []
        
        for measure in new_measures:
            fp_data = self.create_measure_fingerprint(measure)
            fingerprint = fp_data['fingerprint']
            content_hash = fp_data['content_hash']
            
            if fingerprint in existing_fingerprints:
                # Exact duplicate by key fields
                duplicates.append({
                    'measure': measure,
                    'reason': 'exact_match',
                    'matched_with': existing_fingerprints[fingerprint]
                })
            elif content_hash in existing_hashes:
                # Content duplicate (same text, maybe different source)
                duplicates.append({
                    'measure': measure,
                    'reason': 'content_match',
                    'matched_with': existing_hashes[content_hash]
                })
            else:
                # Check if this is an update to an existing measure
                is_update = False
                if fp_data['measure_id'] and fp_data['year']:
                    for existing in existing_measures:
                        existing_fp = self.create_measure_fingerprint(existing)
                        if (existing_fp['measure_id'] == fp_data['measure_id'] and 
                            existing_fp['year'] == fp_data['year']):
                            # Same measure but different content/source
                            updated.append({
                                'old': existing,
                                'new': measure,
                                'reason': 'content_update'
                            })
                            is_update = True
                            break
                
                if not is_update:
                    genuinely_new.append(measure)
        
        print(f"\n📊 Deduplication Results:")
        print(f"   🆕 Genuinely new: {len(genuinely_new)}")
        print(f"   🔄 Updated: {len(updated)}")
        print(f"   ❌ Duplicates: {len(duplicates)}")
        
        return {
            'new': genuinely_new,
            'duplicates': duplicates,
            'updated': updated
        }
    
    def update_database(self, db_data, dedup_results):
        """Update database with new measures"""
        if not dedup_results['new'] and not dedup_results['updated']:
            print("\n✅ No new measures to add to database")
            return False
        
        print("\n💾 Updating database...")
        
        # Add new measures
        for measure in dedup_results['new']:
            measure['added_at'] = datetime.now().isoformat()
            measure['fingerprint'] = self.create_measure_fingerprint(measure)['fingerprint']
            db_data['measures'].append(measure)
        
        # Handle updates
        for update in dedup_results['updated']:
            # Find and update the existing measure
            old_fp = self.create_measure_fingerprint(update['old'])['fingerprint']
            for i, measure in enumerate(db_data['measures']):
                if self.create_measure_fingerprint(measure)['fingerprint'] == old_fp:
                    # Preserve some fields from old, update others
                    updated_measure = update['new'].copy()
                    updated_measure['added_at'] = measure.get('added_at')
                    updated_measure['updated_at'] = datetime.now().isoformat()
                    updated_measure['fingerprint'] = self.create_measure_fingerprint(updated_measure)['fingerprint']
                    
                    # Preserve summaries if not in new data
                    if measure.get('has_summary') and not updated_measure.get('has_summary'):
                        updated_measure['summary_title'] = measure.get('summary_title')
                        updated_measure['summary_text'] = measure.get('summary_text')
                        updated_measure['has_summary'] = True
                    
                    db_data['measures'][i] = updated_measure
                    break
        
        # Update metadata
        db_data['last_updated'] = datetime.now().isoformat()
        db_data['total_measures'] = len(db_data['measures'])
        
        # Add to update history
        db_data['update_history'].append({
            'timestamp': datetime.now().isoformat(),
            'new_measures': len(dedup_results['new']),
            'updated_measures': len(dedup_results['updated']),
            'duplicates_found': len(dedup_results['duplicates'])
        })
        
        # Save database
        with open(self.db_file, 'w') as f:
            json.dump(db_data, f, indent=2)
        
        # Also save in format expected by website generator
        enhanced_format = {
            'scraped_at': db_data['last_updated'],
            'total_measures': db_data['total_measures'],
            'measures_with_summaries': sum(1 for m in db_data['measures'] if m.get('has_summary')),
            'measures': db_data['measures']
        }
        
        enhanced_file = self.data_dir / 'enhanced_measures.json'
        with open(enhanced_file, 'w') as f:
            json.dump(enhanced_format, f, indent=2)
        
        print(f"✅ Database updated: {len(db_data['measures'])} total measures")
        return True
    
    def generate_website(self, force=False):
        """Generate website if there are updates or forced"""
        if force:
            print("\n🌐 Generating website (forced)...")
        else:
            print("\n🌐 Generating website with new data...")
        
        try:
            result = subprocess.run(
                [sys.executable, 'enhanced_website_generator.py'],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                print("✅ Website generated successfully")
                print("📄 Open: auto_enhanced_ballot_measures.html")
                return True
            else:
                print("❌ Website generation failed:")
                print(result.stderr)
                return False
                
        except Exception as e:
            print(f"❌ Error generating website: {e}")
            return False
    
    def run_pipeline(self, check_only=False):
        """Run the complete smart pipeline"""
        print("🚀 SMART BALLOT MEASURES PIPELINE")
        print("=" * 60)
        
        # Load existing database
        db_data = self.load_database()
        
        # Run scrapers
        scraped_data = self.run_scrapers()
        if not scraped_data:
            print("\n❌ Scraping failed, aborting pipeline")
            return False
        
        # Deduplicate
        dedup_results = self.deduplicate_measures(
            db_data['measures'],
            scraped_data.get('measures', [])
        )
        
        # If only checking, report and exit
        if check_only:
            if dedup_results['new']:
                print(f"\n🆕 Found {len(dedup_results['new'])} new measures:")
                for measure in dedup_results['new'][:5]:  # Show first 5
                    print(f"   - {measure.get('year')} {measure.get('measure_text', 'Unknown')[:60]}...")
            else:
                print("\n✅ No new measures found")
            return True
        
        # Update database if needed
        has_updates = self.update_database(db_data, dedup_results)
        
        # Generate website if there are updates
        if has_updates:
            self.generate_website()
        else:
            print("\n✅ No updates needed, website is current")
            
            # Ask if user wants to regenerate anyway
            response = input("\n🔄 Regenerate website anyway? (y/N): ")
            if response.lower() == 'y':
                self.generate_website(force=True)
        
        print("\n✅ Pipeline complete!")
        return True
    
    def show_statistics(self):
        """Show database statistics"""
        db_data = self.load_database()
        
        print("\n📊 DATABASE STATISTICS")
        print("=" * 60)
        print(f"Total measures: {db_data['total_measures']}")
        print(f"Last updated: {db_data['last_updated']}")
        
        # Group by year
        by_year = {}
        for measure in db_data['measures']:
            year = measure.get('year', 'Unknown')
            by_year[year] = by_year.get(year, 0) + 1
        
        print("\nMeasures by year:")
        for year in sorted(by_year.keys(), reverse=True)[:10]:
            print(f"  {year}: {by_year[year]}")
        
        # Show update history
        if db_data.get('update_history'):
            print(f"\nRecent updates:")
            for update in db_data['update_history'][-5:]:
                print(f"  {update['timestamp']}: +{update['new_measures']} new, "
                      f"{update['updated_measures']} updated")


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Smart Ballot Measures Pipeline')
    parser.add_argument('--check', action='store_true', 
                       help='Only check for new measures, don\'t update')
    parser.add_argument('--stats', action='store_true',
                       help='Show database statistics')
    parser.add_argument('--force-website', action='store_true',
                       help='Force website regeneration')
    
    args = parser.parse_args()
    
    pipeline = SmartBallotMeasuresPipeline()
    
    if args.stats:
        pipeline.show_statistics()
    elif args.force_website:
        pipeline.generate_website(force=True)
    else:
        pipeline.run_pipeline(check_only=args.check)


if __name__ == '__main__':
    main()