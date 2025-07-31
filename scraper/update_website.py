#!/usr/bin/env python3
"""
Pipeline: Enhanced Scraper → Website with year organization
"""

import json
import re
from pathlib import Path
from collections import defaultdict

def run_scraper_and_update_site():
    print("🚀 Running enhanced scraper...")
    
    # Import and run the enhanced scraper
    import subprocess
    result = subprocess.run(['python', 'enhanced_scraper.py'], capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"❌ Scraper failed: {result.stderr}")
        return
    
    # Load the results
    with open('data/all_measures.json', 'r') as f:
        data = json.load(f)
    
    update_html_with_data(data)
    print("✅ Website updated!")

def update_html_with_data(scraper_data):
    html_file = Path('ballot_measures_site.html')
    if not html_file.exists():
        print("❌ HTML file not found. Save your HTML as 'ballot_measures_site.html'")
        return
    
    html_content = html_file.read_text()
    
    # Group measures by year
    measures_by_year = defaultdict(list)
    for measure in scraper_data.get('measures', []):
        year = measure.get('year', 'Unknown')
        measures_by_year[year].append(measure)
    
    # Generate HTML organized by year
    measures_html = ""
    
    # Sort years in descending order (newest first)
    sorted_years = sorted(measures_by_year.keys(), reverse=True)
    
    for year in sorted_years:
        measures = measures_by_year[year]
        
        # Year header
        measures_html += f'''
        <div class="year-section">
            <h2 class="year-header">{year}</h2>
            <div class="year-measures">'''
        
        # Add measures for this year (smaller tiles)
        for measure in measures:
            measure_text = measure.get('measure_text', 'Unknown Title')
            source = measure.get('source', 'Unknown')
            pdf_url = measure.get('pdf_url', '#')
            
            # Truncate long titles
            if len(measure_text) > 80:
                display_text = measure_text[:80] + "..."
            else:
                display_text = measure_text
            
            measures_html += f'''
                <div class="measure-card-small">
                    <div class="measure-header-small">
                        <span class="measure-source">{source}</span>
                    </div>
                    <h4 class="measure-title-small">{display_text}</h4>
                    <div class="measure-status-small">
                        <a href="{pdf_url}" class="read-more-small" target="_blank">View →</a>
                    </div>
                </div>'''
        
        measures_html += '''
            </div>
        </div>'''
    
    # Add CSS for the new layout
    new_css = '''
    <style>
    .year-section {
        margin-bottom: 2rem;
    }
    
    .year-header {
        font-size: 1.8rem;
        color: #667eea;
        margin-bottom: 1rem;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid #e2e8f0;
    }
    
    .year-measures {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
        gap: 1rem;
    }
    
    .measure-card-small {
        background: white;
        border-radius: 8px;
        padding: 1rem;
        box-shadow: 0 1px 4px rgba(0,0,0,0.1);
        border-left: 3px solid #667eea;
        transition: transform 0.2s ease;
    }
    
    .measure-card-small:hover {
        transform: translateY(-1px);
        box-shadow: 0 2px 8px rgba(0,0,0,0.15);
    }
    
    .measure-header-small {
        margin-bottom: 0.5rem;
    }
    
    .measure-source {
        background: #f7fafc;
        color: #4a5568;
        padding: 0.2rem 0.5rem;
        border-radius: 3px;
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    .measure-title-small {
        font-size: 0.9rem;
        font-weight: 600;
        margin-bottom: 0.5rem;
        color: #2d3748;
        line-height: 1.3;
    }
    
    .measure-status-small {
        text-align: right;
    }
    
    .read-more-small {
        color: #667eea;
        text-decoration: none;
        font-size: 0.8rem;
        font-weight: 500;
    }
    
    .read-more-small:hover {
        text-decoration: underline;
    }
    </style>'''
    
    # Replace the measures grid with new year-organized content
    pattern = r'<div class="measures-grid" id="measures-container">.*?</div>\s*<!-- Loading state'
    replacement = f'''{new_css}
            <div class="measures-container-new" id="measures-container">{measures_html}
            </div>

            <!-- Loading state'''
    
    updated_html = re.sub(pattern, replacement, html_content, flags=re.DOTALL)
    
    # Update the stats
    total_measures = scraper_data.get('total_measures', 0)
    stats_pattern = r'<span class="stat-number">(\d+)</span>\s*<span>Active Measures</span>'
    stats_replacement = f'<span class="stat-number">{total_measures}</span>\n                    <span>Total Measures</span>'
    updated_html = re.sub(stats_pattern, stats_replacement, updated_html)
    
    # Write updated HTML
    from pathlib import Path
    ROOT = Path(__file__).resolve().parent.parent  # one level up from scraper/
    output_file = ROOT / 'index.html'
    output_file.write_text(updated_html)
    print(f"📄 Updated website: {output_file}")

if __name__ == "__main__":
    run_scraper_and_update_site()