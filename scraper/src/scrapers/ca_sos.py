"""
California Secretary of State ballot measures scraper
"""
import re
import logging
from typing import Dict, List
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
        
        # Scrape each endpoint
        for endpoint_key, endpoint_path in self.config["endpoints"].items():
            logger.info(f"Scraping {endpoint_key} measures...")
            measures = self._scrape_endpoint(endpoint_key, endpoint_path)
            all_measures.extend(measures)
            
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
                measure_text = re.sub(r"\s*\(PDF\)\s*$", "", measure_text, flags=re.I)
                
                if not measure_text:
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
        """Parse individual measure information"""
        # Build the full PDF URL
        pdf_url = urljoin(self.base_url, pdf_href)
        
        # Try to extract year from election info or default to current year
        year = None
        if election_info and election_info.get('date'):
            year_match = re.search(r'(\d{4})', election_info['date'])
            if year_match:
                year = year_match.group(1)
        
        # If no year found, check if it's in the measure text
        if not year:
            year_match = re.search(r'\b(20\d{2})\b', measure_text)
            if year_match:
                year = year_match.group(1)
        
        # Default to 2026 for current measures
        if not year:
            year = "2026"
        
        return {
            'measure_text': measure_text,
            'year': year,
            'pdf_url': pdf_url,
            'election_date': election_info.get('date') if election_info else None,
            'election_type': election_info.get('type') if election_info else None,
        }


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
        
        year_match = re.search(r'\((\d{4})\)', full_text)
        if year_match:
            year = year_match.group(1)
            
        prop_match = re.search(r'Proposition\s+(\d+)', full_text)
        if prop_match:
            prop_num = prop_match.group(1)
        
        # Build measure text
        if prop_num:
            measure_text = f"Proposition {prop_num}: {title}"
        else:
            measure_text = title
            
        return {
            'measure_text': measure_text,
            'year': year or "Unknown",
            'title': title,
            'pdf_url': urljoin(self.base_url, href),
            'source_url': self.base_url + self.config["endpoint"]
        }