#!/usr/bin/env python3
"""
Keyword-based topic classifier for ballot measures.
Uses pattern matching to assign topics to unlabeled measures.
"""
import sys
import re
import logging
import argparse
from pathlib import Path
from collections import Counter

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import DB_PATH
from src.database.operations import Database

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Topic classification rules: (topic_name, keywords, negative_keywords)
# Keywords are checked against title + ballot_question text
# More specific patterns are checked first
TOPIC_RULES = [
    # === SPECIFIC TOPICS (check first) ===

    # Education
    ('Education', [
        r'\bschool\b', r'\beducation\b', r'\bstudent\b', r'\bteacher\b',
        r'\bclassroom\b', r'\bcurriculum\b', r'\bschool district\b',
        r'\bschool board\b', r'\bprek\b', r'\bpre-k\b', r'\bk-12\b',
        r'\buniversity\b', r'\bcollege\b', r'\bhigher ed\b',
        r'\bschool bond\b', r'\beducational\b', r'\bschools\b'
    ], [r'\bdriver.?s school\b', r'\bschool of fish\b']),

    # Public Safety / Criminal Justice
    ('Public Safety', [
        r'\bpolice\b', r'\bfire department\b', r'\bfirefighter\b',
        r'\bparamedic\b', r'\b911\b', r'\bemergency service\b',
        r'\bpublic safety\b', r'\bsheriff\b', r'\blaw enforcement\b',
        r'\bcrime\b', r'\bcriminal\b', r'\bprison\b', r'\bjail\b',
        r'\binmate\b', r'\bsentencing\b', r'\bparole\b', r'\bprobation\b',
        r'\bfelony\b', r'\bmisdemeanor\b', r'\bvictim\b', r'\bfire protection\b'
    ], []),

    # Healthcare / Health
    ('Healthcare', [
        r'\bhealth\b', r'\bhospital\b', r'\bmedic\b', r'\bclinic\b',
        r'\bdoctor\b', r'\bnurse\b', r'\bpatient\b', r'\bhealthcare\b',
        r'\bmental health\b', r'\bdrug\b', r'\bprescription\b',
        r'\binsurance\b', r'\bmedical\b', r'\bdisease\b', r'\btreatment\b',
        r'\bambulance\b', r'\bhealth care\b', r'\bvaccin\b'
    ], [r'\bplant health\b', r'\bfinancial health\b']),

    # Transportation
    ('Transportation', [
        r'\btransportation\b', r'\btransit\b', r'\broad\b', r'\bhighway\b',
        r'\bstreet\b', r'\btraffic\b', r'\bbridge\b', r'\bbus\b',
        r'\brail\b', r'\btrain\b', r'\bairport\b', r'\bparking\b',
        r'\bbicycle\b', r'\bpedestrian\b', r'\bsidewalk\b', r'\bpaving\b',
        r'\bcommut\b', r'\bvehicle\b', r'\bfreeway\b'
    ], []),

    # Environment / Natural Resources
    ('Environment', [
        r'\benvironment\b', r'\bclimate\b', r'\bpollution\b', r'\bclean air\b',
        r'\bclean water\b', r'\bconservation\b', r'\bwildlife\b', r'\bpark\b',
        r'\bopen space\b', r'\bgreen\b', r'\brecycl\b', r'\bwaste\b',
        r'\bnatural resource\b', r'\bcoastal\b', r'\bocean\b', r'\bforest\b',
        r'\btree\b', r'\bhabitat\b', r'\bendangered\b', r'\bsustainab\b',
        r'\bemission\b', r'\bcarbon\b', r'\brenewable\b', r'\bagriculture\b',
        r'\bfarmland\b', r'\bopen space lands\b'
    ], []),

    # Housing
    ('Housing', [
        r'\bhousing\b', r'\brent\b', r'\btenant\b', r'\blandlord\b',
        r'\bapartment\b', r'\bresidential\b', r'\bhomeless\b', r'\bshelter\b',
        r'\baffordable housing\b', r'\brent control\b', r'\beviction\b',
        r'\bmobile home\b', r'\bhomeowner\b', r'\bmortgage\b', r'\blow.?rent\b',
        r'\bunhoused\b', r'\bvacant.*unit\b', r'\bresidential unit\b'
    ], []),

    # Elections / Voting
    ('Elections', [
        r'\belection\b', r'\bvot\b', r'\bballot\b', r'\bcampaign\b',
        r'\bcandidate\b', r'\bprimary\b', r'\bredistric\b', r'\brecall\b',
        r'\bterm limit\b', r'\bpolitical\b', r'\bpartisan\b',
        r'\binitiative\b', r'\breferendum\b', r'\bregistration\b'
    ], [r'\bschool board election\b']),  # Covered by Education

    # Taxes / Revenue
    ('Taxes & Revenue', [
        r'\btax\b', r'\btaxes\b', r'\btaxation\b', r'\bsales tax\b',
        r'\bproperty tax\b', r'\bincome tax\b', r'\bparcel tax\b',
        r'\bassessment\b', r'\blevy\b', r'\bfee\b', r'\brevenue\b',
        r'\bappropriation\b', r'\bbudget\b', r'\bfiscal\b', r'\bspending limit\b',
        r'\btransactions\b.*\buse tax\b', r'\butility.*tax\b', r'\bgas tax\b'
    ], []),

    # Bonds
    ('Bonds', [
        r'\bbond\b', r'\bbonds\b', r'\bgeneral obligation\b', r'\bindebtedness\b',
        r'\bborrowing\b', r'\bdebt\b'
    ], [r'\bbond.*between\b', r'\bbail bond\b']),

    # Labor / Employment
    ('Labor & Employment', [
        r'\blabor\b', r'\bworker\b', r'\bemployee\b', r'\bemployment\b',
        r'\bwage\b', r'\bsalary\b', r'\bunion\b', r'\bcollective bargaining\b',
        r'\bminimum wage\b', r'\bovertime\b', r'\bworkplace\b', r'\bjob\b',
        r'\bhiring\b', r'\bbenefits\b', r'\bpension\b', r'\bretirement\b'
    ], []),

    # Business / Commerce
    ('Business & Commerce', [
        r'\bbusiness\b', r'\bcorporat\b', r'\bcommerce\b', r'\bmerchant\b',
        r'\bretail\b', r'\bfranchise\b', r'\blicens\b', r'\bpermit\b',
        r'\bregulat\b', r'\bcannabis\b', r'\bmarijuana\b', r'\balcohol\b',
        r'\bliquor\b', r'\btobacco\b', r'\bgambling\b', r'\bcasino\b',
        r'\blottery\b', r'\bcard room\b'
    ], []),

    # Land Use / Zoning
    ('Land Use', [
        r'\bzoning\b', r'\bland use\b', r'\bdevelopment\b', r'\bbuilding\b',
        r'\bconstruction\b', r'\bgrowth\b', r'\bdensity\b', r'\bheight limit\b',
        r'\bgeneral plan\b', r'\bplanning\b', r'\bannexation\b', r'\bincorporat\b'
    ], []),

    # Government / Governance
    ('Governance', [
        r'\bcharter\b', r'\bordinance\b', r'\bcouncil\b', r'\bmayor\b',
        r'\bsupervisor\b', r'\bcity manager\b', r'\bcity clerk\b',
        r'\bgovernment\b', r'\bgovernance\b', r'\bbylaws\b', r'\bamend.*charter\b',
        r'\bdistrict\b.*\bformation\b', r'\bconsolidat\b', r'\bdissolution\b',
        r'\bcontract\b', r'\bleasing\b', r'\bbidding\b', r'\bgender.?neutral\b',
        r'\bcouncilmember\b', r'\bterm limit\b', r'\bcity services\b',
        r'\bgeneral.*services\b', r'\bnoncitizen\b'
    ], []),

    # Utilities / Infrastructure
    ('Utilities', [
        r'\bwater\b', r'\bsewer\b', r'\bwastewater\b', r'\bdrainage\b',
        r'\bflood\b', r'\butility\b', r'\butilities\b', r'\belectric\b',
        r'\bpower\b', r'\benergy\b', r'\bgas\b.*\bnatural\b',
        r'\binfrastructure\b', r'\bpipeline\b'
    ], [r'\bwater polo\b', r'\bpower of\b']),

    # Libraries / Community Services
    ('Libraries & Community', [
        r'\blibrary\b', r'\blibraries\b', r'\bcommunity center\b',
        r'\brecreation\b', r'\bsenior center\b', r'\byouth\b',
        r'\bafter.?school\b', r'\barts\b', r'\bcultural\b'
    ], []),
]

