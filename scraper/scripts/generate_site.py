#!/usr/bin/env python3
"""
Generate static website from ballot measures database
"""
import sys
import logging
import argparse
from pathlib import Path
from datetime import datetime
from collections import Counter

# Fix Windows console encoding for emojis
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import DB_PATH, BASE_DIR, WEBSITE_CONFIG
from src.database.operations import Database

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Construct website output path from config
WEBSITE_OUTPUT_PATH = BASE_DIR / WEBSITE_CONFIG.get('output_filename', 'index.html')

def main():
    """Main function for website generation"""
    parser = argparse.ArgumentParser(description='Generate static website from ballot measures database')
    parser.add_argument(
        '--output',
        type=str,
        default=str(WEBSITE_OUTPUT_PATH),
        help='Output HTML file path (default: index.html)'
    )
    parser.add_argument(
        '--style',
        choices=['modern', 'clean', 'newspaper'],
        default='modern',
        help='Website style template (default: modern)'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Force regeneration even if no changes detected'
    )
    parser.add_argument(
        '--deploy',
        action='store_true',
        help='Deploy to GitHub Pages after generation'
    )
    parser.add_argument(
        '--preview',
        action='store_true',
        help='Open website in browser after generation'
    )
    
    args = parser.parse_args()
    
    try:
        # Check if database exists
        if not DB_PATH.exists():
            logger.error(f"Database not found at {DB_PATH}")
            logger.info("Run 'scripts/update_db.py' to create/update the database")
            return 1
        
        # Initialize database operations
        db = Database(DB_PATH)
        
        # Get statistics
        stats = db.get_statistics()
        logger.info(f"Database contains {stats['total_measures']} measures")
        
        # Check if generation is needed
        output_path = Path(args.output)
        if output_path.exists() and not args.force:
            # Check if database was updated after website
            db_mtime = DB_PATH.stat().st_mtime
            site_mtime = output_path.stat().st_mtime
            
            if db_mtime <= site_mtime:
                logger.info("Website is up to date. Use --force to regenerate.")
                return 0
        
        # Get all measures from database
        logger.info("Loading measures from database...")
        
        # Valid BallotMeasure fields
        valid_fields = {
            'fingerprint', 'measure_fingerprint', 'content_hash',
            'measure_id', 'measure_letter', 'year', 'state', 'county', 'jurisdiction',
            'title', 'description', 'ballot_question',
            'generated_title', 'original_title',
            'yes_votes', 'no_votes', 'total_votes', 'percent_yes', 'percent_no',
            'passed', 'pass_fail',
            'measure_type', 'topic_primary', 'topic_secondary', 'category_type', 'category_topic',
            'data_source', 'source_url', 'pdf_url',
            'has_summary', 'summary_title', 'summary_text',
            'election_type', 'election_date', 'decade', 'century',
            'created_at', 'updated_at', 'last_seen_at', 'update_count',
            'is_active', 'is_duplicate', 'duplicate_type', 'master_id', 'merged_from'
        }
        
        # Get measures and handle field issues
        conn = db.connect()
        cursor = conn.execute("""
            SELECT * FROM active_measures
            ORDER BY year DESC, county, measure_letter
        """)
        
        measures = []
        measures_data = []
        for row in cursor:
            # Convert row to dict
            measure_dict = dict(row)
            
            # Store original dict for website
            measures_data.append(measure_dict.copy())
            
            # Filter to only valid fields for BallotMeasure
            filtered_dict = {k: v for k, v in measure_dict.items() if k in valid_fields}
            
            # Ensure required fields exist
            filtered_dict.setdefault('fingerprint', '')
            filtered_dict.setdefault('measure_fingerprint', '')
            filtered_dict.setdefault('content_hash', '')
            
            from src.database.models import BallotMeasure
            measure = BallotMeasure(**filtered_dict)
            measures.append(measure)
        
        logger.info(f"Loaded {len(measures)} measures")
        
        # Close database connection
        db.close()
        
        # Initialize website generator  
        from src.website.generator import WebsiteGenerator
        generator = WebsiteGenerator()
        
        # Prepare data for website
        # Convert measures to format needed by generator
        from src.utils.topic_mapping import get_display_topic

        measures_for_website = []
        for m in measures:
            m_dict = m.to_dict()
            # Add display fields
            m_dict['measure_text'] = m_dict.get('title') or m_dict.get('ballot_question', 'Unknown Measure')
            m_dict['source'] = m_dict.get('data_source', 'Historical')
            # Add consolidated display topic (maps detailed topics to ~12 categories)
            raw_topic = m_dict.get('topic_primary') or m_dict.get('category_topic')
            m_dict['display_topic'] = get_display_topic(raw_topic)

            # Normalize percent_yes/percent_no to 0-100 scale
            # CEDA/NCSL store as decimals (0-1), ICPSR stores as percentages (0-100)
            pct_yes = m_dict.get('percent_yes')
            if pct_yes is not None and pct_yes <= 1:
                m_dict['percent_yes'] = pct_yes * 100

            pct_no = m_dict.get('percent_no')
            if pct_no is not None and pct_no <= 1:
                m_dict['percent_no'] = pct_no * 100
            elif pct_no is None and m_dict.get('percent_yes') is not None:
                m_dict['percent_no'] = 100 - m_dict['percent_yes']

            measures_for_website.append(m_dict)
        
        # Extract topics
        from collections import Counter
        topic_counts = Counter()
        for measure in measures:
            topic = measure.topic_primary or measure.category_topic
            if topic:
                topic_counts[topic] += 1
        
        topics = [
            {'topic': topic, 'count': count}
            for topic, count in topic_counts.most_common(20)
        ]

        # Load recommendations for related measures
        recommendations = generator._load_recommendations()

        # Generate website
        logger.info(f"Generating website...")
        html_content = generator._generate_html(measures_for_website, stats, topics, recommendations)
        
        # Save website
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html_content, encoding='utf-8')
        logger.info(f"Website saved to: {output_path}")
        
        # Also save to root directory for GitHub Pages
        # Get the actual project root (parent of scraper directory)
        script_dir = Path(__file__).resolve().parent.parent  # This is the scraper/ directory
        project_root = script_dir.parent  # This is cal_vgp/ directory
        root_index = project_root / 'index.html'
        logger.info(f"Copying to project root: {root_index.resolve()}")
        try:
            root_index.write_text(html_content, encoding='utf-8')
            # Verify the write
            if root_index.exists() and root_index.stat().st_size > 1000000:  # Should be > 1MB
                logger.info(f"✓ Successfully saved to: {root_index.resolve()}")
            else:
                logger.warning(f"⚠️  File may not have been written correctly: {root_index.resolve()}")
        except Exception as e:
            logger.error(f"Failed to save to project root: {e}")
        
        # Deploy if requested
        if args.deploy:
            logger.info("Deploying to GitHub Pages...")
            deploy_to_github()
        
        # Preview if requested
        if args.preview:
            import webbrowser
            webbrowser.open(f'file://{output_path.absolute()}')
            logger.info("Opened website in browser")
        
        # Print summary
        print("\n" + "="*60)
        print("✅ Website Generation Complete!")
        print("="*60)
        print(f"📊 Total Measures: {stats['total_measures']}")
        print(f"📝 With Summaries: {stats['with_summaries']}")
        print(f"🗳️ With Vote Data: {stats['with_votes']}")
        print(f"📅 Year Range: {stats.get('year_min', 'N/A')}-{stats.get('year_max', 'N/A')}")
        print(f"🌐 Output: {output_path}")
        
        return 0
        
    except Exception as e:
        logger.error(f"Error generating website: {e}", exc_info=True)
        return 1

def deploy_to_github():
    """Deploy website to GitHub Pages"""
    try:
        import subprocess
        
        # Stage changes
        subprocess.run(['git', 'add', '../index.html'], check=True)
        subprocess.run(['git', 'add', 'data/'], check=True)
        
        # Commit
        commit_msg = f"Update website - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        subprocess.run(['git', 'commit', '-m', commit_msg], check=False)
        
        # Push
        subprocess.run(['git', 'push'], check=True)
        
        logger.info("Successfully deployed to GitHub Pages")
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Error deploying to GitHub: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error during deployment: {e}")
        raise

if __name__ == "__main__":
    sys.exit(main())