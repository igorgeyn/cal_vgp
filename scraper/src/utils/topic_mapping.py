"""
Topic consolidation mapping for ballot measures.

Maps detailed topic classifications (from ICPSR, CEDA, keyword classifier)
to ~12 display categories based on:
- Comparative Agendas Project (CAP) - academic gold standard
- Congress.gov Policy Areas - Library of Congress standard
- Ballotpedia ballot measure categories - practitioner standard

The original detailed topic is preserved in topic_primary; this mapping
provides clean display categories for the website dropdown.
"""

# Display categories (12 total) - based on CAP + ballot-specific additions
DISPLAY_CATEGORIES = [
    'Education',
    'Public Safety & Crime',
    'Taxes & Finance',
    'Government & Elections',
    'Healthcare & Welfare',
    'Environment & Natural Resources',
    'Transportation',
    'Housing & Land Use',
    'Business & Labor',
    'Utilities & Energy',
    'Civil Rights',
    'Other',
]

# Mapping from raw topics to display categories
# Keys are lowercase for case-insensitive matching
# Includes ICPSR compound topics, CEDA categories, and keyword classifier outputs
TOPIC_MAPPING = {
    # === EDUCATION ===
    'education': 'Education',
    'education: prek-12': 'Education',
    'education: higher ed': 'Education',
    'education: prek-12 | local government': 'Education',
    'education: prek-12 | tax & revenue': 'Education',
    'education: prek-12 | state government': 'Education',
    'education: prek-12 | labor & employment': 'Education',
    'education: prek-12 | gambling & lotteries': 'Education',
    'education: prek-12 | human services | tax & revenue': 'Education',
    'education: higher ed | tax & revenue': 'Education',
    'education: higher ed | state government': 'Education',
    'education: higher ed | labor & employment | state government': 'Education',
    'education: higher ed | education: prek-12 | gambling & lotteries': 'Education',
    'education: higher ed | education: prek-12 | tax & revenue': 'Education',
    # CEDA education
    'education: bonds': 'Education',
    'education: recall': 'Education',
    'education: districts': 'Education',
    'education: curriculum/policy issues': 'Education',

    # === PUBLIC SAFETY & CRIME ===
    'public safety': 'Public Safety & Crime',
    'criminal justice': 'Public Safety & Crime',
    'law and crime': 'Public Safety & Crime',
    'law, crime, and family issues': 'Public Safety & Crime',
    'criminal justice | drug/alcohol/tobacco policy': 'Public Safety & Crime',
    'criminal justice | juvenile justice': 'Public Safety & Crime',
    'criminal justice | labor & employment': 'Public Safety & Crime',
    'criminal justice | state government': 'Public Safety & Crime',
    'criminal justice | insurance': 'Public Safety & Crime',
    'criminal justice | education: prek-12': 'Public Safety & Crime',
    'criminal justice | labor & employment | tax & revenue': 'Public Safety & Crime',
    'criminal justice | drug/alcohol/tobacco policy | health': 'Public Safety & Crime',
    'criminal justice | drug/alcohol/tobacco policy | tax & revenue': 'Public Safety & Crime',
    # CEDA safety
    'safety': 'Public Safety & Crime',
    'safety: police': 'Public Safety & Crime',
    'safety: fire': 'Public Safety & Crime',
    'safety: multiple emergency services': 'Public Safety & Crime',
    'safety: firearms': 'Public Safety & Crime',

    # === TAXES & FINANCE ===
    'taxes & revenue': 'Taxes & Finance',
    'tax & revenue': 'Taxes & Finance',
    'budgets': 'Taxes & Finance',
    'bonds': 'Taxes & Finance',
    'bond measures': 'Taxes & Finance',
    'macroeconomics': 'Taxes & Finance',
    'economics and public finance': 'Taxes & Finance',
    'banking & financial services': 'Taxes & Finance',
    'budgets | tax & revenue': 'Taxes & Finance',
    'budgets | legislatures': 'Taxes & Finance',
    'budgets | state government': 'Taxes & Finance',
    'budgets | local government': 'Taxes & Finance',
    'budgets | transportation': 'Taxes & Finance',
    'budgets | health': 'Taxes & Finance',
    'budgets | education: prek-12': 'Taxes & Finance',
    'budgets | human services': 'Taxes & Finance',
    'banking & financial services | tax & revenue': 'Taxes & Finance',
    'banking & financial services | state government': 'Taxes & Finance',
    # CEDA revenues
    'revenues': 'Taxes & Finance',
    'revenue': 'Taxes & Finance',
    'revenues: tax creation/incr./contin.': 'Taxes & Finance',
    'revenues: tax repeal/reduction/limit': 'Taxes & Finance',
    'revenues: voter approval requirement': 'Taxes & Finance',

    # === GOVERNMENT & ELECTIONS ===
    'governance': 'Government & Elections',
    'elections': 'Government & Elections',
    'government operations': 'Government & Elections',
    'local government': 'Government & Elections',
    'state government': 'Government & Elections',
    'legislatures': 'Government & Elections',
    'redistricting': 'Government & Elections',
    'elections-initiative process': 'Government & Elections',
    'ethics/lobbying/campaign finance': 'Government & Elections',
    'federal government': 'Government & Elections',
    'elections | local government': 'Government & Elections',
    'elections | state government': 'Government & Elections',
    'elections | judiciary': 'Government & Elections',
    'elections | legislatures | tax & revenue': 'Government & Elections',
    'elections | elections-initiative process': 'Government & Elections',
    'elections-initiative process | legislatures': 'Government & Elections',
    'legislatures | state government': 'Government & Elections',
    'legislatures | term limits': 'Government & Elections',
    'legislatures | tax & revenue': 'Government & Elections',
    'local government | tax & revenue': 'Government & Elections',
    'state government | tax & revenue': 'Government & Elections',
    'redistricting | state government': 'Government & Elections',
    'ethics/lobbying/campaign finance | redistricting': 'Government & Elections',
    'federal government | term limits': 'Government & Elections',
    # CEDA governance
    'governance: organization': 'Government & Elections',
    'governance: political reform/term limits': 'Government & Elections',
    'governance: elections': 'Government & Elections',
    'governance: recall': 'Government & Elections',
    'governance: personnel/labor relations': 'Government & Elections',
    'governance: budget processes': 'Government & Elections',
    'governance: incorporation/formation/annexation': 'Government & Elections',
    'governance: contracting/bidding/leasing': 'Government & Elections',

    # === HEALTHCARE & WELFARE ===
    'healthcare': 'Healthcare & Welfare',
    'health': 'Healthcare & Welfare',
    'human services': 'Healthcare & Welfare',
    'social welfare': 'Healthcare & Welfare',
    'health | tax & revenue': 'Healthcare & Welfare',
    'health | state government': 'Healthcare & Welfare',
    'health | local government': 'Healthcare & Welfare',
    'health | insurance': 'Healthcare & Welfare',
    'health | insurance | labor & employment': 'Healthcare & Welfare',
    'health | human services | state government': 'Healthcare & Welfare',
    'health | human services | tax & revenue': 'Healthcare & Welfare',
    'human services | tax & revenue': 'Healthcare & Welfare',
    'human services | state government': 'Healthcare & Welfare',
    'human services | local government': 'Healthcare & Welfare',
    'human services | military & veterans affairs': 'Healthcare & Welfare',
    'drug/alcohol/tobacco policy': 'Healthcare & Welfare',
    'drug/alcohol/tobacco policy | tax & revenue': 'Healthcare & Welfare',
    'drug/alcohol/tobacco policy | health | tax & revenue': 'Healthcare & Welfare',
    'abortion': 'Healthcare & Welfare',
    # CEDA
    'general services: social/welfare': 'Healthcare & Welfare',
    'facilities: health facilities': 'Healthcare & Welfare',

    # === ENVIRONMENT & NATURAL RESOURCES ===
    'environment': 'Environment & Natural Resources',
    'environmental protection': 'Environment & Natural Resources',
    'natural resources': 'Environment & Natural Resources',
    'agriculture': 'Environment & Natural Resources',
    'animal rights/hunting & fishing': 'Environment & Natural Resources',
    'public lands': 'Environment & Natural Resources',
    'environmental protection | natural resources': 'Environment & Natural Resources',
    'environmental protection | tax & revenue': 'Environment & Natural Resources',
    'natural resources | state government': 'Environment & Natural Resources',
    'natural resources | tax & revenue': 'Environment & Natural Resources',
    'agriculture | local government': 'Environment & Natural Resources',
    'agriculture | tax & revenue': 'Environment & Natural Resources',
    'agriculture | labor & employment': 'Environment & Natural Resources',
    'animal rights/hunting & fishing | natural resources': 'Environment & Natural Resources',
    'animal rights/hunting & fishing | gambling & lotteries': 'Environment & Natural Resources',
    # CEDA
    'land use: open space': 'Environment & Natural Resources',
    'facilities: parks & recreation': 'Environment & Natural Resources',

    # === TRANSPORTATION ===
    'transportation': 'Transportation',
    'transport': 'Transportation',
    'transport: roads': 'Transportation',
    'transport: mass transit': 'Transportation',
    'transport: traffic regulation/reduction': 'Transportation',
    'transportation | tax & revenue': 'Transportation',
    'state government | transportation': 'Transportation',
    'local government | tax & revenue | transportation': 'Transportation',
    'budgets | tax & revenue | transportation': 'Transportation',

    # === HOUSING & LAND USE ===
    'housing': 'Housing & Land Use',
    'land use': 'Housing & Land Use',
    'land use/property rights': 'Housing & Land Use',
    'housing | tax & revenue': 'Housing & Land Use',
    'land use/property rights | transportation': 'Housing & Land Use',
    # CEDA
    'land use: zoning': 'Housing & Land Use',
    'land use: voter approval': 'Housing & Land Use',
    'land use: growth cap/boundary': 'Housing & Land Use',
    'housing: rent control': 'Housing & Land Use',
    'housing: affordable': 'Housing & Land Use',

    # === BUSINESS & LABOR ===
    'business & commerce': 'Business & Labor',
    'labor & employment': 'Business & Labor',
    'labor': 'Business & Labor',
    'domestic commerce': 'Business & Labor',
    'insurance': 'Business & Labor',
    'gambling & lotteries': 'Business & Labor',
    'business & commerce | drug/alcohol/tobacco policy': 'Business & Labor',
    'business & commerce | tax & revenue': 'Business & Labor',
    'business & commerce | local government': 'Business & Labor',
    'business & commerce | state government': 'Business & Labor',
    'business & commerce | health': 'Business & Labor',
    'business & commerce | environmental protection': 'Business & Labor',
    'labor & employment | state government': 'Business & Labor',
    'labor & employment | local government': 'Business & Labor',
    'labor & employment | legislatures': 'Business & Labor',
    'labor & employment | transportation': 'Business & Labor',
    'insurance | tax & revenue': 'Business & Labor',
    'insurance | state government': 'Business & Labor',
    'gambling & lotteries | state-tribal relations': 'Business & Labor',
    'gambling & lotteries | human services': 'Business & Labor',
    'state-tribal relations': 'Business & Labor',

    # === UTILITIES & ENERGY ===
    'utilities': 'Utilities & Energy',
    'energy': 'Utilities & Energy',
    'energy & electric utilities': 'Utilities & Energy',
    'energy & electric utilities | tax & revenue': 'Utilities & Energy',
    'energy & electric utilities | state government': 'Utilities & Energy',
    'energy & electric utilities | environmental protection': 'Utilities & Energy',
    'energy & electric utilities | natural resources': 'Utilities & Energy',
    'energy & electric utilities | local government': 'Utilities & Energy',
    'telecom & info technology': 'Utilities & Energy',
    # CEDA
    'general services: water': 'Utilities & Energy',
    'general services: wastewater/sewage': 'Utilities & Energy',
    'general services: solid waste': 'Utilities & Energy',
    'general services: flood control/drainage': 'Utilities & Energy',

    # === CIVIL RIGHTS ===
    'civil rights': 'Civil Rights',
    'civil & constitutional law': 'Civil Rights',
    'civil rights, minority issues, immigration and civil liberties': 'Civil Rights',
    'immigration': 'Civil Rights',
    'civil & constitutional law | elections': 'Civil Rights',
    'civil & constitutional law | judiciary': 'Civil Rights',
    'civil & constitutional law | health': 'Civil Rights',
    'civil & constitutional law | education: prek-12': 'Civil Rights',
    'civil & constitutional law | land use/property rights': 'Civil Rights',
    'civil & constitutional law | criminal justice': 'Civil Rights',
    'civil & constitutional law | state government': 'Civil Rights',
    'civil & constitutional law | local government': 'Civil Rights',
    'civil & constitutional law | insurance': 'Civil Rights',
    'civil & constitutional law | human services': 'Civil Rights',

    # === JUDICIARY (maps to Government) ===
    'judiciary': 'Government & Elections',
    'judiciary | state government': 'Government & Elections',
    'judiciary | legislatures': 'Government & Elections',
    'judiciary | labor & employment': 'Government & Elections',
    'judiciary | tax & revenue': 'Government & Elections',
    'judiciary | local government': 'Government & Elections',

    # === MILITARY (maps to Government) ===
    'military & veterans affairs': 'Government & Elections',
    'defense': 'Government & Elections',
    'military & veterans affairs | tax & revenue': 'Government & Elections',

    # === LIBRARIES & COMMUNITY (maps to Education or Other) ===
    'libraries & community': 'Education',
    'facilities: libraries': 'Education',
    'arts & culture': 'Other',
    'culture': 'Other',
    'economic development': 'Business & Labor',

    # === GENERAL SERVICES (CEDA) ===
    'general services': 'Government & Elections',
    'general services: maintenance': 'Government & Elections',
    'other': 'Other',
}


