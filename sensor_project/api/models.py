import os
from sqlalchemy import Column, Integer, String, DateTime, create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.sql import func
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Any

# Database configuration
DB_USER = os.environ.get("DB_USER")
DB_PASSWORD = os.environ.get("DB_PASSWORD")
DB_HOST = os.environ.get("DB_HOST")  # RDS endpoint
DB_NAME = os.environ.get("DB_NAME")
DB_PORT = os.environ.get("DB_PORT", "5432")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Dependency to get the database session
def get_db():
    db = SessionLocal()
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
    ts_local = Column(DateTime(timezone=True), nullable=False)
    payload = Column(JSONB, nullable=False)


# Pydantic Models for API requests/responses
class ReadingBase(BaseModel):
    device_id: str
    ts_utc: datetime
    ts_local: datetime
    payload: dict[str, Any] = Field(..., description="JSON data from the sensor")


class ReadingCreate(ReadingBase):
    """Model for creating a new reading"""
    pass


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
