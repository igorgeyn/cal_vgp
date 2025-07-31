#!/usr/bin/env python3
"""
Generate Static Website from Ballot Measures Data
Modern redesign with faceted navigation and progressive disclosure
"""

import json
import sqlite3
from pathlib import Path
from datetime import datetime
from collections import defaultdict, Counter
import re

def load_data_from_json():
    """Load data from JSON files (original workflow)"""
    data_files = [
        'data/enhanced_measures.json',
        'data/all_measures.json'
    ]
    
    for file_path in data_files:
        if Path(file_path).exists():
            print(f"📄 Loading data from {file_path}")
            with open(file_path, 'r') as f:
                return json.load(f)
    
    print("❌ No JSON data found")
    return None

def load_data_from_database():
    """Load data from SQLite database (new workflow)"""
    db_path = 'data/ballot_measures.db'
    
    if not Path(db_path).exists():
        return None
    
    print(f"📊 Loading data from {db_path}")
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    # Get all measures
    cursor = conn.execute("""
        SELECT * FROM measures 
        ORDER BY year DESC, title ASC
    """)
    measures = [dict(row) for row in cursor]
    
    # Get statistics
    stats = {}
    cursor = conn.execute("SELECT COUNT(*) as total FROM measures")
    stats['total_measures'] = cursor.fetchone()['total']
    
    cursor = conn.execute("SELECT MIN(year) as min_year, MAX(year) as max_year FROM measures WHERE year IS NOT NULL")
    row = cursor.fetchone()
    stats['year_min'] = row['min_year']
    stats['year_max'] = row['max_year']
    
    cursor = conn.execute("""
        SELECT 
            COUNT(CASE WHEN passed = 1 THEN 1 END) as passed,
            COUNT(CASE WHEN passed = 0 THEN 1 END) as failed
        FROM measures
    """)
    row = cursor.fetchone()
    stats['passed'] = row['passed']
    stats['failed'] = row['failed']
    
    cursor = conn.execute("SELECT COUNT(*) as count FROM measures WHERE has_summary = 1")
    stats['with_summaries'] = cursor.fetchone()['count']
    
    # Get topics with counts
    cursor = conn.execute("""
        SELECT topic_primary as topic, COUNT(*) as count
        FROM measures
        WHERE topic_primary IS NOT NULL
        GROUP BY topic_primary
        ORDER BY count DESC
        LIMIT 20
    """)
    topics = [{'topic': row['topic'], 'count': row['count']} for row in cursor]
    
    conn.close()
    
    return {
        'measures': measures,
        'statistics': stats,
        'topics': topics
    }

