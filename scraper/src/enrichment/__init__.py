# src/enrichment/__init__.py
"""
Data enrichment modules for ballot measures
"""
from .summaries import SummaryGenerator

__all__ = ['SummaryGenerator']

def enrich_measure(measure_data):
    """
    Enrich a single measure with additional data
    
    Args:
        measure_data: Dictionary containing measure information
    
    Returns:
        Enriched measure dictionary
    """
    generator = SummaryGenerator()
    
    # Add summary if not present
    if not measure_data.get('summary_text'):
        summary_info = generator.generate_summary(measure_data)
        if summary_info:
            measure_data['summary_title'] = summary_info.get('title')
            measure_data['summary_text'] = summary_info.get('summary')
            measure_data['has_summary'] = True
    
    return measure_data
