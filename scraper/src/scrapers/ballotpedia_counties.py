"""
Ballotpedia County Scraper
Scrapes ballot measure data from Ballotpedia county pages
"""
import logging
import re
from typing import List, Dict, Optional
from datetime import datetime
import requests
from bs4 import BeautifulSoup

from ..database.models import BallotMeasure

logger = logging.getLogger(__name__)


class BallotpediaCountyScraper:
    """Scraper for Ballotpedia county ballot measure pages"""

    # All 58 California counties
    CALIFORNIA_COUNTIES = [
        "Alameda", "Alpine", "Amador", "Butte", "Calaveras", "Colusa", "Contra Costa",
        "Del Norte", "El Dorado", "Fresno", "Glenn", "Humboldt", "Imperial", "Inyo",
        "Kern", "Kings", "Lake", "Lassen", "Los Angeles", "Madera", "Marin", "Mariposa",
        "Mendocino", "Merced", "Modoc", "Mono", "Monterey", "Napa", "Nevada", "Orange",
        "Placer", "Plumas", "Riverside", "Sacramento", "San Benito", "San Bernardino",
        "San Diego", "San Francisco", "San Joaquin", "San Luis Obispo", "San Mateo",
        "Santa Barbara", "Santa Clara", "Santa Cruz", "Shasta", "Sierra", "Siskiyou",
        "Solano", "Sonoma", "Stanislaus", "Sutter", "Tehama", "Trinity", "Tulare",
        "Tuolumne", "Ventura", "Yolo", "Yuba"
    ]

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })

    def get_county_url(self, county: str) -> str:
        """Generate Ballotpedia URL for a county"""
        # Handle special cases
        county_formatted = county.replace(" ", "_")
        return f"https://ballotpedia.org/{county_formatted}_County,_California_ballot_measures"

    def scrape_county(self, county: str) -> List[BallotMeasure]:
        """
        Scrape all ballot measures for a specific county

        Args:
            county: County name (e.g., "Los Angeles")

        Returns:
            List of BallotMeasure objects
        """
        url = self.get_county_url(county)
        logger.info(f"Scraping {county} County from {url}")

        try:
            import time

            response = self.session.get(url, timeout=30)

            # Handle rate limiting (HTTP 202 with empty content)
            if response.status_code == 202 or len(response.content) == 0:
                for attempt in range(3):
                    wait_time = 10 * (2 ** attempt)
                    logger.warning(f"Rate limited on county page, waiting {wait_time}s (attempt {attempt + 1}/3)")
                    time.sleep(wait_time)
                    response = self.session.get(url, timeout=30)
                    if response.status_code == 200 and len(response.content) > 0:
                        break
                else:
                    logger.error(f"Rate limited after 3 retries for {county} County")
                    return []

            response.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to fetch {county} County page: {e}")
            return []

        soup = BeautifulSoup(response.content, 'html.parser')
        measures = []
        seen_urls = set()  # Deduplicate by source URL

        # Get main content
        content = soup.find('div', class_='mw-parser-output')
        if not content:
            logger.warning(f"Could not find main content for {county} County")
            return []

        # Find year headers (they can be h1 or h2)
        year_headers = content.find_all(['h1', 'h2'])

        for year_header in year_headers:
            year_text = year_header.get_text().strip()

            # Check if it's a year (e.g., "2025", "2024")
            year_match = re.match(r'^(\d{4})$', year_text)
            if not year_match:
                continue

            section_year = int(year_match.group(1))

            # Get content between this year and the next year heading
            current = year_header.find_next_sibling()

            while current and current.name not in ['h1', 'h2']:
                # Look for election date headers (h3)
                if current.name == 'h3':
                    election_date = current.get_text().strip()

                    # Try to extract the real year from the election date header
                    # e.g. "November 3, 2020 election" or "June 7, 2022"
                    date_year_match = re.search(r'(\d{4})', election_date)
                    real_year = int(date_year_match.group(1)) if date_year_match else section_year

                    # Find the list of measures under this election
                    measures_list = current.find_next_sibling('ul')

                    if measures_list:
                        for li in measures_list.find_all('li', recursive=False):
                            measure = self._parse_measure_item(li, real_year, election_date, county)
                            if measure:
                                # Skip navigation/info links
                                if measure.title and any(skip in measure.title for skip in [
                                    "Local ballot measures, California",
                                    "Ballot measure information on California",
                                    "ballot measures in",
                                ]):
                                    continue

                                # Try to extract actual year from title if it contains a date
                                title_year_match = re.search(r'\((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}\)', measure.title or '')
                                if title_year_match:
                                    ty = re.search(r'(\d{4})', title_year_match.group(0))
                                    if ty:
                                        measure.year = int(ty.group(1))

                                # Deduplicate by URL
                                if measure.source_url and measure.source_url in seen_urls:
                                    continue
                                if measure.source_url:
                                    seen_urls.add(measure.source_url)

                                measures.append(measure)

                current = current.find_next_sibling()

        logger.info(f"Found {len(measures)} measures for {county} County")
        return measures

    def _parse_measure_item(self, li_element, year: int, election_date: str, county: str) -> Optional[BallotMeasure]:
        """Parse a single measure list item"""
        try:
            # Find the main link (measure title)
            link = li_element.find('a')
            if not link:
                return None

            measure_title = link.get_text().strip()
            measure_url = link.get('href', '')

            # Make URL absolute if needed
            if measure_url and not measure_url.startswith('http'):
                measure_url = f"https://ballotpedia.org{measure_url}"

            # Extract measure ID from title (e.g., "Measure A" or "Proposition 13")
            measure_id_match = re.search(r'(Measure|Proposition)\s+([A-Z0-9]+)', measure_title, re.IGNORECASE)
            measure_id = measure_id_match.group(2) if measure_id_match else None

            # Check for pass/fail status
            passed = None
            img_tags = li_element.find_all('img')
            for img in img_tags:
                alt_text = img.get('alt', '').lower()
                if 'approved' in alt_text or 'yes' in alt_text:
                    passed = True
                elif 'defeated' in alt_text or 'no' in alt_text:
                    passed = False

            # Extract description text (everything after the link)
            full_text = li_element.get_text()
            description = full_text[len(measure_title):].strip()

            # Clean up description
            description = re.sub(r'^[\s:•\-]+', '', description)
            description = re.sub(r'\s+', ' ', description).strip()

            # Parse election date to get month
            month_match = re.search(r'(January|February|March|April|May|June|July|August|September|October|November|December)', election_date, re.IGNORECASE)
            election_type = "Primary" if month_match and month_match.group(1) in ["March", "June"] else "General"

            # Fetch detailed summary from measure page (for recent measures)
            summary_title = None
            summary_text = None
            ballot_question = None
            has_summary = False

            if measure_url and year >= 2020:  # Only fetch summaries for recent measures
                summary_data = self._fetch_measure_summary(measure_url)
                if summary_data:
                    ballot_question = summary_data.get('ballot_question')
                    summary_title = summary_data.get('summary_title')
                    summary_text = summary_data.get('summary_text')
                    has_summary = bool(summary_title or summary_text or ballot_question)

            # Create BallotMeasure object
            measure = BallotMeasure(
                measure_id=measure_id,
                year=year,
                county=county.upper(),
                title=measure_title,
                description=description,
                ballot_question=ballot_question,
                summary_title=summary_title,
                summary_text=summary_text,
                has_summary=has_summary,
                passed=passed,
                election_date=self._parse_election_date(election_date, year),
                election_type=election_type,
                data_source="Ballotpedia",
                source_url=measure_url
            )

            return measure

        except Exception as e:
            logger.warning(f"Failed to parse measure item: {e}")
            return None

    def _fetch_measure_summary(self, url: str, retry_count: int = 0) -> Optional[Dict[str, str]]:
        """
        Fetch detailed summary information from a measure's Ballotpedia page

        Args:
            url: Full URL to the measure page
            retry_count: Current retry attempt (for rate limiting)

        Returns:
            Dict with ballot_question, summary_title, summary_text, or None if unavailable
        """
        import time

        try:
            response = self.session.get(url, timeout=15)

            # Handle rate limiting (HTTP 202 with empty content)
            if response.status_code == 202 or len(response.content) == 0:
                if retry_count < 3:
                    # Exponential backoff: wait longer each retry
                    wait_time = 10 * (2 ** retry_count)  # 10s, 20s, 40s
                    logger.warning(f"Rate limited (HTTP {response.status_code}), waiting {wait_time}s before retry {retry_count + 1}/3")
                    time.sleep(wait_time)
                    return self._fetch_measure_summary(url, retry_count + 1)
                else:
                    logger.warning(f"Rate limited after 3 retries, skipping URL: {url}")
                    return None

            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')
            result = {}

            # Find the main content area
            content = soup.find('div', class_='mw-parser-output')
            if not content:
                logger.debug(f"No content found for {url}")
                return None

            # Look for "Ballot question" section
            ballot_question_heading = content.find(['h2', 'h3', 'h4'], string=re.compile(r'Ballot question', re.IGNORECASE))
            if ballot_question_heading:
                # Get the paragraph(s) after the heading
                ballot_text = []
                current = ballot_question_heading.find_next_sibling()

                while current and current.name not in ['h1', 'h2', 'h3', 'h4']:
                    if current.name == 'p':
                        text = current.get_text().strip()
                        if text:
                            ballot_text.append(text)
                    current = current.find_next_sibling()

                    # Stop after 2-3 paragraphs to avoid getting too much
                    if len(ballot_text) >= 3:
                        break

                if ballot_text:
                    result['ballot_question'] = ' '.join(ballot_text)

            # Look for "Impartial analysis" section (this is the detailed summary)
            analysis_heading = content.find(['h2', 'h3', 'h4'], string=re.compile(r'Impartial analysis', re.IGNORECASE))
            if analysis_heading:
                analysis_text = []
                current = analysis_heading.find_next_sibling()

                while current and current.name not in ['h1', 'h2', 'h3', 'h4']:
                    if current.name == 'p':
                        text = current.get_text().strip()
                        # Skip meta text like "The following impartial analysis..."
                        if text and not re.match(r'^The following impartial analysis', text, re.IGNORECASE):
                            analysis_text.append(text)
                    elif current.name == 'table':
                        # Extract text from table (often contains the actual analysis)
                        table_text = current.get_text().strip()
                        # Clean up excessive whitespace
                        table_text = re.sub(r'\s+', ' ', table_text)
                        if table_text and len(table_text) > 50:
                            analysis_text.append(table_text)
                    elif current.name == 'ul':
                        # Include bullet points
                        for li in current.find_all('li'):
                            text = li.get_text().strip()
                            if text:
                                analysis_text.append(f"• {text}")
                    current = current.find_next_sibling()

                    # Limit to ~500 words
                    if len(' '.join(analysis_text)) > 2500:
                        break

                if analysis_text:
                    full_summary = ' '.join(analysis_text)
                    result['summary_text'] = full_summary

                    # Create a short summary_title from first sentence
                    first_sentence = re.split(r'[.!?]', full_summary)[0]
                    if len(first_sentence) > 150:
                        first_sentence = first_sentence[:147] + '...'
                    result['summary_title'] = first_sentence.strip()

            # If no impartial analysis, look for opening paragraph as summary
            if not result.get('summary_text'):
                # Find first substantial paragraph before any heading
                first_p = content.find('p')
                if first_p:
                    text = first_p.get_text().strip()
                    if len(text) > 50:  # Must be substantial
                        result['summary_text'] = text
                        # Create title from first part
                        if len(text) > 150:
                            result['summary_title'] = text[:147] + '...'
                        else:
                            result['summary_title'] = text

            return result if result else None

        except Exception as e:
            logger.debug(f"Could not fetch summary from {url}: {e}")
            return None

    def _parse_election_date(self, date_str: str, year: int) -> Optional[datetime]:
        """Parse election date string to datetime"""
        try:
            # Handle formats like "November 4" or "March 5"
            match = re.search(r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d+)', date_str, re.IGNORECASE)
            if match:
                month_name = match.group(1)
                day = int(match.group(2))
                date_str_full = f"{month_name} {day}, {year}"
                return datetime.strptime(date_str_full, "%B %d, %Y")
        except Exception as e:
            logger.debug(f"Could not parse date '{date_str}': {e}")

        return None

    def scrape_all_counties(self) -> List[BallotMeasure]:
        """
        Scrape all 58 California counties

        Returns:
            List of all measures from all counties
        """
        all_measures = []

        for i, county in enumerate(self.CALIFORNIA_COUNTIES, 1):
            logger.info(f"[{i}/{len(self.CALIFORNIA_COUNTIES)}] Processing {county} County...")

            measures = self.scrape_county(county)
            all_measures.extend(measures)

            # Be nice to Ballotpedia servers
            import time
            time.sleep(1)

        logger.info(f"Total measures scraped from all counties: {len(all_measures)}")
        return all_measures
