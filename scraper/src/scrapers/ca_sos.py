"""
California Secretary of State ballot measures scraper
"""
import re
import logging
from typing import Dict, List, Optional, Tuple
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

        # If title was stripped out by chapter/statutes cleanup, fall back to a readable label
        if title is not None:
            title = re.sub(r'\s+', ' ', title).strip()
        if not title:
            title = measure_id or cleaned_text
        
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
        
        # Extract year (integer or None if unknown)
        year = self._extract_year(election_info, cleaned_text)

        return {
            'measure_id': measure_id,
            'measure_text': cleaned_text,  # Keep cleaned text for reference
            'title': title or "Unknown",
            'year': year,
            'pdf_url': pdf_url,
            'election_date': election_info.get('date') if election_info else None,
            'election_type': election_info.get('type') if election_info else None,
        }
    
    def _extract_year(self, election_info: Dict = None, text: str = "") -> Optional[int]:
        """Extract year from various sources. Returns None if no year found."""
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

        # Convert to integer
        if year:
            try:
                return int(year)
            except (ValueError, TypeError):
                pass

        # Return None instead of defaulting to 2026 — avoids misclassifying
        # historical/undated records as pending upcoming measures
        return None

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

        # Deduplicate by initiative number, keeping the highest-status version
        STATUS_PRIORITY = {
            'qualified': 0, 'eligible': 1, 'pending signature verification': 2,
            'pending verification': 2, 'raw count': 3, 'raw count of signatures': 3,
            '25% of required signatures': 4, '25 percent': 4,
            'cleared for circulation': 5, 'circulating': 5,
            'attorney general': 6, 'failed': 7, 'withdrawn': 8,
        }

        best_by_id = {}
        for m in measures:
            mid = m.get('measure_id', '')
            status_key = m.get('status', '').lower().strip()
            priority = min((v for k, v in STATUS_PRIORITY.items() if k in status_key), default=9)

            if mid not in best_by_id or priority < best_by_id[mid][0]:
                best_by_id[mid] = (priority, m)

        deduped = [v[1] for v in best_by_id.values()]
        logger.info(f"Found {len(deduped)} in-progress initiatives (deduped from {len(measures)})")
        return deduped

    def _scrape_initiative_detail_page(self, url: str, status: str) -> List[Dict]:
        """Scrape individual initiatives from a detail page.

        CA SOS initiative pages use <p>/<strong> blocks, not tables.
        Each initiative is a sequence:
          <p><strong>NUMBER. (AG-ID) TITLE IN CAPS...</strong></p>
          <p>Summary Date: ... | Circulation Deadline ... | Signatures Required: ...</p>
          <a>(PDF link)</a>
          <p>Description text...</p>
          <strong>Fiscal impact...</strong>
          <a>AG-ID link</a>
        """
        html = self._fetch_page(url)
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        measures = []
        seen_nums = set()

        # Strategy: find all <p> and <strong> elements that start with a 4-digit number
        # followed by a period and AG filing number (e.g., "1993. (25-0016)")
        # Each such element starts a new initiative block.
        init_pattern = re.compile(r'^(\d{4})\.\s*\(([^)]+)\)\s*(.+)', re.DOTALL)

        for elem in soup.find_all(['p', 'strong']):
            text = elem.get_text(" ", strip=True)
            match = init_pattern.match(text)
            if not match:
                continue

            initiative_num = match.group(1)
            ag_id = match.group(2).strip()
            raw_title = match.group(3).strip()

            # Skip duplicates (same initiative appears in multiple elements)
            if initiative_num in seen_nums:
                continue
            seen_nums.add(initiative_num)

            # Clean the title — remove metadata that bleeds in
            title = self._clean_initiative_title(raw_title)

            # Look for PDF link in nearby siblings
            pdf_url = None
            next_elem = elem.find_next_sibling()
            for _ in range(5):  # Check up to 5 siblings
                if next_elem is None:
                    break
                pdf_link = next_elem.find('a', href=re.compile(r'\.pdf', re.IGNORECASE))
                if pdf_link:
                    pdf_url = pdf_link.get('href', '')
                    break
                next_elem = next_elem.find_next_sibling()

            # Look for description in the next <p> after metadata
            description = None
            next_elem = elem.find_next_sibling()
            for _ in range(5):
                if next_elem is None:
                    break
                next_text = next_elem.get_text(" ", strip=True)
                # Skip metadata lines and PDF links
                if (not next_text.startswith('Summary Date') and
                    not next_text.startswith('(') and
                    not next_text.startswith('Proponent') and
                    len(next_text) > 30 and
                    not init_pattern.match(next_text)):
                    description = next_text[:500]
                    break
                next_elem = next_elem.find_next_sibling()

            if not self._is_valid_initiative_title(title):
                title = f"Initiative {initiative_num}"

            measures.append({
                'measure_id': f"INIT_{initiative_num}",
                'title': title,
                'description': description,
                'measure_text': title,
                'year': 2026,
                'status': status,
                'in_progress': True,
                'source_url': url,
                'pdf_url': pdf_url,
            })

        # Fall back to table parsing if no block-style content found
        if not measures:
            for table in soup.find_all('table'):
                table_measures = self._parse_initiative_table(table, status, url)
                measures.extend(table_measures)

        return measures

    def _parse_initiative_table(self, table: BeautifulSoup, status: str, url: str) -> List[Dict]:
        """Parse initiatives from a structured status table."""
        measures = []
        rows = table.find_all('tr')
        if not rows:
            return measures

        header_cells = rows[0].find_all(['th', 'td'])
        headers = [cell.get_text(" ", strip=True).lower() for cell in header_cells]
        if not headers:
            return measures

        if not any('initiative' in h or 'title' in h or 'number' in h for h in headers):
            return measures

        id_idx = next((i for i, h in enumerate(headers) if 'initiative' in h or 'number' in h), None)
        title_idx = next((i for i, h in enumerate(headers) if 'title' in h or 'subject' in h), None)

        for row in rows[1:]:
            cells = [cell.get_text(" ", strip=True) for cell in row.find_all('td')]
            if not cells:
                continue

            initiative_num = None
            title = None

            if id_idx is not None and id_idx < len(cells):
                id_match = re.search(r'(\d{4})', cells[id_idx])
                if id_match:
                    initiative_num = id_match.group(1)

            if title_idx is not None and title_idx < len(cells):
                title = self._clean_initiative_title(cells[title_idx])

            if not initiative_num:
                initiative_num, title = self._extract_initiative_from_text(" ".join(cells))

            if not initiative_num:
                continue

            if not self._is_valid_initiative_title(title):
                title = f"Initiative {initiative_num}"

            measures.append({
                'measure_id': f"INIT_{initiative_num}",
                'title': title,
                'measure_text': " | ".join(cells),
                'year': 2026,
                'status': status,
                'in_progress': True,
                'source_url': url
            })

        return measures

    def _extract_initiative_from_text(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        """Extract initiative number and title from free text."""
        if not text:
            return None, None

        cleaned = re.sub(r'\s+', ' ', text).strip()
        if not cleaned:
            return None, None

        lower = cleaned.lower()
        if lower.startswith('please note'):
            return None, None

        match = re.search(r'(?:Initiative\s+#?\s*)?(\d{4})\s*[-–—:]\s*(.+)$', cleaned, re.IGNORECASE)
        if not match:
            match = re.search(r'(?:Initiative\s+#?\s*)?(\d{4})\s+(.+)$', cleaned, re.IGNORECASE)

        if not match:
            return None, None

        initiative_num = match.group(1)
        raw_title = match.group(2)
        title = self._clean_initiative_title(raw_title)

        if not self._is_valid_initiative_title(title):
            return initiative_num, None

        return initiative_num, title

    def _clean_initiative_title(self, title: Optional[str]) -> Optional[str]:
        """Remove status metadata from initiative titles."""
        if not title:
            return None

        cleaned = re.sub(r'\s+', ' ', title).strip()
        # Remove common metadata that bleeds into titles
        for pattern in [
            r'\bSummary Date\b.*', r'\bCirculation Deadline\b.*',
            r'\bSignatures Required\b.*', r'\bFailed\b.*',
            r'\bProponent\(s\)\b.*', r'\(PDF\)\).*',
            r'\bReceive Updates\b.*', r'\bSign up\b.*',
            r'\bOffice:\s*\(\d+\).*', r'\b\d+\w*\s+Street\s+Sacramento\b.*',
            r'\bCalifornia Secretary of State\b.*',
        ]:
            cleaned = re.split(pattern, cleaned, maxsplit=1, flags=re.IGNORECASE)[0].strip()
        cleaned = cleaned.strip(' -|:;.,')
        return cleaned or None

    def _is_valid_initiative_title(self, title: Optional[str]) -> bool:
        """Heuristic filter for placeholder/non-title text."""
        if not title:
            return False
        cleaned = re.sub(r'\s+', ' ', title).strip()
        if len(cleaned) < 6:
            return False
        lower = cleaned.lower()
        if lower.startswith(('please note', 'summary date', 'circulation deadline', 'signatures required')):
            return False
        if re.fullmatch(r'[\(\)\[\]\d\s|:/\.-]+', cleaned):
            return False
        return True

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
    
    def __init__(self, max_items: int = None, max_pages: int = None):
        super().__init__("UC_Law_SF")
        self.config = SOURCES["uc_law_sf"]
        self.base_url = self.config["base_url"]
        self.max_items = max_items or self.config.get("max_items", 50)
        self.max_pages = max_pages or self.config.get("max_pages", 20)
        
    def scrape(self) -> List[Dict]:
        """Scrape historical measures from UC Law SF"""
        url = self.base_url + self.config["endpoint"]
        measures = []
        seen_ids = set()
        pages = 0

        while url:
            html = self._fetch_page(url)
            if not html:
                break

            page_measures, next_url = self._parse_repository_page(html, url)
            for measure in page_measures:
                unique_id = measure.get('pdf_url') or measure.get('source_url') or measure.get('measure_id')
                if unique_id in seen_ids:
                    continue
                seen_ids.add(unique_id)
                measures.append(measure)
                if self.max_items and len(measures) >= self.max_items:
                    return measures

            pages += 1
            if not next_url or (self.max_pages and pages >= self.max_pages):
                break

            url = next_url

        return measures
    
    def _parse_repository_page(self, html: str, source_url: str) -> Tuple[List[Dict], Optional[str]]:
        """Parse measures from repository page, returning measures and next page URL.

        Each measure is a <p class="article-listing"> containing:
          - <a href="/ca_ballot_props/NNN">TITLE TEXT</a>
          - <span class="index_pubinfo"><em>California Proposition N (YYYY)</em></span>
        """
        soup = BeautifulSoup(html, "html.parser")
        measures = []

        for listing in soup.find_all('p', class_='article-listing'):
            if len(measures) >= self.max_items:
                break

            # Find the main link (skip viewcontent/PDF links)
            link = None
            for a in listing.find_all('a', href=True):
                href = a.get('href', '')
                if '/ca_ballot_props/' in href and 'viewcontent' not in href:
                    link = a
                    break

            if not link:
                continue

            href = link.get('href', '')
            title = link.get_text(strip=True)
            if not title:
                continue
            lower_title = title.lower()
            if any(term in lower_title for term in [
                'voter information guide',
                'voter information pamphlet',
                'ballot pamphlet'
            ]):
                continue
            repo_id = self._extract_repository_id(href)

            # Extract prop number and year from the <span class="index_pubinfo"> sibling
            # Note: smallcaps spans break get_text(), so we collapse whitespace
            year = None
            prop_num = None
            measure_id = None

            pubinfo = listing.find('span', class_='index_pubinfo')
            if pubinfo:
                # Collapse all whitespace from the smallcaps markup
                info_text = re.sub(r'\s+', ' ', pubinfo.get_text(' ', strip=True))
                year_match = re.search(r'\((\d{4})\)', info_text)
                if year_match:
                    year = int(year_match.group(1))
                prop_match = re.search(r'P\s*r\s*o\s*p\s*o\s*s\s*i\s*t\s*i\s*o\s*n\s+(\d+[A-Z]?)', info_text, re.IGNORECASE)
                if prop_match:
                    prop_num = prop_match.group(1)
                    measure_id = f"PROP_{prop_num}"

            if not year:
                year = self._extract_year_from_detail_page(href)

            if prop_num:
                measure_text = f"Proposition {prop_num}: {title}"
            else:
                measure_text = title
                if not measure_id and repo_id:
                    measure_id = f"UCLAW_{repo_id}"

            measures.append({
                'measure_id': measure_id,
                'measure_text': measure_text,
                'year': year if year else 0,
                'title': title,
                'pdf_url': urljoin(self.base_url, href),
                'source_url': source_url
            })

            if len(measures) % 10 == 0:
                logger.debug(f"Processed {len(measures)} historical measures...")

        next_url = self._find_next_page(soup, source_url)
        logger.info(f"Found {len(measures)} historical measures")
        return measures, next_url

    def _extract_year_from_detail_page(self, href: str) -> Optional[int]:
        """Fetch a measure detail page to extract year when list metadata is missing."""
        detail_url = urljoin(self.base_url, href)
        html = self._fetch_page(detail_url)
        if not html:
            return None

        soup = BeautifulSoup(html, "html.parser")
        year_block = soup.find('div', id='year')
        if year_block:
            text = year_block.get_text(' ', strip=True)
            match = re.search(r'\b(19\d{2}|20\d{2})\b', text)
            if match:
                return int(match.group(1))

        match = re.search(r'\b(19\d{2}|20\d{2})\b', soup.get_text(' ', strip=True))
        return int(match.group(1)) if match else None

    def _extract_repository_id(self, href: str) -> Optional[str]:
        """Extract the repository item ID from a listing link."""
        match = re.search(r'/ca_ballot_props/(\d+)', href or '')
        return match.group(1) if match else None

    def _find_next_page(self, soup: BeautifulSoup, current_url: str) -> Optional[str]:
        """Find the next page URL from pagination controls."""
        next_link = soup.select_one('a[rel="next"]')
        if not next_link:
            next_link = soup.find('a', class_=re.compile(r'next', re.IGNORECASE))
        if not next_link:
            next_link = soup.find('a', string=re.compile(r'\bnext\b|\bolder\b|›|»', re.IGNORECASE))

        if not next_link:
            return None

        href = next_link.get('href')
        if not href:
            return None

        return urljoin(current_url, href)
