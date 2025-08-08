# src/parsers/__init__.py
"""
Data parsers for various ballot measure data sources
"""
from .ceda import CEDAParser
from .ncsl import NCSLParser
from .icpsr import ICPSRParser

__all__ = ['CEDAParser', 'NCSLParser', 'ICPSRParser']

def get_parser(source_type, data_dir):
    """Factory function to get appropriate parser"""
    parsers = {
        'ceda': CEDAParser,
        'ncsl': NCSLParser,
        'icpsr': ICPSRParser
    }
    
    parser_class = parsers.get(source_type.lower())
    if parser_class:
        return parser_class(data_dir)
    else:
        raise ValueError(f"Unknown parser type: {source_type}")
