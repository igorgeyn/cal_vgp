#!/usr/bin/env python3
"""
Migration: Canonicalize county names, source names, and regenerate derived keys.

This is a one-time migration that:
1. Normalizes county names to uppercase with typo fixes
2. Sets county='Statewide' for statewide measures (currently NULL)
3. Normalizes data_source names to canonical forms
4. Regenerates fingerprint, measure_fingerprint, content_hash for all rows
5. Runs cross-source deduplication

Run with --dry-run first to see what would change.
"""
import sys
import logging
import argparse
import sqlite3
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import DB_PATH

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# County name canonicalization
# ---------------------------------------------------------------------------

# Typo corrections (raw → correct uppercase)
COUNTY_TYPO_FIXES = {
    "SAN BERNADINO": "SAN BERNARDINO",
    "TOULUMNE": "TUOLUMNE",
}

# All valid California counties (uppercase)
VALID_CA_COUNTIES = {
    "ALAMEDA", "ALPINE", "AMADOR", "BUTTE", "CALAVERAS", "COLUSA",
    "CONTRA COSTA", "DEL NORTE", "EL DORADO", "FRESNO", "GLENN",
    "HUMBOLDT", "IMPERIAL", "INYO", "KERN", "KINGS", "LAKE", "LASSEN",
    "LOS ANGELES", "MADERA", "MARIN", "MARIPOSA", "MENDOCINO", "MERCED",
    "MODOC", "MONO", "MONTEREY", "NAPA", "NEVADA", "ORANGE", "PLACER",
    "PLUMAS", "RIVERSIDE", "SACRAMENTO", "SAN BENITO", "SAN BERNARDINO",
    "SAN DIEGO", "SAN FRANCISCO", "SAN JOAQUIN", "SAN LUIS OBISPO",
    "SAN MATEO", "SANTA BARBARA", "SANTA CLARA", "SANTA CRUZ", "SHASTA",
    "SIERRA", "SISKIYOU", "SOLANO", "SONOMA", "STANISLAUS", "SUTTER",
    "TEHAMA", "TRINITY", "TULARE", "TUOLUMNE", "VENTURA", "YOLO", "YUBA",
}


def canonicalize_county(county_raw):
    """Normalize a county name to its canonical uppercase form, or 'Statewide'."""
    if county_raw is None or str(county_raw).strip() == "":
        return "Statewide"

    upper = str(county_raw).strip().upper()

    if upper in ("STATEWIDE", "CALIFORNIA"):
        return "Statewide"

    # Fix known typos
    if upper in COUNTY_TYPO_FIXES:
        upper = COUNTY_TYPO_FIXES[upper]

    # Validate against known counties
    if upper in VALID_CA_COUNTIES:
        return upper

    # If it doesn't match, return uppercase anyway (may be a city/jurisdiction)
    return upper


# ---------------------------------------------------------------------------
# Source name canonicalization
# ---------------------------------------------------------------------------

SOURCE_CANONICAL = {
    "CA_SOS": "CA_SOS",
    "CA_SOS_Scraper": "CA_SOS",
    "Ballotpedia": "Ballotpedia",
    "CEDA": "CEDA",
    "NCSL": "NCSL",
    "ICPSR": "ICPSR",
    "UC Law SF": "UC_Law_SF",
    "UC_Law_SF": "UC_Law_SF",
}


def canonicalize_source(source_raw):
    """Normalize source name."""
    if not source_raw:
        return "Unknown"
    return SOURCE_CANONICAL.get(source_raw, source_raw)


# ---------------------------------------------------------------------------
# Fingerprint regeneration (mirrors BallotMeasure.generate_fingerprints)
# ---------------------------------------------------------------------------

import hashlib
import re


def extract_measure_identifier(measure_id, measure_letter, title, ballot_question, content_hash_hex):
    """Extract standardized measure identifier — mirrors BallotMeasure logic."""
    if measure_id:
        return measure_id.upper().replace('PROPOSITION', 'PROP')

    text = title or ballot_question or ''
    if not text:
        return "UNKNOWN"

    patterns = [
        (r'(?:Proposition|Prop\.?)\s*(\d+[A-Z]?)', 'PROP_{}'),
        (r'([AS]CA)\s*(\d+)', '{}_{}'),
        (r'(AB|SB)\s*(\d+)', '{}_{}'),
        (r'(?:Measure)\s*([A-Z]+)', 'MEASURE_{}'),
    ]

    for pattern, format_str in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            groups = match.groups()
            return format_str.format(*groups).upper()

    if measure_letter:
        return f"MEASURE_{measure_letter}"

    return f"HASH_{content_hash_hex[:8]}"


