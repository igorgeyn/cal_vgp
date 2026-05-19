"""
FastAPI REST API for California Ballot Measures Database
Provides endpoints for querying and analyzing ballot measure data
"""
from fastapi import FastAPI, Query, HTTPException, Path as PathParam
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from pathlib import Path
import logging

# Add parent directory for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.config import DB_PATH, VERSION, API_PORT
from src.database.operations import Database
from src.database.models import BallotMeasure

# Historical context modules are optional — they were planned but not yet implemented.
# The core API endpoints work without them; historical endpoints will return 501.
try:
    from src.database.historical_operations import HistoricalDatabase
    from src.database.historical_schema import TOPIC_CONFIG, MIN_MEASURES_FOR_FILTER
    HISTORICAL_AVAILABLE = True
except ImportError:
    HistoricalDatabase = None
    TOPIC_CONFIG = {}
    MIN_MEASURES_FOR_FILTER = 3
    HISTORICAL_AVAILABLE = False

# Finance modules are optional — finance endpoints return 501 if unavailable.
try:
    from src.finance.operations import FinanceDatabase
    from src.finance.schema import FINANCE_DB_PATH
    FINANCE_AVAILABLE = True
except ImportError:
    FinanceDatabase = None
    FINANCE_DB_PATH = None
    FINANCE_AVAILABLE = False

# Finance kill-switch. Was True 2026-05-04 during the data rebuild;
# flipped False once year-scoped finance_campaign_id was wired in.
# Endpoints still take a bare measure_id from the URL — that lookup may
# need (measure_id, year) disambiguation for PROP_1, but the v2 schema
# returns one campaign per (measure_id, year) so URL params can be
# extended later if it bites.
FINANCE_DISABLED_PENDING_REBUILD = False

# Set up logging
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="California Ballot Measures API",
    description="REST API for accessing historical California ballot measure data",
    version=VERSION,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Global database connections
db_ops = None
historical_db = None
finance_db = None

