#!/usr/bin/env python3
"""
Extract ballot-measure campaign finance data from raw CAL-ACCESS TSV files.

Reads the full CAL-ACCESS data dump (multi-GB TSV files) and produces a clean
CSV of itemized receipts for ballot measure committees only.

The output CSV feeds into the existing build_statewide_prop_finance_db.py ETL.

Usage:
    python scripts/extract_calaccess_finance.py \
        --calaccess-dir C:/path/to/CalAccess/DATA \
        --output data/finance/calaccess_raw/ballot_measure_receipts_clean.csv

    # Or with auto-build of finance DB:
    python scripts/extract_calaccess_finance.py \
        --calaccess-dir C:/path/to/CalAccess/DATA \
        --build-db
"""
import sys
import argparse
import logging
import re
import csv
from pathlib import Path
from collections import defaultdict

import pandas as pd

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DEFAULT_OUTPUT = Path(__file__).parent.parent / "data" / "finance" / "calaccess_raw" / "ballot_measure_receipts_clean.csv"
RCPT_CHUNK_SIZE = 200_000  # Process RCPT_CD in chunks of 200K rows


def load_ballot_measure_filings(calaccess_dir: Path) -> pd.DataFrame:
    """
    Load CVR_CAMPAIGN_DISCLOSURE_CD and filter to ballot measure filings.

    Returns DataFrame with: FILING_ID, FILER_ID, BAL_NAME, BAL_NUM, SUP_OPP_CD,
    FILER_NAML, ELECT_DATE, FROM_DATE, THRU_DATE, CMTTE_TYPE, PRIMFRM_YN
    """
    logger.info("Loading CVR_CAMPAIGN_DISCLOSURE_CD...")
    cvr_path = calaccess_dir / "CVR_CAMPAIGN_DISCLOSURE_CD.TSV"

    # Only load columns we need (the file is 200+ MB)
    usecols = ['FILING_ID', 'AMEND_ID', 'FILER_ID', 'FILER_NAML',
               'BAL_NAME', 'BAL_NUM', 'BAL_JURIS', 'SUP_OPP_CD',
               'ELECT_DATE', 'FROM_DATE', 'THRU_DATE',
               'CMTTE_TYPE', 'PRIMFRM_YN', 'FORM_TYPE']

    cvr = pd.read_csv(cvr_path, sep='\t', encoding='latin-1', low_memory=False,
                       usecols=usecols, dtype=str)
    logger.info(f"  Total CVR records: {len(cvr):,}")

    # Filter to ballot measure filings: BAL_NAME or BAL_NUM must be populated
    bm_filings = cvr[
        (cvr['BAL_NAME'].notna() & (cvr['BAL_NAME'] != '')) |
        (cvr['BAL_NUM'].notna() & (cvr['BAL_NUM'] != ''))
    ].copy()
    logger.info(f"  Ballot measure filings: {len(bm_filings):,}")

    # Keep only the latest amendment for each filing
    bm_filings['AMEND_ID'] = pd.to_numeric(bm_filings['AMEND_ID'], errors='coerce').fillna(0).astype(int)
    bm_filings = bm_filings.sort_values('AMEND_ID', ascending=False).drop_duplicates('FILING_ID', keep='first')
    logger.info(f"  After dedup (latest amendment): {len(bm_filings):,}")

    # Normalize stance
    bm_filings['stance'] = bm_filings['SUP_OPP_CD'].map({'S': 'support', 'O': 'oppose'}).fillna('unknown')

    return bm_filings


def load_filer_names(calaccess_dir: Path) -> dict:
    """Load FILERNAME_CD and return filer_id → name mapping."""
    logger.info("Loading FILERNAME_CD...")
    fn_path = calaccess_dir / "FILERNAME_CD.TSV"

    fn = pd.read_csv(fn_path, sep='\t', encoding='latin-1', low_memory=False,
                      usecols=['FILER_ID', 'FILER_TYPE', 'NAML', 'STATUS'],
                      dtype=str)

    # Keep most recent name per filer (last row)
    fn = fn.drop_duplicates('FILER_ID', keep='last')

    filer_names = {}
    for _, row in fn.iterrows():
        filer_names[str(row['FILER_ID'])] = {
            'name': str(row.get('NAML', '')),
            'type': str(row.get('FILER_TYPE', '')),
        }

    logger.info(f"  Loaded {len(filer_names):,} filer names")
    return filer_names


