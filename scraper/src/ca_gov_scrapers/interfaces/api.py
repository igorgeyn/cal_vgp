#!/usr/bin/env python3
"""
California Government Ballot Measures Scraper - FastAPI REST API
"""

from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
import json
from datetime import datetime

app = FastAPI(
    title="CA Gov Ballot Measures API",
    description="REST API for California government ballot measures",
    version="1.0.0"
)

class ScrapeRequest(BaseModel):
    level: str = "state"
    output_format: str = "json"

@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "CA Government Ballot Measures API", "version": "1.0.0"}

@app.post("/scrape")
async def scrape_measures(request: ScrapeRequest):
    """Scrape ballot measures"""
    try:
        from ..scrapers.state_scraper import CAStateScraper
        
        scraper = CAStateScraper()
        results = scraper.scrape_all()
        
        return {
            "status": "success",
            "data": results,
            "request": request.dict()
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "request": request.dict()
        }

@app.get("/status")
async def get_status():
    """Get API status"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "endpoints": ["/", "/scrape", "/status"]
    }
