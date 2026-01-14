"""
FastAPI application for writing sensor readings.
Handles POST requests from sensor devices.

Entry point: api_server_write.py
"""
from fastapi import FastAPI, Depends, HTTPException, Security
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session
import os

from lib.server.models import (
    get_db,
    ReadingORM,
    ReadingCreate,
    ReadingResponse,
    BulkReadingCreate
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


# FastAPI app for write operations
app = FastAPI(
    title="Sensor Readings API - Writer",
    version="1.0.0",
    description="Write sensor readings to the database"
)


@app.post("/readings", response_model=ReadingResponse, status_code=201)
def create_reading(
    reading: ReadingCreate,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """Create a new sensor reading"""
    db_reading = ReadingORM(**reading.model_dump())
    db.add(db_reading)
    db.commit()
    db.refresh(db_reading)
    return db_reading


@app.post("/readings/bulk", status_code=201)
def create_readings_bulk(
    bulk_reading: BulkReadingCreate,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
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
