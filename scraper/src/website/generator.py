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
        
        # Save to the deployable copy (root of repo, served by GitHub Pages).
        self.output_path.write_text(html, encoding='utf-8')
        logger.info(f"Website generated: {self.output_path}")

        # Also save a scraper-local copy at scraper/index.html for local
        # testing (per scraper/Makefile). Only write if it would actually be a
        # second location — avoid overwriting the deploy copy when output_path
        # has already been pointed at scraper/index.html explicitly.
        scraper_local = BASE_DIR / 'index.html'
        if scraper_local.resolve() != self.output_path.resolve():
            scraper_local.write_text(html, encoding='utf-8')
            logger.info(f"Also saved to: {scraper_local}")
        
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
        """Load finance data from the finance DB if it exists.

        Rolls up by measure_db_id rather than finance_campaign_id so the
        Bucket A year-offset recoveries (multiple campaigns linked to one
        measure) merge into a single measure-level view in the modal.
        Otherwise the late-filing recovery campaign would silently shadow
        the on-cycle campaign on output. See aggregate_for_measure() in
        src/finance/operations.py for the merge semantics.
        """
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
            # Collect distinct measure_db_ids across all matched campaigns,
            # then aggregate per measure. The output is keyed on
            # str(measure_db_id) so the client-side lookup
            # `financeData[String(measure.id)]` resolves cleanly.
            seen_measure_ids: set = set()
            for campaign in fdb.get_all_campaigns():
                mid = campaign.get("measure_db_id")
                if mid is not None:
                    seen_measure_ids.add(int(mid))
            result: Dict[str, Dict] = {}
            for mid in seen_measure_ids:
                rollup = fdb.aggregate_for_measure(mid, donor_limit=20)
                if not rollup:
                    continue
                result[str(mid)] = {
                    "finance_campaign_id": rollup["finance_campaign_id"],
                    "all_campaign_ids": rollup["all_campaign_ids"],
                    "summary": rollup["summary"],
                    "donors": rollup["donors"],
                    "timeline": rollup["timeline"],
                    "breakdown": rollup["breakdown"],
                }
            fdb.close()
            logger.info(
                f"Loaded finance data for {len(result)} measures "
                f"(rolled up from {sum(len(r['all_campaign_ids']) for r in result.values())} campaigns)"
            )
            return result
        except Exception as e:
            logger.warning(f"Could not load finance data: {e}")
            return {}

    def _load_insights_data(self) -> Dict:
        """Load compact precomputed Insights data."""
        insights_path = BASE_DIR / "data" / "insights.json"
        if not insights_path.exists():
            logger.info("Insights data not found, skipping Insights payload")
            return {}
        try:
            with open(insights_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            logger.info(f"Loaded Insights data from {insights_path}")
            return payload
        except Exception as e:
            logger.warning(f"Could not load Insights data: {e}")
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

        # Load compact analysis payload if available
        insights_data = self._load_insights_data()
        insights_json = json.dumps(insights_data, default=str)

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
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.8/dist/chart.umd.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/d3@7/dist/d3.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/topojson-client@3/dist/topojson-client.min.js"></script>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" crossorigin=""/>
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script>
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
                <button class="view-btn" id="insightsView" onclick="setView('insights')" title="Insights: reported analysis from the data">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                        <rect x="4" y="12" width="3" height="8" rx="1"></rect>
                        <rect x="10.5" y="7" width="3" height="13" rx="1"></rect>
                        <rect x="17" y="3" width="3" height="17" rx="1"></rect>
                    </svg>
                    Insights
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
                <button class="view-card" id="insightsViewCard" onclick="setView('insights')">
                    <div class="view-card-icon">
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
                            <rect x="4" y="12" width="3.5" height="8" rx="1"></rect>
                            <rect x="10.25" y="7" width="3.5" height="13" rx="1"></rect>
                            <rect x="16.5" y="3" width="3.5" height="17" rx="1"></rect>
                        </svg>
                    </div>
                    <div class="view-card-text">
                        <span class="view-card-title">Insights</span>
                        <span class="view-card-desc">Reported analysis from the full dataset</span>
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

            <!-- Insights Section -->
            <section class="insights-view" id="insightsSection" style="display: none;">
                <div class="insights-kicker">Analysis</div>
                <div class="insights-hero">
                    <div>
                        <h2>What California ballot measures reveal</h2>
                        <p>
                            A reported-analysis view of the full CalBallot dataset: what voters approve,
                            where the ballot is busiest, which rules turn majorities into losses, and where
                            campaign money does and doesn&rsquo;t decide statewide fights.
                        </p>
                    </div>
                    <div class="insights-method-card">
                        <span class="method-label">Dataset</span>
                        <strong id="insightsDatasetLabel">Active, non-duplicate measures</strong>
                        <span id="insightsGeneratedLabel">Precomputed analysis payload</span>
                    </div>
                </div>

                <div class="insights-analysis-shell">
                    <nav class="insights-side-nav" aria-label="Insights sections">
                        <span>Sections</span>
                        <a href="#insightsOverview" class="active">Overview</a>
                        <a href="#insightsKeyFindings">Key Findings</a>
                        <a href="#insightsTrendPanel">Trend</a>
                        <a href="#insightsTopicsPanel">Topics</a>
                        <a href="#insightsTypesPanel">Measure Types</a>
                        <a href="#insightsGeographyPanel">Geography</a>
                        <a href="#insightsRulesPanel">Rules</a>
                        <a href="#insightsFinanceSection">Finance</a>
                        <a href="#insightsMethodologySection">Methodology</a>
                    </nav>

                    <div class="insights-analysis-content">
                <div class="insights-carousel" id="insightsCarousel">
                    <button class="insights-carousel-arrow insights-carousel-arrow-prev" onclick="moveInsightsSlide(-1)" aria-label="Previous insight">
                        <span aria-hidden="true">&lsaquo;</span>
                    </button>
                    <div class="insights-carousel-viewport">
                        <div class="insights-carousel-track" id="insightsCarouselTrack">
                <section class="insights-carousel-slide insights-anchor-target" id="insightsOverview">
                    <div class="insights-metrics" id="insightsMetrics"></div>
                    <div class="insights-overview-composition" id="insightsComposition"></div>
                    <div class="insights-overview-sparkline" id="insightsSparkline">
                        <div class="insights-overview-sparkline-header">
                            <h4>Activity over time</h4>
                            <button class="overview-jump-btn" onclick="jumpToInsightsPanel('insightsTrendPanel')">Open trend &rarr;</button>
                        </div>
                        <div class="chart-wrap"><canvas id="insightsOverviewSparkChart"></canvas></div>
                    </div>
                    <div class="insights-overview-tops" id="insightsOverviewTops"></div>
                    <div class="insights-overview-coverage" id="insightsCoverage"></div>
                </section>

                <section class="insights-carousel-slide insights-anchor-target insights-key-findings" id="insightsKeyFindings">
                    <div class="key-findings-article" id="insightsFindings"></div>
                </section>

                    <article class="insight-panel insight-panel-wide insights-carousel-slide insights-anchor-target" id="insightsTrendPanel">
                        <div class="panel-heading">
                            <div>
                                <span class="panel-eyebrow">Trend</span>
                                <h3>Ballot activity rises and falls with election cycles</h3>
                            </div>
                        </div>
                        <p class="panel-deck">Annual counts, decade composition, and election-cycle patterns show when California voters faced the heaviest measure load.</p>
                        <div id="trendInsightSummary" class="mini-callouts"></div>
                        <div class="analysis-chart-grid">
                            <div class="chart-module chart-module-wide">
                                <h4>Annual volume and pass rate</h4>
                                <div class="chart-wrap"><canvas id="insightsYearChart"></canvas></div>
                            </div>
                            <div class="chart-module">
                                <h4>Local measures per year (5-yr avg)</h4>
                                <div class="chart-wrap compact"><canvas id="insightsLocalTrendChart"></canvas></div>
                                <p class="chart-footnote">Shown from 1990 forward; CEDA local coverage begins in the 1990s. See the Annual chart above for the full historical arc.</p>
                            </div>
                            <div class="chart-module">
                                <h4>Statewide measures per year (5-yr avg)</h4>
                                <div class="chart-wrap compact"><canvas id="insightsStatewideTrendChart"></canvas></div>
                                <p class="chart-footnote">Shown from 1990 forward to align with local. Statewide propositions are tracked back to 1911 in the Annual chart above.</p>
                            </div>
                            <div class="chart-module">
                                <h4>Avg. measures per year by cycle</h4>
                                <div class="chart-wrap compact"><canvas id="insightsElectionCycleChart"></canvas></div>
                            </div>
                            <div class="chart-module">
                                <h4>Pass rate by cycle</h4>
                                <div class="chart-wrap compact"><canvas id="insightsElectionCyclePassRateChart"></canvas></div>
                            </div>
                        </div>
                        <p class="method-note">Method: active records by election year. Trend fits are descriptive and not coverage-adjusted.</p>
                    </article>

                    <article class="insight-panel insights-carousel-slide insights-anchor-target" id="insightsTopicsPanel">
                        <div class="panel-heading">
                            <div>
                                <span class="panel-eyebrow">Topics</span>
                                <h3>The issue mix is broad, but unevenly classified</h3>
                            </div>
                        </div>
                        <p class="panel-deck">How the issue mix has shifted over time across the most consistently classified topic categories.</p>
                        <div class="analysis-chart-grid single-column">
                            <div class="chart-module">
                                <h4>Topic share by decade</h4>
                                <div class="chart-wrap compact"><canvas id="insightsTopicTrendChart"></canvas></div>
                            </div>
                        </div>
                        <div id="topicEraStrip" class="topic-era-strip"></div>
                        <div id="topicPassRateRankings" class="topic-pass-rate-rankings"></div>
                        <p class="method-note">Method: shares and rankings use topic-classified records only (Other is excluded). Local CEDA records are better analyzed by measure type.</p>
                    </article>

                    <article class="insight-panel insights-carousel-slide insights-anchor-target" id="insightsTypesPanel">
                        <div class="panel-heading">
                            <div>
                                <span class="panel-eyebrow">Measure Types</span>
                                <h3>Fiscal tools dominate the local ballot</h3>
                            </div>
                        </div>
                        <p class="panel-deck">Measure type is the cleaner lens for CEDA-heavy local records.</p>
                        <div class="analysis-chart-grid single-column">
                            <div class="chart-module">
                                <h4>Largest measure types</h4>
                                <div class="chart-wrap compact"><canvas id="insightsTypeChart"></canvas></div>
                            </div>
                            <div class="chart-module">
                                <h4>Fiscal share over time</h4>
                                <div class="chart-wrap compact"><canvas id="insightsFiscalTrendChart"></canvas></div>
                                <p class="chart-footnote">Shown from 1990 forward. Bond, sales tax, and property tax are local-ballot instruments tracked through CEDA; pre-1990 the dataset is statewide-only and these labels do not apply.</p>
                            </div>
                        </div>
                        <div class="type-insights-stack">
                            <section class="type-insights-section" id="typeModernAnatomy"></section>
                            <section class="type-insights-section" id="typeFiscalProfiles"></section>
                            <section class="type-insights-section" id="typeThresholdProfiles"></section>
                            <section class="type-insights-section" id="typeRecallCallout"></section>
                        </div>
                        <p class="method-note">Method: normalized category type from source records. Threshold mixes use derived threshold fields.</p>
                    </article>

                    <article class="insight-panel insight-panel-wide insights-carousel-slide insights-anchor-target" id="insightsGeographyPanel">
                        <div class="panel-heading">
                            <div>
                                <span class="panel-eyebrow">Geography</span>
                                <h3>The map of ballot activity is not evenly distributed</h3>
                            </div>
                        </div>
                        <p class="panel-deck">County totals reflect local-government density and source coverage. They are not population adjusted.</p>
                        <div class="geography-anchor-cards" id="regionInsightSummary"></div>
                        <div class="geography-toolbar">
                            <div class="toolbar-group" role="group" aria-label="Color by">
                                <span class="toolbar-label">Color by</span>
                                <button class="toolbar-btn active" data-geo-color="count" onclick="setGeographyColor('count')">Count</button>
                                <button class="toolbar-btn" data-geo-color="passRate" onclick="setGeographyColor('passRate')">Pass rate</button>
                            </div>
                        </div>
                        <div class="county-map-layout">
                            <div id="californiaCountyMap" class="county-map"></div>
                            <div class="county-map-side">
                                <h4>Busiest counties</h4>
                                <div id="countyLeaderboard"></div>
                            </div>
                        </div>
                        <p class="method-note">Method: active local records grouped by normalized county name. Map geometry loads from the public us-atlas county topology.</p>
                    </article>

                    <article class="insight-panel insights-carousel-slide insights-anchor-target" id="insightsRulesPanel">
                        <div class="panel-heading">
                            <div>
                                <span class="panel-eyebrow">Rules</span>
                                <h3>Thresholds can turn majorities into losses</h3>
                            </div>
                        </div>
                        <p class="panel-deck">A 55% or two-thirds contest is a different world than a simple-majority one. Same yes share, very different legal outcome.</p>
                        <div class="rules-hero" id="rulesHero"></div>
                        <div class="rules-chart-wrap">
                            <h4 class="rules-section-h">Outcome share by threshold</h4>
                            <div class="chart-wrap"><canvas id="insightsThresholdChart"></canvas></div>
                            <p class="chart-footnote">Each bar runs from 0% to 100% of decided records at that threshold. The grey segment is normal failures (didn&rsquo;t reach majority); the red segment is measures that crossed 50% yes but still failed under the higher rule.</p>
                        </div>
                        <div id="rulesThresholdTable"></div>
                        <div id="rulesLandmarks"></div>
                        <div id="rulesPlainEnglish"></div>
                        <div id="rulesBridge"></div>
                        <p class="method-note">Method: pass/fail codes and derived vote-threshold fields. Threshold assignment is selected (mostly by instrument), not random &mdash; so rate gaps below describe the contests, not voter mood. Known edge cases remain under review.</p>
                    </article>

                    <article class="insight-panel insight-panel-wide insights-carousel-slide insights-anchor-target" id="insightsFinanceSection">
                        <div class="panel-heading">
                            <div>
                                <span class="panel-eyebrow">Campaign Finance</span>
                                <h3>Statewide proposition campaigns have drawn billions</h3>
                            </div>
                            <span class="confidence-badge">Statewide only</span>
                        </div>
                        <p class="panel-deck">Finance coverage is intentionally scoped to matched statewide propositions from CalAccess. Each campaign is keyed by election cycle, so receipts attributed to the 2020 PROP_16 are the 2020 measure&rsquo;s, not the 2010 reuse of the same proposition number.</p>

                        <div id="financeInsightSummary" class="mini-callouts finance-summary-callouts"></div>

                        <section class="finance-module">
                            <div class="finance-module-header">
                                <h4>How much money has flowed</h4>
                                <p id="financeArcSubdeck">Total receipts grouped by election cycle. Bars include both support and oppose receipts.</p>
                            </div>
                            <div class="finance-arc-toggle" role="tablist" aria-label="Spending arc view">
                                <button type="button"
                                        class="finance-arc-mode is-active"
                                        data-mode="election"
                                        role="tab"
                                        aria-selected="true">By election cycle</button>
                                <button type="button"
                                        class="finance-arc-mode"
                                        data-mode="calendar"
                                        role="tab"
                                        aria-selected="false">By calendar year</button>
                            </div>
                            <div class="chart-wrap finance-arc-chart"><canvas id="financeAnnualChart"></canvas></div>
                        </section>

                        <section class="finance-module">
                            <div class="finance-module-header">
                                <h4>The donors who showed up</h4>
                                <p>The single most absent thing on the old panel: the names. Both lists below aggregate the per-campaign top-donor reports &mdash; not every transaction, but the donors big enough to land in a campaign&rsquo;s top-20.</p>
                            </div>
                            <div class="finance-donors-grid">
                                <div>
                                    <h5 class="finance-subhead">Top 15 by aggregated receipts</h5>
                                    <p class="finance-subdeck">Donors with the largest total dollars across all campaigns where they appeared in the top-20.</p>
                                    <ol id="financeTopDonors" class="finance-donor-list"></ol>
                                </div>
                                <div>
                                    <h5 class="finance-subhead">Repeat players</h5>
                                    <p class="finance-subdeck">Donors that landed in the top-20 of 3+ campaigns with $1M+ aggregate &mdash; the policy actors, not the one-off industry fights.</p>
                                    <ol id="financeRepeatDonors" class="finance-donor-list"></ol>
                                </div>
                            </div>
                        </section>

                        <section class="finance-module">
                            <div class="finance-module-header">
                                <h4>Three fights, three industries</h4>
                                <p>Curated case studies across gig work, gambling, and healthcare. Top 5 donors per side; concentration line below each card.</p>
                            </div>
                            <div id="financeMarqueeFights" class="finance-marquee-grid"></div>
                        </section>

                        <p class="finance-bridge">Money matters but isn&rsquo;t decisive: the better-funded side wins about 65% of the time and loses the other 35%. And this is the visible top of the iceberg &mdash; California&rsquo;s local ballot has tens of thousands of measures with no comparable donor data.</p>

                        <p class="method-note">Method: receipts include itemized monetary contributions to recipient committees tagged with the prop&rsquo;s CAL-ACCESS ballot number. Independent expenditures, in-kind contributions, loans, and contributions to untagged side-committees are not captured &mdash; our totals therefore run lower than press citations (e.g. Ballotpedia) that combine those scopes. We measure verifiable monetary inflow to the official committees, not total campaign spending. Per-(prop_num, election_year) aggregates from finance_statewide_v2.db (rebuilt 2026-05-12 with row-level date hygiene, cross-filing exact-row dedupe on (committee, donor, date, amount), and minimal donor alias normalization). The spending-arc chart offers two lenses: election-cycle (totals per measure&rsquo;s actual election year, the substantive frame for ballot-measure campaigns) and calendar-year (totals per Monday-of-week bucket of accepted weekly receipts, useful for cash-flow timing). The calendar view groups boundary weeks by their week-start year, so a transaction in the week of 2007-12-31 is attributed to 2007 even though it&rsquo;s for the 2008 cycle. Donor lists aggregate the per-campaign top-20 reports, not all transactions &mdash; a donor below the top-20 cutoff in every campaign won&rsquo;t appear here. Sector labels are hand-curated for prominent visible donors; unlabeled donors are not assigned a sector. Donor canonicalization is partial; some entities still appear under multiple legal-entity variants.</p>
                    </article>

                <details class="insights-methodology insights-carousel-slide insights-anchor-target" id="insightsMethodologySection">
                    <summary>How these insights were calculated</summary>
                    <div id="insightsMethodology"></div>
                </details>
                        </div>
                    </div>
                    <button class="insights-carousel-arrow insights-carousel-arrow-next" onclick="moveInsightsSlide(1)" aria-label="Next insight">
                        <span aria-hidden="true">&rsaquo;</span>
                    </button>
                </div>
                <div class="insights-carousel-status" id="insightsCarouselStatus">1 / 9</div>
                    </div>
                </div>
            </section>

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

                <div class="active-filter-summary" id="activeFilterSummary" style="display: none;" aria-live="polite">
                    <div class="active-filter-summary-header">
                        <span>Active filters</span>
                        <button type="button" onclick="clearAllFilters()">Clear all</button>
                    </div>
                    <div class="active-filter-chips" id="activeFilterChips"></div>
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
                    <label class="settings-label">Provider</label>
                    <select id="aiProvider" class="settings-select" onchange="updateProviderFields()">
                        <option value="">Select provider...</option>
                        <option value="openrouter">OpenRouter (100+ models)</option>
                        <option value="ollama">Local Ollama (free, offline)</option>
                    </select>
                </div>

                <div id="openrouterSection" class="settings-section" style="display: none;">
                    <label class="settings-label">OpenRouter API Key</label>
                    <input type="password" id="apiKey" class="settings-input" placeholder="sk-or-...">
                    <p class="settings-hint">Get a free key at <a href="https://openrouter.ai/keys" target="_blank">openrouter.ai/keys</a>. You pay model costs directly — no markup.</p>
                    <label class="settings-label">Model</label>
                    <select id="openrouterModel" class="settings-select">
                        <option value="anthropic/claude-sonnet-4">Claude Sonnet 4 (~$0.003/query)</option>
                        <option value="anthropic/claude-haiku-4">Claude Haiku 4 (~$0.001/query)</option>
                        <option value="openai/gpt-4o">GPT-4o (~$0.005/query)</option>
                        <option value="openai/gpt-4o-mini">GPT-4o Mini (~$0.001/query)</option>
                        <option value="google/gemini-2.5-flash">Gemini 2.5 Flash (~$0.001/query)</option>
                        <option value="deepseek/deepseek-chat-v3">DeepSeek V3 (~$0.001/query)</option>
                        <option value="meta-llama/llama-4-scout">Llama 4 Scout (free)</option>
                    </select>
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

    <!-- Matrix Cell Detail Modal -->
    <div id="matrixCellModal" class="modal" style="display: none;" onclick="closeMatrixCellModal()">
        <div class="modal-content matrix-cell-modal" onclick="event.stopPropagation()" style="max-width:480px;">
            <div class="modal-header">
                <h3 id="matrixCellTitle" style="margin:0;font-size:1.1rem;"></h3>
                <button class="modal-close" onclick="closeMatrixCellModal()">&times;</button>
            </div>
            <div class="modal-body" id="matrixCellBody" style="padding:1rem;">
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
                <!-- Fixed header (always visible) -->
                <h2 id="modalTitle" class="measure-detail-title"></h2>
                <div id="modalJurisdiction" class="measure-detail-jurisdiction"></div>
                <div class="measure-detail-badges" id="modalBadges"></div>

                <!-- Tab navigation — dictionary/planner style -->
                <div class="modal-tab-container">
                    <div class="modal-tabs">
                        <button class="modal-tab active" data-tab="main" onclick="switchModalTab('main')">Main</button>
                        <button class="modal-tab" data-tab="research" onclick="switchModalTab('research')">Research</button>
                        <button class="modal-tab" data-tab="finance" onclick="switchModalTab('finance')">Finance</button>
                    </div>

                    <!-- TAB: Main -->
                    <div class="modal-tab-panel active" id="tabMain">
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
                    </div>

                    <!-- TAB: Research -->
                    <div class="modal-tab-panel" id="tabResearch">
                        <div id="modalBriefingSection" class="measure-detail-section" style="display: none;">
                            <h3>📋 Research Briefing <span class="info-tip" data-tip="An AI-generated summary synthesizing official sources, historical context, and key facts about this measure. Produced by CalBallot's research agent.">i</span></h3>
                            <div id="modalBriefingContent"></div>
                        </div>

                        <div id="modalHistoricalContextSection" class="measure-detail-section">
                            <div id="modalHistoricalContext"></div>
                        </div>

                        <div id="modalResearchEmpty" class="measure-detail-section" style="display:none;">
                            <p style="color:var(--text-tertiary);font-style:italic;">No research data available for this measure yet. Research briefings are generated for upcoming and recent measures.</p>
                        </div>
                    </div>

                    <!-- TAB: Finance -->
                    <div class="modal-tab-panel" id="tabFinance">
                        <div id="modalFinanceSection" class="measure-detail-section" style="display: none;">
                            <h3>💰 Money &amp; Coalition</h3>
                            <div id="modalFinanceContent" class="measure-detail-finance"></div>
                        </div>
                        <div id="modalFinanceEmpty" class="measure-detail-section" style="display:none;">
                            <p style="color:var(--text-tertiary);font-style:italic;">No campaign finance data available for this measure. (Finance coverage is statewide-only; local measures aren&rsquo;t in CAL-ACCESS.)</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        {self._get_javascript(measures_json, topics_json, recommendations_json, stats, quiz_json, finance_json, insights_json)}
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
            margin: 0 0 1rem;
            border-radius: 10px;
            background: #FDFCFA;
            border: 1px solid #E5E0D8;
            box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        }
        .matrix-toolbar {
            display: flex;
            gap: 0.5rem 0.7rem;
            padding: 0.55rem 0.75rem;
            border-bottom: 1px solid #E5E0D8;
            align-items: center;
            flex-wrap: wrap;
            background: #F8F6F3;
            border-radius: 10px 10px 0 0;
            font-size: 0.82rem;
        }
        .matrix-toolbar > span:first-child {
            flex: 1 1 280px;
            min-width: 240px;
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
            padding: 0.28rem 1.6rem 0.28rem 0.45rem;
            font-size: 0.76rem;
            cursor: pointer;
            transition: border-color 0.2s;
        }
        .matrix-toolbar label {
            align-items: center;
            display: inline-flex;
            gap: 0.35rem;
            white-space: nowrap;
        }
        .matrix-toolbar select:hover {
            border-color: var(--primary);
        }
        .matrix-reset-btn {
            background: #FFFDF8;
            border: 1px solid #D8CEBB;
            border-radius: 6px;
            color: #5F5647;
            cursor: pointer;
            font-size: 0.76rem;
            font-weight: 700;
            padding: 0.32rem 0.55rem;
            transition: background 0.15s ease, border-color 0.15s ease, color 0.15s ease;
        }
        .matrix-reset-btn:hover {
            background: #FFFFFF;
            border-color: var(--primary);
            color: #111;
        }
        .matrix-insight-strip {
            display: grid;
            gap: 0.65rem;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            padding: 0.75rem;
            border-bottom: 1px solid #E5E0D8;
            background: #FFFDF8;
        }
        .matrix-insight-card {
            border: 1px solid #E6DDCC;
            border-radius: 8px;
            background: #FFFFFF;
            padding: 0.7rem 0.8rem;
            min-width: 0;
        }
        .matrix-insight-card span {
            color: #756B5B;
            display: block;
            font-size: 0.68rem;
            font-weight: 800;
            letter-spacing: 0.04em;
            margin-bottom: 0.3rem;
            text-transform: uppercase;
        }
        .matrix-insight-card strong {
            color: #16120B;
            display: block;
            font-size: 0.95rem;
            line-height: 1.18;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        .matrix-insight-card em {
            color: #6F6656;
            display: block;
            font-size: 0.74rem;
            font-style: normal;
            margin-top: 0.28rem;
        }
        .matrix-toolbar-group {
            align-items: center;
            display: inline-flex;
            gap: 0.35rem;
            white-space: nowrap;
        }
        .matrix-toolbar-group-label {
            color: #6F6656;
            font-size: 0.68rem;
            font-weight: 800;
            letter-spacing: 0.04em;
            text-transform: uppercase;
        }
        .matrix-legend {
            display: flex;
            align-items: center;
            gap: 0.35rem;
            margin-left: 0;
            font-size: 0.68rem;
            color: #888;
        }
        .matrix-legend-label {
            color: #666;
        }
        .matrix-legend-bar {
            display: flex;
            height: 10px;
            width: 78px;
            border-radius: 6px;
            overflow: hidden;
            box-shadow: inset 0 1px 2px rgba(0,0,0,0.1);
        }
        .matrix-legend-bar span { flex: 1; }
        .matrix-top-scroll {
            height: 16px;
            overflow-x: auto;
            overflow-y: hidden;
            border-bottom: 1px solid #E5E0D8;
            background: #FDFCFA;
        }
        .matrix-top-scroll-inner {
            height: 1px;
            min-width: 100%;
        }
        .matrix-scroll {
            height: clamp(460px, calc(100vh - 250px), 760px);
            overflow: auto;
        }
        .matrix-wrapper.matrix-compact .matrix-scroll {
            height: auto;
            max-height: calc(100vh - 230px);
        }
        .matrix-table {
            border-collapse: separate;
            border-spacing: 2px;
            font-size: 0.74rem;
            min-width: 100%;
            padding: 0.45rem;
        }
        .matrix-table th,
        .matrix-table td {
            padding: 0.36rem 0.5rem;
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
            font-size: 0.64rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.03em;
            padding-bottom: 0.45rem;
            vertical-align: bottom;
        }
        .matrix-table tfoot th {
            background: #FDFCFA;
            color: #666;
            font-size: 0.64rem;
            font-weight: 600;
            letter-spacing: 0.03em;
            padding-top: 0.45rem;
            text-transform: uppercase;
        }
        .matrix-table thead th:hover { color: var(--primary); }
        .matrix-table tfoot th:hover { color: var(--primary); }
        .matrix-table thead th.sorted-asc::after { content: ' ↑'; color: var(--primary); }
        .matrix-table thead th.sorted-desc::after { content: ' ↓'; color: var(--primary); }
        .matrix-table thead th:first-child,
        .matrix-table tfoot th:first-child,
        .matrix-table td:first-child {
            position: sticky;
            left: 0;
            z-index: 3;
            text-align: left;
            min-width: 138px;
            background: #FDFCFA;
        }
        .matrix-table tfoot th:first-child {
            z-index: 2;
        }
        .matrix-table td:first-child {
            font-weight: 600;
            color: #333;
            z-index: 1;
            font-size: 0.76rem;
            padding-left: 0.4rem;
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
            min-width: 68px;
            border-radius: 6px;
            transition: transform 0.15s, box-shadow 0.15s;
            padding: 0.28rem 0.42rem !important;
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
        .matrix-cell.limited-conf {
            opacity: 0.82;
        }
        .matrix-cell.low-conf .cell-rate {
            font-size: 0.7rem;
        }
        .matrix-cell .cell-note {
            display: block;
            font-size: 0.54rem;
            font-weight: 700;
            color: rgba(255,255,255,0.82);
            margin-top: 1px;
        }
        .matrix-cell .cell-rate {
            font-weight: 700;
            font-size: 0.82rem;
            color: #fff;
            text-shadow: 0 1px 2px rgba(0,0,0,0.2);
            display: block;
        }
        .matrix-cell .cell-count {
            font-size: 0.56rem;
            color: rgba(255,255,255,0.75);
            display: block;
            margin-top: 1px;
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
        .matrix-modal-metrics {
            display: grid;
            gap: 0.6rem;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            margin-bottom: 1rem;
        }
        .matrix-modal-metric {
            background: #F8F6F3;
            border: 1px solid #E5E0D8;
            border-radius: 8px;
            padding: 0.65rem;
            text-align: center;
        }
        .matrix-modal-metric strong {
            display: block;
            font-size: 1.1rem;
            line-height: 1.1;
        }
        .matrix-modal-metric span {
            color: #756B5B;
            display: block;
            font-size: 0.68rem;
            font-weight: 700;
            margin-top: 0.25rem;
        }
        .matrix-modal-section {
            border-top: 1px solid #EEE7DA;
            padding-top: 0.85rem;
            margin-top: 0.85rem;
        }
        .matrix-modal-section h4 {
            font-size: 0.78rem;
            margin: 0 0 0.55rem;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            color: #6F6656;
        }
        .matrix-modal-list-item {
            border-bottom: 1px solid #EEE7DA;
            font-size: 0.8rem;
            padding: 0.48rem 0;
        }
        .matrix-modal-list-item:last-child {
            border-bottom: none;
        }
        .matrix-modal-list-item span {
            color: #756B5B;
            display: block;
            font-size: 0.72rem;
            margin-top: 0.15rem;
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
            padding: 1rem 1.5rem 2rem;
        }

        .content-full {
            min-height: 100vh;
        }

        /* View Switcher */
        .view-switcher {
            display: none;
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
                display: none;
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
            display: none;
            text-align: center;
            padding: 0.75rem 1rem 1rem;
            margin-bottom: 0.75rem;
        }

        .intro-title {
            font-size: 1.35rem;
            font-weight: 700;
            color: var(--text-primary);
            margin-bottom: 0.35rem;
        }

        .intro-text {
            font-size: 0.9rem;
            line-height: 1.45;
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
            border: 1px solid var(--border-color);
            border-radius: 10px;
            padding: 0.8rem 1rem;
            margin-bottom: 0.8rem;
            box-shadow: var(--shadow-sm);
            display: flex;
            align-items: center;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 0.75rem;
        }
        
        .results-info {
            display: flex;
            align-items: baseline;
            gap: 0.7rem;
        }
        
        .results-count {
            font-size: 1.25rem;
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
            border-radius: 10px;
            padding: 0.55rem 1rem;
            margin-bottom: 0.8rem;
            box-shadow: var(--shadow-sm);
        }

        .stats-ribbon-inner {
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 1rem;
            flex-wrap: wrap;
        }

        .stat-item {
            display: flex;
            flex-direction: column;
            align-items: center;
            min-width: 72px;
        }

        .stat-value {
            font-size: 1.16rem;
            font-weight: 700;
            color: var(--primary);
            line-height: 1.2;
        }

        .stat-label {
            font-size: 0.62rem;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-top: 0.12rem;
        }

        .stat-divider {
            width: 1px;
            height: 28px;
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
            border-radius: 10px;
            padding: 0.9rem 1rem;
            margin-bottom: 0.9rem;
            box-shadow: var(--shadow-sm);
        }

        .filter-header-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0.7rem;
            flex-wrap: wrap;
            gap: 0.7rem;
        }

        .filter-title {
            font-size: 1rem;
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
            justify-content: flex-start;
            gap: 0.5rem;
            flex-wrap: wrap;
        }

        .filter-btn {
            display: flex;
            align-items: center;
            gap: 0.45rem;
            padding: 0.55rem 0.8rem;
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.2s ease;
            font-size: 0.82rem;
            color: var(--text-primary);
            font-weight: 500;
            min-width: auto;
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
            font-size: 0.95rem;
        }

        .filter-btn-label {
            font-weight: 500;
        }

        .filter-btn-count {
            background: var(--bg-tertiary);
            color: var(--text-secondary);
            font-size: 0.68rem;
            font-weight: 600;
            padding: 0.1rem 0.35rem;
            border-radius: 10px;
            min-width: 16px;
            text-align: center;
        }

        .filter-btn.active .filter-btn-count {
            background: rgba(255, 255, 255, 0.25);
            color: white;
        }

        .active-filter-summary {
            border-top: 1px solid var(--border-color);
            margin-top: 0.8rem;
            padding-top: 0.75rem;
        }

        .active-filter-summary-header {
            align-items: center;
            display: flex;
            justify-content: space-between;
            gap: 0.75rem;
            margin-bottom: 0.55rem;
        }

        .active-filter-summary-header span {
            color: var(--text-secondary);
            font-size: 0.74rem;
            font-weight: 700;
            letter-spacing: 0.06em;
            text-transform: uppercase;
        }

        .active-filter-summary-header button {
            background: transparent;
            border: 0;
            color: var(--primary-dark);
            cursor: pointer;
            font-size: 0.78rem;
            font-weight: 700;
            padding: 0.2rem 0;
        }

        .active-filter-summary-header button:hover {
            color: var(--error);
            text-decoration: underline;
        }

        .active-filter-chips {
            display: flex;
            flex-wrap: wrap;
            gap: 0.45rem;
        }

        .active-filter-chip {
            align-items: center;
            background: #fffdfa;
            border: 1px solid #d9cda5;
            border-radius: 999px;
            color: var(--text-primary);
            display: inline-flex;
            gap: 0.35rem;
            max-width: 100%;
            min-height: 30px;
            padding: 0.28rem 0.38rem 0.28rem 0.65rem;
        }

        .active-filter-chip strong {
            color: var(--text-tertiary);
            font-size: 0.68rem;
            font-weight: 800;
            letter-spacing: 0.04em;
            text-transform: uppercase;
        }

        .active-filter-chip span {
            font-size: 0.8rem;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }

        .active-filter-chip button {
            align-items: center;
            background: rgba(0,0,0,0.06);
            border: 0;
            border-radius: 999px;
            color: var(--text-secondary);
            cursor: pointer;
            display: inline-flex;
            font-size: 0.95rem;
            height: 20px;
            justify-content: center;
            line-height: 1;
            padding: 0;
            width: 20px;
        }

        .active-filter-chip button:hover {
            background: var(--error);
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

            .active-filter-summary-header {
                align-items: flex-start;
                flex-direction: column;
                gap: 0.35rem;
            }
        }

        /* Card Styles — modest density pass (2026-05-12 v2):
         * Original structure preserved (header / title / description /
         * progress bar / meta) but with tightened whitespace. The v1 cut
         * description from normal cards entirely; that felt stripped-down
         * and lost too much information density. v2 keeps everything and
         * just tightens spacing. */
        .measure-card {
            background: var(--bg-primary);
            border-radius: var(--radius);
            padding: 0.85rem 1rem;
            box-shadow: var(--shadow-sm);
            transition: all 0.2s ease;
            cursor: pointer;
            display: flex;
            flex-direction: column;
            gap: 0.4rem;
            border: 1px solid #E8E2D4;
            min-height: 140px;
        }

        .measure-card:hover {
            box-shadow: 0 6px 20px rgba(26,23,20,.1);
            transform: translateY(-2px);
            border-color: var(--primary);
        }

        /* Hero / featured cards get visual distinction via gold border +
         * background gradient, NOT via heavier internal sizing — internal
         * layout matches normal v2 cards so the homepage reads as a
         * unified rhythm rather than mixed densities. */
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
            margin-bottom: 0.25rem;
        }

        .card-year {
            font-size: 0.85rem;
            font-weight: 600;
            color: var(--text-secondary);
        }

        .badge {
            padding: 0.28rem 0.6rem;
            border-radius: var(--radius-sm);
            font-size: 0.72rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.025em;
            display: inline-flex;
            align-items: center;
            gap: 0.32rem;
        }

        .badge::before {
            content: '';
            width: 5px;
            height: 5px;
            border-radius: 50%;
            display: inline-block;
        }

        .badge-passed {
            background: rgba(58, 140, 40, 0.12);
            color: #2D6A1E;
            border: 1px solid rgba(58, 140, 40, 0.25);
        }
        .badge-passed::before { background: #2D6A1E; }

        .badge-failed {
            background: rgba(192, 57, 43, 0.12);
            color: #A0302A;
            border: 1px solid rgba(192, 57, 43, 0.25);
        }
        .badge-failed::before { background: #C0392B; }

        .badge-pending {
            background: rgba(201, 162, 60, 0.15);
            color: #8A6D14;
            border: 1px solid rgba(201, 162, 60, 0.3);
        }
        .badge-pending::before { background: #C9A23C; }

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
            font-size: 1rem;
            font-weight: 600;
            color: var(--text-primary);
            line-height: 1.35;
            margin: 0 0 0.15rem 0;
            display: -webkit-box;
            -webkit-line-clamp: 3;
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

        /* Card summary — the description paragraph below the title.
         * Slightly tighter than v1 (smaller font, less vertical margin)
         * to claw back ~15-20% of card height while keeping the info.
         * Applied uniformly across normal / hero / featured variants. */
        .card-summary {
            font-size: 0.83rem;
            color: var(--text-secondary);
            line-height: 1.45;
            margin: 0.1rem 0 0.25rem 0;
            display: -webkit-box;
            -webkit-line-clamp: 2;
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
            font-size: 0.76rem;
            color: var(--text-tertiary);
            line-height: 1.35;
            margin-top: 0.35rem;
        }

        .vote-bar {
            height: 5px;
            background: rgba(0, 0, 0, 0.08);
            border-radius: 3px;
            overflow: hidden;
            margin: 0.4rem 0 0.1rem;
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

        /* Grid View — modest density gain (280px -> 260px). */
        .results-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
            gap: 0.75rem;
        }
        @media (max-width: 899px) and (min-width: 640px) {
            .results-grid {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
        }
        @media (max-width: 639px) {
            .results-grid {
                grid-template-columns: 1fr;
            }
            .measure-card {
                padding: 0.75rem 0.85rem;
            }
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

        /* Dictionary/planner-style tabs */
        .modal-tab-container {
            position: relative;
            margin-top: 0.75rem;
        }

        .modal-tabs {
            display: flex;
            gap: 0;
            border-bottom: 2px solid var(--border);
            margin-bottom: 0;
        }

        .modal-tab {
            position: relative;
            padding: 0.5rem 1.2rem;
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-bottom: none;
            border-radius: 8px 8px 0 0;
            cursor: pointer;
            font-size: 0.85rem;
            font-weight: 500;
            color: var(--text-secondary);
            transition: var(--transition);
            margin-right: -1px;
        }

        .modal-tab:hover {
            background: var(--bg-primary);
            color: var(--text-primary);
        }

        .modal-tab.active {
            background: var(--bg-primary);
            color: var(--primary);
            border-color: var(--border);
            border-bottom: 2px solid var(--bg-primary);
            margin-bottom: -2px;
            z-index: 1;
            font-weight: 600;
        }

        .modal-tab-panel {
            display: none;
            padding-top: 0.75rem;
            min-height: 400px;
        }

        .modal-tab-panel.active {
            display: block;
        }

        /* Info tooltip icon */
        .info-tip {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 16px;
            height: 16px;
            border-radius: 50%;
            background: #4a90c2;
            color: white;
            font-size: 10px;
            font-weight: 700;
            font-style: normal;
            cursor: help;
            margin-left: 5px;
            vertical-align: middle;
            position: relative;
            flex-shrink: 0;
        }
        .info-tip::after {
            content: attr(data-tip);
            position: absolute;
            bottom: calc(100% + 6px);
            left: 50%;
            transform: translateX(-50%);
            background: #333;
            color: #fff;
            font-size: 0.72rem;
            font-weight: 400;
            padding: 6px 10px;
            border-radius: 6px;
            white-space: normal;
            width: 220px;
            text-align: left;
            line-height: 1.4;
            pointer-events: none;
            opacity: 0;
            transition: opacity 0.15s;
            z-index: 100;
        }
        .info-tip:hover::after {
            opacity: 1;
        }

        .measure-detail-links {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 0.4rem;
        }

        .measure-detail-links a {
            display: flex;
            align-items: center;
            gap: 0.4rem;
            color: var(--primary);
            text-decoration: none;
            font-size: 0.82rem;
            padding: 0.45rem 0.6rem;
            border-radius: 6px;
            border: 1px solid var(--border);
            background: var(--bg-primary);
            transition: var(--transition);
            line-height: 1.3;
        }

        .measure-detail-links a:hover {
            background: var(--bg-secondary);
            border-color: var(--primary);
        }

        .measure-detail-links a .link-label {
            font-weight: 600;
        }

        .measure-detail-links a .link-source {
            color: var(--text-tertiary);
            font-size: 0.75rem;
        }

        .measure-detail-links a.link-low-confidence {
            opacity: 0.65;
        }

        /* Full-width items (context blocks, disclaimers) */
        .measure-detail-links .pending-context,
        .measure-detail-links .pending-disclaimer {
            grid-column: 1 / -1;
        }

        @media (max-width: 480px) {
            .measure-detail-links {
                grid-template-columns: 1fr;
            }
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

        /* Unified filter option system */
        .filter-section-wrapper .panel-content {
            background: #F4F0E6;
            border: 1px solid #E4DBC8;
            border-radius: 10px;
            padding: 1rem 1.1rem;
        }

        .filter-section-wrapper .panel-hint {
            color: #6F6656;
            font-size: 0.78rem;
            margin: 0 0 0.85rem;
            text-align: center;
        }

        .filter-section-wrapper .level-cards,
        .filter-section-wrapper .region-cards,
        .filter-section-wrapper .topic-cards,
        .filter-section-wrapper .status-cards,
        .filter-section-wrapper .measure-type-cards,
        .filter-section-wrapper .year-chips {
            align-items: center;
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
            justify-content: flex-start;
        }

        .filter-section-wrapper .region-cards,
        .filter-section-wrapper .topic-cards,
        .filter-section-wrapper .measure-type-cards {
            margin: 0 auto;
        }

        .filter-section-wrapper .status-chip,
        .filter-section-wrapper .region-chip,
        .filter-section-wrapper .topic-chip,
        .filter-section-wrapper .measure-type-chip,
        .filter-section-wrapper .year-chip {
            align-items: center;
            background: #FFFDF8;
            border: 1px solid #DDD2BF;
            border-radius: 999px;
            box-shadow: 0 1px 0 rgba(27, 31, 35, 0.04);
            color: var(--text-primary);
            cursor: pointer;
            display: inline-flex;
            font-size: 0.81rem;
            gap: 0.42rem;
            justify-content: center;
            line-height: 1.05;
            min-height: 34px;
            padding: 0.44rem 0.72rem;
            transition: background 0.15s ease, border-color 0.15s ease, box-shadow 0.15s ease, color 0.15s ease, transform 0.15s ease;
            user-select: none;
        }

        .filter-section-wrapper .status-chip:hover,
        .filter-section-wrapper .region-chip:hover,
        .filter-section-wrapper .topic-chip:hover,
        .filter-section-wrapper .measure-type-chip:hover,
        .filter-section-wrapper .year-chip:hover {
            background: #FFFFFF;
            border-color: #C9A23C;
            box-shadow: 0 5px 14px rgba(89, 69, 28, 0.12);
            transform: translateY(-1px);
        }

        .filter-section-wrapper .status-chip.selected,
        .filter-section-wrapper .status-chip[data-status].selected,
        .filter-section-wrapper .status-chip[data-status]:hover,
        .filter-section-wrapper .region-chip.selected,
        .filter-section-wrapper .topic-chip.selected,
        .filter-section-wrapper .measure-type-chip.selected,
        .filter-section-wrapper .year-chip.selected {
            background: #C9A23C;
            border-color: #C9A23C;
            box-shadow: 0 6px 16px rgba(201, 162, 60, 0.22);
            color: #1D1A13;
            font-weight: 700;
        }

        .filter-section-wrapper .status-chip[data-status="failed"].selected,
        .filter-section-wrapper .status-chip[data-status="failed"]:hover {
            background: #7A1F2A;
            border-color: #7A1F2A;
            color: white;
        }

        .filter-section-wrapper .status-chip[data-status="passed"].selected,
        .filter-section-wrapper .status-chip[data-status="passed"]:hover {
            background: #2D7D5F;
            border-color: #2D7D5F;
            color: white;
        }

        .filter-section-wrapper .status-chip-icon,
        .filter-section-wrapper .region-chip-emoji,
        .filter-section-wrapper .topic-chip-icon,
        .filter-section-wrapper .measure-type-chip-icon {
            align-items: center;
            display: inline-flex;
            font-size: 0.95rem;
            height: 1.05rem;
            justify-content: center;
            width: 1.05rem;
        }

        .filter-section-wrapper .status-chip-name,
        .filter-section-wrapper .region-chip-name,
        .filter-section-wrapper .topic-chip-name,
        .filter-section-wrapper .measure-type-chip-name {
            font-weight: 650;
            white-space: nowrap;
        }

        .filter-section-wrapper .status-chip-count,
        .filter-section-wrapper .region-chip-count,
        .filter-section-wrapper .topic-chip-count,
        .filter-section-wrapper .measure-type-chip-count,
        .filter-section-wrapper .year-chip-count {
            color: var(--text-tertiary);
            font-size: 0.72rem;
            font-weight: 650;
            margin-left: 0.1rem;
            opacity: 0.9;
        }

        .filter-section-wrapper .status-chip.selected .status-chip-count,
        .filter-section-wrapper .region-chip.selected .region-chip-count,
        .filter-section-wrapper .topic-chip.selected .topic-chip-count,
        .filter-section-wrapper .measure-type-chip.selected .measure-type-chip-count,
        .filter-section-wrapper .year-chip.selected .year-chip-count {
            color: currentColor;
            opacity: 0.78;
        }

        .filter-section-wrapper .decade-groups {
            gap: 0.75rem;
        }

        .filter-section-wrapper .year-picker-shell {
            overflow-x: auto;
            padding-bottom: 0.15rem;
        }

        .filter-section-wrapper .year-decade-grid {
            display: grid;
            gap: 0.45rem;
            min-width: 100%;
            width: max-content;
        }

        .filter-section-wrapper .year-decade-column {
            background: rgba(255,253,248,0.5);
            border: 1px solid #E1D6C2;
            border-radius: 8px;
            min-width: 0;
            overflow: hidden;
            padding: 0;
        }

        .filter-section-wrapper .year-decade-button {
            align-items: center;
            background: rgba(255,253,248,0.72);
            border: none;
            border-bottom: 1px solid #DDD2BF;
            border-radius: 0;
            color: var(--text-primary);
            cursor: pointer;
            display: grid;
            font-family: inherit;
            gap: 0.2rem 0.5rem;
            grid-template-columns: 1fr auto auto;
            min-height: 44px;
            padding: 0.52rem 0.6rem;
            text-align: left;
            transition: background 0.15s ease, border-color 0.15s ease, box-shadow 0.15s ease;
            width: 100%;
        }

        .filter-section-wrapper .year-decade-button:hover,
        .filter-section-wrapper .year-decade-button.selected {
            background: #FFFFFF;
            box-shadow: 0 5px 14px rgba(89, 69, 28, 0.12);
        }

        .filter-section-wrapper .year-decade-button.selected {
            background: #C9A23C;
            border-bottom-color: #B48F2B;
            color: #1D1A13;
            font-weight: 800;
        }

        .filter-section-wrapper .year-decade-button span {
            font-size: 0.82rem;
            font-weight: 800;
        }

        .filter-section-wrapper .year-decade-button small {
            color: var(--text-tertiary);
            font-size: 0.72rem;
            font-weight: 700;
        }

        .filter-section-wrapper .year-decade-button.selected small {
            color: currentColor;
            opacity: 0.78;
        }

        .filter-section-wrapper .year-decade-button em {
            align-items: center;
            background: rgba(201, 162, 60, 0.18);
            border-radius: 999px;
            color: #7A5D12;
            display: inline-flex;
            font-size: 0.68rem;
            font-style: normal;
            font-weight: 800;
            height: 18px;
            justify-content: center;
            min-width: 18px;
            padding: 0 0.3rem;
        }

        .filter-section-wrapper .year-decade-button.selected em {
            background: rgba(29, 26, 19, 0.14);
            color: currentColor;
        }

        .filter-section-wrapper .year-column-years {
            display: grid;
            gap: 0;
            grid-template-columns: 1fr;
            margin-top: 0;
        }

        .filter-section-wrapper .decade-group {
            align-items: flex-start;
            display: grid;
            gap: 0.65rem;
            grid-template-columns: 48px minmax(0, 1fr);
        }

        .filter-section-wrapper .decade-label {
            color: #6F5B2B;
            font-size: 0.8rem;
            font-weight: 800;
            line-height: 34px;
            min-width: 0;
        }

        .filter-section-wrapper .year-chip {
            background: rgba(255, 253, 248, 0.72);
            border: none;
            border-bottom: 1px solid #E7DCCB;
            border-radius: 0;
            font-family: inherit;
            justify-content: space-between;
            min-width: 0;
            padding: 0.48rem 0.58rem;
            width: 100%;
        }

        .filter-section-wrapper .year-column-years .year-chip:last-child {
            border-bottom: none;
        }

        .filter-section-wrapper .year-chip:hover {
            background: #FFFFFF;
        }

        .filter-section-wrapper .year-chip.covered:not(.selected) {
            background: #F6EDDA;
            color: #4D3D17;
        }

        .filter-section-wrapper .county-navigation {
            background: rgba(255, 253, 248, 0.58);
            border: 1px solid #DED2BA;
            border-radius: 8px;
            margin-top: 0.95rem;
            padding: 0.8rem 1rem;
        }

        .filter-section-wrapper .county-label {
            color: var(--text-primary);
            font-size: 0.84rem;
            font-weight: 700;
        }

        .filter-section-wrapper .county-select {
            background: #FFFFFF;
            border-color: #D8CEBB;
            border-radius: 7px;
            font-size: 0.84rem;
            max-width: 270px;
            padding: 0.55rem 0.8rem;
        }

        @media (max-width: 768px) {
            .matrix-insight-strip {
                grid-template-columns: 1fr;
            }
            .matrix-modal-metrics {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
            .filter-section-wrapper .year-decade-grid {
                min-width: max-content;
            }
        }

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

        /* Insights view */
        .insights-view {
            max-width: 1220px;
            margin: 0 auto 3rem;
            padding: 0 1.5rem 2rem;
        }
        .insights-kicker {
            color: #8a3ffc;
            font-size: 0.78rem;
            font-weight: 800;
            letter-spacing: 0.08em;
            margin-bottom: 0.5rem;
            text-transform: uppercase;
        }
        .insights-hero {
            display: grid;
            grid-template-columns: minmax(0, 1fr) 280px;
            gap: 2rem;
            align-items: end;
            margin-bottom: 1.5rem;
            border-bottom: 1px solid var(--border);
            padding-bottom: 1.5rem;
        }
        .insights-hero h2 {
            font-size: 2.4rem;
            line-height: 1.05;
            margin: 0 0 0.75rem;
            color: var(--text-primary);
            letter-spacing: 0;
        }
        .insights-hero p {
            color: var(--text-secondary);
            font-size: 1rem;
            line-height: 1.6;
            max-width: 760px;
        }
        .insights-method-card {
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 1rem;
            background: #fbfaf7;
            display: flex;
            flex-direction: column;
            gap: 0.35rem;
            color: var(--text-secondary);
            font-size: 0.82rem;
        }
        .insights-method-card strong {
            color: var(--text-primary);
            font-size: 0.95rem;
        }
        .insights-analysis-shell {
            display: block;
        }
        .insights-side-nav {
            display: flex;
            flex-direction: row;
            gap: 0.25rem;
            padding: 0 0 0.75rem;
            margin-bottom: 0.9rem;
            overflow-x: auto;
            overflow-y: hidden;
            border-bottom: 1px solid var(--border);
        }
        .insights-side-nav span {
            color: var(--text-tertiary);
            font-size: 0.68rem;
            font-weight: 800;
            letter-spacing: 0.08em;
            padding: 0.52rem 0.65rem 0.45rem 0;
            text-transform: uppercase;
            white-space: nowrap;
        }
        .insights-side-nav a {
            border-bottom: 3px solid transparent;
            color: var(--text-secondary);
            display: block;
            flex: 0 0 auto;
            font-size: 0.82rem;
            font-weight: 650;
            line-height: 1.2;
            padding: 0.52rem 0.65rem 0.45rem;
            text-decoration: none;
            transition: all 0.15s ease;
            white-space: nowrap;
        }
        .insights-side-nav a:hover {
            background: #fbfaf7;
            color: var(--text-primary);
        }
        .insights-side-nav a.active {
            border-bottom-color: #7A1F2A;
            background: #fbfaf7;
            color: #7A1F2A;
        }
        .insights-analysis-content {
            min-width: 0;
        }
        .insights-carousel {
            position: relative;
        }
        .insights-carousel-viewport {
            overflow: hidden;
            border-radius: 8px;
            transition: height 0.25s ease;
        }
        .insights-carousel-track {
            align-items: flex-start;
            display: flex;
            transition: transform 0.35s ease;
            width: 100%;
        }
        .insights-carousel-slide {
            box-sizing: border-box;
            flex: 0 0 100%;
            min-width: 100%;
            min-height: 0;
        }
        section.insights-carousel-slide {
            background: white;
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 1rem;
        }
        .insight-panel.insights-carousel-slide,
        .insights-methodology.insights-carousel-slide {
            margin: 0;
        }
        .insights-carousel-arrow {
            position: absolute;
            top: 50%;
            transform: translateY(-50%);
            z-index: 5;
            width: 54px;
            height: 54px;
            border-radius: 999px;
            border: 2px solid #7A1F2A;
            background: #FFFFFF;
            color: #7A1F2A;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 12px 32px rgba(0,0,0,0.18);
            transition: transform 0.15s ease, background 0.15s ease, color 0.15s ease;
        }
        .insights-carousel-arrow span {
            display: block;
            font-size: 2.4rem;
            line-height: 1;
            margin-top: -0.1rem;
        }
        .insights-carousel-arrow:hover {
            background: #7A1F2A;
            color: white;
            transform: translateY(-50%) scale(1.05);
        }
        .insights-carousel-arrow-prev {
            left: -28px;
        }
        .insights-carousel-arrow-next {
            right: -28px;
        }
        .insights-carousel-status {
            color: var(--text-tertiary);
            font-size: 0.78rem;
            font-weight: 700;
            margin-top: 0.55rem;
            text-align: center;
        }
        .insights-anchor-target {
            scroll-margin-top: 96px;
        }
        .method-label,
        .panel-eyebrow {
            color: #6b7280;
            font-size: 0.72rem;
            font-weight: 800;
            letter-spacing: 0.06em;
            text-transform: uppercase;
        }
        .insights-metrics {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 0.75rem;
            margin-bottom: 1.2rem;
        }
        .insight-metric,
        .finding-card,
        .insight-panel,
        .insights-methodology {
            border: 1px solid var(--border);
            border-radius: 8px;
            background: white;
        }
        .insight-metric {
            padding: 0.9rem;
        }
        .insight-metric-value {
            font-size: 1.55rem;
            font-weight: 800;
            color: #174ea6;
            line-height: 1;
        }
        .insight-metric-label {
            margin-top: 0.35rem;
            color: var(--text-secondary);
            font-size: 0.78rem;
        }
        /* Overview enhancements (composition bars, sparkline, top-3 cards, coverage) */
        .insights-overview-composition {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 0.85rem;
            margin-bottom: 1.2rem;
        }
        .composition-block {
            border: 1px solid var(--border);
            border-radius: 8px;
            background: white;
            padding: 0.85rem 0.95rem;
        }
        .composition-header {
            display: flex;
            justify-content: space-between;
            align-items: baseline;
            gap: 0.5rem;
            margin-bottom: 0.55rem;
        }
        .composition-header h4 {
            margin: 0;
            font-size: 0.9rem;
            font-weight: 700;
            color: var(--text-primary);
        }
        .composition-bar {
            display: flex;
            height: 12px;
            border-radius: 4px;
            overflow: hidden;
            background: #f3f1ec;
            margin-bottom: 0.55rem;
        }
        .composition-bar-segment {
            height: 100%;
        }
        .composition-legend {
            display: flex;
            flex-direction: column;
            gap: 0.25rem;
        }
        .composition-legend-item {
            display: flex;
            align-items: center;
            gap: 0.4rem;
            font-size: 0.78rem;
            color: var(--text-secondary);
        }
        .composition-legend-item strong {
            color: var(--text-primary);
            font-weight: 700;
            min-width: 5.5rem;
        }
        .composition-legend-swatch {
            width: 10px;
            height: 10px;
            border-radius: 2px;
            flex-shrink: 0;
        }
        .insights-overview-sparkline {
            border: 1px solid var(--border);
            border-radius: 8px;
            background: white;
            padding: 0.85rem 1rem;
            margin-bottom: 1.2rem;
        }
        .insights-overview-sparkline-header {
            display: flex;
            justify-content: space-between;
            align-items: baseline;
            margin-bottom: 0.4rem;
        }
        .insights-overview-sparkline-header h4 {
            margin: 0;
            font-size: 0.9rem;
            font-weight: 700;
            color: var(--text-primary);
        }
        .insights-overview-sparkline .chart-wrap {
            height: 90px;
        }
        .insights-overview-tops {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 0.85rem;
            margin-bottom: 1.2rem;
        }
        .overview-top-card {
            border: 1px solid var(--border);
            border-radius: 8px;
            background: white;
            padding: 0.85rem 0.95rem;
        }
        .overview-top-card-header {
            display: flex;
            justify-content: space-between;
            align-items: baseline;
            margin-bottom: 0.6rem;
        }
        .overview-top-card-header h4 {
            margin: 0;
            font-size: 0.9rem;
            font-weight: 700;
            color: var(--text-primary);
        }
        .overview-top-list {
            list-style: none;
            margin: 0;
            padding: 0;
            display: flex;
            flex-direction: column;
            gap: 0.45rem;
        }
        .overview-top-list li {
            display: grid;
            grid-template-columns: 1.2rem 1fr auto;
            align-items: baseline;
            gap: 0.5rem;
            font-size: 0.85rem;
        }
        .overview-top-rank {
            color: var(--text-tertiary);
            font-weight: 700;
        }
        .overview-top-name {
            color: var(--text-primary);
            font-weight: 600;
        }
        .overview-top-meta {
            color: var(--text-secondary);
            font-size: 0.75rem;
            text-align: right;
        }
        .insights-overview-coverage {
            border: 1px solid var(--border);
            border-radius: 8px;
            background: white;
            padding: 0.85rem 1rem;
        }
        .overview-coverage-row {
            display: flex;
            align-items: baseline;
            flex-wrap: wrap;
            gap: 1.5rem;
        }
        .overview-coverage-item {
            display: flex;
            flex-direction: column;
            gap: 0.15rem;
        }
        .overview-coverage-item strong {
            font-size: 1.15rem;
            font-weight: 800;
            color: var(--text-primary);
        }
        .overview-coverage-item span {
            font-size: 0.78rem;
            color: var(--text-secondary);
        }
        .overview-coverage-item small {
            color: var(--text-tertiary);
            font-size: 0.7rem;
            margin-left: 0.2rem;
        }
        .overview-jump-btn {
            background: none;
            border: none;
            padding: 0;
            color: #174ea6;
            font-size: 0.78rem;
            font-weight: 600;
            cursor: pointer;
            text-decoration: none;
        }
        .overview-jump-btn:hover {
            text-decoration: underline;
        }
        @media (max-width: 1024px) {
            .insights-overview-composition,
            .insights-overview-tops {
                grid-template-columns: 1fr;
            }
        }
        /* Key Findings (prose-flow article) */
        .key-findings-article {
            max-width: 760px;
            margin: 0 auto 1.25rem;
            color: var(--text-primary);
            font-size: 0.97rem;
            line-height: 1.65;
        }
        .key-findings-article p {
            margin: 0 0 0.9rem;
        }
        .kf-lede {
            font-size: 1.05rem;
            line-height: 1.6;
            color: var(--text-primary);
            font-style: italic;
            border-left: 3px solid #7A1F2A;
            padding: 0.2rem 0 0.2rem 1rem;
            margin-bottom: 1.6rem !important;
        }
        .kf-disclaimer {
            font-size: 0.78rem;
            line-height: 1.5;
            color: var(--text-tertiary);
            background: #f8f5ee;
            border: 1px dashed var(--border);
            border-radius: 4px;
            padding: 0.55rem 0.85rem;
            margin: 0 0 1.2rem !important;
        }
        .kf-disclaimer strong {
            color: var(--text-secondary);
            font-weight: 700;
        }
        .kf-kicker {
            border-top: 1px solid var(--border);
            padding-top: 1rem;
            margin-top: 1.6rem;
            color: var(--text-secondary);
            font-size: 0.92rem;
        }
        .kf-finding {
            margin: 0 0 1.7rem;
        }
        .kf-finding h3 {
            font-size: 1.08rem;
            line-height: 1.35;
            margin: 0 0 0.55rem;
            display: flex;
            gap: 0.7rem;
            align-items: baseline;
            color: var(--text-primary);
        }
        .kf-num {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 1.55rem;
            height: 1.55rem;
            border-radius: 50%;
            background: #7A1F2A;
            color: white;
            font-size: 0.78rem;
            font-weight: 800;
            flex-shrink: 0;
        }
        .kf-finding p {
            color: var(--text-primary);
            margin-bottom: 0.85rem;
        }
        .kf-jump {
            display: inline-block;
            margin-top: 0.2rem;
            font-size: 0.82rem;
        }
        .kf-mini-table {
            width: 100%;
            border-collapse: collapse;
            margin: 0.4rem 0 0.95rem;
            font-size: 0.85rem;
            background: white;
            border: 1px solid var(--border);
            border-radius: 6px;
            overflow: hidden;
        }
        .kf-mini-table thead th {
            background: #f8f5ee;
            color: var(--text-secondary);
            font-weight: 700;
            font-size: 0.74rem;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            padding: 0.45rem 0.7rem;
            text-align: left;
            border-bottom: 1px solid var(--border);
        }
        .kf-mini-table tbody th {
            font-weight: 700;
            color: var(--text-primary);
        }
        .kf-mini-table tbody td,
        .kf-mini-table tbody th {
            padding: 0.45rem 0.7rem;
            border-bottom: 1px solid #f0ece4;
        }
        .kf-mini-table tbody tr:last-child td,
        .kf-mini-table tbody tr:last-child th {
            border-bottom: none;
        }
        .kf-decade-strip {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 0.7rem;
            margin: 0.4rem 0 0.95rem;
            background: white;
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 0.85rem 0.9rem;
        }
        .kf-decade-cell {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 0.3rem;
            min-height: 120px;
            justify-content: flex-end;
        }
        .kf-decade-bar {
            width: 60%;
            background: linear-gradient(180deg, #C9A03B, #7A1F2A);
            border-radius: 3px 3px 0 0;
            min-height: 4px;
        }
        .kf-decade-value {
            font-size: 0.85rem;
            font-weight: 800;
            color: var(--text-primary);
        }
        .kf-decade-label {
            font-size: 0.72rem;
            color: var(--text-tertiary);
            font-weight: 700;
        }
        .kf-region-bars {
            margin: 0.4rem 0 0.95rem;
            background: white;
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 0.7rem 0.9rem;
            display: flex;
            flex-direction: column;
            gap: 0.55rem;
        }
        .kf-region-row {
            display: grid;
            grid-template-columns: 11rem 1fr auto;
            align-items: center;
            gap: 0.7rem;
            font-size: 0.83rem;
        }
        .kf-region-name {
            color: var(--text-primary);
            font-weight: 600;
        }
        .kf-region-track {
            background: #f3f1ec;
            height: 10px;
            border-radius: 3px;
            overflow: hidden;
        }
        .kf-region-fill {
            height: 100%;
            border-radius: 3px;
        }
        .kf-region-meta {
            color: var(--text-secondary);
            font-size: 0.78rem;
            white-space: nowrap;
        }
        .kf-region-meta strong {
            color: var(--text-primary);
            font-weight: 800;
        }
        @media (max-width: 720px) {
            .kf-region-row {
                grid-template-columns: 1fr;
                gap: 0.25rem;
            }
            .kf-decade-strip {
                grid-template-columns: repeat(4, minmax(0, 1fr));
                padding: 0.6rem 0.5rem;
            }
            .kf-finding h3 {
                font-size: 1rem;
            }
        }
        .insights-findings {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 1rem;
            margin-bottom: 1.25rem;
        }
        .finding-card {
            padding: 1.05rem;
            min-height: 210px;
            display: flex;
            flex-direction: column;
            gap: 0.7rem;
        }
        .finding-card h3 {
            font-size: 1rem;
            line-height: 1.25;
            margin: 0;
            color: var(--text-primary);
        }
        .finding-card p {
            color: var(--text-secondary);
            font-size: 0.86rem;
            line-height: 1.45;
            margin: 0;
        }
        .finding-metric {
            font-size: 1.75rem;
            line-height: 1;
            font-weight: 800;
            color: #b42318;
        }
        .finding-label {
            color: var(--text-tertiary);
            font-size: 0.76rem;
            font-weight: 700;
        }
        .finding-footer {
            margin-top: auto;
            border-top: 1px solid #eef0f3;
            padding-top: 0.65rem;
            color: var(--text-tertiary);
            font-size: 0.72rem;
            line-height: 1.35;
        }
        .insights-dashboard-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 1rem;
        }
        .insight-panel {
            padding: 1rem;
            min-width: 0;
        }
        .insight-panel-wide {
            grid-column: 1 / -1;
        }
        .panel-heading {
            display: flex;
            justify-content: space-between;
            align-items: start;
            gap: 1rem;
            margin-bottom: 0.55rem;
        }
        .panel-heading h3 {
            margin: 0.2rem 0 0;
            font-size: 1.15rem;
            line-height: 1.25;
            color: var(--text-primary);
        }
        .panel-deck,
        .method-note {
            color: var(--text-secondary);
            font-size: 0.84rem;
            line-height: 1.45;
            margin: 0 0 0.8rem;
        }
        .method-note {
            color: var(--text-tertiary);
            margin: 0.8rem 0 0;
            font-size: 0.75rem;
        }
        .confidence-badge {
            white-space: nowrap;
            background: #eef6f3;
            color: #126e55;
            border: 1px solid #c7e7dd;
            border-radius: 999px;
            padding: 0.25rem 0.55rem;
            font-size: 0.72rem;
            font-weight: 700;
        }
        .chart-wrap {
            height: 320px;
            min-height: 260px;
            position: relative;
        }
        .chart-wrap.compact {
            height: 250px;
            min-height: 220px;
        }
        .analysis-chart-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.85rem;
        }
        .analysis-chart-grid.single-column {
            grid-template-columns: 1fr;
        }
        .chart-module {
            border: 1px solid #ebe2d3;
            border-radius: 8px;
            background: #fffdfa;
            padding: 0.7rem;
            min-width: 0;
        }
        .chart-module-wide {
            grid-column: 1 / -1;
        }
        .chart-module h4 {
            color: var(--text-primary);
            font-size: 0.82rem;
            margin: 0 0 0.55rem;
        }
        .chart-footnote {
            margin: 0.4rem 0 0;
            font-size: 0.7rem;
            color: var(--text-tertiary);
            line-height: 1.4;
        }
        /* Geography panel layout: cards on the left (2-col), map on the right.
           California is taller than wide, so the map gets the vertical real estate. */
        .county-map-layout {
            display: grid;
            grid-template-columns: minmax(0, 2fr) minmax(0, 3fr);
            grid-template-areas: "cards map";
            gap: 1rem;
            align-items: start;
        }
        .county-map-side {
            grid-area: cards;
            margin-top: 0;
        }
        #countyLeaderboard {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.65rem;
            margin-top: 0.4rem;
        }
        #countyLeaderboard .leader-row {
            border: 1px solid var(--border);
            border-radius: 6px;
            background: white;
            padding: 0.65rem 0.8rem;
        }
        @media (max-width: 1024px) {
            /* Layout collapses to single column on tablet/phone; map first, then cards. */
            .county-map-layout {
                grid-template-columns: 1fr;
                grid-template-areas: "map" "cards";
            }
            #countyLeaderboard {
                grid-template-columns: repeat(3, minmax(0, 1fr));
            }
        }
        @media (max-width: 720px) {
            #countyLeaderboard {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
        }
        @media (max-width: 480px) {
            #countyLeaderboard {
                grid-template-columns: 1fr;
            }
        }
        .finance-insights-grid {
            display: grid;
            grid-template-columns: minmax(0, 1fr) 320px;
            gap: 1rem;
            align-items: start;
        }
        .finance-module {
            margin-top: 1.75rem;
            padding-top: 1.5rem;
            border-top: 1px solid #e5e7eb;
        }
        .finance-module-header {
            margin-bottom: 0.85rem;
        }
        .finance-module-header h4 {
            margin: 0 0 0.25rem;
            font-size: 1rem;
            font-weight: 600;
            color: #0f172a;
            letter-spacing: -0.01em;
        }
        .finance-module-header p {
            margin: 0;
            font-size: 0.85rem;
            color: #475569;
            line-height: 1.5;
        }
        .finance-arc-chart {
            position: relative;
            height: 280px;
        }
        .finance-arc-toggle {
            display: inline-flex;
            gap: 0.25rem;
            padding: 0.2rem;
            background: #f1f5f9;
            border-radius: 999px;
            margin-bottom: 0.75rem;
        }
        .finance-arc-mode {
            appearance: none;
            border: none;
            background: transparent;
            color: #475569;
            font-size: 0.78rem;
            font-weight: 600;
            line-height: 1;
            padding: 0.4rem 0.85rem;
            border-radius: 999px;
            cursor: pointer;
            transition: background-color 120ms ease, color 120ms ease;
        }
        .finance-arc-mode:hover {
            color: #0f172a;
        }
        .finance-arc-mode.is-active {
            background: #0f172a;
            color: #ffffff;
        }
        .finance-arc-mode:focus-visible {
            outline: 2px solid #7A1F2A;
            outline-offset: 2px;
        }
        .finance-donors-grid {
            display: grid;
            grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
            gap: 1.75rem;
        }
        .finance-subhead {
            margin: 0 0 0.5rem;
            font-size: 0.78rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color: #475569;
        }
        .finance-subdeck {
            margin: 0 0 0.75rem;
            font-size: 0.8rem;
            color: #64748b;
            line-height: 1.5;
        }
        .finance-donor-list {
            list-style: none;
            counter-reset: donor;
            margin: 0;
            padding: 0;
        }
        .finance-donor-row {
            counter-increment: donor;
            display: grid;
            grid-template-columns: 1.6rem minmax(0, 1fr) auto;
            gap: 0.6rem;
            align-items: baseline;
            padding: 0.4rem 0;
            border-bottom: 1px solid #f1f5f9;
            font-size: 0.85rem;
        }
        .finance-donor-row::before {
            content: counter(donor) '.';
            color: #94a3b8;
            font-variant-numeric: tabular-nums;
            font-size: 0.78rem;
            text-align: right;
        }
        .finance-donor-name {
            color: #0f172a;
            font-weight: 500;
            overflow-wrap: anywhere;
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            gap: 0.4rem;
        }
        .finance-donor-name-text {
            display: inline;
        }
        .finance-sector-chip {
            display: inline-block;
            padding: 0.08rem 0.5rem;
            font-size: 0.68rem;
            font-weight: 500;
            line-height: 1.35;
            color: #475569;
            background: #e2e8f0;
            border-radius: 999px;
            white-space: nowrap;
            vertical-align: 1px;
        }
        /* Marquee-fight donor rows are tighter; smaller chip variant. */
        .finance-fight-donors .finance-sector-chip {
            font-size: 0.62rem;
            padding: 0.05rem 0.4rem;
            margin-left: 0.3rem;
        }
        .finance-donor-meta {
            display: flex;
            flex-direction: column;
            align-items: flex-end;
            gap: 0.1rem;
            white-space: nowrap;
        }
        .finance-donor-amount {
            font-variant-numeric: tabular-nums;
            font-weight: 600;
            color: #0f172a;
        }
        .finance-donor-count {
            font-size: 0.72rem;
            color: #64748b;
        }
        .finance-marquee-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 1rem;
        }
        .finance-fight-card {
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 10px;
            padding: 0.95rem 1rem 1rem;
            display: flex;
            flex-direction: column;
            gap: 0.75rem;
        }
        .finance-fight-header {
            border-bottom: 1px solid #f1f5f9;
            padding-bottom: 0.65rem;
        }
        .finance-fight-eyebrow {
            font-size: 0.72rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: #7A1F2A;
        }
        .finance-fight-headline {
            margin: 0.2rem 0 0.35rem;
            font-size: 0.98rem;
            font-weight: 600;
            color: #0f172a;
            line-height: 1.3;
        }
        .finance-fight-outcome {
            font-size: 0.78rem;
            color: #475569;
        }
        .finance-fight-sides {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 0.6rem;
        }
        .finance-fight-side {
            background: #f8fafc;
            border: 1px solid transparent;
            border-radius: 6px;
            padding: 0.55rem 0.6rem 0.65rem;
        }
        .finance-fight-won-badge {
            display: inline-block;
            margin-left: 0.4rem;
            padding: 0.05rem 0.35rem;
            font-size: 0.62rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color: #475569;
            background: #e2e8f0;
            border-radius: 3px;
            vertical-align: 1px;
        }
        .finance-fight-side-head {
            display: flex;
            justify-content: space-between;
            align-items: baseline;
            gap: 0.4rem;
            margin-bottom: 0.15rem;
        }
        .finance-fight-side-label {
            font-size: 0.72rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: #475569;
        }
        .finance-fight-side-total {
            font-variant-numeric: tabular-nums;
            font-weight: 600;
            color: #0f172a;
            font-size: 0.85rem;
        }
        .finance-fight-side-share {
            font-size: 0.7rem;
            color: #64748b;
            margin-bottom: 0.35rem;
        }
        .finance-fight-donors {
            list-style: none;
            margin: 0;
            padding: 0;
            font-size: 0.74rem;
            line-height: 1.45;
        }
        .finance-fight-donors li {
            display: flex;
            justify-content: space-between;
            gap: 0.4rem;
            padding: 0.12rem 0;
        }
        .finance-fight-donor {
            color: #1e293b;
            overflow-wrap: anywhere;
        }
        .finance-fight-amount {
            font-variant-numeric: tabular-nums;
            color: #475569;
            white-space: nowrap;
        }
        .finance-fight-takeaway {
            margin: 0;
            padding-top: 0.5rem;
            border-top: 1px solid #f1f5f9;
            font-size: 0.82rem;
            color: #1e293b;
            line-height: 1.5;
        }
        .finance-bridge {
            margin: 1.5rem 0 0.75rem;
            padding: 1rem 1.1rem;
            background: #fef3c7;
            border-left: 3px solid #f59e0b;
            border-radius: 4px;
            font-size: 0.88rem;
            color: #1e293b;
            line-height: 1.55;
        }
        .county-map {
            grid-area: map;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            background: #ffffff;
            position: relative;
            height: 640px;
            width: 100%;
        }
        @media (max-width: 1024px) {
            .county-map {
                height: 480px;
            }
        }
        .county-map .leaflet-container {
            width: 100%;
            height: 100%;
            border-radius: 8px;
            background: #ffffff;
            font-family: inherit;
        }
        .county-map .leaflet-tooltip.county-leaflet-tooltip {
            background: rgba(15, 23, 42, 0.92);
            color: white;
            border: none;
            border-radius: 4px;
            padding: 0.4rem 0.55rem;
            font-size: 0.78rem;
            line-height: 1.35;
            box-shadow: 0 2px 8px rgba(0,0,0,0.18);
        }
        .county-map .leaflet-tooltip.county-leaflet-tooltip::before {
            display: none;
        }
        .county-map .leaflet-control-attribution {
            font-size: 0.62rem;
            background: rgba(255,255,255,0.85);
        }
        .county-map .geo-legend {
            background: rgba(255,255,255,0.95);
            padding: 0.45rem 0.6rem;
            border: 1px solid var(--border);
            border-radius: 4px;
            font-size: 0.7rem;
            line-height: 1.3;
            color: var(--text-secondary);
            box-shadow: 0 1px 3px rgba(0,0,0,0.06);
        }
        .county-map .geo-legend-title {
            display: block;
            font-weight: 700;
            color: var(--text-primary);
            margin-bottom: 0.25rem;
            font-size: 0.7rem;
            text-transform: uppercase;
            letter-spacing: 0.04em;
        }
        .county-map .geo-legend-bar {
            display: flex;
            height: 8px;
            width: 140px;
            border-radius: 3px;
            overflow: hidden;
            margin-bottom: 0.2rem;
        }
        .county-map .geo-legend-bar > span {
            flex: 1 1 auto;
        }
        .county-map .geo-legend-scale {
            display: flex;
            justify-content: space-between;
            color: var(--text-tertiary);
        }
        .geography-anchor-cards {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 0.7rem;
            margin: 0.4rem 0 0.85rem;
        }
        .geography-anchor-cards .mini-callout {
            min-height: 86px;
        }
        @media (max-width: 900px) {
            .geography-anchor-cards {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
        }
        @media (max-width: 540px) {
            .geography-anchor-cards {
                grid-template-columns: 1fr;
            }
        }
        .geography-toolbar {
            display: flex;
            flex-wrap: wrap;
            gap: 0.7rem 1.4rem;
            align-items: center;
            margin: 0.4rem 0 0.85rem;
        }
        .geography-toolbar .toolbar-group {
            display: flex;
            align-items: center;
            gap: 0.4rem;
            background: white;
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 0.25rem 0.45rem;
        }
        .geography-toolbar .toolbar-label {
            color: var(--text-tertiary);
            font-size: 0.72rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            padding-right: 0.25rem;
        }
        .geography-toolbar .toolbar-btn {
            background: transparent;
            border: none;
            border-radius: 4px;
            padding: 0.3rem 0.7rem;
            font-size: 0.82rem;
            font-weight: 600;
            color: var(--text-secondary);
            cursor: pointer;
            transition: background 0.12s, color 0.12s;
        }
        .geography-toolbar .toolbar-btn:hover {
            color: var(--text-primary);
        }
        .geography-toolbar .toolbar-btn.active {
            background: #7A1F2A;
            color: white;
        }
        .county-map-side h4 {
            margin: 0 0 0.7rem;
            font-size: 0.95rem;
        }
        .leader-row,
        .compact-row {
            display: grid;
            grid-template-columns: minmax(0, 1fr) auto;
            gap: 0.75rem;
            padding: 0.55rem 0;
            border-bottom: 1px solid #eef0f3;
            color: var(--text-secondary);
            font-size: 0.82rem;
        }
        .leader-row strong,
        .compact-row strong {
            display: block;
            color: var(--text-primary);
            font-size: 0.86rem;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        .leader-bar {
            grid-column: 1 / -1;
            height: 6px;
            border-radius: 999px;
            background: #e5e7eb;
            overflow: hidden;
        }
        .leader-bar span {
            display: block;
            height: 100%;
            background: #174ea6;
        }
        .mini-callouts {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.6rem;
            margin-top: 0.8rem;
        }
        .mini-callouts-single {
            grid-template-columns: 1fr;
        }
        .mini-callout {
            background: #fbfaf7;
            border: 1px solid #ebe2d3;
            border-radius: 8px;
            padding: 0.65rem;
        }
        .mini-callout strong {
            display: block;
            color: var(--text-primary);
            font-size: 1.15rem;
        }
        .mini-callout span {
            color: var(--text-secondary);
            font-size: 0.74rem;
        }
        .compact-list-heading {
            color: var(--text-tertiary);
            font-size: 0.72rem;
            font-weight: 800;
            letter-spacing: 0.05em;
            margin-top: 0.9rem;
            text-transform: uppercase;
        }
        /* Topic era strip + pass-rate rankings */
        .topic-era-strip {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 0.6rem;
            margin: 1rem 0 0.4rem;
        }
        .topic-era-card {
            background: white;
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 0.65rem 0.75rem;
        }
        .topic-era-card-decade {
            font-size: 0.95rem;
            font-weight: 800;
            color: var(--text-primary);
            margin-bottom: 0.05rem;
        }
        .topic-era-card-meta {
            font-size: 0.7rem;
            color: var(--text-tertiary);
            margin-bottom: 0.45rem;
        }
        .topic-era-card-row {
            display: flex;
            justify-content: space-between;
            align-items: baseline;
            font-size: 0.8rem;
            line-height: 1.3;
            margin-bottom: 0.2rem;
        }
        .topic-era-card-row span {
            color: var(--text-primary);
            font-weight: 600;
        }
        .topic-era-card-row strong {
            color: var(--text-secondary);
            font-weight: 700;
            font-size: 0.85rem;
        }
        .topic-pass-rate-rankings {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.85rem;
            margin: 0.9rem 0 0.4rem;
        }
        .topic-rank-block {
            background: white;
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 0.7rem 0.85rem;
        }
        .topic-rank-heading {
            font-size: 0.72rem;
            font-weight: 800;
            color: var(--text-tertiary);
            letter-spacing: 0.05em;
            text-transform: uppercase;
            margin-bottom: 0.5rem;
        }
        .topic-rank-row {
            display: flex;
            justify-content: space-between;
            align-items: baseline;
            font-size: 0.83rem;
            padding: 0.32rem 0;
            border-bottom: 1px solid #f0ece4;
        }
        .topic-rank-row:last-child {
            border-bottom: none;
        }
        .topic-rank-row-name {
            color: var(--text-primary);
            font-weight: 600;
        }
        .topic-rank-row-pct {
            color: var(--text-secondary);
            font-weight: 700;
        }
        .topic-rank-row-pct small {
            color: var(--text-tertiary);
            font-weight: 500;
            margin-left: 0.3rem;
        }
        @media (max-width: 720px) {
            .topic-era-strip,
            .topic-pass-rate-rankings {
                grid-template-columns: 1fr;
            }
        }
        /* Measure Types panel sub-sections */
        .type-insights-stack {
            display: flex;
            flex-direction: column;
            gap: 1.25rem;
            margin-top: 1rem;
        }
        .type-insights-section h4.type-section-h {
            margin: 0 0 0.35rem;
            font-size: 0.95rem;
            font-weight: 700;
            color: var(--text-primary);
        }
        .type-insights-section .type-section-deck {
            margin: 0 0 0.7rem;
            font-size: 0.88rem;
            line-height: 1.5;
            color: var(--text-secondary);
        }
        .type-insights-section .type-section-footnote {
            margin: 0.45rem 0 0;
            font-size: 0.7rem;
            color: var(--text-tertiary);
            line-height: 1.4;
        }
        .type-anatomy-strip {
            display: grid;
            grid-template-columns: repeat(6, minmax(0, 1fr));
            gap: 0.55rem;
        }
        .type-anatomy-cell {
            background: white;
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 0.55rem 0.45rem;
            text-align: center;
        }
        .type-anatomy-num {
            font-size: 1.1rem;
            font-weight: 800;
            color: var(--text-primary);
            line-height: 1;
        }
        .type-anatomy-name {
            margin-top: 0.3rem;
            font-size: 0.74rem;
            color: var(--text-secondary);
            line-height: 1.25;
        }
        .type-profile-table {
            width: 100%;
        }
        .type-profile-table tbody td:last-child {
            color: var(--text-secondary);
            font-size: 0.78rem;
        }
        @media (max-width: 720px) {
            .type-anatomy-strip {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
            .type-profile-table thead {
                display: none;
            }
            .type-profile-table tbody tr {
                display: grid;
                grid-template-columns: 1fr;
                padding: 0.5rem 0;
                border-bottom: 1px solid #f0ece4;
            }
            .type-profile-table tbody td,
            .type-profile-table tbody th {
                padding: 0.15rem 0;
                border-bottom: none;
            }
        }
        /* Rules panel layout */
        .rules-hero {
            background: white;
            border: 1px solid var(--border);
            border-left: 4px solid #B5302F;
            border-radius: 6px;
            padding: 1rem 1.2rem;
            margin: 1rem 0 1.2rem;
        }
        .rules-hero-num {
            font-size: 2rem;
            font-weight: 800;
            color: #B5302F;
            line-height: 1;
        }
        .rules-hero-headline {
            margin-top: 0.35rem;
            font-size: 1rem;
            font-weight: 700;
            color: var(--text-primary);
            line-height: 1.4;
        }
        .rules-hero-sub {
            margin-top: 0.3rem;
            font-size: 0.85rem;
            color: var(--text-secondary);
            line-height: 1.5;
        }
        .rules-chart-wrap {
            background: white;
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 0.85rem 1rem 0.7rem;
            margin-bottom: 1.1rem;
        }
        .rules-chart-wrap .chart-wrap {
            height: 220px;
        }
        .rules-section-h {
            margin: 0 0 0.5rem;
            font-size: 0.92rem;
            font-weight: 700;
            color: var(--text-primary);
        }
        #rulesThresholdTable {
            margin-bottom: 1.1rem;
        }
        .rules-landmarks {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.7rem;
            margin-bottom: 1.1rem;
        }
        .rules-landmark-card {
            background: white;
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 0.8rem 0.95rem;
        }
        .rules-landmark-yes {
            font-size: 1.45rem;
            font-weight: 800;
            color: #B5302F;
            line-height: 1;
        }
        .rules-landmark-tag {
            margin-top: 0.4rem;
            font-size: 0.8rem;
            font-weight: 700;
            color: var(--text-primary);
        }
        .rules-landmark-meta {
            margin-top: 0.18rem;
            font-size: 0.78rem;
            color: var(--text-secondary);
            line-height: 1.45;
        }
        .rules-plain-english {
            background: #fbf7f0;
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 0.85rem 1rem;
            margin-bottom: 1.1rem;
            font-size: 0.92rem;
            line-height: 1.55;
            color: var(--text-primary);
        }
        .rules-plain-english strong {
            color: #B5302F;
        }
        .rules-plain-english .rules-plain-caveat {
            display: block;
            margin-top: 0.4rem;
            font-size: 0.78rem;
            color: var(--text-tertiary);
        }
        .rules-bridge {
            font-size: 0.92rem;
            line-height: 1.6;
            color: var(--text-primary);
            margin-bottom: 0.6rem;
        }
        .rules-bridge p {
            margin: 0 0 0.5rem;
        }
        @media (max-width: 720px) {
            .rules-landmarks {
                grid-template-columns: 1fr;
            }
        }
        .insights-methodology {
            margin-top: 1rem;
            padding: 0.9rem 1rem;
        }
        .insights-methodology summary {
            cursor: pointer;
            font-weight: 700;
            color: var(--text-primary);
        }
        .insights-methodology div {
            margin-top: 0.8rem;
            color: var(--text-secondary);
            font-size: 0.84rem;
            line-height: 1.5;
        }
        .county-tooltip {
            position: fixed;
            pointer-events: none;
            background: rgba(17, 24, 39, 0.94);
            color: white;
            padding: 0.45rem 0.55rem;
            border-radius: 6px;
            font-size: 0.75rem;
            z-index: 9999;
            box-shadow: 0 8px 24px rgba(0,0,0,0.18);
        }

        /* ══════════════════════════════════════════════════════
           MOBILE RESPONSIVE OVERRIDES
           ══════════════════════════════════════════════════════ */

        /* Tablets and small laptops */
        @media (max-width: 768px) {
            .insights-analysis-shell {
                grid-template-columns: 1fr;
                gap: 0.75rem;
            }
            .insights-side-nav {
                position: sticky;
                top: 62px;
                z-index: 20;
                flex-direction: row;
                overflow-x: auto;
                overflow-y: hidden;
                max-height: none;
                background: rgba(255, 255, 255, 0.96);
                border-bottom: 1px solid var(--border);
                padding: 0.45rem 0;
                margin: 0 -0.75rem 0.25rem;
            }
            .insights-side-nav span {
                display: none;
            }
            .insights-side-nav a {
                border-left: 0;
                border-bottom: 3px solid transparent;
                flex: 0 0 auto;
                padding: 0.5rem 0.65rem 0.45rem;
                white-space: nowrap;
            }
            .insights-side-nav a.active {
                border-left-color: transparent;
                border-bottom-color: #7A1F2A;
            }
            .insights-carousel-viewport {
                overflow: visible;
            }
            .insights-carousel-track {
                display: block;
                transform: none !important;
                transition: none;
            }
            .insights-carousel-slide {
                min-height: auto;
                min-width: 0;
                margin-bottom: 1rem;
            }
            .insights-carousel-arrow,
            .insights-carousel-status {
                display: none;
            }
            .insights-hero,
            .county-map-layout,
            .finance-insights-grid,
            .finance-donors-grid {
                grid-template-columns: 1fr;
            }
            .finance-marquee-grid,
            .finance-fight-sides {
                grid-template-columns: 1fr;
            }
            .finance-arc-chart {
                height: 240px;
            }
            .analysis-chart-grid {
                grid-template-columns: 1fr;
            }
            .insights-metrics {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
            .insights-findings,
            .insights-dashboard-grid {
                grid-template-columns: 1fr;
            }
            .insight-panel-wide {
                grid-column: auto;
            }

            /* Modal: fill most of the screen */
            .measure-detail-modal {
                max-width: 95vw !important;
                width: 95vw;
                max-height: 90vh;
            }

            /* Modal tabs: tighter padding */
            .modal-tab {
                padding: 0.4rem 0.8rem;
                font-size: 0.8rem;
            }

            /* Tab panel min-height: shorter on mobile */
            .modal-tab-panel {
                min-height: 280px;
            }

            /* Matrix toolbar: wrap controls */
            .matrix-toolbar {
                flex-wrap: wrap;
                gap: 0.5rem;
            }
            .matrix-toolbar span:first-child {
                flex-basis: 100%;
                font-size: 0.75rem;
            }
            .matrix-scroll {
                height: clamp(420px, calc(100vh - 230px), 620px);
            }

            /* Info tooltips: wider and repositioned */
            .info-tip::after {
                width: 180px;
                left: auto;
                right: -10px;
                transform: none;
            }

            /* Logo: smaller */
            .site-logo h1 {
                font-size: 1rem !important;
            }
        }

        /* Phones */
        @media (max-width: 480px) {
            .insights-view {
                padding: 0 0.75rem 1.5rem;
            }
            .insights-side-nav {
                top: 56px;
            }
            .insights-hero h2 {
                font-size: 1.75rem;
            }
            .insights-metrics {
                grid-template-columns: 1fr;
            }
            .county-map {
                min-height: 360px;
            }

            /* Header: compact */
            .header-content {
                padding: 0.75rem 0.75rem !important;
                gap: 0.5rem;
            }
            .site-logo h1 {
                font-size: 0.9rem !important;
            }
            .logo-icon {
                width: 28px !important;
                height: 28px !important;
            }

            /* Search: compact */
            .search-container input {
                padding: 0.5rem 0.75rem !important;
                font-size: 0.85rem;
            }

            /* View toggle buttons: smaller */
            .view-btn {
                padding: 0.4rem !important;
            }

            /* Cards grid: 1 column on phones */
            .results-grid {
                grid-template-columns: 1fr !important;
                gap: 0.5rem;
            }

            /* Card: even tighter */
            .measure-card {
                padding: 0.75rem 0.85rem;
                gap: 0.4rem;
                min-height: 140px;
            }

            /* Modal: full screen */
            .measure-detail-modal {
                max-width: 100vw !important;
                width: 100vw;
                max-height: 100vh;
                border-radius: 0;
                margin: 0;
            }
            .modal-content {
                border-radius: 0 !important;
            }

            /* Modal tabs: fill width equally */
            .modal-tabs {
                display: flex;
            }
            .modal-tab {
                flex: 1;
                text-align: center;
                padding: 0.4rem 0.4rem;
                font-size: 0.75rem;
            }

            /* Tab panel: shorter min-height */
            .modal-tab-panel {
                min-height: 200px;
            }

            /* Related measures / context tiles: 1 column */
            .measure-detail-related {
                grid-template-columns: 1fr !important;
            }

            /* Links: 1 column */
            .measure-detail-links {
                grid-template-columns: 1fr !important;
            }

            /* Stats ribbon: smaller */
            .stats-ribbon {
                gap: 0.25rem !important;
                padding: 0.5rem !important;
            }
            .stat-value {
                font-size: 1rem !important;
            }
            .stat-label {
                font-size: 0.55rem !important;
            }

            /* Matrix: enable horizontal scroll, reduce cell sizes */
            .matrix-scroll {
                height: clamp(380px, calc(100vh - 210px), 560px);
                -webkit-overflow-scrolling: touch;
            }
            .matrix-cell {
                min-width: 60px !important;
                font-size: 0.7rem;
            }
            .matrix-table td:first-child,
            .matrix-table th:first-child {
                min-width: 100px !important;
                font-size: 0.7rem;
            }

            /* Matrix toolbar: stack vertically */
            .matrix-toolbar {
                flex-direction: column;
                align-items: flex-start;
                gap: 0.4rem;
            }

            /* Chat panel: full width */
            .chat-panel {
                left: 0 !important;
                right: 0 !important;
                bottom: 0 !important;
                width: 100% !important;
                max-width: 100% !important;
                height: 70vh !important;
                border-radius: 12px 12px 0 0 !important;
            }

            /* Info tooltips: smaller, fit screen */
            .info-tip {
                width: 18px;
                height: 18px;
                font-size: 11px;
            }
            .info-tip::after {
                width: min(200px, 70vw);
                font-size: 0.68rem;
            }

            /* Hero section: compact */
            .hero-section {
                padding: 1rem !important;
            }
            .hero-title {
                font-size: 1.1rem !important;
            }

            /* Pagination: wrap */
            .pagination {
                flex-wrap: wrap;
                gap: 0.25rem;
            }
            .pagination button {
                padding: 0.3rem 0.5rem;
                font-size: 0.75rem;
            }

            /* Filter section: compact */
            .filter-panel {
                padding: 0.75rem !important;
            }

            /* Finance: stack columns */
            .finance-sides {
                flex-direction: column !important;
            }

            /* Briefing arguments: stack to 1 column */
            .briefing-args-grid {
                grid-template-columns: 1fr !important;
            }
        }

        /* Very small phones (320px) */
        @media (max-width: 375px) {
            .header-content {
                padding: 0.5rem !important;
            }
            .site-logo h1 {
                font-size: 0.8rem !important;
            }
            .modal-tab {
                font-size: 0.7rem;
                padding: 0.35rem 0.3rem;
            }
            .measure-card {
                padding: 0.6rem 0.7rem;
            }
        }
        """

    def _get_javascript(self, measures_json: str, topics_json: str,
                       recommendations_json: str, stats: Dict, quiz_json: str = "[]",
                       finance_json: str = "{}", insights_json: str = "{}") -> str:
        """Get JavaScript code for the website"""
        return f"""
        // Data
        const allMeasures = {measures_json};
        const topics = {topics_json};
        const recommendations = {recommendations_json};
        const quizQuestions = {quiz_json};
        const financeData = {finance_json};
        const insightsData = {insights_json};

        // Utility function to escape HTML special characters (prevents XSS)
        function escapeHtml(text) {{
            if (!text) return '';
            const div = document.createElement('div');
            div.textContent = String(text);
            return div.innerHTML;
        }}

        // Sanitize URLs — only allow http(s) and relative paths
        function sanitizeUrl(url) {{
            if (!url) return '#';
            const s = String(url).trim();
            if (s.startsWith('http://') || s.startsWith('https://') || s.startsWith('/')) return s;
            return '#';
        }}

        // Escape text for use inside HTML attributes (double-quote safe)
        function escapeAttr(text) {{
            if (!text) return '';
            return String(text).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/'/g, '&#39;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
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
                        // Modal mirrors the Insights panel: donor name +
                        // sector chip when curated. donor_type stays as a
                        // separate field (individual / committee / etc.)
                        // since it's a different concept from sector.
                        const sectorChip = renderSectorChip(d.donor_sector);
                        html += '<div class="finance-donor-row">' +
                            '<span class="finance-donor-name">' + escapeHtml(d.donor_name_canon) + sectorChip + '</span>' +
                            '<span class="finance-donor-amount">' + formatDollars(d.total_amount) + '</span>' +
                            '<span class="finance-donor-type">' + escapeHtml(d.donor_type || '') + '</span>' +
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
            selectedDecades: [],
            thresholds: [],
            search: '',
            regions: [],
            county: null,
            level: null,
            levelCounty: null,
            measureTypes: []
        }};
        let currentSort = 'year-desc';
        let filteredMeasures = [];
        let activeYearDecade = null;
        let yearFilterCounts = {{}};
        let yearFilterDecades = {{}};
        let sortedYearDecades = [];

        // Pagination state
        let pagination = {{
            currentPage: 1,
            itemsPerPage: 12,
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
                    <option value="${{escapeAttr(county)}}">${{escapeHtml(county)}}</option>
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

            currentFilters.county = county || null;
            pagination.currentPage = 1;

            // Update filter count badges
            updateFilterCountBadges();

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
            updateFilterCountBadges();

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
            const yearCount = getEffectiveSelectedYearCount();
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

            renderActiveFilterSummary();
        }}

        function getActiveFilterTokens() {{
            normalizeYearFilters();
            const defaultYearMin = {stats.get('year_min', 1902)};
            const defaultYearMax = {stats.get('year_max', 2026)};
            const statusLabels = {{ passed: 'Passed', failed: 'Failed', pending: 'Pending/Unknown' }};
            const levelLabels = {{ statewide: 'Statewide', local: 'Local' }};
            const tokens = [];

            if (currentFilters.search) {{
                tokens.push({{ kind: 'search', group: 'Search', label: currentFilters.search, value: currentFilters.search }});
            }}
            if (currentFilters.level) {{
                tokens.push({{ kind: 'level', group: 'Level', label: levelLabels[currentFilters.level] || currentFilters.level, value: currentFilters.level }});
            }}
            if (currentFilters.levelCounty) {{
                tokens.push({{ kind: 'levelCounty', group: 'County', label: currentFilters.levelCounty, value: currentFilters.levelCounty }});
            }}
            (currentFilters.regions || []).forEach(region => {{
                tokens.push({{ kind: 'region', group: 'Region', label: region, value: region }});
            }});
            if (currentFilters.county) {{
                tokens.push({{ kind: 'county', group: 'County', label: currentFilters.county, value: currentFilters.county }});
            }}
            (currentFilters.topics || []).forEach(topic => {{
                tokens.push({{ kind: 'topic', group: 'Topic', label: topic, value: topic }});
            }});
            (currentFilters.selectedDecades || []).slice().sort((a, b) => b - a).forEach(decade => {{
                tokens.push({{ kind: 'decade', group: 'Decade', label: `${{decade}}s`, value: decade }});
            }});
            (currentFilters.selectedYears || []).slice().sort((a, b) => b - a).forEach(year => {{
                tokens.push({{ kind: 'year', group: 'Year', label: String(year), value: year }});
            }});
            (currentFilters.thresholds || []).forEach(threshold => {{
                tokens.push({{ kind: 'threshold', group: 'Threshold', label: threshold, value: threshold }});
            }});
            (currentFilters.status || []).forEach(status => {{
                tokens.push({{ kind: 'status', group: 'Status', label: statusLabels[status] || status, value: status }});
            }});
            (currentFilters.measureTypes || []).forEach(type => {{
                tokens.push({{ kind: 'measureType', group: 'Measure Type', label: type, value: type }});
            }});
            (currentFilters.features || []).forEach(feature => {{
                tokens.push({{ kind: 'feature', group: 'Feature', label: feature, value: feature }});
            }});
            if (currentFilters.yearMin !== defaultYearMin || currentFilters.yearMax !== defaultYearMax) {{
                tokens.push({{
                    kind: 'yearRange',
                    group: 'Year Range',
                    label: `${{currentFilters.yearMin}}-${{currentFilters.yearMax}}`,
                    value: 'range'
                }});
            }}

            return tokens;
        }}

        function renderActiveFilterSummary() {{
            const summary = document.getElementById('activeFilterSummary');
            const chips = document.getElementById('activeFilterChips');
            if (!summary || !chips) return;

            const tokens = getActiveFilterTokens();
            summary.style.display = tokens.length ? 'block' : 'none';
            chips.innerHTML = tokens.map(token => `
                <div class="active-filter-chip" title="${{escapeAttr(token.group + ': ' + token.label)}}">
                    <strong>${{escapeHtml(token.group)}}</strong>
                    <span>${{escapeHtml(token.label)}}</span>
                    <button type="button" onclick="removeActiveFilterFromButton(this)" data-kind="${{escapeAttr(token.kind)}}" data-value="${{escapeAttr(String(token.value))}}" aria-label="Remove ${{escapeAttr(token.group + ': ' + token.label)}}">&times;</button>
                </div>
            `).join('');
        }}

        function removeActiveFilterFromButton(button) {{
            removeActiveFilter(button.dataset.kind, button.dataset.value);
        }}

        function removeActiveFilter(kind, value) {{
            if (kind === 'search') {{
                currentFilters.search = '';
                const input = document.getElementById('searchInput');
                if (input) input.value = '';
            }} else if (kind === 'level') {{
                currentFilters.level = null;
                currentFilters.levelCounty = null;
                const select = document.getElementById('levelCountySelect');
                if (select) select.value = '';
                updateLevelChipUI();
            }} else if (kind === 'levelCounty') {{
                currentFilters.levelCounty = null;
                const select = document.getElementById('levelCountySelect');
                if (select) select.value = '';
            }} else if (kind === 'region') {{
                currentFilters.regions = (currentFilters.regions || []).filter(region => region !== value);
                updateRegionChipUI();
            }} else if (kind === 'county') {{
                currentFilters.county = null;
                const select = document.getElementById('countySelect');
                if (select) select.value = '';
            }} else if (kind === 'topic') {{
                currentFilters.topics = (currentFilters.topics || []).filter(topic => topic !== value);
                updateTopicChipUI();
            }} else if (kind === 'year') {{
                const numericYear = parseInt(value);
                currentFilters.selectedYears = (currentFilters.selectedYears || []).filter(year => year !== numericYear);
                renderYearNavigation();
            }} else if (kind === 'decade') {{
                const numericDecade = parseInt(value);
                currentFilters.selectedDecades = (currentFilters.selectedDecades || []).filter(decade => decade !== numericDecade);
                renderYearNavigation();
            }} else if (kind === 'threshold') {{
                currentFilters.thresholds = (currentFilters.thresholds || []).filter(threshold => threshold !== value);
            }} else if (kind === 'status') {{
                currentFilters.status = (currentFilters.status || []).filter(status => status !== value);
                updateStatusChipUI();
            }} else if (kind === 'measureType') {{
                currentFilters.measureTypes = (currentFilters.measureTypes || []).filter(type => type !== value);
                updateMeasureTypeChipUI();
            }} else if (kind === 'feature') {{
                currentFilters.features = (currentFilters.features || []).filter(feature => feature !== value);
                updateFilterUI();
            }} else if (kind === 'yearRange') {{
                currentFilters.yearMin = {stats.get('year_min', 1902)};
                currentFilters.yearMax = {stats.get('year_max', 2026)};
            }}

            pagination.currentPage = 1;
            updateFilterCountBadges();
            applyFilters();
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
                    <div class="topic-chip" data-topic="${{escapeAttr(escapedTopic)}}" onclick="toggleTopicFilter('${{escapedTopic}}')">
                        <span class="topic-chip-icon">${{icon}}</span>
                        <span class="topic-chip-name">${{escapeHtml(topic)}}</span>
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
                    <div class="measure-type-chip" data-measure-type="${{escapeAttr(escapedType)}}" onclick="toggleMeasureTypeFilter('${{escapedType}}')">
                        <span class="measure-type-chip-icon">${{icon}}</span>
                        <span class="measure-type-chip-name">${{escapeHtml(mtype)}}</span>
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
            yearFilterCounts = {{}};
            allMeasures.forEach(m => {{
                const year = parseInt(m.year);
                if (year) {{
                    yearFilterCounts[year] = (yearFilterCounts[year] || 0) + 1;
                }}
            }});

            // Get all years and group by decade
            const years = Object.keys(yearFilterCounts).map(y => parseInt(y)).sort((a, b) => b - a);
            yearFilterDecades = {{}};

            years.forEach(year => {{
                const decade = Math.floor(year / 10) * 10;
                if (!yearFilterDecades[decade]) {{
                    yearFilterDecades[decade] = [];
                }}
                yearFilterDecades[decade].push(year);
            }});

            // Sort decades descending
            sortedYearDecades = Object.keys(yearFilterDecades).map(d => parseInt(d)).sort((a, b) => b - a);
            renderYearNavigation();
        }}

        function getYearDecade(year) {{
            const numericYear = parseInt(year);
            return Number.isFinite(numericYear) ? Math.floor(numericYear / 10) * 10 : null;
        }}

        function normalizeYearFilters() {{
            const selectedDecades = new Set((currentFilters.selectedDecades || [])
                .map(decade => parseInt(decade))
                .filter(decade => Number.isFinite(decade)));

            const selectedYears = new Set((currentFilters.selectedYears || [])
                .map(year => parseInt(year))
                .filter(year => Number.isFinite(year)));

            currentFilters.selectedDecades = Array.from(selectedDecades).sort((a, b) => b - a);
            currentFilters.selectedYears = Array.from(selectedYears)
                .filter(year => !selectedDecades.has(getYearDecade(year)))
                .sort((a, b) => b - a);
        }}

        function getEffectiveSelectedYearCount() {{
            normalizeYearFilters();
            const years = new Set(currentFilters.selectedYears || []);

            (currentFilters.selectedDecades || []).forEach(decade => {{
                (yearFilterDecades[decade] || []).forEach(year => years.add(year));
            }});

            return years.size;
        }}

        function renderYearNavigation() {{
            const container = document.getElementById('decadeGroups');
            if (!container) return;
            normalizeYearFilters();
            if (!sortedYearDecades.length) {{
                container.innerHTML = '';
                return;
            }}

            const decadeColumns = sortedYearDecades.map(decade => {{
                const years = yearFilterDecades[decade] || [];
                const decadeTotal = years.reduce((sum, year) => sum + (yearFilterCounts[year] || 0), 0);
                const selectedCount = years.filter(year => currentFilters.selectedYears.includes(year)).length;
                const decadeSelected = (currentFilters.selectedDecades || []).includes(decade);
                const headerCount = decadeSelected ? years.length : selectedCount;
                return `
                    <div class="year-decade-column ${{decadeSelected ? 'selected' : ''}} ${{headerCount ? 'has-selection' : ''}}">
                        <button type="button" class="year-decade-button ${{decadeSelected ? 'selected' : ''}} ${{headerCount ? 'has-selection' : ''}}" onclick="toggleYearDecade(${{decade}})" aria-pressed="${{decadeSelected}}">
                            <span>${{decade}}s</span>
                            <small>${{decadeTotal.toLocaleString()}}</small>
                            ${{headerCount ? `<em title="${{decadeSelected ? 'Years included in selected decade' : 'Selected years in this decade'}}">${{headerCount}}</em>` : ''}}
                        </button>
                        <div class="year-column-years">
                            ${{years.slice().sort((a, b) => b - a).map(year => `
                                <button type="button" class="year-chip ${{decadeSelected ? 'covered' : ''}}" data-year="${{year}}" onclick="toggleYearFilter(${{year}})" aria-pressed="${{currentFilters.selectedYears.includes(year)}}">
                                    <span>${{year}}</span>
                                    <span class="year-chip-count">(${{yearFilterCounts[year]}})</span>
                                </button>
                            `).join('')}}
                        </div>
                    </div>
                `;
            }}).join('');

            container.innerHTML = `
                <div class="year-picker-shell">
                    <div class="year-decade-grid" style="grid-template-columns: repeat(${{sortedYearDecades.length}}, minmax(86px, 1fr));" aria-label="Select decades or individual years">
                        ${{decadeColumns}}
                    </div>
                </div>
            `;
            updateYearChipUI();
        }}

        function toggleYearDecade(decade) {{
            const selected = currentFilters.selectedDecades || [];
            const index = selected.indexOf(decade);
            if (index === -1) {{
                selected.push(decade);
                currentFilters.selectedYears = (currentFilters.selectedYears || [])
                    .filter(year => getYearDecade(year) !== decade);
            }} else {{
                selected.splice(index, 1);
            }}
            currentFilters.selectedDecades = selected;
            normalizeYearFilters();
            pagination.currentPage = 1;
            renderYearNavigation();
            updateFilterCountBadges();
            applyFilters();
        }}

        // Toggle year filter
        function toggleYearFilter(year) {{
            const decade = getYearDecade(year);
            currentFilters.selectedDecades = (currentFilters.selectedDecades || [])
                .filter(selectedDecade => selectedDecade !== decade);

            const index = currentFilters.selectedYears.indexOf(year);
            if (index === -1) {{
                currentFilters.selectedYears.push(year);
            }} else {{
                currentFilters.selectedYears.splice(index, 1);
            }}
            normalizeYearFilters();
            renderYearNavigation();
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
                    chip.setAttribute('aria-pressed', 'true');
                }} else {{
                    chip.classList.remove('selected');
                    chip.setAttribute('aria-pressed', 'false');
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
                    updateFilterCountBadges();
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
            updateFilterCountBadges();
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
            updateFilterCountBadges();
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
            normalizeYearFilters();
            filteredMeasures = allMeasures.filter(measure => {{
                // Year range filter (from sidebar)
                const year = parseInt(measure.year);
                if (!isNaN(year)) {{
                    if (year < currentFilters.yearMin || year > currentFilters.yearMax) {{
                        return false;
                    }}
                }}

                // Selected years/decades filter
                const selectedDecades = currentFilters.selectedDecades || [];
                const hasYearFilter = currentFilters.selectedYears.length > 0 || selectedDecades.length > 0;
                if (hasYearFilter) {{
                    const decade = !isNaN(year) ? Math.floor(year / 10) * 10 : null;
                    if (!currentFilters.selectedYears.includes(year) && !selectedDecades.includes(decade)) {{
                        return false;
                    }}
                }}

                // Threshold filter (used by Explore drilldowns)
                if ((currentFilters.thresholds || []).length > 0) {{
                    if (!currentFilters.thresholds.includes(getThresholdLabel(measure))) {{
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

                // Exclude upcoming/pending measures (2026+) from default view
                // (they're featured in the dedicated hero section)
                // Historical measures with null passed status are NOT excluded
                if (!currentFilters.status.includes('pending') && currentFilters.selectedYears.length === 0 && (currentFilters.selectedDecades || []).length === 0) {{
                    const measureYear = parseInt(measure.year);
                    if (measure.passed !== 1 && measure.passed !== 0 && measureYear >= 2026) {{
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
                (currentFilters.selectedDecades || []).length === 0 &&
                (currentFilters.thresholds || []).length === 0 &&
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

        function matrixVolumeColor(value, maxValue) {{
            if (!maxValue || value < 1) return '#f0eee8';
            const t = Math.sqrt(value / maxValue);
            const r = Math.round(244 - 115 * t);
            const g = Math.round(237 - 105 * t);
            const b = Math.round(220 - 150 * t);
            return `rgb(${{r}}, ${{g}}, ${{b}})`;
        }}

        function matrixYesColor(avgYes) {{
            if (avgYes == null) return '#f0eee8';
            return matrixCellColor(avgYes, 100);
        }}

        function matrixDeltaColor(delta) {{
            if (delta == null) return '#f0eee8';
            const capped = Math.max(-35, Math.min(35, delta));
            const t = Math.abs(capped) / 35;
            if (capped < 0) {{
                const r = Math.round(248 - 26 * t);
                const g = Math.round(246 - 115 * t);
                const b = Math.round(241 - 143 * t);
                return `rgb(${{r}}, ${{g}}, ${{b}})`;
            }}
            const r = Math.round(248 - 114 * t);
            const g = Math.round(246 - 91 * t);
            const b = Math.round(241 - 125 * t);
            return `rgb(${{r}}, ${{g}}, ${{b}})`;
        }}

        // ── Matrix State ──────────────────────────────
        const matrixState = {{
            rowGrouping: 'jurisdiction',  // 'jurisdiction' | 'region' | 'decade' | 'year'
            rowSort: 'count',             // 'count' | 'alpha' | 'rate'
            colField: 'topic',            // 'topic' | 'measureType' | 'threshold'
            sortCol: null,
            sortDir: 'desc',
            minN: 0,                      // minimum measures per cell to display (0 = show all)
            metric: 'passRate',           // 'passRate' | 'volume' | 'avgYes' | 'baseline' | 'close' | 'trap'
        }};
        // Keep legacy aliases for existing code that references them
        let matrixRowMode = matrixState.rowSort;
        let matrixColField = matrixState.colField;

        // Canonical column orderings (stable across filter changes)
        const CANONICAL_TOPIC_ORDER = ["Education", "Public Safety & Crime", "Taxes & Finance", "Government & Elections", "Healthcare & Welfare", "Environment & Natural Resources", "Transportation", "Housing & Land Use", "Business & Labor", "Utilities & Energy", "Civil Rights", "Other"];
        const CANONICAL_TYPE_ORDER = ["Ordinance", "Charter Amendment", "Sales Tax", "Transient Occupancy Tax", "Business Tax", "Advisory", "Utility Tax", "Recall", "Initiative", "Miscellaneous Tax", "Property Tax", "Gann Limit", "Bond"];

        // Build reverse region lookup from CA_REGIONS
        const countyToRegion = {{}};
        Object.keys(CA_REGIONS).forEach(regionName => {{
            CA_REGIONS[regionName].counties.forEach(c => {{
                countyToRegion[c.toUpperCase()] = regionName;
            }});
        }});

        function escapeJsString(value) {{
            return String(value ?? '').split('\\\\').join('\\\\\\\\').replace(/'/g, "\\\\'");
        }}

        function getMeasureThreshold(measure) {{
            const raw = String(measure.vote_threshold || '').toLowerCase();
            if (raw.includes('66') || raw.includes('2/3') || raw.includes('two-thirds') || raw.includes('two thirds')) return 66.67;
            if (raw.includes('55')) return 55;
            return 50;
        }}

        function getThresholdLabel(measure) {{
            const threshold = getMeasureThreshold(measure);
            if (threshold >= 66) return 'Two-thirds';
            if (threshold === 55) return '55%';
            return 'Simple majority';
        }}

        function getExploreColValue(measure) {{
            if (matrixState.colField === 'measureType') return measure.display_category_type || null;
            if (matrixState.colField === 'threshold') return getThresholdLabel(measure);
            return measure.display_topic || null;
        }}

        function getExploreRowValue(measure) {{
            if (matrixState.rowGrouping === 'region') {{
                const cnty = (measure.county || '').toUpperCase();
                return cnty === 'STATEWIDE' ? 'Statewide' : (countyToRegion[cnty] || 'Other');
            }}
            if (matrixState.rowGrouping === 'decade') {{
                const year = parseInt(measure.year);
                return Number.isFinite(year) ? `${{Math.floor(year / 10) * 10}}s` : 'Unknown';
            }}
            if (matrixState.rowGrouping === 'year') {{
                const year = parseInt(measure.year);
                return Number.isFinite(year) ? String(year) : 'Unknown';
            }}
            return measure.county || 'Unknown';
        }}

        function createExploreCell() {{
            return {{
                passed: 0,
                total: 0,
                trapped: 0,
                close: 0,
                yesSum: 0,
                yesCount: 0,
                measures: []
            }};
        }}

        function addMeasureToExploreCell(cell, measure) {{
            cell.total++;
            cell.passed += measure.passed;
            cell.measures.push(measure);

            const pct = measure.percent_yes;
            if (pct != null && pct >= 0 && pct <= 100) {{
                cell.yesSum += pct;
                cell.yesCount++;
                const threshold = getMeasureThreshold(measure);
                if (Math.abs(pct - threshold) <= 5) cell.close++;
                if (measure.passed === 0 && pct > 50) cell.trapped++;
            }}
        }}

        function finalizeExploreCell(cell, baselineCell = null, maxVolume = 0) {{
            const passRate = cell.total > 0 ? (100 * cell.passed / cell.total) : null;
            const avgYes = cell.yesCount > 0 ? (cell.yesSum / cell.yesCount) : null;
            const closeRate = cell.total > 0 ? (100 * cell.close / cell.total) : null;
            const trapRate = cell.total > 0 ? (100 * cell.trapped / cell.total) : null;
            const baselineRate = baselineCell && baselineCell.total > 0 ? (100 * baselineCell.passed / baselineCell.total) : null;
            const baselineDelta = passRate != null && baselineRate != null ? passRate - baselineRate : null;
            const reliability = cell.total >= 10 ? 'solid' : cell.total >= 3 ? 'limited' : cell.total > 0 ? 'anecdotal' : 'empty';
            return {{ ...cell, passRate, avgYes, closeRate, trapRate, baselineRate, baselineDelta, reliability, maxVolume }};
        }}

        function buildExploreMatrixData() {{
            const colLabel = matrixState.colField === 'measureType' ? 'measure types'
                : matrixState.colField === 'threshold' ? 'thresholds'
                : 'topics';
            const rowLabel = matrixState.rowGrouping === 'region' ? 'regions'
                : matrixState.rowGrouping === 'decade' ? 'decades'
                : matrixState.rowGrouping === 'year' ? 'years'
                : 'jurisdictions';

            const valid = filteredMeasures.filter(m => (m.passed === 1 || m.passed === 0) && getExploreColValue(m));
            const colSet = new Set();
            valid.forEach(m => colSet.add(getExploreColValue(m)));

            const canonicalOrder = matrixState.colField === 'measureType' ? CANONICAL_TYPE_ORDER
                : matrixState.colField === 'threshold' ? ['Simple majority', '55%', 'Two-thirds']
                : CANONICAL_TOPIC_ORDER;
            const columns = canonicalOrder.filter(t => colSet.has(t));
            colSet.forEach(t => {{ if (!columns.includes(t)) columns.push(t); }});

            const matrix = {{}};
            const rowTotals = {{}};
            const colTotals = {{}};
            const grandTotal = createExploreCell();
            columns.forEach(col => colTotals[col] = createExploreCell());

            valid.forEach(m => {{
                const rowKey = getExploreRowValue(m);
                const colValue = getExploreColValue(m);
                if (!matrix[rowKey]) matrix[rowKey] = {{}};
                if (!matrix[rowKey][colValue]) matrix[rowKey][colValue] = createExploreCell();
                if (!rowTotals[rowKey]) rowTotals[rowKey] = createExploreCell();

                addMeasureToExploreCell(matrix[rowKey][colValue], m);
                addMeasureToExploreCell(rowTotals[rowKey], m);
                addMeasureToExploreCell(colTotals[colValue], m);
                addMeasureToExploreCell(grandTotal, m);
            }});

            const allCells = Object.values(matrix).flatMap(row => Object.values(row));
            const maxVolume = Math.max(1, ...allCells.map(cell => cell.total));
            Object.keys(matrix).forEach(rowKey => {{
                columns.forEach(col => {{
                    if (!matrix[rowKey][col]) matrix[rowKey][col] = createExploreCell();
                    matrix[rowKey][col] = finalizeExploreCell(matrix[rowKey][col], colTotals[col], maxVolume);
                }});
            }});
            Object.keys(rowTotals).forEach(rowKey => {{
                rowTotals[rowKey] = finalizeExploreCell(rowTotals[rowKey], grandTotal, maxVolume);
            }});
            columns.forEach(col => {{
                colTotals[col] = finalizeExploreCell(colTotals[col], grandTotal, maxVolume);
            }});
            const finalizedGrandTotal = finalizeExploreCell(grandTotal, grandTotal, maxVolume);

            let rows = Object.keys(rowTotals);
            if (matrixState.sortCol && colTotals[matrixState.sortCol]) {{
                rows.sort((a, b) => {{
                    const av = getExploreMetricSortValue(matrix[a]?.[matrixState.sortCol] || createExploreCell());
                    const bv = getExploreMetricSortValue(matrix[b]?.[matrixState.sortCol] || createExploreCell());
                    return matrixState.sortDir === 'desc' ? bv - av : av - bv;
                }});
            }} else if (matrixState.rowSort === 'alpha') {{
                rows.sort((a, b) => a.localeCompare(b, undefined, {{ numeric: true }}));
            }} else if (matrixState.rowSort === 'rate') {{
                rows.sort((a, b) => (rowTotals[b].passRate ?? -1) - (rowTotals[a].passRate ?? -1));
            }} else {{
                rows.sort((a, b) => (rowTotals[b]?.total || 0) - (rowTotals[a]?.total || 0));
            }}

            return {{ valid, columns, rows, matrix, rowTotals, colTotals, grandTotal: finalizedGrandTotal, rowLabel, colLabel, maxVolume }};
        }}

        function getExploreMetricSortValue(cell) {{
            const finalCell = cell.passRate === undefined ? finalizeExploreCell(cell) : cell;
            switch (matrixState.metric) {{
                case 'volume': return finalCell.total || 0;
                case 'avgYes': return finalCell.avgYes ?? -Infinity;
                case 'baseline': return finalCell.baselineDelta ?? -Infinity;
                case 'close': return finalCell.close || 0;
                case 'trap': return finalCell.trapped || 0;
                default: return finalCell.passRate ?? -Infinity;
            }}
        }}

        function getExploreMetricLabel() {{
            const labels = {{
                passRate: 'Pass Rate',
                volume: 'Volume',
                avgYes: 'Avg Yes Vote',
                baseline: 'Vs. Baseline',
                close: 'Close Calls',
                trap: 'Threshold Trap'
            }};
            return labels[matrixState.metric] || 'Pass Rate';
        }}

        function renderExploreSummary(data) {{
            const reliableCells = [];
            data.rows.forEach(row => {{
                data.columns.forEach(col => {{
                    const cell = data.matrix[row][col];
                    if (cell.total >= 10) reliableCells.push({{ row, col, cell }});
                }});
            }});
            const high = [...reliableCells].sort((a, b) => (b.cell.passRate ?? -1) - (a.cell.passRate ?? -1))[0];
            const low = [...reliableCells].sort((a, b) => (a.cell.passRate ?? 101) - (b.cell.passRate ?? 101))[0];
            const volume = [...reliableCells].sort((a, b) => b.cell.total - a.cell.total)[0];
            const trap = [...reliableCells].sort((a, b) => b.cell.trapped - a.cell.trapped)[0];
            const sparseCells = data.rows.length * data.columns.length - reliableCells.length;
            const sparseShare = data.rows.length && data.columns.length ? Math.round(100 * sparseCells / (data.rows.length * data.columns.length)) : 0;
            const card = (eyebrow, title, detail) => `
                <div class="matrix-insight-card">
                    <span>${{escapeHtml(eyebrow)}}</span>
                    <strong>${{escapeHtml(title)}}</strong>
                    <em>${{escapeHtml(detail)}}</em>
                </div>`;
            return `<div class="matrix-insight-strip">
                ${{high ? card('Highest reliable pass rate', `${{high.row}} / ${{high.col}}`, `${{Math.round(high.cell.passRate)}}% passed across ${{high.cell.total}} measures`) : card('Highest reliable pass rate', 'Not enough data', 'Need at least 10 measures per cell')}}
                ${{low ? card('Lowest reliable pass rate', `${{low.row}} / ${{low.col}}`, `${{Math.round(low.cell.passRate)}}% passed across ${{low.cell.total}} measures`) : card('Lowest reliable pass rate', 'Not enough data', 'Need at least 10 measures per cell')}}
                ${{volume ? card('Largest cluster', `${{volume.row}} / ${{volume.col}}`, `${{volume.cell.total.toLocaleString()}} measures in this cell`) : card('Largest cluster', 'No cluster', 'Adjust filters to include outcomes')}}
                ${{trap && trap.cell.trapped > 0 ? card('Most threshold traps', `${{trap.row}} / ${{trap.col}}`, `${{trap.cell.trapped}} majority-supported failures`) : card('Reliability note', `${{sparseShare}}% sparse`, 'Cells below 10 measures are visually de-emphasized')}}
            </div>`;
        }}

        function renderExploreToolbar(data) {{
            const metric = matrixState.metric;
            return `<div class="matrix-toolbar">
                <span>${{data.valid.length.toLocaleString()}} measures with outcomes - ${{data.rows.length}} ${{data.rowLabel}} x ${{data.columns.length}} ${{data.colLabel}}</span>
                <div class="matrix-toolbar-group">
                    <span class="matrix-toolbar-group-label">Columns</span>
                    <div class="matrix-col-toggle">
                        <button class="${{matrixState.colField === 'topic' ? 'active' : ''}}" onclick="setMatrixColField('topic')">Topic</button>
                        <button class="${{matrixState.colField === 'measureType' ? 'active' : ''}}" onclick="setMatrixColField('measureType')">Measure Type</button>
                        <button class="${{matrixState.colField === 'threshold' ? 'active' : ''}}" onclick="setMatrixColField('threshold')">Threshold</button>
                    </div>
                </div>
                <label>Rows:
                    <select onchange="setMatrixRowGrouping(this.value)">
                        <option value="jurisdiction" ${{matrixState.rowGrouping==='jurisdiction'?'selected':''}}>Jurisdictions</option>
                        <option value="region" ${{matrixState.rowGrouping==='region'?'selected':''}}>Regions</option>
                        <option value="decade" ${{matrixState.rowGrouping==='decade'?'selected':''}}>Decades</option>
                        <option value="year" ${{matrixState.rowGrouping==='year'?'selected':''}}>Years</option>
                    </select>
                </label>
                <label>Metric:
                    <select onchange="setMatrixMetric(this.value)">
                        <option value="passRate" ${{metric==='passRate'?'selected':''}}>Pass Rate</option>
                        <option value="volume" ${{metric==='volume'?'selected':''}}>Volume</option>
                        <option value="avgYes" ${{metric==='avgYes'?'selected':''}}>Avg Yes Vote</option>
                        <option value="baseline" ${{metric==='baseline'?'selected':''}}>Vs. Baseline</option>
                        <option value="close" ${{metric==='close'?'selected':''}}>Close Calls</option>
                        <option value="trap" ${{metric==='trap'?'selected':''}}>Threshold Trap</option>
                    </select>
                </label>
                <label>Sort:
                    <select onchange="setMatrixRowSort(this.value)">
                        <option value="count" ${{matrixState.rowSort==='count'?'selected':''}}>By count</option>
                        <option value="alpha" ${{matrixState.rowSort==='alpha'?'selected':''}}>A-Z</option>
                        <option value="rate" ${{matrixState.rowSort==='rate'?'selected':''}}>By pass rate</option>
                    </select>
                </label>
                <label>Min n:
                    <select onchange="setMatrixMinN(parseInt(this.value))">
                        <option value="0" ${{matrixState.minN===0?'selected':''}}>All</option>
                        <option value="3" ${{matrixState.minN===3?'selected':''}}>3+</option>
                        <option value="5" ${{matrixState.minN===5?'selected':''}}>5+</option>
                        <option value="10" ${{matrixState.minN===10?'selected':''}}>10+</option>
                    </select>
                </label>
                <button class="matrix-reset-btn" type="button" onclick="resetMatrixControls()">Reset Explore</button>
                <div class="matrix-legend">
                    <span class="matrix-legend-label">${{escapeHtml(getExploreMetricLabel())}}</span>
                    <div class="matrix-legend-bar">
                        <span style="background:#E54D4D"></span>
                        <span style="background:#EA7A3F"></span>
                        <span style="background:#F0A030"></span>
                        <span style="background:#7CB86A"></span>
                        <span style="background:#2D9D78"></span>
                    </div>
                    <span style="opacity:0.5; margin-left:8px; color:#666;">o</span><span style="color:#888;font-size:0.7rem;margin-left:2px;">low n</span>
                </div>
            </div>`;
        }}

        function getExploreCellPresentation(cell) {{
            if (!cell || cell.total === 0) return {{ text: '-', subtext: '', bg: '#F0EDE8', empty: true }};
            switch (matrixState.metric) {{
                case 'volume':
                    return {{ text: cell.total.toLocaleString(), subtext: `${{cell.passed}} passed`, bg: matrixVolumeColor(cell.total, cell.maxVolume) }};
                case 'avgYes':
                    return {{ text: cell.avgYes == null ? 'n/a' : `${{cell.avgYes.toFixed(1)}}%`, subtext: `${{cell.yesCount}} with vote %`, bg: matrixYesColor(cell.avgYes) }};
                case 'baseline':
                    return {{ text: cell.baselineDelta == null ? 'n/a' : `${{cell.baselineDelta >= 0 ? '+' : ''}}${{cell.baselineDelta.toFixed(0)}}pt`, subtext: `${{Math.round(cell.passRate ?? 0)}}% pass`, bg: matrixDeltaColor(cell.baselineDelta) }};
                case 'close':
                    return {{ text: String(cell.close), subtext: `${{Math.round(cell.closeRate || 0)}}% close`, bg: trapCellColor(cell.close, cell.total) }};
                case 'trap':
                    return {{ text: String(cell.trapped), subtext: `${{Math.round(cell.trapRate || 0)}}% trap`, bg: trapCellColor(cell.trapped, cell.total) }};
                default:
                    return {{ text: `${{Math.round(cell.passRate ?? 0)}}%`, subtext: String(cell.total), bg: matrixCellColor(cell.passed, cell.total) }};
            }}
        }}

        function renderExploreCell(cell, rowKey, colValue, isTotal = false) {{
            if (!cell || cell.total === 0 || (!isTotal && cell.total < matrixState.minN)) {{
                return '<td class="matrix-cell empty-cell"><span class="cell-rate">-</span></td>';
            }}
            const presentation = getExploreCellPresentation(cell);
            const lowClass = !isTotal && cell.total < 3 ? 'low-conf' : !isTotal && cell.total < 10 ? 'limited-conf' : '';
            const rEsc = escapeJsString(rowKey);
            const cEsc = escapeJsString(colValue);
            const detail = `${{rowKey}}, ${{colValue}}: ${{getExploreMetricLabel()}} ${{presentation.text}}; ${{cell.passed}} of ${{cell.total}} passed`;
            const attrs = isTotal ? '' : `role="button" tabindex="0" onclick="matrixCellClick('${{rEsc}}','${{cEsc}}')" onkeydown="if(event.key==='Enter')matrixCellClick('${{rEsc}}','${{cEsc}}')"`;
            return `<td class="matrix-cell ${{lowClass}}" style="background:${{presentation.bg}}" ${{attrs}} title="${{escapeAttr(detail)}}" aria-label="${{escapeAttr(detail)}}">
                <span class="cell-rate">${{escapeHtml(presentation.text)}}</span>
                <span class="cell-count">${{escapeHtml(presentation.subtext)}}</span>
                ${{!isTotal && cell.total < 10 ? `<span class="cell-note">${{cell.reliability}}</span>` : ''}}
            </td>`;
        }}

        function renderMatrixV2() {{
            const data = buildExploreMatrixData();

            if (data.valid.length === 0) {{
                return `<div class="empty-state">
                    <div class="empty-icon">📊</div>
                    <h3>No outcome data</h3>
                    <p>Adjust filters to include measures with pass/fail results</p>
                </div>`;
            }}

            const matrixDensityClass = data.rows.length <= 16 ? 'matrix-compact' : '';
            let html = `<div class="matrix-wrapper ${{matrixDensityClass}}">`;
            html += renderExploreToolbar(data);
            html += renderExploreSummary(data);
            html += '<div class="matrix-top-scroll" aria-hidden="true"><div class="matrix-top-scroll-inner"></div></div>';
            html += '<div class="matrix-scroll"><table class="matrix-table" role="grid">';

            const rowHeader = matrixState.rowGrouping === 'region' ? 'Region'
                : matrixState.rowGrouping === 'decade' ? 'Decade'
                : matrixState.rowGrouping === 'year' ? 'Year'
                : 'Jurisdiction';
            const jSortCls = !matrixState.sortCol ? 'sorted-desc' : '';
            html += '<thead><tr>';
            html += `<th class="${{jSortCls}}" role="button" tabindex="0" onclick="sortMatrixByRow()" onkeydown="if(event.key==='Enter')sortMatrixByRow()">${{rowHeader}}</th>`;
            data.columns.forEach(col => {{
                const cls = matrixState.sortCol === col ? (matrixState.sortDir === 'asc' ? 'sorted-asc' : 'sorted-desc') : '';
                const escaped = escapeJsString(col);
                html += `<th class="${{cls}}" role="button" tabindex="0" onclick="sortMatrixByCol('${{escaped}}')" onkeydown="if(event.key==='Enter')sortMatrixByCol('${{escaped}}')" title="${{escapeAttr(col)}}">${{escapeHtml(col)}}</th>`;
            }});
            html += '<th>All</th></tr></thead><tbody>';

            data.rows.forEach(row => {{
                const rowTotal = data.rowTotals[row];
                const rEsc = escapeJsString(row);
                html += `<tr><td role="button" tabindex="0" onclick="exploreFilterToCounty('${{rEsc}}')" onkeydown="if(event.key==='Enter')exploreFilterToCounty('${{rEsc}}')">${{escapeHtml(row)}} <span class="cell-count">(${{rowTotal.total}})</span></td>`;
                data.columns.forEach(col => {{
                    html += renderExploreCell(data.matrix[row][col], row, col);
                }});
                html += renderExploreCell(rowTotal, row, 'All', true);
                html += '</tr>';
            }});

            html += '<tr class="matrix-totals"><td>All</td>';
            data.columns.forEach(col => {{
                html += renderExploreCell(data.colTotals[col], 'All', col, true);
            }});
            html += renderExploreCell(data.grandTotal, 'All', 'All', true);
            html += '</tr></tbody>';

            html += '<tfoot><tr>';
            html += `<th role="button" tabindex="0" onclick="sortMatrixByRow()" onkeydown="if(event.key==='Enter')sortMatrixByRow()">${{rowHeader}}</th>`;
            data.columns.forEach(col => {{
                const cls = matrixState.sortCol === col ? (matrixState.sortDir === 'asc' ? 'sorted-asc' : 'sorted-desc') : '';
                const escaped = escapeJsString(col);
                html += `<th class="${{cls}}" role="button" tabindex="0" onclick="sortMatrixByCol('${{escaped}}')" onkeydown="if(event.key==='Enter')sortMatrixByCol('${{escaped}}')" title="${{escapeAttr(col)}}">${{escapeHtml(col)}}</th>`;
            }});
            html += '<th>All</th></tr></tfoot></table></div></div>';
            return html;
        }}

        function renderMatrix() {{
            return renderMatrixV2();
            // Determine which field to use for columns based on toggle
            const colFieldKey = matrixState.colField === 'measureType' ? 'display_category_type' : 'display_topic';
            const colLabel = matrixState.colField === 'measureType' ? 'measure types' : 'topics';

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

            // Use canonical column ordering (stable across filter changes)
            const canonicalOrder = matrixState.colField === 'measureType' ? CANONICAL_TYPE_ORDER : CANONICAL_TOPIC_ORDER;
            const topics = canonicalOrder.filter(t => topicSet.has(t));
            // Append any columns not in canonical order (future-proofing)
            topicSet.forEach(t => {{ if (!topics.includes(t)) topics.push(t); }});

            // Build matrix — aggregate by row key (county or region)
            const matrix = {{}};
            const colTotals = {{}};
            const rowTotals = {{}};
            topics.forEach(t => colTotals[t] = {{passed: 0, total: 0, trapped: 0}});
            const useRegions = matrixState.rowGrouping === 'region';
            const isTrapMode = matrixState.metric === 'trap';

            valid.forEach(m => {{
                let rowKey;
                if (useRegions) {{
                    const cnty = (m.county || '').toUpperCase();
                    rowKey = cnty === 'STATEWIDE' ? 'Statewide' : (countyToRegion[cnty] || 'Other');
                }} else {{
                    rowKey = m.county || 'Unknown';
                }}
                const t = m[colFieldKey];
                if (!matrix[rowKey]) matrix[rowKey] = {{}};
                if (!matrix[rowKey][t]) matrix[rowKey][t] = {{passed: 0, total: 0, trapped: 0}};
                matrix[rowKey][t].total++;
                matrix[rowKey][t].passed += m.passed;
                if (!rowTotals[rowKey]) rowTotals[rowKey] = {{passed: 0, total: 0, trapped: 0}};
                rowTotals[rowKey].total++;
                rowTotals[rowKey].passed += m.passed;
                colTotals[t].total++;
                colTotals[t].passed += m.passed;
                // Threshold trap: majority yes (>50%) but failed
                // Covers 50%, 55% (Prop 39 school bonds), and 66.67% (2/3 supermajority)
                const pct = m.percent_yes;
                if (m.passed === 0 && pct != null && pct >= 0 && pct <= 100 && pct > 50) {{
                    matrix[rowKey][t].trapped++;
                    rowTotals[rowKey].trapped++;
                    colTotals[t].trapped++;
                }}
            }});

            // Collect and sort row keys
            let counties = Object.keys(rowTotals);
            if (matrixState.sortCol && colTotals[matrixState.sortCol]) {{
                counties.sort((a, b) => {{
                    const ac = (matrix[a] && matrix[a][matrixState.sortCol]) || {{passed:0, total:0}};
                    const bc = (matrix[b] && matrix[b][matrixState.sortCol]) || {{passed:0, total:0}};
                    const ar = ac.total > 0 ? ac.passed / ac.total : -1;
                    const br = bc.total > 0 ? bc.passed / bc.total : -1;
                    return matrixState.sortDir === 'desc' ? br - ar : ar - br;
                }});
            }} else if (matrixState.rowSort === 'alpha') {{
                counties.sort((a, b) => a.localeCompare(b));
            }} else if (matrixState.rowSort === 'rate') {{
                counties.sort((a, b) => {{
                    const ar = rowTotals[a]?.total > 0 ? rowTotals[a].passed / rowTotals[a].total : -1;
                    const br = rowTotals[b]?.total > 0 ? rowTotals[b].passed / rowTotals[b].total : -1;
                    return br - ar;
                }});
            }} else {{
                counties.sort((a, b) => (rowTotals[b]?.total || 0) - (rowTotals[a]?.total || 0));
            }}

            // Build HTML
            const matrixDensityClass = counties.length <= 16 ? 'matrix-compact' : '';
            let html = `<div class="matrix-wrapper ${{matrixDensityClass}}">`;

            // Toolbar with info, controls, and legend
            const rowLabel = useRegions ? 'regions' : 'jurisdictions';
            html += `<div class="matrix-toolbar">
                <span>${{valid.length.toLocaleString()}} measures with outcomes · ${{counties.length}} ${{rowLabel}} × ${{topics.length}} ${{colLabel}}</span>
                <div class="matrix-col-toggle">
                    <button class="${{matrixState.colField === 'topic' ? 'active' : ''}}" onclick="setMatrixColField('topic')">Topic</button>
                    <button class="${{matrixState.colField === 'measureType' ? 'active' : ''}}" onclick="setMatrixColField('measureType')">Measure Type</button>
                </div>
                <label>Rows:
                    <select onchange="setMatrixRowGrouping(this.value)">
                        <option value="jurisdiction" ${{matrixState.rowGrouping==='jurisdiction'?'selected':''}}>Jurisdictions</option>
                        <option value="region" ${{matrixState.rowGrouping==='region'?'selected':''}}>Regions</option>
                    </select>
                </label>
                <label>Sort:
                    <select onchange="setMatrixRowSort(this.value)">
                        <option value="count" ${{matrixState.rowSort==='count'?'selected':''}}>By count</option>
                        <option value="alpha" ${{matrixState.rowSort==='alpha'?'selected':''}}>A–Z</option>
                        <option value="rate" ${{matrixState.rowSort==='rate'?'selected':''}}>By pass rate</option>
                    </select>
                </label>
                <label>Min n:
                    <select onchange="setMatrixMinN(parseInt(this.value))">
                        <option value="0" ${{matrixState.minN===0?'selected':''}}>All</option>
                        <option value="3" ${{matrixState.minN===3?'selected':''}}>3+</option>
                        <option value="5" ${{matrixState.minN===5?'selected':''}}>5+</option>
                        <option value="10" ${{matrixState.minN===10?'selected':''}}>10+</option>
                    </select>
                </label>
                <div class="matrix-col-toggle">
                    <button class="${{matrixState.metric === 'passRate' ? 'active' : ''}}" onclick="setMatrixMetric('passRate')">Pass Rate</button>
                    <button class="${{matrixState.metric === 'trap' ? 'active' : ''}}" onclick="setMatrixMetric('trap')" title="Measures that won majority support but failed due to supermajority threshold">Threshold Trap</button>
                </div>
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
                    <span style="opacity:0.5; margin-left:8px; color:#666;">●</span><span style="color:#888;font-size:0.7rem;margin-left:2px;">sparse</span>
                </div>
            </div>`;
            html += '<div class="matrix-top-scroll" aria-hidden="true"><div class="matrix-top-scroll-inner"></div></div>';
            html += '<div class="matrix-scroll"><table class="matrix-table" role="grid">';

            // Header
            html += '<thead><tr>';
            const jSortCls = !matrixState.sortCol ? 'sorted-desc' : '';
            const rowHeader = useRegions ? 'Region' : 'Jurisdiction';
            html += `<th class="${{jSortCls}}" role="button" tabindex="0"
                onclick="sortMatrixByRow()" onkeydown="if(event.key==='Enter')sortMatrixByRow()">${{rowHeader}}</th>`;
            topics.forEach(t => {{
                const cls = matrixState.sortCol === t ? (matrixState.sortDir === 'asc' ? 'sorted-asc' : 'sorted-desc') : '';
                const escaped = t.replace(/'/g, "\\\\'");
                html += `<th class="${{cls}}" role="button" tabindex="0"
                    onclick="sortMatrixByCol('${{escaped}}')"
                    onkeydown="if(event.key==='Enter')sortMatrixByCol('${{escaped}}')"
                    title="${{escapeAttr(t)}}">${{escapeHtml(t)}}</th>`;
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
                    >${{escapeHtml(county)}} <span class="cell-count">(${{rt.total}})</span></td>`;
                topics.forEach(t => {{
                    const cell = (matrix[county] && matrix[county][t]) || {{passed:0, total:0, trapped:0}};
                    if (cell.total === 0 || cell.total < matrixState.minN) {{
                        html += '<td class="matrix-cell empty-cell">—</td>';
                    }} else if (isTrapMode) {{
                        // Threshold trap mode: show trapped count
                        const trapRate = cell.total > 0 ? Math.round(100 * cell.trapped / cell.total) : 0;
                        const bg = trapCellColor(cell.trapped, cell.total);
                        const tEsc = t.replace(/'/g, "\\\\'");
                        const label = `${{escapeAttr(county)}}, ${{escapeAttr(t)}}: ${{cell.trapped}} of ${{cell.total}} measures won majority but failed (${{trapRate}}%)`;
                        html += `<td class="matrix-cell" style="background:${{bg}}"
                            role="button" tabindex="0"
                            onclick="matrixCellClick('${{cEsc}}','${{tEsc}}')"
                            onkeydown="if(event.key==='Enter')matrixCellClick('${{cEsc}}','${{tEsc}}')"
                            title="${{label}}" aria-label="${{label}}">
                            ${{cell.trapped > 0
                                ? `<span class="cell-rate">${{cell.trapped}}</span><span class="cell-count">${{trapRate}}%</span>`
                                : `<span class="cell-rate" style="opacity:0.3;">0</span>`
                            }}
                        </td>`;
                    }} else {{
                        const rate = Math.round(100 * cell.passed / cell.total);
                        const bg = matrixCellColor(cell.passed, cell.total);
                        const low = cell.total < 3;
                        const tEsc = t.replace(/'/g, "\\\\'");
                        const label = `${{escapeAttr(county)}}, ${{escapeAttr(t)}}: ${{rate}}% passed (${{cell.passed}} of ${{cell.total}})${{low ? ' — small sample' : ''}}`;
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
                if (isTrapMode) {{
                    const rowTrapRate = rt.total > 0 ? Math.round(100 * rt.trapped / rt.total) : 0;
                    html += `<td class="matrix-cell" style="background:${{trapCellColor(rt.trapped, rt.total)}}">
                        <span class="cell-rate">${{rt.trapped}}</span><span class="cell-count">${{rowTrapRate}}%</span></td>`;
                }} else {{
                    html += `<td class="matrix-cell" style="background:${{matrixCellColor(rt.passed, rt.total)}}">
                        <span class="cell-rate">${{rowRate}}%</span><span class="cell-count">${{rt.total}}</span></td>`;
                }}
                html += '</tr>';
            }});

            // Totals row
            const gt = {{passed:0, total:0, trapped:0}};
            html += '<tr class="matrix-totals"><td>All</td>';
            topics.forEach(t => {{
                const ct = colTotals[t];
                gt.passed += ct.passed;
                gt.total += ct.total;
                gt.trapped += ct.trapped;
                if (isTrapMode) {{
                    const trapRate = ct.total > 0 ? Math.round(100 * ct.trapped / ct.total) : 0;
                    html += `<td><span class="cell-rate">${{ct.trapped}}</span><span class="cell-count">${{trapRate}}%</span></td>`;
                }} else {{
                    const rate = ct.total > 0 ? Math.round(100 * ct.passed / ct.total) : 0;
                    html += `<td><span class="cell-rate">${{rate}}%</span><span class="cell-count">${{ct.total}}</span></td>`;
                }}
            }});
            if (isTrapMode) {{
                const gtTrapRate = gt.total > 0 ? Math.round(100 * gt.trapped / gt.total) : 0;
                html += `<td><span class="cell-rate">${{gt.trapped}}</span><span class="cell-count">${{gtTrapRate}}%</span></td>`;
            }} else {{
                html += `<td><span class="cell-rate">${{gt.total > 0 ? Math.round(100*gt.passed/gt.total) : 0}}%</span><span class="cell-count">${{gt.total}}</span></td>`;
            }}
            html += '</tr></tbody>';

            // Bottom column labels mirror the header for easier reading after vertical scrolling.
            html += '<tfoot><tr>';
            html += `<th role="button" tabindex="0"
                onclick="sortMatrixByRow()" onkeydown="if(event.key==='Enter')sortMatrixByRow()">${{rowHeader}}</th>`;
            topics.forEach(t => {{
                const cls = matrixState.sortCol === t ? (matrixState.sortDir === 'asc' ? 'sorted-asc' : 'sorted-desc') : '';
                const escaped = t.replace(/'/g, "\\\\'");
                html += `<th class="${{cls}}" role="button" tabindex="0"
                    onclick="sortMatrixByCol('${{escaped}}')"
                    onkeydown="if(event.key==='Enter')sortMatrixByCol('${{escaped}}')"
                    title="${{escapeAttr(t)}}">${{escapeHtml(t)}}</th>`;
            }});
            html += '<th>All</th></tr></tfoot></table></div></div>';

            return html;
        }}

        function syncMatrixScrollbars() {{
            const topScroll = document.querySelector('.matrix-top-scroll');
            const topInner = document.querySelector('.matrix-top-scroll-inner');
            const matrixScroll = document.querySelector('.matrix-scroll');
            const matrixTable = document.querySelector('.matrix-table');
            if (!topScroll || !topInner || !matrixScroll || !matrixTable) return;

            const updateTopWidth = () => {{
                topInner.style.width = matrixTable.scrollWidth + 'px';
                topScroll.scrollLeft = matrixScroll.scrollLeft;
            }};
            updateTopWidth();
            requestAnimationFrame(updateTopWidth);

            let syncing = false;
            topScroll.addEventListener('scroll', () => {{
                if (syncing) return;
                syncing = true;
                matrixScroll.scrollLeft = topScroll.scrollLeft;
                syncing = false;
            }});
            matrixScroll.addEventListener('scroll', () => {{
                if (syncing) return;
                syncing = true;
                topScroll.scrollLeft = matrixScroll.scrollLeft;
                syncing = false;
            }});
        }}

        function sortMatrixByCol(topic) {{
            if (matrixState.sortCol === topic) {{
                matrixState.sortDir = matrixState.sortDir === 'desc' ? 'asc' : 'desc';
            }} else {{
                matrixState.sortCol = topic;
                matrixState.sortDir = 'desc';
            }}
            displayResults();
        }}

        function sortMatrixByRow() {{
            matrixState.sortCol = null;
            displayResults();
        }}

        function setMatrixRowSort(mode) {{
            matrixState.rowSort = mode;
            matrixRowMode = mode; // keep legacy alias
            matrixState.sortCol = null;
            displayResults();
        }}

        function setMatrixColField(field) {{
            matrixState.colField = field;
            matrixColField = field; // keep legacy alias
            matrixState.sortCol = null;
            displayResults();
        }}

        function setMatrixRowGrouping(grouping) {{
            matrixState.rowGrouping = grouping;
            matrixState.sortCol = null;
            displayResults();
        }}

        function setMatrixMinN(n) {{
            matrixState.minN = n;
            displayResults();
        }}

        function setMatrixMetric(metric) {{
            matrixState.metric = metric;
            displayResults();
        }}

        function resetMatrixControls() {{
            matrixState.rowGrouping = 'jurisdiction';
            matrixState.rowSort = 'count';
            matrixState.colField = 'topic';
            matrixState.sortCol = null;
            matrixState.sortDir = 'desc';
            matrixState.minN = 0;
            matrixState.metric = 'passRate';
            matrixRowMode = matrixState.rowSort;
            matrixColField = matrixState.colField;
            displayResults();
        }}

        // Threshold trap color: purple scale
        function trapCellColor(trapCount, total) {{
            if (total < 1 || trapCount === 0) return '#f0eee8';
            const rate = trapCount / total;
            // Light lavender (0%) → Deep purple (100% trapped)
            const r = Math.round(240 - 120 * rate);
            const g = Math.round(238 - 158 * rate);
            const b = Math.round(232 + 23 * rate);
            return `rgb(${{r}}, ${{g}}, ${{b}})`;
        }}

        function matrixCellClick(rowKey, colValue) {{
            // Show cell detail modal instead of drilling down
            const cellMeasures = filteredMeasures.filter(m =>
                (m.passed === 1 || m.passed === 0) &&
                getExploreColValue(m) === colValue &&
                getExploreRowValue(m) === rowKey
            );

            if (cellMeasures.length === 0) return;

            // Compute stats
            const passed = cellMeasures.filter(m => m.passed === 1).length;
            const total = cellMeasures.length;
            const passRate = Math.round(100 * passed / total);
            const validPct = cellMeasures.filter(m => m.percent_yes != null && m.percent_yes >= 0 && m.percent_yes <= 100);
            const avgYes = validPct.length > 0 ? (validPct.reduce((s, m) => s + m.percent_yes, 0) / validPct.length).toFixed(1) : null;
            const trapped = validPct.filter(m => m.passed === 0 && m.percent_yes > 50).length;
            const closeCalls = validPct.filter(m => Math.abs(m.percent_yes - getMeasureThreshold(m)) <= 5).length;
            const reliability = total >= 10 ? 'solid' : total >= 3 ? 'limited' : 'anecdotal';

            // Decade breakdown
            const decades = {{}};
            cellMeasures.forEach(m => {{
                const d = m.decade || (m.year ? Math.floor(m.year / 10) * 10 : null);
                if (d) {{
                    if (!decades[d]) decades[d] = {{passed: 0, total: 0}};
                    decades[d].total++;
                    decades[d].passed += m.passed;
                }}
            }});
            const decadeKeys = Object.keys(decades).sort();

            // Notable measures: tightest race + biggest win
            const withPct = cellMeasures.filter(m => m.percent_yes != null && m.percent_yes >= 0 && m.percent_yes <= 100);
            const tightest = [...withPct].sort((a, b) => Math.abs(a.percent_yes - 50) - Math.abs(b.percent_yes - 50)).slice(0, 2);
            const biggest = [...withPct].sort((a, b) => b.percent_yes - a.percent_yes).slice(0, 1);
            const notable = [...new Map([...tightest, ...biggest].map(m => [m.id, m])).values()].slice(0, 3);

            // Build modal content
            const modal = document.getElementById('matrixCellModal');
            document.getElementById('matrixCellTitle').textContent = `${{rowKey}} — ${{colValue}}`;

            let body = `
                <div style="display:flex;gap:1.5rem;margin-bottom:1rem;align-items:center;">
                    <div style="text-align:center;">
                        <div style="font-size:2rem;font-weight:700;color:${{matrixCellColor(passed, total)}}">${{passRate}}%</div>
                        <div style="font-size:0.75rem;color:#888;">pass rate (${{passed}}/${{total}})</div>
                    </div>
                    ${{avgYes ? `<div style="text-align:center;">
                        <div style="font-size:1.5rem;font-weight:600;color:#555;">${{avgYes}}%</div>
                        <div style="font-size:0.75rem;color:#888;">avg YES vote</div>
                    </div>` : ''}}
                </div>`;
            body = `
                <div class="matrix-modal-metrics">
                    <div class="matrix-modal-metric"><strong>${{passRate}}%</strong><span>Pass rate (${{passed}}/${{total}})</span></div>
                    <div class="matrix-modal-metric"><strong>${{avgYes ? avgYes + '%' : 'n/a'}}</strong><span>Avg yes vote</span></div>
                    <div class="matrix-modal-metric"><strong>${{closeCalls}}</strong><span>Close calls</span></div>
                    <div class="matrix-modal-metric"><strong>${{trapped}}</strong><span>Threshold traps</span></div>
                </div>
                <p style="font-size:0.82rem;color:#5F5647;margin:0 0 0.8rem;">Reliability: <strong>${{reliability}}</strong>. Close calls are measures within 5 points of their inferred legal threshold; threshold traps are majority-supported failures.</p>`;

            // Decade chart
            if (decadeKeys.length >= 2) {{
                const maxTotal = Math.max(...decadeKeys.map(d => decades[d].total));
                body += `<div style="margin-bottom:1rem;"><div style="font-size:0.8rem;font-weight:600;margin-bottom:0.5rem;">Pass rate by decade</div>`;
                body += `<div style="display:flex;align-items:flex-end;gap:4px;height:60px;">`;
                decadeKeys.forEach(d => {{
                    const rate = decades[d].total > 0 ? decades[d].passed / decades[d].total : 0;
                    const h = Math.max(4, Math.round(rate * 50));
                    const bg = matrixCellColor(decades[d].passed, decades[d].total);
                    body += `<div style="display:flex;flex-direction:column;align-items:center;flex:1;" title="${{d}}s: ${{Math.round(rate*100)}}% (${{decades[d].passed}}/${{decades[d].total}})">
                        <div style="width:100%;max-width:32px;height:${{h}}px;background:${{bg}};border-radius:3px 3px 0 0;"></div>
                        <div style="font-size:0.6rem;color:#888;margin-top:2px;">${{d}}s</div>
                    </div>`;
                }});
                body += `</div></div>`;
            }}

            // Notable measures
            if (notable.length > 0) {{
                body += `<div style="margin-bottom:1rem;"><div style="font-size:0.8rem;font-weight:600;margin-bottom:0.5rem;">Notable measures</div>`;
                notable.forEach(m => {{
                    const pct = m.percent_yes != null && m.percent_yes <= 100 ? m.percent_yes.toFixed(1) + '% yes' : '';
                    const status = m.passed === 1 ? '<span style="color:#2D9D78;">Passed</span>' : '<span style="color:#E54D4D;">Failed</span>';
                    const title = escapeHtml(m.generated_title || m.summary_title || m.title || `Measure ${{m.measure_letter || '?'}}`);
                    body += `<div style="padding:0.4rem 0;border-bottom:1px solid #eee;font-size:0.8rem;">
                        <div><strong>${{m.year}}</strong> ${{status}} ${{pct ? '· ' + pct : ''}}</div>
                        <div style="color:#555;margin-top:2px;">${{title.substring(0, 120)}}${{title.length > 120 ? '...' : ''}}</div>
                    </div>`;
                }});
                body += `</div>`;
            }}

            // View all button
            const rEsc = rowKey.replace(/'/g, "\\\\'");
            const cEsc = colValue.replace(/'/g, "\\\\'");
            body += `<button onclick="closeMatrixCellModal(); matrixDrillDown('${{rEsc}}','${{cEsc}}')" style="width:100%;padding:0.6rem;background:var(--primary);color:white;border:none;border-radius:6px;cursor:pointer;font-size:0.85rem;font-weight:600;">View all ${{total}} measures &rarr;</button>`;

            document.getElementById('matrixCellBody').innerHTML = body;
            modal.style.display = 'flex';
        }}

        function matrixDrillDown(rowKey, colValue) {{
            // The old drill-down behavior — sets filters and switches to grid
            if (matrixState.colField === 'measureType') {{
                currentFilters.measureTypes = [colValue];
                currentFilters.thresholds = [];
                updateMeasureTypeChipUI();
            }} else if (matrixState.colField === 'threshold') {{
                currentFilters.measureTypes = [];
                currentFilters.topics = [];
                currentFilters.thresholds = [colValue];
            }} else {{
                currentFilters.topics = [colValue];
                currentFilters.thresholds = [];
                updateTopicChipUI();
            }}
            if (matrixState.rowGrouping === 'decade') {{
                const decade = parseInt(rowKey);
                if (Number.isFinite(decade)) {{
                    currentFilters.selectedDecades = [decade];
                    currentFilters.selectedYears = [];
                    renderYearNavigation();
                }}
            }} else if (matrixState.rowGrouping === 'year') {{
                const year = parseInt(rowKey);
                if (Number.isFinite(year)) {{
                    currentFilters.selectedYears = [year];
                    currentFilters.selectedDecades = [];
                    renderYearNavigation();
                }}
            }} else if (matrixState.rowGrouping === 'region' && CA_REGIONS[rowKey]) {{
                currentFilters.regions = [rowKey];
                currentFilters.level = null;
                currentFilters.levelCounty = null;
            }} else if (rowKey !== 'Statewide') {{
                currentFilters.level = 'local';
                currentFilters.levelCounty = rowKey;
            }} else {{
                currentFilters.level = 'statewide';
                currentFilters.levelCounty = null;
            }}
            setView('grid');
            updateLevelChipUI();
            updateFilterCountBadges();
            applyFilters();
        }}

        function closeMatrixCellModal() {{
            document.getElementById('matrixCellModal').style.display = 'none';
        }}

        function exploreFilterToCounty(rowKey) {{
            if (matrixState.rowGrouping === 'decade') {{
                const decade = parseInt(rowKey);
                if (Number.isFinite(decade)) {{
                    currentFilters.selectedDecades = [decade];
                    currentFilters.selectedYears = [];
                    renderYearNavigation();
                }}
            }} else if (matrixState.rowGrouping === 'year') {{
                const year = parseInt(rowKey);
                if (Number.isFinite(year)) {{
                    currentFilters.selectedYears = [year];
                    currentFilters.selectedDecades = [];
                    renderYearNavigation();
                }}
            }} else if (matrixState.rowGrouping === 'region' && CA_REGIONS[rowKey]) {{
                currentFilters.regions = [rowKey];
                currentFilters.level = null;
                currentFilters.levelCounty = null;
            }} else if (rowKey !== 'Statewide') {{
                currentFilters.level = 'local';
                currentFilters.levelCounty = rowKey;
            }} else {{
                currentFilters.level = 'statewide';
                currentFilters.levelCounty = null;
            }}
            setView('grid');
            updateLevelChipUI();
            updateFilterCountBadges();
            applyFilters();
        }}

        let insightsRendered = false;
        let insightsCharts = {{}};
        let countyMapRendered = false;
        let insightsNavInitialized = false;
        let currentInsightsSlide = 0;

        function formatInsightNumber(value) {{
            if (value === null || value === undefined || Number.isNaN(value)) return '—';
            if (typeof value === 'string') return value;
            if (Math.abs(value) >= 1000000000) return (value / 1000000000).toFixed(1) + 'B';
            if (Math.abs(value) >= 1000000) return (value / 1000000).toFixed(1) + 'M';
            return Number(value).toLocaleString();
        }}

        function formatInsightPct(value) {{
            return value === null || value === undefined || Number.isNaN(value) ? '—' : Number(value).toFixed(1) + '%';
        }}

        function updateViewVisibility() {{
            const isInsights = currentView === 'insights';
            const isExplore = currentView === 'explore';
            const insights = document.getElementById('insightsSection');
            if (insights) insights.style.display = isInsights ? 'block' : 'none';

            const visibility = {{
                '.site-intro': isInsights,
                '#statsRibbon': isInsights || isExplore,
                '.filter-section-wrapper': isInsights || isExplore,
                '.results-header': isInsights || isExplore,
                '#resultsContainer': isInsights,
                '#heroSection': isInsights || isExplore,
                '.quiz-section': isInsights || isExplore
            }};
            Object.entries(visibility).forEach(([selector, hide]) => {{
                const el = document.querySelector(selector);
                if (el) el.style.display = hide ? 'none' : '';
            }});
        }}

        function renderInsights() {{
            updateViewVisibility();
            if (insightsRendered) {{
                if (!countyMapRendered) renderCountyMap();
                initializeInsightsNav();
                return;
            }}

            if (!insightsData || !insightsData.overview) {{
                const section = document.getElementById('insightsSection');
                if (section) {{
                    section.innerHTML = '<div class="empty-state"><h3>Insights data is not available</h3><p>Run scripts/generate_insights.py before generating the site.</p></div>';
                }}
                return;
            }}

            renderInsightsMetrics();
            renderInsightsComposition();
            renderInsightsOverviewTops();
            renderInsightsCoverage();
            renderInsightsFindings();
            renderInsightsCharts();
            renderInsightsSparkline();
            renderTrendSummary();
            renderTopicTrendSummary();
            renderTypeInsights();
            renderCountyLeaderboard();
            renderGeographyInsights();
            renderCountyMap();
            renderThresholdCallouts();
            renderStatisticalComparisons();
            renderFinanceInsights();
            renderInsightsMethodology();
            initializeInsightsNav();
            setInsightsSlide(currentInsightsSlide);

            const overview = insightsData.overview || {{}};
            const datasetLabel = document.getElementById('insightsDatasetLabel');
            const generatedLabel = document.getElementById('insightsGeneratedLabel');
            if (datasetLabel) {{
                datasetLabel.textContent = formatInsightNumber(overview.active_measures) + ' active records, ' + formatInsightNumber(overview.county_count) + ' counties';
            }}
            if (generatedLabel && overview.generated_at) {{
                const generatedDate = new Date(overview.generated_at);
                generatedLabel.textContent = 'Updated ' + generatedDate.toLocaleDateString(undefined, {{ year: 'numeric', month: 'short', day: 'numeric' }});
            }}

            insightsRendered = true;
        }}

        function getInsightsSlides() {{
            return Array.from(document.querySelectorAll('.insights-carousel-slide'));
        }}

        function isInsightsCarouselDesktop() {{
            return window.matchMedia('(min-width: 769px)').matches;
        }}

        function setInsightsSlide(index) {{
            const slides = getInsightsSlides();
            const track = document.getElementById('insightsCarouselTrack');
            const viewport = document.querySelector('.insights-carousel-viewport');
            if (!track || slides.length === 0) return;

            const normalized = ((index % slides.length) + slides.length) % slides.length;
            currentInsightsSlide = normalized;

            if (isInsightsCarouselDesktop()) {{
                track.style.transform = `translateX(-${{normalized * 100}}%)`;
                if (viewport) {{
                    requestAnimationFrame(() => {{
                        viewport.style.height = slides[normalized].offsetHeight + 'px';
                    }});
                }}
            }} else {{
                track.style.transform = 'none';
                if (viewport) viewport.style.height = 'auto';
            }}

            const activeId = slides[normalized].id;
            document.querySelectorAll('.insights-side-nav a[href^="#"]').forEach(link => {{
                link.classList.toggle('active', link.getAttribute('href') === '#' + activeId);
            }});

            const status = document.getElementById('insightsCarouselStatus');
            if (status) status.textContent = `${{normalized + 1}} / ${{slides.length}}`;

            setTimeout(() => {{
                Object.values(insightsCharts || {{}}).forEach(chart => {{
                    if (chart && typeof chart.resize === 'function') chart.resize();
                }});
                if (isInsightsCarouselDesktop() && viewport) {{
                    viewport.style.height = slides[normalized].offsetHeight + 'px';
                }}
            }}, 80);
        }}

        function moveInsightsSlide(delta) {{
            setInsightsSlide(currentInsightsSlide + delta);
        }}

        window.addEventListener('resize', () => {{
            if (currentView === 'insights') setInsightsSlide(currentInsightsSlide);
        }});

        function initializeInsightsNav() {{
            const nav = document.querySelector('.insights-side-nav');
            if (!nav) return;
            const links = Array.from(nav.querySelectorAll('a[href^="#"]'));
            const targets = links.map(link => document.querySelector(link.getAttribute('href'))).filter(Boolean);
            if (links.length === 0 || targets.length === 0) return;

            const setActive = id => {{
                links.forEach(link => link.classList.toggle('active', link.getAttribute('href') === '#' + id));
            }};

            if (!insightsNavInitialized) {{
                links.forEach(link => {{
                    link.addEventListener('click', event => {{
                        const target = document.querySelector(link.getAttribute('href'));
                        if (!target) return;
                        event.preventDefault();
                        const slideIndex = getInsightsSlides().findIndex(slide => slide.id === target.id);
                        if (isInsightsCarouselDesktop() && slideIndex >= 0) {{
                            setInsightsSlide(slideIndex);
                        }} else {{
                            setActive(target.id);
                            target.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
                        }}
                    }});
                }});

                if ('IntersectionObserver' in window) {{
                    const observer = new IntersectionObserver(entries => {{
                        if (isInsightsCarouselDesktop()) return;
                        const visible = entries
                            .filter(entry => entry.isIntersecting)
                            .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
                        if (visible && currentView === 'insights') setActive(visible.target.id);
                    }}, {{ root: null, rootMargin: '-18% 0px -68% 0px', threshold: [0, 0.2, 0.5, 1] }});
                    targets.forEach(target => observer.observe(target));
                }}
                insightsNavInitialized = true;
            }}
        }}

        function jumpToInsightsPanel(panelId) {{
            const slides = getInsightsSlides();
            const idx = slides.findIndex(s => s.id === panelId);
            if (isInsightsCarouselDesktop() && idx >= 0) {{
                setInsightsSlide(idx);
            }} else {{
                const target = document.getElementById(panelId);
                if (target) target.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
            }}
        }}

        function renderInsightsMetrics() {{
            const overview = insightsData.overview || {{}};
            const margin = (insightsData.margin_stats && insightsData.margin_stats.close_counts) || {{}};
            const yearSpan = (overview.year_max && overview.year_min)
                ? (overview.year_max - overview.year_min + 1) : null;
            const localShare = overview.local_share;
            const statewideShare = (localShare !== null && localShare !== undefined)
                ? (100 - localShare) : null;

            const metrics = [
                ['Active measures', formatInsightNumber(overview.active_measures),
                    `${{overview.year_min}}–${{overview.year_max}}${{yearSpan ? ' · ' + yearSpan + ' yrs' : ''}}`],
                ['Pass rate', formatInsightPct(overview.pass_rate),
                    `${{formatInsightNumber(overview.decided_measures)}} decided`],
                ['Passed / failed',
                    `${{formatInsightNumber(overview.passed)}} / ${{formatInsightNumber(overview.failed)}}`,
                    'of decided records'],
                ['With vote data', formatInsightNumber(overview.vote_data_measures), 'valid yes/no totals'],
                ['Local measures', formatInsightNumber(overview.local_measures),
                    `${{formatInsightPct(localShare)}} of dataset`],
                ['Statewide measures', formatInsightNumber(overview.statewide_measures),
                    `${{formatInsightPct(statewideShare)}} of dataset`],
                ['Counties covered', `${{overview.county_count || '—'}} of 58`, 'every CA county'],
                ['Close calls', formatInsightNumber(margin.under_5), 'decided by < 5 points']
            ];
            const target = document.getElementById('insightsMetrics');
            if (!target) return;
            target.innerHTML = metrics.map(([label, value, note]) => `
                <div class="insight-metric">
                    <span>${{escapeHtml(label)}}</span>
                    <strong>${{value}}</strong>
                    <small>${{escapeHtml(note || '')}}</small>
                </div>
            `).join('');
        }}

        function renderInsightsComposition() {{
            const target = document.getElementById('insightsComposition');
            if (!target) return;
            const overview = insightsData.overview || {{}};
            const cycles = insightsData.election_cycle_stats || [];

            const total = overview.active_measures || 0;
            const local = overview.local_measures || 0;
            const statewide = overview.statewide_measures || 0;
            const passed = overview.passed || 0;
            const failed = overview.failed || 0;
            const decided = overview.decided_measures || 0;
            const pending = Math.max(total - decided, 0);

            const cycleTotal = cycles.reduce((s, c) => s + (c.total || 0), 0);
            const cycleColors = ['#3B5BDB', '#8B5CF6', '#F59E0B'];
            const cycleSegments = cycles.map((c, i) => ({{
                label: c.cycle,
                value: c.total || 0,
                pct: cycleTotal ? (100 * (c.total || 0) / cycleTotal) : 0,
                color: cycleColors[i % cycleColors.length]
            }}));

            const renderBar = (title, segments, jumpTo, jumpLabel) => {{
                const bar = segments.map(s => `
                    <div class="composition-bar-segment"
                        style="width: ${{s.pct.toFixed(2)}}%; background: ${{s.color}}"
                        title="${{escapeAttr(s.label + ': ' + formatInsightNumber(s.value) + ' (' + s.pct.toFixed(1) + '%)')}}">
                    </div>
                `).join('');
                const legend = segments.map(s => `
                    <div class="composition-legend-item">
                        <span class="composition-legend-swatch" style="background:${{s.color}}"></span>
                        <strong>${{escapeHtml(s.label)}}</strong>
                        <span>${{formatInsightNumber(s.value)}} &middot; ${{s.pct.toFixed(1)}}%</span>
                    </div>
                `).join('');
                const jumpButton = jumpTo
                    ? `<button class="overview-jump-btn" onclick="jumpToInsightsPanel('${{jumpTo}}')">${{escapeHtml(jumpLabel || 'Open panel')}} &rarr;</button>`
                    : '';
                return `
                    <div class="composition-block">
                        <div class="composition-header">
                            <h4>${{escapeHtml(title)}}</h4>
                            ${{jumpButton}}
                        </div>
                        <div class="composition-bar">${{bar}}</div>
                        <div class="composition-legend">${{legend}}</div>
                    </div>
                `;
            }};

            const whereSegments = [
                {{label: 'Local', value: local, pct: total ? 100 * local / total : 0, color: '#7A1F2A'}},
                {{label: 'Statewide', value: statewide, pct: total ? 100 * statewide / total : 0, color: '#C9A03B'}}
            ];
            const outcomeSegments = [
                {{label: 'Passed', value: passed, pct: total ? 100 * passed / total : 0, color: '#2D9D78'}},
                {{label: 'Failed', value: failed, pct: total ? 100 * failed / total : 0, color: '#E54D4D'}},
                {{label: 'Pending', value: pending, pct: total ? 100 * pending / total : 0, color: '#9CA3AF'}}
            ];

            target.innerHTML =
                renderBar('Where measures appear', whereSegments, 'insightsGeographyPanel', 'Open geography') +
                renderBar('How they ended', outcomeSegments, null, null) +
                renderBar('When they are voted on', cycleSegments, 'insightsTrendPanel', 'Open trend');
        }}

        function renderInsightsSparkline() {{
            const ts = insightsData.time_series || [];
            const rows = ts.filter(r => r.year && r.total > 0);
            createInsightChart('insightsOverviewSparkChart', {{
                type: 'bar',
                data: {{
                    labels: rows.map(r => r.year),
                    datasets: [{{
                        data: rows.map(r => r.total),
                        backgroundColor: '#7A1F2A',
                        borderRadius: 1
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        legend: {{ display: false }},
                        tooltip: {{
                            callbacks: {{
                                title: items => items[0].label,
                                label: item => formatInsightNumber(item.parsed.y) + ' measures'
                            }}
                        }}
                    }},
                    scales: {{
                        x: {{ ticks: {{ maxTicksLimit: 8, font: {{ size: 10 }} }}, grid: {{ display: false }} }},
                        y: {{ display: false, beginAtZero: true }}
                    }}
                }}
            }});
        }}

        function renderInsightsOverviewTops() {{
            const target = document.getElementById('insightsOverviewTops');
            if (!target) return;
            const topics = (insightsData.topic_stats || [])
                .filter(t => t.topic && t.topic !== 'Other')
                .sort((a, b) => (b.total || 0) - (a.total || 0))
                .slice(0, 3);
            const types = (insightsData.category_type_stats || [])
                .filter(t => t.category_type && t.category_type !== 'Other')
                .sort((a, b) => (b.total || 0) - (a.total || 0))
                .slice(0, 3);
            const counties = (insightsData.county_stats || [])
                .filter(c => c.county && c.county !== 'Statewide')
                .sort((a, b) => (b.total || 0) - (a.total || 0))
                .slice(0, 3);

            const card = (title, rows, jumpId, jumpLabel) => `
                <div class="overview-top-card">
                    <div class="overview-top-card-header">
                        <h4>${{escapeHtml(title)}}</h4>
                        <button class="overview-jump-btn" onclick="jumpToInsightsPanel('${{jumpId}}')">${{escapeHtml(jumpLabel)}} &rarr;</button>
                    </div>
                    <ol class="overview-top-list">
                        ${{rows.map((r, i) => `
                            <li>
                                <span class="overview-top-rank">${{i + 1}}</span>
                                <span class="overview-top-name">${{escapeHtml(r.name)}}</span>
                                <span class="overview-top-meta">${{formatInsightNumber(r.count)}} &middot; ${{formatInsightPct(r.passRate)}} pass</span>
                            </li>
                        `).join('')}}
                    </ol>
                </div>
            `;

            target.innerHTML =
                card('Top topics',
                    topics.map(t => ({{name: t.topic, count: t.total, passRate: t.pass_rate}})),
                    'insightsTopicsPanel', 'Open topics') +
                card('Top measure types',
                    types.map(t => ({{name: t.category_type, count: t.total, passRate: t.pass_rate}})),
                    'insightsTypesPanel', 'Open types') +
                card('Busiest counties',
                    counties.map(c => ({{name: c.county, count: c.total, passRate: c.pass_rate}})),
                    'insightsGeographyPanel', 'Open geography');
        }}

        function renderInsightsCoverage() {{
            const target = document.getElementById('insightsCoverage');
            if (!target) return;
            const overview = insightsData.overview || {{}};
            const total = overview.active_measures || 0;
            const decided = overview.decided_measures || 0;
            const withVote = overview.vote_data_measures || 0;
            const withSummary = overview.summary_measures || 0;
            const pct = n => total ? (100 * n / total).toFixed(1) + '%' : '—';

            target.innerHTML = `
                <div class="overview-coverage-row">
                    <div class="overview-coverage-item">
                        <strong>${{formatInsightNumber(decided)}}</strong>
                        <span>decided <small>(${{pct(decided)}})</small></span>
                    </div>
                    <div class="overview-coverage-item">
                        <strong>${{formatInsightNumber(withVote)}}</strong>
                        <span>with vote % <small>(${{pct(withVote)}})</small></span>
                    </div>
                    <div class="overview-coverage-item">
                        <strong>${{formatInsightNumber(withSummary)}}</strong>
                        <span>with AI summary <small>(${{pct(withSummary)}})</small></span>
                    </div>
                    <button class="overview-jump-btn" onclick="jumpToInsightsPanel('insightsMethodologySection')">Methodology &rarr;</button>
                </div>
            `;
        }}

        function renderInsightsFindings() {{
            const target = document.getElementById('insightsFindings');
            if (!target) return;

            const overview = insightsData.overview || {{}};
            const thresholdStats = insightsData.threshold_stats || [];
            const thresholdInsights = insightsData.threshold_insights || {{}};
            const typeTrends = insightsData.type_trends || [];
            const finance = insightsData.finance || {{}};
            const cycles = insightsData.election_cycle_stats || [];
            const regions = insightsData.region_stats || [];
            const geographyInsights = insightsData.geography_insights || {{}};

            const byThreshold = name => thresholdStats.find(t => t.threshold === name) || {{}};
            const t50 = byThreshold('50%');
            const t66 = byThreshold('66.67%');

            const byDecade = year => typeTrends.find(t => t.decade === year) || {{}};
            const fiscal1990s = byDecade(1990).fiscal_share;
            const fiscal2020s = byDecade(2020).fiscal_share;

            const byCycle = name => cycles.find(c => c.cycle === name) || {{}};
            const presYear = byCycle('Presidential year');
            const midterm = byCycle('Midterm year');
            const oddYear = byCycle('Odd year');

            const sortedRegions = [...regions].sort((a, b) => (b.pass_rate || 0) - (a.pass_rate || 0));
            const topRegion = sortedRegions[0] || {{}};
            const bottomRegion = sortedRegions[sortedRegions.length - 1] || {{}};
            const overallPassRate = overview.pass_rate;

            const losses = (finance.better_funded_losses || []).slice(0, 3);
            const lossLabels = losses.map(l => {{
                const num = (l.measure_id || '').replace('PROP_', 'Prop ');
                return `${{num}} (${{l.year}})`;
            }});

            const fmtMoneyB = v => (v == null) ? '—' : '$' + (v / 1e9).toFixed(1) + 'B';

            const renderThresholdTable = () => {{
                const rows = thresholdStats.filter(r => r.threshold);
                return `
                    <table class="kf-mini-table" aria-label="Pass rate by legal threshold">
                        <thead><tr><th scope="col">Threshold</th><th scope="col">Decided</th><th scope="col">Pass rate</th><th scope="col">Majority but failed</th></tr></thead>
                        <tbody>
                            ${{rows.map(r => `
                                <tr>
                                    <th scope="row">${{escapeHtml(r.threshold)}}</th>
                                    <td>${{formatInsightNumber(r.total)}}</td>
                                    <td><strong>${{formatInsightPct(r.pass_rate)}}</strong></td>
                                    <td>${{formatInsightNumber(r.majority_failed)}}</td>
                                </tr>
                            `).join('')}}
                        </tbody>
                    </table>
                `;
            }};

            const renderDecadeStrip = () => {{
                const decades = [1990, 2000, 2010, 2020].map(d => byDecade(d)).filter(r => r.decade);
                const max = Math.max(...decades.map(r => r.fiscal_share || 0), 1);
                return `
                    <div class="kf-decade-strip" aria-label="Fiscal share by decade">
                        ${{decades.map(r => `
                            <div class="kf-decade-cell">
                                <div class="kf-decade-bar" style="height: ${{Math.round(((r.fiscal_share || 0) / max) * 100)}}%"></div>
                                <div class="kf-decade-value">${{formatInsightPct(r.fiscal_share)}}</div>
                                <div class="kf-decade-label">${{r.decade}}s</div>
                            </div>
                        `).join('')}}
                    </div>
                `;
            }};

            const renderRegionBars = () => {{
                const items = [
                    {{name: topRegion.region, rate: topRegion.pass_rate, decided: topRegion.decided, color: '#2D9D78'}},
                    {{name: 'Statewide + local overall', rate: overallPassRate, decided: overview.decided_measures, color: '#9CA3AF'}},
                    {{name: bottomRegion.region, rate: bottomRegion.pass_rate, decided: bottomRegion.decided, color: '#E54D4D'}}
                ];
                return `
                    <div class="kf-region-bars" aria-label="Pass rate: top region vs bottom region vs overall">
                        ${{items.map(it => `
                            <div class="kf-region-row">
                                <span class="kf-region-name">${{escapeHtml(it.name || 'n/a')}}</span>
                                <div class="kf-region-track"><div class="kf-region-fill" style="width: ${{Math.round((it.rate || 0))}}%; background: ${{it.color}}"></div></div>
                                <span class="kf-region-meta"><strong>${{formatInsightPct(it.rate)}}</strong> &middot; ${{formatInsightNumber(it.decided)}} decided</span>
                            </div>
                        `).join('')}}
                    </div>
                `;
            }};

            const renderCycleTable = () => {{
                const rows = [presYear, midterm, oddYear].filter(r => r.cycle);
                return `
                    <table class="kf-mini-table" aria-label="Volume and pass rate by election cycle">
                        <thead><tr><th scope="col">Cycle</th><th scope="col">Avg measures / year</th><th scope="col">Pass rate</th></tr></thead>
                        <tbody>
                            ${{rows.map(r => `
                                <tr>
                                    <th scope="row">${{escapeHtml(r.cycle)}}</th>
                                    <td><strong>${{formatInsightNumber(r.avg_measures_per_year)}}</strong></td>
                                    <td>${{formatInsightPct(r.pass_rate)}}</td>
                                </tr>
                            `).join('')}}
                        </tbody>
                    </table>
                `;
            }};

            const renderJump = (panelId, label) =>
                `<button class="overview-jump-btn kf-jump" onclick="jumpToInsightsPanel('${{panelId}}')">Dig in: ${{escapeHtml(label)}} &rarr;</button>`;

            target.innerHTML = `
                <p class="kf-disclaimer">
                    <strong>Note:</strong> This section was drafted by AI; usual caveats apply. I plan to rewrite it myself &mdash; ideally net of the existing published research on direct democracy in California &mdash; once time allows.
                </p>
                <p class="kf-lede">
                    The dataset does not show one California ballot. It shows several: a statewide proposition arena where money can be enormous,
                    a much larger local ballot where taxes and bonds dominate, and a rulebook where a majority is sometimes not enough.
                    The findings below are descriptive, not predictive &mdash; but they point to where voter power, fiscal need, geography,
                    and legal thresholds most visibly collide.
                </p>

                <article class="kf-finding">
                    <h3><span class="kf-num">1</span>California voters say yes by default &mdash; but the rules decide which yes votes count.</h3>
                    <p>
                        Across decided measures, ${{formatInsightPct(overallPassRate)}} pass. That headline hides a fault line.
                        On simple-majority contests, the pass rate climbs to ${{formatInsightPct(t50.pass_rate)}}. On two-thirds contests,
                        it falls to ${{formatInsightPct(t66.pass_rate)}}, and ${{formatInsightNumber(t66.majority_failed)}} measures
                        crossed 50% yes only to fail under the higher threshold. Across the full dataset,
                        ${{formatInsightNumber(thresholdInsights.majority_failure_count)}} decided measures since
                        ${{overview.year_min || '1911'}} got a majority but did not pass &mdash; almost all of them in the supermajority bucket.
                    </p>
                    ${{renderThresholdTable()}}
                    ${{renderJump('insightsRulesPanel', 'Rules')}}
                </article>

                <article class="kf-finding">
                    <h3><span class="kf-num">2</span>The modern ballot is increasingly a local fiscal instrument.</h3>
                    <p>
                        ${{formatInsightPct(overview.local_share)}} of active records are local measures, and a majority of those fall into
                        fiscal categories &mdash; bonds, sales taxes, charter amendments tied to revenue. That share has been rising.
                        In the 1990s, ${{formatInsightPct(fiscal1990s)}} of measures were fiscal. In the 2020s so far, the figure is
                        ${{formatInsightPct(fiscal2020s)}}. The state ballot most voters remember from television is a small slice of
                        what they actually face on election day.
                    </p>
                    ${{renderDecadeStrip()}}
                    ${{renderJump('insightsTypesPanel', 'Measure Types')}}
                </article>

                <article class="kf-finding">
                    <h3><span class="kf-num">3</span>Campaign money matters &mdash; but it is not destiny.</h3>
                    <p>
                        The finance database links ${{formatInsightNumber(finance.measure_count)}} statewide propositions to
                        ${{fmtMoneyB(finance.total_receipts)}} in committee receipts. The better-funded side won
                        ${{formatInsightNumber(finance.better_funded_won)}} of those races, or ${{formatInsightPct(finance.better_funded_win_rate)}}
                        &mdash; meaningful, but a long way from determinative. Recent better-funded campaigns that lost include some of
                        the largest contests in the dataset:
                        ${{lossLabels.length ? escapeHtml(lossLabels.join(', ')) : 'none on record'}}.
                    </p>
                    ${{renderJump('insightsFinanceSection', 'Finance')}}
                </article>

                <article class="kf-finding">
                    <h3><span class="kf-num">4</span>The Bay Area is not just busier &mdash; measures there pass more often.</h3>
                    <p>
                        ${{escapeHtml(topRegion.region || 'The top region')}} measures pass at ${{formatInsightPct(topRegion.pass_rate)}},
                        well above the ${{formatInsightPct(overallPassRate)}} statewide-and-local average.
                        ${{escapeHtml(bottomRegion.region || 'The bottom region')}} sits at the other end at
                        ${{formatInsightPct(bottomRegion.pass_rate)}} &mdash; a ${{formatInsightNumber(geographyInsights.region_pass_rate_gap)}}-point spread.
                        The county-level gap is wider still, and not explained by population alone.
                    </p>
                    ${{renderRegionBars()}}
                    ${{renderJump('insightsGeographyPanel', 'Geography')}}
                </article>

                <article class="kf-finding">
                    <h3><span class="kf-num">5</span>Election timing changes the load far more than it changes the outcome.</h3>
                    <p>
                        Presidential years average ${{formatInsightNumber(presYear.avg_measures_per_year)}} measures per year, more than double
                        the ${{formatInsightNumber(oddYear.avg_measures_per_year)}} of odd-year cycles. Pass rates barely move:
                        ${{formatInsightPct(presYear.pass_rate)}} in presidential years, ${{formatInsightPct(midterm.pass_rate)}} in midterms,
                        and ${{formatInsightPct(oddYear.pass_rate)}} in odd years. Volume is a turnout-sensitive thing; outcomes are not,
                        at least not on the headline metric.
                    </p>
                    ${{renderCycleTable()}}
                    ${{renderJump('insightsTrendPanel', 'Trend')}}
                </article>

                <p class="kf-kicker">
                    The strongest pattern is not that voters are anti-tax, anti-government, or reflexively pro-measure.
                    It is that ballot outcomes depend heavily on the institutional setting &mdash; local versus statewide, simple majority
                    versus supermajority, presidential year versus off-year, and whether a campaign is fighting in the expensive statewide
                    proposition market. The dedicated tabs above unpack each of these.
                </p>
            `;
        }}

        function createInsightChart(canvasId, config) {{
            if (!window.Chart) return;
            const canvas = document.getElementById(canvasId);
            if (!canvas) return;
            if (insightsCharts[canvasId]) insightsCharts[canvasId].destroy();
            insightsCharts[canvasId] = new Chart(canvas, config);
        }}

        function renderInsightsCharts() {{
            const timeSeries = insightsData.time_series || [];
            const yearRows = timeSeries.filter(row => row.year && row.total > 0);
            createInsightChart('insightsYearChart', {{
                type: 'bar',
                data: {{
                    labels: yearRows.map(row => row.year),
                    datasets: [
                        {{
                            type: 'bar',
                            label: 'Measures',
                            data: yearRows.map(row => row.total),
                            backgroundColor: '#7A1F2A',
                            borderRadius: 3,
                            yAxisID: 'y'
                        }},
                        {{
                            type: 'line',
                            label: 'Pass rate',
                            data: yearRows.map(row => row.pass_rate),
                            borderColor: '#2D9D78',
                            backgroundColor: '#2D9D78',
                            pointRadius: 1.5,
                            tension: 0.2,
                            yAxisID: 'y1'
                        }}
                    ]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: {{ mode: 'index', intersect: false }},
                    plugins: {{ legend: {{ position: 'bottom' }} }},
                    scales: {{
                        x: {{ ticks: {{ maxTicksLimit: 12 }} }},
                        y: {{ beginAtZero: true, title: {{ display: true, text: 'Measures' }} }},
                        y1: {{ beginAtZero: true, max: 100, position: 'right', grid: {{ drawOnChartArea: false }}, title: {{ display: true, text: 'Pass rate' }} }}
                    }}
                }}
            }});

            const tsAll = insightsData.time_series || [];
            // Trim to 1990+: local CEDA coverage starts then; the headline chart up top covers the full arc.
            const ts = tsAll.filter(r => r.year && r.year >= 1990 && r.year <= (insightsData.overview && insightsData.overview.year_max || 2026));
            const tsYears = ts.map(r => r.year);
            const localValues = ts.map(r => r.local || 0);
            const statewideValues = ts.map(r => r.statewide || 0);

            const rollingAvg = (values, window) => {{
                const half = Math.floor(window / 2);
                return values.map((_, i) => {{
                    const start = Math.max(0, i - half);
                    const end = Math.min(values.length, i + half + 1);
                    const slice = values.slice(start, end);
                    if (slice.length === 0) return null;
                    return slice.reduce((a, b) => a + b, 0) / slice.length;
                }});
            }};

            const localRolling = rollingAvg(localValues, 5);
            const statewideRolling = rollingAvg(statewideValues, 5);
            const localMasked = localRolling;

            createInsightChart('insightsLocalTrendChart', {{
                type: 'line',
                data: {{
                    labels: tsYears,
                    datasets: [{{
                        label: 'Local measures (5-yr avg)',
                        data: localMasked,
                        borderColor: '#254E70',
                        backgroundColor: 'rgba(37, 78, 112, 0.12)',
                        tension: 0.25,
                        fill: true,
                        pointRadius: 0,
                        spanGaps: false
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        legend: {{ display: false }},
                        tooltip: {{
                            callbacks: {{
                                title: items => items[0].label,
                                label: item => item.parsed.y == null ? 'No data' : item.parsed.y.toFixed(0) + ' / yr'
                            }}
                        }}
                    }},
                    scales: {{
                        x: {{ ticks: {{ maxTicksLimit: 8, font: {{ size: 10 }} }}, grid: {{ display: false }} }},
                        y: {{ beginAtZero: true, title: {{ display: true, text: 'Measures / year' }} }}
                    }}
                }}
            }});

            createInsightChart('insightsStatewideTrendChart', {{
                type: 'line',
                data: {{
                    labels: tsYears,
                    datasets: [{{
                        label: 'Statewide measures (5-yr avg)',
                        data: statewideRolling,
                        borderColor: '#7A1F2A',
                        backgroundColor: 'rgba(122, 31, 42, 0.12)',
                        tension: 0.25,
                        fill: true,
                        pointRadius: 0
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        legend: {{ display: false }},
                        tooltip: {{
                            callbacks: {{
                                title: items => items[0].label,
                                label: item => item.parsed.y == null ? 'No data' : item.parsed.y.toFixed(1) + ' / yr'
                            }}
                        }}
                    }},
                    scales: {{
                        x: {{ ticks: {{ maxTicksLimit: 8, font: {{ size: 10 }} }}, grid: {{ display: false }} }},
                        y: {{ beginAtZero: true, title: {{ display: true, text: 'Measures / year' }} }}
                    }}
                }}
            }});

            const cycles = insightsData.election_cycle_stats || [];
            createInsightChart('insightsElectionCycleChart', {{
                type: 'bar',
                data: {{
                    labels: cycles.map(row => row.cycle),
                    datasets: [{{
                        label: 'Avg. measures per year',
                        data: cycles.map(row => row.avg_measures_per_year || 0),
                        backgroundColor: '#7A1F2A',
                        borderRadius: 4
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{ legend: {{ display: false }} }},
                    scales: {{
                        y: {{ beginAtZero: true, title: {{ display: true, text: 'Measures/year' }} }}
                    }}
                }}
            }});

            createInsightChart('insightsElectionCyclePassRateChart', {{
                type: 'bar',
                data: {{
                    labels: cycles.map(row => row.cycle),
                    datasets: [{{
                        label: 'Pass rate (%)',
                        data: cycles.map(row => row.pass_rate),
                        backgroundColor: '#2D9D78',
                        borderRadius: 4
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{ legend: {{ display: false }} }},
                    scales: {{
                        y: {{ beginAtZero: true, max: 100, title: {{ display: true, text: 'Pass rate (%)' }} }}
                    }}
                }}
            }});

            const topicTrends = insightsData.topic_trends || {{}};
            const topicTrendRows = topicTrends.decade_shares || [];
            const topicPalette = ['#7A1F2A', '#254E70', '#2D9D78', '#D4A62A', '#8B5CF6', '#E4572E'];

            // Renormalize each decade's shares against classified-only denominator
            // (excluding 'Other' / unclassified). Keeps lines meaningful when CEDA
            // local volume floods the dataset starting in the 1990s.
            const decadeTopicCounts = {{}};
            (insightsData.topic_decade_matrix || []).forEach(row => {{
                decadeTopicCounts[String(row.decade)] = row.topics || {{}};
            }});
            const renormalizedRows = topicTrendRows.map(row => {{
                const counts = decadeTopicCounts[String(row.decade)] || {{}};
                let classifiedSum = 0;
                Object.entries(counts).forEach(([t, n]) => {{
                    if (t !== 'Other') classifiedSum += (n || 0);
                }});
                const newShares = {{}};
                if (classifiedSum > 0) {{
                    Object.entries(counts).forEach(([t, n]) => {{
                        if (t !== 'Other') newShares[t] = (n / classifiedSum) * 100;
                    }});
                }}
                return {{ decade: row.decade, shares: newShares }};
            }});

            createInsightChart('insightsTopicTrendChart', {{
                type: 'line',
                data: {{
                    labels: renormalizedRows.map(row => row.decade + 's'),
                    datasets: (topicTrends.tracked_topics || []).map((topic, i) => ({{
                        label: topic,
                        data: renormalizedRows.map(row => (row.shares || {{}})[topic]),
                        borderColor: topicPalette[i % topicPalette.length],
                        backgroundColor: topicPalette[i % topicPalette.length],
                        pointRadius: 2,
                        tension: 0.25
                    }}))
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{ legend: {{ position: 'bottom' }} }},
                    scales: {{ y: {{ beginAtZero: true, title: {{ display: true, text: 'Share of classified topics (%)' }} }} }}
                }}
            }});

            const types = (insightsData.category_type_stats || []).slice(0, 8);
            createInsightChart('insightsTypeChart', {{
                type: 'bar',
                data: {{
                    labels: types.map(row => row.category_type || row.type),
                    datasets: [{{
                        label: 'Measures',
                        data: types.map(row => row.total),
                        backgroundColor: '#254E70',
                        borderRadius: 4
                    }}]
                }},
                options: {{
                    indexAxis: 'y',
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{ legend: {{ display: false }} }},
                    scales: {{ x: {{ beginAtZero: true }} }}
                }}
            }});

            // Trim to 1990+: pre-1990 dataset is statewide-only, and the Bond / Sales Tax / Property Tax
            // category-type vocabulary is essentially a local-ballot construct (CEDA). Showing decades of
            // zero-line ahead of that misrepresents categorization absence as instrument absence.
            const typeTrendRows = (insightsData.type_trends || []).filter(row => (row.decade || 0) >= 1990);
            createInsightChart('insightsFiscalTrendChart', {{
                type: 'line',
                data: {{
                    labels: typeTrendRows.map(row => row.decade + 's'),
                    datasets: [
                        {{
                            label: 'Fiscal share',
                            data: typeTrendRows.map(row => row.fiscal_share),
                            borderColor: '#7A1F2A',
                            backgroundColor: '#7A1F2A',
                            tension: 0.25
                        }},
                        {{
                            label: 'Bond share',
                            data: typeTrendRows.map(row => row.bond_share),
                            borderColor: '#254E70',
                            backgroundColor: '#254E70',
                            tension: 0.25
                        }},
                        {{
                            label: 'Tax share',
                            data: typeTrendRows.map(row => row.tax_share),
                            borderColor: '#2D9D78',
                            backgroundColor: '#2D9D78',
                            tension: 0.25
                        }}
                    ]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{ legend: {{ position: 'bottom' }} }},
                    scales: {{ y: {{ beginAtZero: true, title: {{ display: true, text: 'Share of records (%)' }} }} }}
                }}
            }});

            const thresholds = insightsData.threshold_stats || [];
            // Horizontal 100%-stacked: each row sums to 100% so the threshold *effect* is
            // legible (52% of the volume is at 50% threshold but tells you nothing about
            // the threshold itself; the proportional view shows what the rule does).
            const segShare = (n, total) => total ? (100 * n / total) : 0;
            createInsightChart('insightsThresholdChart', {{
                type: 'bar',
                data: {{
                    labels: thresholds.map(row => row.threshold + ' threshold'),
                    datasets: [
                        {{
                            label: 'Passed',
                            data: thresholds.map(row => segShare(row.passed, row.total)),
                            backgroundColor: '#2D9D78',
                            borderWidth: 0
                        }},
                        {{
                            label: 'Failed below majority',
                            data: thresholds.map(row => segShare((row.total || 0) - (row.passed || 0) - (row.majority_failed || 0), row.total)),
                            backgroundColor: '#9CA3AF',
                            borderWidth: 0
                        }},
                        {{
                            label: 'Majority but failed',
                            data: thresholds.map(row => segShare(row.majority_failed, row.total)),
                            backgroundColor: '#E54D4D',
                            borderWidth: 0
                        }}
                    ]
                }},
                options: {{
                    indexAxis: 'y',
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        legend: {{ position: 'bottom' }},
                        tooltip: {{
                            callbacks: {{
                                label: (ctx) => {{
                                    const row = thresholds[ctx.dataIndex] || {{}};
                                    const total = row.total || 0;
                                    const counts = [
                                        row.passed || 0,
                                        Math.max((row.total || 0) - (row.passed || 0) - (row.majority_failed || 0), 0),
                                        row.majority_failed || 0
                                    ];
                                    const raw = counts[ctx.datasetIndex] || 0;
                                    return `${{ctx.dataset.label}}: ${{ctx.parsed.x.toFixed(1)}}% (${{raw.toLocaleString()}} of ${{total.toLocaleString()}})`;
                                }}
                            }}
                        }}
                    }},
                    scales: {{
                        x: {{
                            stacked: true,
                            min: 0,
                            max: 100,
                            ticks: {{ callback: v => v + '%' }}
                        }},
                        y: {{ stacked: true }}
                    }}
                }}
            }});

            // Spending-arc chart with toggle between election-cycle and
            // calendar-year aggregations. The bound `onclick` (assignment,
            // not addEventListener) is idempotent — renderInsightsCharts()
            // can run multiple times on view switches without piling up
            // duplicate handlers.
            renderFinanceArcChart('election');
            const arcToggleButtons = document.querySelectorAll('.finance-arc-mode');
            arcToggleButtons.forEach(btn => {{
                btn.onclick = () => {{
                    const mode = btn.dataset.mode;
                    arcToggleButtons.forEach(b => {{
                        const isActive = b === btn;
                        b.classList.toggle('is-active', isActive);
                        b.setAttribute('aria-selected', isActive ? 'true' : 'false');
                    }});
                    renderFinanceArcChart(mode);
                }};
            }});
        }}

        // Configs (subdeck text + tooltip label per mode) live with the
        // renderer so adding a third mode later only touches one spot.
        const FINANCE_ARC_MODES = {{
            election: {{
                rowsKey: 'annual_receipts',
                subdeck: 'Total receipts grouped by each measure&rsquo;s actual election year. Bars include both support and oppose receipts.',
                tooltipLabel: row => row.n_measures + ' active campaign' + (row.n_measures === 1 ? '' : 's'),
            }},
            calendar: {{
                rowsKey: 'calendar_year_receipts',
                subdeck: 'Accepted weekly receipts grouped by calendar year (week of transaction). Measures with multi-year spending appear in multiple bars; boundary-week receipts are attributed to the week-start year.',
                tooltipLabel: row => row.n_measures + ' measure' + (row.n_measures === 1 ? '' : 's') + ' with accepted receipts in this year',
            }},
        }};

        function renderFinanceArcChart(mode) {{
            const finance = insightsData.finance || {{}};
            const config = FINANCE_ARC_MODES[mode] || FINANCE_ARC_MODES.election;
            const rows = finance[config.rowsKey] || [];

            // Update the sub-deck copy on every toggle (in addition to the
            // chart). Codex round-5 caution: keep both updating together.
            const subdeck = document.getElementById('financeArcSubdeck');
            if (subdeck) subdeck.innerHTML = config.subdeck;

            createInsightChart('financeAnnualChart', {{
                type: 'bar',
                data: {{
                    labels: rows.map(row => row.year),
                    datasets: [
                        {{
                            label: 'Total receipts',
                            data: rows.map(row => row.total_receipts || 0),
                            backgroundColor: '#7A1F2A',
                            borderRadius: 3,
                        }}
                    ]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        legend: {{ display: false }},
                        tooltip: {{
                            callbacks: {{
                                label: ctx => formatDollars(ctx.parsed.y || 0),
                                afterLabel: ctx => {{
                                    const row = rows[ctx.dataIndex];
                                    return row ? config.tooltipLabel(row) : '';
                                }}
                            }}
                        }}
                    }},
                    scales: {{
                        x: {{ ticks: {{ maxTicksLimit: 14 }} }},
                        y: {{ beginAtZero: true, ticks: {{ callback: value => formatDollars(value) }} }}
                    }}
                }}
            }});
        }}

        function renderTrendSummary() {{
            const target = document.getElementById('trendInsightSummary');
            if (!target) return;
            const trend = insightsData.trend_insights || {{}};
            const busiestDecade = trend.busiest_decade || {{}};
            const busiestYears = trend.busiest_years || [];
            const busiestYear = busiestYears[0] || {{}};
            const secondBusiest = busiestYears[1] || {{}};

            const decades = insightsData.decade_series || [];
            const byDecade = year => decades.find(d => d.decade === year) || {{}};
            const dec1990 = byDecade(1990);
            const dec2010 = byDecade(2010);
            const passShift = (dec1990.pass_rate != null && dec2010.pass_rate != null)
                ? (dec2010.pass_rate - dec1990.pass_rate)
                : null;
            const passShiftLabel = passShift == null
                ? 'n/a'
                : (passShift > 0 ? '+' : '') + passShift.toFixed(1) + ' pts';

            target.innerHTML = `
                <div class="mini-callout"><strong>${{busiestDecade.decade ? busiestDecade.decade + 's' : 'n/a'}}</strong><span>busiest complete decade, with ${{formatInsightNumber(busiestDecade.total || 0)}} records</span></div>
                <div class="mini-callout"><strong>${{busiestYear.year || 'n/a'}}</strong><span>busiest single year, with ${{formatInsightNumber(busiestYear.total || 0)}} records</span></div>
                <div class="mini-callout"><strong>${{formatInsightNumber(secondBusiest.total || 0)}}</strong><span>measures in ${{secondBusiest.year || 'n/a'}} &mdash; second-busiest year, behind only ${{busiestYear.year || ''}} (${{formatInsightNumber(busiestYear.total || 0)}})</span></div>
                <div class="mini-callout"><strong>${{passShiftLabel}}</strong><span>pass-rate shift from the 1990s (${{formatInsightPct(dec1990.pass_rate)}}) to the 2010s (${{formatInsightPct(dec2010.pass_rate)}})</span></div>
            `;
        }}

        function renderTopicTrendSummary() {{
            // Era anchor strip + pass-rate rankings (replaces the old slope list).
            // Both modules read from the precomputed `topic_insights` payload, which
            // uses the classified-only denominator that the on-page chart also uses.
            const insights = insightsData.topic_insights || {{}};

            const eraTarget = document.getElementById('topicEraStrip');
            if (eraTarget) {{
                const anchors = insights.era_anchors || [];
                eraTarget.innerHTML = anchors.map(era => {{
                    const top = era.top || [];
                    const rows = top.length
                        ? top.map(t => `
                            <div class="topic-era-card-row">
                                <span>${{escapeHtml(t.topic)}}</span>
                                <strong>${{formatInsightPct(t.share)}}</strong>
                            </div>
                        `).join('')
                        : `<div class="topic-era-card-row"><span style="color:var(--text-tertiary)">No classified records</span></div>`;
                    return `
                        <div class="topic-era-card">
                            <div class="topic-era-card-decade">${{era.decade}}s</div>
                            <div class="topic-era-card-meta">n = ${{formatInsightNumber(era.classified_n)}} classified</div>
                            ${{rows}}
                        </div>
                    `;
                }}).join('');
            }}

            const rankTarget = document.getElementById('topicPassRateRankings');
            if (rankTarget) {{
                const rankings = insights.pass_rate_rankings || {{}};
                const renderBlock = (heading, items) => `
                    <div class="topic-rank-block">
                        <div class="topic-rank-heading">${{escapeHtml(heading)}}</div>
                        ${{(items || []).map(it => `
                            <div class="topic-rank-row">
                                <span class="topic-rank-row-name">${{escapeHtml(it.topic)}}</span>
                                <span class="topic-rank-row-pct">${{formatInsightPct(it.pass_rate)}}<small>n = ${{formatInsightNumber(it.decided)}}</small></span>
                            </div>
                        `).join('')}}
                    </div>
                `;
                rankTarget.innerHTML =
                    renderBlock('Clears voters more often', rankings.high) +
                    renderBlock('Struggles more often', rankings.low);
            }}
        }}

        function renderTypeInsights() {{
            // Four narrative modules below the chart row (Codex-recommended):
            //   1. Modern-year ballot anatomy (1990+, per-year averages by instrument)
            //   2. Fiscal instrument profiles (table with typical-use copy)
            //   3. Type x threshold profiles (Bond / Property Tax / Sales Tax)
            //   4. Recall callout
            // All four read from the precomputed `type_insights` payload.
            const ti = insightsData.type_insights || {{}};

            // 1. Modern year anatomy
            const anatomy = ti.modern_year_anatomy || {{}};
            const instruments = anatomy.instruments || [];
            const anatomyTarget = document.getElementById('typeModernAnatomy');
            if (anatomyTarget) {{
                const totalPerYear = instruments.reduce((s, it) => s + (it.per_year_avg || 0), 0);
                const cells = instruments.map(it => `
                    <div class="type-anatomy-cell">
                        <div class="type-anatomy-num">${{formatInsightNumber(Math.round(it.per_year_avg || 0))}}</div>
                        <div class="type-anatomy-name">${{escapeHtml(it.category_type)}}</div>
                    </div>
                `).join('');
                anatomyTarget.innerHTML = `
                    <h4 class="type-section-h">A typical California ballot year is mostly local fiscal machinery</h4>
                    <p class="type-section-deck">Since ${{anatomy.modern_start || 1990}}, voters have faced an average of about <strong>${{Math.round(totalPerYear)}} measures per year</strong> across the instruments below. Most of what shows up on a ballot is borrowing or taxing.</p>
                    <div class="type-anatomy-strip">${{cells}}</div>
                    <p class="type-section-footnote">Records since ${{anatomy.modern_start || 1990}} (${{anatomy.years_covered || ''}} years), where local category types are consistently populated.</p>
                `;
            }}

            // 2. Fiscal instrument profiles
            const profiles = ti.fiscal_instrument_profiles || [];
            const fiscalTarget = document.getElementById('typeFiscalProfiles');
            if (fiscalTarget) {{
                fiscalTarget.innerHTML = `
                    <h4 class="type-section-h">The fiscal ballot is not one thing</h4>
                    <p class="type-section-deck">A single &ldquo;fiscal pass rate&rdquo; flattens real differences across instruments. Business taxes clear voters at very different rates than property taxes; bonds are common but only moderately successful.</p>
                    <table class="kf-mini-table type-profile-table" aria-label="Fiscal instrument profiles">
                        <thead><tr><th scope="col">Instrument</th><th scope="col">Decided</th><th scope="col">Pass rate</th><th scope="col">What it usually means</th></tr></thead>
                        <tbody>
                            ${{profiles.map(p => `
                                <tr>
                                    <th scope="row">${{escapeHtml(p.category_type)}}</th>
                                    <td>${{formatInsightNumber(p.decided)}}</td>
                                    <td><strong>${{formatInsightPct(p.pass_rate)}}</strong></td>
                                    <td>${{escapeHtml(p.typical_use)}}</td>
                                </tr>
                            `).join('')}}
                        </tbody>
                    </table>
                `;
            }}

            // 3. Type x threshold
            const tps = ti.type_threshold_profiles || [];
            const thresholdTarget = document.getElementById('typeThresholdProfiles');
            if (thresholdTarget) {{
                const formatMix = (mix) => {{
                    const order = ['50%', '55%', '66.67%'];
                    return order
                        .filter(t => mix[t] != null)
                        .map(t => `${{t}} (${{Math.round(mix[t])}}%)`)
                        .join(' / ');
                }};
                thresholdTarget.innerHTML = `
                    <h4 class="type-section-h">Some low pass rates are rule stories, not voter mood</h4>
                    <p class="type-section-deck">Property tax measures pass less often largely because most need a two-thirds supermajority. Sales tax mixes simple-majority and supermajority contests; school bonds mostly need 55%.</p>
                    <table class="kf-mini-table type-profile-table" aria-label="Threshold mix by fiscal instrument">
                        <thead><tr><th scope="col">Instrument</th><th scope="col">Decided</th><th scope="col">Pass rate</th><th scope="col">Threshold mix</th><th scope="col">Majority but failed</th></tr></thead>
                        <tbody>
                            ${{tps.map(p => `
                                <tr>
                                    <th scope="row">${{escapeHtml(p.category_type)}}</th>
                                    <td>${{formatInsightNumber(p.decided)}}</td>
                                    <td><strong>${{formatInsightPct(p.pass_rate)}}</strong></td>
                                    <td>${{escapeHtml(formatMix(p.threshold_mix || {{}}))}}</td>
                                    <td>${{formatInsightNumber(p.majority_failed)}}</td>
                                </tr>
                            `).join('')}}
                        </tbody>
                    </table>
                    <p class="type-section-footnote">Thresholds derived from available threshold and type fields. The Rules panel has the deep dive.</p>
                `;
            }}

            // 4. Recall callout
            const rp = ti.recall_profile || {{}};
            const recallTarget = document.getElementById('typeRecallCallout');
            if (recallTarget && rp.total) {{
                recallTarget.innerHTML = `
                    <h4 class="type-section-h">Recalls are rare &mdash; but once they reach the ballot they usually pass</h4>
                    <p class="type-section-deck"><strong>${{formatInsightNumber(rp.total)}}</strong> recall measures across <strong>${{formatInsightNumber(rp.county_count)}}</strong> California counties. Of those that reached a vote, <strong>${{formatInsightPct(rp.pass_rate)}}</strong> passed &mdash; a striking ballot-stage success rate for what voters perceive as exceptional.</p>
                    <p class="type-section-footnote">Recall measures that reached the ballot, not all attempted recalls.</p>
                `;
            }}
        }}

        // Geography panel state (count vs pass rate). Counties-only for now;
        // a Regions toggle was removed because the underlying spatial pattern
        // closely mirrors the county view. Tracked for future revisit.
        const geographyState = {{ colorMode: 'count' }};
        // Cache the loaded county features so the color toggle doesn't re-fetch the topojson.
        let cachedCountyFeatures = null;
        // Persistent Leaflet map + layer references so toggling color mode just re-styles the
        // existing layer instead of re-creating the whole map.
        let leafletCountyMap = null;
        let leafletCountyLayer = null;
        let leafletLegendControl = null;

        function setGeographyColor(mode) {{
            if (mode === geographyState.colorMode) return;
            geographyState.colorMode = mode;
            document.querySelectorAll('[data-geo-color]').forEach(b => {{
                b.classList.toggle('active', b.dataset.geoColor === mode);
            }});
            // Just restyle the existing Leaflet layer; no full re-render needed.
            applyCountyMapStyle();
        }}

        function buildCountyColorScale() {{
            const isPassRate = geographyState.colorMode === 'passRate';
            const stats = (insightsData.county_stats || []);
            if (isPassRate) {{
                const allValues = stats.map(r => r.pass_rate).filter(v => v != null);
                const lo = Math.min(...allValues, 50);
                const hi = Math.max(...allValues, 80);
                return {{
                    isPassRate: true,
                    fn: d3.scaleSequential([lo, hi], d3.interpolateRdYlGn),
                    domain: [lo, hi]
                }};
            }}
            const allValues = stats.map(r => r.total).filter(v => v != null);
            const maxTotal = Math.max(...allValues, 1);
            return {{
                isPassRate: false,
                fn: d3.scaleSequentialSqrt([0, maxTotal], d3.interpolateBlues),
                domain: [0, maxTotal]
            }};
        }}

        function applyCountyMapStyle() {{
            if (!leafletCountyLayer) return;
            const scale = buildCountyColorScale();
            const countyByFips = new Map((insightsData.county_stats || []).map(row => [String(row.fips), row]));
            leafletCountyLayer.setStyle((feature) => {{
                const row = countyByFips.get(String(feature.id).padStart(5, '0'));
                const v = row ? (scale.isPassRate ? row.pass_rate : row.total) : null;
                return {{
                    fillColor: v == null ? '#EEE9E2' : scale.fn(v),
                    weight: 0.7,
                    color: '#FFFFFF',
                    fillOpacity: 1
                }};
            }});
            updateCountyMapLegend(scale);
        }}

        function updateCountyMapLegend(scale) {{
            if (!leafletCountyMap) return;
            if (leafletLegendControl) {{
                leafletCountyMap.removeControl(leafletLegendControl);
                leafletLegendControl = null;
            }}
            leafletLegendControl = L.control({{ position: 'bottomright' }});
            leafletLegendControl.onAdd = () => {{
                const div = L.DomUtil.create('div', 'geo-legend');
                const stops = 5;
                const swatches = [];
                for (let i = 0; i < stops; i++) {{
                    const t = i / (stops - 1);
                    const v = scale.domain[0] + t * (scale.domain[1] - scale.domain[0]);
                    swatches.push(`<span style="background:${{scale.fn(v)}}"></span>`);
                }}
                const fmtLo = scale.isPassRate ? scale.domain[0].toFixed(0) + '%' : '0';
                const fmtHi = scale.isPassRate ? scale.domain[1].toFixed(0) + '%' : formatInsightNumber(scale.domain[1]);
                div.innerHTML = `
                    <span class="geo-legend-title">${{scale.isPassRate ? 'Pass rate' : 'Measures'}}</span>
                    <div class="geo-legend-bar">${{swatches.join('')}}</div>
                    <div class="geo-legend-scale"><span>${{fmtLo}}</span><span>${{fmtHi}}</span></div>
                `;
                return div;
            }};
            leafletLegendControl.addTo(leafletCountyMap);
        }}

        function renderCountyLeaderboard() {{
            const target = document.getElementById('countyLeaderboard');
            if (!target) return;
            const rows = (insightsData.county_stats || []).slice(0, 12);
            const maxTotal = Math.max(...rows.map(row => row.total || 0), 1);
            target.innerHTML = rows.map(row => `
                <div class="leader-row">
                    <div class="leader-row-top">
                        <strong>${{escapeHtml(row.county)}}</strong>
                        <span>${{formatInsightNumber(row.total)}} measures</span>
                    </div>
                    <div class="leader-bar"><span style="width:${{Math.round((row.total || 0) / maxTotal * 100)}}%"></span></div>
                    <small>${{formatInsightPct(row.pass_rate)}} passed</small>
                </div>
            `).join('');
        }}

        function renderGeographyInsights() {{
            // Four anchor cards above the map (visible in both Counties and Regions views):
            //   1. Top-5 county concentration
            //   2. Top region (with volume + pass rate)
            //   3. Bottom region (with volume + pass rate)
            //   4. County pass-rate spread
            const target = document.getElementById('regionInsightSummary');
            if (!target) return;
            const geo = insightsData.geography_insights || {{}};

            // Card 1: top-5 county share of all local measures (computed from county_stats so
            // we don't accidentally include Statewide rows).
            const allCounties = [...(insightsData.county_stats || [])]
                .filter(c => c.county && c.county !== 'Statewide')
                .sort((a, b) => (b.total || 0) - (a.total || 0));
            const top5 = allCounties.slice(0, 5);
            const top5Sum = top5.reduce((s, c) => s + (c.total || 0), 0);
            const allLocalSum = allCounties.reduce((s, c) => s + (c.total || 0), 0);
            const top5Pct = allLocalSum ? (100 * top5Sum / allLocalSum) : null;
            const top5Names = top5.map(c => c.county).join(', ');

            const highRegion = (geo.highest_pass_rate_regions || [])[0];
            const lowRegion = (geo.lowest_pass_rate_regions || [])[0];

            const fmtRegion = r => r
                ? `${{formatInsightPct(r.pass_rate)}} pass &middot; ${{formatInsightNumber(r.total)}} measures`
                : '';

            target.innerHTML = `
                <div class="mini-callout">
                    <strong>${{top5Pct == null ? '—' : Math.round(top5Pct) + '%'}}</strong>
                    <span>of measures from 5 counties &mdash; ${{escapeHtml(top5Names)}}</span>
                </div>
                <div class="mini-callout">
                    <strong>${{highRegion ? escapeHtml(highRegion.region) : 'n/a'}}</strong>
                    <span>highest regional pass rate &mdash; ${{escapeHtml(fmtRegion(highRegion))}}</span>
                </div>
                <div class="mini-callout">
                    <strong>${{lowRegion ? escapeHtml(lowRegion.region) : 'n/a'}}</strong>
                    <span>lowest regional pass rate &mdash; ${{escapeHtml(fmtRegion(lowRegion))}}</span>
                </div>
                <div class="mini-callout">
                    <strong>${{formatInsightPct(geo.county_pass_rate_gap)}}</strong>
                    <span>spread between fastest- and slowest-passing counties (n &ge; 50 decided)</span>
                </div>
            `;
        }}

        function renderCountyMap() {{
            // Leaflet-based choropleth. The user controls pan/zoom themselves so we don't
            // have to nail an exact pixel size. We still load the topojson via d3 + topojson-client
            // because that's how us-atlas counties-10m is shipped; Leaflet consumes the resulting
            // GeoJSON via L.geoJSON().
            const target = document.getElementById('californiaCountyMap');
            if (!target || !window.L || !window.d3 || !window.topojson) return;

            const countyByFips = new Map((insightsData.county_stats || []).map(row => [String(row.fips), row]));

            const drawMap = (counties) => {{
                // Initialize the map only once. Subsequent calls (e.g., from the color toggle)
                // just re-style the layer.
                if (!leafletCountyMap) {{
                    target.innerHTML = '';
                    leafletCountyMap = L.map(target, {{
                        zoomControl: true,
                        attributionControl: false,
                        scrollWheelZoom: false,
                        worldCopyJump: false,
                        minZoom: 5,
                        maxZoom: 9
                    }});
                }} else if (leafletCountyLayer) {{
                    leafletCountyLayer.remove();
                    leafletCountyLayer = null;
                }}

                const collection = {{ type: 'FeatureCollection', features: counties }};
                leafletCountyLayer = L.geoJSON(collection, {{
                    style: () => ({{ fillColor: '#EEE9E2', weight: 0.7, color: '#FFFFFF', fillOpacity: 1 }}),
                    onEachFeature: (feature, layer) => {{
                        const row = countyByFips.get(String(feature.id).padStart(5, '0'));
                        if (!row) return;
                        const html = `<strong>${{escapeHtml(row.county)}}</strong><br>` +
                                     `${{formatInsightNumber(row.total)}} measures &middot; ${{formatInsightPct(row.pass_rate)}} passed`;
                        layer.bindTooltip(html, {{
                            sticky: true,
                            className: 'county-leaflet-tooltip',
                            direction: 'top',
                            offset: [0, -4]
                        }});
                        layer.on({{
                            mouseover: (e) => e.target.setStyle({{ weight: 1.6, color: '#0F172A' }}),
                            mouseout: (e) => leafletCountyLayer.resetStyle(e.target)
                        }});
                    }}
                }}).addTo(leafletCountyMap);

                leafletCountyMap.fitBounds(leafletCountyLayer.getBounds(), {{ padding: [10, 10] }});
                leafletCountyMap.setMaxBounds(leafletCountyLayer.getBounds().pad(0.5));

                applyCountyMapStyle();
                countyMapRendered = true;
            }};

            // The Leaflet container needs to be visible (have a size) before the map is created;
            // when this function runs from an offscreen carousel slide on initial render, sizes are
            // fine because the panel is in the DOM. But to be safe, invalidate after a tick.
            const ensureSized = () => {{
                if (leafletCountyMap) leafletCountyMap.invalidateSize();
            }};

            if (cachedCountyFeatures) {{
                drawMap(cachedCountyFeatures);
                setTimeout(ensureSized, 0);
                return;
            }}
            d3.json('https://cdn.jsdelivr.net/npm/us-atlas@3/counties-10m.json').then(us => {{
                cachedCountyFeatures = topojson.feature(us, us.objects.counties).features
                    .filter(feature => String(feature.id).padStart(5, '0').startsWith('06'));
                drawMap(cachedCountyFeatures);
                setTimeout(ensureSized, 0);
            }}).catch(() => {{
                target.innerHTML = '<div class="empty-state"><p>County map could not load. The leaderboard still shows county totals.</p></div>';
            }});
        }}

        function renderThresholdCallouts() {{
            // Renamed conceptually to "renderRulesPanel" — the function ID stays the same
            // so the renderInsights() call list doesn't need to change. Renders the entire
            // Rules panel below the chart: hero, threshold table, two near-miss landmark
            // cards, plain-English comparison block, and the bridge to Measure Types.
            const ti = insightsData.threshold_insights || {{}};
            const ts = insightsData.threshold_stats || [];
            const tt = (insightsData.type_insights && insightsData.type_insights.type_threshold_profiles) || [];

            // Hero
            const heroTarget = document.getElementById('rulesHero');
            if (heroTarget) {{
                const count = ti.majority_failure_count;
                const share = ti.majority_failure_share_higher_thresholds;
                const higherDecided = ti.higher_threshold_decided;
                heroTarget.innerHTML = `
                    <div class="rules-hero-num">${{count == null ? '—' : count.toLocaleString()}}</div>
                    <div class="rules-hero-headline">measures got more yes votes than no &mdash; and still failed.</div>
                    <div class="rules-hero-sub">
                        That is about <strong>${{share == null ? '—' : share.toFixed(0) + '%'}}</strong> of decided contests at the 55% or two-thirds threshold (${{higherDecided == null ? '—' : higherDecided.toLocaleString()}} records). Almost none come from simple-majority elections, where a majority is enough by definition.
                    </div>
                `;
            }}

            // Threshold table — 5 columns
            const tableTarget = document.getElementById('rulesThresholdTable');
            if (tableTarget) {{
                tableTarget.innerHTML = `
                    <table class="kf-mini-table" aria-label="Outcomes by legal threshold">
                        <thead><tr><th scope="col">Threshold</th><th scope="col">Decided</th><th scope="col">Pass rate</th><th scope="col">Failed below majority</th><th scope="col">Majority but failed</th></tr></thead>
                        <tbody>
                            ${{ts.map(row => {{
                                const total = row.total || 0;
                                const passed = row.passed || 0;
                                const majFail = row.majority_failed || 0;
                                const belowMaj = Math.max(total - passed - majFail, 0);
                                return `
                                    <tr>
                                        <th scope="row">${{escapeHtml(row.threshold)}}</th>
                                        <td>${{formatInsightNumber(total)}}</td>
                                        <td><strong>${{formatInsightPct(row.pass_rate)}}</strong></td>
                                        <td>${{formatInsightNumber(belowMaj)}}</td>
                                        <td><strong>${{formatInsightNumber(majFail)}}</strong></td>
                                    </tr>
                                `;
                            }}).join('')}}
                        </tbody>
                    </table>
                `;
            }}

            // Landmark near-misses (use curated `landmark_near_misses` from the JSON,
            // not raw highest_yes_failures or closest_to_legal_threshold).
            const landTarget = document.getElementById('rulesLandmarks');
            if (landTarget) {{
                const landmarks = (ti.landmark_near_misses || []).slice(0, 2);
                if (landmarks.length === 0) {{
                    landTarget.innerHTML = '';
                }} else {{
                    landTarget.classList.add('rules-landmarks');
                    landTarget.innerHTML = landmarks.map(m => {{
                        const where = m.county || 'Unknown';
                        const year = m.year ? String(m.year) : '';
                        const cat = m.category_type || '';
                        const topic = m.topic || '';
                        const subtitle = [year, cat, topic].filter(Boolean).join(' &middot; ');
                        const tail = m.threshold ? `failed under the ${{escapeHtml(m.threshold)}} threshold` : 'failed';
                        return `
                            <div class="rules-landmark-card">
                                <div class="rules-landmark-yes">${{m.percent_yes == null ? '—' : m.percent_yes.toFixed(2) + '%'}} yes</div>
                                <div class="rules-landmark-tag">${{escapeHtml(where)}}</div>
                                <div class="rules-landmark-meta">${{subtitle}} &mdash; ${{tail}}.</div>
                            </div>
                        `;
                    }}).join('');
                }}
            }}

            // Plain-English replacement for the odds-ratio block.
            const peTarget = document.getElementById('rulesPlainEnglish');
            if (peTarget) {{
                const diffs = ti.threshold_pp_diffs || [];
                const fmtDiff = d => {{
                    const sign = d.pp_vs_simple_majority >= 0 ? '+' : '−';
                    const mag = Math.abs(d.pp_vs_simple_majority).toFixed(1);
                    return `<strong>${{sign}}${{mag}} pts</strong>`;
                }};
                const diff55 = diffs.find(d => d.threshold === '55%');
                const diff66 = diffs.find(d => d.threshold === '66.67%');
                if (diff55 || diff66) {{
                    peTarget.innerHTML = `
                        <div>
                            On <strong>55%</strong> contests, voters approve at about ${{diff55 ? fmtDiff(diff55) : '—'}} relative to simple-majority elections.
                            On <strong>two-thirds</strong> contests, the rate falls ${{diff66 ? fmtDiff(diff66) : '—'}}.
                        </div>
                        <span class="rules-plain-caveat">Threshold assignment is selected (mostly by instrument), not random &mdash; so these gaps describe the contests, not voter mood.</span>
                    `;
                }} else {{
                    peTarget.innerHTML = '';
                }}
            }}

            // Bridge to Measure Types panel — instrument-first, prop-history second.
            const bridgeTarget = document.getElementById('rulesBridge');
            if (bridgeTarget) {{
                const byType = name => tt.find(p => p.category_type === name) || {{}};
                const bondFails = byType('Bond').majority_failed;
                const propFails = byType('Property Tax').majority_failed;
                const salesFails = byType('Sales Tax').majority_failed;
                const fmt = n => n == null ? '—' : formatInsightNumber(n);
                bridgeTarget.innerHTML = `
                    <p>
                        Threshold rules aren&rsquo;t randomly assigned &mdash; they attach to instrument. Most two-thirds contests are
                        property-tax measures (<strong>${{fmt(propFails)}}</strong> majority-backed failures); 55% is mostly school bonds
                        (<strong>${{fmt(bondFails)}}</strong>); sales-tax measures sit in the simple-majority world but still produced
                        <strong>${{fmt(salesFails)}}</strong> majority-backed failures where a higher rule applied. The legal scaffolding here
                        is Prop 13 (1978), Prop 218 (1996), and Prop 39 (2000).
                        <button class="overview-jump-btn" onclick="jumpToInsightsPanel('insightsTypesPanel')">See the type breakdown &rarr;</button>
                    </p>
                `;
            }}
        }}

        function renderStatisticalComparisons() {{
            // Folded into renderThresholdCallouts; no-op kept so the renderInsights call list
            // doesn't need to change.
        }}

        function renderCloseMeasures() {{
            const target = document.getElementById('closeMeasuresList');
            const summary = document.getElementById('closeCallSummary');
            const closeInsight = insightsData.close_call_insights || {{}};
            if (summary) {{
                const counts = closeInsight.counts || {{}};
                summary.innerHTML = `
                    <div class="mini-callout"><strong>${{formatInsightNumber(counts.under_1 || 0)}}</strong><span>measures within 1 point of 50% yes</span></div>
                    <div class="mini-callout"><strong>${{formatInsightNumber(counts.under_5 || 0)}}</strong><span>measures within 5 points of 50% yes</span></div>
                `;
            }}
            if (!target) return;
            const rows = ((insightsData.margin_stats || {{}}).closest_measures || []).slice(0, 8);
            target.innerHTML = rows.map(row => `
                <div class="compact-row">
                    <div>
                        <strong>${{escapeHtml(row.year + ' · ' + (row.county || 'Statewide'))}}</strong>
                        <span>${{escapeHtml(row.title || row.measure_id || 'Measure')}}</span>
                    </div>
                    <em>${{formatInsightPct(row.percent_yes)}} yes · ${{row.passed ? 'Passed' : 'Failed'}}</em>
                </div>
            `).join('');
            const legalRows = (closeInsight.closest_to_legal_threshold || []).slice(0, 5);
            const fiftyRows = rows.slice(0, 5).map(row => `
                <div class="compact-row">
                    <div>
                        <strong>${{escapeHtml(row.year + ' - ' + (row.county || 'Statewide'))}}</strong>
                        <span>${{escapeHtml(row.title || row.measure_id || 'Measure')}}</span>
                    </div>
                    <em>${{formatInsightPct(row.percent_yes)}} yes - ${{row.passed ? 'Passed' : 'Failed'}}</em>
                </div>
            `).join('');
            const legalList = legalRows.map(row => {{
                const margin = row.legal_margin == null ? '' : Math.abs(row.legal_margin).toFixed(2) + ' pts ' + (row.legal_margin >= 0 ? 'above' : 'below');
                return `
                    <div class="compact-row">
                        <div>
                            <strong>${{escapeHtml(row.year + ' - ' + (row.county || 'Statewide'))}}</strong>
                            <span>${{escapeHtml(row.title || row.measure_id || 'Measure')}}</span>
                        </div>
                        <em>${{escapeHtml(margin)}} threshold</em>
                    </div>
                `;
            }}).join('');
            target.innerHTML = `
                <div class="compact-list-heading">Closest to 50% yes</div>
                ${{fiftyRows}}
                <div class="compact-list-heading">Closest to legal threshold</div>
                ${{legalList}}
            `;
        }}

        // Title-case a donor name. CalAccess donor strings are mostly ALL CAPS;
        // rendering them shouty crowds the panel. We title-case ALL-CAPS inputs
        // and leave already-mixed-case inputs alone, with three escape hatches:
        // a brand-display map (DaVita, FanDuel), an acronym allow-list (PAC,
        // SEIU), and a lowercase-connective list (of, and, for) for grammar.
        const FINANCE_ACRONYMS = new Set([
            'PAC','PACS','SEIU','AFSCME','AFT','UFCW','CTA','AHF','AIDS',
            'PG&E','DBA','D/B/A','LLC','LLP','LP','INC','INC.','CO',
            'CO.','CORP','USA','US','U.S.','UAE','UK','TV','EV','EVS','II',
            'III','IV','VI','VII','JR','JR.','SR','SR.','NAACP','ACLU',
            'NRA','AARP','ALG','CAHHS','CCPOA','CSEA','SD','LA','SF','OC',
            'CA','BAC','PACE','COPE','HHS','SF','DC'
        ]);
        const FINANCE_LOWER_WORDS = new Set([
            'of','for','and','the','in','on','to','at','by','with','a','an',
            'as','vs','de','la','el','los','las'
        ]);
        const FINANCE_BRAND_DISPLAY = {{
            'DAVITA': 'DaVita',
            'FANDUEL': 'FanDuel',
            'DRAFTKINGS': 'DraftKings',
            'DOORDASH': 'DoorDash',
            'INSTACART': 'Instacart',
            'JPMORGAN': 'JPMorgan',
            'YOUTUBE': 'YouTube',
            'EBAY': 'eBay',
        }};
        function formatDonorName(raw) {{
            if (!raw) return '';
            // Strip a trailing parenthetical "(SPONSORED BY ...)" suffix.
            let name = String(raw).replace(/\\s*\\(SPONSORED BY[^)]*\\)\\s*$/i, '').trim();
            // Person names: "LAST, FIRST [MIDDLE]" → "First Last"
            const personMatch = name.match(/^([A-Z][A-Z'\\.\\-]+),\\s+([A-Z][A-Z' \\.\\-]+)$/);
            if (personMatch) {{
                name = personMatch[2] + ' ' + personMatch[1];
            }}
            // Two modes:
            //  - ALL-CAPS input: full title-case + brand + acronym + connectives
            //  - Mixed-case input: leave casing alone EXCEPT lowercase the
            //    connective words that happen to be capitalized — fixes the
            //    "California Hospitals Committee on Issues, Sponsored By
            //    CAHHS" case where "By" should be "by" (Codex round-5 catch).
            const isAllCaps = !/[a-z]/.test(name);

            const tokens = name.split(/(\\s+|[\\-/])/);
            const wordIdxs = [];
            tokens.forEach((t, i) => {{
                if (/[A-Z]/.test(t) && t !== '-' && t !== '/') wordIdxs.push(i);
            }});
            const firstWordIdx = wordIdxs[0];
            const lastWordIdx = wordIdxs[wordIdxs.length - 1];

            return tokens.map((tok, idx) => {{
                if (!tok || /^\\s+$/.test(tok) || tok === '-' || tok === '/') return tok;
                const m = tok.match(/^([^A-Z0-9&]*)([A-Z0-9&.''\\-]+)([^A-Z0-9&]*)$/);
                if (!m) return tok;
                const [, lead, core, trail] = m;
                const upperKey = core.replace(/[.,;:]+$/, '').toUpperCase();
                if (FINANCE_BRAND_DISPLAY[upperKey]) {{
                    return lead + FINANCE_BRAND_DISPLAY[upperKey] + trail;
                }}
                // Acronym uppercasing only kicks in for ALL-CAPS inputs.
                // Mixed-case inputs may include "PAC" / "CAHHS" / etc. already
                // correctly capitalized in their original case — don't disturb.
                if (isAllCaps && FINANCE_ACRONYMS.has(upperKey)) {{
                    return lead + core.toUpperCase() + trail;
                }}
                if (idx !== firstWordIdx && idx !== lastWordIdx
                    && FINANCE_LOWER_WORDS.has(core.toLowerCase())) {{
                    return lead + core.toLowerCase() + trail;
                }}
                if (isAllCaps) {{
                    // Title-case the token for ALL-CAPS inputs.
                    const lower = core.toLowerCase();
                    return lead + lower.charAt(0).toUpperCase() + lower.slice(1) + trail;
                }}
                // Mixed-case input: leave the token alone (it's already
                // properly cased by whatever produced it).
                return tok;
            }}).join('');
        }}

        function renderSectorChip(sector) {{
            // Small neutral pill rendered next to donor names when the
            // hand-curated sector lookup hits. Returns '' for null sector
            // so unclassified donors render without any chip.
            if (!sector) return '';
            // Compact CSS-friendly handle for sector-specific colors later
            // (slugged: lowercase, non-alphanum → '-'). Empty class for now;
            // the .finance-sector-chip styling is neutral grey.
            const slug = String(sector).toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
            return `<span class="finance-sector-chip" data-sector="${{slug}}">${{escapeHtml(sector)}}</span>`;
        }}

        function formatFinanceMeasureNumber(measureId) {{
            if (!measureId) return '';
            // Turn "PROP_22" into "Prop 22" for display.
            return String(measureId)
                .replace(/^PROP_/i, 'Prop ')
                .replace(/^MEASURE_/i, 'Measure ')
                .replace(/_/g, ' ');
        }}

        function renderFinanceInsights() {{
            const finance = insightsData.finance || {{}};

            // Module 1 — Hero anchor
            const panel = document.getElementById('financeInsightSummary');
            if (panel) {{
                const losses = (finance.better_funded_known || 0) - (finance.better_funded_won || 0);
                const lossPct = finance.better_funded_known
                    ? Math.round((losses / finance.better_funded_known) * 100 * 10) / 10
                    : null;
                panel.innerHTML = `
                    <div class="mini-callout"><strong>${{formatDollars(finance.total_receipts || 0)}}</strong><span>linked statewide receipts (${{formatInsightNumber(finance.measure_count || 0)}} campaigns)</span></div>
                    <div class="mini-callout"><strong>${{formatInsightPct(finance.better_funded_win_rate)}}</strong><span>better-funded side win rate</span></div>
                    <div class="mini-callout"><strong>${{formatInsightNumber(losses)}}</strong><span>times the better-funded side lost (${{lossPct != null ? lossPct + '%' : 'n/a'}})</span></div>
                `;
            }}

            // Module 3a — Top 15 donors overall
            const topDonors = document.getElementById('financeTopDonors');
            if (topDonors) {{
                const rows = finance.top_donors_overall || [];
                topDonors.innerHTML = rows.map(d => `
                    <li class="finance-donor-row">
                        <div class="finance-donor-name">
                            <span class="finance-donor-name-text">${{escapeHtml(formatDonorName(d.name))}}</span>
                            ${{renderSectorChip(d.donor_sector)}}
                        </div>
                        <div class="finance-donor-meta">
                            <span class="finance-donor-amount">${{formatDollars(d.total_amount || 0)}}</span>
                            <span class="finance-donor-count">${{d.n_campaigns}} campaign${{d.n_campaigns === 1 ? '' : 's'}}</span>
                        </div>
                    </li>
                `).join('');
            }}

            // Module 3b — Repeat players (3+ campaigns, ≥$1M)
            const repeats = document.getElementById('financeRepeatDonors');
            if (repeats) {{
                const rows = finance.repeat_donors || [];
                repeats.innerHTML = rows.map(d => `
                    <li class="finance-donor-row">
                        <div class="finance-donor-name">
                            <span class="finance-donor-name-text">${{escapeHtml(formatDonorName(d.name))}}</span>
                            ${{renderSectorChip(d.donor_sector)}}
                        </div>
                        <div class="finance-donor-meta">
                            <span class="finance-donor-amount">${{d.n_campaigns}} campaigns</span>
                            <span class="finance-donor-count">${{formatDollars(d.total_amount || 0)}} aggregate</span>
                        </div>
                    </li>
                `).join('');
            }}

            // Module 4 — Marquee fights (3 cards)
            const marqueeWrap = document.getElementById('financeMarqueeFights');
            if (marqueeWrap) {{
                const fights = finance.marquee_fights || [];
                marqueeWrap.innerHTML = fights.map(fight => {{
                    const winSide = fight.passed === 1 ? 'support' : (fight.passed === 0 ? 'oppose' : null);
                    const outcomeLabel = fight.passed === 1
                        ? `Passed &mdash; support side won`
                        : (fight.passed === 0 ? `Failed &mdash; oppose side won` : `Outcome not recorded`);
                    const supportTopShare = fight.support_top5_share != null
                        ? Math.round(fight.support_top5_share) + '% from top 5'
                        : null;
                    const opposeTopShare = fight.oppose_top5_share != null
                        ? Math.round(fight.oppose_top5_share) + '% from top 5'
                        : null;
                    const renderSide = (label, total, donors, topShare, isWinner) => {{
                        const donorRows = (donors || []).slice(0, 5).map(d => `
                            <li>
                                <span class="finance-fight-donor">${{escapeHtml(formatDonorName(d.name))}}${{renderSectorChip(d.donor_sector)}}</span>
                                <span class="finance-fight-amount">${{formatDollars(d.total_amount || 0)}}</span>
                            </li>
                        `).join('');
                        // Neutral "Won" badge instead of color-tinting the panel —
                        // tint reads as endorsing the winning money side, which
                        // we don't want on a money-vs-outcome panel.
                        const wonBadge = isWinner ? '<span class="finance-fight-won-badge">Won</span>' : '';
                        return `
                            <div class="finance-fight-side">
                                <div class="finance-fight-side-head">
                                    <span class="finance-fight-side-label">${{label}}${{wonBadge}}</span>
                                    <span class="finance-fight-side-total">${{formatDollars(total || 0)}}</span>
                                </div>
                                ${{topShare ? `<div class="finance-fight-side-share">${{topShare}}</div>` : ''}}
                                <ol class="finance-fight-donors">${{donorRows}}</ol>
                            </div>
                        `;
                    }};
                    return `
                        <article class="finance-fight-card">
                            <header class="finance-fight-header">
                                <div class="finance-fight-eyebrow">${{escapeHtml(formatFinanceMeasureNumber(fight.measure_id))}} &middot; ${{fight.election_year}}</div>
                                <h5 class="finance-fight-headline">${{escapeHtml(fight.headline || '')}}</h5>
                                <div class="finance-fight-outcome">${{outcomeLabel}}</div>
                            </header>
                            <div class="finance-fight-sides">
                                ${{renderSide('Support', fight.support_receipts, fight.support_top_donors, supportTopShare, winSide === 'support')}}
                                ${{renderSide('Oppose', fight.oppose_receipts, fight.oppose_top_donors, opposeTopShare, winSide === 'oppose')}}
                            </div>
                            <p class="finance-fight-takeaway">${{escapeHtml(fight.takeaway || '')}}</p>
                        </article>
                    `;
                }}).join('');
            }}
        }}

        function renderInsightsMethodology() {{
            const target = document.getElementById('insightsMethodology');
            if (!target) return;
            const methodology = insightsData.methodology || {{}};
            const sources = (methodology.sources || []).map(source => {{
                const label = Array.isArray(source) ? source[0] + ': ' + formatInsightNumber(source[1]) + ' records' : source;
                return `<li>${{escapeHtml(label)}}</li>`;
            }}).join('');
            const notes = (methodology.notes || []).map(note => `<li>${{escapeHtml(note)}}</li>`).join('');
            target.innerHTML = `
                <details>
                    <summary>Methodology and limits</summary>
                    <div>
                        <p>${{escapeHtml(methodology.scope || 'Active, non-duplicate records in the local project database.')}}</p>
                        <strong>Sources</strong>
                        <ul>${{sources}}</ul>
                        <strong>Notes</strong>
                        <ul>${{notes}}</ul>
                    </div>
                </details>
            `;
        }}

        function displayResults() {{
            updateViewVisibility();

            if (currentView === 'insights') {{
                renderInsights();
                return;
            }}

            const container = document.getElementById('resultsContainer');

            // Explore matrix view
            if (currentView === 'explore') {{
                container.innerHTML = renderMatrix();
                syncMatrixScrollbars();
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
                            <option value="12" ${{pagination.itemsPerPage === 12 ? 'selected' : ''}}>12 per page</option>
                            <option value="10" ${{pagination.itemsPerPage === 10 ? 'selected' : ''}}>10 per page</option>
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

            // Description / summary preview — kept for all card variants
            // per Igor's pushback on v1's "cut descriptions entirely"
            // call. The v2 design tightens whitespace but keeps the
            // info-rich card shape.
            let summary = '';
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
            if (isPending && measure.historical_context && !summary) {{
                const ctx = measure.historical_context;
                summary = `California has voted on ${{ctx.total_similar.toLocaleString()}} similar ${{ctx.matched_topic.toLowerCase()}} measures since ${{ctx.year_range.split('-')[0]}}. They passed ${{ctx.pass_rate}}% of the time with a median YES vote of ${{ctx.median_yes}}%.`;
            }} else if (isPending && !summary) {{
                summary = 'Full measure details will be available closer to the election. Check back for official language, fiscal analysis, and voter guide information.';
            }}
            const maxLength = 200;
            const truncatedSummary = summary.length > maxLength ? summary.substring(0, maxLength) + '...' : summary;
            const descriptionHtml = truncatedSummary
                ? `<div class="card-summary">${{escapeHtml(truncatedSummary)}}</div>`
                : '';

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

            // Build meta items - % Yes / topic / source / landmark flag.
            // % Yes stays in the meta row (v1 had moved it to the header;
            // that read as awkward floating text — reverted).
            const metaItems = [];
            if (measure.is_landmark) metaItems.push('⭐ Historic');
            if (percentYes != null && !isPending) metaItems.push(`${{Math.round(percentYes)}}% Yes`);
            if (topic) metaItems.push(escapeHtml(topic));
            if (source) metaItems.push(escapeHtml(source));
            if (isPending && !metaItems.length) metaItems.push('Election pending');

            // Use data attribute + index lookup instead of serializing entire object into onclick
            const mIdx = allMeasures.indexOf(measure);

            return `
                <div class="measure-card ${{cardClass}}" data-midx="${{mIdx}}" onclick="viewMeasure(allMeasures[this.dataset.midx])">
                    <div class="card-header">
                        <span class="card-year">${{year}}</span>
                        <span class="badge badge-${{passedClass}}">${{passedText}}</span>
                    </div>
                    <h3 class="card-title">${{escapeHtml(displayTitle)}}</h3>
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
            
            const mIdx = allMeasures.indexOf(measure);
            return `
                <div class="measure-list-item" data-midx="${{mIdx}}" onclick="viewMeasure(allMeasures[this.dataset.midx])">
                    <div class="badge badge-${{passedClass}}">${{passedText}}</div>
                    <div>
                        <div style="font-weight: 500;">${{escapeHtml(displayTitle)}}</div>
                        <div style="font-size: 0.875rem; color: var(--text-secondary);">
                            ${{year}} • ${{escapeHtml(measure.topic_primary || measure.category_topic || 'General')}}
                        </div>
                    </div>
                    <div style="text-align: right;">
                        ${{measure.percent_yes != null ? `<div style="font-weight: 500;">${{Math.round(measure.percent_yes)}}% Yes</div>` : ''}}
                        <div style="font-size: 0.75rem; color: var(--text-tertiary);">
                            ${{escapeHtml(measure.data_source || measure.source || '')}}
                        </div>
                    </div>
                </div>
            `;
        }}
        
        // View measure details in modal
        function viewMeasure(measure) {{
            const modal = document.getElementById('measureDetailModal');
            const isPending = isPendingMeasure(measure);

            // Reset to Main tab
            switchModalTab('main');

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
                badgesHtml.push(`<span class="badge badge-neutral">${{escapeHtml(measure.display_category_type || measure.category_type)}}</span>`);
            }}
            if (measure.category_topic) {{
                badgesHtml.push(`<span class="badge badge-neutral">${{escapeHtml(measure.category_topic)}}</span>`);
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

            let summaryIsHtml = false;
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
                summaryIsHtml = true;
                summaryEl.classList.remove('no-summary-text');
            }} else {{
                summaryText = 'No summary available for this measure.';
                summaryEl.classList.add('no-summary-text');
            }}

            // Use textContent for DB content, innerHTML only for our own trusted HTML
            if (summaryIsHtml) {{
                summaryEl.innerHTML = summaryText;
            }} else {{
                summaryEl.textContent = summaryText;
            }}

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
                    const relIdx = allMeasures.indexOf(relatedMeasure);
                    return `
                        <div class="related-card" data-midx="${{relIdx}}" onclick="viewMeasure(allMeasures[this.dataset.midx])">
                            <div class="related-header">
                                <span class="related-id">${{escapeHtml(relatedDisplayId || relatedMeasure.county || '')}}</span>
                                <span class="related-year">${{relatedMeasure.year}}</span>
                            </div>
                            <div class="related-title">${{escapeHtml(shortTitle)}}</div>
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

            // Research briefing section (for measures with agent-generated briefings)
            const briefingSection = document.getElementById('modalBriefingSection');
            const briefingContent = document.getElementById('modalBriefingContent');
            if (measure.briefing && measure.briefing.text) {{
                let bHtml = '';
                const b = measure.briefing;

                // Briefing summary
                if (b.text && b.text !== 'Not yet available.') {{
                    bHtml += `<div style="font-size:0.9rem;line-height:1.6;margin-bottom:1rem;">${{escapeHtml(b.text)}}</div>`;
                }}

                // Fiscal impact
                if (b.fiscal_impact && b.fiscal_impact !== 'Not yet available.' && b.fiscal_impact.length > 20) {{
                    bHtml += `<div style="margin-bottom:0.75rem;"><strong>Fiscal Impact:</strong> <span style="font-size:0.9rem;">${{escapeHtml(b.fiscal_impact)}}</span></div>`;
                }}

                // Pro/con arguments
                try {{
                    const pros = typeof b.pro_arguments === 'string' ? JSON.parse(b.pro_arguments) : b.pro_arguments;
                    const cons = typeof b.con_arguments === 'string' ? JSON.parse(b.con_arguments) : b.con_arguments;

                    if ((pros && pros.length > 0 && pros[0] !== 'Not yet available.') ||
                        (cons && cons.length > 0 && cons[0] !== 'Not yet available.')) {{
                        bHtml += `<div class="briefing-args-grid" style="display:grid;grid-template-columns:1fr 1fr;gap:1rem;margin-bottom:0.75rem;">`;
                        if (pros && pros.length > 0 && pros[0] !== 'Not yet available.') {{
                            bHtml += `<div><div style="font-weight:600;color:#2D9D78;margin-bottom:0.3rem;font-size:0.85rem;">Arguments For <span class="info-tip" data-tip="Key arguments in favor of this measure, drawn from official sources, ballot arguments, and nonpartisan analyses.">i</span></div>`;
                            pros.forEach(p => {{ bHtml += `<div style="font-size:0.8rem;margin-bottom:0.3rem;">+ ${{escapeHtml(p)}}</div>`; }});
                            bHtml += `</div>`;
                        }}
                        if (cons && cons.length > 0 && cons[0] !== 'Not yet available.') {{
                            bHtml += `<div><div style="font-weight:600;color:#E54D4D;margin-bottom:0.3rem;font-size:0.85rem;">Arguments Against <span class="info-tip" data-tip="Key arguments against this measure, drawn from official sources, ballot arguments, and nonpartisan analyses.">i</span></div>`;
                            cons.forEach(c => {{ bHtml += `<div style="font-size:0.8rem;margin-bottom:0.3rem;">\u2013 ${{escapeHtml(c)}}</div>`; }});
                            bHtml += `</div>`;
                        }}
                        bHtml += `</div>`;
                    }}
                }} catch(e) {{}}

                if (bHtml) {{
                    briefingContent.innerHTML = bHtml;
                    briefingSection.style.display = 'block';
                }} else {{
                    briefingSection.style.display = 'none';
                }}
            }} else {{
                if (briefingSection) briefingSection.style.display = 'none';
            }}

            // Links section
            const linksContainer = document.getElementById('modalLinks');
            const links = [];

            // Add generated external links first (higher quality)
            // Descriptive labels for link sources
            const linkLabels = {{
                'Ballotpedia': {{ label: 'Measure Details', source: 'Ballotpedia' }},
                'CA Voter Guide': {{ label: 'Official Voter Guide', source: 'CA SOS' }},
                'LAO Analysis': {{ label: 'Fiscal Analysis', source: 'CA LAO' }},
                'LAO Ballot Analysis': {{ label: 'Fiscal Analysis', source: 'CA LAO' }},
                'UC Law SF': {{ label: 'Legal Archive', source: 'UC Law SF' }},
                'Wikipedia': {{ label: 'Encyclopedia', source: 'Wikipedia' }},
                'CA SOS - Qualified Measures': {{ label: 'Official Status', source: 'CA SOS' }},
                'CA SOS Eligible Measures': {{ label: 'Eligible Measures', source: 'CA SOS' }},
                'Campaign Finance': {{ label: 'Campaign Finance', source: 'CAL-ACCESS' }},
                'Official Voter Guide': {{ label: 'Voter Guide', source: 'CA SOS' }},
                "Voter's Edge CA": {{ label: 'Nonpartisan Guide', source: "Voter's Edge" }},
                'CEDA Data Archive': {{ label: 'Election Data', source: 'CEDA' }},
            }};
            // Legislature links have dynamic source names
            const legPattern = /^CA Legislature \((.+)\)$/;
            Object.keys(linkLabels).length; // force eval
            // Add legislature labels dynamically
            ['Assembly Constitutional Amendment', 'Senate Constitutional Amendment', 'Assembly Bill', 'Senate Bill'].forEach(t => {{
                linkLabels[`CA Legislature (${{t}})`] = {{ label: 'Bill Details', source: 'Legislature' }};
            }});
            // County registrar labels are dynamic
            const registrarPattern = /^(.+) County Elections$/;

            const linkIcons = {{
                'ballot': '🗳️',
                'government': '🏛️',
                'academic': '🎓',
                'analysis': '📊',
                'wikipedia': '📚'
            }};

            if (measure.external_links && measure.external_links.length > 0) {{
                measure.external_links.forEach(link => {{
                    const icon = linkIcons[link.icon] || '🔗';
                    const confidenceClass = link.confidence === 'low' ? 'link-low-confidence' : '';
                    let labelInfo = linkLabels[link.source];
                    if (!labelInfo) {{
                        const regMatch = link.source.match(registrarPattern);
                        if (regMatch) {{
                            labelInfo = {{ label: 'County Elections', source: regMatch[1] }};
                        }} else {{
                            labelInfo = {{ label: link.source, source: '' }};
                        }}
                    }}
                    const sourceText = labelInfo.source ? ` <span class="link-source">(${{escapeHtml(labelInfo.source)}})</span>` : '';
                    links.push(`<a href="${{escapeAttr(sanitizeUrl(link.url))}}" target="_blank" rel="noopener noreferrer" class="${{confidenceClass}}">${{icon}} <span class="link-label">${{escapeHtml(labelInfo.label)}}</span>${{sourceText}}</a>`);
                }});
            }}

            // Add original source links
            if (measure.source_url) {{
                links.push(`<a href="${{escapeAttr(sanitizeUrl(measure.source_url))}}" target="_blank" rel="noopener noreferrer">🔗 <span class="link-label">Raw Data</span> <span class="link-source">(${{escapeHtml(measure.data_source || 'Source')}})</span></a>`);
            }}
            if (measure.pdf_url && measure.pdf_url !== '#') {{
                links.push(`<a href="${{escapeAttr(sanitizeUrl(measure.pdf_url))}}" target="_blank" rel="noopener noreferrer">📄 <span class="link-label">Full Ballot Text</span> <span class="link-source">(PDF)</span></a>`);
            }}

            // For pending measures, add helpful official source links
            if (isPending && links.length === 0) {{
                links.push(`<a href="https://www.sos.ca.gov/elections/ballot-measures" target="_blank" rel="noopener noreferrer">🏛️ <span class="link-label">Official Status</span> <span class="link-source">(CA SOS)</span></a>`);
                links.push(`<a href="https://lao.ca.gov/BallotAnalysis" target="_blank" rel="noopener noreferrer">📊 <span class="link-label">Fiscal Analysis</span> <span class="link-source">(CA LAO)</span></a>`);
                links.push(`<a href="https://leginfo.legislature.ca.gov/" target="_blank" rel="noopener noreferrer">📜 <span class="link-label">Bill Details</span> <span class="link-source">(Legislature)</span></a>`);
            }} else if (links.length === 0) {{
                links.push('<span class="no-summary-text" style="grid-column:1/-1;">No external links available</span>');
            }}

            // Render historical context in Research tab (not in Links section)
            const histCtxEl = document.getElementById('modalHistoricalContext');
            if (measure.historical_context) {{
                const ctx = measure.historical_context;
                let ctxHtml = `<div style="padding:0.5rem 0;">`;
                ctxHtml += `<h3>📊 Measures Like This <span class="info-tip" data-tip="Semantically similar past measures found using AI embeddings across CalBallot's 12,000+ measure database. Shows how voters decided on comparable issues.">i</span></h3>`;
                ctxHtml += `<div style="font-size:0.85rem;color:#555;line-height:1.5;">`;
                ctxHtml += `We found <strong>${{ctx.total_similar}}</strong> semantically similar past measures (mostly <strong>${{ctx.matched_topic}}</strong>). `;
                ctxHtml += `They passed <strong>${{ctx.pass_rate}}%</strong> of the time `;
                ctxHtml += `with a median YES vote of <strong>${{ctx.median_yes}}%</strong>.`;
                ctxHtml += `</div>`;

                // Helper: build a tile card for a similar measure, clickable to open its detail
                const buildContextTile = (item) => {{
                    const status = item.passed === 1 ? 'passed' : 'failed';
                    const statusIcon = item.passed === 1 ? '✓' : '✗';
                    const pct = item.percent_yes ? `${{item.percent_yes}}% YES` : '';
                    const title = item.title ? item.title.substring(0, 55) : 'Untitled';
                    const county = item.county || '';
                    // Try to find this measure in allMeasures for clickthrough
                    const match = allMeasures.find(m =>
                        m.year == item.year && m.county === county &&
                        (m.percent_yes && Math.abs(m.percent_yes - item.percent_yes) < 0.5)
                    );
                    const clickAttr = match ? `data-midx="${{allMeasures.indexOf(match)}}" onclick="viewMeasure(allMeasures[this.dataset.midx])" style="cursor:pointer;"` : '';
                    return `<div class="related-card" ${{clickAttr}}>
                        <div class="related-header">
                            <span class="related-id">${{escapeHtml(county)}}</span>
                            <span class="related-year">${{item.year}}</span>
                        </div>
                        <div class="related-title" style="font-size:0.75rem;line-height:1.3;">${{escapeHtml(title)}}</div>
                        <div class="related-meta">
                            <span class="badge badge-${{status}} badge-small">${{statusIcon}}</span>
                            <span style="font-size:0.7rem;color:#888;">${{pct}}</span>
                        </div>
                    </div>`;
                }};

                // Most similar measures — tile grid
                if (ctx.top_similar && ctx.top_similar.length > 0) {{
                    ctxHtml += `<div style="font-size:0.8rem;font-weight:600;margin-top:0.75rem;margin-bottom:0.4rem;">Most similar past measures:</div>`;
                    ctxHtml += `<div class="measure-detail-related" style="grid-template-columns:repeat(3,1fr);gap:0.4rem;">`;
                    ctx.top_similar.forEach(ts => {{ ctxHtml += buildContextTile(ts); }});
                    ctxHtml += `</div>`;
                }}

                // Closest races — tile grid
                if (ctx.closest_races && ctx.closest_races.length > 0) {{
                    ctxHtml += `<div style="font-size:0.8rem;font-weight:600;margin-top:0.75rem;margin-bottom:0.4rem;">Closest races on similar measures:</div>`;
                    ctxHtml += `<div class="measure-detail-related" style="grid-template-columns:repeat(3,1fr);gap:0.4rem;">`;
                    ctx.closest_races.forEach(cr => {{ ctxHtml += buildContextTile(cr); }});
                    ctxHtml += `</div>`;
                }}

                ctxHtml += `</div>`;
                histCtxEl.innerHTML = ctxHtml;
                histCtxEl.parentElement.style.display = 'block';
            }} else {{
                histCtxEl.innerHTML = '';
                histCtxEl.parentElement.style.display = 'none';
            }}

            // Add pending disclaimer
            if (isPending) {{
                links.push(`<div class="pending-disclaimer"><strong>Note:</strong> This measure is pending and has not yet been voted on. Information may be updated as official details become available.</div>`);
            }}

            linksContainer.innerHTML = links.join('');

            // Money & Coalition section
            const financeSection = document.getElementById('modalFinanceSection');
            const financeContent = document.getElementById('modalFinanceContent');
            // v2 finance keyed on measure_db_id (str of measure.id) since
            // bare measure_id ("PROP_1") isn't unique across cycles.
            const fd = financeData[String(measure.id)];
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
        function switchModalTab(tabName) {{
            // Switch active tab button
            document.querySelectorAll('.modal-tab').forEach(t => {{
                t.classList.toggle('active', t.dataset.tab === tabName);
            }});
            // Switch active panel
            document.querySelectorAll('.modal-tab-panel').forEach(p => {{
                p.classList.toggle('active', p.id === 'tab' + tabName.charAt(0).toUpperCase() + tabName.slice(1));
            }});
            // Show empty states if no data
            if (tabName === 'finance') {{
                const hasFinance = document.getElementById('modalFinanceSection').style.display !== 'none';
                document.getElementById('modalFinanceEmpty').style.display = hasFinance ? 'none' : 'block';
            }}
            if (tabName === 'research') {{
                const hasBriefing = document.getElementById('modalBriefingSection').style.display !== 'none';
                const hasContext = document.getElementById('modalHistoricalContext').innerHTML.trim().length > 0;
                document.getElementById('modalResearchEmpty').style.display = (hasBriefing || hasContext) ? 'none' : 'block';
            }}
        }}

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
            // Set default items per page based on view
            if (view === 'grid') {{
                pagination.itemsPerPage = 12;
            }} else if (view === 'list') {{
                pagination.itemsPerPage = 10;
            }}
            pagination.currentPage = 1;
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
                selectedDecades: [],
                thresholds: [],
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
            renderYearNavigation();
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
                if (aiConfig.model) {
                    document.getElementById('openrouterModel').value = aiConfig.model;
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
            const openrouterSection = document.getElementById('openrouterSection');
            const ollamaSection = document.getElementById('ollamaSection');
            const testBtn = document.getElementById('testConnection');

            openrouterSection.style.display = 'none';
            ollamaSection.style.display = 'none';
            testBtn.disabled = !provider;

            if (provider === 'openrouter') {
                openrouterSection.style.display = 'block';
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
                if (provider === 'openrouter') {
                    const apiKey = document.getElementById('apiKey').value;
                    const model = document.getElementById('openrouterModel').value;
                    const response = await fetch('https://openrouter.ai/api/v1/chat/completions', {
                        method: 'POST',
                        headers: {
                            'Authorization': `Bearer ${apiKey}`,
                            'Content-Type': 'application/json',
                            'HTTP-Referer': 'https://cal-vgp.igorgeyn.com',
                            'X-Title': 'CalBallot'
                        },
                        body: JSON.stringify({
                            model: model,
                            max_tokens: 5,
                            messages: [{ role: 'user', content: 'Say OK' }]
                        })
                    });
                    if (response.ok) {
                        statusEl.textContent = '✓ Connected to ' + model.split('/')[1];
                        statusEl.className = 'connection-status success';
                    } else {
                        const err = await response.json().catch(() => ({}));
                        throw new Error(err.error?.message || 'Invalid API key or model');
                    }
                } else if (provider === 'ollama') {
                    const url = document.getElementById('ollamaUrl').value;
                    const response = await fetch(`${url}/api/tags`);
                    if (response.ok) {
                        statusEl.textContent = '✓ Connected to Ollama';
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

            if (provider === 'openrouter') {
                const apiKey = document.getElementById('apiKey').value;
                if (!apiKey) {
                    alert('Please enter an OpenRouter API key');
                    return;
                }
                config.apiKey = apiKey;
                config.model = document.getElementById('openrouterModel').value;
            } else if (provider === 'ollama') {
                config.ollamaUrl = document.getElementById('ollamaUrl').value;
                config.ollamaModel = document.getElementById('ollamaModel').value;
            }

            saveAIConfig(config);
            closeChatSettings();

            addBotMessage('AI configured! Using ' + (provider === 'openrouter' ? config.model.split('/')[1] : 'Ollama') + '. Ask me anything about ballot measures.');
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
            if (aiConfig.provider === 'openrouter') {
                return await callOpenRouter(prompt);
            } else if (aiConfig.provider === 'ollama') {
                return await callOllama(prompt);
            }
            throw new Error('No AI provider configured');
        }

        // Call OpenRouter API (unified access to 100+ models, no CORS proxy needed)
        async function callOpenRouter(prompt) {
            const response = await fetch('https://openrouter.ai/api/v1/chat/completions', {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${aiConfig.apiKey}`,
                    'Content-Type': 'application/json',
                    'HTTP-Referer': 'https://cal-vgp.igorgeyn.com',
                    'X-Title': 'CalBallot'
                },
                body: JSON.stringify({
                    model: aiConfig.model,
                    messages: [{ role: 'user', content: prompt }],
                    max_tokens: 1024
                })
            });

            if (!response.ok) {
                const err = await response.json().catch(() => ({}));
                throw new Error(err.error?.message || 'OpenRouter API error');
            }

            const data = await response.json();
            return data.choices[0].message.content;
        }

        // Call Ollama API (local, free, offline)
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
