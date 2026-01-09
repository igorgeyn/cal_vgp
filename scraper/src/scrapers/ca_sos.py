"""
California Secretary of State ballot measures scraper
"""
import re
import logging
from typing import Dict, List, Optional
from urllib.parse import urljoin
from bs4 import BeautifulSoup

from .base import BaseScraper
from ..config import SOURCES

logger = logging.getLogger(__name__)


class CASOSScraper(BaseScraper):
    """Scraper for California Secretary of State ballot measures"""
    
    def __init__(self):
        super().__init__("CA_SOS")
        self.config = SOURCES["ca_sos"]
        self.base_url = self.config["base_url"]
        
    def scrape(self) -> List[Dict]:
        """Scrape all ballot measures from CA SOS"""
        all_measures = []

        # Scrape qualified measures from configured endpoints
        for endpoint_key, endpoint_path in self.config["endpoints"].items():
            logger.info(f"Scraping {endpoint_key} measures...")
            measures = self._scrape_endpoint(endpoint_key, endpoint_path)
            all_measures.extend(measures)

        # Scrape in-progress initiatives from status page
        logger.info("Scraping in-progress initiatives...")
        in_progress = self._scrape_initiative_status()
        all_measures.extend(in_progress)

        # NOTE: Past elections scraper disabled - CA SOS URLs have changed (404s)
        # Historical data is comprehensively covered by CEDA (10,909 measures, 1998-2024)
        # This saves ~60 seconds of failed requests and eliminates log noise
        # If needed in future, re-enable by uncommenting below:
        # logger.info("Scraping past election results...")
        # past_results = self._scrape_past_elections()
        # all_measures.extend(past_results)

        return all_measures
    
    def _scrape_endpoint(self, endpoint_key: str, endpoint_path: str) -> List[Dict]:
        """Scrape a specific endpoint"""
        url = self.base_url + endpoint_path
        html = self._fetch_page(url)
        
        if not html:
            return []
            
        return self._parse_measures_page(html, url, endpoint_key)
    
    def _parse_measures_page(self, html: str, source_url: str, page_type: str) -> List[Dict]:
        """Parse measures from HTML page"""
        soup = BeautifulSoup(html, "html.parser")
        measures = []
        current_election = None
        
        # The CA SOS site structure: election headers are <h2>, measures are links
        for tag in soup.find_all(["h2", "h3", "a"]):
            if tag.name in ["h2", "h3"]:
                # This is an election header
                election_text = tag.get_text(strip=True)
                if election_text:
                    current_election = self._parse_election_info(election_text)
                continue
                
            if tag.name == "a":
                href = tag.get("href", "")
                if not href.lower().endswith(".pdf"):
                    continue
                    
                # This is a measure PDF link
                measure_text = tag.get_text(" ", strip=True)
                
                if not measure_text or measure_text == "(PDF)":
                    continue
                
                # Parse the measure
                measure = self._parse_measure(measure_text, href, current_election)
                if measure:
                    measure['source_url'] = source_url
                    measure['page_type'] = page_type
                    measures.append(measure)
        
        logger.info(f"Found {len(measures)} measures on {page_type} page")
        return measures
    
    def _parse_election_info(self, election_text: str) -> Dict:
        """Parse election information from header text"""
        info = {
            'election_text': election_text,
            'date': None,
            'type': None
        }
        
        # Try to extract date (e.g., "November 5, 2024")
        date_match = re.search(r'(\w+\s+\d{1,2},\s+\d{4})', election_text)
        if date_match:
            info['date'] = date_match.group(1)
            
        # Determine election type
        if 'general' in election_text.lower():
            info['type'] = 'General'
        elif 'primary' in election_text.lower():
            info['type'] = 'Primary'
        elif 'special' in election_text.lower():
            info['type'] = 'Special'
            
        return info
    
    def _parse_measure(self, measure_text: str, pdf_href: str, election_info: Dict = None) -> Dict:
        """Parse individual measure information
        
        Expected formats:
        - "ACA 1 - Protect and Retain the Majority Vote Act (PDF)"
        - "SCA 2 - Recall Process Reform (PDF)"
        - "Proposition 47 - Criminal Sentences Initiative (PDF)"
        - "Assembly Bill 440, Chapter 82, Statutes of 2024 (PDF)"
        """
        # Build the full PDF URL
        pdf_url = urljoin(self.base_url, pdf_href)
        
        # Clean the measure text - remove (PDF) suffix
        cleaned_text = re.sub(r"\s*\(PDF\)\s*$", "", measure_text, flags=re.I).strip()
        
        # Initialize variables
        measure_id = None
        title = None
        
        # Try to parse the measure text format: "MEASURE_ID - TITLE"
        # Handle different types of dashes/hyphens
        patterns = [
            r'^([AS]CA\s+\d+)\s*[-–—]\s*(.+)$',  # ACA/SCA format
            r'^(Prop(?:osition)?\s+\d+[A-Z]?)\s*[-–—]\s*(.+)$',  # Proposition format
            r'^(Measure\s+[A-Z])\s*[-–—]\s*(.+)$',  # Local measure format
            r'^(Assembly\s+Bill\s+\d+|AB\s+\d+)\s*[-–—,]\s*(.+)$',  # Assembly Bill
            r'^(Senate\s+Bill\s+\d+|SB\s+\d+)\s*[-–—,]\s*(.+)$',  # Senate Bill
        ]
        
        matched = False
        for pattern in patterns:
            match = re.match(pattern, cleaned_text, re.IGNORECASE)
            if match:
                measure_id = match.group(1).strip()
                title = match.group(2).strip()
                # Clean up title - remove chapter references if present
                title = re.sub(r',?\s*Chapter\s+\d+,?\s*Statutes\s+of\s+\d+\s*$', '', title, flags=re.I).strip()
                matched = True
                break
        
        if not matched:
            # Special handling for Assembly/Senate Bills without hyphen
            bill_match = re.match(r'^((?:Assembly|Senate)\s+Bill\s+\d+),?\s*(.*)$', cleaned_text, re.IGNORECASE)
            if bill_match:
                measure_id = bill_match.group(1).strip()
                rest = bill_match.group(2).strip()
                # Remove chapter/statutes info to get title
                title = re.sub(r'^Chapter\s+\d+,?\s*Statutes\s+of\s+\d+,?\s*', '', rest, flags=re.I).strip()
                if not title or title == rest:
                    # If no clear title after removing chapter info, use the whole rest
                    title = rest if rest else cleaned_text
                matched = True
        
        if not matched:
            # Fallback: try to extract just the measure ID at the beginning
            id_patterns = [
                r'^([AS]CA\s+\d+)\b',  # ACA 1, SCA 2, etc.
                r'^(Prop(?:osition)?\s+\d+[A-Z]?)\b',  # Proposition 47, Prop 8, etc.
                r'^(Measure\s+[A-Z])\b',  # Measure A, Measure B, etc.
                r'^(Assembly\s+Bill\s+\d+|AB\s+\d+)\b',  # Assembly Bill
                r'^(Senate\s+Bill\s+\d+|SB\s+\d+)\b',  # Senate Bill
            ]
            
            for pattern in id_patterns:
                id_match = re.match(pattern, cleaned_text, re.IGNORECASE)
                if id_match:
                    measure_id = id_match.group(1).strip()
                    # Get the rest as title
                    rest = cleaned_text[len(measure_id):].strip()
                    # Remove leading punctuation/separators
                    title = re.sub(r'^[-–—:,\s]+', '', rest).strip()
                    if not title:
                        title = cleaned_text
                    break
            
            if not measure_id:
                # Last resort: use the whole cleaned text as title
                title = cleaned_text
                logger.debug(f"Could not parse measure format: {cleaned_text}")
        
        # Normalize measure_id format
        if measure_id:
            # Ensure consistent spacing (e.g., "ACA1" -> "ACA 1")
            measure_id = re.sub(r'([A-Z]+)(\d+)', r'\1 \2', measure_id)
            # Normalize "Proposition" to "Prop"
            measure_id = re.sub(r'^Proposition\s+', 'Prop ', measure_id, flags=re.IGNORECASE)
            # Normalize "Assembly Bill" to "AB"
            measure_id = re.sub(r'^Assembly\s+Bill\s+', 'AB ', measure_id, flags=re.IGNORECASE)
            # Normalize "Senate Bill" to "SB"
            measure_id = re.sub(r'^Senate\s+Bill\s+', 'SB ', measure_id, flags=re.IGNORECASE)
            # Uppercase the measure ID
            measure_id = measure_id.upper()
        
        # Extract year (AS INTEGER)
        year = self._extract_year(election_info, cleaned_text)
        
        return {
            'measure_id': measure_id,
            'measure_text': cleaned_text,  # Keep cleaned text for reference
            'title': title or "Unknown",
            'year': year,  # This is now guaranteed to be an integer
            'pdf_url': pdf_url,
            'election_date': election_info.get('date') if election_info else None,
            'election_type': election_info.get('type') if election_info else None,
        }
    
    def _extract_year(self, election_info: Dict = None, text: str = "") -> int:
        """Extract year from various sources - ALWAYS RETURNS INTEGER"""
        year = None
        
        # Try to extract from election info first
        if election_info and election_info.get('date'):
            year_match = re.search(r'(\d{4})', election_info['date'])
            if year_match:
                year = year_match.group(1)
        
        # If no year found, check if it's in the text
        if not year and text:
            year_match = re.search(r'\b(20\d{2})\b', text)
            if year_match:
                year = year_match.group(1)
        
        # Convert to integer and return with default
        if year:
            try:
                return int(year)
            except (ValueError, TypeError):
                pass
        
        # Default to 2026 as integer
        return 2026

    def _scrape_initiative_status(self) -> List[Dict]:
        """Scrape in-progress initiatives from the initiative status page"""
        url = self.base_url + "/elections/ballot-measures/initiative-and-referendum-status"
        html = self._fetch_page(url)

        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        measures = []

        # Find the status table
        table = soup.find('table')
        if not table:
            logger.warning("No initiative status table found")
            return []

        # Parse table rows - skip header row
        rows = table.find_all('tr')[1:]  # Skip header

        for row in rows:
            cells = row.find_all('td')
            if len(cells) < 2:
                continue

            status_text = cells[0].get_text(strip=True)
            count_text = cells[1].get_text(strip=True)

            # Extract count from parentheses
            count_match = re.search(r'\((\d+)\)', count_text)
            if not count_match:
                continue

            count = int(count_match.group(1))
            if count == 0:
                continue

            # Find links in the status cell
            links = cells[0].find_all('a')
            if links:
                # If there's a link to a detail page, follow it
                for link in links:
                    href = link.get('href', '')
                    if href:
                        detail_url = urljoin(self.base_url, href)
                        detail_measures = self._scrape_initiative_detail_page(detail_url, status_text)
                        measures.extend(detail_measures)
            else:
                # No detail link, create placeholder entry
                measures.append({
                    'measure_id': f"IN_PROGRESS_{status_text.replace(' ', '_').upper()}",
                    'title': status_text,
                    'measure_text': f"{count} initiatives in status: {status_text}",
                    'year': 2026,
                    'status': status_text,
                    'in_progress': True,
                    'count': count,
                    'source_url': url
                })

        logger.info(f"Found {len(measures)} in-progress initiatives")
        return measures

    def _scrape_initiative_detail_page(self, url: str, status: str) -> List[Dict]:
        """Scrape individual initiatives from a detail page"""
        html = self._fetch_page(url)
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        measures = []

        # Look for initiative listings
        # CA SOS typically lists initiatives with their number and title
        for elem in soup.find_all(['div', 'p', 'li']):
            text = elem.get_text(strip=True)

            # Look for initiative numbers (e.g., "1234", "Initiative #1234")
            initiative_match = re.search(r'(?:Initiative\s+#?)?(\d{4})', text, re.IGNORECASE)
            if initiative_match:
                initiative_num = initiative_match.group(1)

                # Extract title (text after the number)
                title_match = re.search(r'\d{4}[:\s.-]+(.+?)(?:\.|$)', text)
                title = title_match.group(1) if title_match else text[:100]

                measures.append({
                    'measure_id': f"INIT_{initiative_num}",
                    'title': title,
                    'measure_text': text,
                    'year': 2026,
                    'status': status,
                    'in_progress': True,
                    'source_url': url
                })

        return measures

    def _scrape_past_elections(self) -> List[Dict]:
        """Scrape past election results from CA SOS archives"""
        measures = []

        # Target recent elections: 2024, 2022, 2020, 2018, 2016
        election_years = [2024, 2022, 2020, 2018, 2016]

        for year in election_years:
            logger.info(f"Scraping {year} election results...")

            # Try multiple URL patterns CA SOS might use
            url_patterns = [
                f"{self.base_url}/elections/{year}",
                f"{self.base_url}/elections/prior-elections/{year}",
                f"{self.base_url}/elections/{year}-elections",
                f"{self.base_url}/elections/ballot-measures/{year}",
            ]

            for url in url_patterns:
                html = self._fetch_page(url)
                if html:
                    year_measures = self._parse_election_results_page(html, url, year)
                    if year_measures:
                        measures.extend(year_measures)
                        break  # Found results for this year, move to next

        logger.info(f"Found {len(measures)} measures from past elections")
        return measures

    def _parse_election_results_page(self, html: str, source_url: str, year: int) -> List[Dict]:
        """Parse election results from a historical election page"""
        soup = BeautifulSoup(html, "html.parser")
        measures = []

        # Look for proposition/measure links
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            text = link.get_text(strip=True)

            # Look for proposition patterns
            if any(keyword in text.lower() for keyword in ['proposition', 'measure', 'prop']):
                # Try to extract proposition number
                prop_match = re.search(r'(?:Proposition|Prop|Measure)\s+(\d+[A-Z]?)', text, re.IGNORECASE)
                if prop_match:
                    prop_num = prop_match.group(1)
                    measure_id = f"PROP_{prop_num}_{year}"

                    # Try to get PDF URL if available
                    pdf_url = urljoin(self.base_url, href) if '.pdf' in href.lower() else None

                    measures.append({
                        'measure_id': measure_id,
                        'title': text,
                        'measure_text': text,
                        'year': year,
                        'pdf_url': pdf_url,
                        'source_url': source_url,
                        'historical': True
                    })

        return measures


