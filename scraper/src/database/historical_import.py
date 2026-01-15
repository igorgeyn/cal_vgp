"""
Import script for California historical ballot measures
Handles cleaning and transformation from ballot_measures_combined.csv
"""
import csv
import re
import sqlite3
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

from .historical_schema import HISTORICAL_SCHEMA, TOPIC_CONFIG

logger = logging.getLogger(__name__)


def clean_percentage(value: Any) -> Optional[float]:
    """
    Clean percentage values that may contain % signs or other formatting.

    Examples:
        "57.1%" -> 57.1
        "57.1" -> 57.1
        "N/A" -> None
        "" -> None
    """
    if value is None:
        return None

    value_str = str(value).strip()
    if not value_str or value_str.lower() in ('n/a', 'na', 'null', ''):
        return None

    # Remove % sign and any whitespace
    cleaned = value_str.replace('%', '').strip()

    try:
        return float(cleaned)
    except ValueError:
        logger.warning(f"Could not parse percentage value: {value}")
        return None


def derive_marriage_flag(description: str) -> bool:
    """
    Derive same-sex marriage flag from ballot description text.

    Matches measures about:
    - Same-sex marriage
    - Civil unions
    - Domestic partnerships
    - Gay marriage
    """
    if not description:
        return False

    desc_lower = description.lower()

    # Must match marriage-related terms
    marriage_terms = ['marriage', 'civil union', 'domestic partner']
    has_marriage_term = any(term in desc_lower for term in marriage_terms)

    if not has_marriage_term:
        return False

    # AND must match LGBT-related terms
    lgbt_terms = ['same-sex', 'same sex', 'gay', 'homosexual', 'lesbian']
    has_lgbt_term = any(term in desc_lower for term in lgbt_terms)

    return has_lgbt_term


def parse_bool(value: Any) -> Optional[bool]:
    """Parse various boolean representations."""
    if value is None:
        return None

    if isinstance(value, bool):
        return value

    value_str = str(value).strip().lower()

    if value_str in ('1', 'true', 'yes', 'y', 't'):
        return True
    elif value_str in ('0', 'false', 'no', 'n', 'f'):
        return False

    return None


def compute_margin(pct_yes: Optional[float]) -> Optional[float]:
    """Compute margin from 50% threshold."""
    if pct_yes is None:
        return None
    return pct_yes - 50.0


