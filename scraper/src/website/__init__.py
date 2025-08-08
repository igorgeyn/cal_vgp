# src/website/__init__.py
"""
Website generation for California ballot measures
"""
from .generator import WebsiteGenerator

__all__ = ['WebsiteGenerator']

# Available website styles
AVAILABLE_STYLES = ['modern', 'clean', 'newspaper']

def get_default_style():
    """Get the default website style"""
    return 'modern'
