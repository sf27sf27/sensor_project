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


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

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


device_id = socket.gethostname()

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

    try:
        cur.execute(
        INSERT_SQL,
        (
            device_id,
            ts_utc,
            ts_local,
            json_data
            )
        )

    except Exception as e:
        logger.error(f"DB insert failed: {e}")


    with open(LOG_FILE, "a") as f:
        f.write(json_data + "\n")

    print(json_data)
    time.sleep(10)

