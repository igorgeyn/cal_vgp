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
from ..utils.category_type_mapping import get_display_category_type

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

            # Normalize county names to Title Case with spelling corrections
            county = data.get('county')
            if county:
                county = county.strip().title()
                # Fix known misspellings from CEDA data
                county = {
                    'San Bernadino': 'San Bernardino',
                    'Toulumne': 'Tuolumne',
                }.get(county, county)
                data['county'] = county
            else:
                # Statewide measures (ICPSR, NCSL, CA SOS) have no county
                data['county'] = 'Statewide'

            # Ensure year is string for consistency in JSON
            if data.get('year'):
                data['year'] = str(data['year'])

            # Add consolidated display topic (maps detailed topics to ~12 categories)
            raw_topic = data.get('topic_primary') or data.get('category_topic')
            data['display_topic'] = get_display_topic(raw_topic)

            # Add consolidated display category type (maps ~23 raw types to ~13 clean types)
            data['display_category_type'] = get_display_category_type(data.get('category_type'))

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
            'counties', 'topics', 'statewide_count', 'local_count'
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

        # 8. Number of counties (data is now normalized, just exclude Statewide)
        counties = set(m.get('county') for m in measures if m.get('county') and m.get('county') != 'Statewide')
        questions.append({
            'question': 'How many of California\'s 58 counties are represented in the database?',
            'answer': f'All {len(counties)} counties! The database includes ballot measures from every county in California, from Alpine (population ~1,200) to Los Angeles (population ~10 million).',
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

    def _load_finance_data(self) -> Dict:
        """Load finance data from the finance DB if it exists."""
        try:
            from src.finance.schema import FINANCE_DB_PATH
            from src.finance.operations import FinanceDatabase
        except ImportError:
            logger.info("Finance module not available, skipping finance data")
            return {}

        if not FINANCE_DB_PATH.exists():
            logger.info("Finance DB not found, skipping finance data")
            return {}

        try:
            fdb = FinanceDatabase(FINANCE_DB_PATH)
            result = {}
            for mid in fdb.get_all_measure_ids():
                result[mid] = {
                    'summary': fdb.get_finance_summary(mid),
                    'donors': fdb.get_top_donors(mid),
                    'timeline': fdb.get_finance_timeline(mid),
                    'breakdown': fdb.get_contribution_breakdown(mid),
                }
            fdb.close()
            logger.info(f"Loaded finance data for {len(result)} measures")
            return result
        except Exception as e:
            logger.warning(f"Could not load finance data: {e}")
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

        # Load finance data if available
        finance_data = self._load_finance_data()
        finance_json = json.dumps(finance_data, default=str)

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
    <title>CalBallot — California Ballot Measures</title>
    <style>
        {self._get_css()}
    </style>
</head>
<body>
    <!-- Header -->
    <header class="header">
        <div class="header-content">
            <div class="logo" onclick="resetToHome()" style="cursor: pointer;" title="Return to home">
                <div class="logo-icon">CB</div>
                <h1>CalBallot</h1>
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
                <button class="view-btn" id="exploreView" onclick="setView('explore')" title="Explore: topic × jurisdiction matrix">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                        <rect x="3" y="3" width="4" height="4" rx="1"></rect>
                        <rect x="10" y="3" width="4" height="4" rx="1"></rect>
                        <rect x="17" y="3" width="4" height="4" rx="1"></rect>
                        <rect x="3" y="10" width="4" height="4" rx="1"></rect>
                        <rect x="10" y="10" width="4" height="4" rx="1"></rect>
                        <rect x="17" y="10" width="4" height="4" rx="1"></rect>
                        <rect x="3" y="17" width="4" height="4" rx="1"></rect>
                        <rect x="10" y="17" width="4" height="4" rx="1"></rect>
                        <rect x="17" y="17" width="4" height="4" rx="1"></rect>
                    </svg>
                    Explore
                </button>
            </div>
        </div>
    </header>

    <!-- Main Content -->
    <div class="main-container-full">
        <!-- Main Content Area -->
        <main class="content-full">
            <!-- View Mode Switcher -->
            <div class="view-switcher">
                <button class="view-card active" id="gridViewCard" onclick="setView('grid')">
                    <div class="view-card-icon">
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
                            <rect x="3" y="3" width="7" height="7" rx="1"></rect>
                            <rect x="14" y="3" width="7" height="7" rx="1"></rect>
                            <rect x="3" y="14" width="7" height="7" rx="1"></rect>
                            <rect x="14" y="14" width="7" height="7" rx="1"></rect>
                        </svg>
                    </div>
                    <div class="view-card-text">
                        <span class="view-card-title">Cards</span>
                        <span class="view-card-desc">Browse measures as visual cards</span>
                    </div>
                </button>
                <button class="view-card" id="listViewCard" onclick="setView('list')">
                    <div class="view-card-icon">
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
                            <rect x="3" y="4" width="18" height="2" rx="1"></rect>
                            <rect x="3" y="11" width="18" height="2" rx="1"></rect>
                            <rect x="3" y="18" width="18" height="2" rx="1"></rect>
                        </svg>
                    </div>
                    <div class="view-card-text">
                        <span class="view-card-title">List</span>
                        <span class="view-card-desc">Compact list for quick scanning</span>
                    </div>
                </button>
                <button class="view-card" id="exploreViewCard" onclick="setView('explore')">
                    <div class="view-card-icon">
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
                            <rect x="3" y="3" width="5" height="5" rx="1"></rect>
                            <rect x="10" y="3" width="5" height="5" rx="1"></rect>
                            <rect x="17" y="3" width="5" height="5" rx="1"></rect>
                            <rect x="3" y="10" width="5" height="5" rx="1"></rect>
                            <rect x="10" y="10" width="5" height="5" rx="1"></rect>
                            <rect x="17" y="10" width="5" height="5" rx="1"></rect>
                            <rect x="3" y="17" width="5" height="5" rx="1"></rect>
                            <rect x="10" y="17" width="5" height="5" rx="1"></rect>
                            <rect x="17" y="17" width="5" height="5" rx="1"></rect>
                        </svg>
                    </div>
                    <div class="view-card-text">
                        <span class="view-card-title">Explore</span>
                        <span class="view-card-desc">Pass-rate matrix by topic or measure type</span>
                    </div>
                </button>
            </div>

            <!-- Site Introduction -->
            <div class="site-intro">
                <h1 class="intro-title">CalBallot</h1>
                <p class="intro-text">
                    Explore California ballot measures from {stats.get('year_min', 1998)} to the present.
                    Filter by region, topic, year, or status. Click any measure for details, AI-generated summaries, and related measures.
                </p>
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

            <!-- Filter Section (redesigned) -->
            <div class="filter-section-wrapper">
                <div class="filter-header-row">
                    <h3 class="filter-title">Filter & Explore</h3>
                    <div class="filter-actions">
                        <select class="sort-select" id="sortSelect" onchange="applySort()">
                            <option value="year-desc">Newest First</option>
                            <option value="year-asc">Oldest First</option>
                            <option value="title">Title A-Z</option>
                            <option value="votes">Most Votes</option>
                        </select>
                        <button class="clear-filters-btn" onclick="clearAllFilters()">
                            Clear All
                        </button>
                    </div>
                </div>

                <div class="filter-buttons">
                    <button class="filter-btn" data-panel="level" onclick="toggleAccordion('level')">
                        <span class="filter-btn-icon">🏛️</span>
                        <span class="filter-btn-label">Level</span>
                        <span class="filter-btn-count" id="levelFilterCount"></span>
                    </button>
                    <button class="filter-btn" data-panel="region" onclick="toggleAccordion('region')">
                        <span class="filter-btn-icon">🗺️</span>
                        <span class="filter-btn-label">Region</span>
                        <span class="filter-btn-count" id="regionFilterCount"></span>
                    </button>
                    <button class="filter-btn" data-panel="topic" onclick="toggleAccordion('topic')">
                        <span class="filter-btn-icon">📑</span>
                        <span class="filter-btn-label">Topic</span>
                        <span class="filter-btn-count" id="topicFilterCount"></span>
                    </button>
                    <button class="filter-btn" data-panel="year" onclick="toggleAccordion('year')">
                        <span class="filter-btn-icon">📅</span>
                        <span class="filter-btn-label">Year</span>
                        <span class="filter-btn-count" id="yearFilterCount"></span>
                    </button>
                    <button class="filter-btn" data-panel="status" onclick="toggleAccordion('status')">
                        <span class="filter-btn-icon">✓</span>
                        <span class="filter-btn-label">Status</span>
                        <span class="filter-btn-count" id="statusFilterCount"></span>
                    </button>
                    <button class="filter-btn" data-panel="measureType" onclick="toggleAccordion('measureType')">
                        <span class="filter-btn-icon">📊</span>
                        <span class="filter-btn-label">Measure Type</span>
                        <span class="filter-btn-count" id="measureTypeFilterCount"></span>
                    </button>
                </div>

                <!-- Level Panel -->
                <div class="accordion-panel" id="levelPanel" style="display: none;">
                    <div class="panel-content">
                        <p class="panel-hint">Filter by statewide propositions or local/county measures</p>
                        <div class="level-cards" id="levelCards">
                            <div class="status-chip" data-level="statewide" onclick="toggleLevelFilter('statewide')">
                                <span class="status-chip-icon">🏛️</span>
                                <span class="status-chip-name">Statewide</span>
                                <span class="status-chip-count">({stats.get('statewide_count', 0):,})</span>
                            </div>
                            <div class="status-chip" data-level="local" onclick="toggleLevelFilter('local')">
                                <span class="status-chip-icon">📍</span>
                                <span class="status-chip-name">Local</span>
                                <span class="status-chip-count">({stats.get('local_count', 0):,})</span>
                            </div>
                        </div>
                        <div class="county-navigation" id="levelCountyNav" style="display: none;">
                            <label for="levelCountySelect" class="county-label">
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path>
                                    <circle cx="12" cy="10" r="3"></circle>
                                </svg>
                                Select a specific county:
                            </label>
                            <select id="levelCountySelect" class="county-select" onchange="filterByLevelCounty(this.value)">
                                <option value="">All Local</option>
                                <!-- Will be populated by JavaScript -->
                            </select>
                        </div>
                    </div>
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

                <!-- Measure Type Panel -->
                <div class="accordion-panel" id="measureTypePanel" style="display: none;">
                    <div class="panel-content">
                        <p class="panel-hint">Filter by measure type (GO Bond, Property Tax, Sales Tax, etc.)</p>
                        <div class="measure-type-cards" id="measureTypeCards"></div>
                    </div>
                </div>
            </div>

            <!-- Results Count -->
            <div class="results-header">
                <div class="results-info">
                    <span class="results-count" id="resultsCount">0</span>
                    <span class="results-description" id="resultsDescription">measures found</span>
                </div>
            </div>

            <!-- Results Container -->
            <div id="resultsContainer">
                <div class="loading">
                    <div class="spinner"></div>
                </div>
            </div>

            <!-- Upcoming 2026 Ballot Measures Section -->
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
                <div class="hero-carousel">
                    <button class="carousel-btn carousel-prev" onclick="heroCarouselPrev()" aria-label="Previous">
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <polyline points="15 18 9 12 15 6"></polyline>
                        </svg>
                    </button>
                    <div class="carousel-track-container">
                        <div class="carousel-track" id="heroGrid">
                            <!-- Will be populated by JavaScript -->
                        </div>
                    </div>
                    <button class="carousel-btn carousel-next" onclick="heroCarouselNext()" aria-label="Next">
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <polyline points="9 18 15 12 9 6"></polyline>
                        </svg>
                    </button>
                </div>
                <div class="carousel-dots" id="heroCarouselDots">
                    <!-- Will be populated by JavaScript -->
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
        <p>CalBallot • Updated {datetime.now().strftime('%B %d, %Y')}</p>
        <p>Data sources: CA Secretary of State, NCSL, ICPSR, CEDA</p>
        <p class="footer-links">
            <a href="#" onclick="openAboutModal(); return false;">About</a>
        </p>
        <div class="civic-links">
            <a class="civic-btn" href="https://registertovote.ca.gov/" target="_blank" rel="noopener">Register to Vote</a>
            <a class="civic-btn" href="https://www.sos.ca.gov/elections/polling-place" target="_blank" rel="noopener">Find Polling Place</a>
            <a class="civic-btn" href="https://www.sos.ca.gov/elections/ballot-status" target="_blank" rel="noopener">Track Your Ballot</a>
            <a class="civic-btn" href="https://voterguide.sos.ca.gov/" target="_blank" rel="noopener">Official Voter Guide</a>
        </div>
    </footer>

    <!-- About Modal -->
    <div id="aboutModal" class="modal" style="display: none;" onclick="closeAboutModal(event)">
        <div class="modal-content about-modal" onclick="event.stopPropagation()">
            <button class="modal-close" onclick="closeAboutModal()">&times;</button>
            <h2 class="about-title">About This Project</h2>

            <div class="about-section">
                <p>
                    CalBallot is a tool for exploring over 12,000 ballot measures
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

            <div class="about-section">
                <h3>Data Pipeline</h3>
                <p>
                    Building this database required substantial data engineering work:
                </p>
                <ul>
                    <li><strong>Data collection:</strong> Aggregated records from multiple sources including the CA Secretary of State,
                        NCSL, ICPSR, and CEDA research databases</li>
                    <li><strong>Deduplication:</strong> Merged overlapping records using fingerprinting algorithms to identify
                        the same measure across different sources</li>
                    <li><strong>Standardization:</strong> Normalized county names, vote percentages, and date formats
                        across inconsistent source data</li>
                    <li><strong>Topic classification:</strong> Used K-means clustering on sentence embeddings to automatically
                        categorize measures into ~20 topic clusters</li>
                    <li><strong>AI summaries:</strong> Generated plain-language summaries using LLMs for measures
                        with sufficient ballot text</li>
                    <li><strong>Similarity matching:</strong> Computed semantic embeddings (all-MiniLM-L6-v2) to find
                        related measures based on content similarity</li>
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

                <div id="modalTimelineSection" class="measure-detail-section" style="display: none;">
                    <h3>📍 Status</h3>
                    <div id="modalTimeline"></div>
                </div>

                <div class="measure-detail-section">
                    <h3>📝 Summary</h3>
                    <p id="modalSummary" class="measure-detail-summary"></p>
                    <span id="summaryToggle" class="summary-toggle" style="display:none;" onclick="toggleSummary()">Show more</span>
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

                <div id="modalFinanceSection" class="measure-detail-section" style="display: none;">
                    <h3>💰 Money &amp; Coalition</h3>
                    <div id="modalFinanceContent" class="measure-detail-finance"></div>
                </div>
            </div>
        </div>
    </div>

    <script>
        {self._get_javascript(measures_json, topics_json, recommendations_json, stats, quiz_json, finance_json)}
        {self._get_chat_javascript()}
    </script>
</body>
</html>"""
        
        return html
    
    def _get_css(self) -> str:
        """Get CSS styles for the website"""
        return """
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

        /* Modern CSS Reset and Variables */
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        :root {
            --primary: #C9A23C;
            --primary-dark: #A8841E;
            --primary-hover: #A8841E;
            --accent: #C9A23C;
            --success: #3A8C28;
            --danger: #C0392B;
            --warning: #C9A23C;
            --bg-primary: #F7F5F0;
            --bg-secondary: #EEEADD;
            --bg-tertiary: #E0DAC8;
            --text-primary: #1A1714;
            --text-secondary: #6B5F48;
            --text-tertiary: #999080;
            --border: #E0DAC8;
            --shadow-sm: 0 1px 3px rgba(26,23,20,.08), 0 1px 2px rgba(26,23,20,.06);
            --shadow-md: 0 2px 8px rgba(26,23,20,.1), 0 4px 16px rgba(26,23,20,.06);
            --radius: 8px;
            --radius-sm: 4px;
            --transition: all 0.2s ease;
        }

        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            line-height: 1.6;
            color: var(--text-primary);
            background: var(--bg-secondary);
            -webkit-font-smoothing: antialiased;
        }
        
        /* Header */
        .header {
            background: #111;
            border-bottom: none;
            position: sticky;
            top: 0;
            z-index: 100;
            box-shadow: none;
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
            color: #111;
            font-weight: 800;
            font-size: 14px;
        }

        .logo h1 {
            font-size: 1.25rem;
            font-weight: 800;
            color: #E8E2D4;
            letter-spacing: -0.5px;
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
            border: 1px solid #333;
            border-radius: 24px;
            font-size: 1rem;
            transition: var(--transition);
            background: #1A1A1A;
            color: #ccc;
            font-family: inherit;
        }

        .search-input:focus {
            outline: none;
            border-color: var(--primary);
            background: #1A1A1A;
            box-shadow: none;
        }

        .search-input::placeholder {
            color: #666;
        }

        .search-icon {
            position: absolute;
            left: 1rem;
            top: 50%;
            transform: translateY(-50%);
            color: #666;
        }
        
        /* View Controls */
        .view-controls {
            display: flex;
            gap: 0.5rem;
        }
        
        .view-btn {
            padding: 0.5rem 0.75rem;
            border: 1px solid #333;
            background: #1A1A1A;
            border-radius: var(--radius-sm);
            cursor: pointer;
            color: #999;
            transition: var(--transition);
        }

        .view-btn:hover {
            color: #E8E2D4;
            border-color: #555;
        }

        .view-btn.active {
            background: var(--primary);
            color: #111;
            border-color: var(--primary);
        }

        /* Explore Matrix - Clean Modern Design */
        .matrix-wrapper {
            margin: 1rem 0;
            border-radius: 12px;
            background: #FDFCFA;
            border: 1px solid #E5E0D8;
            box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        }
        .matrix-toolbar {
            display: flex;
            gap: 1rem;
            padding: 1rem 1.25rem;
            border-bottom: 1px solid #E5E0D8;
            align-items: center;
            flex-wrap: wrap;
            background: #F8F6F3;
            border-radius: 12px 12px 0 0;
        }
        .matrix-toolbar-info {
            color: #666;
            font-size: 0.85rem;
            font-weight: 500;
        }
        .matrix-toolbar-info strong {
            color: #333;
        }
        .matrix-toolbar select {
            background: #fff;
            color: #333;
            border: 1px solid #D4CFC5;
            border-radius: 6px;
            padding: 0.4rem 0.6rem;
            font-size: 0.8rem;
            cursor: pointer;
            transition: border-color 0.2s;
        }
        .matrix-toolbar select:hover {
            border-color: var(--primary);
        }
        .matrix-legend {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            margin-left: auto;
            font-size: 0.75rem;
            color: #888;
        }
        .matrix-legend-label {
            color: #666;
        }
        .matrix-legend-bar {
            display: flex;
            height: 12px;
            width: 100px;
            border-radius: 6px;
            overflow: hidden;
            box-shadow: inset 0 1px 2px rgba(0,0,0,0.1);
        }
        .matrix-legend-bar span { flex: 1; }
        .matrix-scroll {
            max-height: 65vh;
            overflow: auto;
        }
        .matrix-table {
            border-collapse: separate;
            border-spacing: 3px;
            font-size: 0.8rem;
            min-width: 100%;
            padding: 0.75rem;
        }
        .matrix-table th,
        .matrix-table td {
            padding: 0.6rem 0.75rem;
            text-align: center;
            white-space: nowrap;
        }
        .matrix-table thead th {
            background: #FDFCFA;
            color: #666;
            position: sticky;
            top: 0;
            z-index: 2;
            user-select: none;
            font-size: 0.7rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.03em;
            padding-bottom: 0.75rem;
        }
        .matrix-table thead th:hover { color: var(--primary); }
        .matrix-table thead th.sorted-asc::after { content: ' ↑'; color: var(--primary); }
        .matrix-table thead th.sorted-desc::after { content: ' ↓'; color: var(--primary); }
        .matrix-table thead th:first-child,
        .matrix-table td:first-child {
            position: sticky;
            left: 0;
            z-index: 3;
            text-align: left;
            min-width: 160px;
            background: #FDFCFA;
        }
        .matrix-table td:first-child {
            font-weight: 600;
            color: #333;
            z-index: 1;
            font-size: 0.85rem;
            padding-left: 0.5rem;
        }
        .matrix-table td:first-child:hover { color: var(--primary); }
        .matrix-table th[role="button"],
        .matrix-table td[role="button"] {
            cursor: pointer;
        }
        .matrix-table th[role="button"]:focus-visible,
        .matrix-table td[role="button"]:focus-visible {
            outline: 2px solid var(--primary);
            outline-offset: 2px;
            border-radius: 6px;
        }
        .matrix-cell {
            min-width: 80px;
            border-radius: 8px;
            transition: transform 0.15s, box-shadow 0.15s;
            padding: 0.5rem 0.6rem !important;
        }
        .matrix-cell[role="button"]:hover {
            transform: scale(1.05);
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            z-index: 10;
            position: relative;
        }
        .matrix-cell.low-conf {
            opacity: 0.6;
        }
        .matrix-cell.low-conf .cell-rate {
            font-size: 0.7rem;
        }
        .matrix-cell .cell-rate {
            font-weight: 700;
            font-size: 0.95rem;
            color: #fff;
            text-shadow: 0 1px 2px rgba(0,0,0,0.2);
            display: block;
        }
        .matrix-cell .cell-count {
            font-size: 0.65rem;
            color: rgba(255,255,255,0.75);
            display: block;
            margin-top: 2px;
            font-weight: 500;
        }
        .matrix-cell.empty-cell {
            background: #F0EDE8 !important;
            color: #BBB;
            cursor: default;
        }
        .matrix-cell.empty-cell .cell-rate {
            color: #BBB;
            text-shadow: none;
            font-weight: 500;
        }
        .matrix-cell.empty-cell:hover {
            transform: none;
            box-shadow: none;
        }
        .matrix-totals td {
            background: #333 !important;
            font-weight: 600;
            border-radius: 8px;
        }
        .matrix-totals td .cell-rate {
            color: var(--primary);
            display: block;
        }
        .matrix-totals td .cell-count {
            display: block;
            font-size: 0.65rem;
            color: rgba(255,255,255,0.75);
        }
        .matrix-totals td:first-child {
            background: transparent !important;
            color: #666;
            font-weight: 600;
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

        /* View Switcher */
        .view-switcher {
            display: flex;
            justify-content: center;
            gap: 1rem;
            padding: 1.25rem 1rem;
            background: var(--bg-secondary);
            border-bottom: 1px solid var(--border);
        }

        .view-card {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            padding: 0.875rem 1.25rem;
            border-radius: 10px;
            border: 2px solid var(--border);
            background: var(--bg-primary);
            cursor: pointer;
            transition: var(--transition);
            min-width: 200px;
        }

        .view-card:hover {
            border-color: var(--primary);
            background: var(--bg-secondary);
        }

        .view-card.active {
            border-color: var(--primary);
            background: rgba(201, 162, 60, 0.1);
        }

        .view-card-icon {
            display: flex;
            align-items: center;
            justify-content: center;
            width: 40px;
            height: 40px;
            border-radius: 8px;
            background: var(--bg-tertiary);
            color: var(--text-secondary);
            flex-shrink: 0;
        }

        .view-card.active .view-card-icon {
            background: var(--primary);
            color: #111;
        }

        .view-card-text {
            display: flex;
            flex-direction: column;
            text-align: left;
        }

        .view-card-title {
            font-size: 0.95rem;
            font-weight: 600;
            color: var(--text-primary);
        }

        .view-card-desc {
            font-size: 0.75rem;
            color: var(--text-tertiary);
            margin-top: 0.15rem;
        }

        @media (max-width: 768px) {
            .view-switcher {
                flex-direction: column;
                align-items: center;
                gap: 0.75rem;
                padding: 1rem;
            }
            .view-card {
                width: 100%;
                max-width: 280px;
                min-width: unset;
            }
        }

        /* Civic action buttons (in footer) */
        .civic-links {
            display: flex;
            justify-content: center;
            flex-wrap: wrap;
            gap: 0.5rem;
            margin-top: 1rem;
        }
        .civic-btn {
            display: inline-flex;
            align-items: center;
            padding: 0.4rem 0.9rem;
            font-size: 0.82rem;
            font-weight: 500;
            border-radius: 6px;
            border: 1px solid #444;
            background: transparent;
            color: #888;
            text-decoration: none;
            transition: var(--transition);
        }
        .civic-btn:hover {
            border-color: var(--primary);
            color: var(--primary);
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
            background: linear-gradient(135deg, rgba(201, 162, 60, 0.08) 0%, rgba(201, 162, 60, 0.03) 100%);
            border: 2px solid rgba(201, 162, 60, 0.2);
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

        /* Hero Carousel */
        .hero-carousel {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            position: relative;
            padding: 0 0.5rem;
        }

        .carousel-track-container {
            flex: 1;
            overflow: hidden;
            min-width: 0;
            position: relative;
        }

        .carousel-track {
            display: flex;
            transition: transform 0.4s ease;
            gap: 20px;
        }

        .carousel-track .measure-card {
            flex: 0 0 calc(33.333% - 14px);
            min-width: calc(33.333% - 14px);
            max-width: calc(33.333% - 14px);
            box-sizing: border-box;
        }

        .carousel-btn {
            flex-shrink: 0;
            width: 44px;
            height: 44px;
            border-radius: 50%;
            background: var(--bg-primary);
            border: 1px solid var(--border);
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            color: var(--text-secondary);
            transition: var(--transition);
            box-shadow: var(--shadow-sm);
            z-index: 10;
        }

        .carousel-btn:hover:not(:disabled) {
            background: var(--bg-secondary);
            color: var(--primary);
            border-color: var(--primary);
        }

        .carousel-btn:disabled {
            opacity: 0.3;
            cursor: not-allowed;
        }

        .carousel-dots {
            display: flex;
            justify-content: center;
            gap: 0.5rem;
            margin-top: 1rem;
        }

        .carousel-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--border);
            border: none;
            cursor: pointer;
            transition: var(--transition);
            padding: 0;
        }

        .carousel-dot:hover {
            background: var(--text-tertiary);
        }

        .carousel-dot.active {
            background: var(--primary);
            width: 24px;
            border-radius: 4px;
        }

        /* Responsive carousel */
        @media (max-width: 1024px) {
            .carousel-track .measure-card {
                flex: 0 0 calc(50% - 10px);
                min-width: calc(50% - 10px);
                max-width: calc(50% - 10px);
            }
        }

        @media (max-width: 640px) {
            .carousel-track .measure-card {
                flex: 0 0 100%;
                min-width: 100%;
                max-width: 100%;
            }

            .carousel-btn {
                width: 36px;
                height: 36px;
            }

            .hero-carousel {
                gap: 0.5rem;
            }
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
            background: rgba(201, 162, 60, 0.06);
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
            background: rgba(201, 162, 60, 0.06);
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
            background: rgba(201, 162, 60, 0.06);
            border-radius: var(--radius);
            border: 1px solid rgba(201, 162, 60, 0.12);
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
            box-shadow: 0 0 0 3px rgba(201, 162, 60, 0.12);
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

        /* Filter Section Styles */
        .filter-section-wrapper {
            background: var(--bg-primary);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 1.5rem;
            margin-bottom: 2rem;
            box-shadow: var(--shadow-sm);
        }

        .filter-header-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1.25rem;
            flex-wrap: wrap;
            gap: 1rem;
        }

        .filter-title {
            font-size: 1.25rem;
            font-weight: 600;
            color: var(--text-primary);
            margin: 0;
        }

        .filter-actions {
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }

        .sort-select {
            padding: 0.5rem 2rem 0.5rem 0.75rem;
            border: 1px solid var(--border-color);
            border-radius: var(--radius-sm);
            background: var(--bg-primary);
            color: var(--text-primary);
            font-size: 0.875rem;
            cursor: pointer;
            appearance: none;
            background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%236b7280' stroke-width='2'%3E%3Cpath d='M6 9l6 6 6-6'/%3E%3C/svg%3E");
            background-repeat: no-repeat;
            background-position: right 0.5rem center;
        }

        .sort-select:hover {
            border-color: var(--primary);
        }

        .clear-filters-btn {
            padding: 0.5rem 1rem;
            border: 1px solid var(--border-color);
            border-radius: var(--radius-sm);
            background: var(--bg-secondary);
            color: var(--text-secondary);
            font-size: 0.875rem;
            cursor: pointer;
            transition: all 0.2s ease;
        }

        .clear-filters-btn:hover {
            background: var(--error);
            color: white;
            border-color: var(--error);
        }

        .filter-buttons {
            display: flex;
            justify-content: center;
            gap: 0.75rem;
            flex-wrap: wrap;
        }

        .filter-btn {
            display: flex;
            align-items: center;
            gap: 0.625rem;
            padding: 0.875rem 1.5rem;
            background: linear-gradient(135deg, var(--bg-secondary) 0%, var(--bg-primary) 100%);
            border: 2px solid var(--border-color);
            border-radius: 12px;
            cursor: pointer;
            transition: all 0.2s ease;
            font-size: 0.95rem;
            color: var(--text-primary);
            font-weight: 500;
            min-width: 120px;
            justify-content: center;
        }

        .filter-btn:hover {
            border-color: var(--primary);
            background: linear-gradient(135deg, rgba(201, 162, 60, 0.08) 0%, rgba(201, 162, 60, 0.03) 100%);
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(201, 162, 60, 0.15);
        }

        .filter-btn.active {
            border-color: var(--primary);
            background: var(--primary);
            color: white;
            box-shadow: 0 4px 12px rgba(201, 162, 60, 0.3);
        }

        .filter-btn.has-selection {
            border-color: var(--accent);
            background: linear-gradient(135deg, rgba(52, 168, 83, 0.12) 0%, rgba(52, 168, 83, 0.05) 100%);
        }

        .filter-btn.has-selection:not(.active) .filter-btn-count {
            background: var(--accent);
            color: white;
        }

        .filter-btn-icon {
            font-size: 1.1rem;
        }

        .filter-btn-label {
            font-weight: 500;
        }

        .filter-btn-count {
            background: var(--bg-tertiary);
            color: var(--text-secondary);
            font-size: 0.75rem;
            font-weight: 600;
            padding: 0.2rem 0.5rem;
            border-radius: 10px;
            min-width: 20px;
            text-align: center;
        }

        .filter-btn.active .filter-btn-count {
            background: rgba(255, 255, 255, 0.25);
            color: white;
        }

        @media (max-width: 768px) {
            .filter-section-wrapper {
                padding: 1rem;
            }

            .filter-header-row {
                flex-direction: column;
                align-items: stretch;
                gap: 0.75rem;
            }

            .filter-title {
                text-align: center;
            }

            .filter-actions {
                justify-content: center;
            }

            .filter-buttons {
                gap: 0.5rem;
            }

            .filter-btn {
                padding: 0.75rem 1rem;
                min-width: auto;
                flex: 1;
                max-width: calc(50% - 0.25rem);
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
            border: 1px solid #E8E2D4;
            min-height: 200px;
            max-height: 400px;
        }

        .measure-card:hover {
            box-shadow: 0 6px 20px rgba(26,23,20,.1);
            transform: translateY(-2px);
            border-color: var(--primary);
        }

        .measure-card.hero {
            border: 2px solid var(--primary);
            box-shadow: 0 4px 12px rgba(201, 162, 60, 0.15);
            background: linear-gradient(135deg, var(--bg-primary) 0%, rgba(201, 162, 60, 0.03) 100%);
        }

        .measure-card.hero:hover {
            box-shadow: 0 8px 24px rgba(201, 162, 60, 0.25);
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
            background: rgba(58, 140, 40, 0.12);
            color: #2D6A1E;
            border: 1px solid rgba(58, 140, 40, 0.25);
        }

        .badge-passed::before {
            background: #2D6A1E;
        }

        .badge-failed {
            background: rgba(192, 57, 43, 0.12);
            color: #A0302A;
            border: 1px solid rgba(192, 57, 43, 0.25);
        }

        .badge-failed::before {
            background: #C0392B;
        }

        .badge-pending {
            background: rgba(201, 162, 60, 0.15);
            color: #8A6D14;
            border: 1px solid rgba(201, 162, 60, 0.3);
        }

        .badge-pending::before {
            background: #C9A23C;
        }

        .badge-neutral {
            background: var(--bg-secondary);
            color: var(--text-secondary);
            border: 1px solid var(--border-light);
        }

        .badge-summary {
            background: rgba(201, 162, 60, 0.12);
            color: #8A6D14;
            border: 1px solid rgba(201, 162, 60, 0.25);
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
            background: rgba(201, 162, 60, 0.03);
            padding: 0.5rem;
            border-radius: 4px;
            border-left: 2px solid rgba(201, 162, 60, 0.15);
        }

        .card-summary[data-full-text]:hover {
            background: rgba(201, 162, 60, 0.05);
            border-left-color: rgba(201, 162, 60, 0.25);
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
            background: linear-gradient(135deg, rgba(201, 162, 60, 0.06) 0%, rgba(255, 255, 255, 0.95) 100%);
            border-radius: 12px;
            padding: 2rem;
            margin-bottom: 2rem;
            border: 1px solid rgba(201, 162, 60, 0.12);
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
            background: #111;
            border-top: none;
            padding: 2rem;
            text-align: center;
            margin-top: 4rem;
            color: #666;
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
            background: linear-gradient(135deg, var(--bg-primary) 0%, rgba(201, 162, 60, 0.04) 100%);
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

        /* Measure timeline stepper */
        .measure-timeline {
            display: flex;
            align-items: center;
            gap: 0;
            margin: 10px 0 4px;
            padding: 0;
        }
        .timeline-step {
            display: flex;
            align-items: center;
            gap: 0;
            flex: 1;
            position: relative;
        }
        .timeline-step:last-child {
            flex: 0;
        }
        .timeline-dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: var(--bg-tertiary);
            border: 2px solid var(--border);
            flex-shrink: 0;
            z-index: 1;
        }
        .timeline-step.completed .timeline-dot {
            background: var(--primary);
            border-color: var(--primary);
        }
        .timeline-step.active .timeline-dot {
            background: #fff;
            border: 2px solid var(--primary);
            box-shadow: 0 0 0 3px rgba(201, 162, 60, 0.25);
        }
        .timeline-line {
            flex: 1;
            height: 2px;
            background: var(--border);
            margin: 0 2px;
        }
        .timeline-step.completed .timeline-line {
            background: var(--primary);
        }
        .timeline-labels {
            display: flex;
            justify-content: space-between;
            margin-top: 2px;
        }
        .timeline-label {
            font-size: 0.6rem;
            color: var(--text-tertiary);
            text-align: center;
            flex: 1;
            letter-spacing: 0.02em;
        }
        .timeline-label:last-child {
            flex: 0;
            min-width: 40px;
        }
        .timeline-label.active {
            color: var(--primary);
            font-weight: 600;
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

        .chat-code-block {
            background: #1a1a1a;
            border-radius: 6px;
            padding: 0.75rem;
            margin: 0.5rem 0;
            overflow-x: auto;
            font-family: 'SF Mono', Monaco, 'Courier New', monospace;
            font-size: 0.75rem;
            line-height: 1.4;
            white-space: pre-wrap;
            word-break: break-word;
        }

        .chat-code-block code {
            color: #e8e2d4;
        }

        .chat-inline-code {
            background: rgba(0,0,0,0.2);
            padding: 0.1rem 0.3rem;
            border-radius: 3px;
            font-family: 'SF Mono', Monaco, 'Courier New', monospace;
            font-size: 0.8em;
        }

        .chat-divider {
            border: none;
            border-top: 1px solid rgba(255,255,255,0.2);
            margin: 0.75rem 0;
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
            max-width: 800px;
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
            font-size: 1.25rem;
            font-weight: 600;
            margin: 0 0 0.5rem 0;
            color: var(--text-primary);
            line-height: 1.35;
        }

        .measure-detail-jurisdiction {
            font-size: 0.9rem;
            color: var(--text-secondary);
            margin-bottom: 0.75rem;
        }

        .measure-detail-badges {
            display: flex;
            flex-wrap: wrap;
            gap: 0.4rem;
            margin-bottom: 1rem;
        }

        .measure-detail-badges .badge {
            font-size: 0.875rem;
            padding: 0.4rem 0.75rem;
        }

        .measure-detail-section {
            margin-bottom: 1rem;
            padding-bottom: 1rem;
            border-bottom: 1px solid var(--border-light);
        }

        .measure-detail-section:last-child {
            margin-bottom: 0;
            padding-bottom: 0;
            border-bottom: none;
        }

        .measure-detail-section h3 {
            font-size: 0.85rem;
            font-weight: 600;
            color: var(--text-secondary);
            margin: 0 0 0.5rem 0;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .measure-detail-summary {
            font-size: 0.95rem;
            line-height: 1.6;
            color: var(--text-primary);
            margin: 0;
        }

        .measure-detail-summary.truncated {
            display: -webkit-box;
            -webkit-line-clamp: 4;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }

        .summary-toggle {
            display: inline-block;
            margin-top: 0.5rem;
            font-size: 0.85rem;
            color: var(--primary);
            cursor: pointer;
            font-weight: 500;
        }

        .summary-toggle:hover {
            text-decoration: underline;
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

        /* Finance Section */
        .measure-detail-finance {
            display: flex;
            flex-direction: column;
            gap: 1.5rem;
        }
        .finance-sides {
            display: flex;
            gap: 1.5rem;
        }
        .finance-side {
            flex: 1;
            min-width: 0;
            border-radius: var(--radius);
            padding: 0.75rem;
            background: var(--bg-secondary);
        }
        .finance-side-support {
            border-left: 4px solid var(--success);
        }
        .finance-side-oppose {
            border-left: 4px solid var(--danger);
        }
        .finance-side h4 {
            margin: 0 0 0.5rem 0;
            font-size: 0.9rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        .finance-side-support h4 { color: var(--success); }
        .finance-side-oppose h4 { color: var(--danger); }
        .finance-total {
            font-size: 1.3rem;
            font-weight: 700;
            margin-bottom: 0.15rem;
        }
        .finance-meta {
            font-size: 0.8rem;
            color: var(--text-secondary);
        }
        .finance-donors-list {
            margin-top: 0.5rem;
        }
        .finance-donors-list h4 {
            font-size: 0.78rem;
            margin: 0 0 0.3rem 0;
            color: var(--text-primary);
        }
        .finance-donor-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 0.2rem 0;
            font-size: 0.78rem;
            border-bottom: 1px solid var(--border);
        }
        .finance-donor-row:last-child { border-bottom: none; }
        .finance-donor-name {
            flex: 1;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            padding-right: 0.5rem;
        }
        .finance-donor-amount {
            font-weight: 600;
            white-space: nowrap;
        }
        .finance-donor-type {
            font-size: 0.75rem;
            color: var(--text-secondary);
            margin-left: 0.5rem;
            white-space: nowrap;
        }
        @media (max-width: 768px) {
            .finance-sides {
                flex-direction: column;
            }
        }

        /* Finance Timeline Chart */
        .finance-timeline {
            margin-top: 1rem;
            padding: 1rem;
            background: var(--bg-secondary);
            border-radius: var(--radius);
        }
        .finance-timeline h4 {
            margin: 0 0 0.75rem 0;
            font-size: 0.85rem;
            color: var(--text-secondary);
        }
        .finance-chart {
            position: relative;
            height: 120px;
            display: flex;
            align-items: flex-end;
            gap: 1px;
        }
        .finance-chart-bar {
            flex: 1;
            min-width: 2px;
            max-width: 8px;
            border-radius: 2px 2px 0 0;
            transition: opacity 0.15s;
        }
        .finance-chart-bar:hover {
            opacity: 0.8;
        }
        .finance-chart-bar.support {
            background: var(--success);
        }
        .finance-chart-bar.oppose {
            background: var(--danger);
        }
        .finance-chart-legend {
            display: flex;
            justify-content: center;
            gap: 1.5rem;
            margin-top: 0.5rem;
            font-size: 0.75rem;
            color: var(--text-secondary);
        }
        .finance-chart-legend span::before {
            content: '';
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 2px;
            margin-right: 4px;
            vertical-align: middle;
        }
        .finance-chart-legend .legend-support::before {
            background: var(--success);
        }
        .finance-chart-legend .legend-oppose::before {
            background: var(--danger);
        }
        .finance-chart-dates {
            display: flex;
            justify-content: space-between;
            font-size: 0.7rem;
            color: var(--text-tertiary);
            margin-top: 0.25rem;
        }

        /* Contribution Size Breakdown (Grassroots Score) */
        .finance-breakdown {
            margin-top: 1rem;
            padding: 1rem;
            background: var(--bg-secondary);
            border-radius: var(--radius);
        }
        .finance-breakdown h4 {
            margin: 0 0 0.75rem 0;
            font-size: 0.85rem;
            color: var(--text-secondary);
        }
        .finance-breakdown-bar {
            height: 24px;
            border-radius: 12px;
            overflow: hidden;
            display: flex;
            background: var(--bg-tertiary);
        }
        .finance-breakdown-segment {
            height: 100%;
            transition: flex 0.3s;
        }
        .finance-breakdown-segment.small { background: #4CAF50; }
        .finance-breakdown-segment.medium { background: #8BC34A; }
        .finance-breakdown-segment.large { background: #FFC107; }
        .finance-breakdown-segment.mega { background: #FF5722; }
        .finance-breakdown-labels {
            display: flex;
            justify-content: space-between;
            margin-top: 0.5rem;
            font-size: 0.7rem;
            color: var(--text-secondary);
        }
        .finance-breakdown-legend {
            display: flex;
            flex-wrap: wrap;
            gap: 0.75rem;
            margin-top: 0.5rem;
            font-size: 0.72rem;
            color: var(--text-secondary);
        }
        .finance-breakdown-legend span {
            display: flex;
            align-items: center;
            gap: 4px;
        }
        .finance-breakdown-legend .dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
        }
        .finance-breakdown-legend .dot.small { background: #4CAF50; }
        .finance-breakdown-legend .dot.medium { background: #8BC34A; }
        .finance-breakdown-legend .dot.large { background: #FFC107; }
        .finance-breakdown-legend .dot.mega { background: #FF5722; }
        .finance-grassroots-score {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            margin-top: 0.75rem;
            padding-top: 0.75rem;
            border-top: 1px solid var(--border);
        }
        .finance-grassroots-score .score-label {
            font-size: 0.8rem;
            color: var(--text-secondary);
        }
        .finance-grassroots-score .score-value {
            font-size: 1.1rem;
            font-weight: 700;
        }
        .finance-grassroots-score .score-desc {
            font-size: 0.75rem;
            color: var(--text-tertiary);
        }

        /* Measure Type chips (mirrors topic-chip pattern) */
        .measure-type-cards {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }
        .measure-type-chip {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 6px 14px;
            border-radius: 20px;
            border: 1.5px solid var(--border);
            background: white;
            cursor: pointer;
            transition: all 0.15s ease;
            font-size: 0.82rem;
        }
        .measure-type-chip:hover { border-color: #7c4dff; background: #f3edff; }
        .measure-type-chip.selected {
            background: #7c4dff;
            color: white;
            border-color: #7c4dff;
        }
        .measure-type-chip.selected .measure-type-chip-count { opacity: 0.85; }
        .measure-type-chip-icon { font-size: 1rem; }
        .measure-type-chip-name { font-weight: 500; }
        .measure-type-chip-count { font-size: 0.75rem; opacity: 0.6; }

        /* Matrix column toggle */
        .matrix-col-toggle {
            display: inline-flex;
            border: 1.5px solid var(--border);
            border-radius: 6px;
            overflow: hidden;
            margin-left: 12px;
        }
        .matrix-col-toggle button {
            padding: 3px 12px;
            font-size: 0.78rem;
            border: none;
            background: white;
            cursor: pointer;
            color: var(--text-secondary);
            transition: all 0.15s ease;
        }
        .matrix-col-toggle button:not(:last-child) {
            border-right: 1.5px solid var(--border);
        }
        .matrix-col-toggle button.active {
            background: var(--accent, #7c4dff);
            color: white;
        }
        .matrix-col-toggle button:hover:not(.active) {
            background: #f5f5f5;
        }
        """

    def _get_javascript(self, measures_json: str, topics_json: str,
                       recommendations_json: str, stats: Dict, quiz_json: str = "[]",
                       finance_json: str = "{}") -> str:
        """Get JavaScript code for the website"""
        return f"""
        // Data
        const allMeasures = {measures_json};
        const topics = {topics_json};
        const recommendations = {recommendations_json};
        const quizQuestions = {quiz_json};
        const financeData = {finance_json};

        // Utility function to escape HTML special characters (prevents XSS)
        function escapeHtml(text) {{
            if (!text) return '';
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }}

        // Utility function to detect AI refusal patterns in summaries
        function isAiRefusal(text) {{
            if (!text) return false;
            const lower = text.toLowerCase();
            return lower.includes("can't provide") ||
                   lower.includes("cannot provide") ||
                   lower.includes("cannot summarize") ||
                   lower.includes("i cannot summarize") ||
                   lower.includes("i cannot provide a summary") ||
                   lower.includes("can't help with that") ||
                   lower.includes("cannot help with that") ||
                   lower.includes("don't have any information") ||
                   lower.includes("do not have any information") ||
                   lower.includes("i don't have information") ||
                   lower.includes("no details about its content") ||
                   lower.includes("ballot text appears to be incomplete") ||
                   lower.includes("no substantive information") ||
                   lower.includes("only showing") ||
                   lower.includes("i'd be happy to provide") ||
                   lower.includes("if you could provide") ||
                   lower.includes("please share the details") ||
                   lower.includes("no information available");
        }}

        function normalizeText(text) {{
            return text ? text.replace(/\s+/g, ' ').trim() : '';
        }}

        function isBadTitle(title) {{
            const cleaned = normalizeText(title);
            if (!cleaned) return true;
            const lower = cleaned.toLowerCase();
            if (lower === 'unknown' || lower === 'untitled measure') return true;
            if (lower.startsWith('please note') ||
                lower.startsWith('summary date') ||
                lower.startsWith('circulation deadline') ||
                lower.startsWith('signatures required')) {{
                return true;
            }}
            if (/^[()\[\]0-9\s|:\/\.-]+$/.test(cleaned)) return true;
            return cleaned.length < 6;
        }}

        function isMetadataSummary(text) {{
            const cleaned = normalizeText(text).toLowerCase();
            if (!cleaned) return false;
            return cleaned.startsWith('summary date') ||
                   cleaned.startsWith('circulation deadline') ||
                   cleaned.startsWith('signatures required') ||
                   cleaned.startsWith('please note') ||
                   cleaned.includes('counties have') ||
                   cleaned.includes('petition to determine');
        }}

        function getInitiativeLabel(measureId) {{
            if (!measureId) return null;
            const match = measureId.match(/^INIT_(\d+)$/);
            return match ? `Initiative ${{match[1]}}` : null;
        }}

        function extractTitleFromSummary(summaryText) {{
            const cleaned = normalizeText(summaryText);
            if (!cleaned) return null;
            const match = cleaned.match(/^[^.!?]+[.!?]/);
            const sentence = match ? match[0].trim() : cleaned;
            if (sentence.length > 90) return sentence.slice(0, 87) + '...';
            return sentence;
        }}

        function getCleanTitle(measure, displayMeasureId) {{
            const rawTitle = measure.generated_title || measure.title || measure.measure_text || '';
            let title = normalizeText(rawTitle);

            if (isBadTitle(title)) {{
                if (measure.summary_title && !isAiRefusal(measure.summary_title)) {{
                    title = normalizeText(measure.summary_title);
                }} else if (measure.summary_text && !isAiRefusal(measure.summary_text)) {{
                    const summaryTitle = extractTitleFromSummary(measure.summary_text);
                    if (summaryTitle) title = summaryTitle;
                }}

                if (isBadTitle(title)) {{
                    const initLabel = getInitiativeLabel(measure.measure_id);
                    title = initLabel || displayMeasureId || 'Pending ballot measure';
                }}
            }}

            return title || 'Untitled Measure';
        }}

        function buildDisplayTitle(title, displayMeasureId) {{
            const cleanedTitle = normalizeText(title);
            if (!displayMeasureId) return cleanedTitle || 'Untitled Measure';
            if (!cleanedTitle) return displayMeasureId;
            if (cleanedTitle.toLowerCase().startsWith(displayMeasureId.toLowerCase())) {{
                return cleanedTitle;
            }}
            return `${{displayMeasureId}}: ${{cleanedTitle}}`;
        }}

        function formatDollars(n) {{
            if (n >= 1e6) return '$' + (n / 1e6).toFixed(1) + 'M';
            if (n >= 1e3) return '$' + (n / 1e3).toFixed(0) + 'K';
            return '$' + n.toLocaleString();
        }}

        function buildFinanceHTML(fd) {{
            let html = '<div class="finance-sides">';
            const sides = [{{'key': 'support', 'label': 'Support', 'cls': 'support'}}, {{'key': 'oppose', 'label': 'Oppose', 'cls': 'oppose'}}];
            sides.forEach(side => {{
                const summary = (fd.summary || []).find(s => s.stance === side.key);
                const donors = (fd.donors || []).filter(d => d.stance === side.key);
                html += '<div class="finance-side finance-side-' + side.cls + '">';
                html += '<h4>' + side.label + '</h4>';
                if (summary) {{
                    html += '<div class="finance-total">' + formatDollars(summary.total_receipts) + '</div>';
                    html += '<div class="finance-meta">' + summary.n_committees + ' committee' + (summary.n_committees !== 1 ? 's' : '') + '</div>';
                }} else {{
                    html += '<div class="finance-total">—</div>';
                }}
                if (donors.length > 0) {{
                    html += '<div class="finance-donors-list"><h4>Top Donors</h4>';
                    donors.slice(0, 5).forEach(d => {{
                        html += '<div class="finance-donor-row">' +
                            '<span class="finance-donor-name">' + d.donor_name_canon + '</span>' +
                            '<span class="finance-donor-amount">' + formatDollars(d.total_amount) + '</span>' +
                            '<span class="finance-donor-type">' + (d.donor_type || '') + '</span>' +
                        '</div>';
                    }});
                    html += '</div>';
                }}
                html += '</div>';
            }});
            html += '</div>';

            // Timeline chart
            const timeline = fd.timeline || [];
            if (timeline.length > 0) {{
                html += buildTimelineChart(timeline);
            }}

            // Contribution size breakdown
            const breakdown = fd.breakdown;
            if (breakdown) {{
                html += buildContributionBreakdown(breakdown);
            }}

            return html;
        }}

        function buildTimelineChart(timeline) {{
            // Group by week and stance
            const supportData = timeline.filter(t => t.stance === 'support');
            const opposeData = timeline.filter(t => t.stance === 'oppose');

            if (supportData.length === 0 && opposeData.length === 0) return '';

            // Find all unique weeks and max cumulative value
            const allWeeks = [...new Set(timeline.map(t => t.week_start))].sort();
            if (allWeeks.length < 2) return '';

            // Get max cumulative for scaling
            const maxCumulative = Math.max(
                ...timeline.map(t => t.cumulative_receipts || 0)
            );
            if (maxCumulative === 0) return '';

            // Sample weeks if too many (max ~60 bars per side)
            let sampledWeeks = allWeeks;
            if (allWeeks.length > 60) {{
                const step = Math.ceil(allWeeks.length / 60);
                sampledWeeks = allWeeks.filter((_, i) => i % step === 0);
            }}

            // Build bar chart
            let html = '<div class="finance-timeline">';
            html += '<h4>Fundraising Over Time (cumulative)</h4>';
            html += '<div class="finance-chart">';

            sampledWeeks.forEach(week => {{
                const sData = supportData.find(t => t.week_start === week);
                const oData = opposeData.find(t => t.week_start === week);
                const sHeight = sData ? (sData.cumulative_receipts / maxCumulative * 100) : 0;
                const oHeight = oData ? (oData.cumulative_receipts / maxCumulative * 100) : 0;

                if (sHeight > 0) {{
                    html += '<div class="finance-chart-bar support" style="height:' + sHeight + '%" title="Support: ' + formatDollars(sData.cumulative_receipts) + ' (' + week + ')"></div>';
                }}
                if (oHeight > 0) {{
                    html += '<div class="finance-chart-bar oppose" style="height:' + oHeight + '%" title="Oppose: ' + formatDollars(oData.cumulative_receipts) + ' (' + week + ')"></div>';
                }}
            }});

            html += '</div>';
            html += '<div class="finance-chart-dates"><span>' + allWeeks[0] + '</span><span>' + allWeeks[allWeeks.length - 1] + '</span></div>';
            html += '<div class="finance-chart-legend"><span class="legend-support">Support</span><span class="legend-oppose">Oppose</span></div>';
            html += '</div>';

            return html;
        }}

        function buildContributionBreakdown(breakdown) {{
            const small = breakdown.small || {{'count': 0, 'total': 0}};
            const medium = breakdown.medium || {{'count': 0, 'total': 0}};
            const large = breakdown.large || {{'count': 0, 'total': 0}};
            const mega = breakdown.mega || {{'count': 0, 'total': 0}};

            const grandTotal = small.total + medium.total + large.total + mega.total;
            const totalCount = small.count + medium.count + large.count + mega.count;

            if (grandTotal === 0) return '';

            const smallPct = (small.total / grandTotal * 100).toFixed(1);
            const mediumPct = (medium.total / grandTotal * 100).toFixed(1);
            const largePct = (large.total / grandTotal * 100).toFixed(1);
            const megaPct = (mega.total / grandTotal * 100).toFixed(1);

            // Grassroots score: weighted by small donation share (0-100)
            // Higher = more grassroots funded
            const grassrootsScore = Math.round((small.count + medium.count) / totalCount * 100);
            let grassrootsLabel = 'Mixed funding';
            if (grassrootsScore >= 80) grassrootsLabel = 'Grassroots-funded';
            else if (grassrootsScore >= 60) grassrootsLabel = 'Broad-based support';
            else if (grassrootsScore < 30) grassrootsLabel = 'Large-donor funded';

            let html = '<div class="finance-breakdown">';
            html += '<h4>Where the Money Comes From</h4>';
            html += '<div class="finance-breakdown-bar">';
            if (parseFloat(smallPct) > 0) html += '<div class="finance-breakdown-segment small" style="flex:' + smallPct + '" title="Under $100: ' + smallPct + '%"></div>';
            if (parseFloat(mediumPct) > 0) html += '<div class="finance-breakdown-segment medium" style="flex:' + mediumPct + '" title="$100-$1K: ' + mediumPct + '%"></div>';
            if (parseFloat(largePct) > 0) html += '<div class="finance-breakdown-segment large" style="flex:' + largePct + '" title="$1K-$10K: ' + largePct + '%"></div>';
            if (parseFloat(megaPct) > 0) html += '<div class="finance-breakdown-segment mega" style="flex:' + megaPct + '" title="$10K+: ' + megaPct + '%"></div>';
            html += '</div>';
            html += '<div class="finance-breakdown-legend">';
            html += '<span><span class="dot small"></span>&lt;$100 (' + smallPct + '%)</span>';
            html += '<span><span class="dot medium"></span>$100-1K (' + mediumPct + '%)</span>';
            html += '<span><span class="dot large"></span>$1K-10K (' + largePct + '%)</span>';
            html += '<span><span class="dot mega"></span>$10K+ (' + megaPct + '%)</span>';
            html += '</div>';
            html += '<div class="finance-grassroots-score">';
            html += '<span class="score-label">Grassroots Score:</span>';
            html += '<span class="score-value">' + grassrootsScore + '%</span>';
            html += '<span class="score-desc">(' + grassrootsLabel + ' — ' + totalCount.toLocaleString() + ' contributions)</span>';
            html += '</div>';
            html += '</div>';

            return html;
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
        let matrixSortCol = null;
        let matrixSortDir = 'desc';
        let currentFilters = {{
            yearMin: {stats.get('year_min', 1902)},
            yearMax: {stats.get('year_max', 2026)},
            status: [],
            features: [],
            topics: [],
            selectedYears: [],
            search: '',
            regions: [],
            county: null,
            level: null,
            levelCounty: null,
            measureTypes: []
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
            populateMeasureTypeNavigation();
            setupEventListeners();
            loadPageFromURL();
            applyFilters();
            initDuckDB();
        }});

        // DuckDB-WASM instance for SQL queries
        let duckDBConn = null;
        let duckDBReady = false;

        // Initialize DuckDB-WASM and load measures data
        async function initDuckDB() {{
            try {{
                // Dynamic import of DuckDB-WASM ES module
                const duckdb = await import('https://cdn.jsdelivr.net/npm/@duckdb/duckdb-wasm@1.28.0/+esm');

                // Get CDN bundles and select best one for this browser
                const JSDELIVR_BUNDLES = duckdb.getJsDelivrBundles();
                const bundle = await duckdb.selectBundle(JSDELIVR_BUNDLES);

                // Create worker with blob URL workaround for CORS
                const workerUrl = URL.createObjectURL(
                    new Blob([`importScripts("${{bundle.mainWorker}}");`], {{ type: 'text/javascript' }})
                );
                const worker = new Worker(workerUrl);
                const logger = new duckdb.ConsoleLogger();
                const db = new duckdb.AsyncDuckDB(logger, worker);
                await db.instantiate(bundle.mainModule, bundle.pthreadWorker);
                URL.revokeObjectURL(workerUrl);

                duckDBConn = await db.connect();

                // Create measures table
                await duckDBConn.query(`
                    CREATE TABLE measures (
                        measure_id VARCHAR,
                        title VARCHAR,
                        year INTEGER,
                        county VARCHAR,
                        topic VARCHAR,
                        display_topic VARCHAR,
                        passed INTEGER,
                        percent_yes DOUBLE,
                        total_votes BIGINT,
                        yes_votes BIGINT,
                        no_votes BIGINT,
                        data_source VARCHAR
                    )
                `);

                // Insert data in small batches with truncated strings
                const batchSize = 50;
                for (let i = 0; i < allMeasures.length; i += batchSize) {{
                    const batch = allMeasures.slice(i, i + batchSize);
                    const values = batch.map(m => {{
                        const esc = s => (s || '').substring(0, 150).replace(/'/g, "''");
                        const num = n => (n != null && !isNaN(n)) ? n : 'NULL';
                        const passed = m.passed === 1 ? 1 : m.passed === 0 ? 0 : 'NULL';
                        return `('${{esc(m.measure_id)}}','${{esc(m.title || m.concise_title)}}',${{num(m.year)}},'${{esc(m.county)}}','${{esc(m.topic_primary)}}','${{esc(m.display_topic)}}',${{passed}},${{num(m.percent_yes)}},${{num(m.total_votes)}},${{num(m.yes_votes)}},${{num(m.no_votes)}},'${{esc(m.data_source)}}')`;
                    }}).join(',');
                    await duckDBConn.query(`INSERT INTO measures VALUES ${{values}}`);
                }}

                duckDBReady = true;
                console.log('DuckDB initialized with', allMeasures.length, 'measures');
            }} catch (err) {{
                console.error('Failed to initialize DuckDB:', err);
            }}
        }}

        // Helper to escape SQL strings
        function sqlStr(val) {{
            if (val == null) return 'NULL';
            return "'" + String(val).replace(/'/g, "''") + "'";
        }}

        // Validate SQL query for safety (block dangerous operations)
        function validateSQL(sql) {{
            const upperSQL = sql.toUpperCase();
            const dangerous = ['DROP', 'DELETE', 'INSERT', 'UPDATE', 'ALTER', 'CREATE', 'TRUNCATE', 'EXEC', 'EXECUTE', 'GRANT', 'REVOKE'];
            for (const keyword of dangerous) {{
                // Check for keyword as whole word (not part of column name)
                const pattern = new RegExp('\\\\b' + keyword + '\\\\b');
                if (pattern.test(upperSQL)) {{
                    throw new Error(`Query contains disallowed keyword: ${{keyword}}`);
                }}
            }}
            // Block multiple statements
            if ((sql.match(/;/g) || []).length > 1) {{
                throw new Error('Multiple statements not allowed');
            }}
            return true;
        }}

        // Execute SQL query and return results
        async function executeDuckDBQuery(sql) {{
            if (!duckDBReady) throw new Error('Database not ready');
            try {{
                validateSQL(sql);  // Security check
                const result = await duckDBConn.query(sql);
                // Convert BigInt to Number to avoid JSON serialization issues
                return result.toArray().map(row => {{
                    const obj = row.toJSON();
                    for (const key in obj) {{
                        if (typeof obj[key] === 'bigint') {{
                            obj[key] = Number(obj[key]);
                        }}
                    }}
                    return obj;
                }});
            }} catch (err) {{
                throw new Error('SQL error: ' + err.message);
            }}
        }}

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

            // Also populate level county dropdown
            populateLevelCountyDropdown();
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
            const tab = document.querySelector(`.filter-btn[data-panel="${{panelName}}"]`);
            const allPanels = document.querySelectorAll('.accordion-panel');
            const allTabs = document.querySelectorAll('.filter-btn');

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
            // Level count
            const levelCount = (currentFilters.level ? 1 : 0) + (currentFilters.levelCounty ? 1 : 0);
            const levelBadge = document.getElementById('levelFilterCount');
            if (levelBadge) {{
                levelBadge.textContent = levelCount > 0 ? levelCount : '';
                const levelTab = document.querySelector('.filter-btn[data-panel="level"]');
                if (levelTab) {{
                    if (levelCount > 0) {{
                        levelTab.classList.add('has-selection');
                    }} else {{
                        levelTab.classList.remove('has-selection');
                    }}
                }}
            }}

            // Region count
            const regionCount = (currentFilters.regions?.length || 0) + (currentFilters.county ? 1 : 0);
            const regionBadge = document.getElementById('regionFilterCount');
            if (regionBadge) {{
                regionBadge.textContent = regionCount > 0 ? regionCount : '';
                const regionTab = document.querySelector('.filter-btn[data-panel="region"]');
                if (regionTab) {{
                    if (regionCount > 0) {{
                        regionTab.classList.add('has-selection');
                    }} else {{
                        regionTab.classList.remove('has-selection');
                    }}
                }}
            }}

            // Topic count
            const topicCount = currentFilters.topics?.length || 0;
            const topicBadge = document.getElementById('topicFilterCount');
            if (topicBadge) {{
                topicBadge.textContent = topicCount > 0 ? topicCount : '';
                const topicTab = document.querySelector('.filter-btn[data-panel="topic"]');
                if (topicTab) {{
                    if (topicCount > 0) {{
                        topicTab.classList.add('has-selection');
                    }} else {{
                        topicTab.classList.remove('has-selection');
                    }}
                }}
            }}

            // Year count
            const yearCount = currentFilters.selectedYears?.length || 0;
            const yearBadge = document.getElementById('yearFilterCount');
            if (yearBadge) {{
                yearBadge.textContent = yearCount > 0 ? yearCount : '';
                const yearTab = document.querySelector('.filter-btn[data-panel="year"]');
                if (yearTab) {{
                    if (yearCount > 0) {{
                        yearTab.classList.add('has-selection');
                    }} else {{
                        yearTab.classList.remove('has-selection');
                    }}
                }}
            }}

            // Status count
            const statusCount = currentFilters.status?.length || 0;
            const statusBadge = document.getElementById('statusFilterCount');
            if (statusBadge) {{
                statusBadge.textContent = statusCount > 0 ? statusCount : '';
                const statusTab = document.querySelector('.filter-btn[data-panel="status"]');
                if (statusTab) {{
                    if (statusCount > 0) {{
                        statusTab.classList.add('has-selection');
                    }} else {{
                        statusTab.classList.remove('has-selection');
                    }}
                }}
            }}

            // Measure type count
            const mtCount = currentFilters.measureTypes?.length || 0;
            const mtBadge = document.getElementById('measureTypeFilterCount');
            if (mtBadge) {{
                mtBadge.textContent = mtCount > 0 ? mtCount : '';
                const mtTab = document.querySelector('.filter-btn[data-panel="measureType"]');
                if (mtTab) {{
                    if (mtCount > 0) {{
                        mtTab.classList.add('has-selection');
                    }} else {{
                        mtTab.classList.remove('has-selection');
                    }}
                }}
            }}
        }}

        // Level filter (statewide vs local)
        function toggleLevelFilter(level) {{
            if (currentFilters.level === level) {{
                // Deselect
                currentFilters.level = null;
                currentFilters.levelCounty = null;
            }} else {{
                currentFilters.level = level;
                if (level !== 'local') {{
                    currentFilters.levelCounty = null;
                }}
            }}
            updateLevelChipUI();
            updateFilterCountBadges();
            pagination.currentPage = 1;
            applyFilters();
        }}

        function filterByLevelCounty(county) {{
            currentFilters.levelCounty = county || null;
            updateFilterCountBadges();
            pagination.currentPage = 1;
            applyFilters();
        }}

        function updateLevelChipUI() {{
            document.querySelectorAll('#levelCards .status-chip').forEach(chip => {{
                const level = chip.dataset.level;
                if (currentFilters.level === level) {{
                    chip.classList.add('selected');
                }} else {{
                    chip.classList.remove('selected');
                }}
            }});
            // Show/hide county dropdown when local is selected
            const countyNav = document.getElementById('levelCountyNav');
            if (countyNav) {{
                countyNav.style.display = currentFilters.level === 'local' ? 'flex' : 'none';
            }}
        }}

        function populateLevelCountyDropdown() {{
            const counties = new Set();
            allMeasures.forEach(m => {{
                if (m.county && m.county !== 'Statewide') {{
                    counties.add(m.county);
                }}
            }});
            const sorted = Array.from(counties).sort();
            const select = document.getElementById('levelCountySelect');
            if (select) {{
                select.innerHTML = '<option value="">All Local</option>' +
                    sorted.map(c => `<option value="${{c}}">${{c}} County</option>`).join('');
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

        // Measure Type icons
        const MEASURE_TYPE_ICONS = {{
            "GO Bond": "🏗️",
            "Property Tax": "🏠",
            "Sales Tax": "🛒",
            "Parcel Tax": "📐",
            "Charter Amendment": "📜",
            "Ordinance": "📋",
            "Advisory Vote": "💬",
            "Initiative": "✍️",
            "Referendum": "🗳️",
            "Recall": "🔄",
            "Bond": "💰"
        }};

        function populateMeasureTypeNavigation() {{
            const container = document.getElementById('measureTypeCards');
            const typeCounts = {{}};
            allMeasures.forEach(m => {{
                const mt = m.display_category_type || m.category_type;
                if (mt) {{
                    typeCounts[mt] = (typeCounts[mt] || 0) + 1;
                }}
            }});
            const sorted = Object.entries(typeCounts).sort((a, b) => b[1] - a[1]);
            container.innerHTML = sorted.map(([mtype, count]) => {{
                const icon = MEASURE_TYPE_ICONS[mtype] || "📌";
                const escapedType = mtype.replace(/'/g, "\\\\'");
                return `
                    <div class="measure-type-chip" data-measure-type="${{escapedType}}" onclick="toggleMeasureTypeFilter('${{escapedType}}')">
                        <span class="measure-type-chip-icon">${{icon}}</span>
                        <span class="measure-type-chip-name">${{mtype}}</span>
                        <span class="measure-type-chip-count">(${{count}})</span>
                    </div>
                `;
            }}).join('');
        }}

        function toggleMeasureTypeFilter(mtype) {{
            const index = currentFilters.measureTypes.indexOf(mtype);
            if (index === -1) {{
                currentFilters.measureTypes.push(mtype);
            }} else {{
                currentFilters.measureTypes.splice(index, 1);
            }}
            updateMeasureTypeChipUI();
            updateFilterCountBadges();
            pagination.currentPage = 1;
            applyFilters();
        }}

        function updateMeasureTypeChipUI() {{
            document.querySelectorAll('.measure-type-chip').forEach(chip => {{
                const mtype = chip.dataset.measureType;
                if (currentFilters.measureTypes.includes(mtype)) {{
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
                
                // Level filter (statewide vs local)
                if (currentFilters.level) {{
                    const isStatewide = measure.county === 'Statewide';
                    if (currentFilters.level === 'statewide' && !isStatewide) return false;
                    if (currentFilters.level === 'local' && isStatewide) return false;
                    // Sub-county filter within local
                    if (currentFilters.level === 'local' && currentFilters.levelCounty) {{
                        if (!measure.county || measure.county.toUpperCase() !== currentFilters.levelCounty.toUpperCase()) {{
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
                
                // Topic filter (uses consolidated display_topic)
                if (currentFilters.topics.length > 0) {{
                    const measureTopic = measure.display_topic || '';
                    if (!currentFilters.topics.includes(measureTopic)) {{
                        return false;
                    }}
                }}

                // Measure type filter
                if (currentFilters.measureTypes.length > 0) {{
                    const measureType = measure.display_category_type || measure.category_type || '';
                    if (!currentFilters.measureTypes.includes(measureType)) {{
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

                // Exclude upcoming/pending measures from search results
                // (they're featured in the dedicated hero section)
                // Only exclude if:
                // 1. User hasn't explicitly filtered for pending status, AND
                // 2. User hasn't explicitly selected years (if they select 2026, show pending measures)
                if (!currentFilters.status.includes('pending') && currentFilters.selectedYears.length === 0) {{
                    if (measure.passed !== 1 && measure.passed !== 0) {{
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
                (!currentFilters.measureTypes || currentFilters.measureTypes.length === 0) &&
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

        // Hero Carousel state
        let heroCarouselIndex = 0;
        let heroCarouselItemsPerView = 3;

        // Display hero measures (2026 upcoming measures) as carousel
        function displayHero() {{
            const track = document.getElementById('heroGrid');
            if (!track || heroMeasures.length === 0) return;

            track.innerHTML = heroMeasures.map(measure => createCard(measure, false, null, true)).join('');

            // Update items per view based on screen size
            updateHeroCarouselItemsPerView();

            // Reset index
            heroCarouselIndex = 0;

            // Small delay to let DOM render before calculating positions
            setTimeout(() => {{
                updateHeroCarouselDots();
                updateHeroCarouselPosition();
            }}, 50);
        }}

        function updateHeroCarouselItemsPerView() {{
            const width = window.innerWidth;
            if (width <= 640) {{
                heroCarouselItemsPerView = 1;
            }} else if (width <= 1024) {{
                heroCarouselItemsPerView = 2;
            }} else {{
                heroCarouselItemsPerView = 3;
            }}
        }}

        function getHeroCarouselMaxIndex() {{
            return Math.max(0, heroMeasures.length - heroCarouselItemsPerView);
        }}

        function heroCarouselPrev() {{
            if (heroCarouselIndex > 0) {{
                heroCarouselIndex--;
                updateHeroCarouselPosition();
                updateHeroCarouselDots();
            }}
        }}

        function heroCarouselNext() {{
            if (heroCarouselIndex < getHeroCarouselMaxIndex()) {{
                heroCarouselIndex++;
                updateHeroCarouselPosition();
                updateHeroCarouselDots();
            }}
        }}

        function heroCarouselGoTo(index) {{
            heroCarouselIndex = Math.min(getHeroCarouselMaxIndex(), Math.max(0, index));
            updateHeroCarouselPosition();
            updateHeroCarouselDots();
        }}

        function updateHeroCarouselPosition() {{
            const track = document.getElementById('heroGrid');
            if (!track) return;

            const cards = track.querySelectorAll('.measure-card');
            if (cards.length === 0) return;

            // Get card width and gap
            const card = cards[0];
            const cardWidth = card.offsetWidth;
            const trackStyle = window.getComputedStyle(track);
            const gap = parseInt(trackStyle.gap) || 20;

            const offset = heroCarouselIndex * (cardWidth + gap);
            track.style.transform = `translateX(-${{offset}}px)`;

            // Update button states
            const prevBtn = document.querySelector('.carousel-prev');
            const nextBtn = document.querySelector('.carousel-next');
            if (prevBtn) prevBtn.disabled = heroCarouselIndex === 0;
            if (nextBtn) nextBtn.disabled = heroCarouselIndex >= getHeroCarouselMaxIndex();
        }}

        function updateHeroCarouselDots() {{
            const dotsContainer = document.getElementById('heroCarouselDots');
            if (!dotsContainer) return;

            const maxIndex = getHeroCarouselMaxIndex();

            // Don't show dots if everything fits
            if (maxIndex <= 0) {{
                dotsContainer.innerHTML = '';
                return;
            }}

            let dotsHTML = '';
            for (let i = 0; i <= maxIndex; i++) {{
                dotsHTML += `<button class="carousel-dot ${{i === heroCarouselIndex ? 'active' : ''}}" onclick="heroCarouselGoTo(${{i}})" aria-label="Go to slide ${{i + 1}}"></button>`;
            }}
            dotsContainer.innerHTML = dotsHTML;
        }}

        // Update carousel on window resize
        let resizeTimeout;
        window.addEventListener('resize', () => {{
            clearTimeout(resizeTimeout);
            resizeTimeout = setTimeout(() => {{
                const prevItemsPerView = heroCarouselItemsPerView;
                updateHeroCarouselItemsPerView();
                heroCarouselIndex = Math.min(heroCarouselIndex, getHeroCarouselMaxIndex());
                updateHeroCarouselPosition();
                updateHeroCarouselDots();
            }}, 100);
        }});

        // Display featured measures (curated selection)
        function displayFeatured() {{
            const grid = document.getElementById('featuredGrid');
            grid.innerHTML = featuredMeasures.map(measure => createCard(measure, true, measure._featuredReason)).join('');
        }}
        
        // Display paginated results
        // ── Explore Matrix ──────────────────────────────
        // Modern color scale: warm red (low pass) → cool teal (high pass)
        function matrixCellColor(passed, total) {{
            if (total < 1) return 'transparent';
            const rate = passed / total;
            // Colors: #E54D4D (red, 0%) → #F0A030 (amber, 50%) → #2D9D78 (teal, 100%)
            let r, g, b;
            if (rate < 0.5) {{
                // Red to amber
                const t = rate * 2;
                r = Math.round(229 + (240 - 229) * t);
                g = Math.round(77 + (160 - 77) * t);
                b = Math.round(77 + (48 - 77) * t);
            }} else {{
                // Amber to teal
                const t = (rate - 0.5) * 2;
                r = Math.round(240 + (45 - 240) * t);
                g = Math.round(160 + (157 - 160) * t);
                b = Math.round(48 + (120 - 48) * t);
            }}
            return `rgb(${{r}}, ${{g}}, ${{b}})`;
        }}

        let matrixRowMode = 'count'; // 'count' | 'alpha' | 'rate'
        let matrixColField = 'topic'; // 'topic' | 'measureType'

        function renderMatrix() {{
            // Determine which field to use for columns based on toggle
            const colFieldKey = matrixColField === 'measureType' ? 'display_category_type' : 'display_topic';
            const colLabel = matrixColField === 'measureType' ? 'measure types' : 'topics';

            const valid = filteredMeasures.filter(m =>
                m[colFieldKey] && (m.passed === 1 || m.passed === 0)
            );

            if (valid.length === 0) {{
                return `<div class="empty-state">
                    <div class="empty-icon">📊</div>
                    <h3>No outcome data</h3>
                    <p>Adjust filters to include measures with pass/fail results</p>
                </div>`;
            }}

            // Build sets
            const topicSet = new Set();
            const countySet = new Set();
            valid.forEach(m => {{
                topicSet.add(m[colFieldKey]);
                countySet.add(m.county || 'Unknown');
            }});

            // Sort columns by total count descending
            const topicCounts = {{}};
            valid.forEach(m => {{
                const t = m[colFieldKey];
                topicCounts[t] = (topicCounts[t] || 0) + 1;
            }});
            const topics = [...topicSet].sort((a, b) => (topicCounts[b] || 0) - (topicCounts[a] || 0));

            // Build matrix
            const matrix = {{}};
            const colTotals = {{}};
            const rowTotals = {{}};
            topics.forEach(t => colTotals[t] = {{passed: 0, total: 0}});

            valid.forEach(m => {{
                const c = m.county || 'Unknown';
                const t = m[colFieldKey];
                if (!matrix[c]) matrix[c] = {{}};
                if (!matrix[c][t]) matrix[c][t] = {{passed: 0, total: 0}};
                matrix[c][t].total++;
                matrix[c][t].passed += m.passed;
                if (!rowTotals[c]) rowTotals[c] = {{passed: 0, total: 0}};
                rowTotals[c].total++;
                rowTotals[c].passed += m.passed;
                colTotals[t].total++;
                colTotals[t].passed += m.passed;
            }});

            // Sort counties
            let counties = [...countySet];
            if (matrixSortCol && colTotals[matrixSortCol]) {{
                counties.sort((a, b) => {{
                    const ac = (matrix[a] && matrix[a][matrixSortCol]) || {{passed:0, total:0}};
                    const bc = (matrix[b] && matrix[b][matrixSortCol]) || {{passed:0, total:0}};
                    const ar = ac.total > 0 ? ac.passed / ac.total : -1;
                    const br = bc.total > 0 ? bc.passed / bc.total : -1;
                    return matrixSortDir === 'desc' ? br - ar : ar - br;
                }});
            }} else if (matrixRowMode === 'alpha') {{
                counties.sort((a, b) => a.localeCompare(b));
            }} else if (matrixRowMode === 'rate') {{
                counties.sort((a, b) => {{
                    const ar = rowTotals[a]?.total > 0 ? rowTotals[a].passed / rowTotals[a].total : -1;
                    const br = rowTotals[b]?.total > 0 ? rowTotals[b].passed / rowTotals[b].total : -1;
                    return br - ar;
                }});
            }} else {{
                counties.sort((a, b) => (rowTotals[b]?.total || 0) - (rowTotals[a]?.total || 0));
            }}

            // Build HTML
            let html = '<div class="matrix-wrapper">';

            // Toolbar with info, column toggle, row sort, and legend
            html += `<div class="matrix-toolbar">
                <span>${{valid.length.toLocaleString()}} measures with outcomes · ${{counties.length}} jurisdictions × ${{topics.length}} ${{colLabel}}</span>
                <div class="matrix-col-toggle">
                    <button class="${{matrixColField === 'topic' ? 'active' : ''}}" onclick="setMatrixColField('topic')">Topic</button>
                    <button class="${{matrixColField === 'measureType' ? 'active' : ''}}" onclick="setMatrixColField('measureType')">Measure Type</button>
                </div>
                <label>Sort rows:
                    <select onchange="setMatrixRowSort(this.value)">
                        <option value="count" ${{matrixRowMode==='count'?'selected':''}}>By count</option>
                        <option value="alpha" ${{matrixRowMode==='alpha'?'selected':''}}>A–Z</option>
                        <option value="rate" ${{matrixRowMode==='rate'?'selected':''}}>By pass rate</option>
                    </select>
                </label>
                <div class="matrix-legend">
                    <span class="matrix-legend-label">Low</span>
                    <div class="matrix-legend-bar">
                        <span style="background:#E54D4D"></span>
                        <span style="background:#EA7A3F"></span>
                        <span style="background:#F0A030"></span>
                        <span style="background:#7CB86A"></span>
                        <span style="background:#2D9D78"></span>
                    </div>
                    <span class="matrix-legend-label">High</span>
                    <span style="opacity:0.5; margin-left:8px; color:#666;">●</span><span style="color:#888;font-size:0.7rem;margin-left:2px;">n&lt;3</span>
                </div>
            </div>`;
            html += '<div class="matrix-scroll"><table class="matrix-table" role="grid">';

            // Header
            html += '<thead><tr>';
            const jSortCls = !matrixSortCol ? 'sorted-desc' : '';
            html += `<th class="${{jSortCls}}" role="button" tabindex="0"
                onclick="sortMatrixByRow()" onkeydown="if(event.key==='Enter')sortMatrixByRow()">Jurisdiction</th>`;
            topics.forEach(t => {{
                const cls = matrixSortCol === t ? (matrixSortDir === 'asc' ? 'sorted-asc' : 'sorted-desc') : '';
                const escaped = t.replace(/'/g, "\\\\'");
                html += `<th class="${{cls}}" role="button" tabindex="0"
                    onclick="sortMatrixByCol('${{escaped}}')"
                    onkeydown="if(event.key==='Enter')sortMatrixByCol('${{escaped}}')"
                    title="${{t}}">${{t}}</th>`;
            }});
            html += '<th>All</th></tr></thead>';

            // Body
            html += '<tbody>';
            counties.forEach(county => {{
                const rt = rowTotals[county] || {{passed:0, total:0}};
                const rowRate = rt.total > 0 ? Math.round(100 * rt.passed / rt.total) : 0;
                const cEsc = county.replace(/'/g, "\\\\'");
                html += `<tr><td role="button" tabindex="0"
                    onclick="exploreFilterToCounty('${{cEsc}}')"
                    onkeydown="if(event.key==='Enter')exploreFilterToCounty('${{cEsc}}')"
                    >${{county}} <span class="cell-count">(${{rt.total}})</span></td>`;
                topics.forEach(t => {{
                    const cell = (matrix[county] && matrix[county][t]) || {{passed:0, total:0}};
                    if (cell.total === 0) {{
                        html += '<td class="matrix-cell empty-cell">—</td>';
                    }} else {{
                        const rate = Math.round(100 * cell.passed / cell.total);
                        const bg = matrixCellColor(cell.passed, cell.total);
                        const low = cell.total < 3;
                        const tEsc = t.replace(/'/g, "\\\\'");
                        const label = `${{county}}, ${{t}}: ${{rate}}% passed (${{cell.passed}} of ${{cell.total}})${{low ? ' — small sample' : ''}}`;
                        html += `<td class="matrix-cell ${{low ? 'low-conf' : ''}}" style="background:${{bg}}"
                            role="button" tabindex="0"
                            onclick="matrixCellClick('${{cEsc}}','${{tEsc}}')"
                            onkeydown="if(event.key==='Enter')matrixCellClick('${{cEsc}}','${{tEsc}}')"
                            title="${{label}}" aria-label="${{label}}">
                            ${{low
                                ? `<span class="cell-rate">n=${{cell.total}}</span>`
                                : `<span class="cell-rate">${{rate}}%</span><span class="cell-count">${{cell.total}}</span>`
                            }}
                        </td>`;
                    }}
                }});
                // Row total
                html += `<td class="matrix-cell" style="background:${{matrixCellColor(rt.passed, rt.total)}}">
                    <span class="cell-rate">${{rowRate}}%</span><span class="cell-count">${{rt.total}}</span></td>`;
                html += '</tr>';
            }});

            // Totals row
            const gt = {{passed:0, total:0}};
            html += '<tr class="matrix-totals"><td>All</td>';
            topics.forEach(t => {{
                const ct = colTotals[t];
                gt.passed += ct.passed;
                gt.total += ct.total;
                const rate = ct.total > 0 ? Math.round(100 * ct.passed / ct.total) : 0;
                html += `<td><span class="cell-rate">${{rate}}%</span><span class="cell-count">${{ct.total}}</span></td>`;
            }});
            html += `<td><span class="cell-rate">${{gt.total > 0 ? Math.round(100*gt.passed/gt.total) : 0}}%</span><span class="cell-count">${{gt.total}}</span></td>`;
            html += '</tr></tbody></table></div></div>';

            return html;
        }}

        function sortMatrixByCol(topic) {{
            if (matrixSortCol === topic) {{
                matrixSortDir = matrixSortDir === 'desc' ? 'asc' : 'desc';
            }} else {{
                matrixSortCol = topic;
                matrixSortDir = 'desc';
            }}
            displayResults();
        }}

        function sortMatrixByRow() {{
            matrixSortCol = null;
            displayResults();
        }}

        function setMatrixRowSort(mode) {{
            matrixRowMode = mode;
            matrixSortCol = null;
            displayResults();
        }}

        function setMatrixColField(field) {{
            matrixColField = field;
            matrixSortCol = null;
            displayResults();
        }}

        function matrixCellClick(county, colValue) {{
            // Set the appropriate filter based on which column mode is active
            if (matrixColField === 'measureType') {{
                currentFilters.measureTypes = [colValue];
                updateMeasureTypeChipUI();
            }} else {{
                currentFilters.topics = [colValue];
                updateTopicChipUI();
            }}
            if (county !== 'Statewide') {{
                currentFilters.level = 'local';
                currentFilters.levelCounty = county;
            }} else {{
                currentFilters.level = 'statewide';
                currentFilters.levelCounty = null;
            }}
            setView('grid');
            updateLevelChipUI();
            updateFilterCountBadges();
            applyFilters();
        }}

        function exploreFilterToCounty(county) {{
            if (county !== 'Statewide') {{
                currentFilters.level = 'local';
                currentFilters.levelCounty = county;
            }} else {{
                currentFilters.level = 'statewide';
                currentFilters.levelCounty = null;
            }}
            setView('grid');
            updateLevelChipUI();
            updateFilterCountBadges();
            applyFilters();
        }}

        function displayResults() {{
            const container = document.getElementById('resultsContainer');

            // Explore matrix view
            if (currentView === 'explore') {{
                container.innerHTML = renderMatrix();
                return;
            }}

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

        // Timeline stages for ballot measures
        const MEASURE_STAGES = ['Filed', 'Circulating', 'Qualified', 'On Ballot', 'Voted'];

        function getMeasureStage(measure) {{
            // Determine stage from source_url and status
            const url = (measure.source_url || '').toLowerCase();
            const passed = measure.passed;

            if (passed === 1 || passed === 0) return 4; // Voted
            if (url.includes('qualified-ballot-measures')) return 3; // On Ballot (qualified)
            if (url.includes('25percent') || url.includes('circulating')) return 1; // Circulating
            if (url.includes('cleared-circulation') || url.includes('cleared')) return 0; // Filed/Cleared
            if (url.includes('failed-qualify')) return 1; // Got stuck at circulating

            // For legislative measures (ACA, SCA, SB, AB), "qualified" = on ballot
            const mid = (measure.measure_id || '');
            if (mid.startsWith('ACA_') || mid.startsWith('SCA_') || mid.startsWith('SB_') || mid.startsWith('AB_')) {{
                return 2; // Legislative measures go straight to qualified
            }}
            // Initiatives with INIT_ prefix that are on the qualified page
            if (mid.startsWith('INIT_')) return 1; // Default: circulating

            return 0; // Unknown → filed
        }}

        function renderTimeline(measure) {{
            const stage = getMeasureStage(measure);
            let html = '<div class="measure-timeline">';
            for (let i = 0; i < MEASURE_STAGES.length; i++) {{
                const cls = i < stage ? 'completed' : (i === stage ? 'active' : '');
                html += `<div class="timeline-step ${{cls}}">`;
                html += `<div class="timeline-dot"></div>`;
                if (i < MEASURE_STAGES.length - 1) {{
                    html += `<div class="timeline-line"></div>`;
                }}
                html += `</div>`;
            }}
            html += '</div>';
            html += '<div class="timeline-labels">';
            for (let i = 0; i < MEASURE_STAGES.length; i++) {{
                const cls = i === stage ? 'active' : '';
                html += `<div class="timeline-label ${{cls}}">${{MEASURE_STAGES[i]}}</div>`;
            }}
            html += '</div>';
            return html;
        }}

        // Get human-readable measure designation (e.g., "Measure A", "Prop 36")
        function getDisplayMeasureId(measure) {{
            const mid = measure.measure_id || '';
            const letter = measure.measure_letter || '';
            const county = measure.county || '';

            // For statewide measures, parse the measure_id
            if (county === 'Statewide' || !county) {{
                // Already readable formats: PROP_36 -> "Prop 36", ACA_13 -> "ACA 13"
                if (mid.startsWith('PROP_')) return 'Prop ' + mid.replace('PROP_', '');
                if (mid.startsWith('ACA_')) return 'ACA ' + mid.replace('ACA_', '');
                if (mid.startsWith('SCA_')) return 'SCA ' + mid.replace('SCA_', '');
                if (mid.startsWith('SB_')) return 'SB ' + mid.replace('SB_', '');
                if (mid.startsWith('AB_')) return 'AB ' + mid.replace('AB_', '');
                if (mid.startsWith('INIT_')) return null; // Don't show INIT_ prefix, just use title
                // If measure_id is already clean (like "Prop 36" or a number), return null
                return null;
            }}

            // For county measures, use measure_letter if available
            if (letter) {{
                // Handle recall measures (letter is a number like "1", "2")
                if (/^\d+$/.test(letter)) return null; // Don't prefix recall numbers
                // Regular letters: "A", "B", "AA", etc.
                return 'Measure ' + letter;
            }}

            // If measure_id is not a CEDA numeric ID, it might be usable
            if (mid && !/^\d{{9,}}$/.test(mid)) {{
                return mid;
            }}

            return null; // No displayable ID
        }}

        // Create card HTML - simplified, cleaner design
        function createCard(measure, featured = false, featuredReason = null, isHero = false) {{
            // Use generated title if available, otherwise fall back to original
            const displayMeasureId = getDisplayMeasureId(measure);
            const title = getCleanTitle(measure, displayMeasureId);
            const displayTitle = buildDisplayTitle(title, displayMeasureId);
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
            if (measure.summary_text && measure.summary_text.length > 50 && !isAiRefusal(measure.summary_text) &&
                !(isPending && isMetadataSummary(measure.summary_text))) {{
                summary = measure.summary_text;
            }} else if (measure.ballot_question && measure.ballot_question.length > 50) {{
                summary = measure.ballot_question;
            }} else if (measure.description && !(isPending && isMetadataSummary(measure.description))) {{
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
            const displayMeasureId = getDisplayMeasureId(measure);
            const title = getCleanTitle(measure, displayMeasureId);
            const displayTitle = buildDisplayTitle(title, displayMeasureId);
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

            // Populate header - use human-readable measure ID
            document.getElementById('modalMeasureId').textContent = getDisplayMeasureId(measure) || '';
            document.getElementById('modalYear').textContent = measure.year || '';

            // Title
            const title = getCleanTitle(measure, getDisplayMeasureId(measure));
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
            if (measure.display_category_type || measure.category_type) {{
                badgesHtml.push(`<span class="badge badge-neutral">${{measure.display_category_type || measure.category_type}}</span>`);
            }}
            if (measure.category_topic) {{
                badgesHtml.push(`<span class="badge badge-neutral">${{measure.category_topic}}</span>`);
            }}
            document.getElementById('modalBadges').innerHTML = badgesHtml.join('');

            // Timeline for pending measures
            const timelineSection = document.getElementById('modalTimelineSection');
            if (isPending) {{
                timelineSection.style.display = 'block';
                document.getElementById('modalTimeline').innerHTML = renderTimeline(measure);
            }} else {{
                timelineSection.style.display = 'none';
            }}

            // Summary - with pending-specific messaging and truncation for long text
            const summaryEl = document.getElementById('modalSummary');
            const summaryToggle = document.getElementById('summaryToggle');
            let summaryText = '';

            if (measure.summary_text && !isAiRefusal(measure.summary_text) &&
                !(isPending && isMetadataSummary(measure.summary_text))) {{
                summaryText = measure.summary_text;
                summaryEl.classList.remove('no-summary-text');
            }} else if (measure.description && !(isPending && isMetadataSummary(measure.description))) {{
                summaryText = measure.description;
                summaryEl.classList.remove('no-summary-text');
            }} else if (isPending) {{
                summaryText = `<div class="pending-info-text">
                    <strong>📋 Coming Soon:</strong> Full measure details, including the official ballot language,
                    fiscal impact analysis, and arguments for and against, will be available as we approach the election.
                </div>`;
                summaryEl.classList.remove('no-summary-text');
            }} else {{
                summaryText = 'No summary available for this measure.';
                summaryEl.classList.add('no-summary-text');
            }}

            summaryEl.innerHTML = summaryText;

            // Show "Show more" toggle for long summaries (>400 chars)
            if (summaryText.length > 400) {{
                summaryEl.classList.add('truncated');
                summaryToggle.style.display = 'inline-block';
                summaryToggle.textContent = 'Show more';
            }} else {{
                summaryEl.classList.remove('truncated');
                summaryToggle.style.display = 'none';
            }}

            // Results section - hide for pending measures
            const resultsSection = document.getElementById('modalResultsSection');
            if (measure.percent_yes != null && measure.yes_votes != null && !isPending) {{
                const percentNo = 100 - measure.percent_yes;
                resultsSection.style.display = 'block';
                document.getElementById('modalYesBar').style.width = measure.percent_yes + '%';
                document.getElementById('modalYesLabel').textContent = `Yes: ${{measure.yes_votes?.toLocaleString() || 0}} (${{measure.percent_yes?.toFixed(1) || 0}}%)`;
                document.getElementById('modalNoLabel').textContent = `No: ${{measure.no_votes?.toLocaleString() || 0}} (${{percentNo.toFixed(1)}}%)`;
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

                    const relatedDisplayId = getDisplayMeasureId(relatedMeasure);
                    return `
                        <div class="related-card" onclick="viewMeasure(allMeasures.find(m => m.measure_id === '${{rec.measure_id}}'))">
                            <div class="related-header">
                                <span class="related-id">${{relatedDisplayId || relatedMeasure.county || ''}}</span>
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

            // Money & Coalition section
            const financeSection = document.getElementById('modalFinanceSection');
            const financeContent = document.getElementById('modalFinanceContent');
            const fd = financeData[measure.measure_id];
            if (fd) {{
                financeContent.innerHTML = buildFinanceHTML(fd);
                financeSection.style.display = 'block';
            }} else {{
                financeSection.style.display = 'none';
            }}

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

        // Toggle summary truncation
        function toggleSummary() {{
            const summaryEl = document.getElementById('modalSummary');
            const toggle = document.getElementById('summaryToggle');
            if (summaryEl.classList.contains('truncated')) {{
                summaryEl.classList.remove('truncated');
                toggle.textContent = 'Show less';
            }} else {{
                summaryEl.classList.add('truncated');
                toggle.textContent = 'Show more';
            }}
        }}

        // Set view mode
        function setView(view) {{
            currentView = view;
            // Update header view buttons (legacy)
            document.querySelectorAll('.view-btn').forEach(btn => btn.classList.remove('active'));
            const headerBtn = document.getElementById(view + 'View');
            if (headerBtn) headerBtn.classList.add('active');
            // Update view switcher cards
            document.querySelectorAll('.view-card').forEach(card => card.classList.remove('active'));
            const viewCard = document.getElementById(view + 'ViewCard');
            if (viewCard) viewCard.classList.add('active');
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
                county: null,
                level: null,
                levelCounty: null,
                measureTypes: []
            }};

            // Reset pagination
            pagination.currentPage = 1;

            // Reset UI
            document.getElementById('searchInput').value = '';
            document.getElementById('countySelect').value = '';
            const levelCountySelect = document.getElementById('levelCountySelect');
            if (levelCountySelect) levelCountySelect.value = '';
            updateFilterUI();
            updateTopicChipUI();
            updateYearChipUI();
            updateStatusChipUI();
            updateRegionChipUI();
            updateLevelChipUI();
            updateMeasureTypeChipUI();
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
            document.querySelectorAll('.filter-btn').forEach(tab => {{
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
            document.getElementById('quizAnswer').innerHTML = '<p>' + escapeHtml(q.answer) + '</p>';
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
                            model: 'claude-sonnet-4-20250514',
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

        // Database schema for LLM context
        const DB_SCHEMA = `
Table: measures (${allMeasures.length} rows)
Columns:
  - measure_id (VARCHAR): Unique identifier like "PROP_36", "MEASURE_A", etc.
  - title (VARCHAR): Full title/description of the measure
  - year (INTEGER): Election year (1998-2026)
  - county (VARCHAR): "Statewide" for propositions, or county name for local measures
  - topic (VARCHAR): Detailed topic category
  - display_topic (VARCHAR): Consolidated topic (~15 categories): Taxes & Revenue, Education, Public Safety, Healthcare, Environment, Housing, Transportation, Government Reform, Labor & Employment, Civil Rights, Cannabis, Water, Business Regulation, Social Services, Other
  - passed (INTEGER): 1=passed, 0=failed, NULL=pending/upcoming
  - percent_yes (DOUBLE): Percentage of yes votes (0-100)
  - total_votes (BIGINT): Total votes cast
  - yes_votes (BIGINT): Number of yes votes
  - no_votes (BIGINT): Number of no votes
  - description (VARCHAR): Longer description text
  - data_source (VARCHAR): Where the data came from

Sample values:
  - Counties include: Statewide, Los Angeles, San Francisco, San Diego, Alameda, etc. (58 counties)
  - Years range from 1998 to 2026
  - About 199 statewide propositions, 12,000+ local measures
`;

        // Query AI using text-to-SQL approach
        async function queryAI(question) {
            if (!duckDBReady) {
                return "The database is still loading. Please try again in a moment.";
            }

            // Step 1: Ask LLM to generate SQL
            const sqlPrompt = `You are a SQL expert helping analyze California ballot measures data.

${DB_SCHEMA}

User question: ${question}

Generate a DuckDB SQL query to answer this question. Return ONLY the SQL query, no explanation.
- Use standard SQL syntax compatible with DuckDB
- Limit results to 20 rows max unless counting/aggregating
- For "surprising" or "interesting" results, consider: measures that narrowly passed/failed (percent_yes near 50), high-spending measures that failed, topics with unusual pass rates, etc.
- Use display_topic for topic analysis (cleaner categories)
- Remember: passed=1 means passed, passed=0 means failed, passed IS NULL means pending`;

            let sql;
            try {
                sql = await callLLM(sqlPrompt);
                // Clean up the SQL (remove markdown code blocks if present)
                sql = sql.replace(/```sql\\n?/gi, '').replace(/```\\n?/g, '').trim();
                // Remove any trailing semicolons for safety
                sql = sql.replace(/;\\s*$/, '');
            } catch (err) {
                return "Error generating query: " + err.message;
            }

            // Step 2: Execute SQL in DuckDB
            let results;
            try {
                results = await executeDuckDBQuery(sql);
            } catch (err) {
                // If SQL fails, ask LLM to fix it or explain
                return `I tried to query the database but encountered an error. The query was:\\n\\n\`${sql}\`\\n\\nError: ${err.message}\\n\\nPlease try rephrasing your question.`;
            }

            // Step 3: Ask LLM to summarize results
            const summaryPrompt = `You analyzed California ballot measures data with this SQL query:

\`\`\`sql
${sql}
\`\`\`

Results (${results.length} rows):
${JSON.stringify(results, null, 2)}

Original question: ${question}

Provide a clear, insightful answer based on these results. Include specific examples with measure names and years. If the results reveal interesting patterns or surprising findings, highlight them.`;

            // Format results as a compact table for display
            const formatResultsTable = (rows) => {{
                if (!rows || rows.length === 0) return 'No results';
                const keys = Object.keys(rows[0]);
                const lines = rows.slice(0, 15).map(row => {{
                    return keys.map(k => {{
                        let v = row[k];
                        if (v === null) return '-';
                        if (typeof v === 'number') return Number.isInteger(v) ? v.toLocaleString() : v.toFixed(2);
                        if (typeof v === 'string' && v.length > 40) return v.substring(0, 37) + '...';
                        return v;
                    }}).join(' | ');
                }});
                const header = keys.join(' | ');
                const moreRows = rows.length > 15 ? '\\n... and ' + (rows.length - 15) + ' more rows' : '';
                return header + '\\n' + '-'.repeat(header.length) + '\\n' + lines.join('\\n') + moreRows;
            }};

            // Build "show your work" section
            const workSection = '**Query:**\\n```sql\\n' + sql + '\\n```\\n\\n' +
                '**Results (' + results.length + ' rows):**\\n```\\n' + formatResultsTable(results) + '\\n```\\n\\n---\\n\\n';

            try {{
                const summary = await callLLM(summaryPrompt);
                return workSection + '**Analysis:**\\n\\n' + summary;
            }} catch (err) {{
                // Fallback: return just the work section if summary fails
                return workSection + '(Summary generation failed: ' + err.message + ')';
            }}
        }

        // Generic LLM call using configured provider
        async function callLLM(prompt) {
            if (aiConfig.provider === 'openai') {
                return await callOpenAI(prompt);
            } else if (aiConfig.provider === 'anthropic') {
                return await callAnthropic(prompt);
            } else if (aiConfig.provider === 'ollama') {
                return await callOllama(prompt);
            }
            throw new Error('No AI provider configured');
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
                    max_tokens: 1024
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
                    model: 'claude-sonnet-4-20250514',
                    max_tokens: 1024,
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
            // First escape HTML to prevent XSS, then apply markdown formatting
            let safeText = escapeHtml(text);

            // Handle code blocks first (```...```)
            let html = safeText.replace(/```(sql|\\w*)?\\n([\\s\\S]*?)```/g, (match, lang, code) => {
                return `<pre class="chat-code-block"><code>${code.trim()}</code></pre>`;
            });

            // Handle inline code (`...`)
            html = html.replace(/`([^`]+)`/g, '<code class="chat-inline-code">$1</code>');

            // Split into paragraphs (but preserve pre blocks)
            html = html
                .split('\\n\\n')
                .map(para => {
                    if (para.startsWith('<pre')) return para;
                    return `<p>${para.replace(/\\n/g, '<br>')}</p>`;
                })
                .join('');

            // Bold text
            html = html.replace(/\\*\\*(.*?)\\*\\*/g, '<strong>$1</strong>');

            // Horizontal rule
            html = html.replace(/<p>---<\\/p>/g, '<hr class="chat-divider">');

            return html;
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
