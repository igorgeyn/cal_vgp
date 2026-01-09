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
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to fetch {county} County page: {e}")
            return []

        soup = BeautifulSoup(response.content, 'html.parser')
        measures = []

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

            year = int(year_match.group(1))

            # Get content between this year and the next year heading
            current = year_header.find_next_sibling()

            while current and current.name not in ['h1', 'h2']:
                # Look for election date headers (h3)
                if current.name == 'h3':
                    election_date = current.get_text().strip()

                    # Find the list of measures under this election
                    measures_list = current.find_next_sibling('ul')

                    if measures_list:
                        for li in measures_list.find_all('li', recursive=False):
                            measure = self._parse_measure_item(li, year, election_date, county)
                            if measure:
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

            # Create BallotMeasure object
            measure = BallotMeasure(
                measure_id=measure_id,
                year=year,
                county=county.upper(),
                title=measure_title,
                description=description,
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
