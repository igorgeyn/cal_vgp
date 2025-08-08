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
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global database connection
db_ops = None

@app.on_event("startup")
async def startup_event():
    """Initialize database connection on startup"""
    global db_ops
    if not DB_PATH.exists():
        logger.error(f"Database not found at {DB_PATH}")
        raise RuntimeError("Database not initialized")
    db_ops = Database(DB_PATH)
    logger.info("API server started successfully")

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on shutdown"""
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
    source: str
    pdf_url: Optional[str]
    created_at: datetime
    updated_at: datetime

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
    unknown: int
    year_min: Optional[int]
    year_max: Optional[int]
    sources: Dict[str, int]
    counties: int
    topics: int

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
            filters=filters,
            limit=limit,
            offset=offset
        )
        
        return measures
    except Exception as e:
        logger.error(f"Error fetching measures: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/measures/{measure_id}", response_model=MeasureResponse, tags=["Measures"])
async def get_measure(measure_id: int = PathParam(..., description="Measure database ID")):
    """Get a specific measure by ID"""
    try:
        measure = db_ops.get_measure_by_id(measure_id)
        if not measure:
            raise HTTPException(status_code=404, detail="Measure not found")
        return measure
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching measure {measure_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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
            filters=filters,
            limit=request.limit,
            offset=request.offset
        )
        
        return {
            "count": len(results),
            "results": results,
            "query": request.query,
            "filters": filters
        }
    except Exception as e:
        logger.error(f"Error searching measures: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stats", response_model=StatsResponse, tags=["Statistics"])
async def get_statistics():
    """Get database statistics"""
    try:
        stats = db_ops.get_statistics()
        return StatsResponse(**stats)
    except Exception as e:
        logger.error(f"Error fetching statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/years", tags=["Metadata"])
async def get_years():
    """Get all years with measure counts"""
    try:
        years = db_ops.get_years_with_counts()
        return years
    except Exception as e:
        logger.error(f"Error fetching years: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/topics", tags=["Metadata"])
async def get_topics():
    """Get all topics with counts"""
    try:
        topics = db_ops.get_topics_with_counts()
        return topics
    except Exception as e:
        logger.error(f"Error fetching topics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/counties", tags=["Metadata"])
async def get_counties():
    """Get all counties with measure counts"""
    try:
        counties = db_ops.get_counties_with_counts()
        return counties
    except Exception as e:
        logger.error(f"Error fetching counties: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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
        
        measures = db_ops.search_measures(filters=filters, limit=10000)
        
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
        raise HTTPException(status_code=500, detail=str(e))

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
                "error": str(e)
            }
        )

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