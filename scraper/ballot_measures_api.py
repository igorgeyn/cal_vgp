#!/usr/bin/env python3
"""
FastAPI Backend for Ballot Measures Database
Provides REST API endpoints for the website
"""

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict
import sqlite3
import json
from datetime import datetime
from pathlib import Path

app = FastAPI(
    title="California Ballot Measures API",
    description="API for accessing historical California ballot measure data",
    version="1.0.0"
)

# Enable CORS for website access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with your website URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database path
DB_PATH = "data/ballot_measures.db"

class BallotMeasure(BaseModel):
    """Ballot measure data model"""
    id: int
    year: Optional[int]
    title: Optional[str]
    description: Optional[str]
    summary: Optional[str]
    percent_yes: Optional[float]
    passed: Optional[int]
    measure_type: Optional[str]
    topic_primary: Optional[str]
    data_source: str
    pdf_url: Optional[str]
    has_summary: bool = False
    summary_title: Optional[str]
    summary_text: Optional[str]

class SearchFilters(BaseModel):
    """Search filter options"""
    year_min: Optional[int] = None
    year_max: Optional[int] = None
    decade: Optional[int] = None
    passed: Optional[bool] = None
    topic: Optional[str] = None
    search_text: Optional[str] = None
    data_source: Optional[str] = None
    has_summary: Optional[bool] = None

