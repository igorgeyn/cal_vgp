#!/usr/bin/env python3
"""
California Secretary of State Ballot Measures Scraper
"""

import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class CAStateScraper:
    """Scraper for California Secretary of State ballot measures"""
    
    def __init__(self):
        self.base_url = "https://www.sos.ca.gov"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; CA-Gov-Scraper/1.0)'
        })
        
        self.endpoints = {
            'qualified': '/elections/ballot-measures/qualified-ballot-measures',
            'initiative_status': '/elections/ballot-measures/initiative-and-referendum-status',
        }
    
    def scrape_page(self, endpoint_key):
        """Scrape a specific page"""
        url = self.base_url + self.endpoints[endpoint_key]
        
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            return self.extract_measures(soup, endpoint_key)
            
        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            return []
    
    def extract_measures(self, soup, page_type):
        """Extract ballot measures from HTML"""
        measures = []
        
        # Look for content - adjust selectors based on actual page structure
        content = soup.get_text(separator='\n', strip=True)
        
        measures.append({
            'title': f'Content from {page_type} page',
            'description': content[:200] + '...' if len(content) > 200 else content,
            'type': page_type,
            'scraped_at': datetime.now().isoformat(),
            'source_url': self.base_url + self.endpoints[page_type]
        })
        
        return measures
    
    def scrape_all(self):
        """Scrape all configured pages"""
        results = {
            'scraped_at': datetime.now().isoformat(),
            'source': 'California Secretary of State',
            'measures': []
        }
        
        for page_type in self.endpoints:
            page_measures = self.scrape_page(page_type)
            results['measures'].extend(page_measures)
            time.sleep(1)  # Be respectful
        
        return results
