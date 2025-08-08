#!/usr/bin/env python3
# Add parent directory to path for imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

"""
Migration script to reorganize the California Ballot Measures project
Moves files from old structure to new organized structure
"""
import os
import shutil
import sys
from pathlib import Path
from datetime import datetime
import json

# Color codes for terminal output
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
BLUE = '\033[94m'
RESET = '\033[0m'


class ProjectMigrator:
    def __init__(self, dry_run=False):
        self.dry_run = dry_run
        self.base_dir = Path.cwd()
        self.backup_dir = self.base_dir / f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.actions = []
        
    def log(self, message, color=None):
        """Log a message with optional color"""
        if color:
            print(f"{color}{message}{RESET}")
        else:
            print(message)
    
    def add_action(self, action_type, source, dest=None):
        """Add an action to the list"""
        self.actions.append({
            'type': action_type,
            'source': source,
            'dest': dest,
            'timestamp': datetime.now()
        })
    
    def create_backup(self):
        """Create a backup of the current state"""
        if self.dry_run:
            self.log(f"[DRY RUN] Would create backup at: {self.backup_dir}", YELLOW)
            return
            
        self.log(f"Creating backup at: {self.backup_dir}", BLUE)
        
        # Files to backup
        backup_items = [
            '*.py',
            'Makefile',
            'requirements.txt',
            '.env*',
            'data/',
            'downloaded/',
            '*.md',
            '*.html',
            '*.json',
            '*.csv'
        ]
        
        self.backup_dir.mkdir(exist_ok=True)
        
        for pattern in backup_items:
            for item in self.base_dir.glob(pattern):
                if item.is_file():
                    dest = self.backup_dir / item.name
                    shutil.copy2(item, dest)
                    self.add_action('backup', item, dest)
                elif item.is_dir() and item.name not in ['__pycache__', '.git', 'backup_*']:
                    dest = self.backup_dir / item.name
                    shutil.copytree(item, dest, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
                    self.add_action('backup', item, dest)
        
        self.log(f"✅ Backup created successfully", GREEN)
    
    def create_directory_structure(self):
        """Create the new directory structure"""
        directories = [
            'src',
            'src/scrapers',
            'src/parsers',
            'src/database',
            'src/enrichment',
            'src/website',
            'src/website/templates',
            'src/api',
            'scripts',
            'data/raw',
            'data/processed',
            'data/exports',
            'tests',
            'docs',
            'logs'
        ]
        
        for dir_path in directories:
            path = self.base_dir / dir_path
            if self.dry_run:
                if not path.exists():
                    self.log(f"[DRY RUN] Would create directory: {dir_path}", YELLOW)
            else:
                path.mkdir(parents=True, exist_ok=True)
                self.add_action('mkdir', path)
        
        # Create __init__.py files
        init_files = [
            'src/__init__.py',
            'src/scrapers/__init__.py',
            'src/parsers/__init__.py',
            'src/database/__init__.py',
            'src/enrichment/__init__.py',
            'src/website/__init__.py',
            'src/api/__init__.py',
            'tests/__init__.py'
        ]
        
        for init_file in init_files:
            path = self.base_dir / init_file
            if self.dry_run:
                if not path.exists():
                    self.log(f"[DRY RUN] Would create: {init_file}", YELLOW)
            else:
                path.touch(exist_ok=True)
                self.add_action('create', path)
    
    def migrate_files(self):
        """Migrate files to new locations"""
        # Define file mappings (old -> new)
        file_mappings = {
            # Parsers
            'ceda_parser_comprehensive.py': 'src/parsers/ceda.py',
            'merge_historical_data.py': 'src/parsers/historical_merger.py',
            
            # Database files - these will be replaced
            'setup_ballot_database.py': None,  # Will be replaced by new database module
            
            # Entry points
            'smart_scraper_sqlite.py': 'scripts/smart_update.py',
            'check_downloads.py': 'scripts/check_downloads.py',
            
            # API
            'ballot_measures_api.py': 'src/api/server.py',
            
            # Keep in place
            'Makefile': 'Makefile',
            'requirements.txt': 'requirements.txt',
            '.env': '.env',
            '.env.example': '.env.example',
            '.gitignore': '.gitignore',
            
            # Documentation
            'README.md': 'README.md',
            'makefile_guide.md': 'docs/makefile_guide.md',
        }
        
        # Files to archive (not migrate)
        archive_files = [
            'scraper.py',
            'enhanced_scraper.py',
            'enhanced_scraper_with_summaries.py',
            'enhanced_website_generator.py',
            'generate_static_website.py',
            'ascii_website.py',
            'clean_website.py',
            'integrated_pipeline.py',
            'smart_scraper_pipeline.py',
            'run_complete_pipeline.py',
            'integrated_ballot_system.py',
            'ceda_integration.py',
            'update_website.py',
            'duplicate_diagnosis.py',
            'pipeline_config.py',
            'analysis_examples.py'
        ]
        
        # Create archive directory
        archive_dir = self.base_dir / 'archived'
        if not self.dry_run:
            archive_dir.mkdir(exist_ok=True)
        
        # Process file mappings
        for old_file, new_file in file_mappings.items():
            old_path = self.base_dir / old_file
            
            if old_path.exists():
                if new_file:
                    new_path = self.base_dir / new_file
                    if self.dry_run:
                        self.log(f"[DRY RUN] Would move: {old_file} -> {new_file}", YELLOW)
                    else:
                        new_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(old_path, new_path)
                        self.add_action('move', old_path, new_path)
                else:
                    # Archive file
                    if self.dry_run:
                        self.log(f"[DRY RUN] Would archive: {old_file}", YELLOW)
                    else:
                        dest = archive_dir / old_file
                        shutil.move(str(old_path), str(dest))
                        self.add_action('archive', old_path, dest)
        
        # Archive other files
        for file_name in archive_files:
            file_path = self.base_dir / file_name
            if file_path.exists():
                if self.dry_run:
                    self.log(f"[DRY RUN] Would archive: {file_name}", YELLOW)
                else:
                    dest = archive_dir / file_name
                    shutil.move(str(file_path), str(dest))
                    self.add_action('archive', file_path, dest)
    
    def update_makefile(self):
        """Update Makefile for new structure"""
        makefile_content = """# California Ballot Measures - Makefile
.PHONY: help install setup update check stats website api clean test

help:
	@echo "California Ballot Measures - Available Commands"
	@echo "=============================================="
	@echo "Setup:"
	@echo "  make install    - Install dependencies"
	@echo "  make setup      - Initial setup"
	@echo ""
	@echo "Operations:"
	@echo "  make update     - Smart update (check + update if needed)"
	@echo "  make check      - Check for new measures only"
	@echo "  make scrape     - Force scrape all sources"
	@echo "  make dedupe     - Run deduplication"
	@echo "  make enrich     - Add summaries"
	@echo ""
	@echo "Output:"
	@echo "  make website    - Generate website"
	@echo "  make api        - Run API server"
	@echo "  make stats      - Show statistics"
	@echo ""
	@echo "Development:"
	@echo "  make test       - Run tests"
	@echo "  make clean      - Clean temporary files"

install:
	pip install -r requirements.txt

setup: install
	python scripts/initialize_db.py

update:
	python scripts/update_db.py --dedupe --enrich

check:
	python scripts/update_db.py --check-only

scrape:
	python scripts/scrape.py

dedupe:
	python scripts/update_db.py --dedupe

enrich:
	python scripts/update_db.py --enrich

website: update
	python scripts/generate_site.py

api:
	python -m uvicorn src.api.server:app --reload

stats:
	python scripts/update_db.py --stats

test:
	pytest tests/

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache
"""
        
        if self.dry_run:
            self.log("[DRY RUN] Would update Makefile", YELLOW)
        else:
            makefile_path = self.base_dir / 'Makefile'
            makefile_path.write_text(makefile_content)
            self.add_action('update', makefile_path)
    
    def save_migration_log(self):
        """Save a log of all migration actions"""
        if self.dry_run:
            self.log("[DRY RUN] Would save migration log", YELLOW)
            return
            
        log_data = {
            'migration_date': datetime.now().isoformat(),
            'backup_location': str(self.backup_dir),
            'actions': [
                {
                    'type': a['type'],
                    'source': str(a['source']),
                    'dest': str(a['dest']) if a['dest'] else None,
                    'timestamp': a['timestamp'].isoformat()
                }
                for a in self.actions
            ]
        }
        
        log_file = self.base_dir / 'migration_log.json'
        with open(log_file, 'w') as f:
            json.dump(log_data, f, indent=2)
        
        self.log(f"✅ Migration log saved to: {log_file}", GREEN)
    
    def run(self):
        """Run the complete migration"""
        self.log("🚀 California Ballot Measures Project Migration", BLUE)
        self.log("=" * 50)
        
        if self.dry_run:
            self.log("Running in DRY RUN mode - no changes will be made", YELLOW)
            self.log("")
        
        # Step 1: Create backup
        if not self.dry_run:
            self.create_backup()
        
        # Step 2: Create new directory structure
        self.log("\n📁 Creating new directory structure...", BLUE)
        self.create_directory_structure()
        
        # Step 3: Migrate files
        self.log("\n📦 Migrating files...", BLUE)
        self.migrate_files()
        
        # Step 4: Update Makefile
        self.log("\n📝 Updating Makefile...", BLUE)
        self.update_makefile()
        
        # Step 5: Save migration log
        if not self.dry_run:
            self.save_migration_log()
        
        # Summary
        self.log("\n✅ Migration Complete!", GREEN)
        self.log("=" * 50)
        
        if not self.dry_run:
            self.log(f"Backup saved to: {self.backup_dir}", BLUE)
            self.log(f"Total actions performed: {len(self.actions)}", BLUE)
        
        self.log("\nNext steps:", BLUE)
        self.log("1. Review the new structure")
        self.log("2. Copy the new src/ files from the artifacts")
        self.log("3. Run: make setup")
        self.log("4. Run: make update")
        self.log("5. Run: make website")
        
        if self.dry_run:
            self.log("\nTo perform the actual migration, run without --dry-run", YELLOW)


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Migrate California Ballot Measures project to new structure'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without making changes'
    )
    parser.add_argument(
        '--no-backup',
        action='store_true',
        help='Skip backup creation (not recommended)'
    )
    
    args = parser.parse_args()
    
    # Confirm before proceeding
    if not args.dry_run:
        print("⚠️  This will reorganize your entire project structure!")
        print("A backup will be created, but please ensure you have committed any changes.")
        response = input("\nProceed with migration? (yes/no): ")
        if response.lower() != 'yes':
            print("Migration cancelled.")
            return 1
    
    migrator = ProjectMigrator(dry_run=args.dry_run)
    
    try:
        migrator.run()
        return 0
    except Exception as e:
        migrator.log(f"\n❌ Migration failed: {e}", RED)
        return 1


if __name__ == '__main__':
    sys.exit(main())