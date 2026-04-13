"""
External link generation for ballot measures.

Generates URLs to authoritative external sources based on measure metadata.
No scraping - just deterministic URL construction.
"""
import re
from typing import Dict, List, Optional
from urllib.parse import quote


def extract_prop_number(measure: Dict) -> Optional[str]:
    """Extract proposition number from measure data."""
    # Check measure_id first
    measure_id = measure.get('measure_id', '') or ''
    if measure_id:
        match = re.search(r'PROP[_\s]*(\d+[A-Z]?)', measure_id, re.IGNORECASE)
        if match:
            return match.group(1)

    # Check measure_letter
    letter = measure.get('measure_letter', '') or ''
    if letter and re.match(r'^\d+[A-Z]?$', letter):
        return letter

    # Try to extract from title
    title = measure.get('title', '') or ''
    patterns = [
        r'Proposition\s+(\d+[A-Z]?)\b',
        r'Prop\.?\s+(\d+[A-Z]?)\b',
    ]
    for pattern in patterns:
        match = re.search(pattern, title, re.IGNORECASE)
        if match:
            return match.group(1)

    return None


def is_statewide(measure: Dict) -> bool:
    """Check if measure is statewide (not county/local)."""
    county = (measure.get('county', '') or '').lower()
    jurisdiction = (measure.get('jurisdiction', '') or '').lower()

    return county in ('statewide', 'california', '') or jurisdiction in ('statewide', 'california', 'state')


def generate_ballotpedia_url(measure: Dict) -> Optional[Dict]:
    """
    Generate Ballotpedia URL for California propositions.

    Pattern: https://ballotpedia.org/California_Proposition_13_(1978)
    """
    if not is_statewide(measure):
        return None

    year = measure.get('year')
    prop_num = extract_prop_number(measure)

    if not year or not prop_num:
        return None

    # Ballotpedia URL pattern
    url = f"https://ballotpedia.org/California_Proposition_{prop_num}_({year})"

    # Confidence based on year - Ballotpedia coverage is better for modern measures
    if year >= 1970:
        confidence = 'high'
    elif year >= 1950:
        confidence = 'medium'
    else:
        confidence = 'low'

    return {
        'source': 'Ballotpedia',
        'url': url,
        'confidence': confidence,
        'icon': 'ballot'
    }


def generate_sos_voter_guide_url(measure: Dict) -> Optional[Dict]:
    """
    Generate CA Secretary of State Voter Information Guide archive URL.

    Pattern: https://vigarchive.sos.ca.gov/1996/
    Note: Archive available from 1996 onwards
    """
    if not is_statewide(measure):
        return None

    year = measure.get('year')
    if not year or year < 1996:
        return None

    # VIG archive URL - links to the year's voter guide
    url = f"https://vigarchive.sos.ca.gov/{year}/"

    return {
        'source': 'CA Voter Guide',
        'url': url,
        'confidence': 'high' if year >= 1996 else 'low',
        'icon': 'government'
    }


def generate_uc_hastings_url(measure: Dict) -> Optional[Dict]:
    """
    Generate UC Hastings California Ballot Propositions Database search URL.

    This is a search URL since direct linking is complex.
    """
    if not is_statewide(measure):
        return None

    year = measure.get('year')
    prop_num = extract_prop_number(measure)

    if not year:
        return None

    # Build search query
    if prop_num:
        query = f"Proposition {prop_num} {year}"
    else:
        title = measure.get('title', '') or measure.get('ballot_question', '')
        if not title:
            return None
        # Use first few words of title
        query = f"{title[:50]} {year}"

    url = f"https://repository.uclawsf.edu/ca_ballot_props/?q={quote(query)}"

    return {
        'source': 'UC Law SF',
        'url': url,
        'confidence': 'medium',
        'icon': 'academic'
    }


def generate_lao_url(measure: Dict) -> Optional[Dict]:
    """
    Generate Legislative Analyst's Office URL for fiscal analysis.

    LAO provides fiscal impact analysis for state propositions.
    Available from ~1996 onwards with good coverage.
    """
    if not is_statewide(measure):
        return None

    year = measure.get('year')
    prop_num = extract_prop_number(measure)

    if not year or year < 1996 or not prop_num:
        return None

    # LAO archive search
    url = f"https://lao.ca.gov/BallotAnalysis?ba={year}"

    return {
        'source': 'LAO Analysis',
        'url': url,
        'confidence': 'high' if year >= 2000 else 'medium',
        'icon': 'analysis'
    }


