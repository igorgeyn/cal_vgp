"""
California Ballot Measures System
A comprehensive tool for collecting, analyzing, and presenting California ballot measures.
"""

__version__ = "2.0.0"
__author__ = "California Ballot Measures Project"

import logging
from pathlib import Path
from .config import LOG_LEVEL, LOG_FORMAT, LOG_FILE

# Set up logging
LOG_FILE.parent.mkdir(exist_ok=True)

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format=LOG_FORMAT,
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)
logger.info(f"California Ballot Measures System v{__version__} initialized")

# Convenience imports
from .scrapers import BaseScraper, CASOSScraper
from .database import Database
from .website import WebsiteGenerator

__all__ = ["Scraper", "Database", "WebsiteGenerator", "__version__"]