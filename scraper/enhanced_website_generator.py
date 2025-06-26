#!/usr/bin/env python3
"""
Enhanced Website Generator 
Automatically uses summaries from the enhanced scraper data
"""

import json
import re
from pathlib import Path
from collections import defaultdict

def update_html_with_auto_summaries(scraper_data):
    """Generate website using summaries from enhanced scraper data"""
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
    
    # Generate enhanced HTML
    measures_html = ""
    total_summaries = scraper_data.get('measures_with_summaries', 0)
    
    # Enhanced header with summary count
    measures_html += f'''
    <div class="newspaper-header">
        <h1>CALIFORNIA BALLOT MEASURES</h1>
        <p>Complete Archive • Organized by Year • {total_summaries} Detailed Summaries • All {scraper_data.get('total_measures', 0)} Measures Shown</p>
        <hr>
    </div>'''
    
    # Sort years descending
    sorted_years = sorted(measures_by_year.keys(), reverse=True)
    
    for year in sorted_years:
        measures = measures_by_year[year]
        year_summaries = sum(1 for m in measures if m.get('has_summary'))
        
        measures_html += f'''
        <div class="year-section">
            <h2>{year} <span class="year-stats">({len(measures)} measures, {year_summaries} with summaries)</span></h2>
            <div class="measures-list">'''
        
        # Show ALL measures: ones with summaries first, then all others
        sorted_measures = sorted(measures, key=lambda x: not x.get('has_summary', False))
        
        for measure in sorted_measures:
            measure_text = measure.get('measure_text', 'Unknown Title')
            source = measure.get('source', 'Unknown')
            pdf_url = measure.get('pdf_url', '#')
            has_summary = measure.get('has_summary', False)
            
            if has_summary:
                summary_title = measure.get('summary_title', 'Summary Available')
                summary_text = measure.get('summary_text', 'No summary text available.')
                
                measures_html += f'''
                    <div class="measure-item-enhanced">
                        <div class="measure-header">
                            <span class="source-tag">[{source}]</span>
                            <span class="measure-title">{measure_text}</span>
                            <span class="summary-badge">📝 Summary</span>
                            <a href="{pdf_url}" target="_blank" class="view-link">→ View PDF</a>
                        </div>
                        <div class="measure-summary">
                            <h4 class="summary-title">{summary_title}</h4>
                            <p class="summary-text">{summary_text}</p>
                        </div>
                    </div>'''
            else:
                # Show measures WITHOUT summaries in the standard format
                measures_html += f'''
                    <div class="measure-item">
                        <span class="source-tag">[{source}]</span>
                        <span class="measure-title">{measure_text}</span>
                        <a href="{pdf_url}" target="_blank" class="view-link">→ View PDF</a>
                    </div>'''
        
        measures_html += '''
            </div>
        </div>'''
    
    # Enhanced CSS with auto-summary styling
    enhanced_css = '''
    <style>
    body {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
        max-width: 1000px;
        margin: 0 auto;
        padding: 20px;
        background: #fff;
        color: #000;
        line-height: 1.6;
    }

    .newspaper-header {
        text-align: center;
        margin-bottom: 40px;
        padding-bottom: 20px;
    }

    .newspaper-header h1 {
        font-size: 32px;
        font-weight: bold;
        margin: 0 0 10px 0;
        letter-spacing: 1px;
    }

    .newspaper-header p {
        font-size: 16px;
        color: #666;
        margin: 0 0 20px 0;
    }

    hr {
        border: none;
        border-top: 3px solid #000;
        margin: 0;
    }

    .year-section {
        margin-bottom: 50px;
        border-bottom: 1px solid #ddd;
        padding-bottom: 30px;
    }

    .year-section h2 {
        font-size: 26px;
        font-weight: bold;
        margin: 0 0 20px 0;
        padding-bottom: 10px;
        border-bottom: 2px solid #000;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }

    .year-stats {
        font-size: 14px;
        color: #666;
        font-weight: normal;
    }

    .measures-list {
        /* Auto-summary enhanced layout */
    }

    .measure-item {
        display: flex;
        align-items: center;
        padding: 15px 0;
        border-bottom: 1px solid #eee;
        gap: 15px;
    }

    .measure-item-enhanced {
        padding: 25px 0;
        border-bottom: 2px solid #ddd;
        margin-bottom: 15px;
        background: #fafbfc;
        border-radius: 8px;
        padding: 20px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }

    .measure-header {
        display: flex;
        align-items: center;
        gap: 15px;
        margin-bottom: 15px;
        flex-wrap: wrap;
    }

    .measure-item:last-child,
    .measure-item-enhanced:last-child {
        border-bottom: none;
    }

    .source-tag {
        font-size: 11px;
        background: #000;
        color: #fff;
        padding: 4px 8px;
        white-space: nowrap;
        font-weight: bold;
        border-radius: 3px;
        text-transform: uppercase;
    }

    .summary-badge {
        font-size: 11px;
        background: #0066cc;
        color: #fff;
        padding: 4px 8px;
        border-radius: 3px;
        white-space: nowrap;
        font-weight: bold;
    }

    .measure-title {
        flex: 1;
        font-size: 15px;
        line-height: 1.4;
        font-weight: 600;
        min-width: 200px;
    }

    .view-link {
        color: #000;
        text-decoration: none;
        font-size: 13px;
        font-weight: bold;
        white-space: nowrap;
        padding: 6px 12px;
        border: 2px solid #000;
        border-radius: 4px;
        transition: all 0.2s ease;
    }

    .view-link:hover {
        background: #000;
        color: #fff;
        transform: translateY(-1px);
    }

    .measure-summary {
        background: #fff;
        padding: 20px;
        border-left: 4px solid #0066cc;
        margin-left: 0;
        border-radius: 0 4px 4px 0;
        box-shadow: inset 0 1px 3px rgba(0,0,0,0.1);
    }

    .summary-title {
        font-size: 18px;
        font-weight: bold;
        margin: 0 0 12px 0;
        color: #0066cc;
    }

    .summary-text {
        font-size: 15px;
        line-height: 1.7;
        margin: 0;
        color: #444;
    }

    /* Remove all the fancy stuff */
    .search-section,
    .stats-bar,
    header,
    footer {
        display: none;
    }

    @media (max-width: 768px) {
        body {
            padding: 15px;
        }
        
        .measure-item,
        .measure-header {
            flex-direction: column;
            align-items: flex-start;
            gap: 12px;
        }
        
        .measure-title {
            font-size: 14px;
            min-width: auto;
        }

        .measure-summary {
            margin-left: 0;
            padding: 15px;
        }

        .year-section h2 {
            flex-direction: column;
            align-items: flex-start;
            gap: 5px;
        }

        .summary-title {
            font-size: 16px;
        }

        .summary-text {
            font-size: 14px;
        }
    }
    </style>'''
    
    # Replace everything with enhanced version
    pattern = r'<style>.*?</style>'
    updated_html = re.sub(pattern, enhanced_css, html_content, flags=re.DOTALL)
    
    # Replace body content
    body_pattern = r'<body>.*</body>'
    new_body = f'''<body>
    {measures_html}
</body>'''
    updated_html = re.sub(body_pattern, new_body, updated_html, flags=re.DOTALL)
    
    output_file = Path('auto_enhanced_ballot_measures.html')
    output_file.write_text(updated_html)
    print(f"📄 Auto-enhanced website: {output_file}")

