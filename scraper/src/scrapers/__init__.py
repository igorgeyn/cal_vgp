# src/scrapers/__init__.py
"""
Web scrapers for California ballot measures
"""
from .base import BaseScraper
from .ca_sos import CASOSScraper
from .ballotpedia_statewide import BallotpediaStatewideScraper
from .ballotpedia_counties import BallotpediaCountyScraper

__all__ = ['BaseScraper', 'CASOSScraper', 'BallotpediaStatewideScraper', 'BallotpediaCountyScraper']
