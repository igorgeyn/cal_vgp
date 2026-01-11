"""
California Regional Groupings
Organized by major metropolitan and geographic regions
"""

CA_REGIONS = {
    "Greater Bay Area": {
        "counties": [
            "ALAMEDA",
            "CONTRA COSTA",
            "MARIN",
            "NAPA",
            "SAN FRANCISCO",
            "SAN MATEO",
            "SANTA CLARA",
            "SOLANO",
            "SONOMA"
        ],
        "emoji": "🌉",
        "description": "San Francisco Bay Area & Silicon Valley"
    },
    "Greater Los Angeles": {
        "counties": [
            "LOS ANGELES",
            "ORANGE",
            "VENTURA",
            "RIVERSIDE",
            "SAN BERNARDINO"
        ],
        "emoji": "🌴",
        "description": "Los Angeles, Orange County & Inland Empire"
    },
    "San Diego Region": {
        "counties": [
            "SAN DIEGO",
            "IMPERIAL"
        ],
        "emoji": "🏖️",
        "description": "San Diego & Imperial Valley"
    },
    "Central Valley": {
        "counties": [
            "FRESNO",
            "KERN",
            "KINGS",
            "MADERA",
            "MERCED",
            "SAN JOAQUIN",
            "STANISLAUS",
            "TULARE"
        ],
        "emoji": "🌾",
        "description": "Agricultural heartland from Stockton to Bakersfield"
    },
    "Sacramento Region": {
        "counties": [
            "SACRAMENTO",
            "PLACER",
            "EL DORADO",
            "YOLO",
            "SUTTER",
            "YUBA"
        ],
        "emoji": "🏛️",
        "description": "State capital region & Sierra foothills"
    },
    "Central Coast": {
        "counties": [
            "MONTEREY",
            "SAN LUIS OBISPO",
            "SANTA BARBARA",
            "SANTA CRUZ",
            "SAN BENITO"
        ],
        "emoji": "🌊",
        "description": "Coastal region from Santa Cruz to Santa Barbara"
    },
    "North Coast": {
        "counties": [
            "MENDOCINO",
            "HUMBOLDT",
            "DEL NORTE",
            "LAKE"
        ],
        "emoji": "🌲",
        "description": "Redwood country & wine regions"
    },
    "Northern California": {
        "counties": [
            "SHASTA",
            "TEHAMA",
            "BUTTE",
            "GLENN",
            "COLUSA",
            "TRINITY",
            "SISKIYOU",
            "MODOC",
            "LASSEN",
            "PLUMAS"
        ],
        "emoji": "⛰️",
        "description": "Rural northern counties & Cascade Range"
    },
    "Eastern Sierra": {
        "counties": [
            "MONO",
            "INYO",
            "ALPINE",
            "AMADOR",
            "CALAVERAS",
            "TUOLUMNE",
            "MARIPOSA",
            "NEVADA",
            "SIERRA"
        ],
        "emoji": "🏔️",
        "description": "Sierra Nevada mountains & eastern desert"
    }
}

def get_region_for_county(county_name):
    """Get the region name for a given county"""
    if not county_name:
        return None

    county_upper = county_name.upper()
    for region, data in CA_REGIONS.items():
        if county_upper in data["counties"]:
            return region
    return "Other"

def get_all_counties_sorted():
    """Get all unique counties sorted alphabetically"""
    all_counties = set()
    for region_data in CA_REGIONS.values():
        all_counties.update(region_data["counties"])
    return sorted(all_counties)

def get_region_stats(measures):
    """Calculate statistics for each region"""
    stats = {}

    for region, data in CA_REGIONS.items():
        region_measures = [
            m for m in measures
            if m.get('county') and m['county'].upper() in data['counties']
        ]

        stats[region] = {
            "count": len(region_measures),
            "with_votes": sum(1 for m in region_measures if m.get('votes_for')),
            "with_summaries": sum(1 for m in region_measures if m.get('has_summary')),
            "emoji": data["emoji"],
            "description": data["description"]
        }

    return stats
