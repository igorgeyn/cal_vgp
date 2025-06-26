#!/usr/bin/env python3
"""
ASCII Newspaper Style Website Generator
"""

import json
import re
from pathlib import Path
from collections import defaultdict

def update_html_with_ascii_newspaper_style(scraper_data):
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
    
    # Generate ASCII newspaper style HTML
    measures_html = ""
    
    # ASCII header
    measures_html += '''
    <div class="ascii-header">
        <pre class="ascii-art">
╔══════════════════════════════════════════════════════════════════════════════╗
║                          CALIFORNIA BALLOT MEASURES                         ║
║                              GOVERNMENT GAZETTE                             ║
╚══════════════════════════════════════════════════════════════════════════════╝
        </pre>
    </div>'''
    
    # Sort years in descending order
    sorted_years = sorted(measures_by_year.keys(), reverse=True)
    
    for year in sorted_years:
        measures = measures_by_year[year]
        
        # ASCII section divider
        measures_html += f'''
        <div class="year-section-ascii">
            <pre class="section-divider">
┌────────────────────────────────────────────────────────────────────────────┐
│ YEAR: {year:<69} │
└────────────────────────────────────────────────────────────────────────────┘
            </pre>
            <div class="measures-grid-ascii">'''
        
        # Add measures for this year
        for i, measure in enumerate(measures):
            measure_text = measure.get('measure_text', 'Unknown Title')
            source = measure.get('source', 'Unknown')
            pdf_url = measure.get('pdf_url', '#')
            
            # Clean up title
            if len(measure_text) > 60:
                display_text = measure_text[:60] + "..."
            else:
                display_text = measure_text
            
            measures_html += f'''
                <div class="measure-card-ascii">
                    <div class="card-border">
                        ┌─ [{source}] {'─' * (50 - len(source))}┐
                        │ {display_text[:47]:<47} │
                        │ {'─' * 49} │
                        │ <a href="{pdf_url}" target="_blank">VIEW DOCUMENT →</a>{'':>30} │
                        └─────────────────────────────────────────────────┘
                    </div>
                </div>'''
        
        measures_html += '''
            </div>
        </div>'''
    
    # ASCII Newspaper CSS
    ascii_css = '''
    <style>
    * {
        margin: 0;
        padding: 0;
        box-sizing: border-box;
    }

    body {
        font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
        background-color: #f8f8f8;
        color: #000;
        line-height: 1.4;
        padding: 20px;
    }

    .container {
        max-width: 1000px;
        margin: 0 auto;
        background: white;
        padding: 20px;
        border: 3px solid #000;
    }

    header {
        background: #000;
        color: #fff;
        padding: 1rem;
        text-align: center;
        margin-bottom: 2rem;
    }

    header h1 {
        font-family: 'Arial Black', sans-serif;
        font-size: 2rem;
        font-weight: 900;
        letter-spacing: 3px;
        text-transform: uppercase;
    }

    header p {
        font-family: 'Arial', sans-serif;
        font-size: 0.9rem;
        margin-top: 0.5rem;
        letter-spacing: 1px;
    }

    .ascii-header {
        margin-bottom: 2rem;
        text-align: center;
    }

    .ascii-art {
        font-family: 'Monaco', 'Menlo', monospace;
        font-size: 0.8rem;
        background: #000;
        color: #0f0;
        padding: 1rem;
        border: 2px solid #000;
        overflow-x: auto;
    }

    .search-section {
        background: #fff;
        border: 2px solid #000;
        padding: 1rem;
        margin-bottom: 2rem;
    }

    .search-container {
        display: flex;
        gap: 1rem;
        align-items: center;
        flex-wrap: wrap;
    }

    .search-input, .filter-select {
        font-family: 'Arial', sans-serif;
        padding: 8px;
        border: 2px solid #000;
        background: #fff;
        font-size: 14px;
    }

    .search-btn {
        padding: 8px 16px;
        background: #000;
        color: #fff;
        border: 2px solid #000;
        font-family: 'Arial', sans-serif;
        font-weight: bold;
        cursor: pointer;
        text-transform: uppercase;
    }

    .search-btn:hover {
        background: #333;
    }

    .stats-bar {
        background: #000;
        color: #fff;
        padding: 1rem;
        margin-bottom: 2rem;
        border: 2px solid #000;
    }

    .stats-container {
        display: flex;
        justify-content: space-between;
        font-family: 'Arial', sans-serif;
        font-weight: bold;
    }

    .year-section-ascii {
        margin-bottom: 3rem;
        border: 2px solid #000;
        background: #fff;
    }

    .section-divider {
        font-family: 'Monaco', 'Menlo', monospace;
        font-size: 0.8rem;
        background: #000;
        color: #fff;
        padding: 0.5rem;
        margin: 0;
        overflow-x: auto;
    }

    .measures-grid-ascii {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
        gap: 1rem;
        padding: 1rem;
        background: #f5f5f5;
    }

    .measure-card-ascii {
        background: #fff;
        border: 2px solid #000;
        font-family: 'Monaco', 'Menlo', monospace;
        font-size: 0.75rem;
    }

    .card-border {
        padding: 0.5rem;
        white-space: pre-line;
        line-height: 1.2;
        background: #fff;
    }

    .card-border a {
        color: #000;
        text-decoration: underline;
        font-weight: bold;
    }

    .card-border a:hover {
        background: #000;
        color: #fff;
    }

    footer {
        background: #000;
        color: #fff;
        text-align: center;
        padding: 2rem;
        margin-top: 3rem;
        font-family: 'Arial', sans-serif;
    }

    @media (max-width: 768px) {
        body {
            padding: 10px;
        }
        
        .container {
            padding: 10px;
        }
        
        .ascii-art {
            font-size: 0.6rem;
        }
        
        .measures-grid-ascii {
            grid-template-columns: 1fr;
        }
        
        .card-border {
            font-size: 0.7rem;
        }
    }
    </style>'''
    
    # Replace the entire content with ASCII newspaper style
    pattern = r'<style>.*?</style>'
    updated_html = re.sub(pattern, ascii_css, html_content, flags=re.DOTALL)
    
    # Replace the measures content
    measures_pattern = r'<div class="measures-grid".*?<!-- Loading state'
    replacement = f'{measures_html}\n            <!-- Loading state'
    updated_html = re.sub(measures_pattern, replacement, updated_html, flags=re.DOTALL)
    
    # Write the ASCII newspaper version
    output_file = Path('ascii_ballot_measures.html')
    output_file.write_text(updated_html)
    print(f"📄 ASCII Newspaper version saved: {output_file}")

def run_ascii_update():
    # Load existing data
    try:
        with open('data/all_measures.json', 'r') as f:
            data = json.load(f)
        update_html_with_ascii_newspaper_style(data)
        print("✅ ASCII newspaper website created!")
    except FileNotFoundError:
        print("❌ No scraped data found. Run 'python enhanced_scraper.py' first.")

if __name__ == "__main__":
    run_ascii_update()