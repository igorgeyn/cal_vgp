"""
HTML/CSS/JS components for historical ballot measure context.
These components can be integrated into the static site generator.
"""

from typing import Dict, List, Optional
from ..database.historical_schema import TOPIC_CONFIG


def get_historical_css() -> str:
    """
    CSS styles for historical context components.
    Should be added to the main stylesheet.
    """
    return """
/* =============================================================================
   Historical Context Components
   ============================================================================= */

/* Topic Tags */
.topic-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 0.375rem;
    margin: 0.5rem 0;
}

.topic-tag {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    padding: 0.25rem 0.625rem;
    border-radius: 100px;
    font-size: 0.75rem;
    font-weight: 500;
    transition: all 0.2s ease;
    cursor: pointer;
    border: 1px solid transparent;
}

.topic-tag:hover {
    filter: brightness(0.95);
    transform: translateY(-1px);
}

.topic-tag.primary {
    font-weight: 600;
}

.topic-tag.secondary {
    opacity: 0.85;
    font-size: 0.7rem;
}

.topic-tag-icon {
    font-size: 0.8rem;
}

/* Topic-specific colors */
.topic-tag.marijuana { background: #dcfce7; color: #166534; border-color: #bbf7d0; }
.topic-tag.gambling { background: #fef9c3; color: #854d0e; border-color: #fef08a; }
.topic-tag.abortion { background: #fce7f3; color: #9d174d; border-color: #fbcfe8; }
.topic-tag.marriage { background: #ede9fe; color: #5b21b6; border-color: #ddd6fe; }
.topic-tag.tax { background: #ffedd5; color: #9a3412; border-color: #fed7aa; }
.topic-tag.education { background: #dbeafe; color: #1e40af; border-color: #bfdbfe; }
.topic-tag.health { background: #fee2e2; color: #991b1b; border-color: #fecaca; }
.topic-tag.elections { background: #e0e7ff; color: #3730a3; border-color: #c7d2fe; }
.topic-tag.criminal { background: #f1f5f9; color: #475569; border-color: #e2e8f0; }
.topic-tag.environment { background: #ccfbf1; color: #115e59; border-color: #99f6e4; }

/* Historical Context Panel */
.historical-panel {
    background: var(--bg-primary, #ffffff);
    border: 1px solid var(--border, #dadce0);
    border-radius: var(--radius, 8px);
    overflow: hidden;
    margin: 1rem 0;
    box-shadow: var(--shadow-sm, 0 1px 2px rgba(0,0,0,0.1));
}

.historical-panel-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 1rem 1.25rem;
    background: var(--bg-secondary, #f8f9fa);
    cursor: pointer;
    user-select: none;
    transition: background 0.2s ease;
}

.historical-panel-header:hover {
    background: var(--bg-tertiary, #e8eaed);
}

.historical-panel-title {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-weight: 600;
    color: var(--text-primary, #202124);
}

.historical-panel-title-icon {
    font-size: 1.25rem;
}

.historical-panel-chevron {
    transition: transform 0.3s ease;
    color: var(--text-secondary, #5f6368);
}

.historical-panel.collapsed .historical-panel-chevron {
    transform: rotate(-90deg);
}

.historical-panel-content {
    padding: 1.25rem;
    display: block;
}

.historical-panel.collapsed .historical-panel-content {
    display: none;
}

/* Context Summary */
.context-summary {
    font-size: 1rem;
    color: var(--text-primary, #202124);
    margin-bottom: 1rem;
    line-height: 1.5;
}

.context-summary strong {
    color: var(--primary, #1a73e8);
}

/* Pass Rate Visualization */
.pass-rate-container {
    margin: 1rem 0;
}

.pass-rate-label {
    font-size: 0.875rem;
    color: var(--text-secondary, #5f6368);
    margin-bottom: 0.5rem;
}

.pass-rate-bar {
    display: flex;
    height: 8px;
    border-radius: 4px;
    overflow: hidden;
    background: var(--bg-tertiary, #e8eaed);
}

.pass-rate-passed {
    background: var(--success, #1e8e3e);
    transition: width 0.5s ease;
}

.pass-rate-failed {
    background: var(--danger, #d93025);
}

.pass-rate-stats {
    display: flex;
    justify-content: space-between;
    margin-top: 0.5rem;
    font-size: 0.8rem;
}

.pass-rate-stats .passed {
    color: var(--success, #1e8e3e);
    font-weight: 500;
}

.pass-rate-stats .failed {
    color: var(--danger, #d93025);
    font-weight: 500;
}

/* Most Recent Measure Card */
.recent-measure {
    background: var(--bg-secondary, #f8f9fa);
    border-radius: var(--radius-sm, 4px);
    padding: 1rem;
    margin-top: 1rem;
}

.recent-measure-header {
    font-size: 0.75rem;
    color: var(--text-tertiary, #80868b);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 0.5rem;
}

.recent-measure-title {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-weight: 600;
    color: var(--text-primary, #202124);
}

.recent-measure-year {
    font-size: 0.875rem;
    color: var(--text-secondary, #5f6368);
    font-weight: normal;
}

.recent-measure-result {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    padding: 0.25rem 0.5rem;
    border-radius: 4px;
    font-size: 0.75rem;
    font-weight: 500;
}

.recent-measure-result.passed {
    background: #dcfce7;
    color: #166534;
}

.recent-measure-result.failed {
    background: #fee2e2;
    color: #991b1b;
}

.recent-measure-description {
    font-size: 0.875rem;
    color: var(--text-secondary, #5f6368);
    margin-top: 0.5rem;
    line-height: 1.4;
}

.recent-measure-margin {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-top: 0.75rem;
    font-size: 0.8rem;
}

.margin-label {
    padding: 0.125rem 0.5rem;
    border-radius: 4px;
    font-weight: 500;
}

.margin-label.landslide { background: #dcfce7; color: #166534; }
.margin-label.comfortable { background: #dbeafe; color: #1e40af; }
.margin-label.close { background: #fef9c3; color: #854d0e; }
.margin-label.very-close { background: #fee2e2; color: #991b1b; }

/* Caveat/Disclaimer */
.historical-caveat {
    font-size: 0.75rem;
    color: var(--text-tertiary, #80868b);
    font-style: italic;
    margin-top: 1rem;
    padding-top: 0.75rem;
    border-top: 1px solid var(--border, #dadce0);
}

/* Topic Filter Chips */
.topic-filter-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    padding: 0.75rem;
    background: var(--bg-secondary, #f8f9fa);
    border-radius: var(--radius, 8px);
    margin-bottom: 1rem;
}

.topic-filter-chip {
    display: inline-flex;
    align-items: center;
    gap: 0.375rem;
    padding: 0.5rem 0.875rem;
    background: var(--bg-primary, #ffffff);
    border: 1px solid var(--border, #dadce0);
    border-radius: 100px;
    cursor: pointer;
    transition: all 0.2s ease;
    font-size: 0.85rem;
    color: var(--text-primary, #202124);
    user-select: none;
}

.topic-filter-chip:hover {
    border-color: var(--primary, #1a73e8);
    background: rgba(26, 115, 232, 0.05);
}

.topic-filter-chip.selected {
    background: var(--primary, #1a73e8);
    border-color: var(--primary, #1a73e8);
    color: white;
}

.topic-filter-chip.disabled {
    opacity: 0.5;
    cursor: not-allowed;
}

.topic-filter-chip-count {
    font-size: 0.75rem;
    opacity: 0.7;
    margin-left: 0.25rem;
}

/* Loading skeleton */
.historical-skeleton {
    animation: skeleton-pulse 1.5s ease-in-out infinite;
}

@keyframes skeleton-pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
}

.skeleton-line {
    height: 1rem;
    background: var(--bg-tertiary, #e8eaed);
    border-radius: 4px;
    margin-bottom: 0.5rem;
}

.skeleton-line.short { width: 60%; }
.skeleton-line.medium { width: 80%; }
.skeleton-line.long { width: 100%; }
"""