def run_auto_enhanced_update():
    """Use enhanced scraper data to create website with auto-summaries"""
    enhanced_data_file = Path('data/enhanced_measures.json')
    fallback_data_file = Path('data/all_measures.json')
    
    try:
        if enhanced_data_file.exists():
            print("📊 Using enhanced data with summaries...")
            with open(enhanced_data_file, 'r') as f:
                data = json.load(f)
        elif fallback_data_file.exists():
            print("📊 Using basic scraped data (no summaries)...")
            with open(fallback_data_file, 'r') as f:
                data = json.load(f)
            # Add empty summary fields for compatibility
            for measure in data.get('measures', []):
                measure['has_summary'] = False
            data['measures_with_summaries'] = 0
        else:
            print("❌ No scraped data found. Run the enhanced scraper first.")
            return
            
        update_html_with_auto_summaries(data)
        
        summary_count = data.get('measures_with_summaries', 0)
        total_measures = data.get('total_measures', len(data.get('measures', [])))
        
        print("✅ Auto-enhanced website created!")
        print(f"📈 Statistics:")
        print(f"   • Total measures: {total_measures}")
        print(f"   • With summaries: {summary_count}")
        print(f"   • Coverage: {(summary_count/total_measures*100):.1f}%")
        
    except Exception as e:
        print(f"❌ Error creating website: {e}")

if __name__ == "__main__":
    run_auto_enhanced_update()