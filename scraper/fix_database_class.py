#!/usr/bin/env python3
"""
Fix the Database class name issue
The class in operations.py is still called DatabaseOperations but everything is trying to import Database
"""
import os
import re
from pathlib import Path

def main():
    print("🔧 Fixing Database Class Name Issue")
    print("="*60)
    
    # Path to operations.py
    ops_file = Path("src/database/operations.py")
    
    if not ops_file.exists():
        print(f"❌ Error: {ops_file} not found!")
        return False
    
    # Read the file
    with open(ops_file, 'r') as f:
        content = f.read()
    
    # Check current class name
    if "class DatabaseOperations" in content:
        print("✅ Found 'class DatabaseOperations' in operations.py")
        print("   This is the issue! The class is still named DatabaseOperations")
        print("   but everything is trying to import Database")
        print("")
        print("We have two options:")
        print("1. Rename the class to Database (recommended)")
        print("2. Change all imports back to DatabaseOperations")
        print("")
        response = input("Choose option (1 or 2): ").strip()
        
        if response == "1":
            # Option 1: Rename the class to Database
            print("\n📝 Renaming class DatabaseOperations to Database...")
            
            # Replace class definition
            content = content.replace("class DatabaseOperations", "class Database")
            
            # Also check for any self-references
            content = re.sub(r'\bDatabaseOperations\(', 'Database(', content)
            
            # Write back
            with open(ops_file, 'w') as f:
                f.write(content)
            
            print("✅ Renamed class to Database in operations.py")
            
            # Now fix the __init__.py to match
            init_file = Path("src/database/__init__.py")
            if init_file.exists():
                with open(init_file, 'r') as f:
                    init_content = f.read()
                
                # Fix the import
                init_content = re.sub(
                    r'from \.operations import \w+',
                    'from .operations import Database',
                    init_content
                )
                
                # Fix the __all__ export
                init_content = re.sub(
                    r"'DatabaseOperations'",
                    "'Database'",
                    init_content
                )
                
                # Make sure Database is in the exports
                if "'Database'" not in init_content and '"Database"' not in init_content:
                    init_content = init_content.replace(
                        "__all__ = [",
                        "__all__ = [\n    'Database',"
                    )
                
                with open(init_file, 'w') as f:
                    f.write(init_content)
                
                print("✅ Fixed src/database/__init__.py imports")
            
            return True
            
        elif response == "2":
            # Option 2: Change everything back to DatabaseOperations
            print("\n📝 Reverting all imports to use DatabaseOperations...")
            
            # Fix all Python files to use DatabaseOperations
            files_to_fix = list(Path(".").rglob("*.py"))
            
            for py_file in files_to_fix:
                # Skip archive and backup directories
                if any(part in str(py_file) for part in ['archive_', 'backup_', '__pycache__', '.git']):
                    continue
                
                try:
                    with open(py_file, 'r') as f:
                        content = f.read()
                    
                    original = content
                    
                    # Change imports back
                    content = re.sub(
                        r'from src\.database import Database\b',
                        'from src.database import DatabaseOperations',
                        content
                    )
                    content = re.sub(
                        r'from src\.database\.operations import Database\b',
                        'from src.database.operations import DatabaseOperations',
                        content
                    )
                    content = re.sub(
                        r'\bDatabase\(',
                        'DatabaseOperations(',
                        content
                    )
                    
                    if content != original:
                        with open(py_file, 'w') as f:
                            f.write(content)
                        print(f"  Fixed: {py_file.relative_to(Path('.'))}")
                
                except Exception as e:
                    print(f"  Error fixing {py_file}: {e}")
            
            return True
        else:
            print("❌ Invalid option")
            return False
            
    elif "class Database" in content:
        print("✅ Class is already named 'Database' in operations.py")
        print("   The issue might be in __init__.py")
        
        # Check and fix __init__.py
        init_file = Path("src/database/__init__.py")
        if init_file.exists():
            with open(init_file, 'r') as f:
                init_content = f.read()
            
            print(f"\n📋 Current __init__.py imports:")
            for line in init_content.split('\n'):
                if 'import' in line and not line.strip().startswith('#'):
                    print(f"   {line}")
            
            # Fix imports
            init_content = re.sub(
                r'from \.operations import \w+',
                'from .operations import Database',
                init_content
            )
            
            # Fix __all__
            if '__all__' in init_content:
                # Make sure Database is exported
                if "'Database'" not in init_content and '"Database"' not in init_content:
                    if "'DatabaseOperations'" in init_content:
                        init_content = init_content.replace("'DatabaseOperations'", "'Database'")
                    elif '"DatabaseOperations"' in init_content:
                        init_content = init_content.replace('"DatabaseOperations"', '"Database"')
            
            with open(init_file, 'w') as f:
                f.write(init_content)
            
            print("\n✅ Fixed __init__.py to properly export Database class")
        
        return True
    else:
        print("❌ Could not find class definition in operations.py")
        print("   File might be corrupted or empty")
        return False

def verify_fix():
    """Verify the fix worked"""
    print("\n🧪 Verifying fix...")
    
    import subprocess
    import sys
    
    # Test import
    result = subprocess.run(
        [sys.executable, "-c", "from src.database import Database; print('Import successful')"],
        capture_output=True,
        text=True,
        cwd=Path.cwd()
    )
    
    if result.returncode == 0:
        print("✅ Database import works!")
        return True
    else:
        print(f"❌ Import still failing: {result.stderr}")
        return False

if __name__ == "__main__":
    success = main()
    if success:
        verify_fix()
    
    print("\n" + "="*60)
    if success:
        print("✅ Fix complete! Now run:")
        print("   python verify.py")
        print("   make db-stats")
    else:
        print("❌ Fix failed. Please check the errors above.")