def generate_static_html(data):
    """Generate modern UI with faceted navigation"""
    
    # Process data
    if 'statistics' in data:
        measures = data['measures']
        stats = data['statistics']
        topics = data.get('topics', [])
    else:
        measures = data.get('measures', [])
        
        # Calculate statistics
        stats = {
            'total_measures': len(measures),
            'year_min': 1902,
            'year_max': 2026,
            'passed': sum(1 for m in measures if m.get('passed') == 1),
            'failed': sum(1 for m in measures if m.get('passed') == 0),
            'with_summaries': sum(1 for m in measures if m.get('has_summary'))
        }
        
        # Extract topics
        topic_counts = Counter()
        for measure in measures:
            topic = measure.get('topic_primary') or measure.get('topic')
            if topic:
                topic_counts[topic] += 1
        topics = [{'topic': t, 'count': c} for t, c in topic_counts.most_common(20)]
    
    # Convert to JSON for embedding
    measures_json = json.dumps(measures, default=str)
    topics_json = json.dumps(topics, default=str)
    
    # Calculate pass rate
    total_with_outcome = stats['passed'] + stats['failed']
    pass_rate = round((stats['passed'] / total_with_outcome * 100)) if total_with_outcome > 0 else 0
    
    # Generate modern HTML
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>California Ballot Measures Database</title>
    <style>
        /* Modern CSS Reset and Variables */
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        :root {{
            --primary: #1a73e8;
            --primary-dark: #1557b0;
            --success: #1e8e3e;
            --danger: #d93025;
            --warning: #f9ab00;
            --bg-primary: #ffffff;
            --bg-secondary: #f8f9fa;
            --bg-tertiary: #e8eaed;
            --text-primary: #202124;
            --text-secondary: #5f6368;
            --text-tertiary: #80868b;
            --border: #dadce0;
            --shadow-sm: 0 1px 2px 0 rgba(60,64,67,.3), 0 1px 3px 1px rgba(60,64,67,.15);
            --shadow-md: 0 1px 3px 0 rgba(60,64,67,.3), 0 4px 8px 3px rgba(60,64,67,.15);
            --radius: 8px;
            --radius-sm: 4px;
            --transition: all 0.2s ease;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
            line-height: 1.6;
            color: var(--text-primary);
            background: var(--bg-secondary);
        }}
        
        /* Header */
        .header {{
            background: var(--bg-primary);
            border-bottom: 1px solid var(--border);
            position: sticky;
            top: 0;
            z-index: 100;
            box-shadow: var(--shadow-sm);
        }}
        
        .header-content {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 1rem 2rem;
            display: flex;
            align-items: center;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 1rem;
        }}
        
        .logo {{
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }}
        
        .logo-icon {{
            width: 32px;
            height: 32px;
            background: var(--primary);
            border-radius: var(--radius-sm);
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: bold;
            font-size: 18px;
        }}
        
        .logo h1 {{
            font-size: 1.25rem;
            font-weight: 600;
            color: var(--text-primary);
        }}
        
        /* Search Bar */
        .search-container {{
            flex: 1;
            max-width: 600px;
        }}
        
        .search-box {{
            position: relative;
        }}
        
        .search-input {{
            width: 100%;
            padding: 0.75rem 1rem 0.75rem 2.75rem;
            border: 1px solid var(--border);
            border-radius: 24px;
            font-size: 1rem;
            transition: var(--transition);
            background: var(--bg-secondary);
        }}
        
        .search-input:focus {{
            outline: none;
            border-color: var(--primary);
            background: var(--bg-primary);
            box-shadow: var(--shadow-sm);
        }}
        
        .search-icon {{
            position: absolute;
            left: 1rem;
            top: 50%;
            transform: translateY(-50%);
            color: var(--text-tertiary);
        }}
        
        /* View Controls */
        .view-controls {{
            display: flex;
            gap: 0.5rem;
        }}
        
        .view-btn {{
            padding: 0.5rem 0.75rem;
            border: 1px solid var(--border);
            background: var(--bg-primary);
            border-radius: var(--radius-sm);
            cursor: pointer;
            color: var(--text-secondary);
            transition: var(--transition);
        }}
        
        .view-btn:hover {{
            background: var(--bg-secondary);
        }}
        
        .view-btn.active {{
            background: var(--primary);
            color: white;
            border-color: var(--primary);
        }}
        
        /* Main Layout */
        .main-container {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 2rem;
            display: grid;
            grid-template-columns: 280px 1fr;
            gap: 2rem;
        }}
        
        /* Sidebar Filters */
        .sidebar {{
            position: sticky;
            top: 80px;
            height: fit-content;
            max-height: calc(100vh - 100px);
            overflow-y: auto;
        }}
        
        .filter-section {{
            background: var(--bg-primary);
            border-radius: var(--radius);
            padding: 1.5rem;
            margin-bottom: 1rem;
            box-shadow: var(--shadow-sm);
        }}
        
        .filter-header {{
            font-size: 0.875rem;
            font-weight: 600;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 1rem;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }}
        
        .filter-clear {{
            font-size: 0.75rem;
            color: var(--primary);
            cursor: pointer;
            font-weight: normal;
            text-transform: none;
            letter-spacing: normal;
        }}
        
        .filter-clear:hover {{
            text-decoration: underline;
        }}
        
        /* Filter Groups */
        .filter-group {{
            margin-bottom: 1.5rem;
        }}
        
        .filter-group:last-child {{
            margin-bottom: 0;
        }}
        
        .filter-label {{
            font-size: 0.875rem;
            font-weight: 500;
            color: var(--text-primary);
            margin-bottom: 0.75rem;
        }}
        
        /* Year Range Slider */
        .year-range {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
            margin-bottom: 0.5rem;
        }}
        
        .year-input {{
            width: 70px;
            padding: 0.375rem 0.5rem;
            border: 1px solid var(--border);
            border-radius: var(--radius-sm);
            font-size: 0.875rem;
            text-align: center;
        }}
        
        .year-separator {{
            color: var(--text-tertiary);
        }}
        
        /* Filter Options */
        .filter-options {{
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
        }}
        
        .filter-option {{
            display: flex;
            align-items: center;
            padding: 0.375rem 0.5rem;
            border-radius: var(--radius-sm);
            cursor: pointer;
            transition: var(--transition);
            font-size: 0.875rem;
        }}
        
        .filter-option:hover {{
            background: var(--bg-secondary);
        }}
        
        .filter-option.active {{
            background: var(--primary);
            color: white;
        }}
        
        .filter-option-label {{
            flex: 1;
        }}
        
        .filter-option-count {{
            font-size: 0.75rem;
            opacity: 0.7;
        }}
        
        /* Topic Tags */
        .topic-tags {{
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
        }}
        
        .topic-tag {{
            padding: 0.375rem 0.75rem;
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 16px;
            font-size: 0.813rem;
            cursor: pointer;
            transition: var(--transition);
        }}
        
        .topic-tag:hover {{
            background: var(--bg-tertiary);
        }}
        
        .topic-tag.active {{
            background: var(--primary);
            color: white;
            border-color: var(--primary);
        }}
        
        /* Content Area */
        .content {{
            min-height: 100vh;
        }}
        
        /* Results Header */
        .results-header {{
            background: var(--bg-primary);
            border-radius: var(--radius);
            padding: 1.5rem;
            margin-bottom: 1.5rem;
            box-shadow: var(--shadow-sm);
            display: flex;
            align-items: center;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 1rem;
        }}
        
        .results-info {{
            display: flex;
            align-items: baseline;
            gap: 1rem;
        }}
        
        .results-count {{
            font-size: 1.5rem;
            font-weight: 600;
            color: var(--text-primary);
        }}
        
        .results-description {{
            color: var(--text-secondary);
            font-size: 0.875rem;
        }}
        
        .sort-controls {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}
        
        .sort-label {{
            font-size: 0.875rem;
            color: var(--text-secondary);
        }}
        
        .sort-select {{
            padding: 0.5rem 1rem;
            border: 1px solid var(--border);
            border-radius: var(--radius-sm);
            background: var(--bg-primary);
            font-size: 0.875rem;
        }}
        
        /* Featured Section */
        .featured-section {{
            margin-bottom: 2rem;
        }}
        
        .section-title {{
            font-size: 1.25rem;
            font-weight: 600;
            color: var(--text-primary);
            margin-bottom: 1rem;
        }}
        
        .featured-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }}
        
        /* Card Styles */
        .measure-card {{
            background: var(--bg-primary);
            border-radius: var(--radius);
            padding: 1.25rem;
            box-shadow: var(--shadow-sm);
            transition: var(--transition);
            cursor: pointer;
            display: flex;
            flex-direction: column;
            gap: 0.75rem;
        }}
        
        .measure-card:hover {{
            box-shadow: var(--shadow-md);
            transform: translateY(-1px);
        }}
        
        .measure-card.featured {{
            border-left: 4px solid var(--primary);
        }}
        
        .card-header {{
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: 1rem;
        }}
        
        .card-year {{
            font-size: 0.875rem;
            font-weight: 600;
            color: var(--text-secondary);
        }}
        
        .card-badges {{
            display: flex;
            gap: 0.5rem;
        }}
        
        .badge {{
            padding: 0.25rem 0.5rem;
            border-radius: var(--radius-sm);
            font-size: 0.75rem;
            font-weight: 500;
        }}
        
        .badge-passed {{
            background: rgba(30, 142, 62, 0.1);
            color: var(--success);
        }}
        
        .badge-failed {{
            background: rgba(217, 48, 37, 0.1);
            color: var(--danger);
        }}
        
        .badge-pending {{
            background: rgba(249, 171, 0, 0.1);
            color: var(--warning);
        }}
        
        .card-title {{
            font-size: 1rem;
            font-weight: 500;
            color: var(--text-primary);
            line-height: 1.4;
        }}
        
        .card-meta {{
            display: flex;
            flex-wrap: wrap;
            gap: 1rem;
            font-size: 0.813rem;
            color: var(--text-secondary);
        }}
        
        .meta-item {{
            display: flex;
            align-items: center;
            gap: 0.375rem;
        }}
        
        .vote-bar {{
            height: 4px;
            background: var(--bg-tertiary);
            border-radius: 2px;
            overflow: hidden;
            margin: 0.5rem 0;
        }}
        
        .vote-bar-fill {{
            height: 100%;
            background: var(--success);
            transition: width 0.3s ease;
        }}
        
        /* Grid View */
        .results-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
            gap: 1rem;
        }}
        
        /* List View */
        .results-list {{
            display: flex;
            flex-direction: column;
            gap: 0.75rem;
        }}
        
        .measure-list-item {{
            background: var(--bg-primary);
            border-radius: var(--radius);
            padding: 1rem 1.25rem;
            box-shadow: var(--shadow-sm);
            display: grid;
            grid-template-columns: auto 1fr auto;
            align-items: center;
            gap: 1rem;
            cursor: pointer;
            transition: var(--transition);
        }}
        
        .measure-list-item:hover {{
            box-shadow: var(--shadow-md);
        }}
        
        /* Stats Dashboard */
        .stats-dashboard {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }}
        
        .stat-card {{
            background: var(--bg-primary);
            border-radius: var(--radius);
            padding: 1.5rem;
            text-align: center;
            box-shadow: var(--shadow-sm);
        }}
        
        .stat-number {{
            font-size: 2rem;
            font-weight: 600;
            color: var(--primary);
            margin-bottom: 0.25rem;
        }}
        
        .stat-label {{
            font-size: 0.875rem;
            color: var(--text-secondary);
        }}
        
        /* Loading State */
        .loading {{
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 4rem;
            color: var(--text-tertiary);
        }}
        
        .spinner {{
            width: 40px;
            height: 40px;
            border: 3px solid var(--border);
            border-top-color: var(--primary);
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }}
        
        @keyframes spin {{
            to {{ transform: rotate(360deg); }}
        }}
        
        /* Empty State */
        .empty-state {{
            text-align: center;
            padding: 4rem 2rem;
            color: var(--text-secondary);
        }}
        
        .empty-icon {{
            font-size: 3rem;
            margin-bottom: 1rem;
            opacity: 0.5;
        }}
        
        /* Responsive */
        @media (max-width: 1024px) {{
            .main-container {{
                grid-template-columns: 1fr;
            }}
            
            .sidebar {{
                position: static;
                max-height: none;
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                gap: 1rem;
            }}
        }}
        
        @media (max-width: 768px) {{
            .header-content {{
                padding: 1rem;
            }}
            
            .main-container {{
                padding: 1rem;
            }}
            
            .search-container {{
                order: 3;
                flex-basis: 100%;
                max-width: none;
            }}
            
            .featured-grid,
            .results-grid {{
                grid-template-columns: 1fr;
            }}
        }}
    </style>