def get_display_topic(raw_topic: str) -> str:
    """
    Map a raw topic to its display category.

    Args:
        raw_topic: The original topic from topic_primary or category_topic

    Returns:
        The consolidated display category, or 'Other' if no mapping found
    """
    if not raw_topic:
        return None

    # Clean the topic string
    clean_topic = raw_topic.strip()

    # Remove special characters (ICPSR encoding issues)
    clean_topic = clean_topic.replace('\ufffd', '').strip()

    # Try exact match first (case-insensitive)
    lookup = clean_topic.lower()
    if lookup in TOPIC_MAPPING:
        return TOPIC_MAPPING[lookup]

    # Try matching the first part of compound topics (before |)
    if '|' in lookup:
        first_part = lookup.split('|')[0].strip()
        if first_part in TOPIC_MAPPING:
            return TOPIC_MAPPING[first_part]

    # Try partial matching for common patterns
    for key, value in TOPIC_MAPPING.items():
        if key in lookup or lookup in key:
            return value

    # Check if any display category name is in the topic
    for category in DISPLAY_CATEGORIES:
        if category.lower().split()[0] in lookup:
            return category

    return 'Other'


def get_all_display_categories() -> list:
    """Return the list of all display categories in preferred order."""
    return DISPLAY_CATEGORIES.copy()
