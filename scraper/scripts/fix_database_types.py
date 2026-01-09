#!/usr/bin/env python3
"""
Database Migration Script - Fix Type Issues
This script fixes any type inconsistencies in the database,
particularly year fields that may be stored as strings.

Run this script to clean up the database before using the updated code.
"""
import sqlite3
import sys
from pathlib import Path
from datetime import datetime

def fix_database_types():
    """Fix all type issues in the database"""
    db_path = Path('data/ballot_measures.db')
    
    if not db_path.exists():
        print("❌ Database not found at data/ballot_measures.db")
        print("   Run 'make setup' first to create the database.")
        return False
    
    print("🔧 Fixing database type issues...")
    print("=" * 60)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 1. Check current state
        print("\n📊 Checking current database state...")
        
        # Check year types
        cursor.execute("""
            SELECT 
                typeof(year) as type,
                COUNT(*) as count
            FROM measures
            WHERE year IS NOT NULL
            GROUP BY typeof(year)
        """)
        
        type_counts = cursor.fetchall()
        print("\nYear field types found:")
        for type_info in type_counts:
            print(f"  • {type_info[0]}: {type_info[1]} records")
        
        # 2. Fix year column to be integers
        print("\n🔄 Converting year values to integers...")
        cursor.execute("""
            UPDATE measures 
            SET year = CAST(year AS INTEGER)
            WHERE year IS NOT NULL AND typeof(year) != 'integer'
        """)
        years_fixed = cursor.rowcount
        print(f"  ✅ Fixed {years_fixed} year values")
        
        # 3. Fix decade and century calculations
        print("\n🔄 Recalculating decade and century values...")
        cursor.execute("""
            UPDATE measures
            SET 
                decade = (CAST(year AS INTEGER) / 10) * 10,
                century = ((CAST(year AS INTEGER) - 1) / 100) + 1
            WHERE year IS NOT NULL
        """)
        print(f"  ✅ Updated decade and century for all records")
        
        # 4. Fix any boolean fields stored as text
        print("\n🔄 Fixing boolean fields...")
        
        # Fix is_active field
        cursor.execute("""
            UPDATE measures
            SET is_active = CASE 
                WHEN is_active IN ('True', 'true', '1', 1) THEN 1
                WHEN is_active IN ('False', 'false', '0', 0) THEN 0
                ELSE 1
            END
        """)
        
        # Fix is_duplicate field
        cursor.execute("""
            UPDATE measures
            SET is_duplicate = CASE 
                WHEN is_duplicate IN ('True', 'true', '1', 1) THEN 1
                WHEN is_duplicate IN ('False', 'false', '0', 0) THEN 0
                ELSE 0
            END
        """)
        
        # Fix has_summary field
        cursor.execute("""
            UPDATE measures
            SET has_summary = CASE 
                WHEN has_summary IN ('True', 'true', '1', 1) THEN 1
                WHEN has_summary IN ('False', 'false', '0', 0) THEN 0
                ELSE 0
            END
        """)
        
        # Fix passed field
        cursor.execute("""
            UPDATE measures
            SET passed = CASE 
                WHEN passed IN ('True', 'true', '1', 1) THEN 1
                WHEN passed IN ('False', 'false', '0', 0) THEN 0
                ELSE NULL
            END
        """)
        print("  ✅ Fixed boolean fields")
        
        # 5. Fix numeric vote fields
        print("\n🔄 Ensuring vote counts are integers...")
        for field in ['yes_votes', 'no_votes', 'total_votes']:
            cursor.execute(f"""
                UPDATE measures
                SET {field} = CAST({field} AS INTEGER)
                WHERE {field} IS NOT NULL AND typeof({field}) != 'integer'
            """)
        print("  ✅ Fixed vote count fields")
        
        # 6. Ensure update_count is integer
        cursor.execute("""
            UPDATE measures
            SET update_count = CAST(update_count AS INTEGER)
            WHERE update_count IS NOT NULL AND typeof(update_count) != 'integer'
        """)
        
        # 7. Commit all changes
        conn.commit()
        print("\n✅ All changes committed to database")
        
        # 8. Verify the fixes
        print("\n📊 Verifying fixes...")
        
        # Check year types again
        cursor.execute("""
            SELECT 
                typeof(year) as type,
                COUNT(*) as count
            FROM measures
            WHERE year IS NOT NULL
            GROUP BY typeof(year)
        """)
        
        type_counts = cursor.fetchall()
        print("\nYear field types after fix:")
        for type_info in type_counts:
            print(f"  • {type_info[0]}: {type_info[1]} records")
        
        # Get year range
        cursor.execute("""
            SELECT 
                MIN(year) as min_year,
                MAX(year) as max_year,
                COUNT(*) as total
            FROM measures
            WHERE year IS NOT NULL
        """)
        
        result = cursor.fetchone()
        print(f"\nYear range: {result[0]} - {result[1]} ({result[2]} records)")
        
        # Check for any remaining issues
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM measures
            WHERE year IS NOT NULL
            AND (typeof(year) != 'integer' OR year < 1900 OR year > 2030)
        """)
        
        issues = cursor.fetchone()[0]
        if issues > 0:
            print(f"\n⚠️  Warning: {issues} records still have year issues")
        else:
            print("\n✅ All year values are valid integers")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        conn.rollback()
        return False
        
    finally:
        conn.close()


def create_backup():
    """Create a backup of the database before making changes"""
    db_path = Path('data/ballot_measures.db')
    
    if not db_path.exists():
        return None
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = db_path.parent / f"ballot_measures_backup_{timestamp}.db"
    
    import shutil
    shutil.copy2(db_path, backup_path)
    print(f"💾 Created backup: {backup_path}")
    
    return backup_path


def main():
    """Main function"""
    print("California Ballot Measures - Database Type Migration")
    print("=" * 60)
    
    # Create backup first
    print("\n📦 Creating backup...")
    backup_path = create_backup()
    
    if not backup_path:
        print("❌ Could not create backup. Database might not exist.")
        return 1
    
    # Run the fixes
    if fix_database_types():
        print("\n" + "=" * 60)
        print("✅ Database migration completed successfully!")
        print(f"\n💾 Backup saved at: {backup_path}")
        print("\n🚀 You can now run:")
        print("   make scrape   - to get new data")
        print("   make website  - to generate the website")
        return 0
    else:
        print("\n" + "=" * 60)
        print("❌ Migration failed. Database was not modified.")
        print(f"💾 Backup available at: {backup_path}")
        return 1


if __name__ == "__main__":
    sys.exit(main())