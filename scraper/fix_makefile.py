#!/usr/bin/env python3
"""
Fix Makefile to use Database instead of DatabaseOperations
"""
from pathlib import Path
import re

def fix_makefile():
    print("🔧 FIXING MAKEFILE DATABASE REFERENCES")
    print("="*60)
    
    makefile_path = Path("Makefile")
    
    if not makefile_path.exists():
        print("❌ Makefile not found!")
        return False
    
    print(f"📝 Reading {makefile_path}...")
    with open(makefile_path, 'r') as f:
        content = f.read()
    
    original_content = content
    
    # Fix all DatabaseOperations references to Database
    replacements = [
        (r'from src\.database\.operations import DatabaseOperations',
         'from src.database.operations import Database'),
        (r'from src\.database import DatabaseOperations',
         'from src.database import Database'),
        (r'DatabaseOperations\(', 'Database('),
        (r'db = DatabaseOperations', 'db = Database'),
    ]
    
    changes_made = []
    for pattern, replacement in replacements:
        new_content = re.sub(pattern, replacement, content)
        if new_content != content:
            changes_made.append(f"{pattern[:30]}... → {replacement[:30]}...")
            content = new_content
    
    if content != original_content:
        print("\n✅ Found and fixed the following:")
        for change in changes_made:
            print(f"   • {change}")
        
        # Write back
        with open(makefile_path, 'w') as f:
            f.write(content)
        
        print(f"\n✅ Updated {makefile_path}")
        
        # Show the fixed commands
        print("\n📋 Fixed commands in Makefile:")
        for line in content.split('\n'):
            if 'Database' in line and 'python -c' in line:
                print(f"   {line.strip()[:80]}...")
        
        return True
    else:
        print("✓ No changes needed (Makefile already fixed)")
        return True

def test_makefile_commands():
    """Test the fixed Makefile commands"""
    print("\n🧪 TESTING MAKEFILE COMMANDS")
    print("="*60)
    
    import subprocess
    
    commands = ["db-stats", "status"]
    
    for cmd in commands:
        print(f"\nTesting: make {cmd}")
        try:
            result = subprocess.run(
                ["make", cmd],
                capture_output=True,
                text=True,
                timeout=5,
                cwd=Path.cwd()
            )
            
            if result.returncode == 0:
                print(f"✅ make {cmd} works!")
                # Show first few lines of output
                output_lines = result.stdout.strip().split('\n')[:5]
                for line in output_lines:
                    print(f"   {line}")
            else:
                print(f"❌ make {cmd} failed:")
                print(f"   {result.stderr[:200]}")
        except subprocess.TimeoutExpired:
            print(f"⚠️  make {cmd} timed out")
        except Exception as e:
            print(f"❌ Error testing make {cmd}: {e}")

def main():
    success = fix_makefile()
    
    if success:
        print("\n" + "="*60)
        print("✅ MAKEFILE FIXED!")
        print("="*60)
        
        # Test the commands
        test_makefile_commands()
        
        print("\n📝 Next steps:")
        print("1. Run: make db-stats")
        print("2. Run: make status")
        print("3. Run: make check")
        print("\nIf all work, your project is fully fixed! 🎉")
    else:
        print("\n❌ Fix failed")

if __name__ == "__main__":
    main()