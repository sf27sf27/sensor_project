from sensors.disk_space  import read as read_disk_space
from sensors.cpu_temp  import read as read_cpu_temp
from sensors.bme280 import read as read_bme280
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import json
import os
from dotenv import load_dotenv
import psycopg2
from psycopg2 import pool
import requests
import socket
import logging
import threading
import shutil
import math

load_dotenv()


LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "read_sensors.log")

# Configure logging to both console and file BEFORE creating logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

LOCAL_DB_CONFIG = {
    "host": "localhost",
    "dbname": "sensors",
    "user": "sensor_user",
    "password": "strongpassword",
    "port": 5432
}

# Initialize connection pool at module level
db_pool = None

# Connection pool initialization retry settings
POOL_INIT_MAX_RETRIES = 10
POOL_INIT_RETRY_DELAY = 2  # seconds


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


# Try to initialize connection pool at startup
initialize_connection_pool()

# API configuration - can be overridden with API_SERVER environment variable
API_SERVER = os.getenv("API_SERVER", "localhost:8000")
API_BASE_URL = f"http://{API_SERVER}"
READINGS_ENDPOINT = f"{API_BASE_URL}/readings"
READINGS_BULK_ENDPOINT = f"{API_BASE_URL}/readings/bulk"

# API authentication
API_KEY = os.getenv("API_KEY")
if not API_KEY:
    logger.warning("API_KEY environment variable not set. API requests will fail with 401 authentication errors.")
API_HEADERS = {"X-API-Key": API_KEY} if API_KEY else {}

# Bulk sync configuration
BULK_SYNC_BATCH_SIZE = 360  # Number of records to upload in each batch

# Global connection variables - initialized in main()
device_id = socket.gethostname()

INSERT_SQL = """
INSERT INTO sensor_project.readings (device_id, ts_utc, ts_local, payload)
VALUES (%s, %s, NULL, %s)
"""

SELECT_UNSYNCED_SQL = """
SELECT id, device_id, ts_utc, payload
FROM sensor_project.readings
WHERE is_synced = FALSE
ORDER BY id ASC
"""

DELETE_SYNCED_SQL = """
DELETE FROM sensor_project.readings
WHERE id = %s
"""

# Disk management configuration
DISK_USAGE_THRESHOLD = 50  # Percentage (e.g., 50%)
DISK_CLEANUP_CHECK_INTERVAL = 300  # Check every 5 minutes
DELETE_STRATEGY = "stratified"  # Delete records evenly across time range

COUNT_ALL_RECORDS_SQL = """
SELECT COUNT(*) FROM sensor_project.readings
"""

GET_TIMESTAMP_RANGE_SQL = """
SELECT MIN(ts_utc), MAX(ts_utc) FROM sensor_project.readings
"""

GET_RECORDS_FOR_DELETION_SQL = """
SELECT id FROM sensor_project.readings
ORDER BY ts_utc ASC
LIMIT %s OFFSET %s
"""

DELETE_RECORDS_BY_ID_SQL = """
DELETE FROM sensor_project.readings
WHERE id = ANY(%s)
"""


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


def read_all_sensors():
    """
    Read all sensors in parallel using ThreadPoolExecutor.
    Returns a dict with sensor data or error messages.
    """
    sensor_data = {}
    
    with ThreadPoolExecutor(max_workers=3) as executor:
        # Submit all sensor read tasks
        futures = {
            executor.submit(read_disk_space): 'disk_space',
            executor.submit(read_cpu_temp): 'cpu_temp',
            executor.submit(read_bme280): 'bme280'
        }
        
        # Collect results as they complete
        for future in as_completed(futures):
            sensor_name = futures[future]
            try:
                sensor_data[sensor_name] = future.result()
            except Exception as e:
                sensor_data[sensor_name] = {"error": str(e)}
                logger.error(f"{sensor_name} read failed: {e}")
    
    return sensor_data


def check_api_health():
    """Check if API server is reachable"""
    try:
        response = requests.get(f"{API_BASE_URL}/docs", timeout=5)
        if response.status_code == 200:
            logger.info(f"API server is reachable at {API_BASE_URL}")
            return True
    except requests.exceptions.RequestException as e:
        logger.warning(f"API server health check failed: {e}")
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


