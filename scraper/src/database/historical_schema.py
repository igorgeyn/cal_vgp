"""
Schema for California historical ballot measures (1902-2020+)
Based on NCSL/Ballotpedia combined dataset spec
"""

HISTORICAL_SCHEMA = """
-- California Historical Ballot Measures
-- Source: NCSL + Ballotpedia combined dataset
-- Coverage: 1902-2020 (display 1970+ in UI)

CREATE TABLE IF NOT EXISTS ca_historical_measures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Core identification
    ballot_name TEXT,                    -- e.g., "Prop 64", "Measure A"
    year INTEGER NOT NULL,
    description TEXT,                    -- Full ballot description

    -- Vote results
    pct_yes REAL,                        -- Percentage voting yes (cleaned, no % symbol)
    passed BOOLEAN,                      -- 1 = passed, 0 = failed

    -- Measure classification
    measure_type TEXT,                   -- "Initiative", "Referendum", "Legislative Referendum"
    election_type TEXT,                  -- "General", "Primary", "Special"

    -- Topic flags (a measure can have multiple = TRUE)
    is_marijuana BOOLEAN DEFAULT FALSE,
    is_gambling BOOLEAN DEFAULT FALSE,
    is_abortion BOOLEAN DEFAULT FALSE,
    is_marriage BOOLEAN DEFAULT FALSE,   -- Derived via text search
    is_tax BOOLEAN DEFAULT FALSE,
    is_education BOOLEAN DEFAULT FALSE,  -- Combines K-12 and Higher Ed
    is_health BOOLEAN DEFAULT FALSE,
    is_elections BOOLEAN DEFAULT FALSE,
    is_criminal BOOLEAN DEFAULT FALSE,
    is_environment BOOLEAN DEFAULT FALSE,

    -- Computed fields
    margin REAL,                         -- pct_yes - 50 (positive = passed margin)
    is_close BOOLEAN,                    -- ABS(margin) < 10
    is_very_close BOOLEAN,               -- ABS(margin) < 5
    is_initiative BOOLEAN,               -- measure_type contains "Initiative"
    is_referendum BOOLEAN,               -- measure_type contains "Referendum"

    -- Future expansion (nullable)
    campaign_spending REAL,
    source_dataset TEXT,                 -- "NCSL", "Ballotpedia", "UC_Law", etc.

    -- Tracking
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_hist_year ON ca_historical_measures(year);
CREATE INDEX IF NOT EXISTS idx_hist_passed ON ca_historical_measures(passed);
CREATE INDEX IF NOT EXISTS idx_hist_marijuana ON ca_historical_measures(is_marijuana);
CREATE INDEX IF NOT EXISTS idx_hist_gambling ON ca_historical_measures(is_gambling);
CREATE INDEX IF NOT EXISTS idx_hist_abortion ON ca_historical_measures(is_abortion);
CREATE INDEX IF NOT EXISTS idx_hist_marriage ON ca_historical_measures(is_marriage);
CREATE INDEX IF NOT EXISTS idx_hist_tax ON ca_historical_measures(is_tax);
CREATE INDEX IF NOT EXISTS idx_hist_education ON ca_historical_measures(is_education);
CREATE INDEX IF NOT EXISTS idx_hist_health ON ca_historical_measures(is_health);
CREATE INDEX IF NOT EXISTS idx_hist_elections ON ca_historical_measures(is_elections);
CREATE INDEX IF NOT EXISTS idx_hist_criminal ON ca_historical_measures(is_criminal);
CREATE INDEX IF NOT EXISTS idx_hist_environment ON ca_historical_measures(is_environment);

-- Composite index for topic + year queries
CREATE INDEX IF NOT EXISTS idx_hist_year_marijuana ON ca_historical_measures(year, is_marijuana);
CREATE INDEX IF NOT EXISTS idx_hist_year_gambling ON ca_historical_measures(year, is_gambling);

-- Full-text search on descriptions
CREATE VIRTUAL TABLE IF NOT EXISTS ca_historical_search
USING fts5(
    id UNINDEXED,
    ballot_name,
    description,
    content='ca_historical_measures',
    content_rowid='id'
);

-- View for measures from 1970 onward (display filter)
CREATE VIEW IF NOT EXISTS ca_historical_modern AS
SELECT * FROM ca_historical_measures
WHERE year >= 1970
ORDER BY year DESC, ballot_name;

-- View for topic statistics
CREATE VIEW IF NOT EXISTS ca_topic_stats AS
SELECT
    'marijuana' as topic,
    COUNT(*) as total_measures,
    MIN(year) as first_year,
    MAX(year) as last_year,
    ROUND(AVG(CASE WHEN passed = 1 THEN 1.0 ELSE 0.0 END) * 100, 1) as pass_rate,
    ROUND(AVG(pct_yes), 1) as avg_yes_pct
FROM ca_historical_measures WHERE is_marijuana = 1 AND year >= 1970
UNION ALL
SELECT
    'gambling' as topic,
    COUNT(*), MIN(year), MAX(year),
    ROUND(AVG(CASE WHEN passed = 1 THEN 1.0 ELSE 0.0 END) * 100, 1),
    ROUND(AVG(pct_yes), 1)
FROM ca_historical_measures WHERE is_gambling = 1 AND year >= 1970
UNION ALL
SELECT
    'abortion' as topic,
    COUNT(*), MIN(year), MAX(year),
    ROUND(AVG(CASE WHEN passed = 1 THEN 1.0 ELSE 0.0 END) * 100, 1),
    ROUND(AVG(pct_yes), 1)
FROM ca_historical_measures WHERE is_abortion = 1 AND year >= 1970
UNION ALL
SELECT
    'marriage' as topic,
    COUNT(*), MIN(year), MAX(year),
    ROUND(AVG(CASE WHEN passed = 1 THEN 1.0 ELSE 0.0 END) * 100, 1),
    ROUND(AVG(pct_yes), 1)
FROM ca_historical_measures WHERE is_marriage = 1 AND year >= 1970
UNION ALL
SELECT
    'tax' as topic,
    COUNT(*), MIN(year), MAX(year),
    ROUND(AVG(CASE WHEN passed = 1 THEN 1.0 ELSE 0.0 END) * 100, 1),
    ROUND(AVG(pct_yes), 1)
FROM ca_historical_measures WHERE is_tax = 1 AND year >= 1970
UNION ALL
SELECT
    'education' as topic,
    COUNT(*), MIN(year), MAX(year),
    ROUND(AVG(CASE WHEN passed = 1 THEN 1.0 ELSE 0.0 END) * 100, 1),
    ROUND(AVG(pct_yes), 1)
FROM ca_historical_measures WHERE is_education = 1 AND year >= 1970
UNION ALL
SELECT
    'health' as topic,
    COUNT(*), MIN(year), MAX(year),
    ROUND(AVG(CASE WHEN passed = 1 THEN 1.0 ELSE 0.0 END) * 100, 1),
    ROUND(AVG(pct_yes), 1)
FROM ca_historical_measures WHERE is_health = 1 AND year >= 1970
UNION ALL
SELECT
    'elections' as topic,
    COUNT(*), MIN(year), MAX(year),
    ROUND(AVG(CASE WHEN passed = 1 THEN 1.0 ELSE 0.0 END) * 100, 1),
    ROUND(AVG(pct_yes), 1)
FROM ca_historical_measures WHERE is_elections = 1 AND year >= 1970
UNION ALL
SELECT
    'criminal' as topic,
    COUNT(*), MIN(year), MAX(year),
    ROUND(AVG(CASE WHEN passed = 1 THEN 1.0 ELSE 0.0 END) * 100, 1),
    ROUND(AVG(pct_yes), 1)
FROM ca_historical_measures WHERE is_criminal = 1 AND year >= 1970
UNION ALL
SELECT
    'environment' as topic,
    COUNT(*), MIN(year), MAX(year),
    ROUND(AVG(CASE WHEN passed = 1 THEN 1.0 ELSE 0.0 END) * 100, 1),
    ROUND(AVG(pct_yes), 1)
FROM ca_historical_measures WHERE is_environment = 1 AND year >= 1970;
"""

