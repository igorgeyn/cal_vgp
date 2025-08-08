"""
Base scraper class with common functionality
"""
import requests
import time
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path

from ..config import SCRAPING_CONFIG, RAW_DATA_DIR

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """Base class for all scrapers with common functionality"""
    
    def __init__(self, source_name: str):
        self.source_name = source_name
        self.session = self._create_session()
        self.last_request_time = 0
        self.results = []
        
    def _create_session(self) -> requests.Session:
        """Create a configured requests session"""
        session = requests.Session()
        session.headers.update({
            'User-Agent': SCRAPING_CONFIG['user_agent']
        })
        return session
    
    def _rate_limit(self):
        """Ensure we don't make requests too frequently"""
        elapsed = time.time() - self.last_request_time
        wait_time = SCRAPING_CONFIG['rate_limit'] - elapsed
        
        if wait_time > 0:
            logger.debug(f"Rate limiting: waiting {wait_time:.2f}s")
            time.sleep(wait_time)
            
        self.last_request_time = time.time()
    
    def _fetch_page(self, url: str, **kwargs) -> Optional[str]:
        """Fetch a page with retries and error handling"""
        max_retries = SCRAPING_CONFIG['max_retries']
        timeout = SCRAPING_CONFIG['timeout']
        
        for attempt in range(max_retries):
            try:
                self._rate_limit()
                
                logger.info(f"Fetching: {url} (attempt {attempt + 1}/{max_retries})")
                response = self.session.get(url, timeout=timeout, **kwargs)
                response.raise_for_status()
                
                return response.text
                
            except requests.exceptions.RequestException as e:
                logger.warning(f"Request failed: {e}")
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.info(f"Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Failed to fetch {url} after {max_retries} attempts")
                    return None
    
    def _save_raw_data(self, data: Dict, filename: str = None):
        """Save raw scraped data"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{self.source_name}_{timestamp}.json"
        
        filepath = RAW_DATA_DIR / filename
        
        import json
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        
        logger.info(f"Saved raw data to: {filepath}")
        return filepath
    
    def _extract_measure_id(self, text: str) -> Optional[str]:
        """Extract standardized measure identifier from text"""
        if not text:
            return None
            
        # Patterns to match various measure formats
        patterns = [
            # State propositions
            (r'(?:Proposition|Prop\.?)\s*(\d+[A-Z]?)', 'PROP_{}'),
            # Constitutional amendments
            (r'([AS]CA)\s*(\d+)', '{}_{}'),
            # Bills
            (r'(AB|SB)\s*(\d+)', '{}_{}'),
            # Local measures
            (r'(?:Measure)\s*([A-Z]+)', 'MEASURE_{}'),
        ]
        
        import re
        for pattern, format_str in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                groups = match.groups()
                return format_str.format(*groups).upper()
        
        return None
    
    def _standardize_measure(self, raw_measure: Dict) -> Dict:
        """Standardize measure data to common format"""
        # Extract measure ID
        measure_text = raw_measure.get('measure_text', '')
        measure_id = self._extract_measure_id(measure_text)
        
        # Standard format
        return {
            'source': self.source_name,
            'measure_id': measure_id,
            'year': raw_measure.get('year'),
            'title': raw_measure.get('title') or measure_text,
            'measure_text': measure_text,
            'description': raw_measure.get('description'),
            'pdf_url': raw_measure.get('pdf_url'),
            'source_url': raw_measure.get('source_url'),
            'election_date': raw_measure.get('election_date'),
            'election_type': raw_measure.get('election_type'),
            'scraped_at': datetime.now().isoformat(),
            'raw_data': raw_measure  # Keep original data
        }
    
    @abstractmethod
    def scrape(self) -> List[Dict]:
        """Main scraping method to be implemented by each scraper"""
        pass
    
    def run(self, save_raw: bool = True) -> Dict:
        """Run the scraper and return results"""
        logger.info(f"Starting {self.source_name} scraper")
        start_time = time.time()
        
        try:
            # Run the scraper
            raw_measures = self.scrape()
            
            # Standardize the results
            standardized_measures = [
                self._standardize_measure(m) for m in raw_measures
            ]
            
            # Prepare results
            results = {
                'source': self.source_name,
                'scraped_at': datetime.now().isoformat(),
                'duration_seconds': time.time() - start_time,
                'total_measures': len(standardized_measures),
                'measures': standardized_measures
            }
            
            # Save raw data if requested
            if save_raw:
                self._save_raw_data(results)
            
            logger.info(f"Completed {self.source_name} scraper: {len(standardized_measures)} measures found")
            return results
            
        except Exception as e:
            logger.error(f"Error in {self.source_name} scraper: {e}")
            raise