def disk_space_monitor():
    """Periodically monitor disk usage and trigger cleanup if needed"""
    while True:
        try:
            disk_usage = get_disk_usage_percent()
            
            if disk_usage is not None:
                logger.info(f"Disk usage: {disk_usage:.1f}%")
                
                if disk_usage > DISK_USAGE_THRESHOLD:
                    logger.warning(f"Disk usage ({disk_usage:.1f}%) exceeds threshold ({DISK_USAGE_THRESHOLD}%)")
                    logger.info("Triggering data granularity reduction...")
                    reduce_data_granularity()
                    
                    # Re-check after cleanup
                    new_usage = get_disk_usage_percent()
                    if new_usage is not None:
                        logger.info(f"Disk usage after cleanup: {new_usage:.1f}%")
                        
        except Exception as e:
            logger.error(f"Disk space monitor error: {e}", exc_info=True)
        
        time.sleep(DISK_CLEANUP_CHECK_INTERVAL)


def connection_pool_monitor():
    """Monitor connection pool health and attempt reconnection if needed"""
    global db_pool
    
    while True:
        try:
            if db_pool is None:
                logger.warning("Connection pool is None, attempting to reinitialize...")
                initialize_connection_pool()
            else:
                # Test the connection pool by getting and returning a connection
                try:
                    conn = db_pool.getconn()
                    db_pool.putconn(conn)
                    # Silently log only periodically to avoid spam
                except Exception as e:
                    logger.warning(f"Connection pool health check failed: {e}")
                    db_pool = None  # Reset to None to trigger reinitialization
                    
        except Exception as e:
            logger.error(f"Connection pool monitor error: {e}", exc_info=True)
        
        time.sleep(30)  # Check every 30 seconds


def insert_reading(device_id, ts_utc, json_data):
    """Send reading to API endpoint, fallback to local DB on failure"""
    try:
        # Parse JSON data if it's a string
        if isinstance(json_data, str):
            payload = json.loads(json_data)
        else:
            payload = json_data
        
        # Prepare the request payload according to API spec
        request_payload = {
            "device_id": device_id,
            "ts_utc": ts_utc.isoformat(),
            "payload": payload
        }
        
        # Send POST request to API
        response = requests.post(
            READINGS_ENDPOINT,
            json=request_payload,
            headers=API_HEADERS,
            timeout=10
        )
        
        if response.status_code == 201:
            logger.info(f"Reading successfully sent to API: {response.json()}")
            return True
        else:
            logger.error(f"API returned status {response.status_code}: {response.text}")
            # Fallback to backup database
            save_to_backup(device_id, ts_utc, json_data)
            return False
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to send reading to API: {e}")
        # Fallback to backup database
        save_to_backup(device_id, ts_utc, json_data)
        return False
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON payload: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error sending to API: {e}")
        # Fallback to backup database
        save_to_backup(device_id, ts_utc, json_data)
        return False


