# src/api/__init__.py
"""
REST API for California ballot measures database
"""
from .server import app

__all__ = ['app']

# API metadata
API_VERSION = "1.0.0"
API_TITLE = "California Ballot Measures API"
API_DESCRIPTION = "REST API for accessing historical California ballot measure data"