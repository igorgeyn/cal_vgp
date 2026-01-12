"""
Website generator for ballot measures
Generates modern, responsive HTML with faceted navigation
"""
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from collections import Counter

from ..database.operations import Database
from ..database.models import BallotMeasure
from ..config import WEBSITE_CONFIG, BASE_DIR
from ..utils import TitleGenerator

logger = logging.getLogger(__name__)


class WebsiteGenerator:
    """Generates static website from ballot measures data"""
    
    def __init__(self, database: Database = None, output_path: Path = None, style: str = 'modern'):
        self.db = database or Database()
        self.output_path = output_path or BASE_DIR.parent / WEBSITE_CONFIG.get('output_filename', 'index.html')
        self.template = style
        self.features = WEBSITE_CONFIG.get('features', {})
        self.title_generator = TitleGenerator(database=self.db)
        
    def generate(self, measures: List[BallotMeasure] = None, stats: Dict = None) -> str:
        """Generate the complete website"""
        logger.info("Generating website...")
        
        # Get data from database if not provided
        if measures is None:
            measures = self.db.get_all_active_measures()
        if stats is None:
            stats = self.db.get_statistics()
        
        # Process data for website
        measures_data = self._prepare_measures_data(measures)
        topics = self._extract_topics(measures)
        
        # Generate HTML
        html = self._generate_html(measures_data, stats, topics)
        
        # Save to file
        self.output_path.write_text(html, encoding='utf-8')
        logger.info(f"Website generated: {self.output_path}")
        
        # Also save to index.html in parent directory for GitHub Pages
        index_path = BASE_DIR.parent / 'index.html'
        index_path.write_text(html, encoding='utf-8')
        logger.info(f"Also saved to: {index_path}")
        
        return html
    
    def _prepare_measures_data(self, measures: List[BallotMeasure]) -> List[Dict]:
        """Convert measures to format needed for website"""
        measures_data = []

        for measure in measures:
            # Convert to dict
            data = measure.to_dict()

            # Add display fields
            data['measure_text'] = data.get('title') or data.get('ballot_question', 'Unknown Measure')
            data['source'] = data.get('data_source', 'Historical')

            # Ensure year is string for consistency in JSON
            if data.get('year'):
                data['year'] = str(data['year'])

            # Generate concise title if needed
            data = self.title_generator.process_measure(data)

            measures_data.append(data)

        return measures_data
    
    def _extract_topics(self, measures: List[BallotMeasure]) -> List[Dict]:
        """Extract topic information for filters"""
        topic_counts = Counter()
        
        for measure in measures:
            topic = measure.topic_primary or measure.category_topic
            if topic:
                topic_counts[topic] += 1
        
        # Return top 20 topics
        topics = [
            {'topic': topic, 'count': count}
            for topic, count in topic_counts.most_common(20)
        ]
        
        return topics
    
    def _sanitize_stats(self, stats: Dict) -> Dict:
        """Ensure all statistics are the correct type"""
        sanitized = {}
        
        # Integer fields
        int_fields = [
            'total_measures', 'with_summaries', 'with_votes',
            'passed', 'failed', 'year_min', 'year_max',
            'counties', 'topics'
        ]
        
        for field in int_fields:
            value = stats.get(field)
            if value is not None:
                try:
                    sanitized[field] = int(value)
                except (ValueError, TypeError):
                    # Provide sensible defaults
                    if field in ['year_min']:
                        sanitized[field] = 1902
                    elif field in ['year_max']:
                        sanitized[field] = 2026
                    else:
                        sanitized[field] = 0
            else:
                # Provide defaults for missing fields
                if field == 'year_min':
                    sanitized[field] = 1902
                elif field == 'year_max':
                    sanitized[field] = 2026
                else:
                    sanitized[field] = 0
        
        # Copy over other fields
        sanitized['by_source'] = stats.get('by_source', {})
        sanitized['sources'] = stats.get('sources', [])
        
        return sanitized
    
    def _generate_html(self, measures: List[Dict], stats: Dict, 
                      topics: List[Dict]) -> str:
        """Generate the complete HTML with type safety"""
        
        # Ensure all stats are proper types
        stats = self._sanitize_stats(stats)
        
        # Convert data to JSON for embedding
        measures_json = json.dumps(measures, default=str)
        topics_json = json.dumps(topics, default=str)
        
        # Calculate additional stats with type safety (unused variables removed)
        
        # Generate HTML using modern template
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>California Ballot Measures Database</title>
    <style>
        {self._get_css()}
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
                            <span class="filter-option-count">{stats['with_votes']}</span>
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
            <!-- Tool Description -->
            <div class="tool-description">
                <h2 class="tool-title">Explore California's Ballot Measures</h2>
                <p class="tool-intro">
                    Search and analyze over <strong>{stats['total_measures']:,} ballot measures</strong> from across California,
                    spanning more than a century of direct democracy. Discover how voters have decided on everything from
                    local school funding to statewide policy changes.
                </p>
                <div class="tool-features">
                    <div class="feature-item">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <circle cx="12" cy="12" r="10"></circle>
                            <polyline points="12 6 12 12 16 14"></polyline>
                        </svg>
                        <span><strong>Historical data</strong> from {stats['year_min']} to present</span>
                    </div>
                    <div class="feature-item">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path>
                            <circle cx="12" cy="10" r="3"></circle>
                        </svg>
                        <span><strong>58 counties</strong> plus statewide propositions</span>
                    </div>
                    <div class="feature-item">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>
                        </svg>
                        <span><strong>Vote results</strong> for {stats['with_votes']:,} measures</span>
                    </div>
                    <div class="feature-item">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                            <polyline points="14 2 14 8 20 8"></polyline>
                        </svg>
                        <span><strong>AI summaries</strong> for easier understanding</span>
                    </div>
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

            <!-- Hero Section for 2026 Upcoming Measures -->
            <div class="hero-section" id="heroSection">
                <div class="hero-header">
                    <h2 class="hero-title">🗳️ Upcoming 2026 Ballot Measures</h2>
                    <p class="hero-description">Get informed about California's upcoming ballot measures before you vote</p>
                </div>
                <div class="hero-grid" id="heroGrid">
                    <!-- Will be populated by JavaScript -->
                </div>
            </div>

            <!-- Featured Section -->
            <div class="featured-section" id="featuredSection">
                <h2 class="section-title">Featured Measures</h2>
                <div class="featured-grid" id="featuredGrid">
                    <!-- Will be populated by JavaScript -->
                </div>
            </div>

            <!-- Regional Navigation -->
            <div class="regional-navigation" id="regionalNavigation">
                <div class="regional-header">
                    <h2 class="section-title">Filter by Region</h2>
                    <p class="regional-subtitle">Click to select one or more regions (click again to deselect)</p>
                </div>

                <div class="region-cards" id="regionCards">
                    <!-- Will be populated by JavaScript -->
                </div>

                <div class="county-navigation">
                    <label for="countySelect" class="county-label">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path>
                            <circle cx="12" cy="10" r="3"></circle>
                        </svg>
                        Or select a specific county:
                    </label>
                    <select id="countySelect" class="county-select" onchange="filterByCounty(this.value)">
                        <option value="">All Counties</option>
                        <!-- Will be populated by JavaScript -->
                    </select>
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

    <!-- Footer -->
    <footer class="footer">
        <p>California Ballot Measures Database • Updated {datetime.now().strftime('%B %d, %Y')}</p>
        <p>Data sources: CA Secretary of State, NCSL, ICPSR, CEDA</p>
    </footer>

    <!-- AI Chat Interface -->
    <div id="chatWidget" class="chat-widget">
        <button id="chatToggle" class="chat-toggle" onclick="toggleChat()">
            <svg class="chat-icon" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
            </svg>
            <svg class="close-icon" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display: none;">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
        </button>

        <div id="chatPanel" class="chat-panel" style="display: none;">
            <div class="chat-header">
                <div class="chat-header-title">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
                    </svg>
                    <span>Ask about ballot measures</span>
                </div>
                <button class="chat-settings-btn" onclick="openChatSettings()" title="Configure AI">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="12" cy="12" r="3"></circle>
                        <path d="M12 1v6m0 6v6m9-9h-6m-6 0H3"></path>
                    </svg>
                </button>
            </div>

            <div id="chatMessages" class="chat-messages">
                <div class="chat-message bot">
                    <div class="chat-message-content">
                        <p>Hi! I can help you explore California ballot measures.</p>
                        <p>To get started, configure your AI provider in settings (click the ⚙️ icon above).</p>
                        <div class="example-prompts">
                            <p><strong>Example questions:</strong></p>
                            <button class="example-prompt" onclick="askExample(this)">What were the 10 closest ballot measures in the last 5 years?</button>
                            <button class="example-prompt" onclick="askExample(this)">Show me all housing-related measures in San Francisco</button>
                            <button class="example-prompt" onclick="askExample(this)">What topics have the lowest pass rates?</button>
                            <button class="example-prompt" onclick="askExample(this)">Tell me about education measures from 2020-2024</button>
                        </div>
                    </div>
                </div>
            </div>

            <div class="chat-input-container">
                <textarea id="chatInput" class="chat-input" placeholder="Ask a question about ballot measures..." rows="1"></textarea>
                <button id="chatSend" class="chat-send-btn" onclick="sendMessage()" disabled>
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <line x1="22" y1="2" x2="11" y2="13"></line>
                        <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
                    </svg>
                </button>
            </div>
        </div>
    </div>

    <!-- AI Settings Modal -->
    <div id="chatSettingsModal" class="modal" style="display: none;">
        <div class="modal-content chat-settings-modal">
            <div class="modal-header">
                <h2>AI Configuration</h2>
                <button class="modal-close" onclick="closeChatSettings()">×</button>
            </div>

            <div class="modal-body">
                <div class="settings-section">
                    <label class="settings-label">AI Provider</label>
                    <select id="aiProvider" class="settings-select" onchange="updateProviderFields()">
                        <option value="">Select provider...</option>
                        <option value="openai">OpenAI (GPT-4)</option>
                        <option value="anthropic">Anthropic (Claude)</option>
                        <option value="ollama">Local Ollama</option>
                    </select>
                </div>

                <div id="apiKeySection" class="settings-section" style="display: none;">
                    <label class="settings-label" id="apiKeyLabel">API Key</label>
                    <input type="password" id="apiKey" class="settings-input" placeholder="sk-...">
                    <p class="settings-hint">Your API key is stored locally in your browser and never sent to our servers.</p>
                </div>

                <div id="ollamaSection" class="settings-section" style="display: none;">
                    <label class="settings-label">Ollama URL</label>
                    <input type="text" id="ollamaUrl" class="settings-input" value="http://localhost:11434" placeholder="http://localhost:11434">
                    <label class="settings-label">Model</label>
                    <input type="text" id="ollamaModel" class="settings-input" value="llama3.2:3b" placeholder="llama3.2:3b">
                    <p class="settings-hint">Make sure Ollama is running locally. <a href="https://ollama.ai" target="_blank">Download Ollama</a></p>
                </div>

                <div class="settings-section">
                    <button id="testConnection" class="btn-primary" onclick="testAIConnection()" disabled>Test Connection</button>
                    <span id="connectionStatus" class="connection-status"></span>
                </div>
            </div>

            <div class="modal-footer">
                <button class="btn-secondary" onclick="closeChatSettings()">Cancel</button>
                <button class="btn-primary" onclick="saveChatSettings()">Save Settings</button>
            </div>
        </div>
    </div>

    <script>
        {self._get_javascript(measures_json, topics_json, stats)}
        {self._get_chat_javascript()}
    </script>
