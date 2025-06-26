#!/usr/bin/env python3
"""
Configuration for the Enhanced Ballot Measures Pipeline
Customize summary generation and scraping behavior
"""

# SCRAPING CONFIGURATION
SCRAPING_CONFIG = {
    # Maximum number of historical measures to scrape from UC Law SF
    'max_historical_measures': 30,
    
    # Delay between requests (in seconds) to be respectful to servers
    'request_delay': 1.0,
    
    # Timeout for web requests (in seconds)
    'request_timeout': 30,
    
    # Sources to scrape from
    'sources': {
        'ca_sos': True,        # California Secretary of State
        'uclsf': True,         # UC Law SF repository
        # Add more sources here as they become available
    }
}

# SUMMARY GENERATION CONFIGURATION
SUMMARY_CONFIG = {
    # Maximum number of measures to attempt summary generation for
    # (to avoid overwhelming external services)
    'max_summary_attempts': 10,
    
    # Delay between summary generation attempts (in seconds)
    'summary_rate_limit': 2.0,
    
    # Prioritize summary generation for these years (most recent first)
    'priority_years': ['2026', '2025', '2024'],
    
    # Always attempt summaries for measures containing these keywords
    'priority_keywords': ['ACA', 'SCA', 'Proposition'],
    
    # Pre-built summaries for known measures
    'known_summaries': {
        "ACA 13": {
            "title": "Protect and Retain the Majority Vote Act",
            "summary": "Would require that ballot measures proposing to increase voting thresholds for future measures must themselves pass by the same increased threshold they seek to impose. Currently, a simple majority can pass a measure requiring supermajority votes for future actions, giving disproportionate power to a minority of voters. The measure aims to prevent abuse of the initiative process and protect local control by ensuring that statewide voters cannot easily override local decision-making with artificially high voting requirements."
        },
        "SCA 1": {
            "title": "Recall Process Reform",
            "summary": "Would reform California's recall process by eliminating the simultaneous successor election that currently appears on recall ballots. Under the current system, voters decide both whether to recall an officer and who should replace them, allowing a replacement to be chosen by a slim plurality rather than majority support. If adopted, when a state officer is recalled, the office would be filled according to existing constitutional succession rules (such as the Lieutenant Governor becoming Governor), removing what supporters call political gamesmanship from the recall process."
        }
        # Add more known summaries here as you research them
    }
}

# WEBSITE GENERATION CONFIGURATION  
WEBSITE_CONFIG = {
    # Output file name for the generated website
    'output_filename': 'enhanced_ballot_measures.html',
    
    # Whether to sort measures with summaries first within each year
    'prioritize_summaries': True,
    
    # Maximum length for measure titles before truncation
    'max_title_length': 120,
    
    # Website styling theme
    'theme': 'clean',  # Options: 'clean', 'newspaper', 'modern'
    
    # Whether to include statistics in the header
    'show_statistics': True,
    
    # Whether to include year-level statistics
    'show_year_stats': True
}

# FILE PATHS CONFIGURATION
PATHS_CONFIG = {
    # Directory for storing scraped data
    'data_directory': 'data',
    
    # Input HTML template file (if you have a custom template)
    'html_template': 'ballot_measures_site.html',
    
    # Output files
    'enhanced_json': 'data/enhanced_measures.json',
    'enhanced_csv': 'data/enhanced_measures.csv',
    'basic_json': 'data/all_measures.json',
    'website_output': 'enhanced_ballot_measures_final.html'
}

# EXTERNAL SERVICES CONFIGURATION
EXTERNAL_CONFIG = {
    # If you want to integrate with external APIs for summary generation
    # (currently not implemented, but ready for future expansion)
    'use_external_apis': False,
    
    # API keys would go here (store in environment variables in practice)
    'api_keys': {
        # 'openai_api_key': 'your_key_here',
        # 'google_search_api_key': 'your_key_here',
    }
}

# LOGGING CONFIGURATION
LOGGING_CONFIG = {
    # Verbosity level: 'minimal', 'normal', 'verbose', 'debug'
    'verbosity': 'normal',
    
    # Whether to save logs to file
    'log_to_file': False,
    
    # Log file path (if log_to_file is True)
    'log_file': 'data/pipeline.log'
}

# UTILITY FUNCTIONS
def get_config(config_name):
    """Get a specific configuration dictionary"""
    configs = {
        'scraping': SCRAPING_CONFIG,
        'summary': SUMMARY_CONFIG,
        'website': WEBSITE_CONFIG,
        'paths': PATHS_CONFIG,
        'external': EXTERNAL_CONFIG,
        'logging': LOGGING_CONFIG
    }
    return configs.get(config_name, {})

def update_config(config_name, key, value):
    """Update a configuration value"""
    config = get_config(config_name)
    if config and key in config:
        config[key] = value
        return True
    return False

def add_known_summary(measure_key, title, summary):
    """Add a new summary to the known summaries"""
    SUMMARY_CONFIG['known_summaries'][measure_key] = {
        'title': title,
        'summary': summary
    }

# Example usage:
if __name__ == "__main__":
    print("🔧 PIPELINE CONFIGURATION")
    print("=" * 40)
    
    print(f"📊 Scraping Configuration:")
    for key, value in SCRAPING_CONFIG.items():
        print(f"   {key}: {value}")
    
    print(f"\n📝 Summary Configuration:")
    print(f"   Max attempts: {SUMMARY_CONFIG['max_summary_attempts']}")
    print(f"   Rate limit: {SUMMARY_CONFIG['summary_rate_limit']}s")
    print(f"   Known summaries: {len(SUMMARY_CONFIG['known_summaries'])}")
    
    print(f"\n🌐 Website Configuration:")
    for key, value in WEBSITE_CONFIG.items():
        print(f"   {key}: {value}")
    
    print(f"\n💾 Current known summaries:")
    for measure, info in SUMMARY_CONFIG['known_summaries'].items():
        print(f"   • {measure}: {info['title']}")
    
    print("\n🔄 To customize, edit this file directly or use the utility functions.")