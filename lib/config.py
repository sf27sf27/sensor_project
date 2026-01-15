"""
Configuration and constants for the sensor reading system.
"""
import os
import logging
from dotenv import load_dotenv

load_dotenv()

# Logging configuration
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "read_sensors.log")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Database configuration
LOCAL_DB_CONFIG = {
    "host": "127.0.0.1",
    "dbname": "sensors",
    "user": "sensor_user",
    "password": "strongpassword",
    "port": 5432
}

# Connection pool initialization retry settings
POOL_INIT_MAX_RETRIES = 10
POOL_INIT_RETRY_DELAY = 2  # seconds

# API configuration
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

# Disk management configuration
DISK_USAGE_THRESHOLD = 50  # Percentage (e.g., 50%)
DISK_CLEANUP_CHECK_INTERVAL = 300  # Check every 5 minutes
DELETE_STRATEGY = "stratified"  # Delete records evenly across time range

# SQL Queries
INSERT_SQL = """
INSERT INTO sensor_project.readings (device_id, ts_utc, payload)
VALUES (%s, %s, %s)
"""

SELECT_UNSYNCED_SQL = """
SELECT id, device_id, ts_utc, ts_local, payload
FROM sensor_project.readings
WHERE is_synced = FALSE
ORDER BY id ASC
"""

DELETE_SYNCED_SQL = """
DELETE FROM sensor_project.readings
WHERE id = %s
"""

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
