#!/usr/bin/env python3
"""
Run Complete Pipeline: Parse CEDA → Integrate → Generate Website
"""

import subprocess
import sys
from pathlib import Path

def run_step(script_name, description):
    """Run a script and check for success"""
    print(f"\n{'='*60}")
    print(f"🔄 {description}")
    print(f"{'='*60}")
    
    try:
        result = subprocess.run([sys.executable, script_name], 
                              capture_output=True, 
                              text=True, 
                              check=True)
        print(result.stdout)
        if result.stderr:
            print("Warnings:", result.stderr)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error running {script_name}:")
        print(e.stdout)
        print(e.stderr)
        return False

def main():
    """Run the complete pipeline"""
    print("🚀 CALIFORNIA BALLOT MEASURES - COMPLETE PIPELINE")
    print("=" * 60)
    
    # Check if we need to parse CEDA data
    ceda_file = Path('data/ceda_combined.csv')
    if not ceda_file.exists():
        print("\n📊 CEDA data not found. Running parser...")
        if not run_step('ceda_parser_comprehensive.py', 
                       'Step 1: Parsing CEDA data files'):
            print("\n❌ Pipeline failed at CEDA parsing step")
            return 1
    else:
        print("\n✅ CEDA data already parsed")
    
    # Run integration
    if not run_step('ceda_integration.py', 
                   'Step 2: Integrating CEDA with scraped data'):
        print("\n❌ Pipeline failed at integration step")
        return 1
    
    # Generate website
    if not run_step('enhanced_website_generator.py', 
                   'Step 3: Generating enhanced website'):
        print("\n❌ Pipeline failed at website generation step")
        return 1
    
    print("\n" + "="*60)
    print("✅ PIPELINE COMPLETE!")
    print("="*60)
    print("\n📁 Output files:")
    print("   - data/enhanced_measures.json (integrated data)")
    print("   - auto_enhanced_ballot_measures.html (website)")
    print("\n🌐 Open auto_enhanced_ballot_measures.html in your browser to view the results!")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())