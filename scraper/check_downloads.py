#!/usr/bin/env python3
"""
Check if downloaded historical data files are in the correct location
"""

from pathlib import Path
import shutil

def check_and_copy_files():
    """Check for downloaded files and copy them if needed"""
    
    files_to_check = [
        ('ncsl_ballot_measures_2014_present.xlsx', 'NCSL data (2014-present)'),
        ('ncslballotmeasures_icpsr_1902_2016.csv', 'ICPSR data (1902-2016)')
    ]
    
    # Possible locations
    locations = [
        Path('downloaded'),           # In scraper directory
        Path('../downloaded'),        # In repository root
        Path('data/downloaded'),      # In scraper/data/downloaded
        Path('.')                    # Current directory
    ]
    
    print("🔍 Checking for downloaded historical data files...")
    print("=" * 50)
    
    all_found = True
    
    for filename, description in files_to_check:
        print(f"\n📄 {description}")
        print(f"   File: {filename}")
        
        found = False
        found_path = None
        
        # Check all locations
        for location in locations:
            file_path = location / filename
            if file_path.exists():
                found = True
                found_path = file_path
                print(f"   ✅ Found at: {file_path}")
                break
        
        if not found:
            print(f"   ❌ NOT FOUND")
            all_found = False
        else:
            # Ensure it's in the data/downloaded/ directory
            target_dir = Path('data/downloaded')
            target_dir.mkdir(parents=True, exist_ok=True)
            target_path = target_dir / filename
            
            if found_path != target_path and not target_path.exists():
                print(f"   📋 Copying to: {target_path}")
                shutil.copy2(found_path, target_path)
    
    print("\n" + "=" * 50)
    
    if all_found:
        print("✅ All required files found!")
        print("\nYou can now run:")
        print("  make merge    # Merge historical data")
        print("  make db       # Create database")
    else:
        print("❌ Some files are missing!")
        print("\nPlease ensure you have:")
        print("1. ncsl_ballot_measures_2014_present.xlsx")
        print("2. ncslballotmeasures_icpsr_1902_2016.csv")
        print("\nPlace them in one of these directories:")
        print("  - scraper/downloaded/")
        print("  - scraper/data/downloaded/")
        print("  - downloaded/ (repository root)")
    
    return all_found

if __name__ == "__main__":
    check_and_copy_files()