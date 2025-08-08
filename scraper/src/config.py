"""
Central configuration for California Ballot Measures System
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Paths
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
EXPORTS_DIR = DATA_DIR / "exports"
DB_PATH = DATA_DIR / "ballot_measures.db"

# Ensure directories exist
for dir_path in [DATA_DIR, RAW_DATA_DIR, PROCESSED_DATA_DIR, EXPORTS_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

# Database
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DB_PATH}")

# API Configuration
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))
API_RELOAD = os.getenv("API_RELOAD", "true").lower() == "true"

# Scraping Configuration
SCRAPING_CONFIG = {
    "rate_limit": float(os.getenv("SCRAPING_RATE_LIMIT", "1.0")),
    "timeout": int(os.getenv("SCRAPING_TIMEOUT", "30")),
    "user_agent": os.getenv("USER_AGENT", "Mozilla/5.0 (compatible; CA-Ballot-Scraper/2.0)"),
    "max_retries": 3,
}

# Data Sources
SOURCES = {
    "ca_sos": {
        "name": "California Secretary of State",
        "base_url": "https://www.sos.ca.gov",
        "endpoints": {
            "qualified": "/elections/ballot-measures/qualified-ballot-measures",
            "initiative_status": "/elections/ballot-measures/initiative-and-referendum-status",
        }
    },
    "uc_law_sf": {
        "name": "UC Law SF Repository",
        "base_url": "https://repository.uclawsf.edu",
        "endpoint": "/ca_ballot_props/",
        "max_items": 50
    }
}

# Summary Generation
SUMMARY_CONFIG = {
    "enabled": os.getenv("ENABLE_SUMMARIES", "true").lower() == "true",
    "max_attempts": int(os.getenv("MAX_SUMMARY_ATTEMPTS", "10")),
    "rate_limit": float(os.getenv("SUMMARY_RATE_LIMIT", "2.0")),
}

# Known summaries (pre-configured)
KNOWN_SUMMARIES = {
    "ACA 13": {
        "title": "Protect and Retain the Majority Vote Act",
        "summary": "Would require that ballot measures proposing to increase voting thresholds for future measures must themselves pass by the same increased threshold they seek to impose. Currently, a simple majority can pass a measure requiring supermajority votes for future actions, giving disproportionate power to a minority of voters."
    },
    "SCA 1": {
        "title": "Recall Process Reform",
        "summary": "Would reform California's recall process by eliminating the simultaneous successor election that currently appears on recall ballots. Under the current system, voters decide both whether to recall an officer and who should replace them, allowing a replacement to be chosen by a slim plurality rather than majority support."
    }
}

# Website Configuration
WEBSITE_CONFIG = {
    "output_filename": "index.html",
    "template": "modern",  # modern, classic, simple
    "features": {
        "search": True,
        "filters": True,
        "statistics": True,
        "export": True
    }
}

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_FILE = BASE_DIR / "logs" / "ballot_measures.log"

# Historical Data Files
HISTORICAL_DATA = {
    "ncsl": {
        "filename": "ncsl_ballot_measures_2014_present.xlsx",
        "search_paths": [
            DATA_DIR / "downloaded",
            BASE_DIR / "downloaded",
            BASE_DIR.parent / "downloaded"
        ]
    },
    "icpsr": {
        "filename": "ncslballotmeasures_icpsr_1902_2016.csv",
        "search_paths": [
            DATA_DIR / "downloaded",
            BASE_DIR / "downloaded",
            BASE_DIR.parent / "downloaded"
        ]
    }
}

# Export formats
EXPORT_FORMATS = ["json", "csv", "excel"]

# Deduplication settings
DEDUP_CONFIG = {
    "fingerprint_fields": ["year", "measure_id", "county", "source"],
    "content_fields": ["title", "ballot_question", "description"],
    "cross_source_matching": True
}