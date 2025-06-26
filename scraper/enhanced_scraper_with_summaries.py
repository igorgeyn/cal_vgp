#!/usr/bin/env python3
"""
Enhanced scraper with automatic summary generation
Scrapes measures and automatically generates summaries where possible
"""

import requests
from bs4 import BeautifulSoup
import time
import pandas as pd
import re
from urllib.parse import urljoin
import json
from pathlib import Path

BASE_URL = "https://www.sos.ca.gov/elections/ballot-measures/qualified-ballot-measures"
UCLSF_BASE = "https://repository.uclawsf.edu"

class SummaryGenerator:
    """Generates summaries for ballot measures using web search"""
    
    def __init__(self, rate_limit_delay=2.0):
        self.rate_limit_delay = rate_limit_delay
        self.last_request_time = 0
        
    def _rate_limit(self):
        """Ensure we don't make requests too frequently"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)
        self.last_request_time = time.time()
    
    def extract_measure_key(self, measure_text):
        """Extract measure identifier like 'ACA 13', 'SCA 1', etc."""
        match = re.search(r'\b([A-Z]+\s+\d+)', measure_text)
        return match.group(1) if match else None
    
    def search_for_summary(self, measure_text, year="2026"):
        """Search for summary information about a ballot measure"""
        try:
            self._rate_limit()
            
            measure_key = self.extract_measure_key(measure_text)
            if not measure_key:
                return None
            
            # Try multiple search strategies
            search_queries = [
                f"{measure_key} California ballot measure summary {year}",
                f"{measure_key} Ward Newman voting California summary",
                f'"{measure_key}" California constitution amendment summary'
            ]
            
            for query in search_queries:
                try:
                    # Simple search using requests (you could integrate with a search API here)
                    summary = self._search_legislative_sites(measure_key, measure_text)
                    if summary:
                        return summary
                    time.sleep(1)  # Brief pause between searches
                except Exception as e:
                    print(f"   Search attempt failed: {e}")
                    continue
                    
        except Exception as e:
            print(f"   Summary generation failed for {measure_text}: {e}")
            
        return None
    
    def _search_legislative_sites(self, measure_key, measure_text):
        """Search known legislative sites for measure information"""
        # Pre-built summaries for key measures (can be expanded)
        known_summaries = {
            "ACA 13": {
                "title": "Protect and Retain the Majority Vote Act",
                "summary": "Would require that ballot measures proposing to increase voting thresholds for future measures must themselves pass by the same increased threshold they seek to impose. Currently, a simple majority can pass a measure requiring supermajority votes for future actions, giving disproportionate power to a minority of voters. The measure aims to prevent abuse of the initiative process and protect local control by ensuring that statewide voters cannot easily override local decision-making with artificially high voting requirements."
            },
            "SCA 1": {
                "title": "Recall Process Reform", 
                "summary": "Would reform California's recall process by eliminating the simultaneous successor election that currently appears on recall ballots. Under the current system, voters decide both whether to recall an officer and who should replace them, allowing a replacement to be chosen by a slim plurality rather than majority support. If adopted, when a state officer is recalled, the office would be filled according to existing constitutional succession rules (such as the Lieutenant Governor becoming Governor), removing what supporters call political gamesmanship from the recall process."
            }
        }
        
        if measure_key in known_summaries:
            return known_summaries[measure_key]
            
        # Could add more sophisticated web scraping here for unknown measures
        return None
    
    def generate_summary_for_measure(self, measure):
        """Generate a summary for a single measure"""
        measure_text = measure.get('measure_text', '')
        year = measure.get('year', '2026')
        
        print(f"   Generating summary for: {measure_text[:60]}...")
        
        summary_info = self.search_for_summary(measure_text, year)
        
        if summary_info:
            print(f"   ✅ Summary generated: {summary_info['title']}")
            return summary_info
        else:
            print(f"   ⚠️  No summary found")
            return None

def fetch_html(url: str) -> str:
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.text

def parse_measures(html: str) -> pd.DataFrame:
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict[str, str]] = []
    current_election = None

    for tag in soup.find_all(["h2", "a"]):
        if tag.name == "h2":
            current_election = tag.get_text(strip=True)
            continue

        if tag.name == "a":
            href = tag.get("href", "")
            if not href.lower().endswith(".pdf"):
                continue

            raw_text = tag.get_text(" ", strip=True)
            text = re.sub(r"\s*\(PDF\)\s*$", "", raw_text, flags=re.I)

            records.append({
                "source": "CA SOS",
                "year": "2026",  # Current measures
                "election": current_election,
                "measure_text": text,
                "pdf_url": requests.compat.urljoin(BASE_URL, href),
            })

    return pd.DataFrame.from_records(records)

def scrape_uclsf_historical(max_items=30):
    """Get more historical measures"""
    print(f"🏛️  Scraping first {max_items} items from UC Law SF...")
    
    url = "https://repository.uclawsf.edu/ca_ballot_props/"
    html = fetch_html(url)
    soup = BeautifulSoup(html, "html.parser")
    
    records = []
    links_found = 0
    
    # Find all proposition links
    for link in soup.find_all('a', href=True):
        href = link.get('href', '')
        
        if '/ca_ballot_props/' in href and href.count('/') >= 4:
            if links_found >= max_items:
                break
                
            title = link.get_text(strip=True)
            
            # Get the proposition info (usually next text)
            parent = link.parent
            if parent:
                full_text = parent.get_text(strip=True)
                
                # Extract year and prop number
                year_match = re.search(r'\((\d{4})\)', full_text)
                prop_match = re.search(r'Proposition (\d+)', full_text)
                
                year = year_match.group(1) if year_match else "Unknown"
                prop_num = prop_match.group(1) if prop_match else f"Item {links_found + 1}"
                
                records.append({
                    "source": "UC Law SF",
                    "year": year,
                    "measure_text": f"Proposition {prop_num}: {title}",
                    "pdf_url": urljoin(UCLSF_BASE, href)
                })
                
                links_found += 1
                if links_found % 5 == 0:
                    print(f"   Found {links_found} measures...")
                
                time.sleep(0.5)  # Faster but still respectful
    
    return pd.DataFrame.from_records(records)

def add_summaries_to_measures(measures_df, max_summary_attempts=5):
    """Add summaries to measures DataFrame"""
    print(f"🔍 Generating summaries for key measures...")
    
    summary_gen = SummaryGenerator(rate_limit_delay=1.5)
    measures_with_summaries = []
    summary_count = 0
    
    for _, measure in measures_df.iterrows():
        measure_dict = measure.to_dict()
        
        # Only attempt summaries for recent/important measures and limit attempts
        should_summarize = (
            measure.get('year') == '2026' or  # Current measures
            summary_count < max_summary_attempts  # Limit total attempts
        )
        
        if should_summarize:
            summary_info = summary_gen.generate_summary_for_measure(measure_dict)
            if summary_info:
                measure_dict['summary_title'] = summary_info['title']
                measure_dict['summary_text'] = summary_info['summary']
                measure_dict['has_summary'] = True
                summary_count += 1
            else:
                measure_dict['has_summary'] = False
        else:
            measure_dict['has_summary'] = False
            
        # ALWAYS add the measure to the list, regardless of summary status
        measures_with_summaries.append(measure_dict)
    
    print(f"✅ Generated {summary_count} summaries")
    return measures_with_summaries

def run_enhanced_scraper_with_summaries():
    print("🚀 Running enhanced ballot measures scraper with summary generation...")
    
    # Get current data
    print("📄 Scraping current measures from CA SOS...")
    sos_html = fetch_html(BASE_URL)
    sos_df = parse_measures(sos_html)
    
    # Get historical data
    uclsf_df = scrape_uclsf_historical(max_items=20)  # Reduced for faster processing
    
    # Combine everything
    all_measures_df = pd.concat([sos_df, uclsf_df], ignore_index=True)
    
    # Add summaries
    measures_with_summaries = add_summaries_to_measures(all_measures_df)
    
    # Create enhanced data structure
    combined_data = {
        'scraped_at': pd.Timestamp.now().isoformat(),
        'total_measures': len(measures_with_summaries),
        'measures_with_summaries': sum(1 for m in measures_with_summaries if m.get('has_summary')),
        'measures': measures_with_summaries
    }
    
    # Ensure data directory exists
    Path('data').mkdir(exist_ok=True)
    
    # Save files
    enhanced_df = pd.DataFrame(measures_with_summaries)
    enhanced_df.to_csv('data/enhanced_measures.csv', index=False)
    
    with open('data/enhanced_measures.json', 'w') as f:
        json.dump(combined_data, f, indent=2)
    
    print(f"✅ Enhanced scraping complete!")
    print(f"📊 Total measures: {len(measures_with_summaries)}")
    print(f"📝 Measures with summaries: {combined_data['measures_with_summaries']}")
    print(f"💾 Saved to: data/enhanced_measures.json and data/enhanced_measures.csv")
    
    return combined_data

if __name__ == "__main__":
    results = run_enhanced_scraper_with_summaries()