def classify_measure(title: str, ballot_question: str) -> str:
    """Classify a measure based on its text content."""
    # Combine title and ballot question for matching
    text = f"{title or ''} {ballot_question or ''}".lower()

    if not text.strip():
        return None

    # Check each topic rule
    for topic, keywords, negative_keywords in TOPIC_RULES:
        # Check negative keywords first (exclusions)
        excluded = False
        for neg_pattern in negative_keywords:
            if re.search(neg_pattern, text, re.IGNORECASE):
                excluded = True
                break

        if excluded:
            continue

        # Check positive keywords
        for pattern in keywords:
            if re.search(pattern, text, re.IGNORECASE):
                return topic

    return None


def main():
    parser = argparse.ArgumentParser(description='Classify ballot measure topics')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be classified without updating database')
    parser.add_argument('--source', type=str, default='CEDA',
                       help='Data source to classify (default: CEDA)')
    parser.add_argument('--force', action='store_true',
                       help='Reclassify even measures that already have topics')
    args = parser.parse_args()

    logger.info("Starting topic classification...")

    db = Database(DB_PATH)
    conn = db.connect()

    # Get measures to classify
    if args.force:
        query = """
            SELECT fingerprint, title, ballot_question, topic_primary, category_topic
            FROM measures
            WHERE data_source = ? AND is_active = 1
        """
    else:
        query = """
            SELECT fingerprint, title, ballot_question, topic_primary, category_topic
            FROM measures
            WHERE data_source = ?
            AND is_active = 1
            AND (topic_primary IS NULL OR topic_primary = '')
            AND (category_topic IS NULL OR category_topic = '')
        """

    cursor = conn.execute(query, (args.source,))
    measures = cursor.fetchall()

    logger.info(f"Found {len(measures)} measures to classify from {args.source}")

    # Classify measures
    classified = Counter()
    updates = []

    for fingerprint, title, ballot_question, existing_topic, existing_cat in measures:
        topic = classify_measure(title, ballot_question)

        if topic:
            classified[topic] += 1
            updates.append((topic, fingerprint))
        else:
            classified['Unclassified'] += 1

    # Show results
    print("\n" + "="*50)
    print("CLASSIFICATION RESULTS")
    print("="*50)

    total_classified = sum(v for k, v in classified.items() if k != 'Unclassified')
    total_unclassified = classified.get('Unclassified', 0)

    print(f"\nTotal measures processed: {len(measures)}")
    print(f"Successfully classified: {total_classified} ({100*total_classified/len(measures):.1f}%)")
    print(f"Unclassified: {total_unclassified} ({100*total_unclassified/len(measures):.1f}%)")

    print("\nBy Topic:")
    for topic, count in classified.most_common():
        pct = 100 * count / len(measures)
        print(f"  {topic}: {count} ({pct:.1f}%)")

    # Update database if not dry run
    if not args.dry_run and updates:
        logger.info(f"Updating {len(updates)} measures in database...")

        # Update topic_primary for classified measures
        cursor = conn.cursor()
        cursor.executemany("""
            UPDATE measures
            SET topic_primary = ?
            WHERE fingerprint = ?
        """, updates)
        conn.commit()

        logger.info(f"Updated {cursor.rowcount} measures")
        print(f"\nDatabase updated with {len(updates)} new topic classifications")
    elif args.dry_run:
        print("\n[DRY RUN] No database changes made")

    db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