def extract_prop_num(bal_name: str, bal_num: str) -> str:
    """
    Extract just the proposition number from CAL-ACCESS ballot measure fields.

    Returns e.g., "36", "1A", "22". This matches the format expected by
    build_statewide_prop_finance_db.py's crosswalk (PROP_36 -> "36").
    """
    # Try BAL_NUM first (most direct)
    if pd.notna(bal_num) and bal_num:
        num_match = re.search(r'(\d+[A-Za-z]?)', str(bal_num).strip())
        if num_match:
            return num_match.group(1).lstrip('0') or '0'

    # Try to extract from BAL_NAME (e.g., "PROPOSITION 036")
    if pd.notna(bal_name) and bal_name:
        name_match = re.search(r'PROP(?:OSITION)?\s*[#]?\s*0*(\d+[A-Za-z]?)', str(bal_name), re.IGNORECASE)
        if name_match:
            return name_match.group(1)
        # Fallback: use BAL_NAME as-is (cleaned) for non-prop measures
        return re.sub(r'[^A-Za-z0-9]', '_', str(bal_name).strip())[:40]

    return "UNKNOWN"


def classify_donor_type(entity_cd: str) -> str:
    """Map CAL-ACCESS entity codes to donor type labels."""
    mapping = {
        'IND': 'individual',
        'COM': 'committee',
        'OTH': 'other',
        'SCC': 'small_contributor_committee',
        'RCP': 'recipient_committee',
        'PTY': 'political_party',
        'OFF': 'officeholder',
    }
    return mapping.get(str(entity_cd).strip().upper(), 'other')


def extract_receipts(calaccess_dir: Path, bm_filings: pd.DataFrame,
                     filer_names: dict, output_path: Path) -> int:
    """
    Process RCPT_CD in chunks, filtering to ballot measure filings only.

    Writes output CSV incrementally.
    """
    rcpt_path = calaccess_dir / "RCPT_CD.TSV"
    logger.info(f"Processing RCPT_CD ({rcpt_path.stat().st_size / 1e9:.1f} GB) in chunks...")

    # Pre-compute the set of ballot measure filing IDs for fast lookup
    bm_filing_ids = set(bm_filings['FILING_ID'].astype(str).values)
    logger.info(f"  Filtering for {len(bm_filing_ids):,} ballot measure filing IDs")

    # Build filing_id → measure info lookup
    filing_info = {}
    for _, row in bm_filings.iterrows():
        fid = str(row['FILING_ID'])
        filer_id = str(row['FILER_ID'])
        filer_data = filer_names.get(filer_id, {})

        prop_num = extract_prop_num(row.get('BAL_NAME', ''), row.get('BAL_NUM', ''))

        # Extract year from election date
        year = None
        if pd.notna(row.get('ELECT_DATE')):
            ym = re.search(r'(\d{4})', str(row['ELECT_DATE']))
            if ym:
                year = int(ym.group(1))

        filing_info[fid] = {
            'prop_num': prop_num,
            'year': year,
            'committee_name': filer_data.get('name', str(row.get('FILER_NAML', ''))),
            'committee_id': filer_id,
            'filer_type': filer_data.get('type', ''),
            'stance': row.get('stance', 'unknown'),
        }

    # Process RCPT_CD in chunks
    output_path.parent.mkdir(parents=True, exist_ok=True)
    total_receipts = 0

    rcpt_usecols = ['FILING_ID', 'AMEND_ID', 'RCPT_DATE', 'AMOUNT',
                     'CTRIB_NAML', 'CTRIB_NAMF', 'ENTITY_CD', 'FORM_TYPE',
                     'CTRIB_EMP', 'CTRIB_OCC']

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['prop_num', 'year', 'committee_name', 'filer_id',
                          'filer_type', 'stance', 'date', 'amount', 'txn_type',
                          'donor_name', 'donor_type', 'donor_sector'])

        for chunk_num, chunk in enumerate(pd.read_csv(
            rcpt_path, sep='\t', encoding='latin-1', low_memory=False,
            chunksize=RCPT_CHUNK_SIZE, usecols=rcpt_usecols, dtype=str
        )):
            # Filter to ballot measure filings
            bm_receipts = chunk[chunk['FILING_ID'].astype(str).isin(bm_filing_ids)]

            if len(bm_receipts) == 0:
                if chunk_num % 20 == 0:
                    logger.info(f"  Chunk {chunk_num}: 0 ballot measure receipts ({chunk_num * RCPT_CHUNK_SIZE:,} rows processed)")
                continue

            # Process each receipt
            for _, rcpt in bm_receipts.iterrows():
                fid = str(rcpt['FILING_ID'])
                info = filing_info.get(fid)
                if not info:
                    continue

                # Parse amount
                try:
                    amount = float(rcpt.get('AMOUNT', 0))
                except (ValueError, TypeError):
                    continue
                if amount <= 0:
                    continue

                # Parse date
                date_str = str(rcpt.get('RCPT_DATE', ''))
                date_match = re.search(r'(\d{1,2}/\d{1,2}/\d{4})', date_str)
                date_clean = date_match.group(1) if date_match else ''

                # Build donor name
                last = str(rcpt.get('CTRIB_NAML', '')).strip()
                first = str(rcpt.get('CTRIB_NAMF', '')).strip()
                if last == 'nan':
                    last = ''
                if first == 'nan':
                    first = ''
                donor_name = f"{last}, {first}".strip(', ') if first else last

                if not donor_name:
                    donor_name = 'Anonymous/Unitemized'

                donor_type = classify_donor_type(rcpt.get('ENTITY_CD', ''))

                writer.writerow([
                    info['prop_num'],
                    info.get('year', ''),
                    info['committee_name'],
                    info['committee_id'],
                    info['filer_type'],
                    info['stance'],
                    date_clean,
                    f"{amount:.2f}",
                    'monetary',
                    donor_name,
                    donor_type,
                    '',  # donor_sector — not available in raw CAL-ACCESS
                ])
                total_receipts += 1

            if chunk_num % 10 == 0:
                logger.info(f"  Chunk {chunk_num}: {total_receipts:,} total receipts so far")

    logger.info(f"Extraction complete: {total_receipts:,} ballot measure receipts")
    return total_receipts