def get_historical_js() -> str:
    """
    JavaScript for historical context components.
    Should be added to the main script section.
    """
    return """
// =============================================================================
// Historical Context JavaScript
// =============================================================================

// Topic configuration (matches backend TOPIC_CONFIG)
const TOPIC_CONFIG = {
    marijuana: { label: 'Marijuana/Cannabis', color: '#22c55e', icon: '🌿', priority: 1 },
    gambling: { label: 'Gambling', color: '#eab308', icon: '🎰', priority: 2 },
    abortion: { label: 'Abortion', color: '#ec4899', icon: '⚕️', priority: 3 },
    marriage: { label: 'Marriage Equality', color: '#8b5cf6', icon: '💒', priority: 4 },
    tax: { label: 'Tax/Fiscal', color: '#f97316', icon: '💰', priority: 5 },
    education: { label: 'Education', color: '#3b82f6', icon: '📚', priority: 6 },
    health: { label: 'Healthcare', color: '#ef4444', icon: '🏥', priority: 7 },
    elections: { label: 'Election Reform', color: '#6366f1', icon: '🗳️', priority: 8 },
    criminal: { label: 'Criminal Justice', color: '#64748b', icon: '⚖️', priority: 9 },
    environment: { label: 'Environment', color: '#14b8a6', icon: '🌍', priority: 10 },
};

// API base URL (adjust for your deployment)
const HISTORICAL_API_BASE = '/api/historical';

/**
 * Fetch historical context for a topic
 * @param {string} topic - Topic key (e.g., 'marijuana')
 * @param {number} minYear - Minimum year filter (default 1970)
 * @returns {Promise<Object>} Topic context data
 */
async function fetchTopicContext(topic, minYear = 1970) {
    try {
        const response = await fetch(`${HISTORICAL_API_BASE}/context/${topic}?min_year=${minYear}`);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error(`Error fetching topic context for ${topic}:`, error);
        return null;
    }
}

/**
 * Fetch all topic statistics
 * @param {number} minYear - Minimum year filter
 * @returns {Promise<Array>} Array of topic stats
 */
async function fetchAllTopicStats(minYear = 1970) {
    try {
        const response = await fetch(`${HISTORICAL_API_BASE}/topics?min_year=${minYear}`);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error('Error fetching topic stats:', error);
        return [];
    }
}

/**
 * Render topic tags for a measure
 * @param {Array} topics - Array of topic keys
 * @returns {string} HTML string
 */
function renderTopicTags(topics) {
    if (!topics || topics.length === 0) {
        return '';
    }

    return `
        <div class="topic-tags">
            ${topics.map((topic, index) => {
                const config = TOPIC_CONFIG[topic];
                if (!config) return '';
                const isPrimary = index === 0;
                return `
                    <span class="topic-tag ${topic} ${isPrimary ? 'primary' : 'secondary'}"
                          onclick="filterByTopic('${topic}')"
                          title="${config.label}">
                        <span class="topic-tag-icon">${config.icon}</span>
                        ${config.label}
                    </span>
                `;
            }).join('')}
        </div>
    `;
}

/**
 * Render the historical context panel
 * @param {Object} context - Topic context data from API
 * @param {boolean} collapsed - Whether panel starts collapsed
 * @returns {string} HTML string
 */
function renderHistoricalPanel(context, collapsed = false) {
    if (!context) {
        return '<div class="historical-panel"><p>No historical data available.</p></div>';
    }

    const passRate = context.pass_rate || 0;
    const passedPct = passRate;
    const failedPct = 100 - passRate;

    // Determine margin label class
    let marginClass = 'comfortable';
    if (context.most_recent) {
        const margin = Math.abs(context.most_recent.margin || 0);
        if (margin < 5) marginClass = 'very-close';
        else if (margin < 10) marginClass = 'close';
        else if (margin >= 20) marginClass = 'landslide';
    }

    return `
        <div class="historical-panel ${collapsed ? 'collapsed' : ''}" id="historical-panel-${context.topic}">
            <div class="historical-panel-header" onclick="toggleHistoricalPanel('${context.topic}')">
                <div class="historical-panel-title">
                    <span class="historical-panel-title-icon">${context.icon || '📊'}</span>
                    Historical Context: ${context.topic_label}
                </div>
                <svg class="historical-panel-chevron" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="6 9 12 15 18 9"></polyline>
                </svg>
            </div>
            <div class="historical-panel-content">
                <p class="context-summary">
                    California has voted on <strong>${context.total_measures}</strong> ${context.topic_label.toLowerCase()} measures
                    since <strong>${context.first_year}</strong>.
                </p>

                <div class="pass-rate-container">
                    <div class="pass-rate-label">Pass Rate</div>
                    <div class="pass-rate-bar">
                        <div class="pass-rate-passed" style="width: ${passedPct}%"></div>
                        <div class="pass-rate-failed" style="width: ${failedPct}%"></div>
                    </div>
                    <div class="pass-rate-stats">
                        <span class="passed">${context.passed_count} passed (${passRate.toFixed(0)}%)</span>
                        <span class="failed">${context.failed_count} failed</span>
                    </div>
                </div>

                ${context.most_recent ? `
                    <div class="recent-measure">
                        <div class="recent-measure-header">Most Recent</div>
                        <div class="recent-measure-title">
                            ${context.most_recent.ballot_name}
                            <span class="recent-measure-year">(${context.most_recent.year})</span>
                            <span class="recent-measure-result ${context.most_recent.passed ? 'passed' : 'failed'}">
                                ${context.most_recent.passed ? '✓ Passed' : '✗ Failed'}
                            </span>
                        </div>
                        ${context.most_recent.description ? `
                            <p class="recent-measure-description">${context.most_recent.description}</p>
                        ` : ''}
                        ${context.most_recent.pct_yes ? `
                            <div class="recent-measure-margin">
                                <span>${context.most_recent.pct_yes.toFixed(1)}% Yes</span>
                                <span class="margin-label ${marginClass}">
                                    ${marginClass === 'very-close' ? 'Very Close' :
                                      marginClass === 'close' ? 'Close' :
                                      marginClass === 'landslide' ? 'Landslide' : 'Comfortable'}
                                </span>
                            </div>
                        ` : ''}
                    </div>
                ` : ''}

                <p class="historical-caveat">
                    Note: Historical pass rates describe past outcomes only and do not predict future results.
                    Each measure is unique and depends on current context, wording, and campaign dynamics.
                </p>
            </div>
        </div>
    `;
}

/**
 * Toggle historical panel collapse state
 * @param {string} topic - Topic key
 */
function toggleHistoricalPanel(topic) {
    const panel = document.getElementById(`historical-panel-${topic}`);
    if (panel) {
        panel.classList.toggle('collapsed');
    }
}

/**
 * Render topic filter chips
 * @param {Array} topicStats - Array of topic statistics
 * @param {string} selectedTopic - Currently selected topic (optional)
 * @returns {string} HTML string
 */
function renderTopicFilterChips(topicStats, selectedTopic = null) {
    if (!topicStats || topicStats.length === 0) {
        return '';
    }

    return `
        <div class="topic-filter-chips">
            <span class="topic-filter-chip ${!selectedTopic ? 'selected' : ''}"
                  onclick="filterByTopic(null)">
                All Topics
            </span>
            ${topicStats.map(stat => `
                <span class="topic-filter-chip ${selectedTopic === stat.topic ? 'selected' : ''} ${stat.total_measures < 3 ? 'disabled' : ''}"
                      onclick="${stat.total_measures >= 3 ? `filterByTopic('${stat.topic}')` : ''}"
                      title="${stat.label}: ${stat.total_measures} measures, ${stat.pass_rate}% pass rate">
                    <span>${stat.icon}</span>
                    ${stat.label}
                    <span class="topic-filter-chip-count">(${stat.total_measures})</span>
                </span>
            `).join('')}
        </div>
    `;
}

/**
 * Filter measures by topic (to be implemented by main app)
 * @param {string|null} topic - Topic key or null for all
 */
function filterByTopic(topic) {
    // This should be implemented in the main application
    console.log('Filter by topic:', topic);

    // Example integration:
    // if (typeof applyTopicFilter === 'function') {
    //     applyTopicFilter(topic);
    // }
}

/**
 * Load and render historical context for a topic into a container
 * @param {string} containerId - ID of container element
 * @param {string} topic - Topic key
 * @param {boolean} collapsed - Start collapsed
 */
async function loadHistoricalContext(containerId, topic, collapsed = false) {
    const container = document.getElementById(containerId);
    if (!container) return;

    // Show loading skeleton
    container.innerHTML = `
        <div class="historical-panel historical-skeleton">
            <div class="historical-panel-header">
                <div class="skeleton-line short"></div>
            </div>
            <div class="historical-panel-content">
                <div class="skeleton-line long"></div>
                <div class="skeleton-line medium"></div>
                <div class="skeleton-line short"></div>
            </div>
        </div>
    `;

    // Fetch and render
    const context = await fetchTopicContext(topic);
    if (context) {
        container.innerHTML = renderHistoricalPanel(context, collapsed);
    } else {
        container.innerHTML = `
            <div class="historical-panel">
                <p style="padding: 1rem; color: var(--text-secondary);">
                    Unable to load historical context for this topic.
                </p>
            </div>
        `;
    }
}
"""


