#!/usr/bin/env python3
"""
Clean Newspaper Style Website Generator
Focus on readability and organization
"""

import json
import re
from pathlib import Path
from collections import defaultdict

def update_html_with_clean_newspaper_style(scraper_data):
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
    
    # Generate clean HTML
    measures_html = ""
    
    # Simple header
    measures_html += '''
    <div class="newspaper-header">
        <h1>CALIFORNIA BALLOT MEASURES</h1>
        <p>Complete Archive • Organized by Year</p>
        <hr>
    </div>'''
    
    # Sort years descending
    sorted_years = sorted(measures_by_year.keys(), reverse=True)
    
    for year in sorted_years:
        measures = measures_by_year[year]
        
        measures_html += f'''
        <div class="year-section">
            <h2>{year}</h2>
            <div class="measures-list">'''
        
        # Simple list format
        for measure in measures:
            measure_text = measure.get('measure_text', 'Unknown Title')
            source = measure.get('source', 'Unknown')
            pdf_url = measure.get('pdf_url', '#')
            
            measures_html += f'''
                <div class="measure-item">
                    <span class="source-tag">[{source}]</span>
                    <span class="measure-title">{measure_text}</span>
                    <a href="{pdf_url}" target="_blank" class="view-link">→ View</a>
                </div>'''
        
        measures_html += '''
            </div>
        </div>'''
    
    # Minimal, clean CSS
    clean_css = '''
    <style>
    body {
        font-family: Arial, sans-serif;
        max-width: 800px;
        margin: 0 auto;
        padding: 20px;
        background: #fff;
        color: #000;
        line-height: 1.5;
    }

    .newspaper-header {
        text-align: center;
        margin-bottom: 40px;
        padding-bottom: 20px;
    }

    .newspaper-header h1 {
        font-size: 28px;
        font-weight: bold;
        margin: 0 0 10px 0;
        letter-spacing: 1px;
    }

    .newspaper-header p {
        font-size: 14px;
        color: #666;
        margin: 0 0 20px 0;
    }

    hr {
        border: none;
        border-top: 2px solid #000;
        margin: 0;
    }

    .year-section {
        margin-bottom: 40px;
        border-bottom: 1px solid #ddd;
        padding-bottom: 30px;
    }

    .year-section h2 {
        font-size: 24px;
        font-weight: bold;
        margin: 0 0 20px 0;
        padding-bottom: 10px;
        border-bottom: 1px solid #000;
    }

    .measures-list {
        /* Simple list layout */
    }

    .measure-item {
        display: flex;
        align-items: center;
        padding: 12px 0;
        border-bottom: 1px solid #eee;
        gap: 15px;
    }

    .measure-item:last-child {
        border-bottom: none;
    }

    .source-tag {
        font-size: 11px;
        background: #000;
        color: #fff;
        padding: 3px 6px;
        white-space: nowrap;
        font-weight: bold;
    }

    .measure-title {
        flex: 1;
        font-size: 14px;
        line-height: 1.4;
    }

    .view-link {
        color: #000;
        text-decoration: none;
        font-size: 12px;
        font-weight: bold;
        white-space: nowrap;
    }

    .view-link:hover {
        text-decoration: underline;
    }

    /* Remove all the fancy stuff */
    .search-section,
    .stats-bar,
    header,
    footer {
        display: none;
    }

    @media (max-width: 600px) {
        body {
            padding: 15px;
        }
        
        .measure-item {
            flex-direction: column;
            align-items: flex-start;
            gap: 8px;
        }
        
        .measure-title {
            font-size: 13px;
        }
    }
    </style>'''
    
    # Replace everything with clean version
    pattern = r'<style>.*?</style>'
    updated_html = re.sub(pattern, clean_css, html_content, flags=re.DOTALL)
    
    # Replace body content
    body_pattern = r'<body>.*</body>'
    new_body = f'''<body>
    {measures_html}
</body>'''
    updated_html = re.sub(body_pattern, new_body, updated_html, flags=re.DOTALL)
    
    output_file = Path('clean_ballot_measures.html')
    output_file.write_text(updated_html)
    print(f"📄 Clean newspaper version: {output_file}")

def run_clean_update():
    try:
        with open('data/all_measures.json', 'r') as f:
            data = json.load(f)
        update_html_with_clean_newspaper_style(data)
        print("✅ Clean newspaper website created!")
    except FileNotFoundError:
        print("❌ No scraped data found. Run 'python enhanced_scraper.py' first.")

if __name__ == "__main__":
    run_clean_update()