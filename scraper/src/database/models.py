"""
Database models and schema definitions
"""
from dataclasses import dataclass
from typing import Optional, Dict, List
from datetime import datetime
import hashlib
import re


@dataclass
class BallotMeasure:
    """Main ballot measure data model"""
    # Core identification
    fingerprint: str  # Unique fingerprint for deduplication
    measure_fingerprint: str  # Cross-source matching fingerprint
    content_hash: str  # Content-based hash
    
    # Basic information
    measure_id: Optional[str] = None
    measure_letter: Optional[str] = None
    year: Optional[int] = None
    state: str = "CA"
    county: str = "Statewide"
    jurisdiction: Optional[str] = None
    
    # Measure content
    title: Optional[str] = None
    description: Optional[str] = None
    ballot_question: Optional[str] = None
    
    # Vote results
    yes_votes: Optional[int] = None
    no_votes: Optional[int] = None
    total_votes: Optional[int] = None
    percent_yes: Optional[float] = None
    percent_no: Optional[float] = None
    passed: Optional[bool] = None
    pass_fail: Optional[str] = None
    
    # Classification
    measure_type: Optional[str] = None
    topic_primary: Optional[str] = None
    topic_secondary: Optional[str] = None
    category_type: Optional[str] = None
    category_topic: Optional[str] = None
    
    # Source tracking
    data_source: str = "Unknown"
    source_url: Optional[str] = None
    pdf_url: Optional[str] = None
    
    # Summary data
    has_summary: bool = False
    summary_title: Optional[str] = None
    summary_text: Optional[str] = None
    
    # Metadata
    election_type: Optional[str] = None
    election_date: Optional[datetime] = None
    decade: Optional[int] = None
    century: Optional[int] = None
    
    # Tracking
    created_at: datetime = datetime.now()
    updated_at: datetime = datetime.now()
    last_seen_at: datetime = datetime.now()
    update_count: int = 0
    
    # Deduplication flags
    is_active: bool = True
    is_duplicate: bool = False
    duplicate_type: Optional[str] = None
    master_id: Optional[int] = None
    merged_from: Optional[List[int]] = None
    
    def __post_init__(self):
        """Post-initialization processing"""
        # Calculate decade and century if year is provided
        if self.year and isinstance(self.year, int):
            self.decade = (self.year // 10) * 10
            self.century = ((self.year - 1) // 100) + 1
            
        # Generate fingerprints if not provided
        if not self.fingerprint:
            self.generate_fingerprints()
    
    def generate_fingerprints(self):
        """Generate fingerprints for deduplication"""
        # Extract measure identifier
        measure_id = self.extract_measure_identifier()
        
        # Create fingerprints
        self.fingerprint = f"{self.year}|{measure_id}|{self.county}|{self.data_source}"
        self.measure_fingerprint = f"{self.year}|{measure_id}|{self.county}"
        
        # Content hash
        content_parts = [
            str(self.title or ''),
            str(self.ballot_question or ''),
            str(self.description or '')
        ]
        content_str = '|'.join(content_parts).lower().strip()
        self.content_hash = hashlib.md5(content_str.encode()).hexdigest()[:16]
    
    def extract_measure_identifier(self) -> str:
        """Extract standardized measure identifier"""
        text = self.title or self.ballot_question or ''
        if not text:
            return "UNKNOWN"
            
        # Patterns to match various measure formats
        patterns = [
            (r'(?:Proposition|Prop\.?)\s*(\d+[A-Z]?)', 'PROP_{}'),
            (r'([AS]CA)\s*(\d+)', '{}_{}'),
            (r'(AB|SB)\s*(\d+)', '{}_{}'),
            (r'(?:Measure)\s*([A-Z]+)', 'MEASURE_{}'),
        ]
        
        for pattern, format_str in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                groups = match.groups()
                return format_str.format(*groups).upper()
                
        # Use measure_id or measure_letter if available
        if self.measure_id:
            return f"ID_{self.measure_id}"
        elif self.measure_letter:
            return f"MEASURE_{self.measure_letter}"
            
        # Last resort: hash of content
        return f"HASH_{self.content_hash[:8]}"
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for storage"""
        data = {}
        for field in self.__dataclass_fields__:
            value = getattr(self, field)
            if isinstance(value, datetime):
                value = value.isoformat()
            data[field] = value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'BallotMeasure':
        """Create from dictionary"""
        # Convert datetime strings back to datetime objects
        for field in ['created_at', 'updated_at', 'last_seen_at', 'election_date']:
            if field in data and isinstance(data[field], str):
                try:
                    data[field] = datetime.fromisoformat(data[field])
                except:
                    pass
                    
        return cls(**data)


# Database schema for SQLite
SCHEMA = """
CREATE TABLE IF NOT EXISTS measures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Unique fingerprint for deduplication
    fingerprint TEXT UNIQUE,
    measure_fingerprint TEXT,
    content_hash TEXT,
    
    -- Core fields
    measure_id TEXT,
    measure_letter TEXT,
    year INTEGER NOT NULL,
    state TEXT DEFAULT 'CA',
    county TEXT DEFAULT 'Statewide',
    jurisdiction TEXT,
    title TEXT,
    description TEXT,
    ballot_question TEXT,
    
    -- Vote results
    yes_votes INTEGER,
    no_votes INTEGER,
    total_votes INTEGER,
    percent_yes REAL,
    percent_no REAL,
    passed INTEGER,
    pass_fail TEXT,
    
    -- Classification
    measure_type TEXT,
    topic_primary TEXT,
    topic_secondary TEXT,
    category_type TEXT,
    category_topic TEXT,
    
    -- Source tracking
    data_source TEXT NOT NULL,
    source_url TEXT,
    pdf_url TEXT,
    
    -- Summary data
    has_summary BOOLEAN DEFAULT 0,
    summary_title TEXT,
    summary_text TEXT,
    
    -- Metadata
    election_type TEXT,
    election_date DATE,
    decade INTEGER,
    century INTEGER,
    
    -- Tracking
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    update_count INTEGER DEFAULT 0,
    
    -- Status flags
    is_active BOOLEAN DEFAULT 1,
    is_duplicate BOOLEAN DEFAULT 0,
    duplicate_type TEXT,
    master_id INTEGER,
    merged_from TEXT,
    
    FOREIGN KEY(master_id) REFERENCES measures(id)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_fingerprint ON measures(fingerprint);
CREATE INDEX IF NOT EXISTS idx_measure_fingerprint ON measures(measure_fingerprint);
CREATE INDEX IF NOT EXISTS idx_year ON measures(year);
CREATE INDEX IF NOT EXISTS idx_county ON measures(county);
CREATE INDEX IF NOT EXISTS idx_passed ON measures(passed);
CREATE INDEX IF NOT EXISTS idx_topic ON measures(topic_primary);
CREATE INDEX IF NOT EXISTS idx_source ON measures(data_source);
CREATE INDEX IF NOT EXISTS idx_has_summary ON measures(has_summary);
CREATE INDEX IF NOT EXISTS idx_content_hash ON measures(content_hash);
CREATE INDEX IF NOT EXISTS idx_is_duplicate ON measures(is_duplicate);

-- Full-text search
CREATE VIRTUAL TABLE IF NOT EXISTS measure_search 
USING fts5(
    fingerprint UNINDEXED,
    title,
    description,
    ballot_question,
    summary_title,
    summary_text,
    county,
    content='measures',
    content_rowid='id'
);

-- Update tracking
CREATE TABLE IF NOT EXISTS measure_updates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    measure_id INTEGER NOT NULL,
    field_name TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    update_source TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(measure_id) REFERENCES measures(id)
);

-- Scraper runs
CREATE TABLE IF NOT EXISTS scraper_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_type TEXT NOT NULL,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    measures_checked INTEGER DEFAULT 0,
    new_measures INTEGER DEFAULT 0,
    updated_measures INTEGER DEFAULT 0,
    duplicates_found INTEGER DEFAULT 0,
    status TEXT,
    error_message TEXT
);

-- Views for easy querying
CREATE VIEW IF NOT EXISTS active_measures AS
SELECT * FROM measures 
WHERE is_active = 1 AND is_duplicate = 0
ORDER BY year DESC, county, measure_letter;

CREATE VIEW IF NOT EXISTS measure_stats AS
SELECT 
    year,
    COUNT(*) as total_measures,
    COUNT(DISTINCT county) as counties,
    SUM(CASE WHEN passed = 1 THEN 1 ELSE 0 END) as passed_count,
    SUM(CASE WHEN passed = 0 THEN 1 ELSE 0 END) as failed_count,
    SUM(CASE WHEN has_summary = 1 THEN 1 ELSE 0 END) as with_summaries,
    SUM(CASE WHEN yes_votes IS NOT NULL THEN 1 ELSE 0 END) as with_votes,
    ROUND(AVG(percent_yes), 1) as avg_percent_yes
FROM active_measures
GROUP BY year
ORDER BY year DESC;
"""