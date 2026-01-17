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
from ..utils.topic_mapping import get_display_topic, get_all_display_categories

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

        # Load recommendations if available
        recommendations = self._load_recommendations()

        # Generate HTML
        html = self._generate_html(measures_data, stats, topics, recommendations)
        
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

            # Add consolidated display topic (maps detailed topics to ~12 categories)
            raw_topic = data.get('topic_primary') or data.get('category_topic')
            data['display_topic'] = get_display_topic(raw_topic)

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

    def _generate_quiz_questions(self, measures: List[Dict], stats: Dict) -> List[Dict]:
        """Generate educational trivia questions from the ballot measures data"""
        questions = []

        # Filter measures with valid data
        measures_with_votes = [m for m in measures if m.get('total_votes') and m.get('total_votes') > 0]
        measures_with_pct = [m for m in measures if m.get('percent_yes') is not None]
        measures_with_year = [m for m in measures if m.get('year')]
        measures_with_numeric_year = [m for m in measures if m.get('year') and str(m.get('year')).isdigit()]

        # Build topic statistics
        topic_pass_rates = {}
        topic_counts = Counter()
        for m in measures:
            topic = m.get('display_topic') or m.get('topic_primary')
            if topic:
                topic_counts[topic] += 1
                if m.get('passed') is not None:
                    if topic not in topic_pass_rates:
                        topic_pass_rates[topic] = {'passed': 0, 'total': 0}
                    topic_pass_rates[topic]['total'] += 1
                    if m.get('passed'):
                        topic_pass_rates[topic]['passed'] += 1

        qualifying_topics = {t: d for t, d in topic_pass_rates.items() if d['total'] >= 20}

        # Build county statistics
        county_counts = Counter(m.get('county') for m in measures if m.get('county'))

        # Build year statistics
        year_counts = Counter(str(m.get('year')) for m in measures_with_year if m.get('year'))

        # Build decade statistics
        decade_counts = Counter((int(m.get('year')) // 10) * 10 for m in measures_with_numeric_year)

        # 1. Overall pass rate - fundamental insight
        passed_count = sum(1 for m in measures if m.get('passed'))
        total_decided = sum(1 for m in measures if m.get('passed') is not None)
        if total_decided > 0:
            pass_rate = (passed_count / total_decided) * 100
            questions.append({
                'question': 'What percentage of California ballot measures pass?',
                'answer': f'{pass_rate:.1f}% - roughly {int(round(pass_rate/10))} out of every 10 measures that go to voters end up passing. This is higher than many people expect!',
                'category': 'Pass Rates'
            })

        # 2. Most common topic
        if topic_counts:
            top_topic, topic_count = topic_counts.most_common(1)[0]
            pct_of_total = (topic_count / len(measures)) * 100
            questions.append({
                'question': 'What is the most common ballot measure topic in California?',
                'answer': f'{top_topic} - accounting for {topic_count:,} measures ({pct_of_total:.1f}% of all measures). Local governments frequently ask voters to approve funding for schools, roads, and public services.',
                'category': 'Topics'
            })

        # 3. Topic with highest pass rate
        if qualifying_topics:
            best_topic = max(qualifying_topics.items(),
                           key=lambda x: x[1]['passed'] / x[1]['total'])
            rate = (best_topic[1]['passed'] / best_topic[1]['total']) * 100
            total = best_topic[1]['total']
            questions.append({
                'question': 'Which type of ballot measure is most likely to pass?',
                'answer': f'{best_topic[0]} measures pass at {rate:.1f}% (based on {total} measures). Voters tend to support these measures more than other types.',
                'category': 'Pass Rates'
            })

        # 4. Topic with lowest pass rate
        if qualifying_topics:
            worst_topic = min(qualifying_topics.items(),
                            key=lambda x: x[1]['passed'] / x[1]['total'])
            rate = (worst_topic[1]['passed'] / worst_topic[1]['total']) * 100
            total = worst_topic[1]['total']
            questions.append({
                'question': 'Which type of ballot measure is least likely to pass?',
                'answer': f'{worst_topic[0]} measures pass at only {rate:.1f}% (based on {total} measures). These face more voter skepticism than other measure types.',
                'category': 'Pass Rates'
            })

        # 5. Busiest year
        if year_counts:
            top_year, top_count = year_counts.most_common(1)[0]
            questions.append({
                'question': 'Which year had the most ballot measures in California?',
                'answer': f'{top_year} with {top_count:,} measures. Election years with presidential races tend to have more measures on the ballot as turnout is higher.',
                'category': 'Trends'
            })

        # 6. Busiest decade
        if decade_counts:
            top_decade, decade_count = decade_counts.most_common(1)[0]
            questions.append({
                'question': 'Which decade saw the most ballot measures?',
                'answer': f'The {top_decade}s with {decade_count:,} measures. Direct democracy has become increasingly popular in California over time.',
                'category': 'Trends'
            })

        # 7. County with most measures
        if county_counts:
            top_county, top_count = county_counts.most_common(1)[0]
            second_county, second_count = county_counts.most_common(2)[1] if len(county_counts) > 1 else ('N/A', 0)
            questions.append({
                'question': 'Which county has the most ballot measures?',
                'answer': f'{top_county} County with {top_count:,} measures, followed by {second_county} County ({second_count:,}). Larger counties have more local jurisdictions putting measures on the ballot.',
                'category': 'Geography'
            })

        # 8. Number of counties
        counties = set(m.get('county') for m in measures if m.get('county'))
        questions.append({
            'question': 'How many of California\'s 58 counties are represented?',
            'answer': f'{len(counties)} counties have ballot measures in the database. California\'s direct democracy system is used across the entire state, from rural to urban areas.',
            'category': 'Geography'
        })

        # 9. Average margin of victory
        margins = [abs((m.get('percent_yes') or 50) - 50) for m in measures_with_pct]
        if margins:
            avg_margin = sum(margins) / len(margins)
            close_votes = sum(1 for m in margins if m < 5)
            questions.append({
                'question': 'How competitive are ballot measure elections?',
                'answer': f'The average margin is {avg_margin:.1f} percentage points from 50%. About {close_votes:,} measures ({100*close_votes/len(margins):.1f}%) were decided by less than 5 points - truly competitive races.',
                'category': 'Competitiveness'
            })

        # 10. Close votes count
        if measures_with_pct:
            very_close = [m for m in measures_with_pct if abs((m.get('percent_yes') or 50) - 50) < 2]
            questions.append({
                'question': 'How many ballot measures were decided by less than 2 percentage points?',
                'answer': f'{len(very_close):,} measures were decided by razor-thin margins (less than 2 points). In these cases, every vote truly mattered!',
                'category': 'Competitiveness'
            })

        # 11. Landslide victories
        if measures_with_pct:
            landslides = [m for m in measures_with_pct if m.get('percent_yes', 0) > 80 or m.get('percent_yes', 100) < 20]
            questions.append({
                'question': 'How many ballot measures passed or failed by a landslide (80%+ or 20%-)?',
                'answer': f'{len(landslides):,} measures were decided by overwhelming margins. These tend to be local measures with broad community support or unpopular proposals.',
                'category': 'Competitiveness'
            })

        # 12. Database scope
        year_min = stats.get('year_min', 1998)
        year_max = stats.get('year_max', 2026)
        years_span = int(year_max) - int(year_min) + 1
        questions.append({
            'question': 'How much California ballot measure history is in this database?',
            'answer': f'{len(measures):,} measures spanning {years_span} years ({year_min}-{year_max}). This represents one of the most comprehensive collections of California ballot measure data available.',
            'category': 'Database'
        })

        # 13. Measures with summaries
        with_summaries = sum(1 for m in measures if m.get('summary_text') or m.get('has_summary'))
        pct_summaries = (with_summaries / len(measures)) * 100 if measures else 0
        questions.append({
            'question': 'How many measures have AI-generated summaries?',
            'answer': f'{with_summaries:,} measures ({pct_summaries:.1f}%) have plain-language summaries to help voters understand what they\'re voting on.',
            'category': 'Database'
        })

        # 14. Voter turnout insights
        if measures_with_votes:
            total_votes = sum(m.get('total_votes', 0) for m in measures_with_votes)
            avg_votes = total_votes / len(measures_with_votes)
            questions.append({
                'question': 'How many votes have been cast on California ballot measures?',
                'answer': f'Over {total_votes:,} total votes across {len(measures_with_votes):,} measures with vote data. That\'s an average of {avg_votes:,.0f} votes per measure.',
                'category': 'Turnout'
            })

        # 15. Tax measures insight
        tax_measures = [m for m in measures if 'tax' in (m.get('display_topic') or '').lower() or 'tax' in (m.get('topic_primary') or '').lower()]
        if tax_measures:
            tax_passed = sum(1 for m in tax_measures if m.get('passed'))
            tax_rate = (tax_passed / len(tax_measures)) * 100 if tax_measures else 0
            questions.append({
                'question': 'How do tax-related measures perform at the ballot?',
                'answer': f'Tax measures pass at {tax_rate:.1f}% ({tax_passed:,} of {len(tax_measures):,}). Many require a 2/3 supermajority to pass, making approval more difficult.',
                'category': 'Topics'
            })

        return questions

    def _load_recommendations(self) -> Dict:
        """Load pre-computed recommendations from embedding metadata"""
        recommendations_path = BASE_DIR / "data" / "embedding_metadata.json"
        if recommendations_path.exists():
            try:
                with open(recommendations_path, 'r') as f:
                    metadata = json.load(f)
                    # Return just the neighbors lookup
                    neighbors = metadata.get('neighbors', {})
                    logger.info(f"Loaded recommendations for {len(neighbors)} measures")
                    return neighbors
            except Exception as e:
                logger.warning(f"Could not load recommendations: {e}")
                return {}
        else:
            logger.info("No recommendations file found, skipping related measures")
            return {}

    def _generate_html(self, measures: List[Dict], stats: Dict,
                      topics: List[Dict], recommendations: Dict = None) -> str:
        """Generate the complete HTML with type safety"""
        recommendations = recommendations or {}

        # Ensure all stats are proper types
        stats = self._sanitize_stats(stats)

        # Convert data to JSON for embedding
        measures_json = json.dumps(measures, default=str)
        topics_json = json.dumps(topics, default=str)
        recommendations_json = json.dumps(recommendations, default=str)

        # Generate quiz questions
        quiz_questions = self._generate_quiz_questions(measures, stats)
        quiz_json = json.dumps(quiz_questions, default=str)

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
            <div class="logo" onclick="resetToHome()" style="cursor: pointer;" title="Return to home">
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
    <div class="main-container-full">
        <!-- Main Content Area -->
        <main class="content-full">
            <!-- Site Introduction -->
            <div class="site-intro">
                <h1 class="intro-title">California Ballot Measures Database</h1>
                <p class="intro-text">
                    Explore <strong>{stats['total_measures']:,}+</strong> ballot measures from {stats.get('year_min', 1998)}-{stats.get('year_max', 2026)}.
                    Filter by region, topic, year, or status. Click any measure for details, AI-generated summaries, and related measures.
                </p>
            </div>

            <!-- Hero Section for 2026 Upcoming Measures -->
            <div class="hero-section" id="heroSection">
                <div class="hero-header">
                    <h2 class="hero-title">🗳️ Upcoming 2026 Ballot Measures</h2>
                    <p class="hero-description">
                        Get informed about California's upcoming ballot measures before you vote.
                        <span style="display: block; margin-top: 0.5rem; font-size: 0.85rem; color: var(--text-tertiary);">
                            📋 Full official details will be available as the election approaches.
                        </span>
                    </p>
                </div>
                <div class="hero-grid" id="heroGrid">
                    <!-- Will be populated by JavaScript -->
                </div>
            </div>

            <!-- Filter Accordion -->
            <div class="filter-accordion">
                <div class="accordion-tabs">
                    <button class="accordion-tab" data-panel="region" onclick="toggleAccordion('region')">
                        <span class="tab-icon">🗺️</span>
                        <span class="tab-label">Region</span>
                        <span class="tab-count" id="regionFilterCount"></span>
                        <svg class="tab-chevron" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <polyline points="6 9 12 15 18 9"></polyline>
                        </svg>
                    </button>
                    <button class="accordion-tab" data-panel="topic" onclick="toggleAccordion('topic')">
                        <span class="tab-icon">📑</span>
                        <span class="tab-label">Topic</span>
                        <span class="tab-count" id="topicFilterCount"></span>
                        <svg class="tab-chevron" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <polyline points="6 9 12 15 18 9"></polyline>
                        </svg>
                    </button>
                    <button class="accordion-tab" data-panel="year" onclick="toggleAccordion('year')">
                        <span class="tab-icon">📅</span>
                        <span class="tab-label">Year</span>
                        <span class="tab-count" id="yearFilterCount"></span>
                        <svg class="tab-chevron" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <polyline points="6 9 12 15 18 9"></polyline>
                        </svg>
                    </button>
                    <button class="accordion-tab" data-panel="status" onclick="toggleAccordion('status')">
                        <span class="tab-icon">✓</span>
                        <span class="tab-label">Status</span>
                        <span class="tab-count" id="statusFilterCount"></span>
                        <svg class="tab-chevron" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <polyline points="6 9 12 15 18 9"></polyline>
                        </svg>
                    </button>
                    <button class="clear-filters-btn" onclick="clearAllFilters()">
                        Clear All
                    </button>
                </div>

                <!-- Region Panel -->
                <div class="accordion-panel" id="regionPanel" style="display: none;">
                    <div class="panel-content">
                        <p class="panel-hint">Click to select one or more regions (click again to deselect)</p>
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
                </div>

                <!-- Topic Panel -->
                <div class="accordion-panel" id="topicPanel" style="display: none;">
                    <div class="panel-content">
                        <p class="panel-hint">Click to select one or more topics (click again to deselect)</p>
                        <div class="topic-cards" id="topicCards">
                            <!-- Will be populated by JavaScript -->
                        </div>
                    </div>
                </div>

                <!-- Year Panel -->
                <div class="accordion-panel" id="yearPanel" style="display: none;">
                    <div class="panel-content">
                        <p class="panel-hint">Click to select one or more years (click again to deselect)</p>
                        <div class="decade-groups" id="decadeGroups">
                            <!-- Will be populated by JavaScript -->
                        </div>
                    </div>
                </div>

                <!-- Status Panel -->
                <div class="accordion-panel" id="statusPanel" style="display: none;">
                    <div class="panel-content">
                        <p class="panel-hint">Filter by measure outcome</p>
                        <div class="status-cards" id="statusCards">
                            <div class="status-chip" data-status="passed" onclick="toggleStatusFilter('passed')">
                                <span class="status-chip-icon">✓</span>
                                <span class="status-chip-name">Passed</span>
                                <span class="status-chip-count">({stats['passed']:,})</span>
                            </div>
                            <div class="status-chip" data-status="failed" onclick="toggleStatusFilter('failed')">
                                <span class="status-chip-icon">✗</span>
                                <span class="status-chip-name">Failed</span>
                                <span class="status-chip-count">({stats['failed']:,})</span>
                            </div>
                            <div class="status-chip" data-status="pending" onclick="toggleStatusFilter('pending')">
                                <span class="status-chip-icon">⏳</span>
                                <span class="status-chip-name">Pending/Unknown</span>
                                <span class="status-chip-count">({stats['total_measures'] - stats['passed'] - stats['failed']:,})</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Stats Ribbon -->
            <div class="stats-ribbon" id="statsRibbon">
                <div class="stats-ribbon-inner">
                    <div class="stat-item">
                        <span class="stat-value" id="statTotal">—</span>
                        <span class="stat-label">Measures</span>
                    </div>
                    <div class="stat-divider"></div>
                    <div class="stat-item">
                        <span class="stat-value" id="statPassRate">—</span>
                        <span class="stat-label">Pass Rate</span>
                    </div>
                    <div class="stat-divider"></div>
                    <div class="stat-item">
                        <span class="stat-value" id="statAvgMargin">—</span>
                        <span class="stat-label">Avg. Win Margin</span>
                    </div>
                    <div class="stat-divider"></div>
                    <div class="stat-item">
                        <span class="stat-value" id="statAvgTurnout">—</span>
                        <span class="stat-label">Avg. Turnout</span>
                    </div>
                    <div class="stat-divider"></div>
                    <div class="stat-item">
                        <span class="stat-value" id="statYearRange">—</span>
                        <span class="stat-label">Year Range</span>
                    </div>
                </div>
            </div>

            <!-- Results Header -->
            <div class="results-header">
                <div class="results-info">
                    <span class="results-count" id="resultsCount">0</span>
                    <span class="results-description" id="resultsDescription">measures found</span>
                </div>
                <div class="sort-controls">
                    <label for="sortSelect" class="sort-label">Sort:</label>
                    <select class="sort-select" id="sortSelect" onchange="applySort()">
                        <option value="year-desc">Newest First</option>
                        <option value="year-asc">Oldest First</option>
                        <option value="title">Title A-Z</option>
                        <option value="votes">Most Votes</option>
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

    <!-- Quiz Widget -->
    <div class="quiz-section">
        <div class="quiz-container">
            <div class="quiz-header">
                <span class="quiz-icon">🎯</span>
                <h3 class="quiz-title">Ballot Measure Trivia</h3>
            </div>
            <div class="quiz-card">
                <div class="quiz-category" id="quizCategory"></div>
                <div class="quiz-question" id="quizQuestion">Loading question...</div>
                <div class="quiz-answer" id="quizAnswer" style="display: none;"></div>
                <div class="quiz-actions">
                    <button class="quiz-btn quiz-reveal-btn" id="quizRevealBtn" onclick="revealAnswer()">
                        Reveal Answer
                    </button>
                    <button class="quiz-btn quiz-next-btn" id="quizNextBtn" onclick="nextQuestion()" style="display: none;">
                        Next Question
                    </button>
                </div>
            </div>
            <div class="quiz-progress">
                <span id="quizProgress">Question 1 of 15</span>
            </div>
        </div>
    </div>

    <!-- Footer -->
    <footer class="footer">
        <p>California Ballot Measures Database • Updated {datetime.now().strftime('%B %d, %Y')}</p>
        <p>Data sources: CA Secretary of State, NCSL, ICPSR, CEDA</p>
        <p class="footer-links">
            <a href="#" onclick="openAboutModal(); return false;">About</a> •
            <a href="https://github.com/igorgeyn/cal_vgp" target="_blank">GitHub</a>
        </p>
    </footer>

    <!-- About Modal -->
    <div id="aboutModal" class="modal" style="display: none;" onclick="closeAboutModal(event)">
        <div class="modal-content about-modal" onclick="event.stopPropagation()">
            <button class="modal-close" onclick="closeAboutModal()">&times;</button>
            <h2 class="about-title">About This Project</h2>

            <div class="about-section">
                <p>
                    The California Ballot Measures Database is a tool for exploring over 12,000 ballot measures
                    from across California, spanning local school bonds to statewide propositions.
                </p>
            </div>

            <div class="about-section">
                <h3>Background</h3>
                <p>
                    This project grew out of the <a href="https://sites.google.com/view/ucla-vgp" target="_blank">UCLA Voter Guide Project</a>,
                    a volunteer-driven initiative I started to research and publish ballot measure summaries for California voters
                    in areas with limited local news coverage. While that project focused on writing new summaries with student volunteers,
                    I wanted to build something that could make historical ballot measure data more accessible and explorable.
                </p>
            </div>

            <div class="about-section">
                <h3>Features</h3>
                <ul>
                    <li>Filter by region, topic, year, and outcome</li>
                    <li>AI-generated plain-language summaries</li>
                    <li>Related measures recommendations using semantic similarity</li>
                    <li>Vote results and historical trends</li>
                </ul>
            </div>

            <div class="about-section about-author">
                <h3>Author</h3>
                <p>
                    Built by <a href="https://igorgeyn.com" target="_blank">Igor Geyn</a>, a data scientist and researcher
                    based in the Bay Area. My background is in political economy and causal inference, with a PhD from UCLA.
                </p>
                <p class="about-links">
                    <a href="https://www.linkedin.com/in/igorgeyn/" target="_blank">LinkedIn</a> •
                    <a href="https://github.com/igorgeyn" target="_blank">GitHub</a> •
                    <a href="mailto:igorgeyn@gmail.com">Contact</a>
                </p>
            </div>
        </div>
    </div>

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

    <!-- Measure Detail Modal -->
    <div id="measureDetailModal" class="modal" style="display: none;">
        <div class="modal-content measure-detail-modal">
            <div class="modal-header">
                <div class="measure-detail-header">
                    <span id="modalMeasureId" class="measure-detail-id"></span>
                    <span id="modalYear" class="measure-detail-year"></span>
                </div>
                <button class="modal-close" onclick="closeMeasureDetail()">×</button>
            </div>

            <div class="modal-body">
                <h2 id="modalTitle" class="measure-detail-title"></h2>

                <div id="modalJurisdiction" class="measure-detail-jurisdiction"></div>

                <div class="measure-detail-badges" id="modalBadges"></div>

                <div class="measure-detail-section">
                    <h3>📝 Summary</h3>
                    <p id="modalSummary" class="measure-detail-summary"></p>
                </div>

                <div id="modalResultsSection" class="measure-detail-section" style="display: none;">
                    <h3>📊 Results</h3>
                    <div class="measure-detail-results">
                        <div class="result-bar-container">
                            <div class="result-bar">
                                <div id="modalYesBar" class="result-bar-yes"></div>
                            </div>
                            <div class="result-labels">
                                <span id="modalYesLabel" class="result-yes-label"></span>
                                <span id="modalNoLabel" class="result-no-label"></span>
                            </div>
                        </div>
                        <div id="modalTotalVotes" class="result-total"></div>
                    </div>
                </div>

                <div id="modalBallotQuestion" class="measure-detail-section" style="display: none;">
                    <h3>📜 Ballot Question</h3>
                    <p id="modalBallotText" class="measure-detail-ballot-text"></p>
                </div>

                <div id="modalRelatedSection" class="measure-detail-section" style="display: none;">
                    <h3>🔗 Related Measures</h3>
                    <div id="modalRelatedMeasures" class="measure-detail-related"></div>
                </div>

                <div id="modalLinksSection" class="measure-detail-section">
                    <h3>📎 Links</h3>
                    <div id="modalLinks" class="measure-detail-links"></div>
                </div>
            </div>
        </div>
    </div>

    <script>
        {self._get_javascript(measures_json, topics_json, recommendations_json, stats, quiz_json)}
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
            --accent: #1a73e8;
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

        /* Full-width layout (no sidebar) */
        .main-container-full {
            max-width: 1400px;
            margin: 0 auto;
            padding: 2rem;
        }

        .content-full {
            min-height: 100vh;
        }

        /* Site Introduction */
        .site-intro {
            text-align: center;
            padding: 2rem 1rem;
            margin-bottom: 1.5rem;
        }

        .intro-title {
            font-size: 2rem;
            font-weight: 700;
            color: var(--text-primary);
            margin-bottom: 0.75rem;
        }

        .intro-text {
            font-size: 1.1rem;
            line-height: 1.6;
            color: var(--text-secondary);
            max-width: 700px;
            margin: 0 auto;
        }

        .intro-text strong {
            color: var(--primary);
            font-weight: 600;
        }

        /* Sidebar Filters */
        .sidebar {
            position: sticky;
            top: 80px;
            height: fit-content;
            max-height: calc(100vh - 100px);
            overflow-y: auto;
        }

        /* Status Chips */
        .status-cards {
            display: flex;
            flex-wrap: wrap;
            gap: 0.75rem;
        }

        .status-chip {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.75rem 1rem;
            background: var(--bg-secondary);
            border: 2px solid var(--border);
            border-radius: var(--radius);
            cursor: pointer;
            transition: var(--transition);
            font-size: 0.9rem;
        }

        .status-chip:hover {
            border-color: var(--primary);
            background: var(--bg-tertiary);
        }

        .status-chip.selected {
            background: var(--primary);
            color: white;
            border-color: var(--primary);
        }

        .status-chip[data-status="passed"]:hover,
        .status-chip[data-status="passed"].selected {
            background: var(--success);
            border-color: var(--success);
            color: white;
        }

        .status-chip[data-status="failed"]:hover,
        .status-chip[data-status="failed"].selected {
            background: var(--error);
            border-color: var(--error);
            color: white;
        }

        .status-chip[data-status="pending"]:hover,
        .status-chip[data-status="pending"].selected {
            background: var(--warning);
            border-color: var(--warning);
            color: #1a1a1a;
        }

        .status-chip-icon {
            font-size: 1.1rem;
        }

        .status-chip-name {
            font-weight: 500;
        }

        .status-chip-count {
            opacity: 0.7;
            font-size: 0.85rem;
        }

        /* Clear All Filters Button */
        .clear-filters-btn {
            padding: 0.5rem 1rem;
            background: transparent;
            border: 1px solid var(--border);
            border-radius: var(--radius-sm);
            color: var(--text-secondary);
            font-size: 0.85rem;
            cursor: pointer;
            transition: var(--transition);
            margin-left: auto;
        }

        .clear-filters-btn:hover {
            background: var(--bg-secondary);
            color: var(--error);
            border-color: var(--error);
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

        /* Filter Accordion */
        .filter-accordion {
            margin: 2rem 0;
            padding: 1.5rem 0;
            border-top: 1px solid var(--border-color);
        }

        .accordion-header {
            text-align: center;
            margin-bottom: 1.5rem;
        }

        .accordion-subtitle {
            color: var(--text-secondary);
            font-size: 0.9rem;
            margin-top: 0.25rem;
        }

        .accordion-tabs {
            display: flex;
            gap: 0.75rem;
            justify-content: center;
            flex-wrap: wrap;
            margin-bottom: 1rem;
        }

        .accordion-tab {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.75rem 1.25rem;
            background: var(--bg-primary);
            border: 2px solid var(--border-color);
            border-radius: 12px;
            cursor: pointer;
            transition: all 0.2s ease;
            font-size: 0.95rem;
            color: var(--text-primary);
            font-weight: 500;
        }

        .accordion-tab:hover {
            border-color: var(--primary);
            background: rgba(66, 133, 244, 0.05);
        }

        .accordion-tab.active {
            border-color: var(--primary);
            background: var(--primary);
            color: white;
        }

        .accordion-tab.active .tab-chevron {
            transform: rotate(180deg);
        }

        .accordion-tab.has-selection {
            border-color: var(--accent);
        }

        .accordion-tab.has-selection:not(.active) {
            background: rgba(52, 168, 83, 0.1);
        }

        .tab-icon {
            font-size: 1.1rem;
        }

        .tab-label {
            font-weight: 500;
        }

        .tab-count {
            font-size: 0.8rem;
            background: rgba(0, 0, 0, 0.1);
            padding: 0.125rem 0.5rem;
            border-radius: 10px;
            min-width: 20px;
            text-align: center;
        }

        .accordion-tab.active .tab-count {
            background: rgba(255, 255, 255, 0.2);
        }

        .accordion-tab.has-selection .tab-count {
            background: var(--accent);
            color: white;
        }

        .tab-chevron {
            transition: transform 0.2s ease;
            opacity: 0.6;
        }

        .accordion-panel {
            overflow: hidden;
            transition: all 0.3s ease;
        }

        .panel-content {
            padding: 1.5rem;
            background: var(--bg-secondary);
            border-radius: 12px;
            border: 1px solid var(--border-color);
        }

        .panel-hint {
            text-align: center;
            color: var(--text-secondary);
            font-size: 0.85rem;
            margin-bottom: 1rem;
        }

        /* Regional Navigation (inside accordion) */
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

        /* Topic Navigation */
        .topic-navigation {
            margin: 2rem 0;
            padding: 2rem 0;
            border-top: 1px solid var(--border-color);
        }

        .topic-cards {
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
            justify-content: center;
        }

        .topic-chip {
            display: inline-flex;
            align-items: center;
            gap: 0.4rem;
            padding: 0.5rem 0.875rem;
            background: var(--bg-primary);
            border: 1px solid var(--border-color);
            border-radius: 100px;
            cursor: pointer;
            transition: all 0.2s ease;
            font-size: 0.85rem;
            color: var(--text-primary);
            user-select: none;
        }

        .topic-chip:hover {
            border-color: var(--accent);
            background: rgba(52, 168, 83, 0.05);
        }

        .topic-chip.selected {
            background: var(--accent);
            border-color: var(--accent);
            color: white;
        }

        .topic-chip.selected:hover {
            background: #2e7d32;
            border-color: #2e7d32;
        }

        .topic-chip-icon {
            font-size: 0.95rem;
        }

        .topic-chip-name {
            font-weight: 500;
        }

        .topic-chip-count {
            font-size: 0.75rem;
            opacity: 0.7;
            margin-left: 0.125rem;
        }

        .topic-chip.selected .topic-chip-count {
            opacity: 0.9;
        }

        /* Year Navigation */
        .year-navigation {
            margin: 2rem 0;
            padding: 2rem 0;
            border-top: 1px solid var(--border-color);
        }

        .decade-groups {
            display: flex;
            flex-direction: column;
            gap: 1rem;
        }

        .decade-group {
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            gap: 0.5rem;
        }

        .decade-label {
            font-weight: 600;
            font-size: 0.85rem;
            color: var(--text-secondary);
            min-width: 50px;
        }

        .year-chips {
            display: flex;
            flex-wrap: wrap;
            gap: 0.375rem;
        }

        .year-chip {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            padding: 0.375rem 0.625rem;
            background: var(--bg-primary);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            cursor: pointer;
            transition: all 0.2s ease;
            font-size: 0.8rem;
            color: var(--text-primary);
            user-select: none;
            min-width: 50px;
        }

        .year-chip:hover {
            border-color: var(--warning);
            background: rgba(251, 188, 4, 0.1);
        }

        .year-chip.selected {
            background: var(--warning);
            border-color: var(--warning);
            color: #333;
            font-weight: 600;
        }

        .year-chip.selected:hover {
            background: #e6a800;
            border-color: #e6a800;
        }

        .year-chip-count {
            font-size: 0.7rem;
            opacity: 0.6;
            margin-left: 0.25rem;
        }

        .year-chip.selected .year-chip-count {
            opacity: 0.8;
        }

        /* Stats Ribbon */
        .stats-ribbon {
            background: linear-gradient(135deg, var(--bg-secondary) 0%, var(--bg-primary) 100%);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 1rem 1.5rem;
            margin-bottom: 1.5rem;
            box-shadow: var(--shadow-sm);
        }

        .stats-ribbon-inner {
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 1.5rem;
            flex-wrap: wrap;
        }

        .stat-item {
            display: flex;
            flex-direction: column;
            align-items: center;
            min-width: 80px;
        }

        .stat-value {
            font-size: 1.5rem;
            font-weight: 700;
            color: var(--primary);
            line-height: 1.2;
        }

        .stat-label {
            font-size: 0.75rem;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-top: 0.25rem;
        }

        .stat-divider {
            width: 1px;
            height: 40px;
            background: var(--border-color);
        }

        @media (max-width: 768px) {
            .stats-ribbon-inner {
                gap: 1rem;
            }

            .stat-item {
                min-width: 60px;
            }

            .stat-value {
                font-size: 1.25rem;
            }

            .stat-label {
                font-size: 0.65rem;
            }

            .stat-divider {
                display: none;
            }
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
            align-items: center;
            justify-content: space-between;
            margin-bottom: 0.75rem;
        }

        .card-year {
            font-size: 0.9rem;
            font-weight: 600;
            color: var(--text-secondary);
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

        .badge-neutral {
            background: var(--bg-secondary);
            color: var(--text-secondary);
            border: 1px solid var(--border-light);
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
            font-size: 0.8rem;
            color: var(--text-tertiary);
            margin-top: 0.75rem;
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

        .footer-links {
            margin-top: 0.75rem !important;
        }

        .footer-links a {
            color: var(--primary);
            text-decoration: none;
        }

        .footer-links a:hover {
            text-decoration: underline;
        }

        /* About Modal */
        .about-modal {
            max-width: 600px;
            padding: 2rem;
        }

        .about-title {
            font-size: 1.5rem;
            font-weight: 700;
            color: var(--text-primary);
            margin-bottom: 1.5rem;
        }

        .about-section {
            margin-bottom: 1.5rem;
        }

        .about-section h3 {
            font-size: 1rem;
            font-weight: 600;
            color: var(--text-primary);
            margin-bottom: 0.5rem;
        }

        .about-section p {
            color: var(--text-secondary);
            line-height: 1.6;
            margin-bottom: 0.5rem;
        }

        .about-section ul {
            color: var(--text-secondary);
            margin: 0;
            padding-left: 1.25rem;
        }

        .about-section li {
            margin-bottom: 0.25rem;
        }

        .about-section a {
            color: var(--primary);
            text-decoration: none;
        }

        .about-section a:hover {
            text-decoration: underline;
        }

        .about-author {
            padding-top: 1rem;
            border-top: 1px solid var(--border);
        }

        .about-links {
            margin-top: 0.75rem;
        }

        .about-links a {
            color: var(--primary);
            text-decoration: none;
        }

        .about-links a:hover {
            text-decoration: underline;
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

        .measure-card.landmark {
            border-left: 4px solid #f59e0b;
            background: linear-gradient(135deg, var(--bg-primary) 0%, rgba(245, 158, 11, 0.05) 100%);
        }

        .measure-card.landmark .card-meta {
            color: #b45309;
        }

        /* Pending/Upcoming Measures (2026+) */
        .measure-card.pending-measure {
            border-left: 4px solid #8b5cf6;
            background: linear-gradient(135deg, var(--bg-primary) 0%, rgba(139, 92, 246, 0.05) 100%);
        }

        .measure-card.pending-measure .card-summary {
            font-style: italic;
            color: var(--text-secondary);
        }

        /* Pending measure placeholder text */
        .pending-info-text {
            font-size: 0.85rem;
            color: var(--text-secondary);
            font-style: italic;
            padding: 0.75rem 1rem;
            background: rgba(139, 92, 246, 0.08);
            border-radius: 8px;
            margin-top: 0.5rem;
            border-left: 3px solid #8b5cf6;
        }

        .pending-disclaimer {
            font-size: 0.8rem;
            color: var(--text-tertiary);
            padding: 1rem;
            background: rgba(139, 92, 246, 0.05);
            border-radius: 8px;
            margin-top: 1rem;
            text-align: center;
        }

        .pending-disclaimer strong {
            color: #7c3aed;
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

            .main-container,
            .main-container-full {
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

            .status-cards {
                flex-direction: column;
            }

            .status-chip {
                width: 100%;
                justify-content: center;
            }

            .accordion-tabs {
                flex-wrap: wrap;
            }

            .clear-filters-btn {
                width: 100%;
                margin-top: 0.5rem;
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

        /* Measure Detail Modal */
        .measure-detail-modal {
            max-width: 680px;
            width: 100%;
        }

        .measure-detail-header {
            display: flex;
            align-items: center;
            gap: 1rem;
        }

        .measure-detail-id {
            font-size: 1.25rem;
            font-weight: 700;
            color: var(--primary);
        }

        .measure-detail-year {
            font-size: 1rem;
            color: var(--text-secondary);
            background: var(--bg-secondary);
            padding: 0.25rem 0.75rem;
            border-radius: 100px;
        }

        .measure-detail-title {
            font-size: 1.35rem;
            font-weight: 600;
            margin: 0 0 0.75rem 0;
            color: var(--text-primary);
            line-height: 1.4;
        }

        .measure-detail-jurisdiction {
            font-size: 0.95rem;
            color: var(--text-secondary);
            margin-bottom: 1rem;
        }

        .measure-detail-badges {
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
            margin-bottom: 1.5rem;
        }

        .measure-detail-badges .badge {
            font-size: 0.875rem;
            padding: 0.4rem 0.75rem;
        }

        .measure-detail-section {
            margin-bottom: 1.5rem;
            padding-bottom: 1.5rem;
            border-bottom: 1px solid var(--border-light);
        }

        .measure-detail-section:last-child {
            margin-bottom: 0;
            padding-bottom: 0;
            border-bottom: none;
        }

        .measure-detail-section h3 {
            font-size: 0.95rem;
            font-weight: 600;
            color: var(--text-secondary);
            margin: 0 0 0.75rem 0;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .measure-detail-summary {
            font-size: 1rem;
            line-height: 1.7;
            color: var(--text-primary);
            margin: 0;
        }

        .measure-detail-results {
            background: var(--bg-secondary);
            border-radius: 8px;
            padding: 1rem;
        }

        .result-bar-container {
            margin-bottom: 0.75rem;
        }

        .result-bar {
            height: 32px;
            background: var(--danger);
            border-radius: 6px;
            overflow: hidden;
        }

        .result-bar-yes {
            height: 100%;
            background: var(--success);
            transition: width 0.5s ease;
        }

        .result-labels {
            display: flex;
            justify-content: space-between;
            margin-top: 0.5rem;
            font-size: 0.95rem;
        }

        .result-yes-label {
            color: var(--success);
            font-weight: 600;
        }

        .result-no-label {
            color: var(--danger);
            font-weight: 600;
        }

        .result-total {
            text-align: center;
            font-size: 0.875rem;
            color: var(--text-secondary);
        }

        .measure-detail-ballot-text {
            font-size: 0.95rem;
            line-height: 1.6;
            color: var(--text-primary);
            background: var(--bg-secondary);
            padding: 1rem;
            border-radius: 8px;
            border-left: 3px solid var(--primary);
            margin: 0;
        }

        .measure-detail-related {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 0.75rem;
        }

        .related-card {
            background: var(--bg-secondary);
            border: 1px solid var(--border-light);
            border-radius: 8px;
            padding: 0.75rem;
            cursor: pointer;
            transition: var(--transition);
        }

        .related-card:hover {
            border-color: var(--primary);
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
        }

        .related-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0.5rem;
        }

        .related-id {
            font-weight: 600;
            font-size: 0.8rem;
            color: var(--primary);
        }

        .related-year {
            font-size: 0.75rem;
            color: var(--text-tertiary);
            background: var(--bg-tertiary);
            padding: 0.125rem 0.375rem;
            border-radius: 4px;
        }

        .related-title {
            font-size: 0.85rem;
            color: var(--text-primary);
            margin-bottom: 0.5rem;
            line-height: 1.3;
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }

        .related-meta {
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 0.75rem;
        }

        .badge-small {
            font-size: 0.7rem;
            padding: 0.125rem 0.375rem;
        }

        .similarity-score {
            color: var(--text-tertiary);
            font-size: 0.7rem;
        }

        .measure-detail-links {
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
        }

        .measure-detail-links a {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            color: var(--primary);
            text-decoration: none;
            font-size: 0.95rem;
            padding: 0.5rem;
            border-radius: 6px;
            transition: var(--transition);
        }

        .measure-detail-links a:hover {
            background: var(--bg-secondary);
        }

        .measure-detail-links a.link-high-confidence {
            font-weight: 500;
        }

        .measure-detail-links a.link-medium-confidence {
            opacity: 0.9;
        }

        .measure-detail-links a.link-low-confidence {
            opacity: 0.75;
            font-size: 0.9rem;
        }

        .measure-detail-links a.link-low-confidence::after {
            content: ' (search)';
            font-size: 0.8rem;
            color: var(--text-tertiary);
        }

        .no-summary-text {
            color: var(--text-tertiary);
            font-style: italic;
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

        /* =============================================================================
           Quiz Widget
           ============================================================================= */
        .quiz-section {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 3rem 2rem;
            margin-top: 2rem;
        }

        .quiz-container {
            max-width: 600px;
            margin: 0 auto;
        }

        .quiz-header {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 0.75rem;
            margin-bottom: 1.5rem;
        }

        .quiz-icon {
            font-size: 2rem;
        }

        .quiz-title {
            color: white;
            font-size: 1.5rem;
            font-weight: 600;
            margin: 0;
        }

        .quiz-card {
            background: white;
            border-radius: 16px;
            padding: 2rem;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
        }

        .quiz-category {
            display: inline-block;
            background: var(--bg-tertiary);
            color: var(--text-secondary);
            padding: 0.25rem 0.75rem;
            border-radius: 100px;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 1rem;
        }

        .quiz-question {
            font-size: 1.25rem;
            font-weight: 500;
            color: var(--text-primary);
            line-height: 1.5;
            margin-bottom: 1.5rem;
        }

        .quiz-answer {
            background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%);
            border: 2px solid #86efac;
            border-radius: 12px;
            padding: 1.25rem;
            margin-bottom: 1.5rem;
            animation: fadeIn 0.3s ease;
        }

        .quiz-answer p {
            margin: 0;
            color: #166534;
            font-size: 1.1rem;
            font-weight: 500;
            line-height: 1.5;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(-10px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .quiz-actions {
            display: flex;
            gap: 1rem;
            justify-content: center;
        }

        .quiz-btn {
            padding: 0.875rem 2rem;
            border: none;
            border-radius: 100px;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
        }

        .quiz-reveal-btn {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }

        .quiz-reveal-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
        }

        .quiz-next-btn {
            background: var(--bg-secondary);
            color: var(--text-primary);
            border: 2px solid var(--border);
        }

        .quiz-next-btn:hover {
            background: var(--bg-tertiary);
            border-color: var(--primary);
            color: var(--primary);
        }

        .quiz-progress {
            text-align: center;
            margin-top: 1.5rem;
            color: rgba(255, 255, 255, 0.8);
            font-size: 0.875rem;
        }

        /* Mobile responsiveness for quiz */
        @media (max-width: 768px) {
            .quiz-section {
                padding: 2rem 1rem;
            }

            .quiz-card {
                padding: 1.5rem;
            }

            .quiz-question {
                font-size: 1.1rem;
            }

            .quiz-actions {
                flex-direction: column;
            }

            .quiz-btn {
                width: 100%;
            }
        }
        """

    def _get_javascript(self, measures_json: str, topics_json: str,
                       recommendations_json: str, stats: Dict, quiz_json: str = "[]") -> str:
        """Get JavaScript code for the website"""
        return f"""
        // Data
        const allMeasures = {measures_json};
        const topics = {topics_json};
        const recommendations = {recommendations_json};
        const quizQuestions = {quiz_json};

        // Utility function to detect AI refusal patterns in summaries
        function isAiRefusal(text) {{
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
        }}

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
            selectedYears: [],
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
            populateTopicNavigation();
            populateYearNavigation();
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

            // Update filter count badges
            updateFilterCountBadges();

            // Apply filters
            applyFilters();
        }}

        function filterByCounty(county) {{
            // Clear region selections when selecting county
            currentFilters.regions = [];
            document.querySelectorAll('.region-chip.selected').forEach(chip => {{
                chip.classList.remove('selected');
            }});

            // Update filter count badges
            updateFilterCountBadges();

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

        // Accordion toggle functionality
        let activeAccordionPanel = null;

        function toggleAccordion(panelName) {{
            const panel = document.getElementById(panelName + 'Panel');
            const tab = document.querySelector(`.accordion-tab[data-panel="${{panelName}}"]`);
            const allPanels = document.querySelectorAll('.accordion-panel');
            const allTabs = document.querySelectorAll('.accordion-tab');

            // If clicking the already active panel, close it
            if (activeAccordionPanel === panelName) {{
                panel.style.display = 'none';
                tab.classList.remove('active');
                activeAccordionPanel = null;
                return;
            }}

            // Close all panels and deactivate all tabs
            allPanels.forEach(p => p.style.display = 'none');
            allTabs.forEach(t => t.classList.remove('active'));

            // Open the selected panel
            panel.style.display = 'block';
            tab.classList.add('active');
            activeAccordionPanel = panelName;
        }}

        // Update filter count badges
        function updateFilterCountBadges() {{
            // Region count
            const regionCount = (currentFilters.regions?.length || 0) + (currentFilters.county ? 1 : 0);
            const regionBadge = document.getElementById('regionFilterCount');
            if (regionBadge) {{
                regionBadge.textContent = regionCount > 0 ? regionCount : '';
                const regionTab = document.querySelector('.accordion-tab[data-panel="region"]');
                if (regionCount > 0) {{
                    regionTab.classList.add('has-selection');
                }} else {{
                    regionTab.classList.remove('has-selection');
                }}
            }}

            // Topic count
            const topicCount = currentFilters.topics?.length || 0;
            const topicBadge = document.getElementById('topicFilterCount');
            if (topicBadge) {{
                topicBadge.textContent = topicCount > 0 ? topicCount : '';
                const topicTab = document.querySelector('.accordion-tab[data-panel="topic"]');
                if (topicCount > 0) {{
                    topicTab.classList.add('has-selection');
                }} else {{
                    topicTab.classList.remove('has-selection');
                }}
            }}

            // Year count
            const yearCount = currentFilters.selectedYears?.length || 0;
            const yearBadge = document.getElementById('yearFilterCount');
            if (yearBadge) {{
                yearBadge.textContent = yearCount > 0 ? yearCount : '';
                const yearTab = document.querySelector('.accordion-tab[data-panel="year"]');
                if (yearCount > 0) {{
                    yearTab.classList.add('has-selection');
                }} else {{
                    yearTab.classList.remove('has-selection');
                }}
            }}

            // Status count
            const statusCount = currentFilters.status?.length || 0;
            const statusBadge = document.getElementById('statusFilterCount');
            if (statusBadge) {{
                statusBadge.textContent = statusCount > 0 ? statusCount : '';
                const statusTab = document.querySelector('.accordion-tab[data-panel="status"]');
                if (statusCount > 0) {{
                    statusTab.classList.add('has-selection');
                }} else {{
                    statusTab.classList.remove('has-selection');
                }}
            }}
        }}

        // Topic icons for consolidated display categories
        const TOPIC_ICONS = {{
            "Education": "🎓",
            "Public Safety & Crime": "🚔",
            "Taxes & Finance": "💰",
            "Government & Elections": "🗳️",
            "Healthcare & Welfare": "🏥",
            "Environment & Natural Resources": "🌲",
            "Transportation": "🚗",
            "Housing & Land Use": "🏠",
            "Business & Labor": "💼",
            "Utilities & Energy": "💡",
            "Civil Rights": "⚖️",
            "Other": "📋"
        }};

        // Populate topic navigation (uses consolidated display_topic for cleaner dropdown)
        function populateTopicNavigation() {{
            const container = document.getElementById('topicCards');

            // Count measures by display topic (consolidated categories)
            const topicCounts = {{}};
            allMeasures.forEach(m => {{
                const topic = m.display_topic;  // Use consolidated display topic
                if (topic) {{
                    topicCounts[topic] = (topicCounts[topic] || 0) + 1;
                }}
            }});

            // Sort by count
            const sortedTopics = Object.entries(topicCounts)
                .sort((a, b) => b[1] - a[1]);

            container.innerHTML = sortedTopics.map(([topic, count]) => {{
                const icon = TOPIC_ICONS[topic] || "📌";
                const escapedTopic = topic.replace(/'/g, "\\\\'");
                return `
                    <div class="topic-chip" data-topic="${{escapedTopic}}" onclick="toggleTopicFilter('${{escapedTopic}}')">
                        <span class="topic-chip-icon">${{icon}}</span>
                        <span class="topic-chip-name">${{topic}}</span>
                        <span class="topic-chip-count">(${{count}})</span>
                    </div>
                `;
            }}).join('');
        }}

        // Toggle topic filter
        function toggleTopicFilter(topic) {{
            const index = currentFilters.topics.indexOf(topic);
            if (index === -1) {{
                currentFilters.topics.push(topic);
            }} else {{
                currentFilters.topics.splice(index, 1);
            }}
            updateTopicChipUI();
            updateFilterCountBadges();
            pagination.currentPage = 1;
            applyFilters();
        }}

        // Update topic chip visual state
        function updateTopicChipUI() {{
            document.querySelectorAll('.topic-chip').forEach(chip => {{
                const topic = chip.dataset.topic;
                if (currentFilters.topics.includes(topic)) {{
                    chip.classList.add('selected');
                }} else {{
                    chip.classList.remove('selected');
                }}
            }});
        }}

        // Populate year navigation
        function populateYearNavigation() {{
            const container = document.getElementById('decadeGroups');

            // Count measures by year
            const yearCounts = {{}};
            allMeasures.forEach(m => {{
                const year = parseInt(m.year);
                if (year) {{
                    yearCounts[year] = (yearCounts[year] || 0) + 1;
                }}
            }});

            // Get all years and group by decade
            const years = Object.keys(yearCounts).map(y => parseInt(y)).sort((a, b) => b - a);
            const decades = {{}};

            years.forEach(year => {{
                const decade = Math.floor(year / 10) * 10;
                if (!decades[decade]) {{
                    decades[decade] = [];
                }}
                decades[decade].push(year);
            }});

            // Sort decades descending
            const sortedDecades = Object.keys(decades).map(d => parseInt(d)).sort((a, b) => b - a);

            container.innerHTML = sortedDecades.map(decade => {{
                const decadeYears = decades[decade].sort((a, b) => b - a);
                return `
                    <div class="decade-group">
                        <span class="decade-label">${{decade}}s</span>
                        <div class="year-chips">
                            ${{decadeYears.map(year => `
                                <div class="year-chip" data-year="${{year}}" onclick="toggleYearFilter(${{year}})">
                                    ${{year}}
                                    <span class="year-chip-count">(${{yearCounts[year]}})</span>
                                </div>
                            `).join('')}}
                        </div>
                    </div>
                `;
            }}).join('');
        }}

        // Toggle year filter
        function toggleYearFilter(year) {{
            const index = currentFilters.selectedYears.indexOf(year);
            if (index === -1) {{
                currentFilters.selectedYears.push(year);
            }} else {{
                currentFilters.selectedYears.splice(index, 1);
            }}
            updateYearChipUI();
            updateFilterCountBadges();
            pagination.currentPage = 1;
            applyFilters();
        }}

        // Update year chip visual state
        function updateYearChipUI() {{
            document.querySelectorAll('.year-chip').forEach(chip => {{
                const year = parseInt(chip.dataset.year);
                if (currentFilters.selectedYears.includes(year)) {{
                    chip.classList.add('selected');
                }} else {{
                    chip.classList.remove('selected');
                }}
            }});
        }}

        // Toggle status filter
        function toggleStatusFilter(status) {{
            const index = currentFilters.status.indexOf(status);
            if (index === -1) {{
                currentFilters.status.push(status);
            }} else {{
                currentFilters.status.splice(index, 1);
            }}
            updateStatusChipUI();
            updateFilterCountBadges();
            pagination.currentPage = 1;
            applyFilters();
        }}

        // Update status chip visual state
        function updateStatusChipUI() {{
            document.querySelectorAll('.status-chip').forEach(chip => {{
                const status = chip.dataset.status;
                if (currentFilters.status.includes(status)) {{
                    chip.classList.add('selected');
                }} else {{
                    chip.classList.remove('selected');
                }}
            }});
        }}

        // Load page number from URL hash
        function loadPageFromURL() {{
            const hash = window.location.hash;
            const match = hash.match(/page=(\d+)/);
            if (match) {{
                pagination.currentPage = Math.max(1, parseInt(match[1]));
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
                // Year range filter (from sidebar)
                const year = parseInt(measure.year);
                if (!isNaN(year)) {{
                    if (year < currentFilters.yearMin || year > currentFilters.yearMax) {{
                        return false;
                    }}
                }}

                // Selected years filter (from year chips)
                if (currentFilters.selectedYears.length > 0) {{
                    if (!currentFilters.selectedYears.includes(year)) {{
                        return false;
                    }}
                }}

                // Status filter
                if (currentFilters.status.length > 0) {{
                    const passed = measure.passed;
                    let matchesStatus = false;

                    if (currentFilters.status.includes('passed') && passed === 1) {{
                        matchesStatus = true;
                    }}
                    if (currentFilters.status.includes('failed') && passed === 0) {{
                        matchesStatus = true;
                    }}
                    if (currentFilters.status.includes('pending') && passed !== 1 && passed !== 0) {{
                        matchesStatus = true;
                    }}

                    if (!matchesStatus) {{
                        return false;
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
                
                // Topic filter (uses consolidated display_topic)
                if (currentFilters.topics.length > 0) {{
                    const measureTopic = measure.display_topic || '';
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

            // Update stats ribbon
            updateStatsRibbon();

            // Update UI
            updateResults();
        }}

        // Update stats ribbon with filtered data
        function updateStatsRibbon() {{
            const measures = filteredMeasures;
            const total = measures.length;

            // Calculate pass rate
            const withVotes = measures.filter(m => m.passed === 1 || m.passed === 0);
            const passed = measures.filter(m => m.passed === 1).length;
            const passRate = withVotes.length > 0 ? (passed / withVotes.length * 100).toFixed(1) : null;

            // Calculate average win margin (absolute difference from 50%)
            const margins = measures
                .filter(m => m.percent_yes != null && m.percent_yes > 0)
                .map(m => Math.abs(m.percent_yes - 50));
            const avgMargin = margins.length > 0
                ? (margins.reduce((a, b) => a + b, 0) / margins.length).toFixed(1)
                : null;

            // Calculate average turnout (total votes)
            const turnouts = measures
                .filter(m => m.total_votes != null && m.total_votes > 0)
                .map(m => m.total_votes);
            const avgTurnout = turnouts.length > 0
                ? Math.round(turnouts.reduce((a, b) => a + b, 0) / turnouts.length)
                : null;

            // Get year range
            const years = measures
                .filter(m => m.year != null)
                .map(m => parseInt(m.year))
                .filter(y => !isNaN(y));
            const minYear = years.length > 0 ? Math.min(...years) : null;
            const maxYear = years.length > 0 ? Math.max(...years) : null;
            const yearRange = minYear && maxYear
                ? (minYear === maxYear ? `${{minYear}}` : `${{minYear}}-${{maxYear}}`)
                : null;

            // Format turnout with K/M suffix
            function formatNumber(num) {{
                if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
                if (num >= 1000) return (num / 1000).toFixed(0) + 'K';
                return num.toLocaleString();
            }}

            // Update DOM
            document.getElementById('statTotal').textContent = total.toLocaleString();
            document.getElementById('statPassRate').textContent = passRate ? `${{passRate}}%` : '—';
            document.getElementById('statAvgMargin').textContent = avgMargin ? `${{avgMargin}}%` : '—';
            document.getElementById('statAvgTurnout').textContent = avgTurnout ? formatNumber(avgTurnout) : '—';
            document.getElementById('statYearRange').textContent = yearRange || '—';
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
            
            // Determine if we should show hero section (only on "home" view with no filters)
            const heroSection = document.getElementById('heroSection');
            const isHomeView = !currentFilters.search &&
                currentFilters.status.length === 0 &&
                currentFilters.features.length === 0 &&
                currentFilters.topics.length === 0 &&
                currentFilters.selectedYears.length === 0 &&
                (!currentFilters.regions || currentFilters.regions.length === 0) &&
                !currentFilters.county &&
                pagination.currentPage === 1;

            if (isHomeView && heroMeasures.length > 0) {{
                heroSection.style.display = 'block';
                displayHero();
            }} else {{
                heroSection.style.display = 'none';
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
        
        // Check if measure is pending (2026 or later, no vote data)
        function isPendingMeasure(measure) {{
            const year = parseInt(measure.year);
            return year >= 2026 || (measure.passed !== 1 && measure.passed !== 0 && !measure.percent_yes);
        }}

        // Create card HTML - simplified, cleaner design
        function createCard(measure, featured = false, featuredReason = null, isHero = false) {{
            // Use generated title if available, otherwise fall back to original
            const title = measure.generated_title || measure.title || measure.measure_text || 'Untitled Measure';
            const measureId = measure.measure_id || '';
            const displayTitle = measureId ? `${{measureId}}: ${{title}}` : title;
            const year = measure.year || 'Unknown';
            const passed = measure.passed;
            const isPending = isPendingMeasure(measure);

            // Pending measures get special status display
            const passedClass = isPending ? 'pending' : (passed === 1 ? 'passed' : passed === 0 ? 'failed' : 'pending');
            const passedText = isPending ? '⏳ Upcoming' : (passed === 1 ? '✓ Passed' : passed === 0 ? '✗ Failed' : '• Pending');

            // Get summary/description - prioritize summary fields
            let summary = '';

            // Priority order: summary_text > ballot_question > description > original_title
            // Skip AI refusals (using global isAiRefusal function)
            if (measure.summary_text && measure.summary_text.length > 50 && !isAiRefusal(measure.summary_text)) {{
                summary = measure.summary_text;
            }} else if (measure.ballot_question && measure.ballot_question.length > 50) {{
                summary = measure.ballot_question;
            }} else if (measure.description) {{
                summary = measure.description;
            }} else if (measure.generated_title && measure.original_title) {{
                summary = measure.original_title;
            }}

            // For pending measures without content, show helpful placeholder
            if (isPending && !summary) {{
                summary = 'Full measure details will be available closer to the election. Check back for official language, fiscal analysis, and voter guide information.';
            }}

            // Truncate summary for card preview (full text available in modal)
            const maxLength = 200;
            const truncatedSummary = summary.length > maxLength ? summary.substring(0, maxLength) + '...' : summary;

            const descriptionHtml = truncatedSummary ? `
                <div class="card-summary">${{truncatedSummary}}</div>
            ` : '';

            // Hide vote bar for pending measures (no vote data yet)
            const percentYes = measure.percent_yes;
            const voteBar = (percentYes != null && !isPending) ? `
                <div class="vote-bar">
                    <div class="vote-bar-fill" style="width: ${{Math.round(percentYes)}}%"></div>
                </div>
            ` : '';

            const topic = measure.topic_primary || measure.category_topic || '';
            const source = measure.data_source || measure.source || '';

            // Determine card class - add pending-measure class for 2026+ measures
            let cardClass = isHero ? 'hero' : (featured ? 'featured' : '');
            if (measure.is_landmark) cardClass += ' landmark';
            if (isPending) cardClass += ' pending-measure';

            // Build meta items - only show what's available, cleaner format
            const metaItems = [];
            if (measure.is_landmark) metaItems.push('⭐ Historic');
            if (percentYes != null && !isPending) metaItems.push(`${{Math.round(percentYes)}}% Yes`);
            if (topic) metaItems.push(topic);
            if (source) metaItems.push(source);
            if (isPending && !metaItems.length) metaItems.push('Election pending');

            return `
                <div class="measure-card ${{cardClass}}" onclick="viewMeasure(${{JSON.stringify(measure).replace(/"/g, '&quot;')}})">
                    <div class="card-header">
                        <span class="card-year">${{year}}</span>
                        <span class="badge badge-${{passedClass}}">${{passedText}}</span>
                    </div>
                    <h3 class="card-title">${{displayTitle}}</h3>
                    ${{descriptionHtml}}
                    ${{voteBar}}
                    <div class="card-meta">${{metaItems.join(' · ')}}</div>
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
        
        // View measure details in modal
        function viewMeasure(measure) {{
            const modal = document.getElementById('measureDetailModal');
            const isPending = isPendingMeasure(measure);

            // Populate header
            document.getElementById('modalMeasureId').textContent = measure.measure_id || '';
            document.getElementById('modalYear').textContent = measure.year || '';

            // Title
            const title = measure.generated_title || measure.title || measure.measure_text || 'Untitled Measure';
            document.getElementById('modalTitle').textContent = title;

            // Jurisdiction
            const jurisdiction = [];
            if (measure.jurisdiction) jurisdiction.push(measure.jurisdiction);
            if (measure.county && measure.county !== 'Statewide') jurisdiction.push(measure.county + ' County');
            else if (measure.county === 'Statewide') jurisdiction.push('California Statewide');
            document.getElementById('modalJurisdiction').textContent = jurisdiction.join(' • ') || 'California';

            // Badges - special handling for pending measures
            const badgesHtml = [];
            const passed = measure.passed;

            if (isPending) {{
                badgesHtml.push(`<span class="badge badge-pending">⏳ Upcoming Election</span>`);
            }} else {{
                const passedClass = passed === 1 ? 'passed' : passed === 0 ? 'failed' : 'pending';
                const passedText = passed === 1 ? '✓ Passed' : passed === 0 ? '✗ Failed' : '• Unknown';
                badgesHtml.push(`<span class="badge badge-${{passedClass}}">${{passedText}}</span>`);
            }}

            if (measure.percent_yes != null && !isPending) {{
                badgesHtml.push(`<span class="badge badge-neutral">📊 ${{Math.round(measure.percent_yes)}}% Yes</span>`);
            }}
            if (measure.category_type) {{
                badgesHtml.push(`<span class="badge badge-neutral">${{measure.category_type}}</span>`);
            }}
            if (measure.category_topic) {{
                badgesHtml.push(`<span class="badge badge-neutral">${{measure.category_topic}}</span>`);
            }}
            document.getElementById('modalBadges').innerHTML = badgesHtml.join('');

            // Summary - with pending-specific messaging
            const summaryEl = document.getElementById('modalSummary');
            if (measure.summary_text && !isAiRefusal(measure.summary_text)) {{
                summaryEl.innerHTML = measure.summary_text;
                summaryEl.classList.remove('no-summary-text');
            }} else if (measure.description) {{
                summaryEl.innerHTML = measure.description;
                summaryEl.classList.remove('no-summary-text');
            }} else if (isPending) {{
                // Helpful message for pending measures without content
                summaryEl.innerHTML = `
                    <div class="pending-info-text">
                        <strong>📋 Coming Soon:</strong> Full measure details, including the official ballot language,
                        fiscal impact analysis, and arguments for and against, will be available as we approach the election.
                    </div>
                `;
                summaryEl.classList.remove('no-summary-text');
            }} else {{
                summaryEl.textContent = 'No summary available for this measure.';
                summaryEl.classList.add('no-summary-text');
            }}

            // Results section - hide for pending measures
            const resultsSection = document.getElementById('modalResultsSection');
            if (measure.percent_yes != null && measure.yes_votes != null && !isPending) {{
                resultsSection.style.display = 'block';
                document.getElementById('modalYesBar').style.width = measure.percent_yes + '%';
                document.getElementById('modalYesLabel').textContent = `Yes: ${{measure.yes_votes?.toLocaleString() || 0}} (${{measure.percent_yes?.toFixed(1) || 0}}%)`;
                document.getElementById('modalNoLabel').textContent = `No: ${{measure.no_votes?.toLocaleString() || 0}} (${{measure.percent_no?.toFixed(1) || 0}}%)`;
                document.getElementById('modalTotalVotes').textContent = `Total votes: ${{measure.total_votes?.toLocaleString() || 0}}`;
            }} else {{
                resultsSection.style.display = 'none';
            }}

            // Ballot question section
            const ballotSection = document.getElementById('modalBallotQuestion');
            if (measure.ballot_question && measure.ballot_question.length > 20) {{
                ballotSection.style.display = 'block';
                document.getElementById('modalBallotText').textContent = measure.ballot_question;
            }} else {{
                ballotSection.style.display = 'none';
            }}

            // Related measures section - populated from recommendations
            const relatedSection = document.getElementById('modalRelatedSection');
            const relatedContainer = document.getElementById('modalRelatedMeasures');
            const measureRecs = recommendations[measure.measure_id];

            if (measureRecs && measureRecs.length > 0) {{
                // Build related measures cards
                const relatedHtml = measureRecs.slice(0, 4).map(rec => {{
                    const relatedMeasure = allMeasures.find(m => m.measure_id === rec.measure_id);
                    if (!relatedMeasure) return '';

                    const title = relatedMeasure.generated_title || relatedMeasure.title || relatedMeasure.measure_text || 'Unknown';
                    const shortTitle = title.length > 60 ? title.substring(0, 57) + '...' : title;
                    const similarity = Math.round(rec.score * 100);
                    const passedClass = relatedMeasure.passed === 1 ? 'passed' : relatedMeasure.passed === 0 ? 'failed' : 'pending';
                    const passedIcon = relatedMeasure.passed === 1 ? '✓' : relatedMeasure.passed === 0 ? '✗' : '•';

                    return `
                        <div class="related-card" onclick="viewMeasure(allMeasures.find(m => m.measure_id === '${{rec.measure_id}}'))">
                            <div class="related-header">
                                <span class="related-id">${{relatedMeasure.measure_id}}</span>
                                <span class="related-year">${{relatedMeasure.year}}</span>
                            </div>
                            <div class="related-title">${{shortTitle}}</div>
                            <div class="related-meta">
                                <span class="badge badge-${{passedClass}} badge-small">${{passedIcon}}</span>
                                <span class="similarity-score">${{similarity}}% similar</span>
                            </div>
                        </div>
                    `;
                }}).join('');

                relatedContainer.innerHTML = relatedHtml;
                relatedSection.style.display = 'block';
            }} else {{
                relatedSection.style.display = 'none';
            }}

            // Links section
            const linksContainer = document.getElementById('modalLinks');
            const links = [];

            // Add generated external links first (higher quality)
            if (measure.external_links && measure.external_links.length > 0) {{
                const linkIcons = {{
                    'ballot': '🗳️',
                    'government': '🏛️',
                    'academic': '🎓',
                    'analysis': '📊',
                    'wikipedia': '📚'
                }};
                measure.external_links.forEach(link => {{
                    const icon = linkIcons[link.icon] || '🔗';
                    const confidenceClass = link.confidence === 'high' ? 'link-high-confidence' :
                                           link.confidence === 'medium' ? 'link-medium-confidence' : 'link-low-confidence';
                    links.push(`<a href="${{link.url}}" target="_blank" rel="noopener noreferrer" class="${{confidenceClass}}">${{icon}} ${{link.source}}</a>`);
                }});
            }}

            // Add original source links
            if (measure.source_url) {{
                links.push(`<a href="${{measure.source_url}}" target="_blank" rel="noopener noreferrer">🔗 Data Source (${{measure.data_source || 'Original'}})</a>`);
            }}
            if (measure.pdf_url && measure.pdf_url !== '#') {{
                links.push(`<a href="${{measure.pdf_url}}" target="_blank" rel="noopener noreferrer">📄 Full Ballot Text (PDF)</a>`);
            }}

            // For pending measures, add helpful official source links
            if (isPending && links.length === 0) {{
                links.push(`<a href="https://www.sos.ca.gov/elections/ballot-measures" target="_blank" rel="noopener noreferrer" class="link-high-confidence">🏛️ CA Secretary of State - Ballot Measures</a>`);
                links.push(`<a href="https://lao.ca.gov/BallotAnalysis" target="_blank" rel="noopener noreferrer" class="link-high-confidence">📊 LAO - Fiscal Analysis</a>`);
                links.push(`<a href="https://leginfo.legislature.ca.gov/" target="_blank" rel="noopener noreferrer" class="link-medium-confidence">📜 CA Legislature - Bill Information</a>`);
            }} else if (links.length === 0) {{
                links.push('<span class="no-summary-text">No external links available</span>');
            }}

            // Add pending disclaimer
            if (isPending) {{
                links.push(`<div class="pending-disclaimer"><strong>Note:</strong> This measure is pending and has not yet been voted on. Information may be updated as official details become available.</div>`);
            }}

            linksContainer.innerHTML = links.join('');

            // Show modal
            modal.style.display = 'flex';
            document.body.style.overflow = 'hidden'; // Prevent background scrolling
        }}

        // Close measure detail modal
        function closeMeasureDetail() {{
            const modal = document.getElementById('measureDetailModal');
            modal.style.display = 'none';
            document.body.style.overflow = ''; // Restore scrolling
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
                selectedYears: [],
                search: '',
                regions: [],
                county: null
            }};

            // Reset pagination
            pagination.currentPage = 1;

            // Reset UI
            document.getElementById('searchInput').value = '';
            document.getElementById('countySelect').value = '';
            updateFilterUI();
            updateTopicChipUI();
            updateYearChipUI();
            updateStatusChipUI();
            updateRegionChipUI();
            updateFilterCountBadges();

            applyFilters();
        }}

        // Reset to home page (clear filters, scroll to top, reset URL)
        function resetToHome() {{
            // Clear all filters
            clearAllFilters();

            // Clear historical topic selection if any
            selectedHistoricalTopic = null;
            document.querySelectorAll('.topic-filter-chip[data-historical-topic]').forEach(el => {{
                el.classList.remove('selected');
            }});
            const historicalPanel = document.getElementById('historical-context-display');
            if (historicalPanel) historicalPanel.remove();

            // Close any open accordion panels
            document.querySelectorAll('.accordion-panel').forEach(panel => {{
                panel.style.display = 'none';
            }});
            document.querySelectorAll('.accordion-tab').forEach(tab => {{
                tab.classList.remove('active');
            }});

            // Reset URL to clean state
            window.history.pushState({{}}, '', window.location.pathname);

            // Scroll to top
            window.scrollTo({{ top: 0, behavior: 'smooth' }});
        }}

        // Update region chip UI state
        function updateRegionChipUI() {{
            document.querySelectorAll('.region-chip').forEach(chip => {{
                const region = chip.dataset.region;
                if (currentFilters.regions && currentFilters.regions.includes(region)) {{
                    chip.classList.add('selected');
                }} else {{
                    chip.classList.remove('selected');
                }}
            }});
        }}

        // =====================================================
        // Quiz Widget
        // =====================================================
        let quizCurrentIndex = 0;
        let quizShuffled = [];

        // Shuffle quiz questions on page load
        function shuffleQuiz() {{
            quizShuffled = [...quizQuestions].sort(() => Math.random() - 0.5);
            quizCurrentIndex = 0;
            displayQuizQuestion();
        }}

        // Display the current quiz question
        function displayQuizQuestion() {{
            if (quizShuffled.length === 0) return;

            const q = quizShuffled[quizCurrentIndex];
            document.getElementById('quizCategory').textContent = q.category;
            document.getElementById('quizQuestion').textContent = q.question;
            document.getElementById('quizAnswer').style.display = 'none';
            document.getElementById('quizAnswer').innerHTML = '<p>' + q.answer + '</p>';
            document.getElementById('quizRevealBtn').style.display = 'inline-block';
            document.getElementById('quizNextBtn').style.display = 'none';
            document.getElementById('quizProgress').textContent =
                'Question ' + (quizCurrentIndex + 1) + ' of ' + quizShuffled.length;
        }}

        // Reveal the answer
        function revealAnswer() {{
            document.getElementById('quizAnswer').style.display = 'block';
            document.getElementById('quizRevealBtn').style.display = 'none';
            document.getElementById('quizNextBtn').style.display = 'inline-block';
        }}

        // Go to next question
        function nextQuestion() {{
            quizCurrentIndex = (quizCurrentIndex + 1) % quizShuffled.length;
            displayQuizQuestion();
        }}

        // Initialize quiz on page load
        document.addEventListener('DOMContentLoaded', function() {{
            if (quizQuestions && quizQuestions.length > 0) {{
                shuffleQuiz();
            }}
        }});
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

            // Check if question is about specific topics (use display_topic for cleaner list)
            const topics = [...new Set(allMeasures.map(m => m.display_topic).filter(Boolean))];
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

            // Close measure detail modal when clicking outside
            const measureModal = document.getElementById('measureDetailModal');
            if (measureModal) {
                measureModal.addEventListener('click', function(e) {
                    if (e.target === measureModal) {
                        closeMeasureDetail();
                    }
                });
            }

            // Close modals with Escape key
            document.addEventListener('keydown', function(e) {
                if (e.key === 'Escape') {
                    closeMeasureDetail();
                    closeChatSettings();
                    closeAboutModal();
                }
            });
        });

        // About modal functions
        function openAboutModal() {
            document.getElementById('aboutModal').style.display = 'flex';
            document.body.style.overflow = 'hidden';
        }

        function closeAboutModal(event) {
            if (!event || event.target.id === 'aboutModal') {
                document.getElementById('aboutModal').style.display = 'none';
                document.body.style.overflow = '';
            }
        }
        """