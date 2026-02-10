"""
Category type consolidation mapping for ballot measures.

Maps raw CEDA `rec_type_name` values (stored as `category_type`) to cleaner
display categories. Follows the same pattern as topic_mapping.py.

The original category_type is preserved; the mapped value is stored as
`display_category_type` for use in the website's Measure Type filter and
Explore matrix view.
"""

# Display categories for measure types (~13 consolidated types)
DISPLAY_CATEGORY_TYPES = [
    'Ordinance',
    'Charter Amendment',
    'Sales Tax',
    'Transient Occupancy Tax',
    'Business Tax',
    'Advisory',
    'Utility Tax',
    'Recall',
    'Initiative',
    'Miscellaneous Tax',
    'Property Tax',
    'Gann Limit',
    'Bond',
]

# Mapping from raw category_type to display category type
# Keys are lowercase for case-insensitive matching
CATEGORY_TYPE_MAPPING = {
    # === Keep as-is (high N, good county coverage) ===
    'ordinance': 'Ordinance',
    'charter amendment': 'Charter Amendment',
    'sales tax': 'Sales Tax',
    'transient occupancy tax': 'Transient Occupancy Tax',
    'business tax': 'Business Tax',
    'utility tax': 'Utility Tax',
    'recall': 'Recall',
    'initiative': 'Initiative',
    'property tax': 'Property Tax',
    'gann limit': 'Gann Limit',

    # === Advisory (merge Policy/Position into Advisory) ===
    'advisory': 'Advisory',
    'policy/position': 'Advisory',

    # === Miscellaneous Tax (absorb rare tax types) ===
    'miscellaneous tax': 'Miscellaneous Tax',
    'development tax': 'Miscellaneous Tax',
    'gasoline tax': 'Miscellaneous Tax',
    'authorize expenditure': 'Miscellaneous Tax',
    'taxes': 'Miscellaneous Tax',

    # === Bond (consolidate all bond types) ===
    'go bond': 'Bond',
    'revenue bond': 'Bond',
    'mello/roos bond': 'Bond',
    'bonds': 'Bond',
}


def get_display_category_type(raw_category_type: str) -> str:
    """
    Map a raw category_type to its display category.

    Args:
        raw_category_type: The original category_type from CEDA rec_type_name

    Returns:
        The consolidated display category, or None for garbage data
    """
    if not raw_category_type:
        return None

    clean = raw_category_type.strip()
    lookup = clean.lower()

    # Drop garbage values
    if lookup in ('#null!', '0', '', 'null', 'none'):
        return None

    # Exact match (case-insensitive)
    if lookup in CATEGORY_TYPE_MAPPING:
        return CATEGORY_TYPE_MAPPING[lookup]

    # Fallback: return the original value cleaned up (title case)
    # This handles any future CEDA types we haven't mapped yet
    return clean.title()


def get_all_display_category_types() -> list:
    """Return the list of all display category types in preferred order."""
    return DISPLAY_CATEGORY_TYPES.copy()
