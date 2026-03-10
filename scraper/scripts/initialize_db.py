#!/usr/bin/env python3
"""
Initialize or reinitialize the ballot measures database
Creates tables, indexes, and loads any existing data
"""
import sys
import logging
import argparse
from pathlib import Path
from datetime import datetime
import shutil

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import DB_PATH, DATA_DIR
from src.database.operations import Database
from src.database.models import BallotMeasure
from src.parsers.ceda import CEDAParser
from src.parsers.ncsl import NCSLParser
from src.parsers.icpsr import ICPSRParser

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def backup_existing_database():
    """Backup existing database if it exists"""
    if DB_PATH.exists():
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = DB_PATH.parent / f"{DB_PATH.stem}_backup_{timestamp}{DB_PATH.suffix}"
        shutil.copy2(DB_PATH, backup_path)
        logger.info(f"Backed up existing database to: {backup_path}")
        return backup_path
    return None

def initialize_database(fresh=False):
    """Initialize the database with schema and indexes"""
    logger.info("Initializing database...")
    
    # Backup existing if requested
    if fresh and DB_PATH.exists():
        backup_path = backup_existing_database()
        DB_PATH.unlink()
        logger.info(f"Removed existing database (backup at {backup_path})")
    
    # Create database
    db_ops = Database(DB_PATH)
    
    # The Database class handles table creation in __init__
    logger.info(f"Database initialized at: {DB_PATH}")
    
    return db_ops

def load_historical_data(db_ops):
    """Load historical data from NCSL and ICPSR if available"""
    logger.info("Loading historical data...")
    
    loaded_sources = []
    total_loaded = 0
    
    # Try NCSL data (parse() returns List[Dict])
    try:
        ncsl_parser = NCSLParser(DATA_DIR)
        ncsl_records = ncsl_parser.parse()
        if ncsl_records:
            count = 0
            for record in ncsl_records:
                try:
                    measure = BallotMeasure.from_dict(record)
                    db_ops.insert_measure(measure)
                    count += 1
                except Exception as e:
                    logger.debug(f"Skipping NCSL record: {e}")
            logger.info(f"Loaded {count} measures from NCSL")
            loaded_sources.append(f"NCSL ({count})")
            total_loaded += count
    except Exception as e:
        logger.warning(f"Could not load NCSL data: {e}")

    # Try ICPSR data (parse() returns List[Dict])
    try:
        icpsr_parser = ICPSRParser(DATA_DIR)
        icpsr_records = icpsr_parser.parse()
        if icpsr_records:
            count = 0
            for record in icpsr_records:
                try:
                    measure = BallotMeasure.from_dict(record)
                    db_ops.insert_measure(measure)
                    count += 1
                except Exception as e:
                    logger.debug(f"Skipping ICPSR record: {e}")
            logger.info(f"Loaded {count} measures from ICPSR")
            loaded_sources.append(f"ICPSR ({count})")
            total_loaded += count
    except Exception as e:
        logger.warning(f"Could not load ICPSR data: {e}")

    # Try CEDA data (parse_all_files() returns List[BallotMeasure])
    try:
        ceda_parser = CEDAParser(DATA_DIR)
        ceda_measures = ceda_parser.parse_all_files()
        if ceda_measures:
            count = 0
            for measure in ceda_measures:
                try:
                    db_ops.insert_measure(measure)
                    count += 1
                except Exception as e:
                    logger.debug(f"Skipping CEDA measure: {e}")
            logger.info(f"Loaded {count} measures from CEDA")
            loaded_sources.append(f"CEDA ({count})")
            total_loaded += count
    except Exception as e:
        logger.warning(f"Could not load CEDA data: {e}")
    
    return loaded_sources, total_loaded

def run_deduplication(db_ops):
    """Run deduplication after initial load"""
    logger.info("Running deduplication...")
    
    from src.database.deduplication import Deduplicator
    
    deduplicator = Deduplicator(db_ops)
    stats = deduplicator.deduplicate_cross_source()

    logger.info(f"Deduplication complete: {stats}")

    return stats

def main():
    """Main initialization function"""
    parser = argparse.ArgumentParser(description='Initialize ballot measures database')
    parser.add_argument(
        '--fresh',
        action='store_true',
        help='Start with a fresh database (backs up existing)'
    )
    parser.add_argument(
        '--no-historical',
        action='store_true',
        help='Skip loading historical data (NCSL, ICPSR, CEDA)'
    )
    parser.add_argument(
        '--no-dedup',
        action='store_true',
        help='Skip deduplication step'
    )
    
    args = parser.parse_args()
    
    try:
        print("\n" + "="*60)
        print("California Ballot Measures Database Initialization")
        print("="*60)
        
        # Initialize database
        db_ops = initialize_database(fresh=args.fresh)
        
        # Load historical data unless skipped
        if not args.no_historical:
            loaded_sources, total_loaded = load_historical_data(db_ops)
        else:
            loaded_sources, total_loaded = [], 0
        
        # Run deduplication unless skipped
        if not args.no_dedup and total_loaded > 0:
            dedup_stats = run_deduplication(db_ops)
        else:
            dedup_stats = None
        
        # Get final statistics
        stats = db_ops.get_statistics()
        
        # Print summary
        print("\n" + "="*60)
        print("✅ Database Initialization Complete!")
        print("="*60)
        print(f"\n📊 Database Statistics:")
        print(f"  - Total measures: {stats['total_measures']}")
        print(f"  - With summaries: {stats['with_summaries']}")
        print(f"  - With vote data: {stats['with_votes']}")
        print(f"  - Year range: {stats.get('year_min', 'N/A')}-{stats.get('year_max', 'N/A')}")
        
        if loaded_sources:
            print(f"\n📥 Data Sources Loaded:")
            for source in loaded_sources:
                print(f"  - {source}")
        
        if dedup_stats:
            print(f"\n🔍 Deduplication Results:")
            if isinstance(dedup_stats, dict):
                print(f"  - Results: {dedup_stats}")
            else:
                print(f"  - Deduplication completed")
        
        print(f"\n💾 Database location: {DB_PATH}")
        print("\nNext steps:")
        print("  1. Run 'make scrape' to get latest measures")
        print("  2. Run 'make website' to generate the website")
        print("  3. Run 'make api' to start the API server")
        
        return 0
        
    except Exception as e:
        logger.error(f"Database initialization failed: {e}", exc_info=True)
        print(f"\n❌ Error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())