from fastapi import FastAPI, Depends, Query, HTTPException, Security
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
import os
from .models import get_db, ReadingORM, ReadingCreate, ReadingResponse, BulkReadingCreate, LatestReadingResponse

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

app = FastAPI(title="Sensor Readings API", version="1.0.0")


@app.post("/readings", response_model=ReadingResponse, status_code=201, include_in_schema=False)
def create_reading(reading: ReadingCreate, db: Session = Depends(get_db), api_key: str = Depends(verify_api_key)):
    """Create a new sensor reading"""
    db_reading = ReadingORM(**reading.model_dump())
    db.add(db_reading)
    db.commit()
    db.refresh(db_reading)
    return db_reading


@app.post("/readings/bulk", status_code=201, include_in_schema=False)
def create_readings_bulk(bulk_reading: BulkReadingCreate, db: Session = Depends(get_db), api_key: str = Depends(verify_api_key)):
    """Bulk create sensor readings from backup database sync"""
    if not bulk_reading.readings:
        return {"created": 0, "message": "No readings provided"}
    
    readings = [
        ReadingORM(**reading.model_dump())
        for reading in bulk_reading.readings
    ]
    db.add_all(readings)
    db.commit()
    return {"created": len(readings), "message": f"Successfully created {len(readings)} readings"}


@app.get("/readings", response_model=List[ReadingResponse], include_in_schema=False)
def fetch_readings(
    start_date: str = Query(..., description="Start date in format YYYY-MM-DD HH:MM:SS"),
    end_date: str = Query(..., description="End date in format YYYY-MM-DD HH:MM:SS"),
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """Fetch readings within a date range based on ts_local"""
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d %H:%M:%S")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        raise ValueError("Date format must be YYYY-MM-DD HH:MM:SS")
    
    return db.query(ReadingORM).filter(
        ReadingORM.ts_local >= start_dt,
        ReadingORM.ts_local <= end_dt
    ).all()


@app.get("/readings/latest", response_model=LatestReadingResponse)
def fetch_latest_reading(db: Session = Depends(get_db), api_key: str = Depends(verify_api_key)):
    """Fetch the most recent reading based on ts_local"""
    latest = db.query(ReadingORM).order_by(
        ReadingORM.ts_local.desc()
    ).first()
    
    if not latest:
        raise ValueError("No readings found in the database")
    
    return latest