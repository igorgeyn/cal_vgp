#!/usr/bin/env python3
"""
Debug script to investigate why summary extraction is failing for most measures
"""
import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.operations import Database
from src.scrapers.ballotpedia_counties import BallotpediaCountyScraper
import requests
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def analyze_page_structure(url: str):
    """Fetch a page and analyze its structure"""
    print(f"\n{'=' * 80}")
    print(f"Analyzing: {url}")
    print('=' * 80)

    try:
        response = requests.get(url, timeout=15, allow_redirects=True)
        response.raise_for_status()

        print(f"  HTTP Status: {response.status_code}")
        print(f"  Final URL: {response.url}")
        print(f"  Content length: {len(response.content)} bytes")

        soup = BeautifulSoup(response.content, 'html.parser')

        # Check page title
        title = soup.find('title')
        if title:
            print(f"  Page title: {title.get_text()}")

        # Check for any divs with 'parser' in class name
        all_divs_with_parser = soup.find_all('div', class_=lambda x: x and 'parser' in x)
        print(f"  Divs with 'parser' in class: {len(all_divs_with_parser)}")

        content = soup.find('div', class_='mw-parser-output')

        if not content:
            print("\n❌ No 'mw-parser-output' div found!")

            # Check if this is a redirect page
            redirect_notice = soup.find('div', class_='redirectMsg')
            if redirect_notice:
                print("  ⚠️  This is a redirect page!")
                print(f"  Redirect text: {redirect_notice.get_text().strip()}")

            # Check if page doesn't exist
            no_article = soup.find('div', class_='noarticletext')
            if no_article:
                print("  ⚠️  Page doesn't exist!")
                print(f"  Message: {no_article.get_text().strip()[:200]}")

            return

        print("\n📋 All headings found on page:")
        headings = content.find_all(['h1', 'h2', 'h3', 'h4'])
        for h in headings[:20]:  # Show first 20
            print(f"  {h.name}: {h.get_text().strip()}")

        print("\n🔍 Looking for summary-related sections:")

        # Check for various possible heading names
        possible_headings = [
            'Ballot question',
            'Impartial analysis',
            'Ballot title',
            'Text of measure',
            'Summary',
            'Petition summary',
            'Fiscal impact',
            'Full text',
            'Path to the ballot'
        ]

        for heading_text in possible_headings:
            import re
            found = content.find(['h2', 'h3', 'h4'], string=re.compile(heading_text, re.IGNORECASE))
            if found:
                print(f"  ✓ Found: '{heading_text}'")
                # Show what comes after
                next_elem = found.find_next_sibling()
                if next_elem:
                    text_preview = next_elem.get_text().strip()[:150]
                    print(f"    Next element ({next_elem.name}): {text_preview}...")
            else:
                print(f"  ✗ Not found: '{heading_text}'")

    except Exception as e:
        print(f"❌ Error fetching page: {e}")


def main():
    """Debug summary extraction failures"""

    print("=" * 80)
    print("DEBUG: Summary Extraction Failures")
    print("=" * 80)

    # Get database connection
    db = Database()
    conn = db.connect()

    # Get a sample of failing measures from different counties
    cursor = conn.execute("""
        SELECT id, measure_id, year, county, title, source_url
        FROM measures
        WHERE data_source = 'Ballotpedia'
          AND year >= 2020
          AND is_active = 1
          AND (has_summary = 0 OR has_summary IS NULL)
          AND source_url IS NOT NULL
          AND source_url != ''
        ORDER BY county, year DESC
        LIMIT 10
    """)

    failing_measures = cursor.fetchall()

    print(f"\n📊 Analyzing {len(failing_measures)} failing measures...\n")

    for measure in failing_measures:
        print(f"\n{'─' * 80}")
        print(f"Measure: {measure['measure_id']} ({measure['year']}) - {measure['county']}")
        print(f"Title: {measure['title']}")

        analyze_page_structure(measure['source_url'])

        # Pause between requests
        import time
        time.sleep(2)

    db.close()

    print("\n" + "=" * 80)
    print("Debug Complete!")
    print("=" * 80)


if __name__ == '__main__':
    main()
