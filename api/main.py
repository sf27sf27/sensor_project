from fastapi import FastAPI, Depends, Query
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
from .models import get_db, ReadingORM, ReadingCreate, ReadingResponse

app = FastAPI(title="Sensor Readings API", version="1.0.0")


@app.post("/readings", response_model=ReadingResponse, status_code=201)
def create_reading(reading: ReadingCreate, db: Session = Depends(get_db)):
    """Create a new sensor reading"""
    db_reading = ReadingORM(**reading.model_dump())
    db.add(db_reading)
    db.commit()
    db.refresh(db_reading)
    return db_reading


@app.get("/readings", response_model=List[ReadingResponse])
def fetch_readings(
    start_date: str = Query(..., description="Start date in format YYYY-MM-DD HH:MM:SS"),
    end_date: str = Query(..., description="End date in format YYYY-MM-DD HH:MM:SS"),
    db: Session = Depends(get_db)
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