def generate_wikipedia_search_url(measure: Dict) -> Optional[Dict]:
    """
    Generate Wikipedia search URL for notable propositions.

    Only generates for statewide propositions - search URL, not direct link.
    """
    if not is_statewide(measure):
        return None

    year = measure.get('year')
    prop_num = extract_prop_number(measure)

    if not year or not prop_num:
        return None

    query = f"California Proposition {prop_num} {year}"
    url = f"https://en.wikipedia.org/wiki/Special:Search?search={quote(query)}"

    return {
        'source': 'Wikipedia',
        'url': url,
        'confidence': 'low',  # Just a search, may not have article
        'icon': 'wikipedia'
    }


def is_pending_measure(measure: Dict) -> bool:
    """Check if measure is pending (2026 or future, no vote results)."""
    year = measure.get('year')
    if not year:
        return False
    return year >= 2026 or (measure.get('passed') is None and measure.get('percent_yes') is None)


def generate_sos_pending_measures_url(measure: Dict) -> Optional[Dict]:
    """
    Generate CA Secretary of State pending ballot measures page URL.

    This is the official source for tracking measures that have qualified
    or may qualify for upcoming elections.
    """
    if not is_statewide(measure):
        return None

    year = measure.get('year')
    if not year or year < 2024:
        return None

    # SOS ballot measures tracking page
    url = "https://www.sos.ca.gov/elections/ballot-measures/qualified-ballot-measures"

    return {
        'source': 'CA SOS - Qualified Measures',
        'url': url,
        'confidence': 'high',
        'icon': 'government'
    }


def generate_legislature_url(measure: Dict) -> Optional[Dict]:
    """
    Generate canonical CA Legislature bill URL for legislative measures.

    Supports ACA, SCA, AB, SB bill types. Uses the direct billNavClient URL
    format with correct session year (CA uses 2-year sessions: 2023-2024, 2025-2026).
    """
    if not is_statewide(measure):
        return None

    measure_id = measure.get('measure_id', '') or ''
    title = measure.get('title', '') or ''
    text = f"{measure_id} {title}"

    # Match bill types: ACA, SCA, AB, SB
    bill_patterns = [
        (r'ACA[_\s]*(\d+)', 'ACA'),
        (r'SCA[_\s]*(\d+)', 'SCA'),
        (r'(?:Assembly\s+Bill|AB)[_\s]*(\d+)', 'AB'),
        (r'(?:Senate\s+Bill|SB)[_\s]*(\d+)', 'SB'),
    ]

    for pattern, bill_type in bill_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            bill_num = match.group(1)
            year = measure.get('year')

            # CA Legislature uses 2-year sessions: odd year starts session
            # Session ID format: YYYYYYY0 (e.g., 20232024 for 2023-2024 session)
            if year:
                if year % 2 == 0:
                    session = f"{year - 1}{year}0"
                else:
                    session = f"{year}{year + 1}0"
            else:
                session = "202520260"  # default to current session

            url = f"https://leginfo.legislature.ca.gov/faces/billNavClient.xhtml?bill_id={session}{bill_type}{bill_num}"

            type_labels = {
                'ACA': 'Assembly Constitutional Amendment',
                'SCA': 'Senate Constitutional Amendment',
                'AB': 'Assembly Bill',
                'SB': 'Senate Bill',
            }

            return {
                'source': f'CA Legislature ({type_labels.get(bill_type, bill_type)})',
                'url': url,
                'confidence': 'high',
                'icon': 'government'
            }

    return None


def generate_lao_pending_url(measure: Dict) -> Optional[Dict]:
    """
    Generate LAO ballot analysis page for pending measures.

    LAO publishes fiscal analyses as measures qualify.
    """
    if not is_statewide(measure):
        return None

    year = measure.get('year')
    if not year or year < 2024:
        return None

    # LAO ballot analysis overview page
    url = "https://lao.ca.gov/BallotAnalysis"

    return {
        'source': 'LAO Ballot Analysis',
        'url': url,
        'confidence': 'high',
        'icon': 'analysis'
    }


def generate_sos_eligible_url(measure: Dict) -> Optional[Dict]:
    """
    Generate CA SOS eligible statewide initiative measures page URL.
    """
    if not is_statewide(measure):
        return None

    year = measure.get('year')
    if not year or year < 2025:
        return None

    return {
        'source': 'CA SOS Eligible Measures',
        'url': 'https://www.sos.ca.gov/elections/ballot-measures/initiative-and-referendum-status/eligible-statewide-initiative-measures',
        'confidence': 'high',
        'icon': 'government'
    }


def generate_calaccess_url(measure: Dict) -> Optional[Dict]:
    """
    Generate CAL-ACCESS campaign finance URL for ballot measures.

    Links to the official CA campaign finance tracking for measure committees.
    """
    if not is_statewide(measure):
        return None

    year = measure.get('year')
    if not year or year < 2024:
        return None

    # CAL-ACCESS uses session years (odd years start sessions)
    session = year if year % 2 == 1 else year - 1
    url = f"https://cal-access.sos.ca.gov/Campaign/Measures/list.aspx?session={session}"

    return {
        'source': 'Campaign Finance',
        'url': url,
        'confidence': 'high',
        'icon': 'analysis'
    }


