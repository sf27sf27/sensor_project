from sensors.disk_space  import read as read_disk_space
from sensors.cpu_temp  import read as read_cpu_temp
from sensors.bme280 import read as read_bme280
from datetime import datetime, timezone
import time
import json
import os
import psycopg2
from psycopg2.extras import execute_values
import socket
import logging
import threading


logger = logging.getLogger(__name__)

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "read_sensors.log")

# Configure logging to both console and file
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

LOCAL_DB_CONFIG = {
    "host": "localhost",
    "dbname": "sensors",
    "user": "sensor_user",
    "password": "strongpassword",
    "port": 5432
}

CLOUD_DB_CONFIG = {
    "host": "sensors.cjkq4ckkcwve.us-east-2.rds.amazonaws.com",
    "dbname": "sensors",
    "user": "sensor_user",
    "password": "strongpassword",
    "port": 5432,
    "sslmode": "require"
}

conn = psycopg2.connect(**CLOUD_DB_CONFIG)
conn.autocommit = True
cur = conn.cursor()

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "read_sensors.log")

INSERT_SQL = """
INSERT INTO sensor_project.readings (device_id, ts_utc, ts_local, payload)
VALUES (%s, %s, %s, %s)
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


device_id = socket.gethostname()


def get_local_db_connection():
    """Create a new connection to local database"""
    return psycopg2.connect(**LOCAL_DB_CONFIG)


def get_cloud_db_connection():
    """Create a new connection to cloud database"""
    return psycopg2.connect(**CLOUD_DB_CONFIG)


def insert_reading(device_id, ts_utc, ts_local, json_data):
    """Try to insert reading to cloud first, fall back to local DB on failure"""
    try:
        # Try cloud first
        cloud_conn = get_cloud_db_connection()
        cloud_conn.autocommit = True
        cloud_cur = cloud_conn.cursor()
        cloud_cur.execute(
            INSERT_SQL,
            (device_id, ts_utc, ts_local, json_data)
        )
        cloud_cur.close()
        cloud_conn.close()
        logger.info("Data inserted into cloud DB")
        return True
    except Exception as e:
        logger.warning(f"Cloud insert failed: {e}, falling back to local DB")
        try:
            local_conn = get_local_db_connection()
            local_conn.autocommit = True
            local_cur = local_conn.cursor()
            local_cur.execute(
                INSERT_SQL,
                (device_id, ts_utc, ts_local, json_data)
            )
            local_cur.close()
            local_conn.close()
            logger.info("Data inserted into local DB as fallback")
            return False
        except Exception as e2:
            logger.error(f"Local DB insert also failed: {e2}")
            return None


def sync_to_cloud():
    """Periodically sync unsynced records from local DB to cloud DB"""
    while True:
        try:
            local_conn = get_local_db_connection()
            local_conn.autocommit = True
            local_cur = local_conn.cursor()
            
            # Fetch unsynced records from local DB
            local_cur.execute(SELECT_UNSYNCED_SQL)
            records = local_cur.fetchall()
            
            if records:
                logger.info(f"Found {len(records)} unsynced records to upload")
                
                try:
                    cloud_conn = get_cloud_db_connection()
                    cloud_conn.autocommit = True
                    cloud_cur = cloud_conn.cursor()
                    
                    uploaded_ids = []
                    for record in records:
                        record_id, dev_id, ts_utc, ts_local, payload = record
                        try:
                            # Ensure payload is JSON string, not dict
                            if isinstance(payload, dict):
                                payload = json.dumps(payload)
                            
                            # Insert into cloud DB
                            cloud_cur.execute(
                                INSERT_SQL,
                                (dev_id, ts_utc, ts_local, payload)
                            )
                            uploaded_ids.append(record_id)
                            logger.info(f"Uploaded record {record_id} to cloud")
                        except Exception as e:
                            logger.error(f"Failed to upload record {record_id}: {e}")
                    
                    # Delete successfully uploaded records from local DB
                    for record_id in uploaded_ids:
                        try:
                            local_cur.execute(DELETE_SYNCED_SQL, (record_id,))
                            logger.info(f"Deleted record {record_id} from local DB")
                        except Exception as e:
                            logger.error(f"Failed to delete record {record_id}: {e}")
                    
                    cloud_cur.close()
                    cloud_conn.close()
                except Exception as e:
                    logger.warning(f"Cloud connection failed during sync: {e}")
            
            local_cur.close()
            local_conn.close()
            
        except Exception as e:
            logger.error(f"Sync to cloud failed: {e}")
        
        # Wait 5 seconds before next sync attempt
        time.sleep(5)


if __name__ == "__main__":
    # Start the cloud sync thread as a daemon
    sync_thread = threading.Thread(target=sync_to_cloud, daemon=True)
    sync_thread.start()
    logger.info("Started cloud sync thread")
    
    # Main loop: continuously read sensors and try cloud first, fallback to local
    while True:
        ts_utc = datetime.now(timezone.utc)
        ts_local = datetime.now().astimezone()
        dt_utc = ts_utc.isoformat()
        dt_local = ts_local.isoformat()
        try:
            disk_data = read_disk_space()
        except Exception as e:
            disk_data = {"error": str(e)}
            logger.error(f"Disk read failed: {e}")

        try:
            cpu_data = read_cpu_temp()
        except Exception as e:
            cpu_data = {"error": str(e)}
            logger.error(f"CPU read failed: {e}")

        try:
            bme280_data = read_bme280()
        except Exception as e:
            bme280_data = {"error": str(e)}
            logger.error(f"BME280 read failed: {e}")

        pi_data = {
            "disk_space": disk_data,
            "cpu_temp": cpu_data,
        }
        data = {
            "dt_utc": dt_utc,
            "dt_local": dt_local,
            "device_id": device_id,
            "rasp_pi": pi_data,
            "bme280": bme280_data
        }

        json_data = json.dumps(data)

        # Try cloud first, fallback to local
        insert_reading(device_id, ts_utc, ts_local, json_data)

        time.sleep(10)  # Read sensors every 5 seconds


