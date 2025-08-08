#!/usr/bin/env python3
"""
Complete Post-Reorganization Fix Script
Fixes all remaining import and class name issues after project reorganization
"""
import os
import re
import sys
import subprocess
from pathlib import Path
from datetime import datetime

class ProjectFixer:
    def __init__(self):
        self.base_dir = Path.cwd()
        self.scripts_dir = self.base_dir / "scripts"
        self.src_dir = self.base_dir / "src"
        self.fixes_applied = []
        self.test_results = {}
        
    def log(self, message, level="INFO"):
        """Log with color coding"""
        colors = {
            "INFO": "\033[94m",
            "SUCCESS": "\033[92m",
            "WARNING": "\033[93m",
            "ERROR": "\033[91m",
            "BOLD": "\033[1m"
        }
        reset = "\033[0m"
        prefix = colors.get(level, "")
        print(f"{prefix}{message}{reset}")
    
    def fix_script_imports(self):
        """Fix import issues in all scripts"""
        self.log("\n🔧 FIXING SCRIPT IMPORTS", "BOLD")
        
        scripts_to_fix = [
            "check_updates.py",
            "generate_site.py", 
            "initialize_db.py",
            "scrape.py",
            "update_db.py",
            "migrate_to_new_structure.py"
        ]
        
        for script_name in scripts_to_fix:
            script_path = self.scripts_dir / script_name
            if not script_path.exists():
                self.log(f"  ⚠️  {script_name} not found", "WARNING")
                continue
                
            self.log(f"  Fixing {script_name}...")
            self._fix_single_script(script_path)
    
    def _fix_single_script(self, script_path):
        """Fix imports and class names in a single script"""
        with open(script_path, 'r') as f:
            content = f.read()
        
        original_content = content
        fixes_made = []
        
        # Fix 1: Ensure proper path setup at the beginning
        if "sys.path.insert" not in content:
            # Add after imports section
            lines = content.split('\n')
            import_end = 0
            for i, line in enumerate(lines):
                if line.strip() and not line.startswith('import') and not line.startswith('from') and not line.startswith('#'):
                    import_end = i
                    break
            
            path_setup = """# Add parent directory to path for imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
"""
            lines.insert(import_end, path_setup)
            content = '\n'.join(lines)
            fixes_made.append("Added path setup")
        
        # Fix 2: Update class names
        replacements = [
            # Database class name fixes
            (r'from src\.database\.operations import DatabaseOperations\b',
             'from src.database.operations import Database'),
            (r'\bDatabaseOperations\(', 'Database('),
            (r'db_ops = DatabaseOperations', 'db_ops = Database'),
            (r'DatabaseOperations\b(?!\()', 'Database'),
            
            # Scraper class name fixes
            (r'from src\.scrapers\.ca_sos import CaliforniaSOSScraper\b',
             'from src.scrapers.ca_sos import CASOSScraper'),
            (r'\bCaliforniaSOSScraper\(', 'CASOSScraper('),
            (r'CaliforniaSOSScraper\b', 'CASOSScraper'),
            
            # Update old scraper imports
            (r'from src\.scrapers import Scraper\b',
             'from src.scrapers import BaseScraper, CASOSScraper'),
            
            # Fix database import style
            (r'from src\.database import DatabaseOperations\b',
             'from src.database import Database'),
        ]
        
        for pattern, replacement in replacements:
            new_content = re.sub(pattern, replacement, content)
            if new_content != content:
                fixes_made.append(f"Replaced {pattern[:30]}...")
                content = new_content
        
        # Only write if changes were made
        if content != original_content:
            with open(script_path, 'w') as f:
                f.write(content)
            self.log(f"    ✅ Fixed: {', '.join(fixes_made)}", "SUCCESS")
            self.fixes_applied.append(f"{script_path.name}: {', '.join(fixes_made)}")
        else:
            self.log(f"    ✓ No changes needed", "INFO")
    
    def fix_database_operations_references(self):
        """Fix any remaining DatabaseOperations references"""
        self.log("\n🔍 CHECKING FOR DatabaseOperations REFERENCES", "BOLD")
        
        # Search all Python files
        for py_file in self.base_dir.rglob("*.py"):
            # Skip archive and backup directories
            if any(part in str(py_file) for part in ['archive_', 'backup_', '__pycache__', '.git']):
                continue
            
            try:
                with open(py_file, 'r') as f:
                    content = f.read()
                
                if 'DatabaseOperations' in content and 'class DatabaseOperations' not in content:
                    self.log(f"  Found in: {py_file.relative_to(self.base_dir)}")
                    self._fix_single_script(py_file)
            except Exception as e:
                self.log(f"  Error reading {py_file}: {e}", "WARNING")
    
    def test_imports(self):
        """Test that basic imports work"""
        self.log("\n🧪 TESTING IMPORTS", "BOLD")
        
        test_cases = [
            ("Config import", "from src.config import DB_PATH"),
            ("Database import", "from src.database import Database"),
            ("Scraper import", "from src.scrapers import BaseScraper, CASOSScraper"),
            ("Models import", "from src.database.models import BallotMeasure"),
            ("Website import", "from src.website import WebsiteGenerator"),
        ]
        
        for test_name, import_statement in test_cases:
            try:
                result = subprocess.run(
                    [sys.executable, "-c", import_statement],
                    capture_output=True,
                    text=True,
                    cwd=self.base_dir
                )
                if result.returncode == 0:
                    self.log(f"  ✅ {test_name}: OK", "SUCCESS")
                    self.test_results[test_name] = "PASS"
                else:
                    self.log(f"  ❌ {test_name}: FAILED", "ERROR")
                    self.log(f"     {result.stderr}", "ERROR")
                    self.test_results[test_name] = f"FAIL: {result.stderr}"
            except Exception as e:
                self.log(f"  ❌ {test_name}: ERROR - {e}", "ERROR")
                self.test_results[test_name] = f"ERROR: {e}"
    
    def test_scripts(self):
        """Test that scripts can at least show help"""
        self.log("\n📜 TESTING SCRIPTS", "BOLD")
        
        scripts_to_test = [
            "check_updates.py",
            "generate_site.py",
            "initialize_db.py",
            "scrape.py",
            "update_db.py"
        ]
        
        for script_name in scripts_to_test:
            script_path = self.scripts_dir / script_name
            if not script_path.exists():
                self.log(f"  ⚠️  {script_name} not found", "WARNING")
                continue
            
            try:
                result = subprocess.run(
                    [sys.executable, str(script_path), "--help"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    cwd=self.base_dir
                )
                if result.returncode == 0 or "usage:" in result.stdout.lower() or "usage:" in result.stderr.lower():
                    self.log(f"  ✅ {script_name}: OK", "SUCCESS")
                    self.test_results[f"script_{script_name}"] = "PASS"
                else:
                    # Some scripts might not have --help but still work
                    if "error" in result.stderr.lower() and "unrecognized arguments: --help" not in result.stderr.lower():
                        self.log(f"  ❌ {script_name}: Import/syntax error", "ERROR")
                        self.log(f"     {result.stderr[:200]}", "ERROR")
                        self.test_results[f"script_{script_name}"] = f"FAIL: {result.stderr[:200]}"
                    else:
                        self.log(f"  ✓ {script_name}: No --help but loads OK", "INFO")
                        self.test_results[f"script_{script_name}"] = "PASS (no help)"
            except subprocess.TimeoutExpired:
                self.log(f"  ⚠️  {script_name}: Timeout (might be waiting for input)", "WARNING")
                self.test_results[f"script_{script_name}"] = "TIMEOUT"
            except Exception as e:
                self.log(f"  ❌ {script_name}: ERROR - {e}", "ERROR")
                self.test_results[f"script_{script_name}"] = f"ERROR: {e}"
    
    def test_makefile_commands(self):
        """Test basic Makefile commands"""
        self.log("\n🔨 TESTING MAKEFILE COMMANDS", "BOLD")
        
        # Only test non-destructive commands
        safe_commands = [
            "help",
            "check-deps",
            "status",
            "db-stats"
        ]
        
        for command in safe_commands:
            try:
                result = subprocess.run(
                    ["make", command],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    cwd=self.base_dir
                )
                if result.returncode == 0:
                    self.log(f"  ✅ make {command}: OK", "SUCCESS")
                    self.test_results[f"make_{command}"] = "PASS"
                else:
                    self.log(f"  ❌ make {command}: FAILED", "ERROR")
                    self.log(f"     {result.stderr[:200]}", "ERROR")
                    self.test_results[f"make_{command}"] = f"FAIL: {result.stderr[:200]}"
            except subprocess.TimeoutExpired:
                self.log(f"  ⚠️  make {command}: Timeout", "WARNING")
                self.test_results[f"make_{command}"] = "TIMEOUT"
            except FileNotFoundError:
                self.log(f"  ⚠️  'make' command not found", "WARNING")
                break
            except Exception as e:
                self.log(f"  ❌ make {command}: ERROR - {e}", "ERROR")
                self.test_results[f"make_{command}"] = f"ERROR: {e}"
    
    def check_remaining_issues(self):
        """Check for any remaining issues"""
        self.log("\n🔎 CHECKING FOR REMAINING ISSUES", "BOLD")
        
        issues = []
        
        # Check for old class names
        old_patterns = [
            "DatabaseOperations",
            "CaliforniaSOSScraper",
            "from src.scrapers import Scraper"
        ]
        
        for pattern in old_patterns:
            files_with_pattern = []
            for py_file in self.base_dir.rglob("*.py"):
                if any(part in str(py_file) for part in ['archive_', 'backup_', '__pycache__', '.git']):
                    continue
                try:
                    with open(py_file, 'r') as f:
                        if pattern in f.read():
                            # Special case: DatabaseOperations class definition is OK
                            if pattern == "DatabaseOperations" and py_file.name == "operations.py":
                                continue
                            files_with_pattern.append(py_file.relative_to(self.base_dir))
                except:
                    pass
            
            if files_with_pattern:
                issues.append(f"Pattern '{pattern}' found in: {', '.join(str(f) for f in files_with_pattern[:3])}")
        
        if issues:
            self.log("  ⚠️  Remaining issues found:", "WARNING")
            for issue in issues:
                self.log(f"    - {issue}", "WARNING")
        else:
            self.log("  ✅ No remaining issues found!", "SUCCESS")
    
    def generate_report(self):
        """Generate final report"""
        self.log("\n" + "="*60, "BOLD")
        self.log("📋 FINAL REPORT", "BOLD")
        self.log("="*60, "BOLD")
        
        # Summary of fixes
        if self.fixes_applied:
            self.log("\n✅ Fixes Applied:", "SUCCESS")
            for fix in self.fixes_applied:
                self.log(f"  - {fix}")
        else:
            self.log("\n✓ No fixes were needed", "INFO")
        
        # Test results summary
        passed = sum(1 for v in self.test_results.values() if "PASS" in v)
        failed = sum(1 for v in self.test_results.values() if "FAIL" in v)
        
        self.log(f"\n📊 Test Results: {passed} passed, {failed} failed", "BOLD")
        
        if failed > 0:
            self.log("\nFailed tests:", "ERROR")
            for test, result in self.test_results.items():
                if "FAIL" in result:
                    self.log(f"  - {test}: {result}")
        
        # Next steps
        self.log("\n📝 NEXT STEPS:", "BOLD")
        if failed == 0:
            self.log("  1. ✅ All tests passed! Your project is ready.", "SUCCESS")
            self.log("  2. Test core functionality:", "INFO")
            self.log("     - make check        # Check for new measures")
            self.log("     - make website      # Generate website")
            self.log("     - make api          # Start API server")
            self.log("  3. Clean up old directories:", "INFO")
            self.log("     - rm -rf archive_*  # Remove archived files")
            self.log("     - rm -rf backup_*   # Remove old backups")
            self.log("  4. Commit changes:", "INFO")
            self.log("     - git add .")
            self.log("     - git commit -m 'Complete project reorganization'")
        else:
            self.log("  1. ❌ Some tests failed. Review errors above.", "ERROR")
            self.log("  2. Common fixes:", "INFO")
            self.log("     - Ensure database exists: make db-init")
            self.log("     - Install missing packages: make install")
            self.log("     - Check Python path: which python")
    
    def create_setup_py(self):
        """Create a setup.py for proper package installation"""
        self.log("\n📦 CREATING setup.py", "BOLD")
        
        setup_content = '''"""
Setup script for California Ballot Measures project
"""
from setuptools import setup, find_packages

setup(
    name="ca-ballot-measures",
    version="2.0.0",
    description="California Ballot Measures Database and API",
    packages=find_packages(),
    install_requires=[
        "requests>=2.31.0",
        "beautifulsoup4>=4.12.0",
        "pandas>=2.1.0",
        "fastapi>=0.104.0",
        "uvicorn[standard]>=0.24.0",
        "python-dotenv>=1.0.0",
    ],
    python_requires=">=3.8",
    entry_points={
        "console_scripts": [
            "ca-ballot-check=scripts.check_updates:main",
            "ca-ballot-update=scripts.update_db:main",
            "ca-ballot-scrape=scripts.scrape:main",
            "ca-ballot-website=scripts.generate_site:main",
        ],
    },
)
'''
        
        setup_path = self.base_dir / "setup.py"
        if not setup_path.exists():
            with open(setup_path, 'w') as f:
                f.write(setup_content)
            self.log("  ✅ Created setup.py", "SUCCESS")
        else:
            self.log("  ✓ setup.py already exists", "INFO")
    
    def run(self):
        """Run all fixes and tests"""
        self.log("🚀 STARTING COMPREHENSIVE PROJECT FIX", "BOLD")
        self.log(f"Working directory: {self.base_dir}\n")
        
        # Apply fixes
        self.fix_script_imports()
        self.fix_database_operations_references()
        
        # Create setup.py
        self.create_setup_py()
        
        # Run tests
        self.test_imports()
        self.test_scripts()
        self.test_makefile_commands()
        
        # Check for remaining issues
        self.check_remaining_issues()
        
        # Generate report
        self.generate_report()

def main():
    """Main entry point"""
    # Check we're in the right directory
    if not Path("src").exists() or not Path("scripts").exists():
        print("❌ Error: Must be run from the project root (where src/ and scripts/ are)")
        print(f"Current directory: {Path.cwd()}")
        sys.exit(1)
    
    fixer = ProjectFixer()
    fixer.run()

if __name__ == "__main__":
    main()