def main():
    parser = argparse.ArgumentParser(description="Extract ballot measure finance data from CAL-ACCESS")
    parser.add_argument("--calaccess-dir", type=str, required=True,
                        help="Path to directory containing CAL-ACCESS TSV files")
    parser.add_argument("--output", type=str, default=str(DEFAULT_OUTPUT),
                        help="Output CSV path")
    parser.add_argument("--build-db", action="store_true",
                        help="Also run build_statewide_prop_finance_db.py after extraction")
    args = parser.parse_args()

    calaccess_dir = Path(args.calaccess_dir)
    output_path = Path(args.output)

    # Verify input files exist
    required_files = ['CVR_CAMPAIGN_DISCLOSURE_CD.TSV', 'FILERNAME_CD.TSV', 'RCPT_CD.TSV']
    for fname in required_files:
        if not (calaccess_dir / fname).exists():
            logger.error(f"Missing required file: {calaccess_dir / fname}")
            sys.exit(1)

    # Step 1: Load ballot measure filings
    bm_filings = load_ballot_measure_filings(calaccess_dir)

    # Step 2: Load filer names
    filer_names = load_filer_names(calaccess_dir)

    # Step 3: Extract receipts (chunked processing of 3.4 GB file)
    total = extract_receipts(calaccess_dir, bm_filings, filer_names, output_path)

    logger.info(f"\nOutput: {output_path}")
    logger.info(f"Total receipts: {total:,}")
    logger.info(f"File size: {output_path.stat().st_size / 1e6:.1f} MB")

    # Step 4: Optionally run ETL
    if args.build_db:
        logger.info("\nRunning finance DB build...")
        import subprocess
        result = subprocess.run(
            [sys.executable, str(Path(__file__).parent / "build_statewide_prop_finance_db.py")],
            cwd=str(Path(__file__).parent.parent)
        )
        if result.returncode == 0:
            logger.info("Finance DB built successfully")
        else:
            logger.error(f"Finance DB build failed with code {result.returncode}")


if __name__ == "__main__":
    main()
