#!/usr/bin/env python3
"""
Unified pipeline for California Ballot Measures data collection.

This is the single authoritative entry point for all scraping, parsing,
and database update operations. All Makefile targets and automation
should call this script.

Modes:
  incremental  - Scrape live sources (CA SOS, Ballotpedia) and update DB
  historical   - Parse historical data files (CEDA, NCSL, ICPSR) into DB
  full         - Run historical + incremental + dedupe
  check        - Dry-run: report what would change without writing to DB
"""
import sys
import logging
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import DB_PATH, DATA_DIR, RAW_DATA_DIR, LOG_LEVEL
from src.database.operations import Database
from src.database.models import BallotMeasure
from src.database.deduplication import Deduplicator
from src.database.utils import normalize_measure_data

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Source registry — single source of truth for what sources exist
# ---------------------------------------------------------------------------

LIVE_SOURCES = ["ca_sos", "uc_law_sf", "ballotpedia_statewide", "ballotpedia_counties"]
HISTORICAL_SOURCES = ["ceda", "ncsl", "icpsr"]
ALL_SOURCES = LIVE_SOURCES + HISTORICAL_SOURCES

# Canonical source names stored in the database (map scraper output → DB name)
CANONICAL_SOURCE_NAMES = {
    "CA_SOS": "CA_SOS",
    "CA_SOS_Scraper": "CA_SOS",       # legacy alias
    "ca_sos": "CA_SOS",
    "Ballotpedia": "Ballotpedia",
    "ballotpedia": "Ballotpedia",
    "CEDA": "CEDA",
    "ceda": "CEDA",
    "NCSL": "NCSL",
    "ncsl": "NCSL",
    "ICPSR": "ICPSR",
    "icpsr": "ICPSR",
    "UC Law SF": "UC_Law_SF",
    "UC_Law_SF": "UC_Law_SF",
    "uc_law_sf": "UC_Law_SF",
}


def canonicalize_source(name: str) -> str:
    """Map any source name variant to its canonical DB form."""
    return CANONICAL_SOURCE_NAMES.get(name, name)


# ---------------------------------------------------------------------------
# Source runners — each returns List[BallotMeasure]
# ---------------------------------------------------------------------------

def run_ca_sos() -> List[BallotMeasure]:
    """Scrape CA Secretary of State (qualified measures + initiative status)."""
    from src.scrapers.ca_sos import CASOSScraper
    logger.info("Running CA SOS scraper...")
    scraper = CASOSScraper()
    result = scraper.run(save_raw=False)
    measures = []
    for m_data in result.get("measures", []):
        normalized = normalize_measure_data(m_data)
        normalized["data_source"] = "CA_SOS"
        measures.append(BallotMeasure(**normalized))
    logger.info(f"  CA SOS: {len(measures)} measures")
    return measures


def run_uc_law_sf() -> List[BallotMeasure]:
    """Scrape UC Law SF historical ballot propositions repository."""
    from src.scrapers.ca_sos import UCLawSFScraper
    logger.info("Running UC Law SF scraper...")
    scraper = UCLawSFScraper()
    result = scraper.run(save_raw=False)
    measures = []
    for m_data in result.get("measures", []):
        normalized = normalize_measure_data(m_data)
        normalized["data_source"] = "UC_Law_SF"
        measures.append(BallotMeasure(**normalized))
    logger.info(f"  UC Law SF: {len(measures)} measures")
    return measures


def run_ballotpedia_statewide(years: Optional[List[int]] = None) -> List[BallotMeasure]:
    """Scrape Ballotpedia statewide propositions."""
    from src.scrapers.ballotpedia_statewide import BallotpediaStatewideScraper
    logger.info("Running Ballotpedia statewide scraper...")
    scraper = BallotpediaStatewideScraper()
    if years:
        scraper.YEARS_TO_SCRAPE = years
    measures = scraper.scrape_all_years()
    # Ensure canonical source name
    for m in measures:
        m.data_source = "Ballotpedia"
    logger.info(f"  Ballotpedia statewide: {len(measures)} measures")
    return measures


