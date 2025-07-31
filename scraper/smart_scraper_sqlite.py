#!/usr/bin/env python3
"""
Smart Scraper Pipeline with SQLite Integration
Uses SQLite as the single source of truth instead of JSON
"""

import subprocess
import sys
from pathlib import Path
from datetime import datetime
import sqlite3
import json

# Import the enhanced database class
sys.path.append(str(Path(__file__).parent))
from setup_ballot_database import EnhancedBallotDatabase

class SmartSQLitePipeline:
    def __init__(self):
        self.db = EnhancedBallotDatabase()
        self.data_dir = Path('data')
        self.data_dir.mkdir(exist_ok=True)
        
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
    
    def process_scraped_data(self, scraped_data):
        """Process scraped data into SQLite database"""
        if not scraped_data:
            return {'new': 0, 'updated': 0, 'unchanged': 0, 'errors': 0}
        
        measures = scraped_data.get('measures', [])
        print(f"\n🔍 Processing {len(measures)} scraped measures...")
        
        self.db.connect()
        
        # Start a scraper run log
        run_id = self.db.log_scraper_run('update')
        
        stats = {
            'new': 0,
            'updated': 0,
            'unchanged': 0,
            'errors': 0,
            'duplicates': 0
        }
        
        try:
            for measure in measures:
                # Prepare measure data for database
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
                    'county': measure.get('county', 'Statewide'),
                    'measure_letter': measure.get('measure_letter')
                }
                
                # Insert or update in database
                action, measure_id = self.db.insert_or_update_measure(measure_data)
                
                if action == 'inserted':
                    stats['new'] += 1
                elif action == 'updated':
                    stats['updated'] += 1
                elif action == 'unchanged':
                    stats['unchanged'] += 1
                elif action == 'error':
                    stats['errors'] += 1
                
                # Check if it was marked as duplicate
                if measure_id:  # measure_id is set when it's a duplicate
                    stats['duplicates'] += 1
            
            # Update scraper run log
            self.db.update_scraper_run(
                run_id,
                measures_checked=len(measures),
                new_measures=stats['new'],
                updated_measures=stats['updated'],
                duplicates_found=stats['duplicates'],
                status='success'
            )
            
            print(f"\n📊 Processing Results:")
            print(f"   🆕 New measures: {stats['new']}")
            print(f"   🔄 Updated: {stats['updated']}")
            print(f"   ✅ Unchanged: {stats['unchanged']}")
            print(f"   🔁 Duplicates: {stats['duplicates']}")
            print(f"   ❌ Errors: {stats['errors']}")
            
        except Exception as e:
            print(f"❌ Error processing data: {e}")
            self.db.update_scraper_run(
                run_id,
                status='failed',
                error_message=str(e)
            )
            stats['errors'] += 1
        finally:
            self.db.close()
        
        return stats
    
    def check_for_updates(self):
        """Check for new measures without updating"""
        print("\n🔍 Checking for new measures...")
        
        # Run scrapers
        scraped_data = self.run_scrapers()
        if not scraped_data:
            print("❌ Could not check for updates")
            return
        
        measures = scraped_data.get('measures', [])
        
        # Check each measure against database
        self.db.connect()
        
        new_measures = []
        potential_updates = []
        
        try:
            for measure in measures:
                # Create fingerprint
                fingerprint, content_hash = self.db.create_fingerprint({
                    'year': measure.get('year'),
                    'title': measure.get('measure_text'),
                    'data_source': measure.get('source', 'CA_SOS'),
                    'county': measure.get('county', 'Statewide')
                })
                
                # Check if exists
                duplicate = self.db.check_duplicate(fingerprint, content_hash)
                
                if not duplicate:
                    new_measures.append(measure)
                elif duplicate['type'] == 'exact':
                    # Check if any fields would be updated
                    cursor = self.db.conn.execute(
                        "SELECT has_summary, yes_votes FROM measures WHERE id = ?",
                        (duplicate['id'],)
                    )
                    current = cursor.fetchone()
                    
                    if (not current['has_summary'] and measure.get('has_summary')) or \
                       (not current['yes_votes'] and measure.get('yes_votes')):
                        potential_updates.append(measure)
            
            print(f"\n📊 Check Results:")
            print(f"   🆕 New measures found: {len(new_measures)}")
            print(f"   🔄 Potential updates: {len(potential_updates)}")
            
            if new_measures:
                print("\n🆕 New measures:")
                for measure in new_measures[:5]:  # Show first 5
                    print(f"   - {measure.get('year')} {measure.get('measure_text', 'Unknown')[:60]}...")
                if len(new_measures) > 5:
                    print(f"   ... and {len(new_measures) - 5} more")
            
            if not new_measures and not potential_updates:
                print("\n✅ No updates needed - database is current")
                
        finally:
            self.db.close()
    
    def generate_website(self, force=False):
        """Generate website from SQLite data"""
        self.db.connect()
        
        try:
            # Get all measures from database
            measures = self.db.get_measures_for_website()
            stats = self.db.get_statistics()
            
            # Format for website generator
            website_data = {
                'scraped_at': datetime.now().isoformat(),
                'total_measures': stats['total_measures'],
                'measures_with_summaries': stats['measures_with_summaries'],
                'measures_with_votes': stats['measures_with_votes'],
                'measures': measures
            }
            
            # Save as enhanced_measures.json for website generator
            output_file = self.data_dir / 'enhanced_measures.json'
            with open(output_file, 'w') as f:
                json.dump(website_data, f, indent=2)
            
            print(f"\n📄 Prepared {len(measures)} measures for website generation")
            
            # Run website generator
            print("\n🌐 Generating website...")
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
                
        finally:
            self.db.close()
    
    def show_statistics(self):
        """Show database statistics"""
        self.db.connect()
        
        try:
            stats = self.db.get_statistics()
            
            print("\n📊 DATABASE STATISTICS")
            print("=" * 60)
            print(f"Total measures: {stats['total_measures']}")
            print(f"With summaries: {stats['measures_with_summaries']} ({stats['measures_with_summaries']/stats['total_measures']*100:.1f}%)")
            print(f"With vote data: {stats['measures_with_votes']} ({stats['measures_with_votes']/stats['total_measures']*100:.1f}%)")
            print(f"Year range: {stats['year_range']}")
            
            print("\nBy source:")
            for source, count in stats['by_source'].items():
                print(f"  {source}: {count}")
            
            # Recent scraper runs
            cursor = self.db.conn.execute("""
                SELECT run_type, started_at, status, new_measures, updated_measures
                FROM scraper_runs
                ORDER BY started_at DESC
                LIMIT 5
            """)
            
            runs = cursor.fetchall()
            if runs:
                print("\nRecent scraper runs:")
                for run in runs:
                    print(f"  {run['started_at']}: {run['run_type']} - {run['status']} "
                          f"(+{run['new_measures']} new, {run['updated_measures']} updated)")
            
        finally:
            self.db.close()
    
    def run_pipeline(self, check_only=False):
        """Run the complete smart pipeline"""
        print("🚀 SMART BALLOT MEASURES PIPELINE (SQLite Edition)")
        print("=" * 60)
        
        if check_only:
            self.check_for_updates()
            return
        
        # Run scrapers and process data
        scraped_data = self.run_scrapers()
        if not scraped_data:
            print("\n❌ Scraping failed, aborting pipeline")
            return
        
        # Process into database
        stats = self.process_scraped_data(scraped_data)
        
        # Generate website if there were changes
        if stats['new'] > 0 or stats['updated'] > 0:
            print("\n🔄 Changes detected, regenerating website...")
            self.generate_website()
        else:
            print("\n✅ No changes detected")
            response = input("\n🔄 Regenerate website anyway? (y/N): ")
            if response.lower() == 'y':
                self.generate_website(force=True)
        
        print("\n✅ Pipeline complete!")


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Smart Ballot Measures Pipeline (SQLite)')
    parser.add_argument('--check', action='store_true', 
                       help='Only check for new measures, don\'t update')
    parser.add_argument('--stats', action='store_true',
                       help='Show database statistics')
    parser.add_argument('--force-website', action='store_true',
                       help='Force website regeneration')
    
    args = parser.parse_args()
    
    pipeline = SmartSQLitePipeline()
    
    if args.stats:
        pipeline.show_statistics()
    elif args.force_website:
        pipeline.generate_website(force=True)
    else:
        pipeline.run_pipeline(check_only=args.check)


if __name__ == '__main__':
    main()