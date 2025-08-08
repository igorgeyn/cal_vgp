#!/usr/bin/env python3
# Add parent directory to path for imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

"""
Post-Reorganization Cleanup Script for California Ballot Measures Project
Safely removes unnecessary files after successful migration to new structure
"""
import os
import shutil
from pathlib import Path
from datetime import datetime, timedelta
import json
import argparse

# Color codes for terminal output
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'


class ProjectCleaner:
    def __init__(self, dry_run=False, force=False):
        self.dry_run = dry_run
        self.force = force
        self.base_dir = Path.cwd()
        self.actions = []
        self.space_saved = 0
        
        # Define what to remove
        self.dirs_to_remove = [
            'new_structure_files',
            'downloaded',  # Empty, data moved to data/raw/
            'dep',  # Old HTML files
        ]
        
        self.files_to_remove = [
            # Migration scripts (can be removed after successful migration)
            'reorganize_project.py',
            'inspect_post_reorg.py',
            'inspect_new_structure.py',
            'prepare_new_files.py',
            'migrate_to_new_structure.py',
            'new_structure_inspection.json',
            
            # Old HTML files in root
            'updated_ballot_measures.html',
            
            # Poetry files (if not using Poetry)
            'poetry.lock',
            'pyproject.toml',
            
            # Old shell scripts
            'run_python.sh',
            'setup.sh',
            
            # Poetry error logs
            'poetry-installer-error-*.log',
        ]
        
        self.old_database_backups = [
            'data/ballot_measures.db.backup',
            'data/ballot_measures.db.pre_dedupe_backup',
            'data/ballot_measures_test_backup.db',
            'data/ballot_measures_backup_*.db',
        ]
        
        self.old_logs = [
            'logs/migration_test*.log',
            'logs/test_*.log',
        ]
        
        # Archive directories to consider (older than X days)
        self.archive_age_days = 7  # Keep archives for at least a week
        
    def log(self, message, color=None):
        """Log a message with optional color"""
        if color:
            print(f"{color}{message}{RESET}")
        else:
            print(message)
    
    def get_size(self, path):
        """Get size of file or directory in bytes"""
        path = Path(path)
        if path.is_file():
            return path.stat().st_size
        elif path.is_dir():
            return sum(f.stat().st_size for f in path.rglob('*') if f.is_file())
        return 0
    
    def format_size(self, size):
        """Format size in human-readable format"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
    
    def check_project_health(self):
        """Verify the project is in a healthy state before cleanup"""
        self.log("\n🔍 Checking project health...", BLUE)
        
        required_dirs = ['src', 'scripts', 'data', 'tests', 'docs']
        required_files = ['Makefile', 'requirements.txt', 'data/ballot_measures.db']
        
        all_good = True
        
        for dir_name in required_dirs:
            dir_path = self.base_dir / dir_name
            if dir_path.exists():
                self.log(f"  ✅ {dir_name}/ exists", GREEN)
            else:
                self.log(f"  ❌ {dir_name}/ missing!", RED)
                all_good = False
        
        for file_name in required_files:
            file_path = self.base_dir / file_name
            if file_path.exists():
                size = self.format_size(self.get_size(file_path))
                self.log(f"  ✅ {file_name} exists ({size})", GREEN)
            else:
                self.log(f"  ❌ {file_name} missing!", RED)
                all_good = False
        
        if not all_good:
            self.log("\n⚠️  Project structure incomplete! Fix issues before cleanup.", RED)
            return False
        
        self.log("\n✅ Project structure looks healthy!", GREEN)
        return True
    
    def consolidate_database_backups(self):
        """Consolidate database backups into a single directory"""
        self.log("\n📦 Consolidating database backups...", BLUE)
        
        backups_dir = self.base_dir / 'data' / 'backups'
        
        if not self.dry_run:
            backups_dir.mkdir(exist_ok=True)
        
        # Find all database backup files
        backup_patterns = [
            'data/*.db.backup',
            'data/*.db.pre_dedupe_backup',
            'data/*_test_backup.db',
            'data/*_backup_*.db',
        ]
        
        consolidated = 0
        for pattern in backup_patterns:
            for backup_file in self.base_dir.glob(pattern):
                if backup_file.name == 'ballot_measures.db':
                    continue  # Skip main database
                
                dest = backups_dir / backup_file.name
                size = self.get_size(backup_file)
                
                if self.dry_run:
                    self.log(f"  Would move: {backup_file.name} → backups/ ({self.format_size(size)})", YELLOW)
                else:
                    shutil.move(str(backup_file), str(dest))
                    self.log(f"  Moved: {backup_file.name} → backups/", GREEN)
                
                consolidated += 1
                self.actions.append(f"Consolidated backup: {backup_file.name}")
        
        if consolidated > 0:
            self.log(f"  Consolidated {consolidated} backup files", GREEN)
        else:
            self.log("  No backup files to consolidate", YELLOW)
    
    def remove_directories(self):
        """Remove unnecessary directories"""
        self.log("\n🗑️  Removing unnecessary directories...", BLUE)
        
        for dir_name in self.dirs_to_remove:
            dir_path = self.base_dir / dir_name
            
            if dir_path.exists():
                size = self.get_size(dir_path)
                
                if self.dry_run:
                    self.log(f"  Would remove: {dir_name}/ ({self.format_size(size)})", YELLOW)
                else:
                    shutil.rmtree(dir_path)
                    self.log(f"  Removed: {dir_name}/ ({self.format_size(size)})", GREEN)
                
                self.space_saved += size
                self.actions.append(f"Removed directory: {dir_name}/")
            else:
                self.log(f"  Skip: {dir_name}/ (not found)", YELLOW)
    
    def remove_files(self):
        """Remove unnecessary files"""
        self.log("\n🗑️  Removing unnecessary files...", BLUE)
        
        for file_pattern in self.files_to_remove:
            # Handle wildcards
            if '*' in file_pattern:
                files = list(self.base_dir.glob(file_pattern))
            else:
                file_path = self.base_dir / file_pattern
                files = [file_path] if file_path.exists() else []
            
            for file_path in files:
                if file_path.exists():
                    size = self.get_size(file_path)
                    
                    if self.dry_run:
                        self.log(f"  Would remove: {file_path.name} ({self.format_size(size)})", YELLOW)
                    else:
                        file_path.unlink()
                        self.log(f"  Removed: {file_path.name} ({self.format_size(size)})", GREEN)
                    
                    self.space_saved += size
                    self.actions.append(f"Removed file: {file_path.name}")
    
    def clean_old_logs(self):
        """Clean old log files"""
        self.log("\n📝 Cleaning old logs...", BLUE)
        
        logs_dir = self.base_dir / 'logs'
        if not logs_dir.exists():
            self.log("  No logs directory found", YELLOW)
            return
        
        for pattern in self.old_logs:
            for log_file in self.base_dir.glob(pattern):
                size = self.get_size(log_file)
                
                if self.dry_run:
                    self.log(f"  Would remove: {log_file.name} ({self.format_size(size)})", YELLOW)
                else:
                    log_file.unlink()
                    self.log(f"  Removed: {log_file.name} ({self.format_size(size)})", GREEN)
                
                self.space_saved += size
                self.actions.append(f"Removed log: {log_file.name}")
    
    def clean_old_archives(self):
        """Clean old archive and backup directories"""
        self.log(f"\n📦 Checking archive directories (older than {self.archive_age_days} days)...", BLUE)
        
        cutoff_date = datetime.now() - timedelta(days=self.archive_age_days)
        
        patterns = ['archive_*', 'backup_*']
        old_archives = []
        
        for pattern in patterns:
            for archive_dir in self.base_dir.glob(pattern):
                if archive_dir.is_dir():
                    # Parse timestamp from directory name
                    try:
                        timestamp_str = archive_dir.name.split('_', 1)[1]
                        dir_date = datetime.strptime(timestamp_str, '%Y%m%d_%H%M%S')
                        
                        if dir_date < cutoff_date:
                            old_archives.append(archive_dir)
                    except (ValueError, IndexError):
                        self.log(f"  Warning: Could not parse date from {archive_dir.name}", YELLOW)
        
        if old_archives:
            self.log(f"  Found {len(old_archives)} old archive(s):", YELLOW)
            for archive in old_archives:
                size = self.get_size(archive)
                age_days = (datetime.now() - datetime.strptime(archive.name.split('_', 1)[1], '%Y%m%d_%H%M%S')).days
                self.log(f"    • {archive.name} ({self.format_size(size)}, {age_days} days old)")
            
            if not self.force:
                self.log(f"\n  Use --remove-old-archives to remove these", YELLOW)
            else:
                for archive in old_archives:
                    size = self.get_size(archive)
                    if self.dry_run:
                        self.log(f"  Would remove: {archive.name}/ ({self.format_size(size)})", YELLOW)
                    else:
                        shutil.rmtree(archive)
                        self.log(f"  Removed: {archive.name}/ ({self.format_size(size)})", GREEN)
                    
                    self.space_saved += size
                    self.actions.append(f"Removed old archive: {archive.name}")
        else:
            self.log("  No old archives to remove", GREEN)
    
    def clean_data_directory(self):
        """Clean duplicate files in data directory"""
        self.log("\n📊 Cleaning data directory...", BLUE)
        
        data_dir = self.base_dir / 'data'
        
        # Remove duplicate/old CSV exports
        old_exports = [
            'data/ceda_combined.csv',
            'data/all_measures.json',
            'data/enhanced_measures.json',
            'data/merged_ballot_measures.json',
        ]
        
        for file_pattern in old_exports:
            file_path = self.base_dir / file_pattern
            if file_path.exists():
                size = self.get_size(file_path)
                
                if self.dry_run:
                    self.log(f"  Would remove: {file_path.name} ({self.format_size(size)})", YELLOW)
                else:
                    file_path.unlink()
                    self.log(f"  Removed: {file_path.name} ({self.format_size(size)})", GREEN)
                
                self.space_saved += size
                self.actions.append(f"Removed old data file: {file_path.name}")
    
    def create_cleanup_report(self):
        """Create a report of cleanup actions"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'dry_run': self.dry_run,
            'actions': self.actions,
            'space_saved_bytes': self.space_saved,
            'space_saved_readable': self.format_size(self.space_saved)
        }
        
        if not self.dry_run:
            report_path = self.base_dir / 'logs' / f'cleanup_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
            report_path.parent.mkdir(exist_ok=True)
            
            with open(report_path, 'w') as f:
                json.dump(report, f, indent=2)
            
            self.log(f"\n📄 Cleanup report saved to: {report_path}", GREEN)
        
        return report
    
    def verify_project_works(self):
        """Verify the project still works after cleanup"""
        self.log("\n🧪 Verifying project functionality...", BLUE)
        
        if self.dry_run:
            self.log("  Skipping verification in dry-run mode", YELLOW)
            return True
        
        tests = [
            ("Database accessible", "python -c 'from src.database.operations import Database; from src.config import DB_PATH; db = Database(DB_PATH); print(\"OK\")'"),
            ("Scripts executable", "python scripts/check_updates.py --help > /dev/null 2>&1"),
            ("Imports working", "python -c 'from src.scrapers import BaseScraper; from src.database import Database; print(\"OK\")'"),
        ]
        
        all_passed = True
        for test_name, command in tests:
            try:
                import subprocess
                result = subprocess.run(command, shell=True, capture_output=True, text=True)
                if result.returncode == 0:
                    self.log(f"  ✅ {test_name}", GREEN)
                else:
                    self.log(f"  ❌ {test_name} failed", RED)
                    all_passed = False
            except Exception as e:
                self.log(f"  ❌ {test_name} error: {e}", RED)
                all_passed = False
        
        return all_passed
    
    def run(self):
        """Run the complete cleanup process"""
        self.log(f"\n{BOLD}🧹 California Ballot Measures - Post-Reorganization Cleanup{RESET}")
        self.log("=" * 60)
        
        if self.dry_run:
            self.log("🔍 DRY RUN MODE - No changes will be made", YELLOW)
        else:
            self.log("⚠️  LIVE MODE - Files will be deleted!", RED)
            if not self.force:
                response = input("\nContinue with cleanup? (yes/no): ")
                if response.lower() != 'yes':
                    self.log("Cleanup cancelled.", YELLOW)
                    return False
        
        # Step 1: Check project health
        if not self.check_project_health():
            return False
        
        # Step 2: Consolidate database backups
        self.consolidate_database_backups()
        
        # Step 3: Remove unnecessary directories
        self.remove_directories()
        
        # Step 4: Remove unnecessary files
        self.remove_files()
        
        # Step 5: Clean old logs
        self.clean_old_logs()
        
        # Step 6: Clean data directory
        self.clean_data_directory()
        
        # Step 7: Handle old archives (only if --remove-old-archives)
        self.clean_old_archives()
        
        # Step 8: Create report
        report = self.create_cleanup_report()
        
        # Step 9: Verify everything still works
        if not self.dry_run:
            verification_passed = self.verify_project_works()
        else:
            verification_passed = True
        
        # Summary
        self.log("\n" + "=" * 60)
        if self.dry_run:
            self.log(f"{BOLD}✅ DRY RUN COMPLETE{RESET}", GREEN)
            self.log(f"\nWould remove {len(self.actions)} items")
            self.log(f"Would free up: {self.format_size(self.space_saved)}")
            self.log("\nTo perform actual cleanup, run without --dry-run")
        else:
            self.log(f"{BOLD}✅ CLEANUP COMPLETE!{RESET}", GREEN)
            self.log(f"\nRemoved {len(self.actions)} items")
            self.log(f"Freed up: {self.format_size(self.space_saved)}")
            
            if verification_passed:
                self.log("\n✅ All verification tests passed!", GREEN)
            else:
                self.log("\n⚠️  Some verification tests failed. Check the project!", RED)
        
        return True


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Clean up California Ballot Measures project after reorganization'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without making changes'
    )
    parser.add_argument(
        '--remove-old-archives',
        action='store_true',
        dest='force',
        help='Also remove old archive/backup directories'
    )
    parser.add_argument(
        '--archive-age-days',
        type=int,
        default=7,
        help='Consider archives older than this many days for removal (default: 7)'
    )
    
    args = parser.parse_args()
    
    cleaner = ProjectCleaner(
        dry_run=args.dry_run,
        force=args.force
    )
    
    if args.archive_age_days:
        cleaner.archive_age_days = args.archive_age_days
    
    success = cleaner.run()
    return 0 if success else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())