def generate_voter_guide_url(measure: Dict) -> Optional[Dict]:
    """
    Generate official CA Voter Guide URL. Available ~Aug before election.
    """
    if not is_statewide(measure):
        return None

    year = measure.get('year')
    if not year or year < 2025:
        return None

    return {
        'source': 'Official Voter Guide',
        'url': 'https://voterguide.sos.ca.gov/',
        'confidence': 'medium',
        'icon': 'government'
    }


def generate_voters_edge_url(measure: Dict) -> Optional[Dict]:
    """
    Generate Voter's Edge California URL (League of Women Voters + MapLight).
    Nonpartisan voter guide with endorsement data.
    """
    if not is_statewide(measure):
        return None

    year = measure.get('year')
    if not year or year < 2025:
        return None

    return {
        'source': "Voter's Edge CA",
        'url': 'https://votersedge.org/ca',
        'confidence': 'medium',
        'icon': 'ballot'
    }


def generate_ballotpedia_county_url(measure: Dict) -> Optional[Dict]:
    """
    Generate Ballotpedia county ballot measures page URL.

    Pattern: https://ballotpedia.org/Los_Angeles_County,_California_ballot_measures
    Works for all 58 California counties.
    """
    if is_statewide(measure):
        return None

    county = (measure.get('county', '') or '').strip()
    if not county:
        return None

    # Format county name for URL (Title Case, underscores)
    county_title = county.title().replace(' ', '_')
    url = f"https://ballotpedia.org/{county_title}_County,_California_ballot_measures"

    return {
        'source': 'Ballotpedia',
        'url': url,
        'confidence': 'high',
        'icon': 'ballot'
    }


# County registrar of voters websites
COUNTY_REGISTRAR_URLS = {
    'ALAMEDA': 'https://www.acvote.org',
    'CONTRA COSTA': 'https://www.cocovote.us',
    'EL DORADO': 'https://www.edcgov.us/Government/Elections',
    'FRESNO': 'https://www.co.fresno.ca.us/departments/county-clerk-registrar-of-voters',
    'KERN': 'https://elections.kerncounty.com',
    'LOS ANGELES': 'https://lavote.gov',
    'MARIN': 'https://www.marinvotes.org',
    'MERCED': 'https://www.co.merced.ca.us/elections',
    'MONTEREY': 'https://www.montereycountyelections.us',
    'NAPA': 'https://www.countyofnapa.org/152/Elections',
    'ORANGE': 'https://www.ocvote.gov',
    'PLACER': 'https://www.placerelections.com',
    'RIVERSIDE': 'https://www.voteinfo.net',
    'SACRAMENTO': 'https://elections.saccounty.gov',
    'SAN BERNARDINO': 'https://www.sbcountyelections.com',
    'SAN DIEGO': 'https://www.sdvote.com',
    'SAN FRANCISCO': 'https://sfelections.sfgov.org',
    'SAN JOAQUIN': 'https://www.sjcrov.org',
    'SAN LUIS OBISPO': 'https://www.slocounty.ca.gov/Departments/Clerk-Recorder/Elections.htm',
    'SAN MATEO': 'https://www.smcacre.org/elections',
    'SANTA BARBARA': 'https://countyofsb.org/care/elections',
    'SANTA CLARA': 'https://www.sccgov.org/sites/rov',
    'SANTA CRUZ': 'https://www.votescount.us',
    'SHASTA': 'https://www.elections.co.shasta.ca.us',
    'SOLANO': 'https://www.solanocounty.com/depts/rov',
    'SONOMA': 'https://sonomacounty.ca.gov/administrative-support-and-fiscal-services/clerk-recorder-assessor-registrar-of-voters/registrar-of-voters',
    'STANISLAUS': 'https://www.stanvote.com',
    'TULARE': 'https://tularecoelections.org',
    'VENTURA': 'https://recorder.countyofventura.org/elections',
    'YOLO': 'https://www.yoloelections.org',
}


def generate_county_registrar_url(measure: Dict) -> Optional[Dict]:
    """
    Generate county registrar of voters website URL.

    Links to the county election authority where measure details may be found.
    """
    if is_statewide(measure):
        return None

    county = (measure.get('county', '') or '').strip().upper()
    url = COUNTY_REGISTRAR_URLS.get(county)

    if not url:
        return None

    return {
        'source': f'{county.title()} County Elections',
        'url': url,
        'confidence': 'medium',
        'icon': 'government'
    }


def generate_ceda_archive_url(measure: Dict) -> Optional[Dict]:
    """
    Generate CEDA (California Elections Data Archive) URL.

    Links to the CSUS data archive where the source data can be found.
    """
    source = measure.get('data_source', '') or measure.get('source', '')
    if source != 'CEDA':
        return None

    return {
        'source': 'CEDA Data Archive',
        'url': 'https://scholars.csus.edu/esploro/outputs/dataset/California-Elections-Data-Archive-CEDA/99257830890201671',
        'confidence': 'high',
        'icon': 'academic'
    }