def run_ballotpedia_counties() -> List[BallotMeasure]:
    """Scrape Ballotpedia county-level measures."""
    from src.scrapers.ballotpedia_counties import BallotpediaCountyScraper
    logger.info("Running Ballotpedia county scraper (58 counties)...")
    scraper = BallotpediaCountyScraper()
    measures = scraper.scrape_all_counties()
    for m in measures:
        m.data_source = "Ballotpedia"
        # Ensure county is canonical uppercase
        if m.county:
            m.county = m.county.upper()
    logger.info(f"  Ballotpedia counties: {len(measures)} measures")
    return measures


def run_ceda() -> List[BallotMeasure]:
    """Parse CEDA historical data files."""
    from src.parsers.ceda import CEDAParser
    from src.config import PROCESSED_DATA_DIR
    logger.info("Running CEDA parser...")

    # Check raw dir first, then processed dir for pre-parsed CSV
    raw_dir = RAW_DATA_DIR
    ceda_raw = list(raw_dir.glob("ceda*")) + list(raw_dir.glob("CEDA*"))
    ceda_processed = list(PROCESSED_DATA_DIR.glob("ceda_parsed.csv"))

    if ceda_raw:
        logger.info(f"  Found {len(ceda_raw)} raw CEDA files in {raw_dir}")
        parser = CEDAParser(raw_dir)
    elif ceda_processed:
        logger.info(f"  No raw files; using pre-parsed CSV from {PROCESSED_DATA_DIR}")
        parser = CEDAParser(PROCESSED_DATA_DIR)
    else:
        logger.error(f"CEDA: No data files in {raw_dir} or {PROCESSED_DATA_DIR}")
        raise FileNotFoundError(
            f"No CEDA files found. Either download raw files from https://ceda.berkeley.edu/ "
            f"to {raw_dir}, or ensure ceda_parsed.csv exists in {PROCESSED_DATA_DIR}"
        )

    measures = parser.parse_all_files()
    for m in measures:
        m.data_source = "CEDA"
    logger.info(f"  CEDA: {len(measures)} measures")
    return measures


def run_ncsl() -> List[BallotMeasure]:
    """Parse NCSL data file."""
    from src.parsers.ncsl import NCSLParser
    logger.info("Running NCSL parser...")
    parser = NCSLParser(DATA_DIR)
    filepath = parser.find_file()
    if not filepath:
        raise FileNotFoundError(
            f"NCSL file not found. Expected ncsl_ballot_measures_2014_present.xlsx "
            f"in {RAW_DATA_DIR}. Download from https://www.ncsl.org/elections-and-campaigns/statewide-ballot-measures-database"
        )
    records = parser.parse()
    measures = []
    for rec in records:
        measures.append(BallotMeasure.from_dict(rec))
    for m in measures:
        m.data_source = "NCSL"
    logger.info(f"  NCSL: {len(measures)} measures")
    return measures


def run_icpsr() -> List[BallotMeasure]:
    """Parse ICPSR historical data file (1902-2016, static dataset)."""
    from src.parsers.icpsr import ICPSRParser
    logger.info("Running ICPSR parser...")
    parser = ICPSRParser(DATA_DIR)
    filepath = parser.find_file()
    if not filepath:
        raise FileNotFoundError(
            f"ICPSR file not found. Expected ncslballotmeasures_icpsr_1902_2016.csv "
            f"in {RAW_DATA_DIR}. This is a static dataset (1902-2016) — if already loaded "
            f"into the DB, you can skip this source."
        )
    records = parser.parse()
    measures = []
    for rec in records:
        measures.append(BallotMeasure.from_dict(rec))
    for m in measures:
        m.data_source = "ICPSR"
    logger.info(f"  ICPSR: {len(measures)} measures")
    return measures


# Map source keys to runner functions
SOURCE_RUNNERS = {
    "ca_sos": run_ca_sos,
    "uc_law_sf": run_uc_law_sf,
    "ballotpedia_statewide": run_ballotpedia_statewide,
    "ballotpedia_counties": run_ballotpedia_counties,
    "ceda": run_ceda,
    "ncsl": run_ncsl,
    "icpsr": run_icpsr,
}


# ---------------------------------------------------------------------------
# Pipeline orchestration
# ---------------------------------------------------------------------------