def get_db():
    """Get database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "California Ballot Measures API",
        "endpoints": [
            "/measures",
            "/measures/{id}",
            "/search",
            "/stats",
            "/topics",
            "/timeline",
            "/export"
        ]
    }

@app.get("/measures", response_model=List[Dict])
async def get_measures(
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0),
    year: Optional[int] = None,
    decade: Optional[int] = None,
    passed: Optional[bool] = None,
    sort_by: str = Query("year", regex="^(year|title|percent_yes)$"),
    order: str = Query("desc", regex="^(asc|desc)$")
):
    """Get ballot measures with optional filters"""
    conn = get_db()
    
    # Build query
    query = "SELECT * FROM measures WHERE 1=1"
    params = []
    
    if year:
        query += " AND year = ?"
        params.append(year)
    if decade:
        query += " AND decade = ?"
        params.append(decade)
    if passed is not None:
        query += " AND passed = ?"
        params.append(1 if passed else 0)
        
    # Add sorting
    query += f" ORDER BY {sort_by} {order.upper()}"
    
    # Add pagination
    query += " LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    
    cursor = conn.execute(query, params)
    measures = [dict(row) for row in cursor]
    conn.close()
    
    return measures

@app.get("/measures/{measure_id}")
async def get_measure(measure_id: int):
    """Get a specific measure by ID"""
    conn = get_db()
    cursor = conn.execute("SELECT * FROM measures WHERE id = ?", (measure_id,))
    measure = cursor.fetchone()
    conn.close()
    
    if not measure:
        raise HTTPException(status_code=404, detail="Measure not found")
        
    return dict(measure)

@app.post("/search")
async def search_measures(filters: SearchFilters):
    """Advanced search with multiple filters"""
    conn = get_db()
    
    query = "SELECT * FROM measures WHERE 1=1"
    params = []
    
    # Apply filters
    if filters.year_min:
        query += " AND year >= ?"
        params.append(filters.year_min)
    if filters.year_max:
        query += " AND year <= ?"
        params.append(filters.year_max)
    if filters.decade:
        query += " AND decade = ?"
        params.append(filters.decade)
    if filters.passed is not None:
        query += " AND passed = ?"
        params.append(1 if filters.passed else 0)
    if filters.topic:
        query += " AND topic_primary LIKE ?"
        params.append(f"%{filters.topic}%")
    if filters.data_source:
        query += " AND data_source = ?"
        params.append(filters.data_source)
    if filters.has_summary is not None:
        query += " AND has_summary = ?"
        params.append(1 if filters.has_summary else 0)
        
    # Full-text search
    if filters.search_text:
        query += """ AND id IN (
            SELECT measure_id FROM measure_search 
            WHERE measure_search MATCH ?
        )"""
        params.append(filters.search_text)
        
    query += " ORDER BY year DESC LIMIT 500"
    
    cursor = conn.execute(query, params)
    measures = [dict(row) for row in cursor]
    conn.close()
    
    return {
        "count": len(measures),
        "filters": filters.dict(),
        "results": measures
    }

@app.get("/stats")
async def get_statistics():
    """Get database statistics"""
    conn = get_db()
    
    stats = {}
    
    # Total measures
    cursor = conn.execute("SELECT COUNT(*) as total FROM measures")
    stats['total_measures'] = cursor.fetchone()['total']
    
    # Year range
    cursor = conn.execute("SELECT MIN(year) as min_year, MAX(year) as max_year FROM measures WHERE year IS NOT NULL")
    row = cursor.fetchone()
    stats['year_range'] = {'min': row['min_year'], 'max': row['max_year']}
    
    # By source
    cursor = conn.execute("""
        SELECT data_source, COUNT(*) as count 
        FROM measures 
        GROUP BY data_source
    """)
    stats['by_source'] = {row['data_source']: row['count'] for row in cursor}
    
    # Pass rate
    cursor = conn.execute("""
        SELECT 
            COUNT(CASE WHEN passed = 1 THEN 1 END) as passed,
            COUNT(CASE WHEN passed = 0 THEN 1 END) as failed,
            COUNT(CASE WHEN passed IS NULL THEN 1 END) as unknown
        FROM measures
    """)
    row = cursor.fetchone()
    stats['outcomes'] = {
        'passed': row['passed'],
        'failed': row['failed'],
        'unknown': row['unknown']
    }
    
    # With summaries
    cursor = conn.execute("SELECT COUNT(*) as count FROM measures WHERE has_summary = 1")
    stats['with_summaries'] = cursor.fetchone()['count']
    
    conn.close()
    return stats

@app.get("/topics")
async def get_topics():
    """Get all unique topics with counts"""
    conn = get_db()
    cursor = conn.execute("""
        SELECT topic_primary as topic, COUNT(*) as count
        FROM measures
        WHERE topic_primary IS NOT NULL
        GROUP BY topic_primary
        ORDER BY count DESC
    """)
    topics = [{'topic': row['topic'], 'count': row['count']} for row in cursor]
    conn.close()
    return topics

@app.get("/timeline")
async def get_timeline():
    """Get measures grouped by decade for timeline visualization"""
    conn = get_db()
    cursor = conn.execute("""
        SELECT 
            decade,
            COUNT(*) as total,
            SUM(CASE WHEN passed = 1 THEN 1 ELSE 0 END) as passed,
            SUM(CASE WHEN passed = 0 THEN 1 ELSE 0 END) as failed
        FROM measures
        WHERE decade IS NOT NULL
        GROUP BY decade
        ORDER BY decade
    """)
    
    timeline = []
    for row in cursor:
        timeline.append({
            'decade': row['decade'],
            'total': row['total'],
            'passed': row['passed'],
            'failed': row['failed'],
            'pass_rate': round((row['passed'] / (row['passed'] + row['failed']) * 100), 1) 
                        if (row['passed'] + row['failed']) > 0 else None
        })
    
    conn.close()
    return timeline

@app.get("/export")
async def export_data(
    format: str = Query("json", regex="^(json|csv)$"),
    year_min: Optional[int] = None,
    year_max: Optional[int] = None
):
    """Export filtered data in JSON or CSV format"""
    conn = get_db()
    
    query = "SELECT * FROM measures WHERE 1=1"
    params = []
    
    if year_min:
        query += " AND year >= ?"
        params.append(year_min)
    if year_max:
        query += " AND year <= ?"
        params.append(year_max)
        
    query += " ORDER BY year DESC"
    
    cursor = conn.execute(query, params)
    measures = [dict(row) for row in cursor]
    conn.close()
    
    if format == "csv":
        # Convert to CSV format
        import csv
        import io
        
        output = io.StringIO()
        if measures:
            writer = csv.DictWriter(output, fieldnames=measures[0].keys())
            writer.writeheader()
            writer.writerows(measures)
        
        return {
            "format": "csv",
            "data": output.getvalue()
        }
    else:
        return {
            "format": "json",
            "count": len(measures),
            "data": measures
        }

@app.get("/measure/{year}/{title}")
async def get_measure_by_year_title(year: int, title: str):
    """Get a measure by year and partial title match"""
    conn = get_db()
    cursor = conn.execute("""
        SELECT * FROM measures 
        WHERE year = ? AND title LIKE ? 
        LIMIT 1
    """, (year, f"%{title}%"))
    
    measure = cursor.fetchone()
    conn.close()
    
    if not measure:
        raise HTTPException(status_code=404, detail="Measure not found")
        
    return dict(measure)

# Run with: uvicorn ballot_measures_api:app --reload
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)