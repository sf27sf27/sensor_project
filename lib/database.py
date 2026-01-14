"""
Database operations and connection pool management.
"""
import os
import time
import json
import math
import shutil
from psycopg2 import pool

from lib.config import (
    logger,
    LOCAL_DB_CONFIG,
    POOL_INIT_MAX_RETRIES,
    POOL_INIT_RETRY_DELAY,
    INSERT_SQL,
    COUNT_ALL_RECORDS_SQL,
    GET_TIMESTAMP_RANGE_SQL,
    GET_RECORDS_FOR_DELETION_SQL,
    DELETE_RECORDS_BY_ID_SQL,
)

# Initialize connection pool at module level
db_pool = None


def initialize_connection_pool():
    """Initialize database connection pool with retry logic"""
    global db_pool
    
    for attempt in range(1, POOL_INIT_MAX_RETRIES + 1):
        try:
            db_pool = pool.SimpleConnectionPool(
                minconn=2,      # Keep 2 idle connections ready
                maxconn=10,     # Max 10 connections total
                **LOCAL_DB_CONFIG,
                connect_timeout=5
            )
            logger.info(f"Database connection pool initialized successfully (attempt {attempt})")
            return True
        except Exception as e:
            logger.warning(f"Failed to create connection pool (attempt {attempt}/{POOL_INIT_MAX_RETRIES}): {e}")
            if attempt < POOL_INIT_MAX_RETRIES:
                time.sleep(POOL_INIT_RETRY_DELAY)
            else:
                logger.error(f"Failed to initialize connection pool after {POOL_INIT_MAX_RETRIES} attempts")
                db_pool = None
                return False
    
    return False


def get_local_db_connection():
    """Get a connection from the pool, with automatic reinitialization if needed"""
    global db_pool
    
    # If pool is None, attempt to reinitialize it
    if db_pool is None:
        logger.warning("Connection pool is None, attempting to reinitialize...")
        if not initialize_connection_pool():
            raise RuntimeError("Connection pool not initialized and reinitialization failed")
    
    try:
        conn = db_pool.getconn()
        return conn
    except pool.PoolError as e:
        logger.error(f"Failed to get connection from pool: {e}")
        # If pool is exhausted, this might be a temporary issue
        raise RuntimeError(f"Failed to get database connection: {e}")


def return_db_connection(conn):
    """Return a connection to the pool"""
    if db_pool and conn:
        db_pool.putconn(conn)


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
    """Delete records evenly across the dataset to reduce granularity"""
    conn = None
    try:
        conn = get_local_db_connection()
        conn.autocommit = False
        cur = conn.cursor()
        
        # Get total record count
        cur.execute(COUNT_ALL_RECORDS_SQL)
        total_records = cur.fetchone()[0]
        
        if total_records == 0:
            logger.info("No records to delete")
            cur.close()
            return
        
        # Get timestamp range
        cur.execute(GET_TIMESTAMP_RANGE_SQL)
        min_ts, max_ts = cur.fetchone()
        
        if min_ts is None or max_ts is None:
            logger.info("Cannot determine timestamp range")
            cur.close()
            return
        
        logger.info(f"Current record count: {total_records}")
        logger.info(f"Time range: {min_ts} to {max_ts}")
        
        # Calculate deletion strategy: delete every nth record to spread deletions evenly
        # Target is to delete ~20% of records to bring disk usage down
        delete_count = max(1, int(total_records * 0.2))
        deletion_interval = max(1, math.ceil(total_records / delete_count))
        
        logger.info(f"Deleting every {deletion_interval}th record (~{delete_count} records)")
        
        # Get record IDs to delete (stratified by timestamp)
        records_to_delete = []
        offset = 0
        step = deletion_interval
        
        while offset < total_records:
            cur.execute(GET_RECORDS_FOR_DELETION_SQL, (1, offset))
            result = cur.fetchone()
            if result:
                records_to_delete.append(result[0])
            offset += step
        
        if records_to_delete:
            logger.info(f"Deleting {len(records_to_delete)} records")
            cur.execute(DELETE_RECORDS_BY_ID_SQL, (records_to_delete,))
            conn.commit()
            logger.info(f"Successfully deleted {cur.rowcount} records")
        else:
            logger.info("No records selected for deletion")
        
        cur.close()
        
        # Check new disk usage
        new_usage = get_disk_usage_percent()
        if new_usage is not None:
            logger.info(f"Disk usage after cleanup: {new_usage:.1f}%")
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to reduce data granularity: {e}", exc_info=True)
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            return_db_connection(conn)


def save_to_backup(device_id, ts_utc, json_data):
    """Save reading to local backup database"""
    conn = None
    try:
        conn = get_local_db_connection()
        conn.autocommit = True
        cur = conn.cursor()
        
        # Convert json_data to string if needed
        if isinstance(json_data, dict):
            payload = json.dumps(json_data)
        else:
            payload = json_data
        
        cur.execute(
            INSERT_SQL,
            (device_id, ts_utc, payload)
        )
        
        cur.close()
        logger.info("Reading saved to local backup database")
        return True
    except Exception as e:
        logger.error(f"Failed to save to backup database: {e}")
        return False
    finally:
        if conn:
            return_db_connection(conn)
