"""
Ballotpedia Statewide Scraper
Scrapes California statewide ballot propositions from Ballotpedia
"""
import logging
import re
from typing import List, Dict, Optional
from datetime import datetime
import requests
from bs4 import BeautifulSoup

from ..database.models import BallotMeasure

logger = logging.getLogger(__name__)


class BallotpediaStatewideScraper:
    """Scraper for California statewide propositions on Ballotpedia"""

    # Years to scrape (recent elections)
    YEARS_TO_SCRAPE = [2020, 2021, 2022, 2023, 2024, 2025, 2026]

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })

    def get_year_url(self, year: int) -> str:
        """Generate Ballotpedia URL for a year's propositions"""
        return f"https://ballotpedia.org/California_{year}_ballot_propositions"

    def scrape_year(self, year: int) -> List[BallotMeasure]:
        """
        Scrape all statewide propositions for a specific year

        Args:
            year: Year to scrape (e.g., 2024)

        Returns:
            List of BallotMeasure objects
        """
        url = self.get_year_url(year)
        logger.info(f"Scraping {year} statewide propositions from {url}")

        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to fetch {year} propositions page: {e}")
            return []

        soup = BeautifulSoup(response.content, 'html.parser')
        measures = []

        # Find all tables with propositions
        content = soup.find('div', class_='mw-parser-output')
        if not content:
            logger.warning(f"Could not find main content for {year}")
            return []

        # Find tables containing propositions (class='bptable')
        tables = content.find_all('table', class_='bptable')

        for table in tables:
            # Check if this table has proposition data
            rows = table.find_all('tr')
            for row in rows[1:]:  # Skip header row
                cells = row.find_all('td')
                if len(cells) >= 2:
                    # Second cell (index 1) has proposition number and link
                    prop_cell = cells[1] if len(cells) > 1 else cells[0]
                    link = prop_cell.find('a')

                    if link:
                        prop_text = link.get_text().strip()
                        # Check if it's a proposition (e.g., "Proposition 1", "Prop 1")
                        if re.match(r'(Proposition|Prop\.?)\s+\d+', prop_text, re.IGNORECASE):
                            prop_url = link.get('href', '')
                            if prop_url and not prop_url.startswith('http'):
                                prop_url = f"https://ballotpedia.org{prop_url}"

                            # Extract proposition number
                            prop_match = re.search(r'(Proposition|Prop\.?)\s+(\d+)', prop_text, re.IGNORECASE)
                            prop_number = prop_match.group(2) if prop_match else None

                            # Fetch detailed measure data
                            if prop_url and prop_number:
                                measure = self._scrape_proposition(prop_url, prop_number, year)
                                if measure:
                                    measures.append(measure)

        logger.info(f"Found {len(measures)} propositions for {year}")
        return measures

    def _scrape_proposition(self, url: str, prop_number: str, year: int) -> Optional[BallotMeasure]:
        """
        Scrape detailed information for a single proposition

        Args:
            url: URL to the proposition page
            prop_number: Proposition number (e.g., "36")
            year: Year of the election

        Returns:
            BallotMeasure object or None
        """
        try:
            logger.info(f"  Fetching Proposition {prop_number} details...")
            response = self.session.get(url, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')
            content = soup.find('div', class_='mw-parser-output')
            if not content:
                return None

            # Extract page title (measure title)
            page_title = soup.find('h1', class_='firstHeading')
            title = page_title.get_text().strip() if page_title else f"Proposition {prop_number}"

            # Extract ballot title/summary
            ballot_title = None
            summary_text = None
            ballot_question = None

            # Look for "Ballot title" section
            ballot_title_heading = content.find(['h2', 'h3'], string=re.compile(r'Ballot title', re.IGNORECASE))
            if ballot_title_heading:
                # Get next paragraph or table
                next_elem = ballot_title_heading.find_next_sibling()
                if next_elem:
                    if next_elem.name == 'p':
                        ballot_title = next_elem.get_text().strip()
                    elif next_elem.name == 'table':
                        ballot_title = next_elem.get_text().strip()
                        ballot_title = re.sub(r'\s+', ' ', ballot_title)

            # Look for "Text of measure" section for ballot question
            text_heading = content.find(['h2'], string=re.compile(r'Text of measure', re.IGNORECASE))
            if text_heading:
                current = text_heading.find_next_sibling()
                ballot_texts = []

                # Get a few paragraphs/sections
                count = 0
                while current and current.name not in ['h2'] and count < 3:
                    if current.name == 'p':
                        text = current.get_text().strip()
                        if text and len(text) > 30:
                            ballot_texts.append(text)
                            count += 1
                    elif current.name == 'table':
                        text = current.get_text().strip()
                        text = re.sub(r'\s+', ' ', text)
                        if len(text) > 50:
                            ballot_texts.append(text)
                            count += 1
                    current = current.find_next_sibling()

                if ballot_texts:
                    ballot_question = ' '.join(ballot_texts)

            # Look for petition summary or fiscal impact
            petition_heading = content.find(['h3', 'h4'], string=re.compile(r'Petition summary|Summary|Fiscal impact', re.IGNORECASE))
            if petition_heading:
                current = petition_heading.find_next_sibling()
                summary_parts = []

                count = 0
                while current and current.name not in ['h2', 'h3'] and count < 3:
                    if current.name == 'p':
                        text = current.get_text().strip()
                        if text and len(text) > 30:
                            summary_parts.append(text)
                            count += 1
                    elif current.name == 'table':
                        text = current.get_text().strip()
                        text = re.sub(r'\s+', ' ', text)
                        if len(text) > 50:
                            summary_parts.append(text)
                            count += 1
                    current = current.find_next_sibling()

                if summary_parts:
                    summary_text = ' '.join(summary_parts)

            # Extract election results if available
            yes_votes = None
            no_votes = None
            total_votes = None
            passed = None

            result_heading = content.find(['h2'], string=re.compile(r'Election results', re.IGNORECASE))
            if result_heading:
                # Find the results table
                result_table = result_heading.find_next_sibling('table')
                if result_table:
                    rows = result_table.find_all('tr')
                    for row in rows:
                        cells = row.find_all(['td', 'th'])
                        if len(cells) >= 2:
                            cell_text = cells[0].get_text().strip().lower()
                            if 'yes' in cell_text or 'support' in cell_text:
                                # Extract vote count
                                vote_text = cells[1].get_text().strip()
                                yes_match = re.search(r'([\d,]+)', vote_text)
                                if yes_match:
                                    yes_votes = int(yes_match.group(1).replace(',', ''))
                            elif 'no' in cell_text or 'oppose' in cell_text:
                                vote_text = cells[1].get_text().strip()
                                no_match = re.search(r'([\d,]+)', vote_text)
                                if no_match:
                                    no_votes = int(no_match.group(1).replace(',', ''))

                if yes_votes and no_votes:
                    total_votes = yes_votes + no_votes
                    passed = yes_votes > no_votes

            # Determine election date (try to extract from title or heading)
            election_date = None
            election_type = "General"

            # Check for date in title (e.g., "(March 2024)" or "(November 2024)")
            date_match = re.search(r'\((January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})\)', title, re.IGNORECASE)
            if date_match:
                month_name = date_match.group(1)
                year_in_title = int(date_match.group(2))
                # Assume election on first Tuesday of November or first Tuesday in March
                if month_name == "November":
                    # First Tuesday after first Monday in November
                    election_date = datetime(year_in_title, 11, 5)  # Approximate
                elif month_name == "March":
                    election_date = datetime(year_in_title, 3, 5)  # Super Tuesday
                    election_type = "Primary"

            # Use ballot_title as summary_title if we don't have a separate summary
            summary_title = ballot_title if ballot_title else None
            if not summary_text and ballot_title:
                summary_text = ballot_title

            # Create measure object
            measure = BallotMeasure(
                measure_id=f"PROP_{prop_number}",
                measure_letter=None,
                year=year,
                state="CA",
                county="Statewide",
                jurisdiction=None,
                title=title,
                description=None,
                ballot_question=ballot_question,
                summary_title=summary_title,
                summary_text=summary_text,
                has_summary=bool(summary_title or summary_text or ballot_question),
                yes_votes=yes_votes,
                no_votes=no_votes,
                total_votes=total_votes,
                passed=passed,
                election_date=election_date,
                election_type=election_type,
                data_source="Ballotpedia",
                source_url=url
            )

            return measure

        except Exception as e:
            logger.error(f"Failed to scrape Proposition {prop_number}: {e}")
            return None

    def scrape_all_years(self) -> List[BallotMeasure]:
        """
        Scrape all recent years (2020-2026)

        Returns:
            List of all measures from all years
        """
        all_measures = []

        for year in self.YEARS_TO_SCRAPE:
            logger.info(f"Processing {year}...")
            measures = self.scrape_year(year)
            all_measures.extend(measures)

            # Be nice to Ballotpedia servers
            import time
            time.sleep(2)

        logger.info(f"Total statewide propositions scraped: {len(all_measures)}")
        return all_measures