@dataclass
class PipelineResult:
    """Result of a pipeline run."""
    mode: str
    sources_attempted: List[str]
    sources_succeeded: List[str]
    sources_failed: Dict[str, str]  # source → error message
    measures_collected: int
    measures_inserted: int
    measures_updated: int
    measures_duplicate: int
    errors: int

    @property
    def success(self) -> bool:
        return len(self.sources_failed) == 0

    def summary(self) -> str:
        lines = [
            f"\n{'='*60}",
            f"Pipeline complete: {self.mode} mode",
            f"{'='*60}",
            f"Sources: {len(self.sources_succeeded)}/{len(self.sources_attempted)} succeeded",
        ]
        if self.sources_failed:
            lines.append(f"FAILED sources:")
            for src, err in self.sources_failed.items():
                lines.append(f"  {src}: {err}")
        lines.extend([
            f"Measures collected: {self.measures_collected}",
            f"  Inserted: {self.measures_inserted}",
            f"  Updated:  {self.measures_updated}",
            f"  Dupes:    {self.measures_duplicate}",
            f"  Errors:   {self.errors}",
        ])
        return "\n".join(lines)


def collect_measures(sources: List[str], fail_fast: bool = False) -> tuple:
    """
    Run specified source collectors and return measures + status.

    Returns:
        (measures, succeeded, failed) where failed is {source: error_msg}
    """
    all_measures = []
    succeeded = []
    failed = {}

    for source in sources:
        runner = SOURCE_RUNNERS.get(source)
        if not runner:
            failed[source] = f"Unknown source: {source}"
            continue
        try:
            measures = runner()
            if not measures:
                logger.warning(f"{source}: returned 0 measures")
            all_measures.extend(measures)
            succeeded.append(source)
        except FileNotFoundError as e:
            failed[source] = str(e)
            logger.error(f"{source}: {e}")
            if fail_fast:
                break
        except Exception as e:
            failed[source] = str(e)
            logger.error(f"{source} failed: {e}", exc_info=True)
            if fail_fast:
                break

    return all_measures, succeeded, failed


def ingest_measures(db: Database, measures: List[BallotMeasure],
                    dry_run: bool = False) -> Dict[str, int]:
    """
    Insert/update measures into the database with deduplication.

    Returns:
        dict with keys: inserted, updated, duplicate, errors
    """
    stats = {"inserted": 0, "updated": 0, "duplicate": 0, "errors": 0}

    if dry_run:
        for m in measures:
            existing = db.find_by_fingerprint(m.fingerprint)
            if existing:
                # Check if content differs
                content_match = db.find_by_content_hash(m.content_hash)
                if content_match:
                    stats["duplicate"] += 1
                else:
                    stats["updated"] += 1
            else:
                stats["inserted"] += 1
        return stats

    deduplicator = Deduplicator(db)

    for measure in measures:
        try:
            dup = deduplicator.check_duplicate(measure)

            if dup:
                if dup["type"] == "exact":
                    # Update existing record with any new data
                    db.update_measure(dup["id"], measure.to_dict())
                    stats["updated"] += 1
                else:
                    # Cross-source or content duplicate — insert and mark
                    try:
                        measure_id = db.insert_measure(measure)
                        deduplicator.mark_duplicate(
                            measure_id, dup["id"], dup["type"]
                        )
                        stats["duplicate"] += 1
                    except Exception:
                        stats["duplicate"] += 1
            else:
                db.insert_measure(measure)
                stats["inserted"] += 1

        except Exception as e:
            stats["errors"] += 1
            logger.error(f"Error ingesting measure: {e}")

    return stats