@app.on_event("startup")
async def startup_event():
    """Initialize database connection on startup"""
    global db_ops, historical_db, finance_db
    if not DB_PATH.exists():
        logger.error(f"Database not found at {DB_PATH}")
        raise RuntimeError("Database not initialized")
    db_ops = Database(DB_PATH)
    if HISTORICAL_AVAILABLE:
        historical_db = HistoricalDatabase(DB_PATH)
        logger.info("API server started with historical context support")
    else:
        logger.warning("Historical context modules not available — historical endpoints disabled")
    if FINANCE_AVAILABLE and FINANCE_DB_PATH and FINANCE_DB_PATH.exists():
        finance_db = FinanceDatabase(FINANCE_DB_PATH)
        logger.info("Finance database loaded")
    else:
        logger.warning("Finance database not available — finance endpoints disabled")
    logger.info("API server started successfully")

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on shutdown"""
    global historical_db, finance_db
    if historical_db:
        historical_db.close()
    if finance_db:
        finance_db.close()
    logger.info("API server shutting down")

# Response models
class MeasureResponse(BaseModel):
    """Response model for a single ballot measure"""
    id: int
    fingerprint: str
    year: Optional[int]
    state: str = "CA"
    county: Optional[str]
    title: Optional[str]
    description: Optional[str]
    summary_text: Optional[str]
    measure_type: Optional[str]
    topic_primary: Optional[str]
    percent_yes: Optional[float]
    passed: Optional[int]
    pass_fail: Optional[str]
    yes_votes: Optional[int]
    no_votes: Optional[int]
    total_votes: Optional[int]
    data_source: str
    pdf_url: Optional[str]
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class SearchRequest(BaseModel):
    """Request model for search endpoint"""
    query: Optional[str] = Field(None, description="Search query text")
    year_min: Optional[int] = Field(None, ge=1900, le=2030)
    year_max: Optional[int] = Field(None, ge=1900, le=2030)
    county: Optional[str] = None
    passed: Optional[bool] = None
    has_summary: Optional[bool] = None
    has_votes: Optional[bool] = None
    topic: Optional[str] = None
    source: Optional[str] = None
    limit: int = Field(100, ge=1, le=1000)
    offset: int = Field(0, ge=0)

class StatsResponse(BaseModel):
    """Response model for statistics"""
    total_measures: int
    with_summaries: int
    with_votes: int
    passed: int
    failed: int
    unknown: int = 0
    year_min: Optional[int]
    year_max: Optional[int]
    sources: List[str]
    by_source: Optional[Dict[str, int]] = None
    counties: int
    topics: int


# Historical Context Response Models

class MostRecentMeasure(BaseModel):
    """Most recent measure in a topic"""
    id: int
    ballot_name: str
    year: int
    description: Optional[str]
    pct_yes: Optional[float]
    passed: Optional[bool]
    margin: Optional[float]


class TopicContextResponse(BaseModel):
    """
    Historical context for a topic.
    All statistics are descriptive only - they describe what happened historically,
    not predictions of future outcomes.
    """
    topic: str
    topic_label: str
    total_measures: int
    first_year: int
    last_year: int
    pass_rate: float  # Percentage (0-100)
    avg_yes_pct: float
    passed_count: int
    failed_count: int
    most_recent: Optional[MostRecentMeasure]
    # UI helper fields
    color: str
    icon: str


class TopicTagResponse(BaseModel):
    """Topic tag with metadata for UI display"""
    topic: str
    label: str
    color: str
    icon: str
    priority: int
    is_primary: bool = False


class HistoricalMeasureResponse(BaseModel):
    """Historical measure with topic tags"""
    id: int
    ballot_name: str
    year: int
    description: str
    description_truncated: str  # First 100 chars
    pct_yes: Optional[float]
    passed: Optional[bool]
    measure_type: str
    election_type: str
    topics: List[TopicTagResponse]
    primary_topic: Optional[str]
    margin: Optional[float]
    margin_label: str  # "Landslide", "Comfortable", "Close", "Very Close"
    is_close: bool


class TopicStatsResponse(BaseModel):
    """Statistics for all topics"""
    topic: str
    label: str
    color: str
    icon: str
    priority: int
    total_measures: int
    first_year: int
    pass_rate: float
    avg_yes_pct: float

# API Endpoints

@app.get("/", tags=["General"])
async def root():
    """Root endpoint with API information"""
    return {
        "name": "California Ballot Measures API",
        "version": VERSION,
        "documentation": "/docs",
        "endpoints": {
            "measures": "/api/measures",
            "search": "/api/search",
            "statistics": "/api/stats",
            "measure_by_id": "/api/measures/{id}",
            "years": "/api/years",
            "topics": "/api/topics",
            "export": "/api/export"
        }
    }

@app.get("/api/measures", response_model=List[MeasureResponse], tags=["Measures"])
async def get_measures(
    year: Optional[int] = Query(None, description="Filter by year"),
    county: Optional[str] = Query(None, description="Filter by county"),
    passed: Optional[bool] = Query(None, description="Filter by pass/fail status"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum results to return"),
    offset: int = Query(0, ge=0, description="Number of results to skip")
):
    """Get a list of ballot measures with optional filters"""
    try:
        filters = {}
        if year:
            filters['year'] = year
        if county:
            filters['county'] = county
        if passed is not None:
            filters['passed'] = 1 if passed else 0
        
        measures = db_ops.search_measures(
            limit=limit,
            offset=offset,
            **filters
        )
        
        return measures
    except Exception as e:
        logger.error(f"Error fetching measures: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/api/measures/{measure_id}", response_model=MeasureResponse, tags=["Measures"])
async def get_measure(measure_id: int = PathParam(..., description="Measure database ID")):
    """Get a specific measure by ID"""
    try:
        measure = db_ops.get_measure(measure_id)
        if not measure:
            raise HTTPException(status_code=404, detail="Measure not found")
        return measure
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching measure {measure_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/api/search", tags=["Search"])
async def search_measures(request: SearchRequest):
    """Advanced search with multiple filters"""
    try:
        # Build filters from request
        filters = {}
        if request.year_min:
            filters['year_min'] = request.year_min
        if request.year_max:
            filters['year_max'] = request.year_max
        if request.county:
            filters['county'] = request.county
        if request.passed is not None:
            filters['passed'] = 1 if request.passed else 0
        if request.has_summary is not None:
            filters['has_summary'] = 1 if request.has_summary else 0
        if request.topic:
            filters['topic_primary'] = request.topic
        if request.source:
            filters['source'] = request.source
        
        # Perform search
        results = db_ops.search_measures(
            query=request.query,
            limit=request.limit,
            offset=request.offset,
            **filters
        )
        
        return {
            "count": len(results),
            "results": results,
            "query": request.query,
            "filters": filters
        }
    except Exception as e:
        logger.error(f"Error searching measures: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/api/stats", response_model=StatsResponse, tags=["Statistics"])
async def get_statistics():
    """Get database statistics"""
    try:
        stats = db_ops.get_statistics()
        return StatsResponse(**stats)
    except Exception as e:
        logger.error(f"Error fetching statistics: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/api/years", tags=["Metadata"])
async def get_years():
    """Get all years with measure counts"""
    try:
        years = db_ops.get_years_with_counts()
        return years
    except Exception as e:
        logger.error(f"Error fetching years: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/api/topics", tags=["Metadata"])
async def get_topics():
    """Get all topics with counts"""
    try:
        topics = db_ops.get_topics_with_counts()
        return topics
    except Exception as e:
        logger.error(f"Error fetching topics: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/api/counties", tags=["Metadata"])
async def get_counties():
    """Get all counties with measure counts"""
    try:
        counties = db_ops.get_counties_with_counts()
        return counties
    except Exception as e:
        logger.error(f"Error fetching counties: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/api/export", tags=["Export"])
async def export_data(
    format: str = Query("json", regex="^(json|csv)$", description="Export format"),
    year_min: Optional[int] = Query(None, description="Minimum year"),
    year_max: Optional[int] = Query(None, description="Maximum year"),
    county: Optional[str] = Query(None, description="Filter by county")
):
    """Export filtered data in JSON or CSV format"""
    try:
        filters = {}
        if year_min:
            filters['year_min'] = year_min
        if year_max:
            filters['year_max'] = year_max
        if county:
            filters['county'] = county
        
        measures = db_ops.search_measures(limit=10000, **filters)
        
        if format == "csv":
            # Generate CSV file
            import csv
            import io
            
            output = io.StringIO()
            if measures:
                fieldnames = measures[0].keys()
                writer = csv.DictWriter(output, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(measures)
            
            return JSONResponse(
                content={
                    "format": "csv",
                    "count": len(measures),
                    "data": output.getvalue()
                }
            )
        else:
            return JSONResponse(
                content={
                    "format": "json",
                    "count": len(measures),
                    "data": measures
                }
            )
    except Exception as e:
        logger.error(f"Error exporting data: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/api/health", tags=["System"])
async def health_check():
    """Health check endpoint"""
    try:
        # Check database connection
        stats = db_ops.get_statistics()
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "database": "connected",
            "measures": stats['total_measures']
        }
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": "Database connection failed"
            }
        )


# =============================================================================
# Historical Context Endpoints
# =============================================================================

@app.get("/api/historical/context/{topic}", response_model=TopicContextResponse, tags=["Historical"])
async def get_topic_context(
    topic: str = PathParam(..., description="Topic key (e.g., 'marijuana', 'gambling')"),
    min_year: int = Query(1970, ge=1900, le=2030, description="Minimum year to include")
):
    """
    Get historical context for a ballot measure topic.

    Returns aggregate statistics about how California has voted on this topic,
    including pass rates, average yes percentages, and the most recent measure.

    **Note**: All statistics are descriptive only. Historical pass rates do not
    predict future outcomes.

    Available topics: marijuana, gambling, abortion, marriage, tax, education,
    health, elections, criminal, environment
    """
    if not HISTORICAL_AVAILABLE:
        raise HTTPException(status_code=501, detail="Historical context modules not installed")

    if topic not in TOPIC_CONFIG:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown topic: {topic}. Valid topics: {list(TOPIC_CONFIG.keys())}"
        )

    try:
        context = historical_db.get_topic_context(topic, min_year)
        if context is None:
            raise HTTPException(
                status_code=404,
                detail=f"No measures found for topic '{topic}' since {min_year}"
            )

        config = TOPIC_CONFIG[topic]

        # Build most_recent response
        most_recent = None
        if context.most_recent:
            most_recent = MostRecentMeasure(
                id=context.most_recent['id'],
                ballot_name=context.most_recent['ballot_name'],
                year=context.most_recent['year'],
                description=context.most_recent['description'],
                pct_yes=context.most_recent['pct_yes'],
                passed=context.most_recent['passed'],
                margin=context.most_recent['margin'],
            )

        return TopicContextResponse(
            topic=topic,
            topic_label=config['label'],
            total_measures=context.total_measures,
            first_year=context.first_year,
            last_year=context.last_year,
            pass_rate=round(context.pass_rate * 100, 1),
            avg_yes_pct=round(context.avg_yes_pct, 1),
            passed_count=context.passed_count,
            failed_count=context.failed_count,
            most_recent=most_recent,
            color=config['color'],
            icon=config['icon'],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching topic context for {topic}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/historical/topics", response_model=List[TopicStatsResponse], tags=["Historical"])
async def get_all_topic_stats(
    min_year: int = Query(1970, ge=1900, le=2030, description="Minimum year to include")
):
    """
    Get statistics for all available topics.

    Returns topics sorted by priority order, filtered to only include topics
    with at least 3 historical measures in California.
    """
    if not HISTORICAL_AVAILABLE:
        raise HTTPException(status_code=501, detail="Historical context modules not installed")
    try:
        stats = historical_db.get_all_topic_stats(min_year)
        return [TopicStatsResponse(**s) for s in stats]
    except Exception as e:
        logger.error(f"Error fetching topic stats: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/historical/measures", response_model=List[HistoricalMeasureResponse], tags=["Historical"])
async def get_historical_measures(
    topic: Optional[str] = Query(None, description="Filter by topic"),
    min_year: int = Query(1970, ge=1900, le=2030, description="Minimum year"),
    passed: Optional[bool] = Query(None, description="Filter by pass/fail"),
    limit: int = Query(50, ge=1, le=500, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Offset for pagination")
):
    """
    Get historical ballot measures with topic tags.

    Each measure includes all applicable topic tags, with the primary
    (highest priority) topic indicated.
    """
    if not HISTORICAL_AVAILABLE:
        raise HTTPException(status_code=501, detail="Historical context modules not installed")
    try:
        if topic and topic not in TOPIC_CONFIG:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown topic: {topic}. Valid topics: {list(TOPIC_CONFIG.keys())}"
            )

        measures = historical_db.get_measures_by_topic(
            topic=topic or 'tax',  # Default to tax if no topic specified
            min_year=min_year,
            limit=limit,
            offset=offset
        ) if topic else []

        # If no topic specified, we'd need a different query
        # For now, return empty if no topic
        if not topic:
            return []

        results = []
        for m in measures:
            # Build topic tags
            topic_tags = []
            for i, t in enumerate(m.topics):
                config = TOPIC_CONFIG[t]
                topic_tags.append(TopicTagResponse(
                    topic=t,
                    label=config['label'],
                    color=config['color'],
                    icon=config['icon'],
                    priority=config['priority'],
                    is_primary=(i == 0)
                ))

            results.append(HistoricalMeasureResponse(
                id=m.id,
                ballot_name=m.ballot_name,
                year=m.year,
                description=m.description,
                description_truncated=m.description[:100] + '...' if len(m.description) > 100 else m.description,
                pct_yes=m.pct_yes,
                passed=m.passed,
                measure_type=m.measure_type,
                election_type=m.election_type,
                topics=topic_tags,
                primary_topic=m.primary_topic,
                margin=m.margin,
                margin_label=m.margin_label,
                is_close=m.is_close,
            ))

        return results
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching historical measures: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/historical/measures/{measure_id}", response_model=HistoricalMeasureResponse, tags=["Historical"])
async def get_historical_measure(
    measure_id: int = PathParam(..., description="Historical measure ID")
):
    """Get a single historical measure by ID with full topic tags."""
    if not HISTORICAL_AVAILABLE:
        raise HTTPException(status_code=501, detail="Historical context modules not installed")
    try:
        m = historical_db.get_measure_by_id(measure_id)
        if m is None:
            raise HTTPException(status_code=404, detail="Measure not found")

        # Build topic tags
        topic_tags = []
        for i, t in enumerate(m.topics):
            config = TOPIC_CONFIG[t]
            topic_tags.append(TopicTagResponse(
                topic=t,
                label=config['label'],
                color=config['color'],
                icon=config['icon'],
                priority=config['priority'],
                is_primary=(i == 0)
            ))

        return HistoricalMeasureResponse(
            id=m.id,
            ballot_name=m.ballot_name,
            year=m.year,
            description=m.description,
            description_truncated=m.description[:100] + '...' if len(m.description) > 100 else m.description,
            pct_yes=m.pct_yes,
            passed=m.passed,
            measure_type=m.measure_type,
            election_type=m.election_type,
            topics=topic_tags,
            primary_topic=m.primary_topic,
            margin=m.margin,
            margin_label=m.margin_label,
            is_close=m.is_close,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching historical measure {measure_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/historical/measures/{measure_id}/similar", response_model=List[HistoricalMeasureResponse], tags=["Historical"])
async def get_similar_measures(
    measure_id: int = PathParam(..., description="Historical measure ID"),
    limit: int = Query(5, ge=1, le=20, description="Maximum results")
):
    """
    Get measures similar to the given measure (same primary topic).

    Useful for showing "Related measures" in the UI.
    """
    if not HISTORICAL_AVAILABLE:
        raise HTTPException(status_code=501, detail="Historical context modules not installed")
    try:
        measures = historical_db.get_similar_measures(measure_id, limit)

        results = []
        for m in measures:
            topic_tags = []
            for i, t in enumerate(m.topics):
                config = TOPIC_CONFIG[t]
                topic_tags.append(TopicTagResponse(
                    topic=t,
                    label=config['label'],
                    color=config['color'],
                    icon=config['icon'],
                    priority=config['priority'],
                    is_primary=(i == 0)
                ))

            results.append(HistoricalMeasureResponse(
                id=m.id,
                ballot_name=m.ballot_name,
                year=m.year,
                description=m.description,
                description_truncated=m.description[:100] + '...' if len(m.description) > 100 else m.description,
                pct_yes=m.pct_yes,
                passed=m.passed,
                measure_type=m.measure_type,
                election_type=m.election_type,
                topics=topic_tags,
                primary_topic=m.primary_topic,
                margin=m.margin,
                margin_label=m.margin_label,
                is_close=m.is_close,
            ))

        return results
    except Exception as e:
        logger.error(f"Error fetching similar measures for {measure_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/historical/search", tags=["Historical"])
async def search_historical_measures(
    query: str = Query(..., min_length=2, description="Search text"),
    topic: Optional[str] = Query(None, description="Filter by topic"),
    passed: Optional[bool] = Query(None, description="Filter by pass/fail"),
    min_year: int = Query(1970, ge=1900, le=2030, description="Minimum year"),
    limit: int = Query(50, ge=1, le=200, description="Maximum results")
):
    """
    Full-text search on historical measure descriptions.

    Searches ballot names and descriptions. Optionally filter by topic
    and pass/fail status.
    """
    if not HISTORICAL_AVAILABLE:
        raise HTTPException(status_code=501, detail="Historical context modules not installed")
    try:
        measures = historical_db.search_measures(
            query=query,
            min_year=min_year,
            topic=topic,
            passed=passed,
            limit=limit
        )

        results = []
        for m in measures:
            topic_tags = []
            for i, t in enumerate(m.topics):
                config = TOPIC_CONFIG[t]
                topic_tags.append({
                    'topic': t,
                    'label': config['label'],
                    'color': config['color'],
                    'is_primary': (i == 0)
                })

            results.append({
                'id': m.id,
                'ballot_name': m.ballot_name,
                'year': m.year,
                'description_truncated': m.description[:100] + '...' if len(m.description) > 100 else m.description,
                'pct_yes': m.pct_yes,
                'passed': m.passed,
                'topics': topic_tags,
                'margin_label': m.margin_label,
            })

        return {
            'query': query,
            'count': len(results),
            'results': results
        }
    except Exception as e:
        logger.error(f"Error searching historical measures: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# =============================================================================
# Finance Endpoints
# =============================================================================

class FinanceSideResponse(BaseModel):
    stance: str
    # Combined: v2 monetary + v3 loan + in-kind + IE.
    total_receipts: float
    # Split for transparency: how much of the total came from each
    # source. monetary_amount is direct contributions to committees;
    # non_monetary_amount lumps loans + in-kind + IE.
    monetary_amount: float
    non_monetary_amount: float
    # Optional because the count is best-effort across two data sources
    # and may not be defined for v3-only slices.
    n_committees: Optional[int]
    n_transactions: Optional[int]
    top5_share: Optional[float]
    hhi: Optional[float]

class FinanceSummaryResponse(BaseModel):
    measure_id: str
    sides: List[FinanceSideResponse]

class FinanceTimelineEntry(BaseModel):
    stance: str
    week_start: str
    weekly_receipts: float
    cumulative_receipts: float

class FinanceTimelineResponse(BaseModel):
    measure_id: str
    support: List[FinanceTimelineEntry]
    oppose: List[FinanceTimelineEntry]

class FinanceDonorEntry(BaseModel):
    donor_name: str
    donor_type: Optional[str]
    donor_sector: Optional[str]
    total_amount: float
    # Receipt types this donor's money flowed through (combined view).
    flow_types: Optional[List[str]] = None

class FinanceTopDonorsResponse(BaseModel):
    measure_id: str
    support: List[FinanceDonorEntry]
    oppose: List[FinanceDonorEntry]


def _resolve_finance_measure_db_id(measure_id: str, year: Optional[int]) -> int:
    """Resolve a (measure_id, year) URL pair to a v3 measure_db_id.
    Goes through v2's resolve_campaign (which already understands the
    crosswalk + collision semantics), then pulls measure_db_id from
    finance_campaign metadata. Raises HTTPException on disabled,
    unavailable, ambiguous, or not-found cases.
    """
    if FINANCE_DISABLED_PENDING_REBUILD:
        raise HTTPException(status_code=503, detail="Finance data temporarily unavailable: rebuild in progress.")
    if not FINANCE_AVAILABLE or not finance_db:
        raise HTTPException(status_code=501, detail="Finance data not available")
    try:
        cid = finance_db.resolve_campaign(measure_id=measure_id, year=year)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not cid:
        raise HTTPException(status_code=404, detail=f"No finance campaign for {measure_id} ({year or 'any year'})")
    meta = finance_db.get_campaign_metadata(cid)
    if not meta or meta.get("measure_db_id") is None:
        raise HTTPException(status_code=404, detail=f"No measure_db_id for {cid}")
    return int(meta["measure_db_id"])


@app.get("/api/measure/{measure_id}/finance_summary", response_model=FinanceSummaryResponse, tags=["Finance"])
async def get_finance_summary(
    measure_id: str = PathParam(..., description="Measure ID (e.g., PROP_36)"),
    year: Optional[int] = None,
):
    """Campaign finance summary across all receipt types (monetary
    contributions + loans + in-kind + independent expenditures).
    monetary_amount is sourced from v2; non_monetary_amount from v3.
    Optional `year` disambiguates measure_ids reused across cycles."""
    mid = _resolve_finance_measure_db_id(measure_id, year)
    rows = finance_db.get_combined_summary(mid)
    if not rows:
        raise HTTPException(status_code=404, detail=f"No finance data for measure_db_id={mid}")
    return FinanceSummaryResponse(measure_id=measure_id, sides=[FinanceSideResponse(**r) for r in rows])


@app.get("/api/measure/{measure_id}/finance_timeline", response_model=FinanceTimelineResponse, tags=["Finance"])
async def get_finance_timeline(
    measure_id: str = PathParam(..., description="Measure ID (e.g., PROP_36)"),
    year: Optional[int] = None,
):
    """Weekly + cumulative receipts timeline, combined across all
    receipt types."""
    mid = _resolve_finance_measure_db_id(measure_id, year)
    rows = finance_db.get_combined_timeline(mid)
    if not rows:
        raise HTTPException(status_code=404, detail=f"No finance data for measure_db_id={mid}")
    support = [FinanceTimelineEntry(**r) for r in rows if r["stance"] == "support"]
    oppose = [FinanceTimelineEntry(**r) for r in rows if r["stance"] == "oppose"]
    return FinanceTimelineResponse(measure_id=measure_id, support=support, oppose=oppose)


@app.get("/api/measure/{measure_id}/finance_top_donors", response_model=FinanceTopDonorsResponse, tags=["Finance"])
async def get_finance_top_donors(
    measure_id: str = PathParam(..., description="Measure ID (e.g., PROP_36)"),
    year: Optional[int] = None,
):
    """Top donors across all receipt types, ranked per stance with
    combined v2 + v3 totals. donor_sector resolved at query time."""
    mid = _resolve_finance_measure_db_id(measure_id, year)
    rows = finance_db.get_combined_top_donors(mid)
    if not rows:
        raise HTTPException(status_code=404, detail=f"No finance data for measure_db_id={mid}")
    support = [
        FinanceDonorEntry(
            donor_name=r["donor_name_canon"],
            donor_type=r["donor_type"],
            donor_sector=r.get("donor_sector"),
            total_amount=r["total_amount"],
            flow_types=r.get("flow_types"),
        )
        for r in rows if r["stance"] == "support"
    ]
    oppose = [
        FinanceDonorEntry(
            donor_name=r["donor_name_canon"],
            donor_type=r["donor_type"],
            donor_sector=r.get("donor_sector"),
            total_amount=r["total_amount"],
            flow_types=r.get("flow_types"),
        )
        for r in rows if r["stance"] == "oppose"
    ]
    return FinanceTopDonorsResponse(measure_id=measure_id, support=support, oppose=oppose)


# Run the API server
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=API_PORT,
        reload=True,
        log_level="info"
    )