</body>
</html>"""
        
        return html
    
    def _get_css(self) -> str:
        """Get CSS styles for the website"""
        return """
        /* Modern CSS Reset and Variables */
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        :root {
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
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
            line-height: 1.6;
            color: var(--text-primary);
            background: var(--bg-secondary);
        }
        
        /* Header */
        .header {
            background: var(--bg-primary);
            border-bottom: 1px solid var(--border);
            position: sticky;
            top: 0;
            z-index: 100;
            box-shadow: var(--shadow-sm);
        }
        
        .header-content {
            max-width: 1400px;
            margin: 0 auto;
            padding: 1rem 2rem;
            display: flex;
            align-items: center;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 1rem;
        }
        
        .logo {
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }
        
        .logo-icon {
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
        }
        
        .logo h1 {
            font-size: 1.25rem;
            font-weight: 600;
            color: var(--text-primary);
        }
        
        /* Search Bar */
        .search-container {
            flex: 1;
            max-width: 600px;
        }
        
        .search-box {
            position: relative;
        }
        
        .search-input {
            width: 100%;
            padding: 0.75rem 1rem 0.75rem 2.75rem;
            border: 1px solid var(--border);
            border-radius: 24px;
            font-size: 1rem;
            transition: var(--transition);
            background: var(--bg-secondary);
        }
        
        .search-input:focus {
            outline: none;
            border-color: var(--primary);
            background: var(--bg-primary);
            box-shadow: var(--shadow-sm);
        }
        
        .search-icon {
            position: absolute;
            left: 1rem;
            top: 50%;
            transform: translateY(-50%);
            color: var(--text-tertiary);
        }
        
        /* View Controls */
        .view-controls {
            display: flex;
            gap: 0.5rem;
        }
        
        .view-btn {
            padding: 0.5rem 0.75rem;
            border: 1px solid var(--border);
            background: var(--bg-primary);
            border-radius: var(--radius-sm);
            cursor: pointer;
            color: var(--text-secondary);
            transition: var(--transition);
        }
        
        .view-btn:hover {
            background: var(--bg-secondary);
        }
        
        .view-btn.active {
            background: var(--primary);
            color: white;
            border-color: var(--primary);
        }
        
        /* Main Layout */
        .main-container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 2rem;
            display: grid;
            grid-template-columns: 280px 1fr;
            gap: 2rem;
        }
        
        /* Sidebar Filters */
        .sidebar {
            position: sticky;
            top: 80px;
            height: fit-content;
            max-height: calc(100vh - 100px);
            overflow-y: auto;
        }
        
        .filter-section {
            background: var(--bg-primary);
            border-radius: var(--radius);
            padding: 1.5rem;
            margin-bottom: 1rem;
            box-shadow: var(--shadow-sm);
        }
        
        .filter-header {
            font-size: 0.875rem;
            font-weight: 600;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 1rem;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        
        .filter-clear {
            font-size: 0.75rem;
            color: var(--primary);
            cursor: pointer;
            font-weight: normal;
            text-transform: none;
            letter-spacing: normal;
        }
        
        .filter-clear:hover {
            text-decoration: underline;
        }
        
        /* Filter Groups */
        .filter-group {
            margin-bottom: 1.5rem;
        }
        
        .filter-group:last-child {
            margin-bottom: 0;
        }
        
        .filter-label {
            font-size: 0.875rem;
            font-weight: 500;
            color: var(--text-primary);
            margin-bottom: 0.75rem;
        }
        
        /* Year Range Slider */
        .year-range {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            margin-bottom: 0.5rem;
        }
        
        .year-input {
            width: 70px;
            padding: 0.375rem 0.5rem;
            border: 1px solid var(--border);
            border-radius: var(--radius-sm);
            font-size: 0.875rem;
            text-align: center;
        }
        
        .year-separator {
            color: var(--text-tertiary);
        }
        
        /* Filter Options */
        .filter-options {
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
        }
        
        .filter-option {
            display: flex;
            align-items: center;
            padding: 0.375rem 0.5rem;
            border-radius: var(--radius-sm);
            cursor: pointer;
            transition: var(--transition);
            font-size: 0.875rem;
        }
        
        .filter-option:hover {
            background: var(--bg-secondary);
        }
        
        .filter-option.active {
            background: var(--primary);
            color: white;
        }
        
        .filter-option-label {
            flex: 1;
        }
        
        .filter-option-count {
            font-size: 0.75rem;
            opacity: 0.7;
        }
        
        /* Topic Tags */
        .topic-tags {
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
        }
        
        .topic-tag {
            padding: 0.375rem 0.75rem;
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 16px;
            font-size: 0.813rem;
            cursor: pointer;
            transition: var(--transition);
        }
        
        .topic-tag:hover {
            background: var(--bg-tertiary);
        }
        
        .topic-tag.active {
            background: var(--primary);
            color: white;
            border-color: var(--primary);
        }
        
        /* Content Area */
        .content {
            min-height: 100vh;
        }
        
        /* Results Header */
        .results-header {
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
        }
        
        .results-info {
            display: flex;
            align-items: baseline;
            gap: 1rem;
        }
        
        .results-count {
            font-size: 1.5rem;
            font-weight: 600;
            color: var(--text-primary);
        }
        
        .results-description {
            color: var(--text-secondary);
            font-size: 0.875rem;
        }
        
        .sort-controls {
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        
        .sort-label {
            font-size: 0.875rem;
            color: var(--text-secondary);
        }
        
        .sort-select {
            padding: 0.5rem 1rem;
            border: 1px solid var(--border);
            border-radius: var(--radius-sm);
            background: var(--bg-primary);
            font-size: 0.875rem;
        }
        
        /* Hero Section for 2026 Measures */
        .hero-section {
            background: linear-gradient(135deg, rgba(26, 115, 232, 0.08) 0%, rgba(26, 115, 232, 0.02) 100%);
            border: 2px solid rgba(26, 115, 232, 0.2);
            border-radius: 12px;
            padding: 2rem;
            margin-bottom: 3rem;
        }

        .hero-header {
            text-align: center;
            margin-bottom: 2rem;
        }

        .hero-title {
            font-size: 1.75rem;
            font-weight: 700;
            color: var(--text-primary);
            margin-bottom: 0.5rem;
        }

        .hero-description {
            font-size: 1rem;
            color: var(--text-secondary);
            max-width: 600px;
            margin: 0 auto;
        }

        .hero-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 1.25rem;
        }

        /* Featured Section */
        .featured-section {
            margin-bottom: 2rem;
        }

        .section-title {
            font-size: 1.25rem;
            font-weight: 600;
            color: var(--text-primary);
            margin-bottom: 1rem;
        }

        .featured-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }

        /* Regional Navigation */
        .regional-navigation {
            margin: 3rem 0;
            padding: 2rem 0;
            border-top: 1px solid var(--border-color);
        }

        .regional-header {
            text-align: center;
            margin-bottom: 2rem;
        }

        .regional-subtitle {
            color: var(--text-secondary);
            font-size: 0.95rem;
            margin-top: 0.5rem;
        }

        .region-cards {
            display: flex;
            flex-wrap: wrap;
            gap: 0.75rem;
            margin-bottom: 1.5rem;
        }

        .region-chip {
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.6rem 1rem;
            background: var(--bg-primary);
            border: 1px solid var(--border-color);
            border-radius: 100px;
            cursor: pointer;
            transition: all 0.2s ease;
            font-size: 0.9rem;
            color: var(--text-primary);
            user-select: none;
        }

        .region-chip:hover {
            border-color: var(--primary);
            background: rgba(66, 133, 244, 0.05);
        }

        .region-chip.selected {
            background: var(--primary);
            border-color: var(--primary);
            color: white;
        }

        .region-chip.selected:hover {
            background: var(--primary-dark);
            border-color: var(--primary-dark);
        }

        .region-chip-emoji {
            font-size: 1.1rem;
        }

        .region-chip-name {
            font-weight: 500;
        }

        .region-chip-count {
            font-size: 0.8rem;
            opacity: 0.8;
            margin-left: 0.25rem;
        }

        .region-chip.selected .region-chip-count {
            opacity: 0.9;
        }

        .county-navigation {
            display: flex;
            align-items: center;
            gap: 1rem;
            padding: 1.5rem;
            background: rgba(66, 133, 244, 0.05);
            border-radius: var(--radius);
            border: 1px solid rgba(66, 133, 244, 0.1);
        }

        .county-label {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            font-weight: 500;
            color: var(--text-primary);
            white-space: nowrap;
            cursor: pointer;
        }

        .county-label svg {
            color: var(--accent);
        }

        .county-select {
            flex: 1;
            max-width: 300px;
            padding: 0.75rem 1rem;
            border: 1px solid var(--border-color);
            border-radius: var(--radius);
            background: var(--bg-primary);
            font-size: 0.95rem;
            color: var(--text-primary);
            cursor: pointer;
            transition: all 0.2s ease;
        }

        .county-select:hover {
            border-color: var(--accent);
        }

        .county-select:focus {
            outline: none;
            border-color: var(--accent);
            box-shadow: 0 0 0 3px rgba(66, 133, 244, 0.1);
        }

        /* Card Styles */
        .measure-card {
            background: var(--bg-primary);
            border-radius: var(--radius);
            padding: 1.5rem;
            box-shadow: var(--shadow-sm);
            transition: all 0.2s ease;
            cursor: pointer;
            display: flex;
            flex-direction: column;
            gap: 0.875rem;
            border: 1px solid rgba(0, 0, 0, 0.05);
            min-height: 200px;
            max-height: 400px;
        }

        .measure-card:hover {
            box-shadow: 0 8px 16px rgba(0, 0, 0, 0.12);
            transform: translateY(-2px);
            border-color: rgba(66, 133, 244, 0.2);
        }

        .measure-card:has(.card-summary.expanded) {
            max-height: none;
        }
        
        .measure-card.hero {
            border: 2px solid var(--primary);
            box-shadow: 0 4px 12px rgba(26, 115, 232, 0.15);
            background: linear-gradient(135deg, var(--bg-primary) 0%, rgba(26, 115, 232, 0.02) 100%);
        }

        .measure-card.hero:hover {
            box-shadow: 0 8px 24px rgba(26, 115, 232, 0.25);
            transform: translateY(-4px);
        }

        .measure-card.featured {
            border-left: 4px solid var(--primary);
        }
        
        .card-header {
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: 1rem;
        }
        
        .card-year {
            font-size: 0.875rem;
            font-weight: 600;
            color: var(--text-secondary);
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        .featured-label {
            background: var(--primary);
            color: white;
            padding: 0.125rem 0.5rem;
            border-radius: var(--radius-sm);
            font-size: 0.688rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .card-badges {
            display: flex;
            gap: 0.5rem;
        }
        
        .badge {
            padding: 0.375rem 0.75rem;
            border-radius: var(--radius-sm);
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.025em;
            display: inline-flex;
            align-items: center;
            gap: 0.375rem;
        }

        .badge::before {
            content: '';
            width: 6px;
            height: 6px;
            border-radius: 50%;
            display: inline-block;
        }

        .badge-passed {
            background: linear-gradient(135deg, rgba(30, 142, 62, 0.15), rgba(30, 142, 62, 0.08));
            color: #1a7a3e;
            border: 1px solid rgba(30, 142, 62, 0.25);
        }

        .badge-passed::before {
            background: #1a7a3e;
        }

        .badge-failed {
            background: linear-gradient(135deg, rgba(217, 48, 37, 0.15), rgba(217, 48, 37, 0.08));
            color: #c4241f;
            border: 1px solid rgba(217, 48, 37, 0.25);
        }

        .badge-failed::before {
            background: #c4241f;
        }

        .badge-pending {
            background: linear-gradient(135deg, rgba(249, 171, 0, 0.15), rgba(249, 171, 0, 0.08));
            color: #b87503;
            border: 1px solid rgba(249, 171, 0, 0.25);
        }

        .badge-pending::before {
            background: #b87503;
        }

        .badge-summary {
            background: linear-gradient(135deg, rgba(26, 115, 232, 0.12), rgba(26, 115, 232, 0.06));
            color: #1a73e8;
            border: 1px solid rgba(26, 115, 232, 0.25);
            font-size: 0.75rem;
            padding: 0.25rem 0.5rem;
            border-radius: 4px;
            font-weight: 500;
            display: inline-flex;
            align-items: center;
            gap: 0.25rem;
        }

        .card-title {
            font-size: 1.0625rem;
            font-weight: 600;
            color: var(--text-primary);
            line-height: 1.5;
            margin-bottom: 0.25rem;
            display: -webkit-box;
            -webkit-line-clamp: 4;
            -webkit-box-orient: vertical;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        .card-description {
            font-size: 0.875rem;
            color: var(--text-secondary);
            line-height: 1.6;
            margin: 0.5rem 0;
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        /* Card summary (new - replaces description when summary available) */
        .card-summary {
            font-size: 0.875rem;
            color: var(--text-secondary);
            line-height: 1.6;
            margin: 0.75rem 0 0.5rem 0;
            display: -webkit-box;
            -webkit-line-clamp: 3;
            -webkit-box-orient: vertical;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        .card-summary.has-summary {
            /* Subtle background to indicate it's a real summary */
            background: rgba(26, 115, 232, 0.02);
            padding: 0.5rem;
            border-radius: 4px;
            border-left: 2px solid rgba(26, 115, 232, 0.15);
        }

        .card-summary[data-full-text]:hover {
            background: rgba(26, 115, 232, 0.04);
            border-left-color: rgba(26, 115, 232, 0.25);
        }

        .card-summary.expanded {
            -webkit-line-clamp: unset !important;
            -webkit-box-orient: vertical !important;
            display: block !important;
            overflow: visible !important;
            max-height: none !important;
        }

        .read-more {
            color: var(--primary);
            font-size: 0.813rem;
            font-weight: 500;
            text-decoration: none;
            display: inline-flex;
            align-items: center;
            gap: 0.25rem;
            margin-top: 0.25rem;
            cursor: pointer;
            transition: all 0.2s ease;
        }

        .read-more:hover {
            text-decoration: underline;
            transform: translateX(2px);
        }
        
        .card-meta {
            display: flex;
            flex-wrap: wrap;
            gap: 1.25rem;
            font-size: 0.813rem;
            color: var(--text-secondary);
            padding-top: 0.5rem;
            border-top: 1px solid rgba(0, 0, 0, 0.06);
        }

        .meta-item {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            font-weight: 500;
        }

        .meta-item::before {
            font-size: 1rem;
            line-height: 1;
        }
        
        .vote-bar {
            height: 6px;
            background: rgba(0, 0, 0, 0.08);
            border-radius: 3px;
            overflow: hidden;
            margin: 0.5rem 0;
            position: relative;
        }

        .vote-bar-fill {
            height: 100%;
            background: linear-gradient(90deg, var(--success), #34a853);
            transition: width 0.3s ease;
            border-radius: 3px;
        }

        .measure-card:hover .vote-bar-fill {
            box-shadow: 0 0 8px rgba(30, 142, 62, 0.4);
        }
        
        /* Grid View */
        .results-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
            gap: 1rem;
        }
        
        /* List View */
        .results-list {
            display: flex;
            flex-direction: column;
            gap: 0.75rem;
        }
        
        .measure-list-item {
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
        }
        
        .measure-list-item:hover {
            box-shadow: var(--shadow-md);
        }
        
        /* Stats Dashboard */
        /* Tool Description */
        .tool-description {
            background: linear-gradient(135deg, rgba(66, 133, 244, 0.05) 0%, rgba(255, 255, 255, 0.95) 100%);
            border-radius: 12px;
            padding: 2rem;
            margin-bottom: 2rem;
            border: 1px solid rgba(66, 133, 244, 0.1);
        }

        .tool-title {
            font-size: 1.75rem;
            font-weight: 700;
            color: var(--text-primary);
            margin-bottom: 0.75rem;
        }

        .tool-intro {
            font-size: 1.05rem;
            line-height: 1.6;
            color: var(--text-secondary);
            margin-bottom: 1.5rem;
        }

        .tool-intro strong {
            color: var(--text-primary);
            font-weight: 600;
        }

        .tool-features {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 1rem;
        }

        .feature-item {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            padding: 0.75rem;
            background: var(--bg-primary);
            border-radius: var(--radius);
            transition: all 0.2s ease;
        }

        .feature-item:hover {
            box-shadow: var(--shadow-sm);
            transform: translateY(-1px);
        }

        .feature-item svg {
            flex-shrink: 0;
            color: var(--primary);
        }

        .feature-item span {
            font-size: 0.9rem;
            color: var(--text-secondary);
        }

        .feature-item strong {
            color: var(--text-primary);
            font-weight: 600;
        }
        
        /* Loading State */
        .loading {
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 4rem;
            color: var(--text-tertiary);
        }
        
        .spinner {
            width: 40px;
            height: 40px;
            border: 3px solid var(--border);
            border-top-color: var(--primary);
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }
        
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        
        /* Empty State */
        .empty-state {
            text-align: center;
            padding: 4rem 2rem;
            color: var(--text-secondary);
        }
        
        .empty-icon {
            font-size: 3rem;
            margin-bottom: 1rem;
            opacity: 0.5;
        }
        
        /* Footer */
        .footer {
            background: var(--bg-primary);
            border-top: 1px solid var(--border);
            padding: 2rem;
            text-align: center;
            margin-top: 4rem;
            color: var(--text-secondary);
            font-size: 0.875rem;
        }
        
        .footer p {
            margin: 0.25rem 0;
        }
        
        /* Pagination */
        .pagination-container {
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            justify-content: center;
            gap: 0.5rem;
            margin-top: 2rem;
            padding: 1.5rem;
            background: var(--bg-primary);
            border-radius: var(--radius);
            box-shadow: var(--shadow-sm);
        }
        
        .pagination-controls {
            display: flex;
            align-items: center;
            gap: 0.25rem;
        }
        
        .pagination-btn {
            min-width: 40px;
            height: 40px;
            padding: 0.5rem;
            border: 1px solid var(--border);
            background: var(--bg-primary);
            border-radius: var(--radius-sm);
            cursor: pointer;
            font-size: 0.875rem;
            color: var(--text-secondary);
            transition: var(--transition);
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        .pagination-btn:hover:not(:disabled) {
            background: var(--bg-secondary);
            border-color: var(--primary);
            color: var(--primary);
        }
        
        .pagination-btn:disabled {
            opacity: 0.4;
            cursor: not-allowed;
        }
        
        .pagination-btn.active {
            background: var(--primary);
            color: white;
            border-color: var(--primary);
        }
        
        .pagination-ellipsis {
            padding: 0 0.5rem;
            color: var(--text-tertiary);
        }
        
        .pagination-info {
            display: flex;
            align-items: center;
            gap: 1rem;
            margin-left: 1rem;
            padding-left: 1rem;
            border-left: 1px solid var(--border);
            font-size: 0.875rem;
            color: var(--text-secondary);
        }
        
        .page-size-select {
            padding: 0.375rem 0.75rem;
            border: 1px solid var(--border);
            border-radius: var(--radius-sm);
            background: var(--bg-primary);
            font-size: 0.875rem;
            cursor: pointer;
        }
        
        /* Featured card enhancements */
        .featured-label {
            display: inline-flex;
            align-items: center;
            gap: 0.25rem;
            padding: 0.25rem 0.5rem;
            background: var(--bg-tertiary);
            border-radius: var(--radius-sm);
            font-size: 0.7rem;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.03em;
        }
        
        .measure-card.featured {
            border-left: 4px solid var(--primary);
            background: linear-gradient(135deg, var(--bg-primary) 0%, rgba(26, 115, 232, 0.03) 100%);
        }
        
        .measure-card.featured .card-title {
            font-size: 1.05rem;
        }
        
        /* Responsive */
        @media (max-width: 1024px) {
            .main-container {
                grid-template-columns: 1fr;
            }
            
            .sidebar {
                position: static;
                max-height: none;
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                gap: 1rem;
            }
        }
        
        @media (max-width: 768px) {
            .header-content {
                padding: 1rem;
            }
            
            .main-container {
                padding: 1rem;
            }
            
            .search-container {
                order: 3;
                flex-basis: 100%;
                max-width: none;
            }
            
            .featured-grid,
            .results-grid {
                grid-template-columns: 1fr;
            }
            
            .pagination-container {
                flex-direction: column;
                gap: 1rem;
            }
            
            .pagination-info {
                margin-left: 0;
                padding-left: 0;
                border-left: none;
                padding-top: 0.75rem;
                border-top: 1px solid var(--border);
                width: 100%;
                justify-content: center;
            }
            
            .pagination-btn {
                min-width: 36px;
                height: 36px;
                font-size: 0.8rem;
            }
        }

        /* AI Chat Interface Styles */
        .chat-widget {
            position: fixed;
            bottom: 24px;
            right: 24px;
            z-index: 1000;
        }

        .chat-toggle {
            width: 60px;
            height: 60px;
            border-radius: 50%;
            background: var(--primary);
            border: none;
            box-shadow: var(--shadow-md);
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            transition: var(--transition);
        }

        .chat-toggle:hover {
            background: var(--primary-dark);
            transform: scale(1.05);
        }

        .chat-panel {
            position: fixed;
            bottom: 100px;
            right: 24px;
            width: 400px;
            height: 600px;
            background: var(--bg-primary);
            border-radius: 12px;
            box-shadow: 0 4px 24px rgba(0, 0, 0, 0.15);
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }

        .chat-header {
            padding: 1rem;
            background: var(--primary);
            color: white;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .chat-header-title {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            font-weight: 600;
        }

        .chat-settings-btn {
            background: rgba(255, 255, 255, 0.2);
            border: none;
            color: white;
            border-radius: 4px;
            padding: 0.5rem;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: var(--transition);
        }

        .chat-settings-btn:hover {
            background: rgba(255, 255, 255, 0.3);
        }

        .chat-messages {
            flex: 1;
            overflow-y: auto;
            padding: 1rem;
            display: flex;
            flex-direction: column;
            gap: 1rem;
        }

        .chat-message {
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
            animation: slideIn 0.3s ease;
        }

        @keyframes slideIn {
            from {
                opacity: 0;
                transform: translateY(10px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        .chat-message.user {
            align-items: flex-end;
        }

        .chat-message.bot {
            align-items: flex-start;
        }

        .chat-message-content {
            max-width: 85%;
            padding: 0.75rem 1rem;
            border-radius: 12px;
            line-height: 1.5;
        }

        .chat-message.user .chat-message-content {
            background: var(--primary);
            color: white;
        }

        .chat-message.bot .chat-message-content {
            background: var(--bg-secondary);
            color: var(--text-primary);
        }

        .chat-message-content p {
            margin: 0.5rem 0;
        }

        .chat-message-content p:first-child {
            margin-top: 0;
        }

        .chat-message-content p:last-child {
            margin-bottom: 0;
        }

        .example-prompts {
            margin-top: 1rem;
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
        }

        .example-prompts p {
            font-size: 0.875rem;
            color: var(--text-secondary);
            margin-bottom: 0.25rem;
        }

        .example-prompt {
            background: white;
            border: 1px solid var(--border);
            padding: 0.5rem 0.75rem;
            border-radius: 8px;
            text-align: left;
            cursor: pointer;
            font-size: 0.875rem;
            transition: var(--transition);
        }

        .example-prompt:hover {
            background: var(--bg-secondary);
            border-color: var(--primary);
        }

        .chat-input-container {
            padding: 1rem;
            border-top: 1px solid var(--border);
            display: flex;
            gap: 0.5rem;
            align-items: flex-end;
        }

        .chat-input {
            flex: 1;
            padding: 0.75rem;
            border: 1px solid var(--border);
            border-radius: 8px;
            font-family: inherit;
            font-size: 1rem;
            resize: none;
            max-height: 120px;
            min-height: 44px;
        }

        .chat-input:focus {
            outline: none;
            border-color: var(--primary);
        }

        .chat-send-btn {
            width: 44px;
            height: 44px;
            background: var(--primary);
            border: none;
            border-radius: 8px;
            color: white;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: var(--transition);
        }

        .chat-send-btn:hover:not(:disabled) {
            background: var(--primary-dark);
        }

        .chat-send-btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }

        .chat-typing-indicator {
            display: flex;
            gap: 0.25rem;
            padding: 0.75rem 1rem;
        }

        .chat-typing-dot {
            width: 8px;
            height: 8px;
            background: var(--text-tertiary);
            border-radius: 50%;
            animation: typing 1.4s infinite;
        }

        .chat-typing-dot:nth-child(2) {
            animation-delay: 0.2s;
        }

        .chat-typing-dot:nth-child(3) {
            animation-delay: 0.4s;
        }

        @keyframes typing {
            0%, 60%, 100% {
                opacity: 0.3;
                transform: translateY(0);
            }
            30% {
                opacity: 1;
                transform: translateY(-8px);
            }
        }

        /* Modal Styles */
        .modal {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.5);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 2000;
            padding: 1rem;
        }

        .modal-content {
            background: var(--bg-primary);
            border-radius: 12px;
            max-width: 500px;
            width: 100%;
            max-height: 90vh;
            overflow-y: auto;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
        }

        .modal-header {
            padding: 1.5rem;
            border-bottom: 1px solid var(--border);
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .modal-header h2 {
            font-size: 1.25rem;
            font-weight: 600;
            margin: 0;
        }

        .modal-close {
            background: none;
            border: none;
            font-size: 1.5rem;
            cursor: pointer;
            color: var(--text-secondary);
            width: 32px;
            height: 32px;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 4px;
            transition: var(--transition);
        }

        .modal-close:hover {
            background: var(--bg-secondary);
        }

        .modal-body {
            padding: 1.5rem;
        }

        .modal-footer {
            padding: 1rem 1.5rem;
            border-top: 1px solid var(--border);
            display: flex;
            gap: 0.75rem;
            justify-content: flex-end;
        }

        .settings-section {
            margin-bottom: 1.5rem;
        }

        .settings-section:last-child {
            margin-bottom: 0;
        }

        .settings-label {
            display: block;
            font-weight: 500;
            margin-bottom: 0.5rem;
            color: var(--text-primary);
        }

        .settings-select,
        .settings-input {
            width: 100%;
            padding: 0.75rem;
            border: 1px solid var(--border);
            border-radius: 8px;
            font-family: inherit;
            font-size: 1rem;
            margin-bottom: 0.5rem;
        }

        .settings-select:focus,
        .settings-input:focus {
            outline: none;
            border-color: var(--primary);
        }

        .settings-hint {
            font-size: 0.875rem;
            color: var(--text-secondary);
            margin: 0.5rem 0 0 0;
        }

        .settings-hint a {
            color: var(--primary);
        }

        .connection-status {
            margin-left: 1rem;
            font-size: 0.875rem;
        }

        .connection-status.success {
            color: var(--success);
        }

        .connection-status.error {
            color: var(--danger);
        }

        .btn-primary,
        .btn-secondary {
            padding: 0.75rem 1.5rem;
            border: none;
            border-radius: 8px;
            font-weight: 500;
            cursor: pointer;
            transition: var(--transition);
        }

        .btn-primary {
            background: var(--primary);
            color: white;
        }

        .btn-primary:hover:not(:disabled) {
            background: var(--primary-dark);
        }

        .btn-primary:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }

        .btn-secondary {
            background: var(--bg-secondary);
            color: var(--text-primary);
        }

        .btn-secondary:hover {
            background: var(--bg-tertiary);
        }

        /* Mobile Responsiveness for Chat */
        @media (max-width: 768px) {
            .chat-panel {
                bottom: 90px;
                right: 12px;
                left: 12px;
                width: auto;
                height: 500px;
            }

            .chat-widget {
                bottom: 12px;
                right: 12px;
            }
        }
        """
    
    def _get_javascript(self, measures_json: str, topics_json: str, 
                       stats: Dict) -> str:
        """Get JavaScript code for the website"""
        return f"""
        // Data
        const allMeasures = {measures_json};
        const topics = {topics_json};

        // California Regions
        const CA_REGIONS = {{
            "Greater Bay Area": {{
                counties: ["ALAMEDA", "CONTRA COSTA", "MARIN", "NAPA", "SAN FRANCISCO", "SAN MATEO", "SANTA CLARA", "SOLANO", "SONOMA"],
                emoji: "🌉",
                description: "San Francisco Bay Area & Silicon Valley"
            }},
            "Greater Los Angeles": {{
                counties: ["LOS ANGELES", "ORANGE", "VENTURA", "RIVERSIDE", "SAN BERNARDINO"],
                emoji: "🌴",
                description: "Los Angeles, Orange County & Inland Empire"
            }},
            "San Diego Region": {{
                counties: ["SAN DIEGO", "IMPERIAL"],
                emoji: "🏖️",
                description: "San Diego & Imperial Valley"
            }},
            "Central Valley": {{
                counties: ["FRESNO", "KERN", "KINGS", "MADERA", "MERCED", "SAN JOAQUIN", "STANISLAUS", "TULARE"],
                emoji: "🌾",
                description: "Agricultural heartland from Stockton to Bakersfield"
            }},
            "Sacramento Region": {{
                counties: ["SACRAMENTO", "PLACER", "EL DORADO", "YOLO", "SUTTER", "YUBA"],
                emoji: "🏛️",
                description: "State capital region & Sierra foothills"
            }},
            "Central Coast": {{
                counties: ["MONTEREY", "SAN LUIS OBISPO", "SANTA BARBARA", "SANTA CRUZ", "SAN BENITO"],
                emoji: "🌊",
                description: "Coastal region from Santa Cruz to Santa Barbara"
            }},
            "North Coast": {{
                counties: ["MENDOCINO", "HUMBOLDT", "DEL NORTE", "LAKE"],
                emoji: "🌲",
                description: "Redwood country & wine regions"
            }},
            "Northern California": {{
                counties: ["SHASTA", "TEHAMA", "BUTTE", "GLENN", "COLUSA", "TRINITY", "SISKIYOU", "MODOC", "LASSEN", "PLUMAS"],
                emoji: "⛰️",
                description: "Rural northern counties & Cascade Range"
            }},
            "Eastern Sierra": {{
                counties: ["MONO", "INYO", "ALPINE", "AMADOR", "CALAVERAS", "TUOLUMNE", "MARIPOSA", "NEVADA", "SIERRA"],
                emoji: "🏔️",
                description: "Sierra Nevada mountains & eastern desert"
            }}
        }};

        // State
        let currentView = 'grid';
        let currentFilters = {{
            yearMin: {stats.get('year_min', 1902)},
            yearMax: {stats.get('year_max', 2026)},
            status: [],
            features: [],
            topics: [],
            search: '',
            regions: [],
            county: null
        }};
        let currentSort = 'year-desc';
        let filteredMeasures = [];

        // Pagination state
        let pagination = {{
            currentPage: 1,
            itemsPerPage: 25,
            totalPages: 0
        }};

        // Featured measures (selected once on load)
        let featuredMeasures = [];
        let heroMeasures = [];

        // Initialize
        document.addEventListener('DOMContentLoaded', () => {{
            selectHeroMeasures();
            selectFeaturedMeasures();
            populateRegionalNavigation();
            initializeTopicTags();
            setupEventListeners();
            loadPageFromURL();
            applyFilters();
        }});

        // Select 2026 upcoming measures for hero section
        function selectHeroMeasures() {{
            heroMeasures = allMeasures
                .filter(m => {{
                    const year = parseInt(m.year);
                    // Include 2026 measures (pending/upcoming)
                    return year === 2026;
                }})
                .sort((a, b) => {{
                    // Sort statewide first, then by measure ID
                    if (a.county && !b.county) return 1;
                    if (!a.county && b.county) return -1;
                    return (a.measure_id || '').localeCompare(b.measure_id || '');
                }});
        }}

        // Select interesting featured measures (excluding 2026 which are in hero)
        function selectFeaturedMeasures() {{
            const candidates = allMeasures.filter(m => parseInt(m.year) !== 2026);
            const selected = [];

            // 1. Get 2 most recent measures (2025 or latest year excluding 2026)
            const recent = candidates
                .filter(m => m.year)
                .sort((a, b) => (parseInt(b.year) || 0) - (parseInt(a.year) || 0))
                .slice(0, 2);
            recent.forEach(m => {{
                m._featuredReason = '🗓️ Recent';
                selected.push(m);
            }});

            // 2. Get 1-2 historical measures (oldest with vote data)
            const historical = candidates
                .filter(m => m.year && parseInt(m.year) < 1930 && m.yes_votes != null && !selected.includes(m))
                .sort((a, b) => (parseInt(a.year) || 9999) - (parseInt(b.year) || 9999))
                .slice(0, 2);
            historical.forEach(m => {{
                m._featuredReason = '📜 Historical';
                selected.push(m);
            }});

            // 3. Get 1 close vote (closest to 50%)
            const closeVote = candidates
                .filter(m => m.percent_yes != null && !selected.includes(m))
                .sort((a, b) => Math.abs(a.percent_yes - 50) - Math.abs(b.percent_yes - 50))
                .slice(0, 1);
            closeVote.forEach(m => {{
                m._featuredReason = '⚖️ Close Vote';
                selected.push(m);
            }});

            // 4. Fill remaining with random picks (for discovery)
            const remaining = candidates.filter(m => !selected.includes(m) && m.title);
            while (selected.length < 5 && remaining.length > 0) {{
                const randomIndex = Math.floor(Math.random() * remaining.length);
                const pick = remaining.splice(randomIndex, 1)[0];
                pick._featuredReason = '🎲 Discover';
                selected.push(pick);
            }}

            featuredMeasures = selected.slice(0, 5);
        }}

        // Regional Navigation Functions
        function populateRegionalNavigation() {{
            // Calculate stats for each region
            const regionStats = {{}};
            Object.keys(CA_REGIONS).forEach(regionName => {{
                const regionData = CA_REGIONS[regionName];
                const regionMeasures = allMeasures.filter(m =>
                    m.county && regionData.counties.includes(m.county.toUpperCase())
                );

                regionStats[regionName] = {{
                    count: regionMeasures.length
                }};
            }});

            // Populate region chips
            const regionCardsContainer = document.getElementById('regionCards');
            regionCardsContainer.innerHTML = Object.keys(CA_REGIONS).map(regionName => {{
                const regionData = CA_REGIONS[regionName];
                const stats = regionStats[regionName];

                return `
                    <div class="region-chip" data-region="${{regionName}}" onclick="toggleRegion('${{regionName}}')">
                        <span class="region-chip-emoji">${{regionData.emoji}}</span>
                        <span class="region-chip-name">${{regionName}}</span>
                        <span class="region-chip-count">(${{stats.count.toLocaleString()}})</span>
                    </div>
                `;
            }}).join('');

            // Populate county dropdown
            const countySelect = document.getElementById('countySelect');
            const allCounties = new Set();
            allMeasures.forEach(m => {{
                if (m.county) allCounties.add(m.county);
            }});

            const sortedCounties = Array.from(allCounties).sort();
            countySelect.innerHTML = '<option value="">All Counties</option>' +
                sortedCounties.map(county => `
                    <option value="${{county}}">${{county}}</option>
                `).join('');
        }}

        function toggleRegion(regionName) {{
            // Toggle region in the selected regions array
            if (!currentFilters.regions) {{
                currentFilters.regions = [];
            }}

            const index = currentFilters.regions.indexOf(regionName);
            if (index > -1) {{
                // Remove region
                currentFilters.regions.splice(index, 1);
            }} else {{
                // Add region
                currentFilters.regions.push(regionName);
            }}

            // Update chip visual state
            const chip = document.querySelector(`.region-chip[data-region="${{regionName}}"]`);
            if (chip) {{
                chip.classList.toggle('selected');
            }}

            // Clear county selection when using regions
            currentFilters.county = null;
            document.getElementById('countySelect').value = '';

            // Apply filters
            applyFilters();
        }}

        function filterByCounty(county) {{
            // Clear region selections when selecting county
            currentFilters.regions = [];
            document.querySelectorAll('.region-chip.selected').forEach(chip => {{
                chip.classList.remove('selected');
            }});

            currentFilters.county = county || null;

            // Apply filters
            applyFilters();
        }}

        function clearRegionFilter() {{
            currentFilters.regions = [];
            currentFilters.county = null;

            // Update UI
            document.getElementById('countySelect').value = '';
            document.querySelectorAll('.region-chip.selected').forEach(chip => {{
                chip.classList.remove('selected');
            }});

            // Apply filters
            applyFilters();

            // Scroll to top
            window.scrollTo({{ top: 0, behavior: 'smooth' }});
        }}

        // Initialize topic tags
        function initializeTopicTags() {{
            const container = document.getElementById('topicTags');
            container.innerHTML = topics.slice(0, 12).map(topic => `
                <div class="topic-tag" onclick="toggleTopic('${{topic.topic.replace(/'/g, "\\\\'")}}')">
                    ${{topic.topic}} (${{topic.count}})
                </div>
            `).join('');
        }}
        
        // Load page number from URL hash
        function loadPageFromURL() {{
            const hash = window.location.hash;
            const match = hash.match(/page=(\d+)/);
            if (match) {{
                pagination.currentPage = Math.max(1, parseInt(match[1]));
            }}
        }}

        // Toggle summary expansion
        function toggleSummary(element) {{
            event.stopPropagation(); // Prevent card click from interfering
            const fullText = element.getAttribute('data-full-text');
            const shortText = element.getAttribute('data-short-text');
            const isExpanded = element.classList.contains('expanded');
            const card = element.closest('.measure-card');

            if (isExpanded) {{
                element.textContent = shortText;
                element.classList.remove('expanded');
                element.style.display = '-webkit-box';
                element.title = 'Click to expand';
                if (card) card.classList.remove('expanded');
            }} else {{
                element.textContent = fullText;
                element.classList.add('expanded');
                element.style.display = 'block';
                element.title = 'Click to collapse';
                if (card) card.classList.add('expanded');
            }}
        }}

        // Update URL hash with current page
        function updateURL() {{
            const newHash = pagination.currentPage > 1 ? `#page=${{pagination.currentPage}}` : '';
            if (window.location.hash !== newHash) {{
                history.replaceState(null, '', newHash || window.location.pathname);
            }}
        }}
        
        // Setup event listeners
        function setupEventListeners() {{
            // Search input with debounce
            let searchTimeout;
            document.getElementById('searchInput').addEventListener('input', (e) => {{
                clearTimeout(searchTimeout);
                searchTimeout = setTimeout(() => {{
                    currentFilters.search = e.target.value.toLowerCase();
                    pagination.currentPage = 1; // Reset to first page on search
                    applyFilters();
                }}, 300);
            }});
            
            // Year inputs
            document.getElementById('yearMin').addEventListener('change', (e) => {{
                currentFilters.yearMin = parseInt(e.target.value);
                pagination.currentPage = 1;
                applyFilters();
            }});
            
            document.getElementById('yearMax').addEventListener('change', (e) => {{
                currentFilters.yearMax = parseInt(e.target.value);
                pagination.currentPage = 1;
                applyFilters();
            }});
            
            // Handle browser back/forward
            window.addEventListener('hashchange', () => {{
                loadPageFromURL();
                updateResults();
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
            
            // Reset pagination on filter change
            pagination.currentPage = 1;
            
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
            
            // Reset pagination on filter change
            pagination.currentPage = 1;
            
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
                    const measureTopic = measure.topic_primary || measure.category_topic || '';
                    if (!currentFilters.topics.includes(measureTopic)) {{
                        return false;
                    }}
                }}
                
                // Search filter
                if (currentFilters.search) {{
                    const searchText = [
                        measure.title,
                        measure.measure_text,
                        measure.measure_id,
                        measure.description,
                        measure.summary_text,
                        measure.topic_primary,
                        measure.year
                    ].filter(Boolean).join(' ').toLowerCase();

                    if (!searchText.includes(currentFilters.search)) {{
                        return false;
                    }}
                }}

                // Regions filter (multi-select)
                if (currentFilters.regions && currentFilters.regions.length > 0) {{
                    // Get all counties from selected regions
                    const selectedCounties = [];
                    currentFilters.regions.forEach(regionName => {{
                        const regionData = CA_REGIONS[regionName];
                        if (regionData) {{
                            selectedCounties.push(...regionData.counties);
                        }}
                    }});

                    // Check if measure is in any selected region
                    if (!measure.county || !selectedCounties.includes(measure.county.toUpperCase())) {{
                        return false;
                    }}
                }}

                // County filter
                if (currentFilters.county) {{
                    if (!measure.county || measure.county.toUpperCase() !== currentFilters.county.toUpperCase()) {{
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
            // Calculate pagination
            pagination.totalPages = Math.ceil(filteredMeasures.length / pagination.itemsPerPage);
            pagination.currentPage = Math.min(pagination.currentPage, Math.max(1, pagination.totalPages));
            
            // Update URL
            updateURL();
            
            // Update count
            document.getElementById('resultsCount').textContent = filteredMeasures.length.toLocaleString();
            
            // Update description
            const desc = currentFilters.search ? 
                `measures matching "${{currentFilters.search}}"` : 
                'measures found';
            document.getElementById('resultsDescription').textContent = desc;
            
            // Determine if we should show hero and featured sections (only on "home" view with no filters)
            const heroSection = document.getElementById('heroSection');
            const featuredSection = document.getElementById('featuredSection');
            const isHomeView = !currentFilters.search &&
                currentFilters.status.length === 0 &&
                currentFilters.features.length === 0 &&
                currentFilters.topics.length === 0 &&
                currentFilters.yearMin === {stats.get('year_min', 1902)} &&
                currentFilters.yearMax === {stats.get('year_max', 2026)} &&
                pagination.currentPage === 1;

            if (isHomeView) {{
                // Show hero section only if we have 2026 measures
                if (heroMeasures.length > 0) {{
                    heroSection.style.display = 'block';
                    displayHero();
                }} else {{
                    heroSection.style.display = 'none';
                }}

                featuredSection.style.display = 'block';
                displayFeatured();
            }} else {{
                heroSection.style.display = 'none';
                featuredSection.style.display = 'none';
            }}

            // Display paginated results
            displayResults();
        }}

        // Display hero measures (2026 upcoming measures)
        function displayHero() {{
            const grid = document.getElementById('heroGrid');
            grid.innerHTML = heroMeasures.map(measure => createCard(measure, false, null, true)).join('');
        }}

        // Display featured measures (curated selection)
        function displayFeatured() {{
            const grid = document.getElementById('featuredGrid');
            grid.innerHTML = featuredMeasures.map(measure => createCard(measure, true, measure._featuredReason)).join('');
        }}
        
        // Display paginated results
        function displayResults() {{
            const container = document.getElementById('resultsContainer');
            
            if (filteredMeasures.length === 0) {{
                container.innerHTML = `
                    <div class="empty-state">
                        <div class="empty-icon">🔍</div>
                        <h3>No measures found</h3>
                        <p>Try adjusting your filters or search terms</p>
                    </div>
                `;
                return;
            }}
            
            // Calculate slice for current page
            const startIndex = (pagination.currentPage - 1) * pagination.itemsPerPage;
            const endIndex = startIndex + pagination.itemsPerPage;
            const pageMeasures = filteredMeasures.slice(startIndex, endIndex);
            
            // Render results
            let resultsHTML;
            if (currentView === 'grid') {{
                resultsHTML = `
                    <div class="results-grid">
                        ${{pageMeasures.map(m => createCard(m)).join('')}}
                    </div>
                `;
            }} else {{
                resultsHTML = `
                    <div class="results-list">
                        ${{pageMeasures.map(m => createListItem(m)).join('')}}
                    </div>
                `;
            }}
            
            // Add pagination controls
            const paginationHTML = renderPaginationControls(startIndex, endIndex);

            container.innerHTML = resultsHTML + paginationHTML;
        }}
        
        // Render pagination controls
        function renderPaginationControls(startIndex, endIndex) {{
            if (pagination.totalPages <= 1) {{
                return ''; // No pagination needed for single page
            }}
            
            const current = pagination.currentPage;
            const total = pagination.totalPages;
            
            // Build page buttons
            let pageButtons = '';
            
            // Calculate which page numbers to show
            const pages = [];
            pages.push(1); // Always show first page
            
            // Pages around current
            for (let i = Math.max(2, current - 2); i <= Math.min(total - 1, current + 2); i++) {{
                pages.push(i);
            }}
            
            if (total > 1) pages.push(total); // Always show last page
            
            // Remove duplicates and sort
            const uniquePages = [...new Set(pages)].sort((a, b) => a - b);
            
            // Build buttons with ellipsis
            let lastPage = 0;
            uniquePages.forEach(page => {{
                if (page - lastPage > 1) {{
                    pageButtons += '<span class="pagination-ellipsis">...</span>';
                }}
                const activeClass = page === current ? 'active' : '';
                pageButtons += `<button class="pagination-btn ${{activeClass}}" onclick="goToPage(${{page}})">${{page}}</button>`;
                lastPage = page;
            }});
            
            const showingStart = startIndex + 1;
            const showingEnd = Math.min(endIndex, filteredMeasures.length);
            
            return `
                <div class="pagination-container">
                    <div class="pagination-controls">
                        <button class="pagination-btn" onclick="goToPage(1)" ${{current === 1 ? 'disabled' : ''}} title="First page">
                            ⟪
                        </button>
                        <button class="pagination-btn" onclick="goToPage(${{current - 1}})" ${{current === 1 ? 'disabled' : ''}} title="Previous page">
                            ←
                        </button>
                        ${{pageButtons}}
                        <button class="pagination-btn" onclick="goToPage(${{current + 1}})" ${{current === total ? 'disabled' : ''}} title="Next page">
                            →
                        </button>
                        <button class="pagination-btn" onclick="goToPage(${{total}})" ${{current === total ? 'disabled' : ''}} title="Last page">
                            ⟫
                        </button>
                    </div>
                    <div class="pagination-info">
                        <span>Showing ${{showingStart.toLocaleString()}}–${{showingEnd.toLocaleString()}} of ${{filteredMeasures.length.toLocaleString()}}</span>
                        <select class="page-size-select" onchange="updateItemsPerPage(this.value)">
                            <option value="25" ${{pagination.itemsPerPage === 25 ? 'selected' : ''}}>25 per page</option>
                            <option value="50" ${{pagination.itemsPerPage === 50 ? 'selected' : ''}}>50 per page</option>
                            <option value="100" ${{pagination.itemsPerPage === 100 ? 'selected' : ''}}>100 per page</option>
                        </select>
                    </div>
                </div>
            `;
        }}
        
        // Go to specific page
        function goToPage(page) {{
            pagination.currentPage = Math.max(1, Math.min(page, pagination.totalPages));
            updateResults();
            
            // Scroll to top of results
            document.getElementById('resultsContainer').scrollIntoView({{ behavior: 'smooth', block: 'start' }});
        }}
        
        // Update items per page
        function updateItemsPerPage(value) {{
            pagination.itemsPerPage = parseInt(value);
            pagination.currentPage = 1; // Reset to first page
            updateResults();
        }}
        
        // Create card HTML
        function createCard(measure, featured = false, featuredReason = null, isHero = false) {{
            // Use generated title if available, otherwise fall back to original
            const title = measure.generated_title || measure.title || measure.measure_text || 'Untitled Measure';
            const originalTitle = measure.original_title || measure.title || measure.measure_text;
            const measureId = measure.measure_id || '';
            const displayTitle = measureId ? `${{measureId}}: ${{title}}` : title;
            const year = measure.year || 'Unknown';
            const passed = measure.passed;
            const passedClass = passed === 1 ? 'passed' : passed === 0 ? 'failed' : 'pending';
            const passedText = passed === 1 ? 'Passed' : passed === 0 ? 'Failed' : 'Pending';

            // Get summary/description - prioritize summary fields
            let summary = '';
            let hasSummary = false;

            // Check for AI refusal patterns (bad summaries that should be filtered out)
            const isAiRefusal = (text) => {{
                if (!text) return false;
                const lower = text.toLowerCase();
                return lower.includes("can't provide") ||
                       lower.includes("cannot provide") ||
                       lower.includes("can't help with that") ||
                       lower.includes("cannot help with that") ||
                       lower.includes("don't have any information") ||
                       lower.includes("do not have any information") ||
                       lower.includes("i don't have information") ||
                       lower.includes("i'd be happy to provide") ||
                       lower.includes("if you could provide") ||
                       lower.includes("please share the details") ||
                       lower.includes("no information available");
            }};

            // Priority order: summary_text > ballot_question > description > original_title
            // But skip AI refusals
            if (measure.summary_text && measure.summary_text.length > 50 && !isAiRefusal(measure.summary_text)) {{
                summary = measure.summary_text;
                hasSummary = true;
            }} else if (measure.ballot_question && measure.ballot_question.length > 50) {{
                summary = measure.ballot_question;
                hasSummary = true;
            }} else if (measure.description) {{
                summary = measure.description;
            }} else if (measure.generated_title && measure.original_title) {{
                // If we generated a title, show the original as fallback
                summary = measure.original_title;
            }}

            // Truncate to 2-3 lines (approximately 200 chars)
            const maxLength = 200;
            const truncatedSummary = summary.length > maxLength ? summary.substring(0, maxLength) + '...' : summary;
            const isLongSummary = summary.length > maxLength;

            const descriptionHtml = truncatedSummary ? `
                <div class="card-summary ${{hasSummary ? 'has-summary' : ''}}"
                     ${{isLongSummary ? 'data-full-text="' + summary.replace(/"/g, '&quot;') + '" data-short-text="' + truncatedSummary.replace(/"/g, '&quot;') + '"' : ''}}
                     ${{isLongSummary ? 'style="cursor: pointer;" title="Click to expand"' : ''}}
                     onclick="${{isLongSummary ? 'toggleSummary(this)' : ''}}">${{truncatedSummary}}</div>
                ${{isLongSummary && measure.source_url ? '<a href="' + measure.source_url + '" target="_blank" rel="noopener noreferrer" class="read-more">Read more on Ballotpedia →</a>' : ''}}
            ` : '';

            const percentYes = measure.percent_yes;
            const voteBar = percentYes != null ? `
                <div class="vote-bar">
                    <div class="vote-bar-fill" style="width: ${{Math.round(percentYes)}}%"></div>
                </div>
            ` : '';

            const topic = measure.topic_primary || measure.category_topic || '';
            const source = measure.data_source || measure.source || 'Unknown';

            const featuredLabel = featured && featuredReason ?
                `<span class="featured-label">${{featuredReason}}</span>` : '';

            // Add summary badge if has_summary
            const summaryBadge = hasSummary ? '<span class="badge badge-summary" title="Has detailed summary">📄 Summary</span>' : '';

            // Determine card class
            const cardClass = isHero ? 'hero' : (featured ? 'featured' : '');

            return `
                <div class="measure-card ${{cardClass}}" onclick="viewMeasure(${{JSON.stringify(measure).replace(/"/g, '&quot;')}})">
                    <div class="card-header">
                        <div class="card-year">📅 ${{year}} ${{featuredLabel}}</div>
                        <div class="card-badges">
                            <span class="badge badge-${{passedClass}}">${{passedText}}</span>
                            ${{summaryBadge}}
                        </div>
                    </div>
                    <h3 class="card-title">${{displayTitle}}</h3>
                    ${{descriptionHtml}}
                    ${{voteBar}}
                    <div class="card-meta">
                        ${{percentYes != null ? `<div class="meta-item">📊 ${{Math.round(percentYes)}}% Yes</div>` : ''}}
                        ${{topic ? `<div class="meta-item">🏷️ ${{topic}}</div>` : ''}}
                        <div class="meta-item">🗂️ ${{source}}</div>
                    </div>
                </div>
            `;
        }}
        
        // Create list item HTML
        function createListItem(measure) {{
            const title = measure.title || measure.measure_text || 'Untitled Measure';
            const measureId = measure.measure_id || '';
            const displayTitle = measureId ? `${{measureId}}: ${{title}}` : title;
            const year = measure.year || 'Unknown';
            const passed = measure.passed;
            const passedClass = passed === 1 ? 'passed' : passed === 0 ? 'failed' : 'pending';
            const passedText = passed === 1 ? '✓' : passed === 0 ? '✗' : '?';
            
            return `
                <div class="measure-list-item" onclick="viewMeasure(${{JSON.stringify(measure).replace(/"/g, '&quot;')}})">
                    <div class="badge badge-${{passedClass}}">${{passedText}}</div>
                    <div>
                        <div style="font-weight: 500;">${{displayTitle}}</div>
                        <div style="font-size: 0.875rem; color: var(--text-secondary);">
                            ${{year}} • ${{measure.topic_primary || measure.category_topic || 'General'}}
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
            displayResults();
        }}
        
        // Clear all filters
        function clearAllFilters() {{
            currentFilters = {{
                yearMin: {stats.get('year_min', 1902)},
                yearMax: {stats.get('year_max', 2026)},
                status: [],
                features: [],
                topics: [],
                search: ''
            }};
            
            // Reset pagination
            pagination.currentPage = 1;
            
            // Reset UI
            document.getElementById('searchInput').value = '';
            document.getElementById('yearMin').value = {stats.get('year_min', 1902)};
            document.getElementById('yearMax').value = {stats.get('year_max', 2026)};
            updateFilterUI();
            updateTopicUI();
            
            applyFilters();
        }}
        """

    def _get_chat_javascript(self) -> str:
        """Get JavaScript for AI chat functionality"""
        return """
        // AI Chat Configuration
        const AI_CONFIG_KEY = 'ballotMeasuresAIConfig';
        let aiConfig = null;

        // Load AI configuration from localStorage
        function loadAIConfig() {
            const saved = localStorage.getItem(AI_CONFIG_KEY);
            if (saved) {
                aiConfig = JSON.parse(saved);
                updateChatInputState();
            }
        }

        // Save AI configuration to localStorage
        function saveAIConfig(config) {
            aiConfig = config;
            localStorage.setItem(AI_CONFIG_KEY, JSON.stringify(config));
            updateChatInputState();
        }

        // Update chat input state based on whether AI is configured
        function updateChatInputState() {
            const chatInput = document.getElementById('chatInput');
            const chatSend = document.getElementById('chatSend');

            if (aiConfig && aiConfig.provider) {
                chatInput.disabled = false;
                chatInput.placeholder = 'Ask a question about ballot measures...';
                chatSend.disabled = false;
            } else {
                chatInput.disabled = true;
                chatInput.placeholder = 'Configure AI provider first (click ⚙️)';
                chatSend.disabled = true;
            }
        }

        // Toggle chat panel
        function toggleChat() {
            const panel = document.getElementById('chatPanel');
            const chatIcon = document.querySelector('.chat-icon');
            const closeIcon = document.querySelector('.close-icon');

            if (panel.style.display === 'none' || !panel.style.display) {
                panel.style.display = 'flex';
                chatIcon.style.display = 'none';
                closeIcon.style.display = 'block';
            } else {
                panel.style.display = 'none';
                chatIcon.style.display = 'block';
                closeIcon.style.display = 'none';
            }
        }

        // Open settings modal
        function openChatSettings() {
            const modal = document.getElementById('chatSettingsModal');
            modal.style.display = 'flex';

            // Load current settings
            if (aiConfig) {
                document.getElementById('aiProvider').value = aiConfig.provider || '';
                if (aiConfig.apiKey) {
                    document.getElementById('apiKey').value = aiConfig.apiKey;
                }
                if (aiConfig.ollamaUrl) {
                    document.getElementById('ollamaUrl').value = aiConfig.ollamaUrl;
                }
                if (aiConfig.ollamaModel) {
                    document.getElementById('ollamaModel').value = aiConfig.ollamaModel;
                }
                updateProviderFields();
            }
        }

        // Close settings modal
        function closeChatSettings() {
            const modal = document.getElementById('chatSettingsModal');
            modal.style.display = 'none';
        }

        // Update provider fields based on selection
        function updateProviderFields() {
            const provider = document.getElementById('aiProvider').value;
            const apiKeySection = document.getElementById('apiKeySection');
            const ollamaSection = document.getElementById('ollamaSection');
            const testBtn = document.getElementById('testConnection');
            const apiKeyLabel = document.getElementById('apiKeyLabel');

            apiKeySection.style.display = 'none';
            ollamaSection.style.display = 'none';
            testBtn.disabled = !provider;

            if (provider === 'openai') {
                apiKeySection.style.display = 'block';
                apiKeyLabel.textContent = 'OpenAI API Key';
                document.getElementById('apiKey').placeholder = 'sk-...';
            } else if (provider === 'anthropic') {
                apiKeySection.style.display = 'block';
                apiKeyLabel.textContent = 'Anthropic API Key';
                document.getElementById('apiKey').placeholder = 'sk-ant-...';
            } else if (provider === 'ollama') {
                ollamaSection.style.display = 'block';
            }
        }

        // Test AI connection
        async function testAIConnection() {
            const provider = document.getElementById('aiProvider').value;
            const statusEl = document.getElementById('connectionStatus');
            const testBtn = document.getElementById('testConnection');

            testBtn.disabled = true;
            statusEl.textContent = 'Testing...';
            statusEl.className = 'connection-status';

            try {
                if (provider === 'openai') {
                    const apiKey = document.getElementById('apiKey').value;
                    const response = await fetch('https://cal-vgp-proxy.igorgeyn.workers.dev/openai', {
                        headers: { 'Authorization': `Bearer ${apiKey}` }
                    });
                    if (response.ok) {
                        statusEl.textContent = '✓ Connected';
                        statusEl.className = 'connection-status success';
                    } else {
                        throw new Error('Invalid API key');
                    }
                } else if (provider === 'anthropic') {
                    const apiKey = document.getElementById('apiKey').value;
                    const response = await fetch('https://cal-vgp-proxy.igorgeyn.workers.dev/anthropic', {
                        method: 'POST',
                        headers: {
                            'x-api-key': apiKey,
                            'anthropic-version': '2023-06-01',
                            'content-type': 'application/json'
                        },
                        body: JSON.stringify({
                            model: 'claude-3-5-sonnet-20241022',
                            max_tokens: 1,
                            messages: [{ role: 'user', content: 'test' }]
                        })
                    });
                    if (response.ok || response.status === 400) {
                        statusEl.textContent = '✓ Connected';
                        statusEl.className = 'connection-status success';
                    } else {
                        throw new Error('Invalid API key');
                    }
                } else if (provider === 'ollama') {
                    const url = document.getElementById('ollamaUrl').value;
                    const response = await fetch(`${url}/api/tags`);
                    if (response.ok) {
                        statusEl.textContent = '✓ Connected';
                        statusEl.className = 'connection-status success';
                    } else {
                        throw new Error('Cannot connect to Ollama');
                    }
                }
            } catch (error) {
                statusEl.textContent = '✗ ' + error.message;
                statusEl.className = 'connection-status error';
            }

            testBtn.disabled = false;
        }

        // Save chat settings
        function saveChatSettings() {
            const provider = document.getElementById('aiProvider').value;

            if (!provider) {
                alert('Please select an AI provider');
                return;
            }

            const config = { provider };

            if (provider === 'openai' || provider === 'anthropic') {
                const apiKey = document.getElementById('apiKey').value;
                if (!apiKey) {
                    alert('Please enter an API key');
                    return;
                }
                config.apiKey = apiKey;
            } else if (provider === 'ollama') {
                config.ollamaUrl = document.getElementById('ollamaUrl').value;
                config.ollamaModel = document.getElementById('ollamaModel').value;
            }

            saveAIConfig(config);
            closeChatSettings();

            // Show success message in chat
            addBotMessage('AI configured successfully! You can now ask questions about ballot measures.');
        }

        // Send user message
        async function sendMessage() {
            const input = document.getElementById('chatInput');
            const message = input.value.trim();

            if (!message || !aiConfig) return;

            // Add user message to chat
            addUserMessage(message);
            input.value = '';

            // Show typing indicator
            showTypingIndicator();

            try {
                // Query data and get AI response
                const response = await queryAI(message);
                hideTypingIndicator();
                addBotMessage(response);
            } catch (error) {
                hideTypingIndicator();
                addBotMessage('Sorry, I encountered an error: ' + error.message);
            }
        }

        // Query AI with relevant data
        async function queryAI(question) {
            // Get relevant data from the measures
            const context = prepareDataContext(question);

            // Build prompt
            const prompt = `You are a helpful assistant analyzing California ballot measures data.

Here's information about the ballot measures database:
${context}

User question: ${question}

Please provide a helpful, accurate response based on the data provided. If you reference specific measures, include their title and year.`;

            // Call appropriate AI API
            if (aiConfig.provider === 'openai') {
                return await callOpenAI(prompt);
            } else if (aiConfig.provider === 'anthropic') {
                return await callAnthropic(prompt);
            } else if (aiConfig.provider === 'ollama') {
                return await callOllama(prompt);
            }
        }

        // Prepare data context for AI
        function prepareDataContext(question) {
            const q = question.toLowerCase();
            let context = `Total measures in database: ${allMeasures.length}\\n`;
            context += `Years covered: ${Math.min(...allMeasures.map(m => m.year || 0))} - ${Math.max(...allMeasures.map(m => m.year || 0))}\\n\\n`;

            // Check if question is about specific topics
            const topics = [...new Set(allMeasures.map(m => m.topic_primary).filter(Boolean))];
            if (q.includes('topic') || q.includes('category')) {
                context += `Topics available: ${topics.slice(0, 20).join(', ')}\\n\\n`;
            }

            // Check if question is about pass rates
            if (q.includes('pass') || q.includes('fail') || q.includes('success')) {
                const passed = allMeasures.filter(m => m.result === 'Passed').length;
                const failed = allMeasures.filter(m => m.result === 'Failed').length;
                context += `Pass/Fail statistics: ${passed} passed, ${failed} failed\\n\\n`;
            }

            // Check if question is about close races
            if (q.includes('close') || q.includes('narrow') || q.includes('margin')) {
                const withVotes = allMeasures.filter(m => m.votes_for && m.votes_against);
                const closeMeasures = withVotes
                    .map(m => ({
                        ...m,
                        margin: Math.abs(m.votes_for - m.votes_against) / (m.votes_for + m.votes_against)
                    }))
                    .sort((a, b) => a.margin - b.margin)
                    .slice(0, 10);

                context += `10 Closest measures:\\n`;
                closeMeasures.forEach((m, i) => {
                    context += `${i+1}. ${m.concise_title || m.title} (${m.year}) - ${(m.margin * 100).toFixed(1)}% margin\\n`;
                });
                context += '\\n';
            }

            // Check if question is about specific years
            const yearMatch = question.match(/20\\d{2}/);
            if (yearMatch) {
                const year = yearMatch[0];
                const yearMeasures = allMeasures.filter(m => m.year == year);
                context += `Measures from ${year}: ${yearMeasures.length} total\\n\\n`;
            }

            // Check if question is about specific counties
            const counties = [...new Set(allMeasures.map(m => m.county).filter(Boolean))];
            counties.forEach(county => {
                if (q.includes(county.toLowerCase())) {
                    const countyMeasures = allMeasures.filter(m => m.county === county);
                    context += `Measures in ${county}: ${countyMeasures.length} total\\n\\n`;
                }
            });

            return context;
        }

        // Call OpenAI API
        async function callOpenAI(prompt) {
            const response = await fetch('https://cal-vgp-proxy.igorgeyn.workers.dev/openai', {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${aiConfig.apiKey}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    model: 'gpt-4o',
                    messages: [{ role: 'user', content: prompt }],
                    max_tokens: 500
                })
            });

            if (!response.ok) {
                throw new Error('OpenAI API error');
            }

            const data = await response.json();
            return data.choices[0].message.content;
        }

        // Call Anthropic API
        async function callAnthropic(prompt) {
            const response = await fetch('https://cal-vgp-proxy.igorgeyn.workers.dev/anthropic', {
                method: 'POST',
                headers: {
                    'x-api-key': aiConfig.apiKey,
                    'anthropic-version': '2023-06-01',
                    'content-type': 'application/json'
                },
                body: JSON.stringify({
                    model: 'claude-3-5-sonnet-20241022',
                    max_tokens: 500,
                    messages: [{ role: 'user', content: prompt }]
                })
            });

            if (!response.ok) {
                throw new Error('Anthropic API error');
            }

            const data = await response.json();
            return data.content[0].text;
        }

        // Call Ollama API
        async function callOllama(prompt) {
            const response = await fetch(`${aiConfig.ollamaUrl}/api/generate`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    model: aiConfig.ollamaModel,
                    prompt: prompt,
                    stream: false
                })
            });

            if (!response.ok) {
                throw new Error('Ollama API error');
            }

            const data = await response.json();
            return data.response;
        }

        // Add user message to chat
        function addUserMessage(text) {
            const messagesContainer = document.getElementById('chatMessages');
            const messageEl = document.createElement('div');
            messageEl.className = 'chat-message user';
            messageEl.innerHTML = `
                <div class="chat-message-content">
                    <p>${escapeHtml(text)}</p>
                </div>
            `;
            messagesContainer.appendChild(messageEl);
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }

        // Add bot message to chat
        function addBotMessage(text) {
            const messagesContainer = document.getElementById('chatMessages');
            const messageEl = document.createElement('div');
            messageEl.className = 'chat-message bot';
            messageEl.innerHTML = `
                <div class="chat-message-content">
                    ${formatBotMessage(text)}
                </div>
            `;
            messagesContainer.appendChild(messageEl);
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }

        // Format bot message (support markdown-like syntax)
        function formatBotMessage(text) {
            // Simple markdown: **bold**, numbered lists
            let html = text
                .split('\\n\\n')
                .map(para => `<p>${para}</p>`)
                .join('');

            // Bold text
            html = html.replace(/\\*\\*(.*?)\\*\\*/g, '<strong>$1</strong>');

            return html;
        }

        // Escape HTML
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        // Show typing indicator
        function showTypingIndicator() {
            const messagesContainer = document.getElementById('chatMessages');
            const indicator = document.createElement('div');
            indicator.id = 'typingIndicator';
            indicator.className = 'chat-message bot';
            indicator.innerHTML = `
                <div class="chat-typing-indicator">
                    <div class="chat-typing-dot"></div>
                    <div class="chat-typing-dot"></div>
                    <div class="chat-typing-dot"></div>
                </div>
            `;
            messagesContainer.appendChild(indicator);
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }

        // Hide typing indicator
        function hideTypingIndicator() {
            const indicator = document.getElementById('typingIndicator');
            if (indicator) {
                indicator.remove();
            }
        }

        // Handle example prompt click
        function askExample(button) {
            const question = button.textContent;
            document.getElementById('chatInput').value = question;
            sendMessage();
        }

        // Handle Enter key in chat input
        document.addEventListener('DOMContentLoaded', function() {
            const chatInput = document.getElementById('chatInput');
            if (chatInput) {
                chatInput.addEventListener('keydown', function(e) {
                    if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault();
                        sendMessage();
                    }
                });

                // Auto-resize textarea
                chatInput.addEventListener('input', function() {
                    this.style.height = 'auto';
                    this.style.height = Math.min(this.scrollHeight, 120) + 'px';
                });
            }

            // Load AI config on page load
            loadAIConfig();

            // Close modal when clicking outside
            const modal = document.getElementById('chatSettingsModal');
            if (modal) {
                modal.addEventListener('click', function(e) {
                    if (e.target === modal) {
                        closeChatSettings();
                    }
                });
            }
        });
        """