def run_pipeline(mode: str, sources: Optional[List[str]] = None,
                 dry_run: bool = False, dedupe: bool = True,
                 fail_fast: bool = False,
                 min_source_count: int = 0) -> PipelineResult:
    """
    Run the full pipeline.

    Args:
        mode: "incremental", "historical", "full", or "check"
        sources: Override source list (default: based on mode)
        dry_run: If True, report changes without writing to DB
        dedupe: If True, run cross-source deduplication after ingest
        fail_fast: If True, stop on first source failure
        min_source_count: Minimum number of sources that must succeed (0 = no minimum)
    """
    if dry_run or mode == "check":
        dry_run = True

    # Determine sources based on mode
    if sources:
        source_list = sources
    elif mode == "incremental":
        source_list = LIVE_SOURCES
    elif mode == "historical":
        source_list = HISTORICAL_SOURCES
    elif mode == "full":
        source_list = HISTORICAL_SOURCES + LIVE_SOURCES
    else:
        source_list = LIVE_SOURCES  # default for check

    logger.info(f"Pipeline mode={mode}, dry_run={dry_run}, sources={source_list}")

    # Collect measures from all sources
    measures, succeeded, failed = collect_measures(source_list, fail_fast=fail_fast)

    # Enforce minimum source count
    if min_source_count > 0 and len(succeeded) < min_source_count:
        logger.error(
            f"Only {len(succeeded)}/{min_source_count} required sources succeeded. "
            f"Failed: {list(failed.keys())}. Aborting."
        )
        return PipelineResult(
            mode=mode,
            sources_attempted=source_list,
            sources_succeeded=succeeded,
            sources_failed=failed,
            measures_collected=len(measures),
            measures_inserted=0,
            measures_updated=0,
            measures_duplicate=0,
            errors=1,
        )

    # Ingest into database
    if measures:
        with Database() as db:
            run_id = db.log_scraper_run(mode)

            ingest_stats = ingest_measures(db, measures, dry_run=dry_run)

            # Run cross-source deduplication
            if dedupe and not dry_run and ingest_stats["inserted"] > 0:
                logger.info("Running cross-source deduplication...")
                deduplicator = Deduplicator(db)
                deduplicator.deduplicate_cross_source()

            if not dry_run:
                db.update_scraper_run(
                    run_id,
                    measures_checked=len(measures),
                    new_measures=ingest_stats["inserted"],
                    updated_measures=ingest_stats["updated"],
                    duplicates_found=ingest_stats["duplicate"],
                    status="success" if ingest_stats["errors"] == 0 else "completed_with_errors",
                )
    else:
        ingest_stats = {"inserted": 0, "updated": 0, "duplicate": 0, "errors": 0}

    result = PipelineResult(
        mode=mode,
        sources_attempted=source_list,
        sources_succeeded=succeeded,
        sources_failed=failed,
        measures_collected=len(measures),
        measures_inserted=ingest_stats["inserted"],
        measures_updated=ingest_stats["updated"],
        measures_duplicate=ingest_stats["duplicate"],
        errors=ingest_stats["errors"],
    )

    logger.info(result.summary())
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Unified pipeline for California Ballot Measures",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Modes:
  incremental   Scrape live sources (CA SOS, Ballotpedia) and update DB
  historical    Parse historical data files (CEDA, NCSL, ICPSR) into DB
  full          Run historical + incremental + dedupe
  check         Dry-run: report what would change without writing to DB

Examples:
  python pipeline.py incremental
  python pipeline.py check
  python pipeline.py full --fail-fast
  python pipeline.py incremental --sources ca_sos ballotpedia_statewide
  python pipeline.py historical --sources ceda
        """,
    )
    parser.add_argument(
        "mode",
        choices=["incremental", "historical", "full", "check"],
        help="Pipeline mode",
    )
    parser.add_argument(
        "--sources",
        nargs="+",
        choices=ALL_SOURCES,
        default=None,
        help="Override source list (default: based on mode)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report changes without writing to DB",
    )
    parser.add_argument(
        "--no-dedupe",
        action="store_true",
        help="Skip cross-source deduplication",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop on first source failure",
    )
    parser.add_argument(
        "--min-sources",
        type=int,
        default=0,
        help="Minimum number of sources that must succeed (0 = no minimum)",
    )

    args = parser.parse_args()

    result = run_pipeline(
        mode=args.mode,
        sources=args.sources,
        dry_run=args.dry_run or args.mode == "check",
        dedupe=not args.no_dedupe,
        fail_fast=args.fail_fast,
        min_source_count=args.min_sources,
    )

    print(result.summary())

    # Exit code: 0 if all sources succeeded, 1 if any failed
    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    main()
