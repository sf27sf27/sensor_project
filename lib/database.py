"""
Database utility functions for local sensor backup database.
All database access now uses SQLAlchemy ORM via models.py
"""
import os
import time
import json
import math
import shutil
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.sql import func, text

from lib.config import logger
from lib.server.models import LocalSessionLocal, ReadingORM


def initialize_connection_pool():
    """
    Legacy function for backward compatibility.
    SQLAlchemy now handles connection pooling automatically.
    Returns True if local database is accessible.
    """
    db = LocalSessionLocal()
    try:
        # Test connection by executing a simple query
        db.execute(text("SELECT 1"))
        logger.info("Local database connection pool initialized successfully (SQLAlchemy)")
        db.close()
        return True
    except Exception as e:
        logger.error(f"Failed to initialize database connection: {e}")
        return False


def get_disk_usage_percent():
    """Get disk usage percentage for the database directory"""
    try:
        db_dir = os.path.expanduser("~")  # or specify your database directory
        stat = shutil.disk_usage(db_dir)
        usage_percent = (stat.used / stat.total) * 100
        return usage_percent
    except Exception as e:
        logger.error(f"Failed to get disk usage: {e}")
        return None


def reduce_data_granularity():
    """Delete records evenly across the dataset using SQLAlchemy ORM"""
    db = LocalSessionLocal()
    try:
        # Get total record count
        total_records = db.query(ReadingORM).count()
        
        if total_records == 0:
            logger.info("No records to delete")
            return True
        
        # Get timestamp range
        min_max = db.query(
            func.min(ReadingORM.ts_utc),
            func.max(ReadingORM.ts_utc)
        ).first()
        
        min_ts, max_ts = min_max
        
        if min_ts is None or max_ts is None:
            logger.info("Cannot determine timestamp range")
            return True
        
        logger.info(f"Current record count: {total_records}")
        logger.info(f"Time range: {min_ts} to {max_ts}")
        
        # Calculate deletion strategy: delete every nth record to spread deletions evenly
        # Target is to delete ~20% of records to bring disk usage down
        delete_count = max(1, int(total_records * 0.2))
        deletion_interval = max(1, math.ceil(total_records / delete_count))
        
        logger.info(f"Deleting every {deletion_interval}th record (~{delete_count} records)")
        
        # Get all record IDs in order
        all_records = db.query(ReadingORM.id).order_by(ReadingORM.ts_utc).all()
        
        # Select every nth record for deletion
        records_to_delete_ids = [all_records[i][0] for i in range(0, len(all_records), deletion_interval)]
        
        if records_to_delete_ids:
            logger.info(f"Deleting {len(records_to_delete_ids)} records")
            
            # Delete in batches to avoid issues with large IN clauses
            batch_size = 1000
            for i in range(0, len(records_to_delete_ids), batch_size):
                batch_ids = records_to_delete_ids[i:i+batch_size]
                db.query(ReadingORM).filter(ReadingORM.id.in_(batch_ids)).delete()
                db.commit()
            
            logger.info(f"Successfully deleted {len(records_to_delete_ids)} records")
        else:
            logger.info("No records selected for deletion")
        
        # Check new disk usage
        new_usage = get_disk_usage_percent()
        if new_usage is not None:
            logger.info(f"Disk usage after cleanup: {new_usage:.1f}%")
        
        return True
        
    except SQLAlchemyError as e:
        logger.error(f"Failed to reduce data granularity: {e}", exc_info=True)
        db.rollback()
        return False
    finally:
        db.close()


def save_to_backup(device_id, ts_utc, json_data):
    """Save reading to local backup database using SQLAlchemy ORM"""
    db = LocalSessionLocal()
    try:
        # Convert json_data to dict if needed
        if isinstance(json_data, str):
            payload = json.loads(json_data)
        else:
            payload = json_data
        
        # Create ORM object
        reading = ReadingORM(
            device_id=device_id,
            ts_utc=ts_utc,
            payload=payload
        )
        
        db.add(reading)
        db.commit()
        db.refresh(reading)
        
        logger.info(f"Reading saved to local backup database: id={reading.id}")
        return True
    except SQLAlchemyError as e:
        logger.error(f"Failed to save to backup database: {e}")
        db.rollback()
        return False
    finally:
        db.close()

