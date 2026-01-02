from sensors.disk_space  import read as read_disk_space
from sensors.cpu_temp  import read as read_cpu_temp
from sensors.bme280 import read as read_bme280
from datetime import datetime, timezone
import time
import json
import os
import requests
import socket
import logging
import threading


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

# API configuration - can be overridden with API_SERVER environment variable
API_SERVER = os.getenv("API_SERVER", "localhost:8000")
API_BASE_URL = f"http://{API_SERVER}"
READINGS_ENDPOINT = f"{API_BASE_URL}/readings"

# Global connection variables - initialized in main()
device_id = socket.gethostname()


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


def insert_reading(device_id, ts_utc, ts_local, json_data):
    """Send reading to API endpoint"""
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
            "ts_local": ts_local.isoformat(),
            "payload": payload
        }
        
        # Send POST request to API
        response = requests.post(
            READINGS_ENDPOINT,
            json=request_payload,
            timeout=10
        )
        
        if response.status_code == 201:
            logger.info(f"Reading successfully sent to API: {response.json()}")
            return True
        else:
            logger.error(f"API returned status {response.status_code}: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to send reading to API: {e}")
        return False
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON payload: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error sending to API: {e}")
        return False


if __name__ == "__main__":
    logger.info(f"Starting sensor reader, API endpoint: {READINGS_ENDPOINT}")
    
    # Check API health before starting main loop
    if not check_api_health():
        logger.error("API server is not reachable. Please check connectivity.")
        logger.info("Make sure to set API_SERVER environment variable if API is on different host")
        logger.info("Example: export API_SERVER=192.168.1.100:8000")
    
    # Main loop: continuously read sensors and send to API
    while True:
        try:
            logger.info("Starting sensor read cycle")
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

            # Send to API
            result = insert_reading(device_id, ts_utc, ts_local, data)
            logger.info(f"Insert result: {result}")

            time.sleep(10)  # Read sensors every 10 seconds
        except Exception as e:
            logger.error(f"Main loop error: {e}", exc_info=True)
            time.sleep(10)