def sync_backup_to_api():
    """Periodically sync unsynced records from local backup to API using bulk upload"""
    while True:
        conn = None
        try:
            conn = get_local_db_connection()
            conn.autocommit = True
            cur = conn.cursor()
            
            # Fetch unsynced records from backup DB
            cur.execute(SELECT_UNSYNCED_SQL)
            records = cur.fetchall()
            
            if records:
                logger.info(f"Found {len(records)} unsynced records in backup database")
                
                # Process records in batches
                total_synced = 0
                for batch_start in range(0, len(records), BULK_SYNC_BATCH_SIZE):
                    batch_end = min(batch_start + BULK_SYNC_BATCH_SIZE, len(records))
                    batch = records[batch_start:batch_end]
                    
                    try:
                        # Prepare batch payload
                        batch_readings = []
                        batch_ids = []
                        
                        for record in batch:
                            record_id, dev_id, ts_utc, payload = record
                            batch_ids.append(record_id)
                            
                            # Ensure payload is properly formatted
                            if isinstance(payload, dict):
                                payload_dict = payload
                            else:
                                payload_dict = json.loads(payload) if isinstance(payload, str) else {}
                            
                            reading_entry = {
                                "device_id": dev_id,
                                "ts_utc": ts_utc.isoformat() if hasattr(ts_utc, 'isoformat') else ts_utc,
                                "payload": payload_dict
                            }
                            batch_readings.append(reading_entry)
                        
                        # Send batch to API
                        bulk_payload = {"readings": batch_readings}
                        response = requests.post(
                            READINGS_BULK_ENDPOINT,
                            json=bulk_payload,
                            headers=API_HEADERS,
                            timeout=30  # Allow longer timeout for bulk uploads
                        )
                        
                        if response.status_code == 201:
                            response_data = response.json()
                            created_count = response_data.get("created", 0)
                            logger.info(f"Bulk synced {created_count} records to API (batch {batch_start // BULK_SYNC_BATCH_SIZE + 1})")
                            
                            # Delete successfully uploaded records from local DB
                            try:
                                placeholders = ','.join(['%s'] * len(batch_ids))
                                delete_batch_sql = f"DELETE FROM sensor_project.readings WHERE id IN ({placeholders})"
                                cur.execute(delete_batch_sql, batch_ids)
                                logger.info(f"Deleted {len(batch_ids)} synced records from backup database")
                                total_synced += len(batch_ids)
                            except Exception as e:
                                logger.error(f"Failed to delete synced records: {e}")
                        else:
                            logger.warning(f"Failed to sync batch: API returned {response.status_code} - {response.text}")
                            
                    except Exception as e:
                        logger.error(f"Failed to sync batch: {e}")
                
                if total_synced > 0:
                    logger.info(f"Successfully synced {total_synced} total records to API")
            
            cur.close()
            
        except Exception as e:
            logger.error(f"Backup sync to API failed: {e}")
        finally:
            if conn:
                return_db_connection(conn)
        
        # Wait before next sync attempt
        time.sleep(5)


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


if __name__ == "__main__":
    logger.info(f"Starting sensor reader, API endpoint: {READINGS_ENDPOINT}")
    logger.info(f"Disk usage threshold: {DISK_USAGE_THRESHOLD}%")
    
    # Validate database connection before starting main loop
    if db_pool is None:
        logger.critical("Database connection pool failed to initialize. Please check:")
        logger.critical("1. PostgreSQL service is running")
        logger.critical("2. Database credentials in LOCAL_DB_CONFIG are correct")
        logger.critical("3. Database and tables exist (run SETUP.md)")
        logger.critical("4. Network connectivity to database host")
        exit(1)
    
    # Verify we can get a connection from the pool
    test_conn = None
    try:
        test_conn = get_local_db_connection()
        return_db_connection(test_conn)
        logger.info("Database connectivity verified")
    except Exception as e:
        logger.critical(f"Failed to verify database connectivity: {e}")
        exit(1)
    
    # Check API health before starting main loop
    if not check_api_health():
        logger.error("API server is not reachable. Please check connectivity.")
        logger.info("Make sure to set API_SERVER environment variable if API is on different host")
        logger.info("Example: export API_SERVER=192.168.1.100:8000")
    
    # Start the connection pool monitor thread as a daemon
    pool_monitor_thread = threading.Thread(target=connection_pool_monitor, daemon=True)
    pool_monitor_thread.start()
    logger.info("Started connection pool monitor thread")
    
    # Start the backup sync thread as a daemon
    sync_thread = threading.Thread(target=sync_backup_to_api, daemon=True)
    sync_thread.start()
    logger.info("Started backup sync thread")
    
    # Start the disk space monitor thread as a daemon
    disk_monitor_thread = threading.Thread(target=disk_space_monitor, daemon=True)
    disk_monitor_thread.start()
    logger.info("Started disk space monitor thread")
    
    # Main loop: continuously read sensors and send to API
    while True:
        try:
            logger.info("Starting sensor read cycle")
            ts_utc = datetime.now(timezone.utc)
            
            # Read all sensors in parallel
            sensor_data = read_all_sensors()
            
            pi_data = {
                "disk_space": sensor_data['disk_space'],
                "cpu_temp": sensor_data['cpu_temp'],
            }
            data = {
                "device_id": device_id,
                "rasp_pi": pi_data,
                "bme280": sensor_data['bme280']
            }

            json_data = json.dumps(data)

            # Send to API
            result = insert_reading(device_id, ts_utc, data)
            logger.info(f"Insert result: {result}")

            time.sleep(10)  # Read sensors every 10 seconds
        except Exception as e:
            logger.error(f"Main loop error: {e}", exc_info=True)
            time.sleep(10)