</head>
<body>
    <!-- Header -->
    <header class="header">
        <div class="header-content">
            <div class="logo">
                <div class="logo-icon">CA</div>
                <h1>California Ballot Measures</h1>
            </div>
            
            <div class="search-container">
                <div class="search-box">
                    <svg class="search-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="11" cy="11" r="8"></circle>
                        <path d="m21 21-4.35-4.35"></path>
                    </svg>
                    <input type="text" class="search-input" id="searchInput" placeholder="Search measures by title, topic, or year...">
                </div>
            </div>
            
            <div class="view-controls">
                <button class="view-btn active" id="gridView" onclick="setView('grid')">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                        <rect x="3" y="3" width="7" height="7"></rect>
                        <rect x="14" y="3" width="7" height="7"></rect>
                        <rect x="3" y="14" width="7" height="7"></rect>
                        <rect x="14" y="14" width="7" height="7"></rect>
                    </svg>
                </button>
                <button class="view-btn" id="listView" onclick="setView('list')">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                        <rect x="3" y="4" width="18" height="2"></rect>
                        <rect x="3" y="11" width="18" height="2"></rect>
                        <rect x="3" y="18" width="18" height="2"></rect>
                    </svg>
                </button>
            </div>
        </div>
    </header>

    <!-- Main Content -->
    <div class="main-container">
        <!-- Sidebar Filters -->
        <aside class="sidebar">
            <div class="filter-section">
                <div class="filter-header">
                    Filters
                    <span class="filter-clear" onclick="clearAllFilters()">Clear all</span>
                </div>
                
                <!-- Year Range -->
                <div class="filter-group">
                    <div class="filter-label">Year Range</div>
                    <div class="year-range">
                        <input type="number" class="year-input" id="yearMin" value="{stats['year_min']}" min="{stats['year_min']}" max="{stats['year_max']}">
                        <span class="year-separator">–</span>
                        <input type="number" class="year-input" id="yearMax" value="{stats['year_max']}" min="{stats['year_min']}" max="{stats['year_max']}">
                    </div>
                </div>
                
                <!-- Status Filter -->
                <div class="filter-group">
                    <div class="filter-label">Status</div>
                    <div class="filter-options">
                        <div class="filter-option" onclick="toggleFilter('status', 'passed')">
                            <span class="filter-option-label">Passed</span>
                            <span class="filter-option-count">{stats['passed']}</span>
                        </div>
                        <div class="filter-option" onclick="toggleFilter('status', 'failed')">
                            <span class="filter-option-label">Failed</span>
                            <span class="filter-option-count">{stats['failed']}</span>
                        </div>
                        <div class="filter-option" onclick="toggleFilter('status', 'unknown')">
                            <span class="filter-option-label">Unknown</span>
                            <span class="filter-option-count">{stats['total_measures'] - stats['passed'] - stats['failed']}</span>
                        </div>
                    </div>
                </div>
                
                <!-- Features Filter -->
                <div class="filter-group">
                    <div class="filter-label">Features</div>
                    <div class="filter-options">
                        <div class="filter-option" onclick="toggleFilter('features', 'summary')">
                            <span class="filter-option-label">Has Summary</span>
                            <span class="filter-option-count">{stats['with_summaries']}</span>
                        </div>
                        <div class="filter-option" onclick="toggleFilter('features', 'votes')">
                            <span class="filter-option-label">Has Vote Data</span>
                            <span class="filter-option-count">{sum(1 for m in measures if m.get('yes_votes') is not None)}</span>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Topic Filter -->
            <div class="filter-section">
                <div class="filter-header">Popular Topics</div>
                <div class="topic-tags" id="topicTags">
                    <!-- Will be populated by JavaScript -->
                </div>
            </div>
        </aside>

        <!-- Main Content Area -->
        <main class="content">
            <!-- Stats Dashboard -->
            <div class="stats-dashboard">
                <div class="stat-card">
                    <div class="stat-number">{stats['total_measures']:,}</div>
                    <div class="stat-label">Total Measures</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{pass_rate}%</div>
                    <div class="stat-label">Pass Rate</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{stats['year_max'] - stats['year_min']} years</div>
                    <div class="stat-label">Historical Coverage</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{len(topics)}</div>
                    <div class="stat-label">Topic Categories</div>
                </div>
            </div>

            <!-- Results Header -->
            <div class="results-header">
                <div class="results-info">
                    <div class="results-count" id="resultsCount">0</div>
                    <div class="results-description" id="resultsDescription">measures found</div>
                </div>
                <div class="sort-controls">
                    <span class="sort-label">Sort by:</span>
                    <select class="sort-select" id="sortSelect" onchange="applySort()">
                        <option value="year-desc">Year (Newest First)</option>
                        <option value="year-asc">Year (Oldest First)</option>
                        <option value="title">Title (A-Z)</option>
                        <option value="votes">Most Votes</option>
                    </select>
                </div>
            </div>

            <!-- Featured Section -->
            <div class="featured-section" id="featuredSection">
                <h2 class="section-title">Recent Measures</h2>
                <div class="featured-grid" id="featuredGrid">
                    <!-- Will be populated by JavaScript -->
                </div>
            </div>

            <!-- Results Container -->
            <div id="resultsContainer">
                <div class="loading">
                    <div class="spinner"></div>
                </div>
            </div>
        </main>
    </div>

    <script>
        // Data
        const allMeasures = {measures_json};
        const topics = {topics_json};
        
        // State
        let currentView = 'grid';
        let currentFilters = {{
            yearMin: {stats['year_min']},
            yearMax: {stats['year_max']},
            status: [],
            features: [],
            topics: [],
            search: ''
        }};
        let currentSort = 'year-desc';
        let filteredMeasures = [];
        
        // Initialize
        document.addEventListener('DOMContentLoaded', () => {{
            initializeTopicTags();
            setupEventListeners();
            applyFilters();
        }});
        
        // Initialize topic tags
        function initializeTopicTags() {{
            const container = document.getElementById('topicTags');
            container.innerHTML = topics.slice(0, 12).map(topic => `
                <div class="topic-tag" onclick="toggleTopic('${{topic.topic.replace(/'/g, "\\'")}}')">
                    ${{topic.topic}} (${{topic.count}})
                </div>
            `).join('');
        }}
        
        // Setup event listeners
        function setupEventListeners() {{
            // Search input with debounce
            let searchTimeout;
            document.getElementById('searchInput').addEventListener('input', (e) => {{
                clearTimeout(searchTimeout);
                searchTimeout = setTimeout(() => {{
                    currentFilters.search = e.target.value.toLowerCase();
                    applyFilters();
                }}, 300);
            }});
            
            // Year inputs
            document.getElementById('yearMin').addEventListener('change', (e) => {{
                currentFilters.yearMin = parseInt(e.target.value);
                applyFilters();
            }});
            
            document.getElementById('yearMax').addEventListener('change', (e) => {{
                currentFilters.yearMax = parseInt(e.target.value);
                applyFilters();
            }});
        }}
        
        // Toggle filter
        function toggleFilter(type, value) {{
            const index = currentFilters[type].indexOf(value);
            if (index > -1) {{
                currentFilters[type].splice(index, 1);
            }} else {{
                currentFilters[type].push(value);
            }}
            
            // Update UI
            updateFilterUI();
            applyFilters();
        }}
        
        // Toggle topic
        function toggleTopic(topic) {{
            const index = currentFilters.topics.indexOf(topic);
            if (index > -1) {{
                currentFilters.topics.splice(index, 1);
            }} else {{
                currentFilters.topics.push(topic);
            }}
            
            // Update UI
            updateTopicUI();
            applyFilters();
        }}
        
        // Update filter UI
        function updateFilterUI() {{
            document.querySelectorAll('.filter-option').forEach(el => {{
                el.classList.remove('active');
            }});
            
            // Update status filters
            currentFilters.status.forEach(status => {{
                const el = document.querySelector(`.filter-option[onclick="toggleFilter('status', '${{status}}')"]`);
                if (el) el.classList.add('active');
            }});
            
            // Update feature filters
            currentFilters.features.forEach(feature => {{
                const el = document.querySelector(`.filter-option[onclick="toggleFilter('features', '${{feature}}')"]`);
                if (el) el.classList.add('active');
            }});
        }}
        
        // Update topic UI
        function updateTopicUI() {{
            document.querySelectorAll('.topic-tag').forEach(el => {{
                const topic = el.textContent.split(' (')[0];
                if (currentFilters.topics.includes(topic)) {{
                    el.classList.add('active');
                }} else {{
                    el.classList.remove('active');
                }}
            }});
        }}
        
        // Apply filters
        function applyFilters() {{
            filteredMeasures = allMeasures.filter(measure => {{
                // Year filter
                const year = parseInt(measure.year);
                if (!isNaN(year)) {{
                    if (year < currentFilters.yearMin || year > currentFilters.yearMax) {{
                        return false;
                    }}
                }}
                
                // Status filter
                if (currentFilters.status.length > 0) {{
                    const passed = measure.passed;
                    if (currentFilters.status.includes('passed') && passed !== 1) {{
                        if (!currentFilters.status.includes('failed') && !currentFilters.status.includes('unknown')) {{
                            return false;
                        }}
                    }}
                    if (currentFilters.status.includes('failed') && passed !== 0) {{
                        if (!currentFilters.status.includes('passed') && !currentFilters.status.includes('unknown')) {{
                            return false;
                        }}
                    }}
                    if (currentFilters.status.includes('unknown') && (passed === 1 || passed === 0)) {{
                        if (!currentFilters.status.includes('passed') && !currentFilters.status.includes('failed')) {{
                            return false;
                        }}
                    }}
                }}
                
                // Features filter
                if (currentFilters.features.length > 0) {{
                    if (currentFilters.features.includes('summary') && !measure.has_summary) {{
                        return false;
                    }}
                    if (currentFilters.features.includes('votes') && measure.yes_votes == null) {{
                        return false;
                    }}
                }}
                
                // Topic filter
                if (currentFilters.topics.length > 0) {{
                    const measureTopic = measure.topic_primary || measure.topic || '';
                    if (!currentFilters.topics.includes(measureTopic)) {{
                        return false;
                    }}
                }}
                
                // Search filter
                if (currentFilters.search) {{
                    const searchText = [
                        measure.title,
                        measure.measure_text,
                        measure.description,
                        measure.summary_text,
                        measure.topic_primary,
                        measure.year
                    ].filter(Boolean).join(' ').toLowerCase();
                    
                    if (!searchText.includes(currentFilters.search)) {{
                        return false;
                    }}
                }}
                
                return true;
            }});
            
            // Apply sort
            sortMeasures();
            
            // Update UI
            updateResults();
        }}
        
        // Sort measures
        function sortMeasures() {{
            filteredMeasures.sort((a, b) => {{
                switch (currentSort) {{
                    case 'year-desc':
                        return (b.year || 0) - (a.year || 0);
                    case 'year-asc':
                        return (a.year || 0) - (b.year || 0);
                    case 'title':
                        const titleA = a.title || a.measure_text || '';
                        const titleB = b.title || b.measure_text || '';
                        return titleA.localeCompare(titleB);
                    case 'votes':
                        return (b.total_votes || 0) - (a.total_votes || 0);
                    default:
                        return 0;
                }}
            }});
        }}
        
        // Apply sort
        function applySort() {{
            currentSort = document.getElementById('sortSelect').value;
            sortMeasures();
            updateResults();
        }}
        
        // Update results display
        function updateResults() {{
            // Update count
            document.getElementById('resultsCount').textContent = filteredMeasures.length.toLocaleString();
            
            // Update description
            const desc = currentFilters.search ? 
                `measures matching "${{currentFilters.search}}"` : 
                'measures found';
            document.getElementById('resultsDescription').textContent = desc;
            
            // Show/hide featured section
            const featuredSection = document.getElementById('featuredSection');
            if (!currentFilters.search && currentFilters.status.length === 0 && 
                currentFilters.features.length === 0 && currentFilters.topics.length === 0 &&
                currentFilters.yearMin === {stats['year_min']} && currentFilters.yearMax === {stats['year_max']}) {{
                // Show featured section
                featuredSection.style.display = 'block';
                displayFeatured();
                displayResults(filteredMeasures.slice(5)); // Skip featured items
            }} else {{
                // Hide featured section
                featuredSection.style.display = 'none';
                displayResults(filteredMeasures);
            }}
        }}
        
        // Display featured measures
        function displayFeatured() {{
            const featured = filteredMeasures.slice(0, 5);
            const grid = document.getElementById('featuredGrid');
            
            grid.innerHTML = featured.map(measure => createCard(measure, true)).join('');
        }}
        
        // Display results
        function displayResults(measures) {{
            const container = document.getElementById('resultsContainer');
            
            if (measures.length === 0) {{
                container.innerHTML = `
                    <div class="empty-state">
                        <div class="empty-icon">🔍</div>
                        <h3>No measures found</h3>
                        <p>Try adjusting your filters or search terms</p>
                    </div>
                `;
                return;
            }}
            
            if (currentView === 'grid') {{
                container.innerHTML = `
                    <div class="results-grid">
                        ${{measures.map(m => createCard(m)).join('')}}
                    </div>
                `;
            }} else {{
                container.innerHTML = `
                    <div class="results-list">
                        ${{measures.map(m => createListItem(m)).join('')}}
                    </div>
                `;
            }}
        }}
        
        // Create card HTML
        function createCard(measure, featured = false) {{
            const title = measure.title || measure.measure_text || 'Untitled Measure';
            const year = measure.year || 'Unknown';
            const passed = measure.passed;
            const passedClass = passed === 1 ? 'passed' : passed === 0 ? 'failed' : 'pending';
            const passedText = passed === 1 ? 'Passed' : passed === 0 ? 'Failed' : 'Pending';
            
            const percentYes = measure.percent_yes;
            const voteBar = percentYes != null ? `
                <div class="vote-bar">
                    <div class="vote-bar-fill" style="width: ${{Math.round(percentYes)}}%"></div>
                </div>
            ` : '';
            
            const topic = measure.topic_primary || measure.topic || '';
            const source = measure.data_source || measure.source || 'Unknown';
            
            return `
                <div class="measure-card ${{featured ? 'featured' : ''}}" onclick="viewMeasure(${{JSON.stringify(measure).replace(/"/g, '&quot;')}})">
                    <div class="card-header">
                        <div class="card-year">${{year}}</div>
                        <div class="card-badges">
                            <span class="badge badge-${{passedClass}}">${{passedText}}</span>
                        </div>
                    </div>
                    <h3 class="card-title">${{title}}</h3>
                    ${{voteBar}}
                    <div class="card-meta">
                        ${{percentYes != null ? `<div class="meta-item">📊 ${{Math.round(percentYes)}}% Yes</div>` : ''}}
                        ${{topic ? `<div class="meta-item">🏷️ ${{topic}}</div>` : ''}}
                        <div class="meta-item">📁 ${{source}}</div>
                    </div>
                </div>
            `;
        }}
        
        // Create list item HTML
        function createListItem(measure) {{
            const title = measure.title || measure.measure_text || 'Untitled Measure';
            const year = measure.year || 'Unknown';
            const passed = measure.passed;
            const passedClass = passed === 1 ? 'passed' : passed === 0 ? 'failed' : 'pending';
            const passedText = passed === 1 ? '✓' : passed === 0 ? '✗' : '?';
            
            return `
                <div class="measure-list-item" onclick="viewMeasure(${{JSON.stringify(measure).replace(/"/g, '&quot;')}})">
                    <div class="badge badge-${{passedClass}}">${{passedText}}</div>
                    <div>
                        <div style="font-weight: 500;">${{title}}</div>
                        <div style="font-size: 0.875rem; color: var(--text-secondary);">
                            ${{year}} • ${{measure.topic_primary || measure.topic || 'General'}}
                        </div>
                    </div>
                    <div style="text-align: right;">
                        ${{measure.percent_yes != null ? `<div style="font-weight: 500;">${{Math.round(measure.percent_yes)}}% Yes</div>` : ''}}
                        <div style="font-size: 0.75rem; color: var(--text-tertiary);">
                            ${{measure.data_source || measure.source || ''}}
                        </div>
                    </div>
                </div>
            `;
        }}
        
        // View measure details
        function viewMeasure(measure) {{
            // In a real app, this would open a modal or navigate to a detail page
            console.log('View measure:', measure);
            if (measure.pdf_url && measure.pdf_url !== '#') {{
                window.open(measure.pdf_url, '_blank');
            }}
        }}
        
        // Set view mode
        function setView(view) {{
            currentView = view;
            document.querySelectorAll('.view-btn').forEach(btn => btn.classList.remove('active'));
            document.getElementById(view + 'View').classList.add('active');
            displayResults(currentFilters.search || currentFilters.status.length > 0 || 
                          currentFilters.features.length > 0 || currentFilters.topics.length > 0 ? 
                          filteredMeasures : filteredMeasures.slice(5));
        }}
        
        // Clear all filters
        function clearAllFilters() {{
            currentFilters = {{
                yearMin: {stats['year_min']},
                yearMax: {stats['year_max']},
                status: [],
                features: [],
                topics: [],
                search: ''
            }};
            
            // Reset UI
            document.getElementById('searchInput').value = '';
            document.getElementById('yearMin').value = {stats['year_min']};
            document.getElementById('yearMax').value = {stats['year_max']};
            updateFilterUI();
            updateTopicUI();
            
            applyFilters();
        }}
    </script>
</body>
</html>"""
    
    return html

def main():
    """Generate static website from available data"""
    print("🌐 Generating Modern Faceted Navigation Website")
    print("=" * 50)
    
    # Try to load from database first
    data = load_data_from_database()
    
    # Fall back to JSON if no database
    if not data:
        data = load_data_from_json()
    
    if not data:
        print("❌ No data available! Run scraper or database setup first.")
        return
    
    # Generate HTML
    html = generate_static_html(data)
    
    # Save HTML
    output_file = Path('index.html')
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"✅ Static website generated: {output_file}")
    print(f"📊 Total measures: {len(data.get('measures', []))}")
    
    # Also save to parent directory for deployment
    parent_output = Path('../index.html')
    with open(parent_output, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"✅ Also saved to: {parent_output}")
    
    print("\n🎯 Key Features:")
    print("   • Modern faceted navigation sidebar")
    print("   • Live search with instant filtering")
    print("   • Grid and list view options")
    print("   • Featured/recent measures section")
    print("   • Smart progressive disclosure")
    print("   • Topic-based filtering")
    print("   • Year range slider")
    print("   • Clean, scannable card design")
    print("   • Responsive layout")
    print("   • Stats dashboard")

if __name__ == "__main__":
    main()