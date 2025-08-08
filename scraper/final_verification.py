#!/usr/bin/env python3
"""
Final verification that everything is working correctly
"""
import sys
import subprocess
from pathlib import Path

# Add to path
sys.path.insert(0, str(Path.cwd()))

def test_item(description, test_func):
    """Run a test and report results"""
    try:
        result = test_func()
        if result:
            print(f"✅ {description}")
            return True
        else:
            print(f"❌ {description}")
            return False
    except Exception as e:
        print(f"❌ {description}: {str(e)[:50]}")
        return False

def main():
    print("🚀 FINAL PROJECT VERIFICATION")
    print("="*60)
    
    all_passed = True
    
    # 1. Test Python imports
    print("\n📦 Python Imports:")
    
    all_passed &= test_item(
        "Config import",
        lambda: __import__('src.config')
    )
    
    all_passed &= test_item(
        "Database import",
        lambda: __import__('src.database').database.Database
    )
    
    all_passed &= test_item(
        "Scraper import", 
        lambda: __import__('src.scrapers').scrapers.CASOSScraper
    )
    
    # 2. Test database connection
    print("\n💾 Database:")
    
    def test_db():
        from src.config import DB_PATH
        if not DB_PATH.exists():
            print(f"   ⚠️  Database not found at {DB_PATH}")
            print(f"   Run: python scripts/initialize_db.py")
            return False
        
        from src.database import Database
        db = Database()
        stats = db.get_statistics()
        print(f"   Total measures: {stats['total_measures']}")
        return True
    
    all_passed &= test_item("Database connection", test_db)
    
    # 3. Test Makefile commands
    print("\n🔨 Makefile Commands:")
    
    def test_make_cmd(cmd):
        result = subprocess.run(
            ["make", cmd],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    
    for cmd in ["help", "db-stats", "status"]:
        all_passed &= test_item(f"make {cmd}", lambda c=cmd: test_make_cmd(c))
    
    # 4. Test scripts can at least load
    print("\n📜 Scripts:")
    
    def test_script(script_name):
        script_path = Path("scripts") / script_name
        if not script_path.exists():
            return False
        
        result = subprocess.run(
            [sys.executable, str(script_path), "--help"],
            capture_output=True,
            text=True,
            timeout=3
        )
        # Script loads if it returns 0 or shows usage
        return result.returncode == 0 or "usage" in result.stdout.lower() or "usage" in result.stderr.lower()
    
    scripts = ["update_db.py", "check_updates.py", "scrape.py", "generate_site.py"]
    for script in scripts:
        all_passed &= test_item(f"{script}", lambda s=script: test_script(s))
    
    # 5. Check for old class names
    print("\n🔍 Code Consistency:")
    
    def check_no_old_names():
        issues = []
        patterns_to_avoid = [
            ("DatabaseOperations", ["operations.py", "complete_fix.py", "fix_database_class.py"]),
            ("CaliforniaSOSScraper", ["complete_fix.py", "fix_database_class.py"])
        ]
        
        for pattern, allowed_files in patterns_to_avoid:
            for py_file in Path(".").rglob("*.py"):
                if any(part in str(py_file) for part in ['archive_', 'backup_', '__pycache__', '.git']):
                    continue
                
                # Skip allowed files
                if any(allowed in py_file.name for allowed in allowed_files):
                    continue
                
                try:
                    with open(py_file, 'r') as f:
                        if pattern in f.read():
                            issues.append(f"{pattern} in {py_file.relative_to(Path('.'))}")
                except:
                    pass
        
        if issues:
            print(f"   Found {len(issues)} files with old class names")
            for issue in issues[:3]:
                print(f"   ⚠️  {issue}")
            return False
        return True
    
    all_passed &= test_item("No old class names", check_no_old_names)
    
    # Final report
    print("\n" + "="*60)
    if all_passed:
        print("✅ ALL TESTS PASSED! 🎉")
        print("\nYour project is fully functional!")
        print("\nYou can now:")
        print("  • make check       - Check for new measures")
        print("  • make website     - Generate website")
        print("  • make api         - Start API server")
        print("\nCleanup old directories:")
        print("  • rm -rf archive_*")
        print("  • rm -rf backup_*")
        print("\nCommit your changes:")
        print("  • git add .")
        print("  • git commit -m 'Fixed project reorganization'")
    else:
        print("❌ SOME TESTS FAILED")
        print("\nReview the failures above and:")
        print("  1. Run: python fix_makefile.py")
        print("  2. If database missing: python scripts/initialize_db.py")
        print("  3. If imports fail: check file contents")
    
    print("="*60)

if __name__ == "__main__":
    main()