def render_topic_tags_html(topics: List[str]) -> str:
    """
    Render topic tags as static HTML.

    Args:
        topics: List of topic keys, sorted by priority

    Returns:
        HTML string for topic tags
    """
    if not topics:
        return ''

    tags = []
    for i, topic in enumerate(topics):
        if topic not in TOPIC_CONFIG:
            continue

        config = TOPIC_CONFIG[topic]
        is_primary = (i == 0)
        class_name = f"topic-tag {topic} {'primary' if is_primary else 'secondary'}"

        tag = f'''<span class="{class_name}" data-topic="{topic}" title="{config['label']}">
            <span class="topic-tag-icon">{config['icon']}</span>
            {config['label']}
        </span>'''
        tags.append(tag)

    return f'<div class="topic-tags">{" ".join(tags)}</div>'


def render_historical_panel_html(
    topic: str,
    total_measures: int,
    first_year: int,
    pass_rate: float,
    passed_count: int,
    failed_count: int,
    most_recent: Optional[Dict] = None,
    collapsed: bool = False
) -> str:
    """
    Render historical context panel as static HTML.

    Args:
        topic: Topic key
        total_measures: Total number of measures
        first_year: First year with measures
        pass_rate: Pass rate percentage (0-100)
        passed_count: Number of passed measures
        failed_count: Number of failed measures
        most_recent: Most recent measure dict (optional)
        collapsed: Whether to start collapsed

    Returns:
        HTML string for historical panel
    """
    if topic not in TOPIC_CONFIG:
        return ''

    config = TOPIC_CONFIG[topic]
    collapsed_class = 'collapsed' if collapsed else ''

    # Most recent measure HTML
    recent_html = ''
    if most_recent:
        passed = most_recent.get('passed', False)
        pct_yes = most_recent.get('pct_yes')
        margin = most_recent.get('margin', 0) if pct_yes else 0

        # Determine margin class
        if abs(margin) < 5:
            margin_class = 'very-close'
            margin_label = 'Very Close'
        elif abs(margin) < 10:
            margin_class = 'close'
            margin_label = 'Close'
        elif abs(margin) >= 20:
            margin_class = 'landslide'
            margin_label = 'Landslide'
        else:
            margin_class = 'comfortable'
            margin_label = 'Comfortable'

        result_class = 'passed' if passed else 'failed'
        result_text = '✓ Passed' if passed else '✗ Failed'

        recent_html = f'''
        <div class="recent-measure">
            <div class="recent-measure-header">Most Recent</div>
            <div class="recent-measure-title">
                {most_recent.get('ballot_name', 'Unknown')}
                <span class="recent-measure-year">({most_recent.get('year', '')})</span>
                <span class="recent-measure-result {result_class}">{result_text}</span>
            </div>
            {f'<p class="recent-measure-description">{most_recent.get("description", "")}</p>' if most_recent.get('description') else ''}
            {f'''<div class="recent-measure-margin">
                <span>{pct_yes:.1f}% Yes</span>
                <span class="margin-label {margin_class}">{margin_label}</span>
            </div>''' if pct_yes else ''}
        </div>
        '''

    return f'''
    <div class="historical-panel {collapsed_class}" id="historical-panel-{topic}">
        <div class="historical-panel-header" onclick="toggleHistoricalPanel('{topic}')">
            <div class="historical-panel-title">
                <span class="historical-panel-title-icon">{config['icon']}</span>
                Historical Context: {config['label']}
            </div>
            <svg class="historical-panel-chevron" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="6 9 12 15 18 9"></polyline>
            </svg>
        </div>
        <div class="historical-panel-content">
            <p class="context-summary">
                California has voted on <strong>{total_measures}</strong> {config['label'].lower()} measures
                since <strong>{first_year}</strong>.
            </p>

            <div class="pass-rate-container">
                <div class="pass-rate-label">Pass Rate</div>
                <div class="pass-rate-bar">
                    <div class="pass-rate-passed" style="width: {pass_rate:.0f}%"></div>
                    <div class="pass-rate-failed" style="width: {100 - pass_rate:.0f}%"></div>
                </div>
                <div class="pass-rate-stats">
                    <span class="passed">{passed_count} passed ({pass_rate:.0f}%)</span>
                    <span class="failed">{failed_count} failed</span>
                </div>
            </div>

            {recent_html}

            <p class="historical-caveat">
                Note: Historical pass rates describe past outcomes only and do not predict future results.
                Each measure is unique and depends on current context, wording, and campaign dynamics.
            </p>
        </div>
    </div>
    '''
