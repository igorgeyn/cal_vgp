# src/scrapers/__init__.py
"""
Web scrapers for California ballot measures
"""
from .base import BaseScraper
from .ca_sos import CASOSScraper

__all__ = ['BaseScraper', 'CASOSScraper']
