#!/usr/bin/env python3
"""
Quick diagnostic to identify the exact Database import issue
"""
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path.cwd()))

def diagnose():
    print("🔍 DIAGNOSING DATABASE IMPORT ISSUE")
    print("="*60)
    
    # 1. Check what's in operations.py
    print("\n1. Checking operations.py class name...")
    ops_file = Path("src/database/operations.py")
    
    if not ops_file.exists():
        print(f"   ❌ {ops_file} not found!")
        return
    
    with open(ops_file, 'r') as f:
        content = f.read()
    
    # Look for class definition
    import re
    class_matches = re.findall(r'^class (\w+)', content, re.MULTILINE)
    if class_matches:
        print(f"   Found classes: {', '.join(class_matches)}")
        for cls in class_matches:
            if 'Database' in cls or 'database' in cls.lower():
                print(f"   📌 Main class appears to be: {cls}")
    else:
        print("   ❌ No class definitions found!")
    
    # 2. Check what __init__.py is trying to import
    print("\n2. Checking database/__init__.py imports...")
    init_file = Path("src/database/__init__.py")
    
    if not init_file.exists():
        print(f"   ❌ {init_file} not found!")
    else:
        with open(init_file, 'r') as f:
            init_content = f.read()
        
        # Find import statements
        import_matches = re.findall(r'from [.\w]+ import ([\w, ]+)', init_content)
        for imp in import_matches:
            print(f"   Importing: {imp}")
        
        # Find __all__ exports
        all_match = re.search(r'__all__\s*=\s*\[(.*?)\]', init_content, re.DOTALL)
        if all_match:
            exports = all_match.group(1)
            print(f"   __all__ exports: {exports.strip()}")
    
    # 3. Try different import methods
    print("\n3. Testing different import methods...")
    
    test_imports = [
        ("from src.database.operations import Database", "Database"),
        ("from src.database.operations import DatabaseOperations", "DatabaseOperations"),
        ("from src.database import Database", "Database"),
        ("from src.database import DatabaseOperations", "DatabaseOperations"),
    ]
    
    for import_stmt, class_name in test_imports:
        try:
            exec(import_stmt)
            print(f"   ✅ Works: {import_stmt}")
        except ImportError as e:
            print(f"   ❌ Fails: {import_stmt}")
            print(f"      Error: {e}")
        except Exception as e:
            print(f"   ⚠️  Other error: {import_stmt}")
            print(f"      Error: {e}")
    
    # 4. Check what generate_site.py is trying to do
    print("\n4. Checking generate_site.py imports...")
    gen_file = Path("scripts/generate_site.py")
    
    if gen_file.exists():
        with open(gen_file, 'r') as f:
            lines = f.readlines()
        
        # Find database-related imports
        for i, line in enumerate(lines[:50], 1):  # Check first 50 lines
            if 'database' in line.lower() and 'import' in line:
                print(f"   Line {i}: {line.strip()}")
    
    # 5. Check Makefile database commands
    print("\n5. Checking Makefile db-stats command...")
    makefile = Path("Makefile")
    
    if makefile.exists():
        with open(makefile, 'r') as f:
            content = f.read()
        
        # Find db-stats command
        match = re.search(r'db-stats:.*?(?=^\w|\Z)', content, re.MULTILINE | re.DOTALL)
        if match:
            print("   Makefile db-stats command:")
            for line in match.group(0).split('\n')[:5]:
                if line.strip():
                    print(f"   {line}")
    
    print("\n" + "="*60)
    print("DIAGNOSIS COMPLETE")
    print("="*60)
    print("\nBased on the diagnosis above, the issue is likely:")
    print("• The class in operations.py is named 'DatabaseOperations'")
    print("• But imports are trying to use 'Database'")
    print("\nRun: python fix_database_class.py")
    print("This will give you options to fix the mismatch.")

if __name__ == "__main__":
    diagnose()