#!/usr/bin/env python3
"""
Normalize county names in the database.
Fixes:
- Inconsistent casing (ALAMEDA vs Alameda)
- Typos (SAN BERNADINO -> SAN BERNARDINO, TOULUMNE -> TUOLUMNE)
- Standardizes to Title Case for readability
"""
import sys
import sqlite3
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

DB_PATH = Path(__file__).parent.parent / "data" / "ballot_measures.db"

# Standard California county names (Title Case)
CA_COUNTIES = {
    'ALAMEDA': 'Alameda',
    'ALPINE': 'Alpine',
    'AMADOR': 'Amador',
    'BUTTE': 'Butte',
    'CALAVERAS': 'Calaveras',
    'COLUSA': 'Colusa',
    'CONTRA COSTA': 'Contra Costa',
    'DEL NORTE': 'Del Norte',
    'EL DORADO': 'El Dorado',
    'FRESNO': 'Fresno',
    'GLENN': 'Glenn',
    'HUMBOLDT': 'Humboldt',
    'IMPERIAL': 'Imperial',
    'INYO': 'Inyo',
    'KERN': 'Kern',
    'KINGS': 'Kings',
    'LAKE': 'Lake',
    'LASSEN': 'Lassen',
    'LOS ANGELES': 'Los Angeles',
    'MADERA': 'Madera',
    'MARIN': 'Marin',
    'MARIPOSA': 'Mariposa',
    'MENDOCINO': 'Mendocino',
    'MERCED': 'Merced',
    'MODOC': 'Modoc',
    'MONO': 'Mono',
    'MONTEREY': 'Monterey',
    'NAPA': 'Napa',
    'NEVADA': 'Nevada',
    'ORANGE': 'Orange',
    'PLACER': 'Placer',
    'PLUMAS': 'Plumas',
    'RIVERSIDE': 'Riverside',
    'SACRAMENTO': 'Sacramento',
    'SAN BENITO': 'San Benito',
    'SAN BERNARDINO': 'San Bernardino',
    'SAN DIEGO': 'San Diego',
    'SAN FRANCISCO': 'San Francisco',
    'SAN JOAQUIN': 'San Joaquin',
    'SAN LUIS OBISPO': 'San Luis Obispo',
    'SAN MATEO': 'San Mateo',
    'SANTA BARBARA': 'Santa Barbara',
    'SANTA CLARA': 'Santa Clara',
    'SANTA CRUZ': 'Santa Cruz',
    'SHASTA': 'Shasta',
    'SIERRA': 'Sierra',
    'SISKIYOU': 'Siskiyou',
    'SOLANO': 'Solano',
    'SONOMA': 'Sonoma',
    'STANISLAUS': 'Stanislaus',
    'SUTTER': 'Sutter',
    'TEHAMA': 'Tehama',
    'TRINITY': 'Trinity',
    'TULARE': 'Tulare',
    'TUOLUMNE': 'Tuolumne',
    'VENTURA': 'Ventura',
    'YOLO': 'Yolo',
    'YUBA': 'Yuba',
    # Special cases
    'STATEWIDE': 'Statewide',
}

# Known typos
TYPO_FIXES = {
    'SAN BERNADINO': 'SAN BERNARDINO',
    'TOULUMNE': 'TUOLUMNE',
}


def normalize_county(county: str) -> str:
    """Normalize a county name to standard Title Case."""
    if not county:
        return county

    upper = county.upper().strip()

    # Fix known typos first
    if upper in TYPO_FIXES:
        upper = TYPO_FIXES[upper]

    # Look up standard name
    if upper in CA_COUNTIES:
        return CA_COUNTIES[upper]

    # If not found, return original (might be a city or other jurisdiction)
    return county


def main():
    print("=" * 60)
    print("NORMALIZING COUNTY NAMES")
    print("=" * 60)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get all distinct county values
    cursor.execute('SELECT DISTINCT county FROM measures WHERE county IS NOT NULL')
    counties = [row[0] for row in cursor.fetchall()]

    print(f"\nFound {len(counties)} distinct county values")

    # Build update mapping
    updates = {}
    for county in counties:
        normalized = normalize_county(county)
        if normalized != county:
            updates[county] = normalized

    print(f"Will normalize {len(updates)} county values:\n")

    for old, new in sorted(updates.items()):
        cursor.execute('SELECT COUNT(*) FROM measures WHERE county = ?', (old,))
        count = cursor.fetchone()[0]
        print(f"  '{old}' -> '{new}' ({count} measures)")

    # Confirm
    print(f"\nTotal updates: {len(updates)} county name variants")
    response = input("\nProceed with update? [y/N]: ")

    if response.lower() != 'y':
        print("Aborted.")
        return 1

    # Perform updates
    total_updated = 0
    for old, new in updates.items():
        cursor.execute('UPDATE measures SET county = ? WHERE county = ?', (new, old))
        total_updated += cursor.rowcount

    conn.commit()
    conn.close()

    print(f"\n✅ Updated {total_updated} measures")
    print("\nNext steps:")
    print("  1. Run 'make website' to regenerate the site")
    print("  2. Verify county filters work correctly")

    return 0


if __name__ == '__main__':
    sys.exit(main())