def import_from_csv(
    csv_path: Path,
    db_path: Path,
    state_filter: str = 'CA'
) -> Dict[str, int]:
    """
    Import ballot measures from combined CSV into database.

    Args:
        csv_path: Path to ballot_measures_combined.csv
        db_path: Path to SQLite database
        state_filter: State to filter (default 'CA')

    Returns:
        Dict with import statistics
    """
    stats = {
        'total_rows': 0,
        'filtered_rows': 0,
        'imported': 0,
        'skipped_no_year': 0,
        'skipped_no_votes': 0,
        'errors': 0,
        'topics': {topic: 0 for topic in TOPIC_CONFIG.keys()}
    }

    # Initialize database
    conn = sqlite3.connect(db_path)
    conn.executescript(HISTORICAL_SCHEMA)
    conn.commit()

    # Column mapping from CSV to our schema
    # Based on spec: st, year, ballotname, ballotdescrip, pctyesvotes, passed, type, electiontype
    # Topic flags: drug, gambling_lottery, abort, tax_rev, ed_prek12, ed_higher, health, elections, criminal, environ

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        for row in reader:
            stats['total_rows'] += 1

            # Filter to state
            state = row.get('st', '').strip().upper()
            if state != state_filter:
                continue

            stats['filtered_rows'] += 1

            # Skip if no year
            year_str = row.get('year', '')
            try:
                year = int(year_str)
            except (ValueError, TypeError):
                stats['skipped_no_year'] += 1
                continue

            # Parse vote percentage
            pct_yes = clean_percentage(row.get('pctyesvotes'))
            if pct_yes is None:
                stats['skipped_no_votes'] += 1
                # Still import, just without vote data

            # Parse passed flag
            passed = parse_bool(row.get('passed'))

            # Get description for derived fields
            description = row.get('ballotdescrip', '') or ''

            # Compute topic flags
            is_marijuana = parse_bool(row.get('drug')) or False
            is_gambling = parse_bool(row.get('gambling_lottery')) or False
            is_abortion = parse_bool(row.get('abort')) or False
            is_marriage = derive_marriage_flag(description)
            is_tax = parse_bool(row.get('tax_rev')) or False
            is_education = (parse_bool(row.get('ed_prek12')) or
                          parse_bool(row.get('ed_higher')) or False)
            is_health = parse_bool(row.get('health')) or False
            is_elections = parse_bool(row.get('elections')) or False
            is_criminal = parse_bool(row.get('criminal')) or False
            is_environment = parse_bool(row.get('environ')) or False

            # Track topic counts
            if is_marijuana: stats['topics']['marijuana'] += 1
            if is_gambling: stats['topics']['gambling'] += 1
            if is_abortion: stats['topics']['abortion'] += 1
            if is_marriage: stats['topics']['marriage'] += 1
            if is_tax: stats['topics']['tax'] += 1
            if is_education: stats['topics']['education'] += 1
            if is_health: stats['topics']['health'] += 1
            if is_elections: stats['topics']['elections'] += 1
            if is_criminal: stats['topics']['criminal'] += 1
            if is_environment: stats['topics']['environment'] += 1

            # Compute derived fields
            margin = compute_margin(pct_yes)
            is_close = abs(margin) < 10 if margin is not None else None
            is_very_close = abs(margin) < 5 if margin is not None else None

            measure_type = row.get('type', '') or ''
            is_initiative = 'initiative' in measure_type.lower()
            is_referendum = 'referendum' in measure_type.lower()

            # Insert record
            try:
                conn.execute("""
                    INSERT INTO ca_historical_measures (
                        ballot_name, year, description, pct_yes, passed,
                        measure_type, election_type,
                        is_marijuana, is_gambling, is_abortion, is_marriage,
                        is_tax, is_education, is_health, is_elections,
                        is_criminal, is_environment,
                        margin, is_close, is_very_close,
                        is_initiative, is_referendum,
                        source_dataset
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    row.get('ballotname', ''),
                    year,
                    description,
                    pct_yes,
                    passed,
                    measure_type,
                    row.get('electiontype', ''),
                    is_marijuana,
                    is_gambling,
                    is_abortion,
                    is_marriage,
                    is_tax,
                    is_education,
                    is_health,
                    is_elections,
                    is_criminal,
                    is_environment,
                    margin,
                    is_close,
                    is_very_close,
                    is_initiative,
                    is_referendum,
                    'NCSL_Ballotpedia'
                ))
                stats['imported'] += 1

            except Exception as e:
                logger.error(f"Error importing row {stats['total_rows']}: {e}")
                stats['errors'] += 1

    conn.commit()

    # Update FTS index
    try:
        conn.execute("""
            INSERT INTO ca_historical_search(ca_historical_search)
            VALUES('rebuild')
        """)
        conn.commit()
    except Exception as e:
        logger.warning(f"Could not rebuild FTS index: {e}")

    conn.close()

    logger.info(f"Import complete: {stats['imported']} measures imported")
    logger.info(f"Topic breakdown: {stats['topics']}")

    return stats


def generate_mock_data(db_path: Path) -> Dict[str, int]:
    """
    Generate realistic mock data for testing when CSV is unavailable.
    Based on actual California ballot measure history.
    """
    # Real California ballot measure data (simplified)
    mock_measures = [
        # Marijuana measures
        {'ballot_name': 'Prop 19', 'year': 1972, 'description': 'Decriminalization of marijuana for personal use', 'pct_yes': 33.5, 'passed': False, 'is_marijuana': True},
        {'ballot_name': 'Prop 215', 'year': 1996, 'description': 'Medical marijuana legalization - Compassionate Use Act', 'pct_yes': 55.6, 'passed': True, 'is_marijuana': True, 'is_health': True},
        {'ballot_name': 'Prop 19', 'year': 2010, 'description': 'Regulate, Control and Tax Cannabis Act', 'pct_yes': 46.5, 'passed': False, 'is_marijuana': True, 'is_tax': True},
        {'ballot_name': 'Prop 64', 'year': 2016, 'description': 'Adult Use of Marijuana Act - recreational legalization', 'pct_yes': 57.1, 'passed': True, 'is_marijuana': True, 'is_tax': True},

        # Gambling measures
        {'ballot_name': 'Prop 37', 'year': 1984, 'description': 'California State Lottery Act', 'pct_yes': 58.0, 'passed': True, 'is_gambling': True},
        {'ballot_name': 'Prop 1A', 'year': 2000, 'description': 'Indian gaming compacts expansion', 'pct_yes': 64.5, 'passed': True, 'is_gambling': True},
        {'ballot_name': 'Prop 68', 'year': 2004, 'description': 'Non-tribal gaming expansion', 'pct_yes': 16.1, 'passed': False, 'is_gambling': True},
        {'ballot_name': 'Prop 27', 'year': 2022, 'description': 'Online sports betting legalization', 'pct_yes': 16.6, 'passed': False, 'is_gambling': True, 'is_tax': True},
        {'ballot_name': 'Prop 26', 'year': 2022, 'description': 'In-person sports betting at racetracks and tribal casinos', 'pct_yes': 33.7, 'passed': False, 'is_gambling': True},

        # Abortion measures
        {'ballot_name': 'Prop 1', 'year': 2022, 'description': 'Constitutional right to reproductive freedom including abortion', 'pct_yes': 66.9, 'passed': True, 'is_abortion': True, 'is_health': True},
        {'ballot_name': 'Prop 4', 'year': 2008, 'description': 'Parental notification for abortion - minors', 'pct_yes': 47.8, 'passed': False, 'is_abortion': True},
        {'ballot_name': 'Prop 85', 'year': 2006, 'description': 'Parental notification before termination of pregnancy', 'pct_yes': 45.5, 'passed': False, 'is_abortion': True},
        {'ballot_name': 'Prop 73', 'year': 2005, 'description': 'Waiting period and parental notification for abortion', 'pct_yes': 47.1, 'passed': False, 'is_abortion': True},

        # Marriage measures
        {'ballot_name': 'Prop 22', 'year': 2000, 'description': 'Limit on marriages - only between man and woman', 'pct_yes': 61.4, 'passed': True, 'is_marriage': True},
        {'ballot_name': 'Prop 8', 'year': 2008, 'description': 'Eliminates right of same-sex couples to marry', 'pct_yes': 52.2, 'passed': True, 'is_marriage': True},

        # Tax measures
        {'ballot_name': 'Prop 13', 'year': 1978, 'description': 'Property tax limitation initiative', 'pct_yes': 64.8, 'passed': True, 'is_tax': True},
        {'ballot_name': 'Prop 30', 'year': 2012, 'description': 'Temporary taxes to fund education', 'pct_yes': 55.4, 'passed': True, 'is_tax': True, 'is_education': True},
        {'ballot_name': 'Prop 55', 'year': 2016, 'description': 'Extension of Prop 30 income tax increases', 'pct_yes': 63.3, 'passed': True, 'is_tax': True, 'is_education': True},
        {'ballot_name': 'Prop 15', 'year': 2020, 'description': 'Split roll property tax for commercial properties', 'pct_yes': 48.0, 'passed': False, 'is_tax': True, 'is_education': True},

        # Education measures
        {'ballot_name': 'Prop 98', 'year': 1988, 'description': 'Minimum school funding guarantee', 'pct_yes': 50.7, 'passed': True, 'is_education': True},
        {'ballot_name': 'Prop 227', 'year': 1998, 'description': 'English in public schools (end bilingual education)', 'pct_yes': 60.9, 'passed': True, 'is_education': True},
        {'ballot_name': 'Prop 58', 'year': 2016, 'description': 'Multilingual education repeal of Prop 227', 'pct_yes': 73.5, 'passed': True, 'is_education': True},

        # Healthcare measures
        {'ballot_name': 'Prop 45', 'year': 2014, 'description': 'Health insurance rate regulation', 'pct_yes': 40.8, 'passed': False, 'is_health': True},
        {'ballot_name': 'Prop 61', 'year': 2016, 'description': 'Drug price standards tied to VA prices', 'pct_yes': 46.2, 'passed': False, 'is_health': True},
        {'ballot_name': 'Prop 29', 'year': 2020, 'description': 'Kidney dialysis clinic requirements', 'pct_yes': 36.6, 'passed': False, 'is_health': True},

        # Criminal justice measures
        {'ballot_name': 'Prop 184', 'year': 1994, 'description': 'Three strikes sentencing law', 'pct_yes': 71.8, 'passed': True, 'is_criminal': True},
        {'ballot_name': 'Prop 36', 'year': 2012, 'description': 'Three strikes reform - serious felonies only', 'pct_yes': 69.3, 'passed': True, 'is_criminal': True},
        {'ballot_name': 'Prop 47', 'year': 2014, 'description': 'Reduced penalties for some crimes', 'pct_yes': 59.6, 'passed': True, 'is_criminal': True},
        {'ballot_name': 'Prop 57', 'year': 2016, 'description': 'Parole for nonviolent offenders', 'pct_yes': 64.5, 'passed': True, 'is_criminal': True},

        # Elections measures
        {'ballot_name': 'Prop 14', 'year': 2010, 'description': 'Top-two open primary elections', 'pct_yes': 53.8, 'passed': True, 'is_elections': True},
        {'ballot_name': 'Prop 11', 'year': 2008, 'description': 'Independent redistricting commission', 'pct_yes': 51.0, 'passed': True, 'is_elections': True},
        {'ballot_name': 'Prop 17', 'year': 2020, 'description': 'Voting rights restoration for parolees', 'pct_yes': 58.6, 'passed': True, 'is_elections': True},

        # Environment measures
        {'ballot_name': 'Prop 65', 'year': 1986, 'description': 'Safe Drinking Water and Toxic Enforcement Act', 'pct_yes': 63.2, 'passed': True, 'is_environment': True, 'is_health': True},
        {'ballot_name': 'Prop 23', 'year': 2010, 'description': 'Suspend AB 32 climate change law', 'pct_yes': 38.4, 'passed': False, 'is_environment': True},
        {'ballot_name': 'Prop 37', 'year': 2012, 'description': 'GMO food labeling requirement', 'pct_yes': 48.6, 'passed': False, 'is_environment': True, 'is_health': True},
        {'ballot_name': 'Prop 12', 'year': 2018, 'description': 'Farm animal confinement standards', 'pct_yes': 62.7, 'passed': True, 'is_environment': True},
    ]

    # Initialize database
    conn = sqlite3.connect(db_path)
    conn.executescript(HISTORICAL_SCHEMA)
    conn.commit()

    stats = {
        'imported': 0,
        'topics': {topic: 0 for topic in TOPIC_CONFIG.keys()}
    }

    for m in mock_measures:
        margin = m['pct_yes'] - 50

        conn.execute("""
            INSERT INTO ca_historical_measures (
                ballot_name, year, description, pct_yes, passed,
                measure_type, election_type,
                is_marijuana, is_gambling, is_abortion, is_marriage,
                is_tax, is_education, is_health, is_elections,
                is_criminal, is_environment,
                margin, is_close, is_very_close,
                is_initiative, is_referendum,
                source_dataset
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            m['ballot_name'],
            m['year'],
            m['description'],
            m['pct_yes'],
            m['passed'],
            'Initiative',
            'General',
            m.get('is_marijuana', False),
            m.get('is_gambling', False),
            m.get('is_abortion', False),
            m.get('is_marriage', False),
            m.get('is_tax', False),
            m.get('is_education', False),
            m.get('is_health', False),
            m.get('is_elections', False),
            m.get('is_criminal', False),
            m.get('is_environment', False),
            margin,
            abs(margin) < 10,
            abs(margin) < 5,
            True,
            False,
            'MOCK_DATA'
        ))

        stats['imported'] += 1
        for topic in TOPIC_CONFIG.keys():
            if m.get(f'is_{topic}', False):
                stats['topics'][topic] += 1

    conn.commit()

    # Rebuild FTS index
    try:
        conn.execute("""
            INSERT INTO ca_historical_search(ca_historical_search)
            VALUES('rebuild')
        """)
        conn.commit()
    except:
        pass

    conn.close()

    logger.info(f"Generated {stats['imported']} mock measures")
    return stats


if __name__ == '__main__':
    import sys

    logging.basicConfig(level=logging.INFO)

    # Default paths
    project_root = Path(__file__).parent.parent.parent.parent
    db_path = project_root / 'data' / 'ballot_measures.db'
    csv_path = project_root / 'data' / 'raw' / 'ballot_measures_combined.csv'

    if len(sys.argv) > 1 and sys.argv[1] == '--mock':
        print("Generating mock data...")
        stats = generate_mock_data(db_path)
    elif csv_path.exists():
        print(f"Importing from {csv_path}...")
        stats = import_from_csv(csv_path, db_path)
    else:
        print(f"CSV not found at {csv_path}")
        print("Use --mock flag to generate mock data instead")
        print(f"  python {sys.argv[0]} --mock")
        sys.exit(1)

    print(f"\nImport statistics:")
    print(f"  Imported: {stats['imported']}")
    print(f"  Topics: {stats['topics']}")