class UCLawSFScraper(BaseScraper):
    """Scraper for UC Law SF historical ballot measures"""
    
    def __init__(self, max_items: int = None):
        super().__init__("UC_Law_SF")
        self.config = SOURCES["uc_law_sf"]
        self.base_url = self.config["base_url"]
        self.max_items = max_items or self.config.get("max_items", 50)
        
    def scrape(self) -> List[Dict]:
        """Scrape historical measures from UC Law SF"""
        url = self.base_url + self.config["endpoint"]
        html = self._fetch_page(url)
        
        if not html:
            return []
            
        return self._parse_repository_page(html)
    
    def _parse_repository_page(self, html: str) -> List[Dict]:
        """Parse measures from repository page"""
        soup = BeautifulSoup(html, "html.parser")
        measures = []
        
        # Find all proposition links
        links_found = 0
        for link in soup.find_all('a', href=True):
            if links_found >= self.max_items:
                break
                
            href = link.get('href', '')
            
            # Look for ballot proposition links
            if '/ca_ballot_props/' in href and href.count('/') >= 4:
                title = link.get_text(strip=True)
                if not title:
                    continue
                    
                # Parse the measure
                measure = self._parse_historical_measure(link, href)
                if measure:
                    measures.append(measure)
                    links_found += 1
                    
                    if links_found % 10 == 0:
                        logger.debug(f"Processed {links_found} historical measures...")
        
        logger.info(f"Found {len(measures)} historical measures")
        return measures
    
    def _parse_historical_measure(self, link_element, href: str) -> Dict:
        """Parse a historical measure from repository"""
        title = link_element.get_text(strip=True)
        
        # Try to get more context from parent element
        parent = link_element.parent
        full_text = parent.get_text(strip=True) if parent else title
        
        # Extract year and proposition number
        year = None
        prop_num = None
        measure_id = None
        
        year_match = re.search(r'\((\d{4})\)', full_text)
        if year_match:
            year = int(year_match.group(1))  # Convert to int immediately
        
        prop_match = re.search(r'Proposition\s+(\d+[A-Z]?)', full_text, re.IGNORECASE)
        if prop_match:
            prop_num = prop_match.group(1)
            measure_id = f"PROP {prop_num}"  # Standardize to uppercase PROP
        
        # Build measure text
        if prop_num:
            measure_text = f"Proposition {prop_num}: {title}"
        else:
            measure_text = title
            
        return {
            'measure_id': measure_id,
            'measure_text': measure_text,
            'year': year if year else 0,  # Return integer, 0 if unknown
            'title': title,
            'pdf_url': urljoin(self.base_url, href),
            'source_url': self.base_url + self.config["endpoint"]
        }