def compute_content_hash(title, ballot_question, description):
    """Compute content hash — mirrors BallotMeasure logic."""
    parts = [
        str(title or ''),
        str(ballot_question or ''),
        str(description or ''),
    ]
    content_str = '|'.join(parts).lower().strip()
    return hashlib.md5(content_str.encode()).hexdigest()[:16]


def compute_fingerprints(year, measure_id_std, county_canon, data_source_canon, content_hash_hex):
    """Compute all three fingerprints."""
    fingerprint = f"{year}|{measure_id_std}|{county_canon}|{data_source_canon}"
    measure_fingerprint = f"{year}|{measure_id_std}|{county_canon}"
    return fingerprint, measure_fingerprint, content_hash_hex


# ---------------------------------------------------------------------------
# Main migration
# ---------------------------------------------------------------------------

def run_migration(dry_run=False):
    db_path = DB_PATH
    logger.info(f"Database: {db_path}")
    logger.info(f"Dry run: {dry_run}")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get all measures
    cursor.execute("""
        SELECT id, county, data_source, year, measure_id, measure_letter,
               title, ballot_question, description,
               fingerprint, measure_fingerprint, content_hash
        FROM measures
    """)
    rows = cursor.fetchall()
    logger.info(f"Total rows: {len(rows)}")

    # Track changes
    county_changes = Counter()
    source_changes = Counter()
    fingerprint_changes = 0
    statewide_fixes = 0

    updates = []  # (id, county, data_source, fingerprint, measure_fp, content_hash)

    for row in rows:
        row_id = row['id']
        old_county = row['county']
        old_source = row['data_source']
        old_fp = row['fingerprint']
        old_mfp = row['measure_fingerprint']
        old_ch = row['content_hash']

        # Canonicalize
        new_county = canonicalize_county(old_county)
        new_source = canonicalize_source(old_source)

        # Track county changes
        if old_county != new_county:
            county_changes[f"{old_county!r} -> {new_county!r}"] += 1
            if new_county == "Statewide" and (old_county is None or old_county == ""):
                statewide_fixes += 1

        # Track source changes
        if old_source != new_source:
            source_changes[f"{old_source!r} -> {new_source!r}"] += 1

        # Recompute content hash
        new_ch = compute_content_hash(row['title'], row['ballot_question'], row['description'])

        # Extract standardized measure ID
        measure_id_std = extract_measure_identifier(
            row['measure_id'], row['measure_letter'],
            row['title'], row['ballot_question'], new_ch
        )

        # Recompute fingerprints with canonical county and source
        new_fp, new_mfp, _ = compute_fingerprints(
            row['year'], measure_id_std, new_county, new_source, new_ch
        )

        # Track fingerprint changes
        if new_fp != old_fp or new_mfp != old_mfp or new_ch != old_ch:
            fingerprint_changes += 1

        # Only queue update if something changed
        if (new_county != old_county or new_source != old_source or
                new_fp != old_fp or new_mfp != old_mfp or new_ch != old_ch):
            updates.append((new_county, new_source, new_fp, new_mfp, new_ch, row_id))

    # Report
    print(f"\n{'='*60}")
    print(f"CANONICALIZATION REPORT")
    print(f"{'='*60}")
    print(f"Total rows: {len(rows)}")
    print(f"Rows with changes: {len(updates)}")
    print(f"Fingerprints regenerated: {fingerprint_changes}")
    print(f"Statewide NULL->Statewide fixes: {statewide_fixes}")

    if county_changes:
        print(f"\nCounty changes ({sum(county_changes.values())} total):")
        for change, count in county_changes.most_common(20):
            print(f"  {change}: {count}")

    if source_changes:
        print(f"\nSource changes ({sum(source_changes.values())} total):")
        for change, count in source_changes.most_common():
            print(f"  {change}: {count}")

    # Check for fingerprint collisions (duplicates that will be created)
    seen_fps = {}
    collision_count = 0
    for row in rows:
        row_id = row['id']
        # Find the updated fingerprint for this row
        matching_update = None
        for u in updates:
            if u[5] == row_id:
                matching_update = u
                break
        if matching_update:
            fp = matching_update[2]
        else:
            fp = row['fingerprint']

        if fp in seen_fps:
            collision_count += 1
        else:
            seen_fps[fp] = row_id

    if collision_count > 0:
        print(f"\nWARNING: {collision_count} fingerprint collisions detected after canonicalization.")
        print("These will need deduplication after migration.")

    if dry_run:
        print(f"\nDRY RUN — no changes written. Run without --dry-run to apply.")
        conn.close()
        return

    # Apply updates
    logger.info(f"Applying {len(updates)} updates...")

    # Temporarily drop unique constraint on fingerprint to avoid conflicts during update
    # We'll handle collisions via dedup after
    cursor.execute("PRAGMA foreign_keys = OFF")

    # Drop and recreate the unique index as a non-unique one temporarily
    cursor.execute("DROP INDEX IF EXISTS idx_fingerprint")
    cursor.execute("CREATE INDEX idx_fingerprint ON measures(fingerprint)")

    # Batch update
    cursor.executemany("""
        UPDATE measures
        SET county = ?, data_source = ?, fingerprint = ?, measure_fingerprint = ?, content_hash = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, updates)

    conn.commit()
    logger.info(f"Applied {cursor.rowcount} updates")

    # Now handle fingerprint collisions — mark duplicates
    logger.info("Checking for fingerprint collisions to deduplicate...")
    cursor.execute("""
        SELECT fingerprint, GROUP_CONCAT(id) as ids, COUNT(*) as cnt
        FROM measures
        WHERE is_duplicate = 0
        GROUP BY fingerprint
        HAVING cnt > 1
    """)
    collision_groups = cursor.fetchall()

    deduped_count = 0
    for group in collision_groups:
        ids = [int(x) for x in group[1].split(',')]
        # Keep the one with the most data (lowest id as tiebreaker for stability)
        # Simple heuristic: keep the one with the most non-null fields
        best_id = None
        best_score = -1
        for mid in ids:
            cursor.execute("""
                SELECT id,
                    (CASE WHEN title IS NOT NULL THEN 1 ELSE 0 END +
                     CASE WHEN description IS NOT NULL THEN 1 ELSE 0 END +
                     CASE WHEN yes_votes IS NOT NULL THEN 1 ELSE 0 END +
                     CASE WHEN summary_text IS NOT NULL THEN 1 ELSE 0 END +
                     CASE WHEN pdf_url IS NOT NULL THEN 1 ELSE 0 END +
                     CASE WHEN ballot_question IS NOT NULL THEN 1 ELSE 0 END) as score
                FROM measures WHERE id = ?
            """, (mid,))
            row = cursor.fetchone()
            if row and row[1] > best_score:
                best_score = row[1]
                best_id = row[0]
            elif row and row[1] == best_score and row[0] < best_id:
                best_id = row[0]

        # Mark others as duplicates
        for mid in ids:
            if mid != best_id:
                cursor.execute("""
                    UPDATE measures
                    SET is_duplicate = 1, duplicate_type = 'canonicalization', master_id = ?
                    WHERE id = ?
                """, (best_id, mid))
                deduped_count += 1

    conn.commit()

    # Restore unique index (on the unique fingerprint for non-duplicates)
    # We can't enforce UNIQUE on fingerprint anymore since duplicates share them
    # The UNIQUE constraint is on the table definition, so just recreate the index
    cursor.execute("DROP INDEX IF EXISTS idx_fingerprint")
    cursor.execute("CREATE UNIQUE INDEX idx_fingerprint ON measures(fingerprint)")
    # This will fail if there are still collisions among non-dup rows — handle that
    try:
        conn.commit()
    except sqlite3.IntegrityError:
        # Fall back to non-unique index if collisions remain
        logger.warning("Could not restore UNIQUE index — fingerprint collisions remain among active rows")
        cursor.execute("DROP INDEX IF EXISTS idx_fingerprint")
        cursor.execute("CREATE INDEX idx_fingerprint ON measures(fingerprint)")
        conn.commit()

    cursor.execute("PRAGMA foreign_keys = ON")
    conn.commit()

    # Final stats
    cursor.execute("SELECT COUNT(*) FROM measures WHERE is_duplicate = 0")
    active_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM measures WHERE is_duplicate = 1")
    dup_count = cursor.fetchone()[0]

    print(f"\nMigration complete:")
    print(f"  Rows updated: {len(updates)}")
    print(f"  New duplicates marked: {deduped_count}")
    print(f"  Active measures: {active_count}")
    print(f"  Duplicate measures: {dup_count}")

    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Canonicalize county/source names and regenerate keys")
    parser.add_argument("--dry-run", action="store_true", help="Report changes without writing")
    args = parser.parse_args()
    run_migration(dry_run=args.dry_run)
