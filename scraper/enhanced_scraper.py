#!/usr/bin/env python3
"""
Enhanced scraper - gets more measures and organizes by year
"""

import requests
from bs4 import BeautifulSoup
import time
import pandas as pd
import re
from urllib.parse import urljoin

BASE_URL = "https://www.sos.ca.gov/elections/ballot-measures/qualified-ballot-measures"
UCLSF_BASE = "https://repository.uclawsf.edu"

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

def run_enhanced_scraper():
    print("🚀 Running enhanced ballot measures scraper...")
    
    # Get current data
    sos_html = fetch_html(BASE_URL)
    sos_df = parse_measures(sos_html)
    
    # Get historical data
    uclsf_df = scrape_uclsf_historical(max_items=30)
    
    # Combine everything
    all_measures = pd.concat([sos_df, uclsf_df], ignore_index=True)
    
    combined_data = {
        'scraped_at': pd.Timestamp.now().isoformat(),
        'total_measures': len(all_measures),
        'measures': all_measures.to_dict('records')
    }
    
    # Save files
    all_measures.to_csv('data/all_measures.csv', index=False)
    
    import json
    with open('data/all_measures.json', 'w') as f:
        json.dump(combined_data, f, indent=2)
    
    print(f"✅ Found {len(all_measures)} total measures")
    return combined_data

if __name__ == "__main__":
    results = run_enhanced_scraper()