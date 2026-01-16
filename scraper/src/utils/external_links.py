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
    Generate CA Legislature bill search URL for constitutional amendments.

    ACAs (Assembly Constitutional Amendments) and SCAs (Senate Constitutional
    Amendments) can be looked up on the legislature website.
    """
    if not is_statewide(measure):
        return None

    measure_id = measure.get('measure_id', '') or ''

    # Check if this is a constitutional amendment from the legislature
    aca_match = re.search(r'ACA[_\s]*(\d+)', measure_id, re.IGNORECASE)
    sca_match = re.search(r'SCA[_\s]*(\d+)', measure_id, re.IGNORECASE)

    if aca_match:
        bill_num = aca_match.group(1)
        url = f"https://leginfo.legislature.ca.gov/faces/billSearchClient.xhtml?session_year=2025&house=Both&lawCode=All&keyword=ACA+{bill_num}"
        return {
            'source': 'CA Legislature (ACA)',
            'url': url,
            'confidence': 'medium',
            'icon': 'government'
        }
    elif sca_match:
        bill_num = sca_match.group(1)
        url = f"https://leginfo.legislature.ca.gov/faces/billSearchClient.xhtml?session_year=2025&house=Both&lawCode=All&keyword=SCA+{bill_num}"
        return {
            'source': 'CA Legislature (SCA)',
            'url': url,
            'confidence': 'medium',
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


def generate_external_links(measure: Dict) -> List[Dict]:
    """
    Generate all applicable external links for a measure.

    Returns a list of link objects, sorted by confidence.
    Uses different generators for pending vs historical measures.
    """
    is_pending = is_pending_measure(measure)

    if is_pending:
        # Pending measures get special sources
        generators = [
            generate_sos_pending_measures_url,
            generate_lao_pending_url,
            generate_legislature_url,
            generate_ballotpedia_url,
        ]
    else:
        # Historical measures get archival sources
        generators = [
            generate_ballotpedia_url,
            generate_sos_voter_guide_url,
            generate_lao_url,
            generate_uc_hastings_url,
            generate_wikipedia_search_url,
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