# Topic configuration with priority order and display info
TOPIC_CONFIG = {
    'marijuana': {
        'column': 'is_marijuana',
        'label': 'Marijuana/Cannabis',
        'priority': 1,
        'color': '#22c55e',  # green
        'icon': '🌿',
    },
    'gambling': {
        'column': 'is_gambling',
        'label': 'Gambling',
        'priority': 2,
        'color': '#eab308',  # yellow
        'icon': '🎰',
    },
    'abortion': {
        'column': 'is_abortion',
        'label': 'Abortion',
        'priority': 3,
        'color': '#ec4899',  # pink
        'icon': '⚕️',
    },
    'marriage': {
        'column': 'is_marriage',
        'label': 'Marriage Equality',
        'priority': 4,
        'color': '#8b5cf6',  # purple
        'icon': '💒',
    },
    'tax': {
        'column': 'is_tax',
        'label': 'Tax/Fiscal',
        'priority': 5,
        'color': '#f97316',  # orange
        'icon': '💰',
    },
    'education': {
        'column': 'is_education',
        'label': 'Education',
        'priority': 6,
        'color': '#3b82f6',  # blue
        'icon': '📚',
    },
    'health': {
        'column': 'is_health',
        'label': 'Healthcare',
        'priority': 7,
        'color': '#ef4444',  # red
        'icon': '🏥',
    },
    'elections': {
        'column': 'is_elections',
        'label': 'Election Reform',
        'priority': 8,
        'color': '#6366f1',  # indigo
        'icon': '🗳️',
    },
    'criminal': {
        'column': 'is_criminal',
        'label': 'Criminal Justice',
        'priority': 9,
        'color': '#64748b',  # slate
        'icon': '⚖️',
    },
    'environment': {
        'column': 'is_environment',
        'label': 'Environment',
        'priority': 10,
        'color': '#14b8a6',  # teal
        'icon': '🌍',
    },
}

# Minimum measures required to show topic in filters
MIN_MEASURES_FOR_FILTER = 3
