"""
FastAPI application for querying sensor readings.
Handles GET requests for reading sensor data.

Entry point: api_server_query.py
"""
from fastapi import FastAPI, Depends, Query, HTTPException, Security
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from datetime import datetime
import os

from lib.server.models import (
    get_db,
    ReadingORM,
    ReadingResponse,
    LatestReadingResponse
)

# API Key configuration
api_key_header = APIKeyHeader(name="X-API-Key", description="API Key for authentication")


def verify_api_key(api_key: str = Security(api_key_header)):
    """Verify the API key from the request header"""
    valid_api_key = os.getenv("API_KEY")
    if not valid_api_key:
        raise HTTPException(status_code=500, detail="API_KEY not configured on server")
    if api_key != valid_api_key:
        raise HTTPException(status_code=403, detail="Invalid API Key")
    return api_key


# FastAPI app for read operations
app = FastAPI(
    title="Sensor Readings API - Query",
    version="1.0.0",
    description="Query and retrieve sensor readings from the database"
)


@app.get("/readings", response_model=List[ReadingResponse])
def fetch_readings(
    start_date: str = Query(..., description="Start date in format YYYY-MM-DD HH:MM:SS"),
    end_date: str = Query(..., description="End date in format YYYY-MM-DD HH:MM:SS"),
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """Fetch readings within a date range based on ts_utc"""
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d %H:%M:%S")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Date format must be YYYY-MM-DD HH:MM:SS"
        )
    
    return db.query(ReadingORM).filter(
        ReadingORM.ts_utc >= start_dt,
        ReadingORM.ts_utc <= end_dt
    ).all()


@app.get("/readings/latest", response_model=List[LatestReadingResponse])
def fetch_latest_reading(
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """Fetch the most recent reading per device_id based on ts_utc"""
    subquery = db.query(
        ReadingORM.device_id,
        func.max(ReadingORM.ts_utc).label('max_ts')
    ).group_by(ReadingORM.device_id).subquery()

    latest = db.query(ReadingORM).join(
        subquery,
        (ReadingORM.device_id == subquery.c.device_id) & 
        (ReadingORM.ts_utc == subquery.c.max_ts)
    ).with_entities(
        ReadingORM.id,
        ReadingORM.device_id,
        ReadingORM.ts_local,
        ReadingORM.ts_utc,
        ReadingORM.payload
    ).all()
    
    if not latest:
        raise HTTPException(
            status_code=404,
            detail="No readings found in the database"
        )
    
    return latest
