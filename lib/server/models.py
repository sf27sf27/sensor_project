"""
Database models and schemas for the sensor API.
Supports both local (RPi backup) and cloud (RDS) databases.
"""
import os
from sqlalchemy import Column, Integer, String, DateTime, create_engine, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.sql import func
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Any, List

# Cloud Database configuration (RDS for API servers)
CLOUD_DB_USER = os.environ.get("DB_USER")
CLOUD_DB_PASSWORD = os.environ.get("DB_PASSWORD")
CLOUD_DB_HOST = os.environ.get("DB_HOST")  # RDS endpoint
CLOUD_DB_NAME = os.environ.get("DB_NAME")
CLOUD_DB_PORT = os.environ.get("DB_PORT", "5432")

CLOUD_DATABASE_URL = f"postgresql://{CLOUD_DB_USER}:{CLOUD_DB_PASSWORD}@{CLOUD_DB_HOST}:{CLOUD_DB_PORT}/{CLOUD_DB_NAME}"

# Local Database configuration (RPi backup database)
LOCAL_DB_HOST = os.environ.get("LOCAL_DB_HOST", "127.0.0.1")
LOCAL_DB_USER = os.environ.get("LOCAL_DB_USER", "sensor_user")
LOCAL_DB_PASSWORD = os.environ.get("LOCAL_DB_PASSWORD", "strongpassword")
LOCAL_DB_NAME = os.environ.get("LOCAL_DB_NAME", "sensors")
LOCAL_DB_PORT = os.environ.get("LOCAL_DB_PORT", "5432")

LOCAL_DATABASE_URL = f"postgresql://{LOCAL_DB_USER}:{LOCAL_DB_PASSWORD}@{LOCAL_DB_HOST}:{LOCAL_DB_PORT}/{LOCAL_DB_NAME}"

# Create engines for both databases
cloud_engine = create_engine(CLOUD_DATABASE_URL, pool_pre_ping=True)
local_engine = create_engine(LOCAL_DATABASE_URL, pool_pre_ping=True)

# Create sessionmakers for both databases
CloudSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=cloud_engine)
LocalSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=local_engine)

# For backward compatibility: SessionLocal points to cloud database (used by API servers)
SessionLocal = CloudSessionLocal
engine = cloud_engine

# Shared base for all models
Base = declarative_base()

# Dependency to get the cloud database session (for FastAPI)
def get_db():
    db = CloudSessionLocal()
    try:
        yield db
    finally:
        db.close()

# Dependency to get the local database session (for sensor reading)
def get_local_db():
    db = LocalSessionLocal()
    try:
        yield db
    finally:
        db.close()


# SQLAlchemy ORM Model
class ReadingORM(Base):
    __tablename__ = "readings"
    __table_args__ = {"schema": "sensor_project"}

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String, index=True, nullable=False)
    ts_utc = Column(DateTime(timezone=True), nullable=False)
    ts_local = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    payload = Column(JSONB, nullable=False)


# Pydantic Models for API requests/responses
class ReadingBase(BaseModel):
    device_id: str
    ts_utc: datetime
    payload: dict[str, Any] = Field(..., description="JSON data from the sensor")
    ts_local: Optional[datetime] = None


class ReadingCreate(BaseModel):
    """Model for creating a new reading - ts_local is auto-generated"""
    device_id: str
    ts_utc: datetime
    payload: dict[str, Any] = Field(..., description="JSON data from the sensor")


class ReadingUpdate(BaseModel):
    """Model for updating a reading"""
    device_id: Optional[str] = None
    ts_utc: Optional[datetime] = None
    ts_local: Optional[datetime] = None
    payload: Optional[dict[str, Any]] = None


class ReadingResponse(ReadingBase):
    """Model for reading response"""
    id: int

    class Config:
        from_attributes = True


class BulkReadingCreate(BaseModel):
    """Model for bulk creating readings from backup sync"""
    readings: List[ReadingCreate]


class LatestReadingResponse(ReadingBase):
    """Model for the most recent reading based on ts_local"""
    id: int

    class Config:
        from_attributes = True