def generate_external_links(measure: Dict) -> List[Dict]:
    """
    Generate all applicable external links for a measure.

    Returns a list of link objects, sorted by confidence.
    Uses different generators for pending vs historical measures.
    """
    is_pending = is_pending_measure(measure)

    if is_pending:
        # Pending measures get comprehensive sources
        generators = [
            generate_sos_pending_measures_url,
            generate_sos_eligible_url,
            generate_legislature_url,
            generate_lao_pending_url,
            generate_calaccess_url,
            generate_ballotpedia_url,
            generate_voter_guide_url,
            generate_voters_edge_url,
            generate_ballotpedia_county_url,
            generate_county_registrar_url,
        ]
    elif is_statewide(measure):
        # Statewide historical measures get archival sources
        generators = [
            generate_ballotpedia_url,
            generate_sos_voter_guide_url,
            generate_lao_url,
            generate_uc_hastings_url,
            generate_wikipedia_search_url,
        ]
    else:
        # Local/county measures
        generators = [
            generate_ballotpedia_county_url,
            generate_county_registrar_url,
            generate_ceda_archive_url,
        ]

    links = []
    for generator in generators:
        try:
            link = generator(measure)
            if link:
                links.append(link)
        except Exception:
            # Skip failed generators silently
            pass

    # Sort by confidence: high > medium > low
    confidence_order = {'high': 0, 'medium': 1, 'low': 2}
    links.sort(key=lambda x: confidence_order.get(x.get('confidence', 'low'), 3))

    return links


# Landmark measures that should always have rich external links
LANDMARK_PROPOSITIONS = [
    # Tax/Finance
    {'year': 1978, 'prop': '13', 'name': 'Property Tax Limitation (Jarvis-Gann)'},
    {'year': 1988, 'prop': '98', 'name': 'Education Funding Guarantee'},
    {'year': 2012, 'prop': '30', 'name': 'Tax Increase for Education'},

    # Social Issues
    {'year': 1994, 'prop': '187', 'name': 'Illegal Immigration'},
    {'year': 1996, 'prop': '209', 'name': 'Affirmative Action Ban'},
    {'year': 1996, 'prop': '215', 'name': 'Medical Marijuana'},
    {'year': 2000, 'prop': '22', 'name': 'Marriage Definition'},
    {'year': 2008, 'prop': '8', 'name': 'Same-Sex Marriage Ban'},
    {'year': 2016, 'prop': '64', 'name': 'Recreational Marijuana'},

    # Criminal Justice
    {'year': 1994, 'prop': '184', 'name': 'Three Strikes Law'},
    {'year': 2014, 'prop': '47', 'name': 'Criminal Sentencing Reform'},
    {'year': 2016, 'prop': '57', 'name': 'Parole and Sentencing'},
    {'year': 2024, 'prop': '36', 'name': 'Criminal Sentencing Changes'},

    # Elections/Government
    {'year': 1990, 'prop': '140', 'name': 'Term Limits'},
    {'year': 2010, 'prop': '14', 'name': 'Open Primary'},
    {'year': 2010, 'prop': '20', 'name': 'Redistricting'},
    {'year': 2011, 'prop': '11', 'name': 'Citizens Redistricting Commission'},

    # Labor/Business
    {'year': 2020, 'prop': '22', 'name': 'Gig Worker Classification'},
    {'year': 2024, 'prop': '32', 'name': 'Minimum Wage Increase'},

    # Environment
    {'year': 2006, 'prop': '84', 'name': 'Water Quality and Parks'},
    {'year': 2008, 'prop': '2', 'name': 'Farm Animal Confinement'},

    # Healthcare
    {'year': 2004, 'prop': '71', 'name': 'Stem Cell Research'},
    {'year': 2020, 'prop': '23', 'name': 'Kidney Dialysis Clinics'},
]


def is_landmark_measure(measure: Dict) -> bool:
    """Check if a measure is in the landmark list."""
    year = measure.get('year')
    prop_num = extract_prop_number(measure)

    if not year or not prop_num:
        return False

    for landmark in LANDMARK_PROPOSITIONS:
        if landmark['year'] == year and landmark['prop'] == prop_num:
            return True

    return False


def get_landmark_info(measure: Dict) -> Optional[Dict]:
    """Get landmark information for a measure if it exists."""
    year = measure.get('year')
    prop_num = extract_prop_number(measure)

    if not year or not prop_num:
        return None

    for landmark in LANDMARK_PROPOSITIONS:
        if landmark['year'] == year and landmark['prop'] == prop_num:
            return landmark

    return None
